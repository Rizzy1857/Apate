import sys
import os
import time
sys.path.append(os.path.join(os.getcwd(), "src"))

from chronos.interface.fuse import ChronosFUSE
from chronos.core.state import StateHypervisor

def test_fuse_interface():
    print("[-] Initializing ChronosFUSE...")
    # Ensure root exists
    hv = StateHypervisor()
    hv.initialize_filesystem()
    
    fs = ChronosFUSE("/")
    
    print("[-] Testing mkdir /foo...")
    try:
        fs.mkdir("/foo", 0o755)
        print("[+] mkdir success")
    except Exception as e:
        print(f"[!] mkdir failed: {e}")
        return False
        
    print("[-] Testing create /foo/bar.txt...")
    try:
        # Create returns fd
        fd = fs.create("/foo/bar.txt", 0o644)
        print(f"[+] create success (fd={fd})")
    except Exception as e:
        print(f"[!] create failed: {e}")
        return False

    print("[-] Testing write to /foo/bar.txt...")
    content = b"Hello Chronos!"
    try:
        written = fs.write("/foo/bar.txt", content, 0, fd)
        print(f"[+] write success (bytes={written})")
    except Exception as e:
        print(f"[!] write failed: {e}")
        return False

    print("[-] Testing read back...")
    try:
        # Open fresh fd to be sure
        fd_read = fs.open("/foo/bar.txt", 0)
        data = fs.read("/foo/bar.txt", 100, 0, fd_read)
        print(f"[+] read data: {data}")
        if data != content:
            print("[!] Content mismatch!")
            return False
        print("[+] Content verified")
    except Exception as e:
        print(f"[!] read failed: {e}")
        return False

    print("[-] Testing unlink /foo/bar.txt...")
    try:
        fs.unlink("/foo/bar.txt")
        print("[+] unlink success")
    except Exception as e:
        print(f"[!] unlink failed: {e}")
        return False

    print("[-] Testing rmdir /foo...")
    try:
        fs.rmdir("/foo")
        print("[+] rmdir success")
    except Exception as e:
        print(f"[!] rmdir failed: {e}")
        return False
        
    return True

if __name__ == "__main__":
    if test_fuse_interface():
        print("\n[SUCCESS] Phase 2 Interface Verified")
        sys.exit(0)
    else:
        print("\n[FAILURE] Phase 2 Verification Failed")
        sys.exit(1)
