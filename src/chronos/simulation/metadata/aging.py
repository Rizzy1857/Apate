import time
import random
from typing import Dict, Any, Optional
from chronos.simulation.event_bus import EventBus, FileCreated, FileModified, FileDeleted, EventPriority
from chronos.simulation.metadata.profiles import AgingProfile, determine_profile

class MetadataAgingPlugin:
    def __init__(self, redis_client, event_bus: EventBus):
        self.redis = redis_client
        self.event_bus = event_bus
        self.boot_time = time.time() - (86400 * 7) # Faked 7 days ago
        
        # Subscribe to immediate filesystem changes to update directory mtimes
        self.event_bus.subscribe(FileCreated, self.on_file_created, EventPriority.HIGH)
        self.event_bus.subscribe(FileDeleted, self.on_file_deleted, EventPriority.HIGH)
        self.event_bus.subscribe(FileModified, self.on_file_modified, EventPriority.HIGH)
        
    def _resolve_parent_inode(self, path: str) -> Optional[int]:
        import os
        parent_path = os.path.dirname(path)
        parts = [p for p in parent_path.split('/') if p]
        current_inode = 1
        for part in parts:
            child_inode = self.redis.hget(f"fs:dentry:{current_inode}", part)
            if not child_inode:
                return None
            current_inode = int(child_inode)
        return current_inode

    def _update_parent_mtime(self, path: str, timestamp: float):
        parent_inode = self._resolve_parent_inode(path)
        if parent_inode:
            self.redis.hset(f"fs:inode:{parent_inode}", mapping={"mtime": timestamp, "ctime": timestamp})

    def on_file_created(self, event: FileCreated):
        self._update_parent_mtime(event.path, event.timestamp)
        
    def on_file_deleted(self, event: FileDeleted):
        self._update_parent_mtime(event.path, event.timestamp)
        
    def on_file_modified(self, event: FileModified):
        # Modification of a file updates the file's mtime (already handled in FUSE)
        # However, we can track directory access time if desired.
        pass

    def apply_lazy_aging(self, path: str, meta: Dict[str, Any]) -> Dict[str, Any]:
        """
        Takes raw inode metadata and mathematically applies aging/growth
        based on the World Simulation's simulated clock.
        This is called synchronously by FUSE getattr.
        """
        profile = determine_profile(path)
        current_time = time.time()
        elapsed = current_time - self.boot_time
        
        aged_meta = meta.copy()
        
        try:
            original_size = int(aged_meta.get("size", 0))
        except (ValueError, TypeError):
            return aged_meta

        if profile == AgingProfile.STATIC:
            pass 
            
        elif profile == AgingProfile.CONFIG:
            pass
            
        elif profile == AgingProfile.LOG:
            hours_uptime = elapsed / 3600
            aged_meta["size"] = str(original_size + int(hours_uptime * 1024))
            aged_meta["mtime"] = str(current_time - random.randint(10, 600))
            aged_meta["atime"] = aged_meta["mtime"]
            
        elif profile == AgingProfile.CACHE:
            fluctuation = int(original_size * 0.1)
            aged_meta["size"] = str(max(0, original_size + random.randint(-fluctuation, fluctuation)))
            aged_meta["mtime"] = str(current_time - random.randint(10, 3600))
            
        elif profile == AgingProfile.TEMP:
            aged_meta["mtime"] = str(current_time - random.randint(5, 120))
            aged_meta["atime"] = str(current_time - random.randint(1, 60))
            
        elif profile == AgingProfile.USER_DATA:
            aged_meta["mtime"] = str(current_time - random.randint(60, 14400))
            
        return aged_meta
