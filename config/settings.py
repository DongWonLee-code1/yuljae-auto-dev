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
