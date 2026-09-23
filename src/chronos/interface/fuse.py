"""FUSE callbacks over Redis state, attributed using registered worker PIDs."""

import errno
import hashlib
import os
import stat
import threading
import time
import logging
from fuse import FUSE, FuseOSError, Operations

from chronos.core.state import StateHypervisor
from chronos.core.content import mutate_content, read_blob
from chronos.core.session_cleanup import orphan_sessions, delete_namespace
from chronos.intelligence.inference import get_runtime
from chronos.intelligence.ubuntu_profile import UbuntuProfile
from chronos.intelligence.orchestrator import GenerationOrchestrator, posix_timeout_error
from chronos.simulation.orchestrator import world_simulation
from chronos.simulation.event_bus import FileCreated, FileModified, FileDeleted

# FUSE context will be resolved per-request using fuse_get_context()[2] (the caller's PID).
# The mapping PID -> session_id is maintained in Redis by the SSH gateway's SessionWorker.
from fuse import fuse_get_context



class ChronosFUSE(Operations):
    def __init__(self, root, db_layer=None):
        self.root = root
        self.db_layer = db_layer
        self._control = StateHypervisor().redis
        self.profile = UbuntuProfile()
        self._sessions = {}
        self._session_lock = threading.Lock()
        self._stop = threading.Event()
        threading.Thread(target=self._reap_sessions, daemon=True).start()

        # fd-table: fd → {session_id, inode, open_time, flags, path}
        self.fd_table: dict = {}
        self.next_fd = 10
        self._fd_lock = threading.Lock()


    # ------------------------------------------------------------------
    # Session context helpers
    # ------------------------------------------------------------------

    def _current_session_id(self) -> str:
        """Return the session_id by looking up the caller PID in Redis."""
        uid, gid, pid = fuse_get_context()
        session_id = self._control.get(f"session_pid:{pid}")
        if not session_id:
            raise FuseOSError(errno.EACCES)
        return session_id.decode("utf-8") if isinstance(session_id, bytes) else session_id

    def _session(self):
        session_id = self._current_session_id()
        import uuid
        session_id = str(uuid.UUID(session_id))
        with self._session_lock:
            if session_id not in self._sessions:
                hv = StateHypervisor(prefix=f"session:{session_id}:")
                hv.initialize_filesystem()
                generator = GenerationOrchestrator(hv.redis, self.profile, max_workers=1)
                self._sessions[session_id] = (hv, generator, fuse_get_context()[2])
            return self._sessions[session_id]

    @property
    def hv(self):
        return self._session()[0]

    @property
    def redis(self):
        return self.hv.redis

    @property
    def orchestrator(self):
        return self._session()[1]

    def _reap_sessions(self):
        while not self._stop.wait(30):
            try:
                stale = orphan_sessions(self._control)
                for session_id in stale:
                    # Never hold the global session lock while draining model jobs.
                    with self._session_lock:
                        entry = self._sessions.get(session_id)
                    if entry:
                        entry[1].close()
                    delete_namespace(self._control, session_id)
                    with self._session_lock:
                        self._sessions.pop(session_id, None)
                    with self._fd_lock:
                        self.fd_table = {fd: entry for fd, entry in self.fd_table.items()
                                         if entry['session_id'] != session_id}
            except Exception:
                logging.exception('Session namespace cleanup failed; will retry')

    def destroy(self, path):
        self._stop.set()

    def _get_machine_state(self, session_id: str) -> dict:
        """Return (and create if absent) the MachineState for this session."""
        return self.profile.get_or_create_machine_state(self.redis, session_id)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _audit(self, session_id, operation, path, inode, metadata):
        """Link kernel events to the sequential worker command, not its thread."""
        if self.db_layer is None:
            return
        command_id = self._control.get(f"session:{session_id}:active_command")
        if isinstance(command_id, bytes):
            command_id = command_id.decode('utf-8')
        self.db_layer.log_operation(session_id, operation, path, inode, {
            **metadata, 'command_id': command_id, 'schema_version': 1,
            'origin': 'participant' if command_id else 'unattributed',
        })

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

    def _refresh_world(self, path, inode):
        if path == '/var/log/syslog':
            from chronos.simulation.world_files import refresh_syslog
            if refresh_syslog(self.redis, inode) and self.db_layer:
                self.db_layer.log_operation(self._current_session_id(), 'world_file_update', path,
                                            inode, {'origin': 'synthetic', 'schema_version': 1})

    # ------------------------------------------------------------------
    # Filesystem Methods — state operations (unchanged, deterministic)
    # ------------------------------------------------------------------

    def getattr(self, path, fh=None):
        # libfuse/kernel mount setup can stat the mount root without a session.
        if path == "/" and not self._control.get(f"session_pid:{fuse_get_context()[2]}"):
            return {'st_mode': stat.S_IFDIR | 0o755, 'st_nlink': 2, 'st_size': 4096,
                    'st_uid': 0, 'st_gid': 0, 'st_ino': 1}
        inode = self._resolve_path(path)
        self._refresh_world(path, inode)
        meta = self._get_inode_meta(inode)

        # Report persisted metadata; random synthetic sizes break read/stat consistency.
        
        return {
            'st_ino': inode,
            'st_mode': int(meta['mode']),
            'st_nlink': int(meta.get('nlink', 1)),
            'st_uid': int(meta['uid']),
            'st_gid': int(meta['gid']),
            'st_size': int(meta['size']),
            'st_ctime': float(meta.get('ctime', 0)),
            'st_mtime': float(meta.get('mtime', 0)),
            'st_atime': float(meta.get('atime', 0))
        }

    def readdir(self, path, fh):
        inode = self._resolve_path(path)
        files = self.redis.zrange(f"fs:dir:{inode}", 0, -1)

        session_id = self._current_session_id()
        if self.db_layer:
            self._audit(session_id, "readdir", path, inode, {})
        return [".", ".."] + [name for name in files if name not in (".", "..")]

    def mkdir(self, path, mode):
        self._current_session_id()  # Authorize before mutation.
        parent_inode, name = self._get_parent_and_name(path)
        mode = (mode & 0o777) | stat.S_IFDIR
        try:
            inode = self.hv.atomic_mkdir(parent_inode, name, mode)
            uid, gid, _ = fuse_get_context()
            self.redis.hset(f'fs:inode:{inode}', mapping={'uid': uid, 'gid': gid})
        except FileExistsError:
            raise FuseOSError(errno.EEXIST)
            
        world_simulation.event_bus.publish(FileCreated(
            path=path,
            session_id=self._current_session_id(),
            timestamp=time.time()
        ))

    def rmdir(self, path):
        parent_inode, name = self._get_parent_and_name(path)
        session_id = self._current_session_id()
        try:
            self.hv.atomic_rmdir(parent_inode, name)
        except FileNotFoundError:
            raise FuseOSError(errno.ENOENT)
        except OSError:
            raise FuseOSError(errno.ENOTEMPTY)
            
        world_simulation.event_bus.publish(FileDeleted(
            path=path,
            session_id=session_id,
            timestamp=time.time()
        ))

    def unlink(self, path):
        parent_inode, name = self._get_parent_and_name(path)
        session_id = self._current_session_id()
        inode = self._resolve_path(path)
        
        if self.db_layer:
            self._audit(session_id, "unlink", path, inode, {})
            
        try:
            self.hv.atomic_unlink(parent_inode, name)
        except FileNotFoundError:
            raise FuseOSError(errno.ENOENT)
            
        world_simulation.event_bus.publish(FileDeleted(
            path=path,
            session_id=session_id,
            timestamp=time.time()
        ))

    def create(self, path, mode, fi=None):
        parent_inode, name = self._get_parent_and_name(path)
        session_id = self._current_session_id()
        created = False
        try:
            inode = self.hv.create_file(parent_inode, name, stat.S_IFREG | (mode & 0o7777))
            uid, gid, _ = fuse_get_context()
            self.redis.hset(f'fs:inode:{inode}', mapping={'uid': uid, 'gid': gid})
            created = True
        except FileExistsError:
            pass  # open existing

        if created:
            world_simulation.event_bus.publish(FileCreated(
                path=path,
                session_id=session_id,
                timestamp=time.time()
            ))

        fd = self.open(path, 0)
        if self.db_layer:
            self._audit(session_id, "create", path, self.fd_table[fd]["inode"], {})
        return fd

    def open(self, path, flags):
        inode = self._resolve_path(path)
        session_id = self._current_session_id()
        with self._fd_lock:
            fd = self.next_fd
            self.next_fd += 1
        self.fd_table[fd] = {
            "session_id": session_id,
            "inode":      inode,
            "open_time":  time.time(),
            "flags":      flags,
            "path":       path,
        }
        return fd

    def read(self, path, size, offset, fh):
        if fh not in self.fd_table:
            raise FuseOSError(errno.EBADF)

        entry = self.fd_table[fh]
        if entry["session_id"] != self._current_session_id():
            raise FuseOSError(errno.EACCES)
        inode = entry["inode"]
        session_id = entry["session_id"]
        self._refresh_world(path, inode)
        def completed(data):
            self._audit(session_id, "read", path, inode, {
                "requested_bytes": size, "offset": offset,
                "actual_bytes": len(data), "outcome": "completed",
            })
            return data

        meta = self._get_inode_meta(inode)
        content_hash = meta.get("content_hash")

        # Fast path: content already cached
        if content_hash:
            return completed(read_blob(self.redis, content_hash)[offset:offset + size])
        if meta.get("manifest_class", "runtime") not in ("ai_backed", "deterministic"):
            return completed(b"")

        # Cache miss: delegate to orchestrator (non-blocking, adaptive timeout)
        print(f"[FUSE] Cache miss — generating {path} (session={session_id})")
        machine_state = self._get_machine_state(session_id)

        result = self.orchestrator.get_or_generate(
            inode=inode,
            path=path,
            session_id=session_id,
            machine_state=machine_state,
        )

        if result is None:
            # Timeout — return a randomized POSIX error.
            # Generation continues in the background; next read will hit cache.
            raise FuseOSError(posix_timeout_error())

        return completed(result[offset:offset + size])

    def write(self, path, buf, offset, fh):
        if fh not in self.fd_table:
            raise FuseOSError(errno.EBADF)
        entry = self.fd_table[fh]
        if entry["session_id"] != self._current_session_id():
            raise FuseOSError(errno.EACCES)
        inode = entry["inode"]
        session_id = entry["session_id"]
        
        self._audit(session_id, "write_attempt", path, inode, {
            "requested_bytes": len(buf), "offset": offset,
        })

        mutate_content(self.redis, inode, buf=buf, offset=offset)
        self._audit(session_id, "write", path, inode, {
            "actual_bytes": len(buf), "offset": offset, "outcome": "completed",
        })

        world_simulation.event_bus.publish(FileModified(
            path=path,
            session_id=session_id,
            timestamp=time.time()
        ))
        
        return len(buf)

    def chmod(self, path, mode):
        self._current_session_id()  # Authorize before mutation.
        inode = self._resolve_path(path)
        meta = self._get_inode_meta(inode)
        self.redis.hset(f"fs:inode:{inode}", "mode", stat.S_IFMT(int(meta["mode"])) | (mode & 0o7777))
        world_simulation.event_bus.publish(FileModified(
            path=path,
            session_id=self._current_session_id(),
            timestamp=time.time()
        ))

    def chown(self, path, uid, gid):
        self._current_session_id()  # Authorize before mutation.
        inode = self._resolve_path(path)
        mapping = {}
        if uid != -1: mapping["uid"] = uid
        if gid != -1: mapping["gid"] = gid
        if mapping:
            self.redis.hset(f"fs:inode:{inode}", mapping=mapping)
            world_simulation.event_bus.publish(FileModified(
                path=path,
                session_id=self._current_session_id(),
                timestamp=time.time()
            ))

    def truncate(self, path, length, fh=None):
        self._current_session_id()  # Authorize before mutation.
        inode = self._resolve_path(path)
        mutate_content(self.redis, inode, length=length)
        world_simulation.event_bus.publish(FileModified(
            path=path,
            session_id=self._current_session_id(),
            timestamp=time.time()
        ))

    def utimens(self, path, times=None):
        self._current_session_id()
        inode = self._resolve_path(path)
        atime, mtime = times or (time.time(), time.time())
        self.redis.hset(f"fs:inode:{inode}", mapping={"atime": atime, "mtime": mtime})

    def release(self, path, fh):
        """Called when the last reference to an fd is closed."""
        self.fd_table.pop(fh, None)
        return 0
