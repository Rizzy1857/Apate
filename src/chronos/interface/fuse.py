"""FUSE callbacks over Redis state, attributed using registered worker PIDs."""

import errno
import hashlib
import os
import stat
import threading
import time
import logging
import uuid
from fuse import FUSE, FuseOSError, Operations

from chronos.core.state import StateHypervisor
from chronos.core.content import mutate_content, read_blob
from chronos.core.research_runs import namespace_prefix
from chronos.core.session_cleanup import (
    acknowledge_disconnect,
    delete_namespace,
    orphan_sessions,
    prepare_disconnect,
)
from chronos.core.mutation_journal import (
    acknowledge as acknowledge_mutation,
    add_to_pipeline as add_mutation_to_pipeline,
    journal_mapping,
    pending as pending_mutations,
)
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
                hv = StateHypervisor(prefix=namespace_prefix(self._control, session_id))
                hv.initialize_filesystem()
                self._reconcile_mutations(session_id, hv)
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
                        self._reconcile_mutations(session_id, entry[0])
                    elif self.db_layer is not None:
                        recovered = StateHypervisor(prefix=namespace_prefix(self._control, session_id))
                        self._reconcile_mutations(session_id, recovered)
                    if self.db_layer is not None:
                        lifecycle = prepare_disconnect(
                            self._control, session_id,
                            outcome="interrupted", reason="orphaned_session",
                        )
                        if lifecycle:
                            self.db_layer.log_operation(
                                session_id, "ssh_disconnect", "", 0, lifecycle
                            )
                            acknowledge_disconnect(self._control, session_id)
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

    def _audit(self, session_id, operation, path, inode, metadata):
        """Correlate kernel callbacks with the active sequential SSH command."""
        if self.db_layer is None:
            return
        command_id = self._control.get(f"session:{session_id}:active_command")
        if isinstance(command_id, bytes):
            command_id = command_id.decode("utf-8")
        origin = self._control.get(f"session:{session_id}:active_command_origin")
        if isinstance(origin, bytes):
            origin = origin.decode("utf-8")
        if not command_id or origin not in ("participant", "scripted_test"):
            origin = "unattributed"
        recorded_command_id = metadata.get("command_id", command_id)
        recorded_origin = metadata.get("origin")
        if recorded_origin not in ("participant", "scripted_test", "unattributed"):
            recorded_origin = origin
        self.db_layer.log_operation(session_id, operation, path, inode, {
            **metadata,
            "command_id": recorded_command_id,
            "schema_version": 1,
            "origin": recorded_origin,
        })

    def _new_mutation(self, session_id, operation, path):
        command_id = self._control.get(f"session:{session_id}:active_command")
        origin = self._control.get(f"session:{session_id}:active_command_origin")
        if isinstance(command_id, bytes):
            command_id = command_id.decode("utf-8")
        if isinstance(origin, bytes):
            origin = origin.decode("utf-8")
        if origin not in ("participant", "scripted_test"):
            origin = "unattributed"
        record = journal_mapping(
            str(uuid.uuid4()), operation, path, command_id, origin
        )
        record["session_id"] = session_id
        return record

    def _audit_completed_mutation(self, session_id, journal, inode, metadata=None):
        stored = self.redis.hgetall(f"fs:mutation:{journal['operation_id']}")
        if not stored:
            raise OSError(errno.EIO, "Mutation journal missing after state change")
        completed = {
            "operation_id": journal["operation_id"],
            "completed_at": float(stored["completed_at"]),
            "outcome": "completed",
            "command_id": journal.get("command_id"),
            "origin": journal.get("origin", "unattributed"),
        }
        self._audit(session_id, journal["operation"], journal["path"], inode, completed)
        acknowledge_mutation(self.redis, journal["operation_id"])

    def _reconcile_mutations(self, session_id, hv):
        if self.db_layer is None:
            return
        for record in pending_mutations(hv.redis):
            metadata = {
                "operation_id": record["operation_id"],
                "completed_at": float(record["completed_at"]),
                "outcome": "completed",
                "command_id": record.get("command_id") or None,
                "origin": record.get("origin", "unattributed"),
            }
            self._audit(
                record.get("session_id") or session_id, record["operation"], record["path"],
                int(float(record.get("inode", 0))), metadata,
            )
            acknowledge_mutation(hv.redis, record["operation_id"])

    def _audit_failure(self, session_id, operation, path, inode, error_number,
                       *, state_may_have_changed=False, journal=None):
        self._audit(session_id, f"{operation}_result", path, inode, {
            "outcome": "failed",
            "errno": error_number,
            "reason": os.strerror(error_number),
            "state_may_have_changed": state_may_have_changed,
            **({"operation_id": journal["operation_id"]} if journal else {}),
        })

    def _refresh_world(self, path, inode):
        if path == "/var/log/syslog":
            from chronos.simulation.world_files import refresh_syslog
            if refresh_syslog(self.redis, inode) and self.db_layer:
                self.db_layer.log_operation(
                    self._current_session_id(), "world_file_update", path, inode,
                    {"origin": "synthetic", "schema_version": 1},
                )

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
        session_id = self._current_session_id()
        journal = self._new_mutation(session_id, "mkdir", path)
        mode = (mode & 0o777) | stat.S_IFDIR
        self._audit(session_id, "mkdir_attempt", path, 0, {
            "mode": mode, "operation_id": journal["operation_id"],
        })
        inode = 0
        try:
            parent_inode, name = self._get_parent_and_name(path)
            uid, gid, _ = fuse_get_context()
            inode = self.hv.atomic_mkdir(
                parent_inode, name, mode, uid=uid, gid=gid, journal=journal
            )
        except FileExistsError:
            self._audit_failure(session_id, "mkdir", path, inode, errno.EEXIST,
                                journal=journal)
            raise FuseOSError(errno.EEXIST)
        except OSError as exc:
            error_number = exc.errno or errno.EIO
            self._audit_failure(session_id, "mkdir", path, inode, error_number,
                                state_may_have_changed=bool(inode), journal=journal)
            raise

        self._audit_completed_mutation(session_id, journal, inode, {"mode": mode})

        world_simulation.event_bus.publish(FileCreated(
            path=path,
            session_id=session_id,
            timestamp=time.time()
        ))

    def rmdir(self, path):
        session_id = self._current_session_id()
        journal = self._new_mutation(session_id, "rmdir", path)
        self._audit(session_id, "rmdir_attempt", path, 0, {
            "operation_id": journal["operation_id"],
        })
        inode = 0
        try:
            parent_inode, name = self._get_parent_and_name(path)
            inode = self._resolve_path(path)
            self.hv.atomic_rmdir(parent_inode, name, journal=journal)
        except FileNotFoundError:
            self._audit_failure(session_id, "rmdir", path, inode, errno.ENOENT,
                                journal=journal)
            raise FuseOSError(errno.ENOENT)
        except OSError as exc:
            error_number = exc.errno or errno.ENOTEMPTY
            self._audit_failure(session_id, "rmdir", path, inode, error_number,
                                journal=journal)
            raise FuseOSError(error_number)

        self._audit_completed_mutation(session_id, journal, inode)
            
        world_simulation.event_bus.publish(FileDeleted(
            path=path,
            session_id=session_id,
            timestamp=time.time()
        ))

    def unlink(self, path):
        session_id = self._current_session_id()
        journal = self._new_mutation(session_id, "unlink", path)
        self._audit(session_id, "unlink_attempt", path, 0, {
            "operation_id": journal["operation_id"],
        })
        inode = 0
        try:
            parent_inode, name = self._get_parent_and_name(path)
            inode = self._resolve_path(path)
            self.hv.atomic_unlink(parent_inode, name, journal=journal)
        except FileNotFoundError:
            self._audit_failure(session_id, "unlink", path, inode, errno.ENOENT,
                                journal=journal)
            raise FuseOSError(errno.ENOENT)
        except OSError as exc:
            error_number = exc.errno or errno.EIO
            self._audit_failure(session_id, "unlink", path, inode, error_number,
                                journal=journal)
            raise FuseOSError(error_number)

        self._audit_completed_mutation(session_id, journal, inode)

        world_simulation.event_bus.publish(FileDeleted(
            path=path,
            session_id=session_id,
            timestamp=time.time()
        ))

    def create(self, path, mode, fi=None):
        session_id = self._current_session_id()
        journal = self._new_mutation(session_id, "create", path)
        requested_mode = stat.S_IFREG | (mode & 0o7777)
        self._audit(session_id, "create_attempt", path, 0, {
            "mode": requested_mode, "operation_id": journal["operation_id"],
        })
        created = False
        inode = 0
        try:
            parent_inode, name = self._get_parent_and_name(path)
            uid, gid, _ = fuse_get_context()
            inode = self.hv.create_file(
                parent_inode, name, requested_mode, uid=uid, gid=gid,
                journal=journal,
            )
            created = True
        except FileExistsError:
            inode = self._resolve_path(path)
        except OSError as exc:
            error_number = exc.errno or errno.EIO
            self._audit_failure(session_id, "create", path, inode, error_number,
                                state_may_have_changed=bool(inode), journal=journal)
            raise

        if created:
            world_simulation.event_bus.publish(FileCreated(
                path=path,
                session_id=session_id,
                timestamp=time.time()
            ))

        try:
            fd = self.open(path, 0)
        except OSError as exc:
            error_number = exc.errno or errno.EIO
            self._audit_failure(session_id, "create", path, inode, error_number,
                                state_may_have_changed=created,
                                journal=journal if created else None)
            raise
        if created:
            self._audit_completed_mutation(session_id, journal, inode)
        else:
            self._audit(session_id, "create_result", path, inode, {
                "outcome": "completed", "created": False,
            })
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
        
        journal = self._new_mutation(session_id, "write", path)
        self._audit(session_id, "write_attempt", path, inode, {
            "requested_bytes": len(buf), "offset": offset,
            "operation_id": journal["operation_id"],
        })

        try:
            mutate_content(
                self.redis, inode, buf=buf, offset=offset, journal=journal
            )
        except OSError as exc:
            error_number = exc.errno or errno.EIO
            self._audit_failure(
                session_id, "write", path, inode, error_number, journal=journal
            )
            raise
        self._audit_completed_mutation(session_id, journal, inode)

        world_simulation.event_bus.publish(FileModified(
            path=path,
            session_id=session_id,
            timestamp=time.time()
        ))
        
        return len(buf)

    def chmod(self, path, mode):
        session_id = self._current_session_id()
        journal = self._new_mutation(session_id, "chmod", path)
        self._audit(session_id, "chmod_attempt", path, 0, {
            "requested_mode": mode, "operation_id": journal["operation_id"],
        })
        inode = 0
        try:
            inode = self._resolve_path(path)
            meta = self._get_inode_meta(inode)
            old_mode = int(meta["mode"])
            new_mode = stat.S_IFMT(old_mode) | (mode & 0o7777)
            completed = {**journal, "inode": inode, "completed_at": time.time()}
            with self.redis.pipeline() as pipe:
                pipe.multi()
                pipe.hset(f"fs:inode:{inode}", "mode", new_mode)
                add_mutation_to_pipeline(pipe, completed)
                pipe.execute()
        except OSError as exc:
            error_number = exc.errno or errno.EIO
            self._audit_failure(
                session_id, "chmod", path, inode, error_number, journal=journal
            )
            raise
        self._audit_completed_mutation(session_id, journal, inode)
        world_simulation.event_bus.publish(FileModified(
            path=path,
            session_id=session_id,
            timestamp=time.time()
        ))

    def chown(self, path, uid, gid):
        session_id = self._current_session_id()
        journal = self._new_mutation(session_id, "chown", path)
        self._audit(session_id, "chown_attempt", path, 0, {
            "requested_uid": uid, "requested_gid": gid,
            "operation_id": journal["operation_id"],
        })
        inode = 0
        try:
            inode = self._resolve_path(path)
            meta = self._get_inode_meta(inode)
            mapping = {}
            if uid != -1: mapping["uid"] = uid
            if gid != -1: mapping["gid"] = gid
            if mapping:
                completed = {**journal, "inode": inode, "completed_at": time.time()}
                with self.redis.pipeline() as pipe:
                    pipe.multi()
                    pipe.hset(f"fs:inode:{inode}", mapping=mapping)
                    add_mutation_to_pipeline(pipe, completed)
                    pipe.execute()
        except OSError as exc:
            error_number = exc.errno or errno.EIO
            self._audit_failure(
                session_id, "chown", path, inode, error_number, journal=journal
            )
            raise
        if mapping:
            self._audit_completed_mutation(session_id, journal, inode)
            world_simulation.event_bus.publish(FileModified(
                path=path, session_id=session_id, timestamp=time.time()
            ))
        else:
            self._audit(session_id, "chown_result", path, inode, {
                "outcome": "completed", "changed": False,
            })

    def truncate(self, path, length, fh=None):
        session_id = self._current_session_id()
        journal = self._new_mutation(session_id, "truncate", path)
        self._audit(session_id, "truncate_attempt", path, 0, {
            "requested_length": length, "operation_id": journal["operation_id"],
        })
        inode = 0
        try:
            inode = self._resolve_path(path)
            mutate_content(self.redis, inode, length=length, journal=journal)
        except OSError as exc:
            error_number = exc.errno or errno.EIO
            self._audit_failure(
                session_id, "truncate", path, inode, error_number, journal=journal
            )
            raise
        self._audit_completed_mutation(session_id, journal, inode)
        world_simulation.event_bus.publish(FileModified(
            path=path,
            session_id=session_id,
            timestamp=time.time()
        ))

    def utimens(self, path, times=None):
        session_id = self._current_session_id()
        journal = self._new_mutation(session_id, "utimens", path)
        self._audit(session_id, "utimens_attempt", path, 0, {
            "operation_id": journal["operation_id"],
        })
        inode = 0
        try:
            inode = self._resolve_path(path)
            self._get_inode_meta(inode)
            atime, mtime = times or (time.time(), time.time())
            completed = {**journal, "inode": inode, "completed_at": time.time()}
            with self.redis.pipeline() as pipe:
                pipe.multi()
                pipe.hset(
                    f"fs:inode:{inode}", mapping={"atime": atime, "mtime": mtime}
                )
                add_mutation_to_pipeline(pipe, completed)
                pipe.execute()
        except OSError as exc:
            error_number = exc.errno or errno.EIO
            self._audit_failure(
                session_id, "utimens", path, inode, error_number, journal=journal
            )
            raise
        self._audit_completed_mutation(session_id, journal, inode)

    def release(self, path, fh):
        """Called when the last reference to an fd is closed."""
        self.fd_table.pop(fh, None)
        return 0
