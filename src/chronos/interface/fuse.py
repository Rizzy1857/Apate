import os
import errno
import stat
import time
import hashlib
from fuse import FUSE, FuseOSError, Operations
from chronos.core.state import StateHypervisor
from chronos.intelligence.llm import get_provider
from chronos.intelligence.persona import PersonaEngine

class ChronosFUSE(Operations):
    def __init__(self, root):
        self.root = root
        self.hv = StateHypervisor()
        self.redis = self.hv.redis
        
        # Initialize Intelligence
        self.provider = get_provider()
        self.persona_engine = PersonaEngine(self.provider)
        
        self.fd_table = {}
        self.next_fd = 10

    # Helpers
    # =======

    def _resolve_path(self, path):
        if path == "/":
            return 1
        
        parts = [p for p in path.split("/") if p]
        current_inode = 1
        
        for part in parts:
            inode = self.redis.zscore(f"fs:dir:{current_inode}", part)
            if not inode:
                raise FuseOSError(errno.ENOENT)
            current_inode = int(inode)
            
        return current_inode

    def _get_parent_and_name(self, path):
        parent_path = os.path.dirname(path)
        name = os.path.basename(path)
        parent_inode = self._resolve_path(parent_path)
        return parent_inode, name

    def _get_inode_meta(self, inode):
        meta = self.redis.hgetall(f"fs:inode:{inode}")
        if not meta:
            raise FuseOSError(errno.ENOENT)
        return meta

    # Filesystem Methods
    # ==================

    def getattr(self, path, fh=None):
        inode = self._resolve_path(path)
        meta = self._get_inode_meta(inode)
        
        st = {
            'st_mode': int(meta['mode']),
            'st_nlink': int(meta.get('nlink', 1)),
            'st_size': int(meta['size']),
            'st_atime': float(meta['atime']),
            'st_mtime': float(meta['mtime']),
            'st_ctime': float(meta['ctime']),
            'st_uid': int(meta['uid']),
            'st_gid': int(meta['gid'])
        }
        return st

    def readdir(self, path, fh):
        inode = self._resolve_path(path)
        files = self.redis.zrange(f"fs:dir:{inode}", 0, -1)
        return ['.', '..'] + files

    def mkdir(self, path, mode):
        parent_inode, name = self._get_parent_and_name(path)
        
        # Using atomic_create with S_IFDIR
        # Ensure mode has directory bit
        mode = (mode & 0o777) | stat.S_IFDIR
        
        try:
            self.hv.create_file(parent_inode, name, mode)
        except FileExistsError:
            raise FuseOSError(errno.EEXIST)
            
        # Initialize directory (dot entries) - technically atomic_create doesn't do this yet
        # But verify_phase1 showed it worked for files.
        # Ideally we should fix atomic_create to handle this or do it here.
        # atomic_create returns inode.
        # We need the inode to add . and ..
        
        # Let's verify if atomic_create handles S_IFDIR logic? The lua script was generic.
        # We need to manually add . and .. for now or update Lua.
        # Updating Lua is better, but for speed let's just get inode and add entries.
        
        inode = int(self.redis.zscore(f"fs:dir:{parent_inode}", name))
        self.redis.zadd(f"fs:dir:{inode}", {".": inode, "..": parent_inode})

    def rmdir(self, path):
        parent_inode, name = self._get_parent_and_name(path)
        inode = self._resolve_path(path)
        
        # Check empty (only . and ..)
        count = self.redis.zcard(f"fs:dir:{inode}")
        if count > 2:
            raise FuseOSError(errno.ENOTEMPTY)
            
        # Remove from parent
        self.redis.zrem(f"fs:dir:{parent_inode}", name)
        # We should also clean up inode keys, but for prototype we leak.

    def unlink(self, path):
        parent_inode, name = self._get_parent_and_name(path)
        self.redis.zrem(f"fs:dir:{parent_inode}", name)

    def create(self, path, mode, fi=None):
        parent_inode, name = self._get_parent_and_name(path)
        try:
            self.hv.create_file(parent_inode, name, mode)
        except FileExistsError:
            pass # open existing
            
        return self.open(path, 0)

    def open(self, path, flags):
        inode = self._resolve_path(path)
        fd = self.next_fd
        self.next_fd += 1
        self.fd_table[fd] = {'inode': inode, 'flags': flags, 'path': path}
        return fd

    def read(self, path, size, offset, fh):
        if fh not in self.fd_table: raise FuseOSError(errno.EBADF)
        inode = self.fd_table[fh]['inode']
        
        meta = self._get_inode_meta(inode)
        content_hash = meta.get('content_hash')
        
        # Lazy Generation Logic
        if not content_hash:
            # Check if we should generate
            # For this prototype, we'll try to generate for ANY empty file if it has a name
            # In production, we'd check a 'dynamic' flag or file extension
            
            try:
                # Generate content
                print(f"[*] Generating content for {path}...")
                filename = os.path.basename(path)
                content_str = self.persona_engine.generate_content(filename, f"File at {path}")
                content = content_str.encode('utf-8')
                
                # Persist it basically like a write
                new_hash = hashlib.sha256(content).hexdigest()
                self.redis.set(f"fs:blob:{new_hash}", content)
                
                self.redis.hset(f"fs:inode:{inode}", mapping={
                    'content_hash': new_hash,
                    'size': len(content),
                    'mtime': time.time()
                })
                
                return content[offset:offset+size]
                
            except Exception as e:
                print(f"[!] Generation failed: {e}")
                return b''
        
        blob = self.redis.get(f"fs:blob:{content_hash}")
        if not blob: return b''
        
        if isinstance(blob, str): blob = blob.encode('utf-8')
        return blob[offset:offset+size]

    def write(self, path, buf, offset, fh):
        if fh not in self.fd_table: raise FuseOSError(errno.EBADF)
        inode = self.fd_table[fh]['inode']
        
        # Read full content
        meta = self._get_inode_meta(inode)
        content_hash = meta.get('content_hash')
        current_content = b''
        if content_hash:
            val = self.redis.get(f"fs:blob:{content_hash}")
            if val:
                current_content = val.encode('utf-8') if isinstance(val, str) else val
        
        # Apply patch
        # Handle sparse files? Nah.
        if offset > len(current_content):
            current_content += b'\x00' * (offset - len(current_content))
        
        new_content = current_content[:offset] + buf + current_content[offset+len(buf):]
        
        # Store new blob
        new_hash = hashlib.sha256(new_content).hexdigest()
        self.redis.set(f"fs:blob:{new_hash}", new_content)
        
        # Update inode
        self.redis.hset(f"fs:inode:{inode}", mapping={
            'content_hash': new_hash,
            'size': len(new_content),
            'mtime': time.time()
        })
        
        return len(buf)

    def chmod(self, path, mode):
        inode = self._resolve_path(path)
        self.redis.hset(f"fs:inode:{inode}", 'mode', mode)

    def chown(self, path, uid, gid):
        inode = self._resolve_path(path)
        mapping = {}
        if uid != -1: mapping['uid'] = uid
        if gid != -1: mapping['gid'] = gid
        self.redis.hset(f"fs:inode:{inode}", mapping=mapping)

    def truncate(self, path, length, fh=None):
        inode = self._resolve_path(path)
        # Simplistic truncate
        self.redis.hset(f"fs:inode:{inode}", mapping={'size': length, 'mtime': time.time()})
        # Note: Doesn't actually truncate blob content for now
