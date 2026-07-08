"""
fuse.py
-------
ChronosFUSE — the FUSE filesystem interface for Chronos.

Key changes in Phase 2:
  - fd-table entries extended to {session_id, inode, open_time, flags, path}
  - read() delegates to GenerationOrchestrator (non-blocking, adaptive timeout)
  - create() fires background generation (fire-and-forget, HIGH priority)
  - readdir() triggers bounded prewarm for high-priority children
  - Session ID is injected from the SSH gateway via threading.local()
    (never read from /proc — a session, not a process, is the identity)

Unchanged: getattr, mkdir, rmdir, unlink, write, chmod, chown, truncate,
           atomic Lua scripts, inode allocation.
"""

import errno
import hashlib
import os
import stat
import threading
import time
from fuse import FUSE, FuseOSError, Operations

from chronos.core.state import StateHypervisor
from chronos.intelligence.inference import get_runtime
from chronos.intelligence.ubuntu_profile import UbuntuProfile
from chronos.intelligence.orchestrator import GenerationOrchestrator, posix_timeout_error

# Thread-local storage for session context injection from the SSH gateway.
# Usage: fuse_context.session_id = <str>
# This is set by SSHSession before every FUSE-touching command.
fuse_context = threading.local()

_PREWARM_LIMIT = 5  # max children to prewarm per readdir()


class ChronosFUSE(Operations):
    def __init__(self, root):
        self.root = root
        self.hv = StateHypervisor()
        self.redis = self.hv.redis

        # Ubuntu profile and MachineState
        self.profile = UbuntuProfile()

        # Generation orchestrator (non-blocking)
        runtime = get_runtime()
        self.orchestrator = GenerationOrchestrator(
            redis_client=self.redis,
            profile=self.profile,
            runtime=runtime,
        )

        # fd-table: fd → {session_id, inode, open_time, flags, path}
        self.fd_table: dict = {}
        self.next_fd = 10
        self._fd_lock = threading.Lock()

    # ------------------------------------------------------------------
    # Session context helpers
    # ------------------------------------------------------------------

    def _current_session_id(self) -> str:
        """Return the session_id injected by the SSH gateway, or a fallback."""
        return getattr(fuse_context, "session_id", "unknown")

    def _get_machine_state(self, session_id: str) -> dict:
        """Return (and create if absent) the MachineState for this session."""
        return self.profile.get_or_create_machine_state(self.redis, session_id)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

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

    # ------------------------------------------------------------------
    # Filesystem Methods — state operations (unchanged, deterministic)
    # ------------------------------------------------------------------

    def getattr(self, path, fh=None):
        inode = self._resolve_path(path)
        meta = self._get_inode_meta(inode)
        return {
            "st_mode":  int(meta["mode"]),
            "st_nlink": int(meta.get("nlink", 1)),
            "st_size":  int(meta["size"]),
            "st_atime": float(meta["atime"]),
            "st_mtime": float(meta["mtime"]),
            "st_ctime": float(meta["ctime"]),
            "st_uid":   int(meta["uid"]),
            "st_gid":   int(meta["gid"]),
        }

    def readdir(self, path, fh):
        inode = self._resolve_path(path)
        files = self.redis.zrange(f"fs:dir:{inode}", 0, -1)

        # Bounded prewarm: submit background generation for ungenerated children
        session_id = self._current_session_id()
        machine_state = self._get_machine_state(session_id)
        prewarm_count = 0

        for name in files:
            if prewarm_count >= _PREWARM_LIMIT:
                break
            child_path = os.path.join(path, name)
            child_inode_score = self.redis.zscore(f"fs:dir:{inode}", name)
            if child_inode_score is None:
                continue
            child_inode = int(child_inode_score)
            child_meta = self.redis.hgetall(f"fs:inode:{child_inode}")
            if child_meta and not child_meta.get("content_hash"):
                self.orchestrator.submit_background(
                    inode=child_inode,
                    path=child_path,
                    session_id=session_id,
                    machine_state=machine_state,
                )
                prewarm_count += 1

        return [".", ".."] + files

    def mkdir(self, path, mode):
        parent_inode, name = self._get_parent_and_name(path)
        mode = (mode & 0o777) | stat.S_IFDIR
        try:
            self.hv.create_file(parent_inode, name, mode)
        except FileExistsError:
            raise FuseOSError(errno.EEXIST)
        inode = int(self.redis.zscore(f"fs:dir:{parent_inode}", name))
        self.redis.zadd(f"fs:dir:{inode}", {"." : inode, "..": parent_inode})

    def rmdir(self, path):
        parent_inode, name = self._get_parent_and_name(path)
        inode = self._resolve_path(path)
        count = self.redis.zcard(f"fs:dir:{inode}")
        if count > 2:
            raise FuseOSError(errno.ENOTEMPTY)
        self.redis.zrem(f"fs:dir:{parent_inode}", name)

    def unlink(self, path):
        parent_inode, name = self._get_parent_and_name(path)
        self.redis.zrem(f"fs:dir:{parent_inode}", name)

    def create(self, path, mode, fi=None):
        parent_inode, name = self._get_parent_and_name(path)
        try:
            self.hv.create_file(parent_inode, name, mode)
        except FileExistsError:
            pass  # open existing

        # Fire-and-forget background generation (HIGH priority)
        fd = self.open(path, 0)
        entry = self.fd_table[fd]
        session_id = entry["session_id"]
        machine_state = self._get_machine_state(session_id)
        self.orchestrator.submit_background(
            inode=entry["inode"],
            path=path,
            session_id=session_id,
            machine_state=machine_state,
            priority=1,  # PRIORITY_HIGH
        )
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
        inode = entry["inode"]
        session_id = entry["session_id"]

        meta = self._get_inode_meta(inode)
        content_hash = meta.get("content_hash")

        # Fast path: content already cached
        if content_hash:
            blob = self.redis.get(f"fs:blob:{content_hash}")
            if blob:
                if isinstance(blob, str):
                    blob = blob.encode("utf-8")
                return blob[offset:offset + size]

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

        return result[offset:offset + size]

    def write(self, path, buf, offset, fh):
        if fh not in self.fd_table:
            raise FuseOSError(errno.EBADF)
        inode = self.fd_table[fh]["inode"]

        meta = self._get_inode_meta(inode)
        content_hash = meta.get("content_hash")
        current_content = b""
        if content_hash:
            val = self.redis.get(f"fs:blob:{content_hash}")
            if val:
                current_content = val.encode("utf-8") if isinstance(val, str) else val

        if offset > len(current_content):
            current_content += b"\x00" * (offset - len(current_content))

        new_content = current_content[:offset] + buf + current_content[offset + len(buf):]
        new_hash = hashlib.sha256(new_content).hexdigest()
        self.redis.set(f"fs:blob:{new_hash}", new_content)
        self.redis.hset(f"fs:inode:{inode}", mapping={
            "content_hash": new_hash,
            "size": len(new_content),
            "mtime": time.time(),
        })
        return len(buf)

    def chmod(self, path, mode):
        inode = self._resolve_path(path)
        self.redis.hset(f"fs:inode:{inode}", "mode", mode)

    def chown(self, path, uid, gid):
        inode = self._resolve_path(path)
        mapping = {}
        if uid != -1: mapping["uid"] = uid
        if gid != -1: mapping["gid"] = gid
        if mapping:
            self.redis.hset(f"fs:inode:{inode}", mapping=mapping)

    def truncate(self, path, length, fh=None):
        inode = self._resolve_path(path)
        self.redis.hset(f"fs:inode:{inode}", mapping={"size": length, "mtime": time.time()})

    def release(self, path, fh):
        """Called when the last reference to an fd is closed."""
        self.fd_table.pop(fh, None)
        return 0
