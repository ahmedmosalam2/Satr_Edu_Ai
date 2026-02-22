from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    APP_NAME: str = "Satr_Edu"
    APP_VERSION: str = "0.1"

    # File settings
    FILE_ALLOWED_EXTION: list = [".pdf", ".doc", ".docx", ".txt"]
    IMAGE_ALLOWED_EXTION: list = [".jpg", ".jpeg", ".png"]
    FILE_MAX_SIZE: int = 10
    FILE_DEFALUTE_CHUNK: int = 512000

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

    # Vector DB
    VECTOR_DB_BACKEND: str = "QDRANT"
    VECTOR_DB_PATH: str = "qdrant_db"
    VECTOR_DB_DISTANCE_METHOD: str = "cosine"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

def get_settings():
    return Settings()
