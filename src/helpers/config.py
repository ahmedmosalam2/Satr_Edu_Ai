from pydantic_settings import BaseSettings,SettingsConfigDict

class Settings(BaseSettings):
    APP_NAME:str
    APP_VERSION:str
    OPENAI_API_KEY:str
    FILE_ALLOWED_EXTION:list[str]
    IMAGE_ALLOWED_EXTION:list[str]
    FILE_MAX_SIZE:int
    FILE_DEFALUTE_CHUNK:int
    OCR_MODEL:str
    MONGODB_URL:str
    MONGODB_DATABASE:str
    class Config:
        env_file=".env"
        env_file_encoding="utf-8"
    
def get_settings():
    return Settings()
