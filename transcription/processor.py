"""
통화 녹음 파일을 텍스트로 변환하는 STT 프로세서.
OpenAI Whisper API를 사용하여 한국어 음성을 정확하게 인식.
"""
import os
import hashlib
from dataclasses import dataclass, field
from pathlib import Path
from datetime import datetime

from openai import OpenAI
from tenacity import retry, stop_after_attempt, wait_exponential

from config import settings


@dataclass
class TranscriptionResult:
    file_path: str
    text: str
    language: str
    duration_seconds: float
    file_hash: str
    created_at: datetime = field(default_factory=datetime.utcnow)
    segments: list[dict] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)


class TranscriptionProcessor:
    SUPPORTED_FORMATS = {".mp3", ".mp4", ".mpeg", ".mpga", ".m4a", ".wav", ".webm", ".ogg"}
    MAX_FILE_SIZE_BYTES = settings.max_audio_size_mb * 1024 * 1024

    def __init__(self):
        self.client = OpenAI(api_key=settings.openai_api_key)

    def process_file(self, file_path: str | Path) -> TranscriptionResult:
        path = Path(file_path)
        self._validate_file(path)

        file_hash = self._compute_hash(path)
        file_size = path.stat().st_size

        transcript = self._transcribe(path)

        return TranscriptionResult(
            file_path=str(path.absolute()),
            text=transcript.text,
            language=transcript.language if hasattr(transcript, "language") else settings.whisper_language,
            duration_seconds=self._estimate_duration(file_size),
            file_hash=file_hash,
            segments=getattr(transcript, "segments", []),
            metadata={
                "file_name": path.name,
                "file_size_bytes": file_size,
                "model": settings.whisper_model,
            },
        )

    def process_bytes(self, audio_bytes: bytes, filename: str) -> TranscriptionResult:
        suffix = Path(filename).suffix.lower()
        if suffix not in self.SUPPORTED_FORMATS:
            raise ValueError(f"지원하지 않는 오디오 형식: {suffix}")

        temp_path = Path(settings.audio_storage_path) / f"_tmp_{hashlib.md5(audio_bytes).hexdigest()}{suffix}"
        try:
            temp_path.write_bytes(audio_bytes)
            return self.process_file(temp_path)
        finally:
            if temp_path.exists():
                temp_path.unlink()

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    def _transcribe(self, path: Path):
        with open(path, "rb") as audio_file:
            return self.client.audio.transcriptions.create(
                model=settings.whisper_model,
                file=audio_file,
                language=settings.whisper_language,
                response_format="verbose_json",
                timestamp_granularities=["segment"],
            )

    def _validate_file(self, path: Path) -> None:
        if not path.exists():
            raise FileNotFoundError(f"파일을 찾을 수 없습니다: {path}")
        if path.suffix.lower() not in self.SUPPORTED_FORMATS:
            raise ValueError(f"지원하지 않는 형식: {path.suffix}")
        if path.stat().st_size > self.MAX_FILE_SIZE_BYTES:
            raise ValueError(f"파일 크기 초과: 최대 {settings.max_audio_size_mb}MB")

    def _compute_hash(self, path: Path) -> str:
        sha256 = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                sha256.update(chunk)
        return sha256.hexdigest()

    def _estimate_duration(self, file_size_bytes: int) -> float:
        # MP3 128kbps 기준 추정 (실제값은 segments에서 가져옴)
        return file_size_bytes / (128 * 1024 / 8)

    def save_audio(self, audio_bytes: bytes, filename: str) -> Path:
        """업로드된 오디오 파일을 스토리지에 저장."""
        storage_path = Path(settings.audio_storage_path)
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        safe_name = f"{timestamp}_{Path(filename).stem[:50]}{Path(filename).suffix}"
        dest = storage_path / safe_name
        dest.write_bytes(audio_bytes)
        return dest
