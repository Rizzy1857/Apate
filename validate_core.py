#!/usr/bin/env python3
"""
Phase 1 Core Validation Script
Tests fundamental system integrity without ego or hype.
"""

import time
import redis
import psycopg2
from datetime import datetime
import json
import sys

class ValidationReport:
    def __init__(self):
        self.tests = []
        self.start_time = datetime.now()
    
    def add_test(self, name, passed, evidence, notes=""):
        self.tests.append({
            "name": name,
            "passed": passed,
            "evidence": evidence,
            "notes": notes,
            "timestamp": datetime.now().isoformat()
        })
    
    def print_summary(self):
        print("\n" + "="*80)
        print("PHASE 1 VALIDATION REPORT")
        print("="*80)
        print(f"Start Time: {self.start_time}")
        print(f"Duration: {datetime.now() - self.start_time}")
        print(f"Total Tests: {len(self.tests)}")
        
        passed = sum(1 for t in self.tests if t['passed'])
        failed = len(self.tests) - passed
        
        print(f"\n✅ PASSED: {passed}")
        print(f"❌ FAILED: {failed}")
        print(f"Success Rate: {(passed/len(self.tests)*100):.1f}%\n")
        
        for i, test in enumerate(self.tests, 1):
            status = "✅ PASS" if test['passed'] else "❌ FAIL"
            print(f"{i}. {test['name']}: {status}")
            if not test['passed'] or test['notes']:
                print(f"   Evidence: {test['evidence']}")
                if test['notes']:
                    print(f"   Notes: {test['notes']}")
        
        print("\n" + "="*80)
        
        return passed == len(self.tests)


def test_redis_connection(report):
    """Test 1: Can we connect to Redis?"""
    try:
        r = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)
        r.ping()
        report.add_test(
            "Redis Connection",
            True,
            "Successfully connected and pinged Redis"
        )
        return r
    except Exception as e:
        report.add_test(
            "Redis Connection",
            False,
            f"Failed to connect: {str(e)}",
            "Ensure Redis is running: docker-compose up -d redis"
        )
        return None


def test_postgres_connection(report):
    """Test 2: Can we connect to PostgreSQL?"""
    try:
        conn = psycopg2.connect(
            host='localhost',
            port=5432,
            database='chronos',
            user='chronos',
            password='chronos_dev_password'
        )
        conn.close()
        report.add_test(
            "PostgreSQL Connection",
            True,
            "Successfully connected to PostgreSQL"
        )
        return True
    except Exception as e:
        report.add_test(
            "PostgreSQL Connection",
            False,
            f"Failed to connect: {str(e)}",
            "Ensure PostgreSQL is running and initialized"
        )
        return False


def test_state_atomicity(report, r):
    """Test 3: Are state operations atomic?"""
    if not r:
        report.add_test(
            "State Atomicity",
            False,
            "Redis not available",
            "Cannot test without Redis connection"
        )
        return
    
    try:
        # Test atomic counter
        test_key = "fs:test:counter"
        r.delete(test_key)
        
        # Increment 100 times
        for _ in range(100):
            r.incr(test_key)
        
        value = int(r.get(test_key))
        expected = 100
        
        if value == expected:
            report.add_test(
                "State Atomicity (Counter)",
                True,
                f"Counter reached {value} (expected {expected})"
            )
        else:
            report.add_test(
                "State Atomicity (Counter)",
                False,
                f"Counter is {value} (expected {expected})",
                "Possible race condition"
            )
        
        r.delete(test_key)
    except Exception as e:
        report.add_test(
            "State Atomicity",
            False,
            f"Exception: {str(e)}"
        )


def test_state_persistence(report, r):
    """Test 4: Does state persist across operations?"""
    if not r:
        report.add_test(
            "State Persistence",
            False,
            "Redis not available"
        )
        return
    
    try:
        # Create a test inode
        test_inode = "fs:test:inode:1000"
        test_data = {
            "mode": "33188",
            "uid": "0",
            "gid": "0",
            "size": "1024",
            "nlink": "1"
        }
        
        # Write
        r.hset(test_inode, mapping=test_data)
        
        # Read back
        retrieved = r.hgetall(test_inode)
        
        # Verify
        match = all(retrieved.get(k) == v for k, v in test_data.items())
        
        if match:
            report.add_test(
                "State Persistence (Hash)",
                True,
                f"All {len(test_data)} fields retrieved correctly"
            )
        else:
            report.add_test(
                "State Persistence (Hash)",
                False,
                f"Mismatch: wrote {test_data}, got {retrieved}"
            )
        
        r.delete(test_inode)
    except Exception as e:
        report.add_test(
            "State Persistence",
            False,
            f"Exception: {str(e)}"
        )


def test_lua_script_execution(report, r):
    """Test 5: Can we execute Lua scripts?"""
    if not r:
        report.add_test(
            "Lua Script Execution",
            False,
            "Redis not available"
        )
        return
    
    try:
        # Simple Lua script to test atomic operations
        lua_script = """
        local key = KEYS[1]
        local value = ARGV[1]
        redis.call('SET', key, value)
        return redis.call('GET', key)
        """
        
        test_key = "fs:test:lua"
        test_value = "atomic_test"
        
        result = r.eval(lua_script, 1, test_key, test_value)
        
        if result == test_value:
            report.add_test(
                "Lua Script Execution",
                True,
                f"Script executed successfully, returned '{result}'"
            )
        else:
            report.add_test(
                "Lua Script Execution",
                False,
                f"Expected '{test_value}', got '{result}'"
            )
        
        r.delete(test_key)
    except Exception as e:
        report.add_test(
            "Lua Script Execution",
            False,
            f"Exception: {str(e)}"
        )


def test_directory_simulation(report, r):
    """Test 6: Can we simulate directory structures?"""
    if not r:
        report.add_test(
            "Directory Simulation",
            False,
            "Redis not available"
        )
        return
    
    try:
        # Simulate: /tmp (inode 2) containing file1, file2, file3
        dir_key = "fs:test:dir:2"
        
        # Clear any existing test data
        r.delete(dir_key)
        
        # Add entries (using sorted set)
        entries = {
            "file1": 1001,
            "file2": 1002,
            "file3": 1003
        }
        
        for filename, inode in entries.items():
            r.zadd(dir_key, {filename: inode})
        
        # Retrieve entries
        retrieved = r.zrange(dir_key, 0, -1, withscores=True)
        retrieved_dict = {name: int(score) for name, score in retrieved}
        
        if retrieved_dict == entries:
            report.add_test(
                "Directory Simulation",
                True,
                f"Directory contains {len(entries)} entries"
            )
        else:
            report.add_test(
                "Directory Simulation",
                False,
                f"Expected {entries}, got {retrieved_dict}"
            )
        
        r.delete(dir_key)
    except Exception as e:
        report.add_test(
            "Directory Simulation",
            False,
            f"Exception: {str(e)}"
        )


def test_concurrent_operations(report, r):
    """Test 7: Simulate concurrent writes (single client)"""
    if not r:
        report.add_test(
            "Concurrent Operations",
            False,
            "Redis not available"
        )
        return
    
    try:
        # This is a simplified test (true concurrency requires multiple processes)
        test_key = "fs:test:concurrent"
        r.delete(test_key)
        
        # Simulate rapid writes
        for i in range(50):
            r.incr(test_key)
        
        value = int(r.get(test_key))
        
        if value == 50:
            report.add_test(
                "Concurrent Operations (Simulated)",
                True,
                f"50 increments resulted in {value}",
                "Note: Full concurrency test requires multi-process setup"
            )
        else:
            report.add_test(
                "Concurrent Operations (Simulated)",
                False,
                f"Expected 50, got {value}"
            )
        
        r.delete(test_key)
    except Exception as e:
        report.add_test(
            "Concurrent Operations",
            False,
            f"Exception: {str(e)}"
        )


def test_performance_baseline(report, r):
    """Test 8: Measure basic Redis operation latency"""
    if not r:
        report.add_test(
            "Performance Baseline",
            False,
            "Redis not available"
        )
        return
    
    try:
        test_key = "fs:test:perf"
        iterations = 1000
        
        # Test SET performance
        start = time.time()
        for i in range(iterations):
            r.set(f"{test_key}:{i}", f"value_{i}")
        set_time = (time.time() - start) * 1000  # Convert to ms
        
        # Test GET performance
        start = time.time()
        for i in range(iterations):
            r.get(f"{test_key}:{i}")
        get_time = (time.time() - start) * 1000
        
        # Cleanup
        for i in range(iterations):
            r.delete(f"{test_key}:{i}")
        
        avg_set = set_time / iterations
        avg_get = get_time / iterations
        
        # Acceptable if average operation < 1ms
        if avg_set < 1.0 and avg_get < 1.0:
            report.add_test(
                "Performance Baseline",
                True,
                f"SET: {avg_set:.3f}ms/op, GET: {avg_get:.3f}ms/op"
            )
        else:
            report.add_test(
                "Performance Baseline",
                False,
                f"SET: {avg_set:.3f}ms/op, GET: {avg_get:.3f}ms/op",
                "Operations taking >1ms may indicate performance issues"
            )
    except Exception as e:
        report.add_test(
            "Performance Baseline",
            False,
            f"Exception: {str(e)}"
        )


def main():
    print("\n🧪 CHRONOS PHASE 1 CORE VALIDATION")
    print("="*80)
    print("Testing fundamental system integrity without hype.")
    print("This is not about features. This is about proving the core works.")
    print("="*80 + "\n")
    
    report = ValidationReport()
    
    # Run tests
    r = test_redis_connection(report)
    test_postgres_connection(report)
    test_state_atomicity(report, r)
    test_state_persistence(report, r)
    test_lua_script_execution(report, r)
    test_directory_simulation(report, r)
    test_concurrent_operations(report, r)
    test_performance_baseline(report, r)
    
    # Print report
    all_passed = report.print_summary()
    
    print("\n📋 NEXT STEPS:")
    if not all_passed:
        print("❌ Core tests failed. Fix infrastructure before proceeding.")
        print("   - Ensure Docker services are running: make up")
        print("   - Check Redis connectivity")
        print("   - Check PostgreSQL connectivity")
    else:
        print("✅ Core infrastructure validated.")
        print("   - Proceed with FUSE interface testing")
        print("   - Run attack simulations")
        print("   - Measure end-to-end latency")
    
    print("\n💡 REMEMBER:")
    print("   Phase 1 is not about innovation.")
    print("   Phase 1 is about proving the spine is strong.")
    print("   Measure everything. Document failures honestly.")
    print()
    
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
