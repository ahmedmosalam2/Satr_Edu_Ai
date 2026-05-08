import requests
import sys

r = requests.post("http://localhost:8000/api/v1/auth/login", json={
    "user_email": "student@satr.ai",
    "user_password": "pass123456"
})

if r.status_code == 200:
    data = r.json()
    print("Email: student@satr.ai")
    print("Password: pass123456")
    print("Student ID:", data.get("user", {}).get("user_id"))
else:
    print("Failed to login:", r.text)

r2 = requests.post("http://localhost:8000/api/v1/auth/login", json={
    "user_email": "teacher@satr.ai",
    "user_password": "pass123456"
})

if r2.status_code == 200:
    data2 = r2.json()
    print("Teacher ID:", data2.get("user", {}).get("user_id"))
