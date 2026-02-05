import sys
import os
import time

sys.path.append(os.path.join(os.getcwd(), "src"))
from chronos.interface.fuse import ChronosFUSE
from chronos.core.state import StateHypervisor

def test_intelligence():
    print("[-] Initializing ChronosFUSE with Intelligence...")
    hv = StateHypervisor()
    fs = ChronosFUSE("/") # This should load PersonaEngine
    
    print(f"[-] Creating directory /etc...")
    try:
        fs.mkdir("/etc", 0o755)
    except OSError:
        pass # Already exists

    filename = f"ghost_{int(time.time())}.conf"
    path = f"/etc/{filename}"
    
    print(f"[-] Creating empty file {path}...")
    try:
        # Create without content
        fs.create(path, 0o644)
    except Exception as e:
        print(f"[!] Create failed: {e}")
        return False
        
    print(f"[-] Reading {path} (Triggering Generation)...")
    try:
        # We need to resolve inode
        # Note: In a real mount, the kernel calls open then read.
        # Here we call method directly.
        fd = fs.open(path, 0)
        content = fs.read(path, 1024, 0, fd)
        
        print(f"[+] Generated Content: {content}")
        
        if b"[MOCK RESPOSE]" in content:
            print("[+] Mock LLM signature detected. (PASS)")
        else:
            print("[!] Unexpected content. (FAIL)")
            return False
            
    except Exception as e:
        print(f"[!] Read/Generation failed: {e}")
        return False

    return True

if __name__ == "__main__":
    if test_intelligence():
        print("\n[SUCCESS] Phase 3 Intelligence Verified")
        sys.exit(0)
    else:
        print("\n[FAILURE] Phase 3 Verification Failed")
        sys.exit(1)
