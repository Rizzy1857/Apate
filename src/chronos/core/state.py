import time
from chronos.core.database import Database

class StateHypervisor:
    def __init__(self):
        self.db = Database()
        self.redis = self.db.get_connection()

    def initialize_filesystem(self):
        """Initialize the root filesystem from the manifest if it doesn't exist"""
        if not self.redis.exists("fs:inode:1"):
            print("Initializing root filesystem from manifest...")
            self.redis.set("fs:next_inode", 1)
            timestamp = time.time()
            
            # Create Root Inode (1)
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
            
            # Load manifest
            from chronos.intelligence.ubuntu_profile import UbuntuProfile
            import os
            profile = UbuntuProfile()
            manifest = profile.filesystem_manifest
            
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
                    print(f"[State] Warning: Parent directory for {path} not found.")
                    continue
                    
                entry_type = entry.get("type", "file")
                entry_class = entry.get("class", "static")
                
                if entry_type == "directory":
                    try:
                        self.atomic_mkdir(parent_inode, name)
                    except FileExistsError:
                        pass
                else:
                    try:
                        inode = self.create_file(parent_inode, name)
                        # Mark content_state for the orchestrator
                        content_state = "missing" if entry_class in ["ai_backed", "deterministic"] else "static"
                        self.redis.hset(f"fs:inode:{inode}", mapping={
                            "content_state": content_state,
                            "manifest_class": entry_class
                        })
                    except FileExistsError:
                        pass
                        
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

    def create_file(self, parent_inode: int, filename: str, mode: int = 33188):
        """
        Create a new file in the given parent directory.
        Default mode: 0100644 (Regular file + 644)
        """
        timestamp = time.time()
        result = self.db.run_script(
            "atomic_create", 
            keys=[], 
            args=[parent_inode, filename, mode, timestamp]
        )
        
        if result == -1:
            raise FileExistsError(f"File {filename} already exists")
        
        return result

    def atomic_mkdir(self, parent_inode: int, filename: str, mode: int = 16877):
        """
        Create a new directory in the given parent directory.
        Default mode: 040755 (Directory + 755)
        """
        timestamp = time.time()
        result = self.db.run_script(
            "atomic_mkdir",
            keys=[],
            args=[parent_inode, filename, mode, timestamp]
        )
        
        if result == -1:
            raise FileExistsError(f"Directory {filename} already exists")
            
        return result

    def atomic_unlink(self, parent_inode: int, filename: str):
        """
        Atomically unlink a file and clean up its inode/blob if nlink is 0.
        """
        result = self.db.run_script(
            "atomic_unlink",
            keys=[],
            args=[parent_inode, filename]
        )
        
        if result == -1:
            raise FileNotFoundError(f"File {filename} not found in directory {parent_inode}")
            
        return result

    def atomic_rmdir(self, parent_inode: int, filename: str):
        """
        Atomically remove an empty directory.
        """
        result = self.db.run_script(
            "atomic_rmdir",
            keys=[],
            args=[parent_inode, filename]
        )
        
        if result == -1:
            raise FileNotFoundError(f"Directory {filename} not found in directory {parent_inode}")
        if result == -2:
            raise OSError("Directory not empty")
            
        return result
