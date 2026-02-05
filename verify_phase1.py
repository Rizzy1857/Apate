import sys
import os
import time

# Add src to path
sys.path.append(os.path.join(os.getcwd(), "src"))

from chronos.core.state import StateHypervisor

def test_foundation():
    print("[-] Connecting to State Hypervisor...")
    try:
        hv = StateHypervisor()
    except Exception as e:
        print(f"[!] Failed to connect: {e}")
        return False

    print("[-] Initializing Filesystem...")
    hv.initialize_filesystem()

    print("[-] Creating test file 'hackme.txt'...")
    try:
        inode = hv.create_file(1, "hackme.txt")
        print(f"[+] Created 'hackme.txt' with inode {inode}")
    except FileExistsError:
        print("[*] 'hackme.txt' already exists (expected if re-running)")
    except Exception as e:
        print(f"[!] Failed to create file: {e}")
        return False

    print("[-] Verifying atomic duplicate prevention...")
    try:
        hv.create_file(1, "hackme.txt")
        print("[!] Duplicate creation succeeded! (FAIL)")
        return False
    except FileExistsError:
        print("[+] Duplicate creation prevented. (PASS)")

    print("[-] Creating 100 benchmark files...")
    start = time.time()
    for i in range(100):
        try:
            hv.create_file(1, f"bench_{i}.txt")
        except:
            pass
    duration = time.time() - start
    print(f"[+] Created 100 files in {duration:.4f}s ({100/duration:.2f} ops/sec)")
    
    return True

if __name__ == "__main__":
    if test_foundation():
        print("\n[SUCCESS] Phase 1 Foundation Verified")
        sys.exit(0)
    else:
        print("\n[FAILURE] Phase 1 Verification Failed")
        sys.exit(1)
