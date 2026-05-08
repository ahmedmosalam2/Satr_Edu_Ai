import requests
import json

url = "http://localhost:8000/api/v1/process/52657158-43e1-4646-ab38-1d9e83dc1a2d"
payload = {
    "file_id": "hpkFrr0OUG_Sec7.pptx",
    "chunk_size": 500,
    "chunk_overlap": 100,
    "do_reset": False
}
headers = {"Content-Type": "application/json"}

try:
    response = requests.post(url, json=payload, headers=headers)
    print(f"Status Code: {response.status_code}")
    print(f"Response snippet: {response.text[:200]}")
    if response.status_code == 200:
        data = response.json()
        print(f"\nKeys in JSON: {list(data.keys())}")
        if 'data' in data and 'chunks' in data['data']:
            print(f"Number of chunks returned in response: {len(data['data']['chunks'])}")
except Exception as e:
    print(f"Error: {e}")
