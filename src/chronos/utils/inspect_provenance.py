#!/usr/bin/env python3
import sys
import redis
import json
import datetime
from typing import Optional, Dict

def inspect_provenance(path: str):
    r = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)
    
    # 1. Resolve path to inode via the State Hypervisor tree.
    # The honeypot root is an inode 1, but resolving paths requires walking the tree.
    # Since this is a simple utility, we'll fetch all inodes to find a match.
    # In a real tool we'd use the FUSE path resolution logic, but this is a debug CLI.
    # Actually, a simpler way for debugging is to look up the path in fs:dentry:*
    
    parts = [p for p in path.split('/') if p]
    current_inode = 1
    
    for part in parts:
        dentry_key = f"fs:dentry:{current_inode}"
        child_inode = r.hget(dentry_key, part)
        if not child_inode:
            print(f"Error: Path '{path}' not found at component '{part}'")
            return
        current_inode = int(child_inode)
        
    # 2. Get the blob hash
    inode_meta = r.hgetall(f"fs:inode:{current_inode}")
    if not inode_meta:
        print(f"Error: Inode {current_inode} missing metadata")
        return
        
    blob_hash = inode_meta.get("content_hash")
    if not blob_hash:
        print(f"Error: No content_hash for inode {current_inode}")
        return
        
    # 3. Get provenance
    meta = r.hgetall(f"fs:blob_meta:{blob_hash}")
    
    if not meta:
        print(f"Path:\n{path}\n")
        print(f"Blob:\n{blob_hash[:8]}...\n")
        print("Provenance: None (Empty file or no metadata)")
        return
        
    # Pretty print
    try:
        ts = float(meta.get("generated_at", 0))
        dt = datetime.datetime.fromtimestamp(ts, tz=datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    except ValueError:
        dt = "Unknown"
        
    print(f"Path:\n{path}\n")
    print(f"Blob:\n{blob_hash[:8]}...\n")
    print(f"Model:\n{meta.get('model', 'Unknown')}\n")
    print(f"Source:\n{meta.get('generation_source', 'Unknown')}\n")
    print(f"Prompt:\n{meta.get('prompt_version', 'Unknown')}\n")
    print(f"Validated:\n{meta.get('validated', 'Unknown')}\n")
    print(f"Generated:\n{dt}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: ./inspect_provenance.py /path/to/file")
        sys.exit(1)
        
    inspect_provenance(sys.argv[1])
