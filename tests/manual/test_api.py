import requests
import json

# Test the API endpoints
def test_api():
    base_url = "http://127.0.0.1:8001"
    
    try:
        # Test root endpoint
        response = requests.get(f"{base_url}/")
        print("Root endpoint response:")
        print(json.dumps(response.json(), indent=2))
        print()
        
        # Test status endpoint
        response = requests.get(f"{base_url}/status")
        print("Status endpoint response:")
        print(json.dumps(response.json(), indent=2))
        print()
        
        # Test alerts endpoint
        response = requests.get(f"{base_url}/alerts")
        print("Alerts endpoint response:")
        print(json.dumps(response.json(), indent=2))
        print()
        
        print("✅ All API tests passed!")
        
    except requests.exceptions.ConnectionError:
        print("❌ Could not connect to server. Make sure it's running on port 8001.")
    except Exception as e:
        print(f"❌ Test failed: {e}")

if __name__ == "__main__":
    test_api()
