import rust_protocol
import sys

def test_ffi():
    print("Testing Rust FFI...")
    
    # Test IP validation
    ip = "192.168.1.1"
    is_valid = rust_protocol.validate_ip(ip)
    print(f"IP Validation ({ip}): {is_valid}")
    if not is_valid:
        print("FAIL: IP should be valid")
        sys.exit(1)

    # Test IP Validation Limit
    try:
        rust_protocol.validate_ip("A" * 50)
        print("FAIL: Should have raised ValueError for long IP")
        sys.exit(1)
    except ValueError as e:
        print(f"Caught expected error for long IP: {e}")

    # Test Entropy
    data = "AAAAA"
    entropy = rust_protocol.calculate_entropy(data)
    print(f"Entropy ({data}): {entropy}")
    if entropy != 0.0:
        print("FAIL: Entropy of 'AAAAA' should be 0.0")
        sys.exit(1)

    # Test Entropy Limit
    try:
        rust_protocol.calculate_entropy("A" * 1_000_001)
        print("FAIL: Should have raised ValueError for large entropy input")
        sys.exit(1)
    except ValueError as e:
        print(f"Caught expected error for large entropy input: {e}")

    # Test Fingerprint
    fingerprint = rust_protocol.generate_fingerprint("test")
    print(f"Fingerprint ('test'): {fingerprint}")
    if not fingerprint:
        print("FAIL: Fingerprint should not be empty")
        sys.exit(1)

    print("SUCCESS: All FFI tests passed!")

if __name__ == "__main__":
    test_ffi()
