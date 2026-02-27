from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://nbplab:nbplab@localhost:5432/nbplab"
    database_url_sync: str = "postgresql://nbplab:nbplab@localhost:5432/nbplab"
    redis_url: str = "redis://localhost:6379/0"
    gemini_api_key: str = ""
    telemetry_default: bool = False
    upload_dir: str = "uploads"
    export_dir: str = "exports"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}


settings = Settings()
