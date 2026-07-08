from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    DEEPSEEK_API_KEY: str = ""
    DEEPSEEK_MODEL: str = "deepseek-chat"
    DEEPSEEK_BASE_URL: str = "https://api.deepseek.com"
    BACKEND_URL: str = "http://127.0.0.1:7860"
    class Config:
        env_file = ".env"

settings = Settings()
