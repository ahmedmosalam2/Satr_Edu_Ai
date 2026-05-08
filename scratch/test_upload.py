from fastapi.testclient import TestClient
from main import app
import os

def test_upload():
    project_id = "52657158-43e1-4646-ab38-1d9e83dc1a2d"
    
    # Create a dummy file
    file_path = "test_upload_file.txt"
    with open(file_path, "w") as f:
        f.write("This is a test file for upload.")
        
    with TestClient(app) as client:
        with open(file_path, "rb") as f:
            response = client.post(
                f"/api/v1/upload/{project_id}",
                files={"file": ("test_upload_file.txt", f, "text/plain")}
            )
        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.json()}")

if __name__ == "__main__":
    test_upload()
