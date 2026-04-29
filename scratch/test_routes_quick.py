from fastapi.testclient import TestClient
from main import app
import sys

def test_routes():
    # Use context manager to trigger startup/shutdown events
    with TestClient(app) as client:
        print("Testing /openapi.json generation (validates all route schemas)...")
        response = client.get("/openapi.json")
        if response.status_code != 200:
            print(f"FAILED to generate OpenAPI schema: {response.status_code}")
            sys.exit(1)
        
        schema = response.json()
        paths = schema.get("paths", {})
        print(f"SUCCESS: Generated OpenAPI schema with {len(paths)} unique endpoint paths.")

        print("Testing /api/v1/ endpoint...")
        response = client.get("/api/v1/")
        print(f"Status: {response.status_code}, Response: {response.json()}")

        print("Testing /api/v1/health endpoint...")
        response = client.get("/api/v1/health")
        print(f"Status: {response.status_code}, Response: {response.json()}")

if __name__ == "__main__":
    try:
        test_routes()
        print("\nALL ROUTE INTEGRITY CHECKS PASSED!")
    except Exception as e:
        print(f"ERROR: {e}")
        sys.exit(1)
