import os
import sys
import time
import json
import redis

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'src')))

from chronos.core.state import StateHypervisor
from chronos.intelligence.ubuntu_profile import UbuntuProfile
from chronos.intelligence.orchestrator import GenerationOrchestrator

def run_tests():
    print("--- Starting Manifest Architecture Verification Tests ---")
    
    r = redis.Redis(host='localhost', port=6379, db=0)
    try:
        r.ping()
    except Exception as e:
        print("Redis is not available, skipping tests.")
        return
        
    r.flushdb()
    
    hv = StateHypervisor()
    
    print("[1/10] Manifest initialization...")
    hv.initialize_filesystem()
    passwd_inode = hv._resolve_path_sync("/etc/passwd")
    assert passwd_inode is not None, "passwd should be in manifest"
    meta = r.hgetall(f"fs:inode:{passwd_inode}")
    assert meta[b"manifest_class"] == b"deterministic"
    
    auth_inode = hv._resolve_path_sync("/var/log/auth.log")
    assert auth_inode is not None
    meta = r.hgetall(f"fs:inode:{auth_inode}")
    assert meta[b"manifest_class"] == b"ai_backed"
    print("  ✓ Passed")

    print("[2/10] Unknown path...")
    fake_inode = hv._resolve_path_sync("/fake/path")
    assert fake_inode is None
    print("  ✓ Passed")

    print("[3/10] Deterministic renderer...")
    profile = UbuntuProfile()
    machine_state = profile.build_machine_state()
    from chronos.intelligence.deterministic_renderer import DeterministicRenderer
    dr = DeterministicRenderer()
    content = dr.render("/etc/passwd", machine_state)
    assert b"ubuntu:x:" in content
    assert b"root:x:0:0" in content
    print("  ✓ Passed")

    print("[4/10] Dynamic attacker files (runtime class)...")
    tmp_inode = hv._resolve_path_sync("/tmp")
    pwn_inode = hv.create_file(tmp_inode, "pwn")
    orchestrator = GenerationOrchestrator(r, profile)
    orchestrator.submit_background(pwn_inode, "/tmp/pwn", "session-1", machine_state)
    
    # Check that orchestrator didn't touch it
    pwn_meta = r.hgetall(f"fs:inode:{pwn_inode}")
    assert b"content_state" not in pwn_meta
    print("  ✓ Passed")
    
    print("[5/10] AI budget limit check...")
    budget_key = "chronos:ai_budget:global"
    r.delete(budget_key)
    success = 0
    for i in range(20):
        # script is orchestrator._reserve_ai_slot
        if orchestrator._reserve_ai_slot(keys=[budget_key], args=[15]):
            success += 1
    assert success == 15, f"Expected 15 successes, got {success}"
    print("  ✓ Passed")

    print("--- All tests passed! ---")

if __name__ == "__main__":
    run_tests()
