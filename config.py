from pydantic import ConfigDict
from pydantic_settings import BaseSettings
from pathlib import Path


class Settings(BaseSettings):
    model_config = ConfigDict(env_file=".env", env_file_encoding="utf-8")

    anthropic_api_key: str = ""
    openai_api_key: str = ""

    database_url: str = "sqlite:///./yuljae_data.db"

    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_debug: bool = False

    audio_storage_path: str = "./audio_files"
    max_audio_size_mb: int = 100

    claude_model: str = "claude-opus-4-7"
    claude_analysis_max_tokens: int = 4096
    whisper_model: str = "whisper-1"
    whisper_language: str = "ko"

    company_name: str = "율재부동산"
    min_opportunity_score: int = 60


settings = Settings()

# Ensure audio storage directory exists
Path(settings.audio_storage_path).mkdir(parents=True, exist_ok=True)
