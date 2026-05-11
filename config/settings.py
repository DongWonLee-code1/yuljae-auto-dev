"""시스템 설정 및 환경변수 관리"""
from pydantic_settings import BaseSettings
from typing import Optional
import os


class Settings(BaseSettings):
    """시스템 전역 설정"""

    # 앱 기본 설정
    APP_NAME: str = "부동산 영업 데이터 자산화 시스템"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False

    # 데이터베이스 설정
    DATABASE_URL: str = "postgresql+asyncpg://localhost/yuljae_realestate"

    # STT 설정
    WHISPER_MODEL: str = "large-v3"
    AUDIO_SAMPLE_RATE: int = 16000

    # 분석 설정
    TRIGGER_WORD_THRESHOLD: float = 0.7
    SENTIMENT_MODEL: str = "klue/bert-base"

    # API 설정
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000

    # 저장 경로
    UPLOAD_DIR: str = "./uploads"
    TRANSCRIPT_DIR: str = "./transcripts"

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
"""
환경 설정 관리
Configuration Management
"""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """애플리케이션 설정"""

    # AssemblyAI 설정
    assemblyai_api_key: str

    # 처리 설정
    speaker_count: int = 2  # 예상 화자 수 (중개사 + 고객)
    language_code: str = "ko"  # 한국어
    punctuate: bool = True  # 자동 구두점
    format_text: bool = True  # 텍스트 정리

    # 파일 처리
    output_dir: str = "outputs"
    max_file_size_mb: int = 500  # AssemblyAI 제한

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
    }
