from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    APP_NAME: str = "Satr_Edu"
    APP_VERSION: str = "0.1"

    # File settings
    FILE_ALLOWED_EXTION: list = [".pdf", ".doc", ".docx", ".txt"]
    IMAGE_ALLOWED_EXTION: list = [".jpg", ".jpeg", ".png"]
    FILE_MAX_SIZE: int = 10
    FILE_DEFALUTE_CHUNK: int = 512000

    # OCR Model (local GPU — Florence-2)
    OCR_MODEL: str = "microsoft/Florence-2-base"

    # OCR Backend: "gemini" (cloud, recommended) | "local" (Florence-2, needs GPU) | "tesseract" (CPU fallback)
    OCR_BACKEND: str = "surya"
    SURYA_SERVICE_URL: str = "http://host.docker.internal:8765"

    # Gemini API (Google AI Studio — مجاني)
    # احصل عليه من: https://aistudio.google.com
    GEMINI_API_KEY: str = ""
    GEMINI_API_KEY_2: str = ""
    GEMINI_API_KEY_3: str = ""
    GEMINI_VISION_MODEL: str = "gemini-2.0-flash"

    # MongoDB
    MONGODB_URL: str = "mongodb://admin:admin@localhost:27017"
    MONGODB_DATABASE: str = "Satr-Edu"

    # LLM Backends
    GENERATION_BACKEND: str = "OPENAI"
    EMBEDDING_BACKEND: str = "COHERE"

    # OpenAI
    OPENAI_API_KEY: str = ""
    OPENAI_API_URL: str = "https://api.openai.com/v1"

    # Cohere
    COHERE_API_KEY: str = ""

    # Generation model
    GENERATION_MODEL_ID: str = "gpt-3.5-turbo-0125"
    EMBEDDING_MODEL_ID: str = "embed-multilingual-light-v3.0"
    EMBEDDING_MODEL_SIZE: int = 384

    # Generation defaults
    INPUT_DAFAULT_MAX_CHARACTERS: int = 1024
    GENERATION_DAFAULT_MAX_TOKENS: int = 200
    GENERATION_DAFAULT_TEMPERATURE: float = 0.1

    # Ollama (local)
    OLLAMA_BASE_URL: str = "http://localhost:11434"

    # Vector DB
    VECTOR_DB_BACKEND: str = "QDRANT"
    VECTOR_DB_PATH: str = "qdrant_db"
    VECTOR_DB_DISTANCE_METHOD: str = "cosine"

    # Reranker
    RERANKER_ENABLED: bool = True
    RERANKER_MODEL: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"
    RERANKER_TOP_K: int = 3

    # Multi-Retrieval (Qdrant vector + MongoDB keyword)
    MULTI_RETRIEVAL_ENABLED: bool = True
    VECTOR_SEARCH_LIMIT: int = 10     # كام نتيجة من Qdrant
    KEYWORD_SEARCH_LIMIT: int = 10    # كام نتيجة من MongoDB text search

    # Redis / Celery
    REDIS_URL: str = "redis://localhost:6379/0"

    # Auth / JWT
    JWT_SECRET_KEY: str = "satr-edu-super-secret-key-change-in-production"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 60 * 24  # 24 hours

    # MinIO Object Storage (optional — falls back to filesystem if unavailable)
    MINIO_ENDPOINT: str = "localhost:9000"
    MINIO_ACCESS_KEY: str = "minioadmin"
    MINIO_SECRET_KEY: str = "minioadmin123"
    MINIO_SECURE: bool = False
    MINIO_BUCKET: str = "satr-edu-files"

    # ── WhatsApp / Ultramsg ────────────────────────────────────────────
    # احصل عليهم من: https://app.ultramsg.com/
    ULTRAMSG_INSTANCE_ID: str = ""
    ULTRAMSG_TOKEN: str = ""

    # ── Absence Automation ────────────────────────────────────────
    ABSENCE_THRESHOLD: int = 3               # عدد مرات الغياب قبل الإشعار
    ABSENCE_COOLDOWN_DAYS: int = 7           # كم يوم بين كل إشعار والتالي (anti-spam)

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

def get_settings():
    return Settings()
