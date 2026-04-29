import sys
import os
import io

# Fix encoding for Windows terminal
if sys.stdout.encoding != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from fastapi.testclient import TestClient
from main import app
from src.helpers.auth import get_current_user
from src.models.enums.UserRole import UserRole

# Mock User Data
MOCK_TEACHER = {
    "user_id": "teacher_123",
    "user_role": UserRole.TEACHER.value,
    "user_email": "teacher@satredu.ai"
}

def mock_get_teacher():
    return MOCK_TEACHER

def test_analytics_eval():
    app.dependency_overrides[get_current_user] = mock_get_teacher
    
    with TestClient(app) as client:
        print("=" * 70)
        print("   TESTING ANALYTICS & EVALUATION ROUTES")
        print("=" * 70)

        # 1. Student Analytics
        print("\n[1] GET /api/v1/analytics/student/student_456")
        resp = client.get("/api/v1/analytics/student/student_456")
        print(f"Status: {resp.status_code}")
        try:
            print(f"Response: {resp.json()}")
        except:
            print(f"Response: {resp.text}")

        # 2. Leaderboard
        print("\n[2] GET /api/v1/analytics/leaderboard/proj_789")
        resp = client.get("/api/v1/analytics/leaderboard/proj_789")
        print(f"Status: {resp.status_code}")
        try:
            print(f"Response: {resp.json()}")
        except:
            print(f"Response: {resp.text}")

        # 3. Teacher Overview
        print("\n[3] GET /api/v1/analytics/teacher/teacher_123/overview")
        resp = client.get("/api/v1/analytics/teacher/teacher_123/overview")
        print(f"Status: {resp.status_code}")
        try:
            print(f"Response: {resp.json()}")
        except:
            print(f"Response: {resp.text}")

        # 4. Evaluation - Retrieval
        print("\n[4] POST /api/v1/eval/retrieval")
        payload = {"project_id": "non_existent", "query": "test", "limit": 1}
        resp = client.post("/api/v1/eval/retrieval", json=payload)
        print(f"Status: {resp.status_code}")
        # Not found logic in ProjectModel might return error
        print(f"Body snippet: {resp.text[:100]}")

    app.dependency_overrides = {}
    print("\n" + "=" * 70)
    print("   DONE")
    print("=" * 70)

if __name__ == "__main__":
    test_analytics_eval()
