"""
tests/test_routes.py
────────────────────
FastAPI routes test suite for Satr Edu AI.
Covers all route groups: base, auth, projects, documents, ai, models, eval, adaptive, stream, admin.
All external services (MongoDB, Qdrant, LLMs) are mocked.
"""

import os
import sys
import json
import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, AsyncMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from main import app
from src.helpers.auth import create_access_token, hash_password
from src.models.scheme_db.user import User
from src.models.scheme_db.project import Project
from src.models.scheme_db.document import Document
from src.models.enums.UserRole import UserRole

# ══════════════════════════════════════════════════════════════════════════════
# Mock Data
# ══════════════════════════════════════════════════════════════════════════════

mock_teacher = User(
    user_id="teacher_id",
    user_name="Teacher Name",
    user_email="teacher@satr.edu",
    user_password=hash_password("password123"),
    user_role=UserRole.TEACHER.value,
    is_approved=True,
    is_active=True
)

mock_student = User(
    user_id="student_id",
    user_name="Student Name",
    user_email="student@satr.edu",
    user_password=hash_password("password123"),
    user_role=UserRole.STUDENT.value,
    is_approved=True,
    is_active=True
)

mock_ops = User(
    user_id="ops_id",
    user_name="Operations Name",
    user_email="ops@satr.edu",
    user_password=hash_password("password123"),
    user_role=UserRole.OPERATIONS.value,
    is_approved=True,
    is_active=True
)

# Generate valid JWT tokens for headers
teacher_token = create_access_token({
    'user_id': mock_teacher.user_id,
    'user_email': mock_teacher.user_email,
    'user_role': mock_teacher.user_role,
    'user_name': mock_teacher.user_name
})
teacher_headers = {
    "Authorization": f"Bearer {teacher_token}"
}

student_token = create_access_token({
    'user_id': mock_student.user_id,
    'user_email': mock_student.user_email,
    'user_role': mock_student.user_role,
    'user_name': mock_student.user_name
})
student_headers = {
    "Authorization": f"Bearer {student_token}"
}

ops_token = create_access_token({
    'user_id': mock_ops.user_id,
    'user_email': mock_ops.user_email,
    'user_role': mock_ops.user_role,
    'user_name': mock_ops.user_name
})
ops_headers = {
    "Authorization": f"Bearer {ops_token}"
}


# Mock FastAPI application properties
app.client = MagicMock()
app.llm_provider = MagicMock()

# Setup OLLAMA/Embedding/Gemini methods on llm_provider
app.llm_provider.generate_text = AsyncMock(return_value="Mocked LLM generation response")
app.llm_provider.embed_text = AsyncMock(return_value=[0.1] * 768)

class MockCollection(MagicMock):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.insert_one = AsyncMock(return_value=MagicMock(inserted_id="mock_id"))
        self.insert_many = AsyncMock(return_value=MagicMock(inserted_ids=["mock_id"]))
        self.find_one = AsyncMock(return_value=None)
        self.update_one = AsyncMock(return_value=MagicMock(matched_count=1, modified_count=1))
        self.delete_one = AsyncMock(return_value=MagicMock(deleted_count=1))
        self.delete_many = AsyncMock(return_value=MagicMock(deleted_count=1))
        self.create_index = AsyncMock()
        self.count_documents = AsyncMock(return_value=0)
        self._items = []

        # Cursor for find()
        mock_cursor = MagicMock()
        mock_cursor.skip.return_value = mock_cursor
        mock_cursor.limit.return_value = mock_cursor
        mock_cursor.to_list = AsyncMock(return_value=[])

        # Support for: async for doc in cursor:
        async def mock_async_iterator():
            for item in self._items:
                yield item
        mock_cursor.__aiter__ = MagicMock(side_effect=mock_async_iterator)

        self.find = MagicMock()
        self.find.return_value = mock_cursor

mock_collections = {}

def get_mock_collection(name):
    if name not in mock_collections:
        mock_collections[name] = MockCollection()
    return mock_collections[name]

mock_db = MagicMock()
mock_db.list_collection_names = AsyncMock(return_value=["project", "chunk", "asset", "document", "documents", "users", "student_answers", "exams", "conversations"])
mock_db.__getitem__.side_effect = get_mock_collection
mock_db.get_collection.side_effect = get_mock_collection

app.client.__getitem__.return_value = mock_db
app.client["Satr-Edu"] = mock_db


# ══════════════════════════════════════════════════════════════════════════════
# Base & Health Route Tests
# ══════════════════════════════════════════════════════════════════════════════

def test_base_welcome():
    client = TestClient(app)
    response = client.get("/api/v1/")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "running"
    assert "app_name" in data

def test_base_health_healthy():
    client = TestClient(app)
    # Mock ping call success
    app.client.admin.command = AsyncMock(return_value={"ok": 1})
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["services"]["mongodb"] == "connected"

# ══════════════════════════════════════════════════════════════════════════════
# Auth Route Tests
# ══════════════════════════════════════════════════════════════════════════════

@patch("src.models.UserModel.UserModel.email_exists", new_callable=AsyncMock)
@patch("src.models.UserModel.UserModel.create_user", new_callable=AsyncMock)
def test_auth_register_success(mock_create, mock_exists):
    mock_exists.return_value = False
    mock_create.return_value = True

    client = TestClient(app)
    payload = {
        "user_name": "New Teacher",
        "user_email": "new_teacher@satr.edu",
        "user_password": "secure_password",
        "user_role": "teacher"
    }
    response = client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["user_email"] == "new_teacher@satr.edu"
    assert data["is_approved"] is False  # Teacher starts unapproved

@patch("src.models.UserModel.UserModel.get_user_by_email", new_callable=AsyncMock)
def test_auth_login_success(mock_get_user):
    mock_get_user.return_value = mock_student

    client = TestClient(app)
    payload = {
        "user_email": "student@satr.edu",
        "user_password": "password123"
    }
    response = client.post("/api/v1/auth/login", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["user"]["user_role"] == "student"

@patch("src.models.UserModel.UserModel.get_user_by_id", new_callable=AsyncMock)
def test_auth_get_me(mock_get_user):
    mock_get_user.return_value = mock_student

    client = TestClient(app)
    response = client.get("/api/v1/auth/me", headers=student_headers)
    assert response.status_code == 200
    assert response.json()["user_id"] == mock_student.user_id

@patch("src.models.UserModel.UserModel.get_user_by_id", new_callable=AsyncMock)
@patch("src.models.UserModel.UserModel.email_exists", new_callable=AsyncMock)
def test_auth_update_profile(mock_email_exists, mock_get_user):
    mock_get_user.return_value = mock_student
    mock_email_exists.return_value = False
    mock_db["user"].update_one = AsyncMock(return_value=MagicMock(matched_count=1))

    client = TestClient(app)
    payload = {"user_name": "Updated Name", "user_email": "new_email@satr.edu"}
    response = client.put("/api/v1/auth/me/profile", json=payload, headers=student_headers)
    assert response.status_code == 200
    assert response.json()["status"] == "success"

@patch("src.models.UserModel.UserModel.get_user_by_id", new_callable=AsyncMock)
def test_auth_change_password(mock_get_user):
    mock_get_user.return_value = mock_student
    mock_db["user"].update_one = AsyncMock(return_value=MagicMock(matched_count=1))

    client = TestClient(app)
    payload = {"current_password": "password123", "new_password": "newpassword123"}
    response = client.put("/api/v1/auth/me/change-password", json=payload, headers=student_headers)
    assert response.status_code == 200
    assert response.json()["status"] == "success"

@patch("src.models.UserModel.UserModel.approve_teacher", new_callable=AsyncMock)
def test_auth_approve_teacher(mock_approve):
    mock_approve.return_value = True

    client = TestClient(app)
    # Operations role is required for approve endpoint
    response = client.put("/api/v1/auth/approve/some_teacher_id", headers=ops_headers)
    assert response.status_code == 200
    assert "approved successfully" in response.json()["message"]

# ══════════════════════════════════════════════════════════════════════════════
# Project Route Tests
# ══════════════════════════════════════════════════════════════════════════════

@patch("src.models.ProjectModel.ProjectModel.create_project", new_callable=AsyncMock)
def test_projects_create(mock_create_proj):
    mock_create_proj.return_value = True

    client = TestClient(app)
    payload = {"project_name": "Calculus II", "project_description": "University Calculus"}
    response = client.post("/api/v1/projects", json=payload, headers=teacher_headers)
    assert response.status_code == 201
    assert response.json()["status"] == "success"

@patch("src.models.ProjectModel.ProjectModel.get_all_projects", new_callable=AsyncMock)
def test_projects_list(mock_get_all):
    mock_project = Project(
        project_id="proj_1",
        project_name="Math",
        project_description="Calculus",
        project_files=[]
    )
    mock_get_all.return_value = {"projects": [mock_project], "total_document": 1, "total_page": 1}

    client = TestClient(app)
    response = client.get("/api/v1/projects", headers=student_headers)
    assert response.status_code == 200
    assert response.json()["status"] == "success"
    assert len(response.json()["projects"]) == 1

@patch("src.models.ProjectModel.ProjectModel.get_project", new_callable=AsyncMock)
def test_projects_get_single(mock_get_proj):
    mock_project = Project(
        project_id="proj_1",
        project_name="Math",
        project_description="Calculus",
        project_files=[]
    )
    mock_get_proj.return_value = mock_project

    client = TestClient(app)
    response = client.get("/api/v1/projects/proj_1", headers=student_headers)
    assert response.status_code == 200
    assert response.json()["project"]["project_name"] == "Math"

@patch("src.models.ProjectModel.ProjectModel.get_project", new_callable=AsyncMock)
def test_projects_get_single_not_found(mock_get_proj):
    mock_get_proj.return_value = None

    client = TestClient(app)
    response = client.get("/api/v1/projects/nonexistent_id", headers=student_headers)
    assert response.status_code == 404

# ══════════════════════════════════════════════════════════════════════════════
# Document Route Tests
# ══════════════════════════════════════════════════════════════════════════════

@patch("src.models.DocumentModel.DocumentModel.get_project_documents", new_callable=AsyncMock)
def test_documents_list(mock_get_docs):
    mock_doc = Document(
        document_id="doc_1",
        project_id="proj_1",
        file_name="algebra.pdf",
        status="processed"
    )
    mock_get_docs.return_value = {"documents": [mock_doc], "total": 1, "total_pages": 1, "page": 1}

    client = TestClient(app)
    response = client.get("/api/v1/documents/proj_1", headers=teacher_headers)
    assert response.status_code == 200
    assert len(response.json()["documents"]) == 1

@patch("src.models.DocumentModel.DocumentModel.get_document", new_callable=AsyncMock)
def test_documents_get_single(mock_get_doc):
    mock_doc = Document(
        document_id="doc_1",
        project_id="proj_1",
        file_name="algebra.pdf",
        status="processed"
    )
    mock_get_doc.return_value = mock_doc

    client = TestClient(app)
    response = client.get("/api/v1/documents/proj_1/doc_1", headers=teacher_headers)
    assert response.status_code == 200
    assert response.json()["document"]["file_name"] == "algebra.pdf"

# ══════════════════════════════════════════════════════════════════════════════
# AI Route Tests
# ══════════════════════════════════════════════════════════════════════════════

@patch("src.controllers.AIController.AIController.generate_exam_questions", new_callable=AsyncMock)
def test_ai_exam_generate(mock_gen):
    mock_gen.return_value = {
        "questions": [
            {
                "question_text": "What is 1+1?",
                "question_type": "MCQ",
                "options": ["A) 1", "B) 2", "C) 3", "D) 4"],
                "correct_answer": "B"
            }
        ]
    }

    client = TestClient(app)
    payload = {
        "content": "This content is long enough to meet the 50 characters threshold minimum requirement.",
        "num_questions": 1,
        "difficulty": "easy"
    }
    response = client.post("/api/v1/ai/exam/generate", json=payload, headers=teacher_headers)
    assert response.status_code == 200
    assert response.json()["questions_count"] == 1

@patch("src.controllers.AIController.AIController.summarize_content", new_callable=AsyncMock)
def test_ai_summarize(mock_sum):
    mock_sum.return_value = "This is a summary of the text."

    client = TestClient(app)
    payload = {
        "content": "This content is long enough to meet the 50 characters threshold minimum requirement."
    }
    response = client.post("/api/v1/ai/summarize", json=payload, headers=teacher_headers)
    assert response.status_code == 200
    assert response.json()["summary"] == "This is a summary of the text."

@patch("src.controllers.AIController.AIController.grade_essay", new_callable=AsyncMock)
def test_ai_grade_essay(mock_grade):
    mock_grade.return_value = {
        "score": 8,
        "feedback": "Good answer but missing details on photosynthesis."
    }

    client = TestClient(app)
    payload = {
        "question": "Describe photosynthesis.",
        "model_answer": "Photosynthesis is the process...",
        "student_answer": "It is how plants make food using sun light.",
        "max_score": 10
    }
    response = client.post("/api/v1/ai/grade/essay", json=payload, headers=teacher_headers)
    assert response.status_code == 200
    assert response.json()["grading_result"]["score"] == 8

# ══════════════════════════════════════════════════════════════════════════════
# Models Settings Route Tests
# ══════════════════════════════════════════════════════════════════════════════

def test_models_current():
    client = TestClient(app)
    response = client.get("/api/v1/models/current")
    assert response.status_code == 200
    assert "current_models" in response.json()

@patch("requests.get")
def test_models_available(mock_get):
    mock_get.return_value = MagicMock(
        status_code=200,
        json=lambda: {"models": [{"name": "llama3:latest", "size": 4700000000}]}
    )
    client = TestClient(app)
    response = client.get("/api/v1/models/available")
    assert response.status_code == 200
    assert response.json()["total"] == 1
    assert response.json()["models"][0]["name"] == "llama3:latest"

# ══════════════════════════════════════════════════════════════════════════════
# Evaluation Route Tests
# ══════════════════════════════════════════════════════════════════════════════

@patch("src.models.ProjectModel.ProjectModel.get_project", new_callable=AsyncMock)
@patch("src.controllers.NLPController.NLPController.search_vector_db_collection", new_callable=AsyncMock)
@patch("src.evaluation.retrieval_metrics.RetrievalEvaluator.evaluate", new_callable=AsyncMock)
def test_eval_retrieval(mock_eval, mock_search, mock_get_project):
    mock_get_project.return_value = Project(project_id="p1", project_name="p")
    mock_search.return_value = []
    mock_eval.return_value = {"hit_rate": 1.0, "mrr": 1.0}

    client = TestClient(app)
    payload = {"project_id": "p1", "query": "what is math?", "limit": 3}
    response = client.post("/api/v1/eval/retrieval", json=payload, headers=teacher_headers)
    assert response.status_code == 200
    assert response.json()["metrics"]["hit_rate"] == 1.0

# ══════════════════════════════════════════════════════════════════════════════
# Adaptive Learning Route Tests
# ══════════════════════════════════════════════════════════════════════════════

@patch("src.models.ExamResultModel.ExamResultModel.get_result", new_callable=AsyncMock)
def test_adaptive_explain_not_found(mock_get_res):
    mock_get_res.return_value = None

    client = TestClient(app)
    response = client.get("/api/v1/adaptive/explain/exam_999", headers=student_headers)
    assert response.status_code == 404

# ══════════════════════════════════════════════════════════════════════════════
# Streaming Route Tests
# ══════════════════════════════════════════════════════════════════════════════

def test_stream_ask_endpoint():
    client = TestClient(app)
    payload = {"project_id": "p1", "query": "hello", "language": "en"}
    # SSE responses are text/event-stream
    # TestClient supports streaming responses via stream=True or simple post
    response = client.post("/api/v1/stream/ask", json=payload)
    assert response.status_code == 200
    assert "text/event-stream" in response.headers["Content-Type"]

# ══════════════════════════════════════════════════════════════════════════════
# Admin Route Tests
# ══════════════════════════════════════════════════════════════════════════════

@patch("src.models.UserModel.UserModel.get_all_users", new_callable=AsyncMock)
@patch("src.models.UserModel.UserModel.count_users", new_callable=AsyncMock)
def test_admin_list_users(mock_count, mock_get_all):
    mock_get_all.return_value = [mock_student]
    mock_count.return_value = 1

    client = TestClient(app)
    response = client.get("/api/v1/admin/users", headers=ops_headers)
    assert response.status_code == 200
    assert len(response.json()["users"]) == 1

@patch("src.models.UserModel.UserModel.get_user_by_id", new_callable=AsyncMock)
def test_admin_get_user(mock_get_user):
    mock_get_user.return_value = mock_student

    client = TestClient(app)
    response = client.get(f"/api/v1/admin/users/{mock_student.user_id}", headers=ops_headers)
    assert response.status_code == 200
    assert response.json()["user"]["user_id"] == mock_student.user_id

def test_admin_storage_status():
    client = TestClient(app)
    response = client.get("/api/v1/admin/storage/status", headers=ops_headers)
    assert response.status_code == 200
    assert response.json()["status"] == "success"
