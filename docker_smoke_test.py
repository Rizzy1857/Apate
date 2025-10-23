#!/usr/bin/env python3
"""
Docker Smoke Test for Apate Honeypot
------------------------------------
Verifies that the Docker Compose setup is working correctly.
"""

import requests
import time
import sys
import subprocess
import json

def run_command(cmd, capture_output=True):
    """Run a shell command and return the result"""
    try:
        result = subprocess.run(cmd, shell=True, capture_output=capture_output, text=True, timeout=30)
        return result.returncode == 0, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return False, "", "Command timed out"

def wait_for_service(url, max_attempts=30, delay=2):
    """Wait for a service to become available"""
    print(f"Waiting for service at {url}...")
    for attempt in range(max_attempts):
        try:
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                print(f"✅ Service at {url} is ready!")
                return True
        except requests.exceptions.RequestException:
            pass
        
        print(f"  Attempt {attempt + 1}/{max_attempts} - waiting {delay}s...")
        time.sleep(delay)
    
    print(f"❌ Service at {url} failed to start within {max_attempts * delay}s")
    return False

def test_service_endpoint(url, expected_status=200, description=""):
    """Test a service endpoint"""
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == expected_status:
            print(f"✅ {description}: {response.status_code}")
            return True, response.json() if response.headers.get('content-type', '').startswith('application/json') else response.text
        else:
            print(f"❌ {description}: Expected {expected_status}, got {response.status_code}")
            return False, response.text
    except Exception as e:
        print(f"❌ {description}: {str(e)}")
        return False, str(e)

def main():
    print("🚀 Starting Apate Honeypot Docker Smoke Test")
    print("=" * 50)
    
    # Check if Docker is available
    print("1. Checking Docker availability...")
    success, stdout, stderr = run_command("docker --version")
    if not success:
        print("❌ Docker is not available. Please install Docker first.")
        sys.exit(1)
    print(f"✅ Docker version: {stdout.strip()}")
    
    # Check if Docker Compose is available
    print("\n2. Checking Docker Compose availability...")
    success, stdout, stderr = run_command("docker-compose --version")
    if not success:
        success, stdout, stderr = run_command("docker compose version")
    if not success:
        print("❌ Docker Compose is not available. Please install Docker Compose.")
        sys.exit(1)
    print(f"✅ Docker Compose available: {stdout.strip()}")
    
    # Start services with override
    print("\n3. Starting services with docker-compose...")
    print("This may take a few minutes for the first run (building images)...")
    success, stdout, stderr = run_command("docker-compose -f docker-compose.yml -f docker-compose.override.yml up -d --build", capture_output=False)
    if not success:
        print("❌ Failed to start Docker services")
        print("Stderr:", stderr)
        sys.exit(1)
    
    # Wait for services to be ready
    print("\n4. Waiting for services to be ready...")
    
    services_to_test = [
        ("http://localhost:8000", "FastAPI Backend"),
        ("http://localhost:5432", "PostgreSQL Database", False),  # PostgreSQL doesn't respond to HTTP
        ("http://localhost:6379", "Redis Cache", False),  # Redis doesn't respond to HTTP
    ]
    
    # Wait for main backend service
    if not wait_for_service("http://localhost:8000"):
        print("❌ Backend service failed to start")
        print("\nChecking logs...")
        run_command("docker-compose logs backend", capture_output=False)
        sys.exit(1)
    
    # Test API endpoints
    print("\n5. Testing API endpoints...")
    
    endpoints = [
        ("http://localhost:8000/", "Root endpoint"),
        ("http://localhost:8000/status", "Status endpoint"),
        ("http://localhost:8000/alerts", "Alerts endpoint"),
        ("http://localhost:8000/logs", "Logs endpoint"),
    ]
    
    all_tests_passed = True
    
    for url, description in endpoints:
        success, data = test_service_endpoint(url, description=description)
        if success and isinstance(data, dict):
            print(f"  📊 Response: {json.dumps(data, indent=2)[:200]}...")
        all_tests_passed = all_tests_passed and success
    
    # Test database connection
    print("\n6. Testing database connection...")
    success, stdout, stderr = run_command("docker-compose exec -T postgres pg_isready -U apate_user -d apate_dev")
    if success:
        print("✅ Database connection: OK")
    else:
        print("❌ Database connection: Failed")
        all_tests_passed = False
    
    # Show service status
    print("\n7. Service status:")
    run_command("docker-compose ps", capture_output=False)
    
    # Clean up
    print("\n8. Cleaning up...")
    cleanup = input("Do you want to stop the services? (y/N): ").lower().strip()
    if cleanup in ['y', 'yes']:
        run_command("docker-compose down", capture_output=False)
        print("✅ Services stopped")
    else:
        print("🔄 Services left running. Use 'docker-compose down' to stop them.")
    
    # Final result
    print("\n" + "=" * 50)
    if all_tests_passed:
        print("🎉 All smoke tests passed! The Docker setup is working correctly.")
        sys.exit(0)
    else:
        print("❌ Some tests failed. Please check the logs and configuration.")
        sys.exit(1)

if __name__ == "__main__":
    main()
