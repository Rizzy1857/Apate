import time
from chronos.core.database import Database

class StateHypervisor:
    def __init__(self):
        self.db = Database()
        self.redis = self.db.get_connection()

    def initialize_filesystem(self):
        """Initialize the root filesystem if it doesn't exist"""
        # Check if root inode (1) exists
        if not self.redis.exists("fs:inode:1"):
            print("Initializing root filesystem...")
            # Reset counters
            self.redis.set("fs:next_inode", 1)
            
            # Create Root Inode (1)
            timestamp = time.time()
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
            
            # Create root directory structure (loops to itself)
            # Not strictly needed for ZADD based logic unless typical unix . and ..
            self.redis.zadd("fs:dir:1", {".": 1, "..": 1})
            
            print("Filesystem initialized.")
        else:
            print("Filesystem already exists.")

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
