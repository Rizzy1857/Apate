#!/usr/bin/env python3
"""
Crash Recovery Test
Tests system recovery from various failure scenarios
"""

import sys
import os
import time
import subprocess
import redis
import psycopg2
from datetime import datetime
import json

def check_docker_container(container_name: str) -> bool:
    """Check if a Docker container is running"""
    try:
        result = subprocess.run(
            ['docker', 'ps', '--filter', f'name={container_name}', '--format', '{{.Names}}'],
            capture_output=True,
            text=True,
            check=True
        )
        return container_name in result.stdout
    except Exception as e:
        print(f"Error checking container: {e}")
        return False


def stop_container(container_name: str):
    """Stop a Docker container"""
    print(f"  Stopping {container_name}...")
    try:
        subprocess.run(['docker', 'stop', container_name], check=True, capture_output=True)
        time.sleep(2)
        print(f"  ✅ {container_name} stopped")
    except Exception as e:
        print(f"  ❌ Failed to stop {container_name}: {e}")


def start_container(container_name: str):
    """Start a Docker container"""
    print(f"  Starting {container_name}...")
    try:
        subprocess.run(['docker', 'start', container_name], check=True, capture_output=True)
        time.sleep(5)  # Wait for startup
        print(f"  ✅ {container_name} started")
    except Exception as e:
        print(f"  ❌ Failed to start {container_name}: {e}")


def test_redis_crash_recovery():
    """Test Redis crash and recovery"""
    print(f"\n{'='*80}")
    print(f"TEST 1: Redis Crash Recovery")
    print(f"{'='*80}\n")
    
    container_name = "chronos_redis"
    results = {
        "test": "redis_crash_recovery",
        "timestamp": datetime.now().isoformat(),
        "success": False,
        "details": {}
    }
    
    # Step 1: Write test data
    print("[1] Writing test data to Redis...")
    try:
        r = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)
        test_key = "crash_test:data"
        test_value = f"test_data_{int(time.time())}"
        r.set(test_key, test_value)
        print(f"  ✅ Written: {test_key} = {test_value}")
        results["details"]["test_key"] = test_key
        results["details"]["test_value"] = test_value
    except Exception as e:
        print(f"  ❌ Failed: {e}")
        return results
    
    # Step 2: Stop Redis
    print(f"\n[2] Simulating Redis crash...")
    stop_container(container_name)
    
    # Step 3: Verify down
    print(f"\n[3] Verifying Redis is down...")
    try:
        r = redis.Redis(host='localhost', port=6379, db=0, socket_timeout=2, decode_responses=True)
        r.ping()
        print(f"  ⚠️  Still responding")
    except Exception:
        print(f"  ✅ Confirmed down")
    
    # Step 4: Restart
    print(f"\n[4] Restarting Redis...")
    start_container(container_name)
    
    # Step 5: Verify recovery
    print(f"\n[5] Checking data recovery...")
    try:
        r = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)
        recovered_value = r.get(test_key)
        
        if recovered_value == test_value:
            print(f"  ✅ Data recovered: {recovered_value}")
            results["success"] = True
        else:
            print(f"  ❌ Data mismatch")
        
        r.delete(test_key)
    except Exception as e:
        print(f"  ❌ Failed: {e}")
    
    return results


def test_postgres_crash_recovery():
    """Test PostgreSQL crash and recovery"""
    print(f"\n{'='*80}")
    print(f"TEST 2: PostgreSQL Crash Recovery")
    print(f"{'='*80}\n")
    
    container_name = "chronos_db"
    results = {
        "test": "postgres_crash_recovery",
        "timestamp": datetime.now().isoformat(),
        "success": False
    }
    
    # Step 1: Verify initial connectivity
    print("[1] Verifying PostgreSQL is running...")
    try:
        conn = psycopg2.connect(
            host='localhost',
            port=5432,
            database='chronos',
            user='chronos',
            password='chronos_dev_password'
        )
        cursor = conn.cursor()
        cursor.execute("SELECT version();")
        version = cursor.fetchone()[0]
        print(f"  ✅ Connected: {version.split(',')[0]}")
        cursor.close()
        conn.close()
    except Exception as e:
        print(f"  ❌ Failed: {e}")
        return results
    
    # Step 2: Stop PostgreSQL
    print(f"\n[2] Simulating PostgreSQL crash...")
    stop_container(container_name)
    
    # Step 3: Verify down
    print(f"\n[3] Verifying PostgreSQL is down...")
    try:
        conn = psycopg2.connect(
            host='localhost',
            port=5432,
            database='chronos',
            user='chronos',
            password='chronos_dev_password',
            connect_timeout=2
        )
        conn.close()
        print(f"  ⚠️  Still responding")
    except Exception:
        print(f"  ✅ Confirmed down")
    
    # Step 4: Restart
    print(f"\n[4] Restarting PostgreSQL...")
    start_container(container_name)
    
    # Step 5: Verify reconnection
    print(f"\n[5] Checking PostgreSQL reconnection...")
    try:
        conn = psycopg2.connect(
            host='localhost',
            port=5432,
            database='chronos',
            user='chronos',
            password='chronos_dev_password'
        )
        cursor = conn.cursor()
        cursor.execute("SELECT 1 AS alive;")
        alive = cursor.fetchone()[0]
        
        if alive == 1:
            print(f"  ✅ Database reconnected successfully")
            results["success"] = True
        else:
            print(f"  ❌ Unexpected response")
        
        cursor.close()
        conn.close()
    except Exception as e:
        print(f"  ❌ Failed: {e}")
    
    return results


def main():
    """Run crash recovery tests"""
    print(f"{'='*80}")
    print(f"CHRONOS CRASH RECOVERY TEST")
    print(f"{'='*80}")
    print(f"Started: {datetime.now().isoformat()}")
    print(f"\n⚠️  WARNING: This will stop and restart Docker containers!")
    print(f"Press Ctrl+C to cancel...")
    time.sleep(3)
    
    all_results = {
        "timestamp": datetime.now().isoformat(),
        "tests": {}
    }
    
    # Test 1: Redis
    all_results["tests"]["redis"] = test_redis_crash_recovery()
    
    # Test 2: PostgreSQL
    all_results["tests"]["postgres"] = test_postgres_crash_recovery()
    
    # Summary
    print(f"\n{'='*80}")
    print(f"SUMMARY")
    print(f"{'='*80}\n")
    
    for name, result in all_results["tests"].items():
        status = "✅ PASSED" if result.get("success") else "❌ FAILED"
        print(f"{name}: {status}")
    
    # Save results
    output_file = f"/tmp/chronos_crash_recovery_{int(time.time())}.json"
    with open(output_file, 'w') as f:
        json.dump(all_results, f, indent=2)
    
    print(f"\n✅ Results saved to: {output_file}")


if __name__ == "__main__":
    main()
