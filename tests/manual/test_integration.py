from backend.app.main import app
from fastapi.testclient import TestClient

def test_integration():
    """Integration test for the backend API"""
    print("🧪 Running backend integration tests...")
    
    client = TestClient(app)
    
    # Test root endpoint
    response = client.get("/")
    print(f"✅ Root endpoint: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        print(f"   Service: {data.get('service')}")
        print(f"   Status: {data.get('status')}")
    
    # Test status endpoint
    response = client.get("/status")
    print(f"✅ Status endpoint: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        print(f"   System: {data.get('system')}")
    
    # Test alerts endpoint
    response = client.get("/alerts")
    print(f"✅ Alerts endpoint: {response.status_code}")
    
    # Test logs endpoint
    response = client.get("/logs")
    print(f"✅ Logs endpoint: {response.status_code}")
    
    print("\n🎉 Backend integration tests completed!")

if __name__ == "__main__":
    test_integration()
