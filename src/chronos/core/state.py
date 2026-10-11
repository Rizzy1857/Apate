import os
import time
from chronos.core.database import Database

class StateHypervisor:
    def __init__(self, prefix=None):
        self.db = Database(prefix=prefix)
        self.redis = self.db.get_connection()

    def initialize_filesystem(self, artifact_treatment=None):
        treatment = artifact_treatment or os.environ.get(
            "CHRONOS_ARTIFACT_TREATMENT", "deterministic"
        )
        if treatment not in ("deterministic", "prepared"):
            raise ValueError(
                "CHRONOS_ARTIFACT_TREATMENT must be 'deterministic' or 'prepared'"
            )
        with self.redis.lock("fs:initialize", timeout=30, blocking_timeout=5):
            self._initialize_filesystem(artifact_treatment=treatment)

    def _initialize_filesystem(self, artifact_treatment="deterministic"):
        """Initialize the root filesystem from the manifest if it doesn't exist"""
        if not self.redis.exists("fs:initialized"):
            from chronos.intelligence.ubuntu_profile import UbuntuProfile
            from chronos.intelligence.prepared_artifacts import (
                bundle_key,
                install,
                load_bundle,
            )

            profile = UbuntuProfile()
            manifest = profile.filesystem_manifest
            prepared = {}
            if artifact_treatment == "prepared":
                prepared = load_bundle(self.redis.get(bundle_key(profile)))
                if not prepared:
                    raise RuntimeError(
                        "Prepared artifact treatment selected but no current bundle exists"
                    )
                required = {
                    entry["path"] for entry in manifest.get("entries", [])
                    if entry.get("class") == "ai_backed"
                }
                missing = sorted(required - set(prepared))
                if missing:
                    raise RuntimeError(
                        f"Prepared artifact bundle is incomplete: {missing}"
                    )

            print("Initializing root filesystem from manifest...")
            self.redis.set("fs:next_inode", 1, nx=True)
            timestamp = time.time()
            
            # Create Root Inode (1)
            if not self.redis.exists("fs:inode:1"):
                self.redis.hset("fs:inode:1", mapping={
                    "mode": 16877,  # 040755 (Dir + 755)
                    "uid": 0,
                    "gid": 0,
                    "size": 4096,
                    "ctime": timestamp,
                    "mtime": timestamp,
                    "atime": timestamp,
                    "nlink": 2
                })
            self.redis.zadd("fs:dir:1", {".": 1, "..": 1})
            
            # Sort entries by depth to ensure parent directories are created first
            entries = sorted(manifest.get("entries", []), key=lambda x: len(x["path"].split("/")))
            
            for entry in entries:
                path = entry["path"]
                if path == "/":
                    continue
                    
                parent_path = os.path.dirname(path)
                name = os.path.basename(path)
                
                parent_inode = self._resolve_path_sync(parent_path)
                if not parent_inode:
                    raise ValueError(f'Manifest parent directory missing for {path}')
                    
                entry_type = entry.get("type", "file")
                entry_class = entry.get("class", "static")
                
                if entry_type == "directory":
                    try:
                        inode = self.atomic_mkdir(parent_inode, name)
                    except FileExistsError:
                        inode = self._resolve_path_sync(path)
                else:
                    try:
                        inode = self.create_file(parent_inode, name)
                    except FileExistsError:
                        inode = self._resolve_path_sync(path)
                    # Resume a creation interrupted before its classification was written.
                    content_state = "missing" if entry_class in ["ai_backed", "deterministic"] else "static"
                    self.redis.hsetnx(f"fs:inode:{inode}", "content_state", content_state)
                    self.redis.hsetnx(f"fs:inode:{inode}", "manifest_class", entry_class)
                    if entry_class == 'ai_backed' and path in prepared:
                        install(self.redis, inode, prepared[path])
                # Apply profile ownership during baseline initialization only.
                user_home = f"/home/{profile.primary_user}"
                user_owned = path == user_home or path.startswith(user_home + "/")
                uid = int(entry.get('uid', 1000 if user_owned else 0))
                gid = int(entry.get('gid', 1000 if user_owned else 0))
                default_mode = 0o755 if entry_type == 'directory' else 0o644
                if path == '/tmp':
                    default_mode = 0o1777
                elif path in ('/root', user_home + '/.ssh'):
                    default_mode = 0o700
                mode = int(str(entry['mode']), 8) if 'mode' in entry else default_mode
                self.redis.hset(f"fs:inode:{inode}", mapping={
                    'uid': uid, 'gid': gid,
                    'mode': (0o40000 if entry_type == 'directory' else 0o100000) | mode
                })
                        
            self.redis.set("fs:initialized", "1")
            print("Filesystem initialized from manifest.")
        else:
            print("Filesystem already exists.")

    def _resolve_path_sync(self, path):
        """Helper to resolve a path to an inode synchronously"""
        if path == "/":
            return 1
        parts = [p for p in path.split("/") if p]
        current_inode = 1
        for part in parts:
            inode = self.redis.zscore(f"fs:dir:{current_inode}", part)
            if not inode:
                return None
            current_inode = int(inode)
        return current_inode

    def create_file(self, parent_inode: int, filename: str, mode: int = 33188,
                    uid: int = 0, gid: int = 0, journal=None):
        """
        Create a new file in the given parent directory.
        Default mode: 0100644 (Regular file + 644)
        """
        timestamp = time.time()
        result = self.db.run_script(
            "atomic_create", 
            keys=[], 
            args=[parent_inode, filename, mode, timestamp, uid, gid]
            + self._journal_args(journal)
        )
        
        if result == -1:
            raise FileExistsError(f"File {filename} already exists")
        
        return result

    def atomic_mkdir(self, parent_inode: int, filename: str, mode: int = 16877,
                     uid: int = 0, gid: int = 0, journal=None):
        """
        Create a new directory in the given parent directory.
        Default mode: 040755 (Directory + 755)
        """
        timestamp = time.time()
        result = self.db.run_script(
            "atomic_mkdir",
            keys=[],
            args=[parent_inode, filename, mode, timestamp, uid, gid]
            + self._journal_args(journal)
        )
        
        if result == -1:
            raise FileExistsError(f"Directory {filename} already exists")
            
        return result

    def atomic_unlink(self, parent_inode: int, filename: str, journal=None):
        """
        Atomically unlink a file and clean up its inode/blob if nlink is 0.
        """
        result = self.db.run_script(
            "atomic_unlink",
            keys=[],
            args=[parent_inode, filename] + self._journal_args(journal)
        )
        
        if result == -1:
            raise FileNotFoundError(f"File {filename} not found in directory {parent_inode}")
            
        return result

    def atomic_rmdir(self, parent_inode: int, filename: str, journal=None):
        """
        Atomically remove an empty directory.
        """
        result = self.db.run_script(
            "atomic_rmdir",
            keys=[],
            args=[parent_inode, filename] + self._journal_args(journal)
        )
        
        if result == -1:
            raise FileNotFoundError(f"Directory {filename} not found in directory {parent_inode}")
        if result == -2:
            raise OSError("Directory not empty")
            
        return result

    @staticmethod
    def _journal_args(journal):
        if not journal:
            return []
        return [
            journal["operation_id"], journal["operation"], journal["path"],
            journal.get("command_id") or "", journal.get("origin") or "unattributed",
        ]
