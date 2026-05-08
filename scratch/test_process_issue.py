import requests
import json

def test():
    # Use the same project_id and file_id from the user's postman screenshot
    project_id = "52657158-43e1-4646-ab38-1d9e83dc1a2d"
    url = f"http://localhost:8000/api/v1/process/{project_id}"
    
    payload = {
        "file_id": "rcsgM9xqwF_Screenshot20260422032627.png",
        "chunk_size": 500,
        "chunk_overlap": 100,
        "do_reset": False
    }
    
    try:
        r = requests.post(url, json=payload)
        print(f"Status Code: {r.status_code}")
        print("Response JSON:")
        print(json.dumps(r.json(), indent=2, ensure_ascii=False))
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test()
