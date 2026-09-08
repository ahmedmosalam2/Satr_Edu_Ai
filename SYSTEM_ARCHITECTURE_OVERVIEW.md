# Satr Edu - Complete System Architecture Overview

## 🏗️ System Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           FRONTEND (React/Vite)                              │
│                    c:\Users\Dell\Downloads\satr-edu                          │
│                                                                              │
│  Components:                                                                 │
│  ├─ Course Management (courses.service.js)                                  │
│  ├─ AI Chat & Smart Ask (ai.service.js)                                     │
│  ├─ Exams & Progress (exams.service.js)                                     │
│  ├─ Authentication (auth.service.js)                                        │
│  └─ Physics/Chemistry Tools (lab.js, electrical-circuit.js, etc.)           │
│                                                                              │
│  API Client: axios → VITE_API_URL or http://localhost:8000                 │
│  Proxy: /api → (VITE_API_URL || Django Backend at http://194.31.52.11)    │
└────────────────────────────────────────────────────────────────────────────┘
                              ↓ HTTP/REST
         ┌─────────────────────────────────────────────────────────────────────┐
         │         DJANGO BACKEND (Production / Main API)                      │
         │      c:\Users\Dell\Downloads\backend-grad                            │
         │         Running on http://194.31.52.11                              │
         │                                                                      │
         │  Technology Stack:                                                   │
         │  ├─ Django 4.2 + DRF (Django REST Framework)                        │
         │  ├─ PostgreSQL (primary database)                                   │
         │  ├─ Redis (caching, sessions)                                       │
         │  ├─ JWT Authentication (djangorestframework-simplejwt)              │
         │  └─ CORS + drf-spectacular (OpenAPI docs)                           │
         │                                                                      │
         │  Core Modules:                                                       │
         │  ├─ accounts/ - User management, authentication                     │
         │  ├─ courses/ - Course management & sync with AI backend             │
         │  ├─ lessons/ - Lesson content                                       │
         │  ├─ materials/ - Course materials (PDFs, docs)                      │
         │  ├─ exams/ - Exam management                                        │
         │  ├─ enrollments/ - Student enrollment                               │
         │  ├─ progress/ - Student progress tracking                           │
         │  ├─ notifications/ - Real-time notifications                        │
         │  ├─ parents/ - Parent portal                                        │
         │  ├─ dashboard/ - Admin/teacher dashboards                           │
         │  └─ ai_integration/ - Bridge to FastAPI AI Backend                  │
         │                                                                      │
         │  Key Endpoints:                                                      │
         │  ├─ /api/auth/login/ - User authentication                          │
         │  ├─ /api/auth/refresh/ - Token refresh                              │
         │  ├─ /api/courses/ - Course CRUD & listing                           │
         │  ├─ /api/courses/{id}/lessons/ - Lessons                            │
         │  ├─ /api/courses/{id}/materials/ - Materials upload                 │
         │  ├─ /api/courses/{id}/exams/ - Course exams                         │
         │  ├─ /api/courses/{id}/progress/ - Course progress                   │
         │  ├─ /api/courses/{id}/ai/chat/ - Chat with AI (proxies to FastAPI) │
         │  ├─ /api/courses/{id}/ai/smart-ask/ - Multi-agent AI               │
         │  ├─ /api/courses/{id}/ai/summary/ - AI summaries                    │
         │  ├─ /api/courses/{id}/ai/conversations/ - Chat history              │
         │  ├─ /api/ai/adaptive/ - Adaptive learning features                  │
         │  ├─ /api/exams/ - Exam management                                   │
         │  └─ /api/dashboard/ - Dashboard data                                │
         │                                                                      │
         │  AI Backend Communication:                                           │
         │  ├─ Base URL: AI_BACKEND_BASE_URL (default: http://194.31.52.11)  │
         │  ├─ Internal API Key: AI_BACKEND_INTERNAL_API_KEY                   │
         │  ├─ Timeout: 30 seconds                                             │
         │  ├─ Headers: X-Internal-API-Key, X-User-Id, X-User-Role            │
         │  └─ Client: AIBackendClient (ai_integration/client.py)              │
         └────────────────────────────────────────────────────────────────────┘
                       ↓ HTTP/REST (Internal API)
         ┌─────────────────────────────────────────────────────────────────────┐
         │         FASTAPI AI BACKEND (AI Services)                             │
         │          d:\Satr_Edu_Ai (main.py)                                   │
         │       Running on http://localhost:8000                              │
         │       (Docker: http://satr_edu_app:8000)                            │
         │                                                                      │
         │  Technology Stack:                                                   │
         │  ├─ FastAPI + Uvicorn                                               │
         │  ├─ MongoDB (vector database + metadata)                            │
         │  ├─ Qdrant (vector store for embeddings)                            │
         │  ├─ Redis (task queue, caching)                                     │
         │  ├─ MinIO (file storage)                                            │
         │  ├─ LangChain (RAG, document processing)                            │
         │  ├─ Ollama (local LLM, fallback)                                    │
         │  ├─ Cohere (embeddings)                                             │
         │  ├─ OpenAI (primary generation)                                     │
         │  ├─ Google Gemini (vision/OCR)                                      │
         │  ├─ Surya (OCR service at 8765)                                     │
         │  └─ PyTorch + HuggingFace (transformers)                            │
         │                                                                      │
         │  Core Routes (/api/v1/):                                             │
         │  ├─ / - Welcome/status                                              │
         │  ├─ /health - Health check                                          │
         │  │                                                                   │
         │  ├─ /projects - Project CRUD                                        │
         │  ├─ /documents/{project_id}/upload - File upload & processing       │
         │  ├─ /documents/{project_id}/list - List documents                   │
         │  ├─ /pipeline/strategies - Document chunking strategies             │
         │  │                                                                   │
         │  ├─ /chat/{project_id} - RAG chat (streaming)                       │
         │  ├─ /chat/conversations - List user conversations                   │
         │  ├─ /chat/conversations/{id} - Get conversation                     │
         │  ├─ /chat/conversations/{id}/clear - Clear history                  │
         │  │                                                                   │
         │  ├─ /agent/ask - Multi-agent RAG (with tools)                       │
         │  │  └─ Tools: KnowledgeSearch, Calculator, ConceptMap,              │
         │  │            PythonScratchpad                                       │
         │  │                                                                   │
         │  ├─ /ai/summarize - Text summarization                              │
         │  ├─ /ai/exam/generate - AI exam question generation                 │
         │  ├─ /ai/exam/grade-answer - Short answer grading                    │
         │  │                                                                   │
         │  ├─ /exam/create - Exam creation                                    │
         │  ├─ /exam/{id} - Exam retrieval                                     │
         │  ├─ /exam/{id}/submit - Submit exam answers                         │
         │  ├─ /exam/{id}/results - Get results                                │
         │  │                                                                   │
         │  ├─ /ocr/process-image - Image OCR (Gemini/Surya)                   │
         │  ├─ /ocr/process-pdf - PDF OCR                                      │
         │  │                                                                   │
         │  ├─ /stream/{project_id} - WebSocket streaming (future)             │
         │  │                                                                   │
         │  ├─ /analytics/* - Analytics & logging                              │
         │  ├─ /admin/* - Admin operations                                     │
         │  └─ /auth/* - Token & user authentication                           │
         │                                                                      │
         │  Key Controllers:                                                    │
         │  ├─ AIController - Exam generation, grading, summarization          │
         │  ├─ NLPController - Embeddings, retrieval, RAG                      │
         │  ├─ OCRController - Document & image OCR                            │
         │  ├─ ProjectController - Project management                          │
         │  └─ Specialized Controllers in src/tasks/ and src/evaluation/       │
         │                                                                      │
         │  LLM Provider Factory:                                               │
         │  ├─ Supports multiple backends (OpenAI, Cohere, Ollama, Gemini)    │
         │  ├─ Embeddings: COHERE (embed-multilingual-light-v3.0 - 384 dims) │
         │  ├─ Generation: OPENAI (gpt-3.5-turbo-0125)                         │
         │  └─ Fallback chain for robustness                                   │
         └────────────────────────────────────────────────────────────────────┘
                            ↓ Internal Docker Network
         ┌─────────────────────────────────────────────────────────────────────┐
         │                   INFRASTRUCTURE SERVICES                             │
         │                                                                      │
         │  MongoDB (Port 27017)                                                │
         │  ├─ Database: Satr-Edu                                              │
         │  ├─ Collections: projects, documents, chunks, conversations,        │
         │  │              exams, exam_results, users, etc.                    │
         │  └─ Volume: docker/data/mongodb/                                    │
         │                                                                      │
         │  Qdrant (Port 6333)                                                  │
         │  ├─ Vector database for embeddings                                  │
         │  ├─ Collections: project vectors, semantic search                   │
         │  └─ Volume: docker/data/qdrant_storage/                             │
         │                                                                      │
         │  Redis (Port 6379)                                                   │
         │  ├─ Caching layer                                                   │
         │  ├─ Celery task queue                                               │
         │  ├─ Session storage                                                 │
         │  └─ Real-time notifications                                         │
         │                                                                      │
         │  MinIO (Port 9000)                                                   │
         │  ├─ S3-compatible object storage                                    │
         │  ├─ Buckets: documents, images, exports                             │
         │  ├─ Credentials: minioadmin/minioadmin123                           │
         │  └─ Volume: docker/data/minio_storage/                              │
         │                                                                      │
         │  Ollama (Port 11434, optional)                                       │
         │  ├─ Local LLM service (fallback, can use local models)              │
         │  ├─ Detected via: localhost, 127.0.0.1, WSL2 gateway, or           │
         │  │               host.docker.internal                               │
         │  └─ Health checked on startup                                       │
         │                                                                      │
         │  Surya OCR Service (Port 8765)                                       │
         │  ├─ External OCR service (accessible from container)                │
         │  ├─ Alternative to Gemini OCR                                       │
         │  └─ Set via SURYA_SERVICE_URL env var                               │
         │                                                                      │
         │  NGINX Load Balancer (Port 80)                                       │
         │  ├─ Reverse proxy                                                   │
         │  ├─ Routes traffic to FastAPI app                                   │
         │  └─ Config: docker/nginx.conf                                       │
         └────────────────────────────────────────────────────────────────────┘
```

---

## 📁 Project Details

### 1️⃣ **Satr_Edu_Ai** (FastAPI Backend - AI Services)
**Location:** `d:\Satr_Edu_Ai`

#### Dependencies (requirements.txt)
```
FastAPI + Uvicorn
MongoDB (motor async driver)
Qdrant (vector database)
LangChain + LangChain Community
OpenAI + Cohere APIs
Google Gemini Vision
PyTorch + Transformers + TensorFlow
Sentence Transformers
PyPDF2, pdfplumber, unstructured (document parsing)
Pytesseract, PyMuPDF (OCR)
Python-docx, python-pptx, openpyxl (office docs)
Celery + Redis
FastAPI-JWT authentication
```

#### Main Routes

| Method | Endpoint | Purpose |
|--------|----------|---------|
| **GET** | `/api/v1/` | Welcome message & status |
| **GET** | `/api/v1/health` | Service health check |
| **POST** | `/api/v1/projects` | Create project |
| **GET** | `/api/v1/projects` | List projects |
| **POST** | `/api/v1/documents/{project_id}/upload` | Upload & process file |
| **POST** | `/api/v1/chat/{project_id}` | RAG chat (streaming) |
| **POST** | `/api/v1/agent/ask` | Multi-agent RAG with tools |
| **POST** | `/api/v1/ai/exam/generate` | Generate exam questions |
| **POST** | `/api/v1/ai/exam/grade-answer` | Grade short answers |
| **POST** | `/api/v1/ai/summarize` | Summarize documents |
| **POST** | `/api/v1/exam/create` | Create exam |
| **POST** | `/api/v1/exam/{exam_id}/submit` | Submit exam answers |
| **GET** | `/api/v1/exam/{exam_id}/results` | Get exam results |
| **POST** | `/api/v1/ocr/process-image` | OCR on images |
| **POST** | `/api/v1/pipeline/process` | Generic document processing |

#### Configuration (src/helpers/config.py)
```python
# LLM Backends
GENERATION_BACKEND = "OPENAI"
GENERATION_MODEL_ID = "gpt-3.5-turbo-0125"
EMBEDDING_BACKEND = "COHERE"
EMBEDDING_MODEL_ID = "embed-multilingual-light-v3.0"
EMBEDDING_MODEL_SIZE = 384

# APIs
OPENAI_API_KEY = ""  # From .env
COHERE_API_KEY = ""
GEMINI_API_KEY = ""
GEMINI_VISION_MODEL = "gemini-2.0-flash"

# Databases
MONGODB_URL = "mongodb://admin:admin@localhost:27017"
MONGODB_DATABASE = "Satr-Edu"

# OCR
OCR_BACKEND = "surya"  # or "gemini", "local" (Florence-2)
SURYA_SERVICE_URL = "http://host.docker.internal:8765"
```

#### Docker Services (docker-compose.yml)
```yaml
services:
  mongodb:     # Port 27017
  redis:       # Port 6379
  qdrant:      # Port 6333
  minio:       # Port 9000
  app:         # FastAPI, Port 8000
  nginx:       # Reverse proxy, Port 80
```

---

### 2️⃣ **satr-edu** (Frontend - React/Vite)
**Location:** `c:\Users\Dell\Downloads\satr-edu`

#### Tech Stack
- **Framework:** React 18 + Vite
- **API Client:** Axios
- **Styling:** TailwindCSS + custom CSS
- **State Management:** Context API + custom hooks
- **Build Tool:** Vite with hot module replacement

#### API Configuration (vite.config.js)
```javascript
const apiUrl = env.VITE_API_URL || "http://localhost:8000";

server: {
  proxy: {
    "/api": {
      target: apiUrl,  // Points to Django backend or FastAPI
      changeOrigin: true,
      secure: false,
    },
  },
}
```

#### API Client (src/api/client.js)
```javascript
const API_URL = stripTrailing(import.meta.env.VITE_API_URL || "");
const baseURL = API_URL ? `${API_URL}/api` : "/api";

axios.create({
  baseURL,
  headers: { "Content-Type": "application/json" },
});

// Interceptors: JWT token in Authorization header
// Token stored in localStorage
```

#### Services

| Service | Endpoints | Purpose |
|---------|-----------|---------|
| **auth.service.js** | `/auth/login/`, `/auth/register/`, `/auth/refresh/` | User authentication |
| **courses.service.js** | `/courses/`, `/courses/{id}/lessons/`, `/courses/{id}/materials/` | Course management |
| **ai.service.js** | `/courses/{id}/ai/chat/`, `/courses/{id}/ai/smart-ask/`, `/ai/conversations/` | AI chat & adaptive learning |
| **exams.service.js** | `/courses/{id}/exams/`, `/exams/{id}/submit/` | Exam management |
| **materials.service.js** | `/courses/{id}/materials/` | Course materials |
| **progress.service.js** | `/progress/`, `/courses/{id}/progress/` | Student progress |
| **dashboard.service.js** | `/dashboard/` | Dashboard data |

#### Interactive Tools (public/tools/)
```
electrical-circuit.html     → physics_electrical_circuit.js
inclined-plane.html         → physics_inclined.js
mass-spring.html            → physics_mass_spring.js
pendulum.html               → physics_pendulum.js
projectile.html             → physics_projectile.js
ph-indicator.html           → ph_indicator.js
precipitation.html          → precipitation.js
titration.html              → titration.js
solubility.html             → solubility.js
reaction-rate.html          → reaction_rate.js
```

---

### 3️⃣ **backend-grad** (Django REST Backend - Main API)
**Location:** `c:\Users\Dell\Downloads\backend-grad`

#### Tech Stack
- **Framework:** Django 4.2 + Django REST Framework
- **Database:** PostgreSQL (primary)
- **Cache:** Redis + django-redis
- **Authentication:** JWT (djangorestframework-simplejwt)
- **Task Queue:** Celery + Redis
- **Documentation:** drf-spectacular (OpenAPI/Swagger)

#### Dependencies (requirements.txt)
```
Django 4.2
djangorestframework
djangorestframework-simplejwt
django-cors-headers
psycopg2-binary (PostgreSQL driver)
Celery + Redis
Pillow (image processing)
Gunicorn
drf-spectacular (OpenAPI)
```

#### Configuration (satr_edu/settings.py)
```python
# Database
DATABASES = {
    "default": env.db(
        "DATABASE_URL",
        default="postgres://satredu:satredu_pass@localhost:5432/satredu_db"
    )
}

# AI Backend Integration
AI_BACKEND_BASE_URL = os.getenv("AI_BACKEND_BASE_URL", "http://194.31.52.11")
AI_BACKEND_INTERNAL_API_KEY = os.getenv("AI_BACKEND_INTERNAL_API_KEY", "")
AI_BACKEND_TIMEOUT = 30

# CORS
CORS_ALLOWED_ORIGINS = ["http://localhost:3000", "http://194.31.52.11"]

# Authentication
AUTH_USER_MODEL = "accounts.User"
INSTALLED_APPS = [
    ..., "rest_framework", "rest_framework_simplejwt", "corsheaders", ...
]
```

#### Main Endpoints (satr_edu/urls.py)
```
/api/auth/              → accounts.urls (login, register, refresh, profile)
/api/admin/             → accounts.admin_urls (admin operations)
/api/                   → courses.urls (course management)
/api/                   → lessons.urls (lesson management)
/api/                   → materials.urls (materials upload)
/api/                   → enrollments.urls (student enrollment)
/api/                   → exams.urls (exam endpoints)
/api/                   → progress.urls (progress tracking)
/api/notifications/     → notifications.urls (notifications)
/api/parents/           → parents.urls (parent portal)
/api/                   → ai_integration.urls (AI bridge)
/api/dashboard/         → dashboard.urls (dashboard data)
/api/schema/            → OpenAPI schema
/api/docs/              → Swagger UI documentation
```

#### AI Integration Routes (ai_integration/urls.py)
```python
/api/courses/{course_id}/ai/chat/              → AIChatView
/api/courses/{course_id}/ai/conversations/     → AIConversationListView
/api/ai/conversations/{id}/                    → AIConversationDetailView
/api/courses/{course_id}/ai/smart-ask/         → AISmartAskView
/api/courses/{course_id}/ai/summary/           → AISummaryView
/api/ai/adaptive/explain/{exam_id}/            → AdaptiveExplainView
/api/ai/adaptive/recommendations/              → AdaptiveRecommendationsView
/api/ai/adaptive/study-plan/                   → AdaptiveStudyPlanView
/api/ai/adaptive/dashboard/                    → AdaptiveDashboardView
/api/ai/adaptive/progress/                     → AdaptiveProgressView
```

#### AI Backend Client (ai_integration/client.py)
```python
class AIBackendClient:
    def __init__(self):
        self.base_url = settings.AI_BACKEND_BASE_URL  # e.g., http://194.31.52.11/api/v1
        self.api_key = settings.AI_BACKEND_INTERNAL_API_KEY
        self.timeout = 30
    
    # Methods:
    # chat(project_id, text, user, conversation_id, limit)
    # list_conversations(user, page, page_size)
    # get_conversation(conversation_id, user)
    # delete_conversation(conversation_id, user)
    # summarize(text)
    # generate_exam(prompt, exam_type, language)
    # grade_short_answer(question, student_answer, model_answer)
    # create_project(name, description)
    # upload_file(project_id, file)
    # ... and more
```

**Headers for every request to FastAPI:**
```
X-Internal-API-Key: <AI_BACKEND_INTERNAL_API_KEY>
X-User-Id: <django_user_id>
X-User-Role: <django_user_role>  # e.g., "teacher", "student", "admin"
```

---

## 🔄 Communication Flow

### Flow 1: User Signup/Login
```
Frontend (React)
  ↓ POST /api/auth/login/ (credentials)
Django Backend
  ↓ Validates credentials
  ↓ Returns JWT tokens
Frontend
  ↓ Stores tokens in localStorage
  ↓ Includes Bearer token in all subsequent requests
```

### Flow 2: Student Enrolls in Course
```
Frontend
  ↓ POST /api/courses/{id}/enroll/
Django Backend (Enrollment)
  ↓ Checks permissions
  ↓ Creates enrollment record in PostgreSQL
  ↓ (Optional) Syncs AI project: calls AIBackendClient.create_project()
FastAPI Backend
  ↓ Creates project in MongoDB
  ↓ Initializes vector store in Qdrant
```

### Flow 3: Course Material Upload
```
Frontend (Teacher)
  ↓ POST /api/courses/{id}/materials/ (file)
Django Backend (Materials)
  ↓ Validates file
  ↓ Calls AIBackendClient.upload_file(project_id, file)
FastAPI Backend (Documents)
  ↓ Saves file to MinIO or disk
  ↓ Runs document pipeline:
  │  ├─ Detects file type (PDF, DOCX, etc.)
  │  ├─ Extracts text (PyPDF2, python-docx, etc.)
  │  ├─ Chunks text (naive, structure, or semantic)
  │  ├─ Generates embeddings (Cohere)
  │  ├─ Stores in Qdrant + MongoDB
  │  └─ Returns processing status
```

### Flow 4: Student Asks AI Question
```
Frontend (Student)
  ↓ POST /api/courses/{id}/ai/chat/ (text, conversation_id)
Django Backend (AI Integration)
  ↓ Validates access permissions
  ↓ Calls AIBackendClient.chat(
       project_id, text, user, conversation_id
     )
FastAPI Backend (Chat)
  ↓ Retrieves conversation context
  ↓ Searches Qdrant for relevant chunks (RAG)
  ↓ Builds context from top-k results
  ↓ Sends to OpenAI (with system prompt)
  ↓ Streams response back
  ↓ Saves message to MongoDB conversation
  ↓ Returns structured response with sources
Django Backend
  ↓ Returns response to Frontend
Frontend
  ↓ Displays chat message + sources
```

### Flow 5: AI Exam Generation
```
Frontend (Teacher)
  ↓ POST /api/courses/{id}/ai/exam/generate/
Django Backend (Exams)
  ↓ Validates permission (must be teacher)
  ↓ Calls AIBackendClient.generate_exam(...)
FastAPI Backend (AI Controller)
  ↓ Retrieves course project/content
  ↓ Passes to OpenAI with prompt engineering
  ↓ OpenAI generates structured exam JSON
  │  ├─ question_id, question_text, question_type
  │  ├─ options (for MCQ), correct_answer
  │  ├─ points, chunk_ref
  │  └─ language (ar/en)
  ├─ Stores exam in MongoDB
  ├─ Returns exam to Django
Django Backend
  ├─ Maps exam to Django Exam model
  ├─ Saves to PostgreSQL
  ├─ Returns to Frontend
```

### Flow 6: Exam Submission & Grading
```
Frontend (Student)
  ↓ POST /api/exams/{id}/submit/ (answers)
Django Backend (Exams)
  ↓ Validates exam availability & deadline
  ↓ For each answer:
  │  └─ If short-answer: calls AIBackendClient.grade_short_answer()
FastAPI Backend (AI Controller)
  ├─ Compares student answer with expected answer
  ├─ Uses OpenAI for semantic similarity
  ├─ Returns score + feedback
Django Backend
  ├─ Saves scores to PostgreSQL (exam_result table)
  ├─ Calculates final grade
  ├─ Triggers adaptive learning recommendations
  └─ Returns results to Frontend
Frontend
  ├─ Displays grade + detailed feedback
  └─ Shows areas for improvement
```

### Flow 7: Smart Ask (Multi-Agent RAG)
```
Frontend
  ↓ POST /api/courses/{id}/ai/smart-ask/ (query)
Django Backend
  ↓ Calls AIBackendClient with multi-agent flag
FastAPI Backend (Agent)
  ├─ Initializes RAGAgent with tools:
  │  ├─ KnowledgeSearchTool (vector search in Qdrant)
  │  ├─ CalculatorTool (arithmetic operations)
  │  ├─ ConceptMapTool (generates concept diagrams)
  │  └─ PythonScratchpadTool (executes safe Python code)
  ├─ Runs agent loop (ReAct pattern):
  │  ├─ Agent decides which tool to use
  │  ├─ Calls tool
  │  ├─ Observes result
  │  ├─ Repeats until done
  ├─ Generates final answer
  └─ Returns: answer, steps, confidence
```

---

## 📊 Database Schema Overview

### FastAPI Backend (MongoDB)
```
Collections:
├─ projects
│  ├─ _id, name, description, teacher_id, created_at
│  └─ metadata (file counts, chunk counts, vector store status)
├─ documents
│  ├─ _id, project_id, file_name, file_type, status
│  ├─ file_path, chunk_strategy, chunk_size, chunk_overlap
│  └─ created_at, updated_at
├─ chunks (data_chunk)
│  ├─ _id, document_id, project_id, chunk_index
│  ├─ text, page_number, vector_id (reference to Qdrant)
│  └─ metadata (line_count, word_count, etc.)
├─ conversations
│  ├─ _id, project_id, user_id, title
│  ├─ messages: [{ role, text, timestamp, sources }]
│  └─ created_at, updated_at, last_accessed
├─ exams
│  ├─ _id, project_id, exam_id, exam_type, language
│  ├─ questions: [{ question_id, text, type, options, answer, points }]
│  └─ created_at, approved_at
├─ exam_results
│  ├─ _id, exam_id, student_id, submission_time
│  ├─ answers: [{ question_id, student_answer, score, feedback }]
│  ├─ total_score, passed
│  └─ submission_time, completed_at
```

### FastAPI Backend (Qdrant)
```
Collections:
├─ project_embeddings
│  ├─ vectors: 384-dim (Cohere embeddings)
│  ├─ payload: { chunk_id, project_id, document_id, text_preview }
│  └─ Used for semantic search in RAG
```

### Django Backend (PostgreSQL)
```
Tables:
├─ accounts_user
│  ├─ id, username, email, role (teacher/student/admin/parent)
│  ├─ password_hash, is_active, created_at
│  └─ profile (name, bio, profile_pic)
├─ courses_course
│  ├─ id, name, description, teacher_id, code
│  ├─ ai_project_id (links to FastAPI project)
│  ├─ created_at, updated_at
│  └─ metadata (enrollment count, material count)
├─ lessons_lesson
│  ├─ id, course_id, title, content, order
│  ├─ video_url, duration, created_at
├─ materials_material
│  ├─ id, course_id, file_name, file_url, upload_date
│  ├─ size, file_type
├─ enrollments_enrollment
│  ├─ id, student_id, course_id, status (active/completed/dropped)
│  ├─ enrollment_date, progress_percentage
├─ exams_exam
│  ├─ id, course_id, title, exam_type (quiz/midterm/final)
│  ├─ questions: [{ id, text, type, options, answer }]
│  ├─ duration, passing_score, created_at
│  └─ approved_at, approved_by
├─ exams_examresult
│  ├─ id, exam_id, student_id, score, passed
│  ├─ submitted_at, graded_at
├─ progress_progress
│  ├─ id, student_id, course_id, lesson_id
│  ├─ completion_percentage, last_accessed
├─ notifications_notification
│  ├─ id, user_id, type (message/assignment/grade/announcement)
│  ├─ content, read_at, created_at
```

---

## 🔐 Authentication & Authorization

### Frontend → Django Backend
1. **Login:** POST `/api/auth/login/` → Returns `{access_token, refresh_token}`
2. **Token Storage:** localStorage (`access_token`, `refresh_token`)
3. **Request Headers:** `Authorization: Bearer <access_token>`
4. **Token Refresh:** POST `/api/auth/refresh/` → Returns new `access_token`

### Django Backend → FastAPI Backend
1. **Internal API Key:** `X-Internal-API-Key` header (secrets, no JWT)
2. **User Context:** `X-User-Id` and `X-User-Role` headers (passed from Django request)
3. **No separate authentication:** FastAPI trusts Django's verification

### Role-Based Access Control
- **Teacher:** Can create projects, upload materials, create exams, grade answers
- **Student:** Can view materials, take exams, chat with AI, access adaptive learning
- **Admin:** Full access to all resources
- **Parent:** Limited access to child's progress

---

## 🌍 Environment Configuration

### Frontend (satr-edu)
```env
VITE_API_URL=http://localhost:8000  # Points to Django or FastAPI
```

### FastAPI Backend (Satr_Edu_Ai .env)
```env
# LLM APIs
OPENAI_API_KEY=sk-...
COHERE_API_KEY=...
GEMINI_API_KEY=...

# Databases
MONGODB_URL=mongodb://admin:admin@localhost:27017
VECTOR_DB_PATH=http://localhost:6333  # Qdrant

# Storage
MINIO_ENDPOINT=localhost:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin123

# Ollama (optional local LLM)
OLLAMA_BASE_URL=http://localhost:11434

# OCR
OCR_BACKEND=surya  # or gemini, local
SURYA_SERVICE_URL=http://localhost:8765
```

### Django Backend (backend-grad .env)
```env
# Database
DATABASE_URL=postgres://satredu:satredu_pass@localhost:5432/satredu_db

# AI Backend Integration
AI_BACKEND_BASE_URL=http://194.31.52.11/api/v1  # FastAPI endpoint
AI_BACKEND_INTERNAL_API_KEY=<secret_key>

# JWT
SECRET_KEY=django-secret-key
DEBUG=False

# CORS
ALLOWED_HOSTS=localhost,194.31.52.11
CORS_ALLOWED_ORIGINS=http://localhost:3000,http://194.31.52.11
```

---

## 📈 Data Flow Example: Complete User Journey

### 1. Signup
```
User → Frontend (React)
  ↓ Enters credentials
  ↓ POST /api/auth/register/ → Django
  ↓ Django validates & creates User in PostgreSQL
  ↓ Returns JWT tokens
  ↓ Frontend stores tokens → localStorage
```

### 2. Browse Courses
```
User → Frontend
  ↓ GET /api/courses/ → Django (with JWT)
  ↓ Django queries PostgreSQL → returns list
  ↓ Frontend displays courses
```

### 3. Enroll in Course
```
User (Student) → Frontend
  ↓ POST /api/courses/1/enroll/ → Django
  ↓ Django creates Enrollment record
  ↓ Returns success
  ↓ Frontend updates course list
```

### 4. View Materials
```
User → Frontend
  ↓ GET /api/courses/1/materials/ → Django
  ↓ Django queries PostgreSQL
  ↓ Returns list of materials + file URLs
  ↓ Frontend displays materials
```

### 5. Upload Material (Teacher)
```
Teacher → Frontend
  ↓ POST /api/courses/1/materials/ (file) → Django
  ↓ Django validates permission
  ↓ Calls AIBackendClient.upload_file()
  ↓ FastAPI processes: extract text → chunk → embed → store in Qdrant
  ↓ Returns success
  ↓ Frontend shows processing status
```

### 6. Ask AI Question
```
Student → Frontend (Chat UI)
  ↓ Types question → "Explain photosynthesis"
  ↓ POST /api/courses/1/ai/chat/ → Django
  ↓ Django: calls AIBackendClient.chat()
FastAPI:
  ├─ Searches Qdrant for relevant chunks (top-5)
  ├─ Builds prompt with chunks + question
  ├─ Calls OpenAI API
  ├─ Streams response back
  ├─ Saves to MongoDB conversations collection
  └─ Returns: {answer, sources: [{chunk_id, document, excerpt}]}
Django → Frontend
  ↓ Returns response with sources
  ↓ Frontend displays: answer + cited sources
  ↓ Student can click sources → view document excerpt
```

### 7. Generate Exam
```
Teacher → Frontend
  ↓ Clicks "Generate Exam with AI"
  ↓ POST /api/courses/1/ai/exam/generate/ → Django
  ↓ Django calls AIBackendClient.generate_exam()
FastAPI:
  ├─ Gets project content from MongoDB
  ├─ Calls OpenAI with structured prompt
  ├─ OpenAI returns: [{question_text, options, correct_answer, points, ...}]
  ├─ Stores in MongoDB exams collection
  └─ Returns exam structure
Django:
  ├─ Maps to Exam model
  ├─ Stores in PostgreSQL
  └─ Returns to Frontend
Frontend:
  ├─ Displays exam preview
  ├─ Teacher can edit, delete, or approve
  └─ Once approved → students can take
```

### 8. Take Exam
```
Student → Frontend (Exam UI)
  ↓ Starts exam
  ├─ For MCQ: selects option
  ├─ For short answer: types text
  ↓ Submits exam
  ↓ POST /api/exams/1/submit/ (answers) → Django
Django:
  ├─ Validates exam still available
  ├─ For short answers: calls AIBackendClient.grade_short_answer()
FastAPI:
  ├─ Uses semantic similarity (Cohere embeddings + cosine)
  ├─ Returns: score (0-100), feedback
Django:
  ├─ Records scores in PostgreSQL exam_result
  ├─ Calls adaptive learning API
  └─ Returns grade + feedback
Frontend:
  ├─ Shows grade
  ├─ Shows feedback for each answer
  └─ Links to adaptive learning recommendations
```

---

## 🚀 Deployment Architecture

### Local Development
```
Frontend:    http://localhost:3000 (Vite dev server)
Django:      http://localhost:8001 (Django runserver)
FastAPI:     http://localhost:8000 (Uvicorn)
PostgreSQL:  localhost:5432
MongoDB:     localhost:27017
Qdrant:      localhost:6333
Redis:       localhost:6379
MinIO:       localhost:9000
```

### Docker Production (Satr_Edu_Ai)
```
Frontend:    http://194.31.52.11:3000 (React app via Nginx)
Django:      http://194.31.52.11/api (Nginx reverse proxy)
FastAPI:     http://satr_edu_app:8000 (internal Docker network)
NGINX:       Port 80 (reverse proxy)
Services:    Internal Docker network (mongodb, redis, qdrant, minio)
```

### Production Server Setup
```
194.31.52.11 (Main server)
├─ Nginx (reverse proxy)
│  ├─ /api → Django backend (Gunicorn)
│  └─ / → React frontend (static)
├─ Django backend (Gunicorn + Supervisor)
│  ├─ PostgreSQL driver
│  └─ HTTPClient to FastAPI
├─ FastAPI backend (Docker container or Uvicorn)
│  └─ Internal MongoDB, Redis, Qdrant, MinIO
└─ Celery workers (task queue)
```

---

## 🔍 Key Integration Points

### 1. AI Project Sync
- When teacher creates course → optionally creates AI project in FastAPI
- `course.ai_project_id` links Django course to FastAPI project

### 2. Material Upload → Vector Store
- Material uploaded to Django → sent to FastAPI
- FastAPI stores file + creates embeddings → stores in Qdrant
- Next chat queries Qdrant for relevant context

### 3. Exam Generation → Question Bank
- FastAPI generates exam questions
- Django stores in PostgreSQL
- Teacher can approve/edit before deployment

### 4. Adaptive Learning
- Student exam results → stored in PostgreSQL
- Django calls adaptive endpoints in FastAPI
- FastAPI generates personalized recommendations

### 5. Real-time Updates
- Redis subscriptions for notifications
- WebSocket streaming (future: `/api/v1/stream/`)
- Celery tasks for async processing

---

## ⚙️ System Health Checks

```bash
# FastAPI
GET http://localhost:8000/api/v1/health
→ {
    "status": "healthy",
    "services": {
      "mongodb": "connected",
      "llm_provider": "ready"
    }
  }

# Django (API endpoints)
GET http://localhost:8001/api/docs/  → Swagger documentation

# Frontend
GET http://localhost:3000/           → React app

# Services
MongoDB:  mongosh → admin.command("ping")
Qdrant:   curl http://localhost:6333/health → {"status":"ok"}
Redis:    redis-cli ping → PONG
MinIO:    curl http://localhost:9000/minio/health/live → {}
```

---

## 📚 Technology Matrix

| Layer | Tech | Purpose | Details |
|-------|------|---------|---------|
| **Frontend** | React 18 | UI Framework | Component-based, hooks, context |
| | Vite | Build Tool | Fast dev server, optimized builds |
| | Axios | HTTP Client | REST API calls, JWT interceptors |
| | TailwindCSS | Styling | Utility-first CSS |
| **Backend (Main)** | Django 4.2 | Web Framework | ORM, middleware, admin panel |
| | DRF | API Framework | Serializers, viewsets, permissions |
| | PostgreSQL | Primary DB | User accounts, courses, exams, results |
| | Redis | Cache/Queue | Celery tasks, session cache |
| **Backend (AI)** | FastAPI | Async API | High-performance async endpoints |
| | MongoDB | NoSQL DB | Flexible schema for AI data |
| | Qdrant | Vector DB | Semantic search, RAG retrieval |
| | LangChain | RAG Framework | Document chunking, retrieval chains |
| | OpenAI | LLM | Text generation (primary) |
| | Cohere | Embeddings | 384-dim multilingual embeddings |
| | Gemini | Vision | Image OCR, vision tasks |
| | Ollama | Local LLM | Fallback for on-premise setup |
| **Infrastructure** | Docker | Containerization | Compose for multi-service |
| | Nginx | Reverse Proxy | Load balancing, SSL termination |
| | Celery | Task Queue | Async jobs, scheduled tasks |
| | MinIO | File Storage | S3-compatible object storage |

---

## 🎯 Summary

**Satr Edu** is a comprehensive educational platform with:

1. **Frontend:** React/Vite SPA with interactive physics/chemistry tools
2. **Main Backend:** Django REST for user management, courses, exams (production server)
3. **AI Backend:** FastAPI microservice for LLM/RAG, document processing, exam generation
4. **Communication:** Django → FastAPI via internal HTTP + headers (AI_BACKEND_CLIENT)
5. **Databases:** PostgreSQL (courses/users), MongoDB (AI/conversations), Qdrant (vectors)
6. **Services:** Redis (cache/queue), MinIO (storage), Ollama (local LLM)

The architecture enables:
- ✅ AI-powered exam generation
- ✅ Intelligent tutoring (RAG-based chat)
- ✅ Multi-agent reasoning (Agent/Tools)
- ✅ Semantic answer grading
- ✅ Adaptive learning recommendations
- ✅ Interactive STEM labs
- ✅ Multi-language support (AR/EN)
