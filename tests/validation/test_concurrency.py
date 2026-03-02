#!/usr/bin/env python3
"""
Multi-Process Concurrency Test (Direct State Access)
Tests Chronos state management under concurrent load
"""

import sys
import os
import time
import redis
import multiprocessing as mp
from dataclasses import dataclass, asdict
from typing import List, Dict
from datetime import datetime
import json
import random

# Add src to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../src')))

@dataclass
class WorkerResult:
    """Result from a worker process"""
    worker_id: int
    success: bool
    operations_executed: int
    errors: List[str]
    duration: float


def worker_process(worker_id: int, num_operations: int, result_queue: mp.Queue):
    """
    Simulate concurrent Redis state operations
    """
    result = WorkerResult(
        worker_id=worker_id,
        success=False,
        operations_executed=0,
        errors=[],
        duration=0.0
    )
    
    start_time = time.time()
    
    try:
        # Connect to Redis
        r = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)
        r.ping()
        
        # Perform operations
        for i in range(num_operations):
            op_type = random.choice(['create', 'read', 'update', 'delete'])
            key = f"test:worker{worker_id}:item{i}"
            
            try:
                if op_type == 'create':
                    r.set(key, f"data_{worker_id}_{i}", nx=True)
                elif op_type == 'read':
                    r.get(f"test:worker{random.randint(0, worker_id)}:item{random.randint(0, i if i > 0 else 1)}")
                elif op_type == 'update':
                    r.set(key, f"updated_{worker_id}_{i}")
                elif op_type == 'delete':
                    r.delete(key)
                
                result.operations_executed += 1
            except Exception as e:
                result.errors.append(f"Operation '{op_type}' failed: {str(e)}")
        
        result.success = True
        
    except Exception as e:
        result.errors.append(f"Worker {worker_id} failed: {str(e)}")
    
    result.duration = time.time() - start_time
    result_queue.put(asdict(result))


def increment_worker(worker_id: int, iterations: int, test_key: str, result_queue: mp.Queue):
    """Worker that increments a counter"""
    try:
        client = redis.Redis(host='localhost', port=6379, db=0)
        for _ in range(iterations):
            client.incr(test_key)
        result_queue.put({"success": True, "worker": worker_id})
    except Exception as e:
        result_queue.put({"success": False, "worker": worker_id, "error": str(e)})


def test_concurrent_operations(num_workers: int, operations_per_worker: int) -> Dict:
    """
    Test concurrent Redis operations
    """
    print(f"\n{'='*80}")
    print(f"Testing {num_workers} concurrent workers, {operations_per_worker} operations each")
    print(f"{'='*80}\n")
    
    result_queue = mp.Queue()
    processes = []
    
    # Start all workers simultaneously
    start_time = time.time()
    
    for worker_id in range(num_workers):
        p = mp.Process(
            target=worker_process,
            args=(worker_id, operations_per_worker, result_queue)
        )
        p.start()
        processes.append(p)
    
    # Wait for all to complete
    for p in processes:
        p.join()
    
    total_duration = time.time() - start_time
    
    # Collect results
    results = []
    while not result_queue.empty():
        results.append(result_queue.get())
    
    # Calculate statistics
    successful = sum(1 for r in results if r['success'])
    total_ops = sum(r['operations_executed'] for r in results)
    total_errors = sum(len(r['errors']) for r in results)
    
    print(f"Results:")
    print(f"  Successful workers: {successful}/{num_workers}")
    print(f"  Total operations: {total_ops}")
    print(f"  Total errors: {total_errors}")
    print(f"  Total duration: {total_duration:.2f}s")
    if total_ops > 0:
        print(f"  Throughput: {total_ops/total_duration:.2f} ops/sec")
    
    # Print first error for debugging
    if total_errors > 0:
        for r in results:
            if r['errors']:
                print(f"  First error: {r['errors'][0]}")
                break
    
    return {
        "num_workers": num_workers,
        "operations_per_worker": operations_per_worker,
        "successful_workers": successful,
        "total_operations": total_ops,
        "total_errors": total_errors,
        "duration": total_duration,
        "throughput": total_ops / total_duration if total_ops > 0 else 0,
        "results": results
    }


def test_race_conditions():
    """
    Test for race conditions in state management
    """
    print(f"\n{'='*80}")
    print(f"Testing for race conditions in Redis state")
    print(f"{'='*80}\n")
    
    redis_client = redis.Redis(
        host='localhost',
        port=6379,
        db=0,
        decode_responses=True
    )
    
    # Clear test keys
    test_key = "test:race_condition"
    redis_client.delete(test_key)
    
    num_workers = 10
    iterations_per_worker = 100
    expected_final_value = num_workers * iterations_per_worker
    
    result_queue = mp.Queue()
    processes = []
    
    for i in range(num_workers):
        p = mp.Process(target=increment_worker, args=(i, iterations_per_worker, test_key, result_queue))
        p.start()
        processes.append(p)
    
    for p in processes:
        p.join()
    
    # Check final value
    final_value = int(redis_client.get(test_key) or 0)
    
    print(f"Expected final value: {expected_final_value}")
    print(f"Actual final value: {final_value}")
    
    if final_value == expected_final_value:
        print(f"✅ No race conditions detected")
        race_condition = False
    else:
        print(f"❌ Race condition detected! Lost {expected_final_value - final_value} increments")
        race_condition = True
    
    redis_client.delete(test_key)
    
    return {
        "expected": expected_final_value,
        "actual": final_value,
        "race_condition_detected": race_condition
    }


def test_session_isolation():
    """
    Test that concurrent operations don't interfere
    """
    print(f"\n{'='*80}")
    print(f"Testing operation isolation")
    print(f"{'='*80}\n")
    
    redis_client = redis.Redis(
        host='localhost',
        port=6379,
        db=0,
        decode_responses=True
    )
    
    # Get initial key count
    initial_keys = len(redis_client.keys("test:worker*"))
    
    # Run concurrent operations
    result = test_concurrent_operations(num_workers=5, operations_per_worker=20)
    
    # Wait a moment
    time.sleep(1)
    
    # Check final key count
    final_keys = len(redis_client.keys("test:worker*"))
    
    print(f"\nOperation Isolation Check:")
    print(f"  Initial test keys: {initial_keys}")
    print(f"  Final test keys: {final_keys}")
    print(f"  Keys created: {final_keys - initial_keys}")
    
    # Cleanup
    for key in redis_client.keys("test:worker*"):
        redis_client.delete(key)
    
    return {
        "initial_keys": initial_keys,
        "final_keys": final_keys,
        "keys_created": final_keys - initial_keys,
        "concurrency_result": result
    }


def main():
    """Run all concurrency tests"""
    print(f"{'='*80}")
    print(f"CHRONOS MULTI-PROCESS CONCURRENCY TEST")
    print(f"{'='*80}")
    print(f"Started: {datetime.now().isoformat()}")
    print(f"\nNote: Testing Redis state concurrency (not SSH)")
    
    results = {
        "timestamp": datetime.now().isoformat(),
        "tests": {}
    }
    
    # Test 1: Low concurrency (2 workers)
    print(f"\n[TEST 1] Low Concurrency")
    results["tests"]["low_concurrency"] = test_concurrent_operations(
        num_workers=2,
        operations_per_worker=50
    )
    
    # Test 2: Medium concurrency (5 workers)
    print(f"\n[TEST 2] Medium Concurrency")
    results["tests"]["medium_concurrency"] = test_concurrent_operations(
        num_workers=5,
        operations_per_worker=100
    )
    
    # Test 3: High concurrency (10 workers)
    print(f"\n[TEST 3] High Concurrency")
    results["tests"]["high_concurrency"] = test_concurrent_operations(
        num_workers=10,
        operations_per_worker=150
    )
    
    # Test 4: Race conditions
    print(f"\n[TEST 4] Race Conditions")
    results["tests"]["race_conditions"] = test_race_conditions()
    
    # Test 5: Operation isolation
    print(f"\n[TEST 5] Operation Isolation")
    results["tests"]["operation_isolation"] = test_session_isolation()
    
    # Summary
    print(f"\n{'='*80}")
    print(f"SUMMARY")
    print(f"{'='*80}\n")
    
    total_workers = (
        results["tests"]["low_concurrency"]["num_workers"] +
        results["tests"]["medium_concurrency"]["num_workers"] +
        results["tests"]["high_concurrency"]["num_workers"]
    )
    
    total_ops = (
        results["tests"]["low_concurrency"]["total_operations"] +
        results["tests"]["medium_concurrency"]["total_operations"] +
        results["tests"]["high_concurrency"]["total_operations"]
    )
    
    print(f"Total workers tested: {total_workers}")
    print(f"Total operations executed: {total_ops}")
    print(f"Race conditions: {'❌ DETECTED' if results['tests']['race_conditions']['race_condition_detected'] else '✅ NONE'}")
    
    # Save results
    output_file = f"/tmp/chronos_concurrency_test_{int(time.time())}.json"
    with open(output_file, 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"\n✅ Results saved to: {output_file}")
    print(f"Completed: {datetime.now().isoformat()}")


if __name__ == "__main__":
    main()
