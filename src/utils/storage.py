"""파일 저장소 관리 모듈

데이터 저장 구조:
├── data/
│   ├── audio/               # 원본 음성 파일
│   │   ├── incoming/        # 신규 업로드 대기
│   │   ├── processing/      # 처리 중
│   │   └── archived/        # 처리 완료 아카이브
│   │       └── YYYY/MM/DD/  # 날짜별 정리
│   ├── transcripts/         # 변환된 텍스트
│   │   └── YYYY/MM/DD/
│   ├── analysis/            # 분석 결과
│   │   └── YYYY/MM/DD/
│   └── exports/             # 내보내기 파일
"""
from pathlib import Path
from datetime import datetime
from typing import Optional, List
import shutil
import json
import os


class StorageConfig:
    """저장소 설정"""

    def __init__(self, base_path: str = "./data"):
        self.base_path = Path(base_path)

        # 음성 파일 경로
        self.audio_incoming = self.base_path / "audio" / "incoming"
        self.audio_processing = self.base_path / "audio" / "processing"
        self.audio_archived = self.base_path / "audio" / "archived"

        # 텍스트 변환 결과 경로
        self.transcripts = self.base_path / "transcripts"

        # 분석 결과 경로
        self.analysis = self.base_path / "analysis"

        # 내보내기 경로
        self.exports = self.base_path / "exports"

        # 임시 파일 경로
        self.temp = self.base_path / "temp"

    def initialize(self):
        """모든 디렉토리 생성"""
        directories = [
            self.audio_incoming,
            self.audio_processing,
            self.audio_archived,
            self.transcripts,
            self.analysis,
            self.exports,
            self.temp
        ]
        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)


class FileStorageManager:
    """파일 저장소 관리자"""

    def __init__(self, config: Optional[StorageConfig] = None):
        self.config = config or StorageConfig()
        self.config.initialize()

    def _get_date_path(self, base_path: Path) -> Path:
        """날짜 기반 경로 생성"""
        now = datetime.now()
        date_path = base_path / str(now.year) / f"{now.month:02d}" / f"{now.day:02d}"
        date_path.mkdir(parents=True, exist_ok=True)
        return date_path

    def save_incoming_audio(self, file_path: str, customer_id: str) -> Path:
        """신규 음성 파일 저장

        Args:
            file_path: 원본 파일 경로
            customer_id: 고객 ID

        Returns:
            저장된 파일 경로
        """
        source = Path(file_path)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        new_filename = f"{customer_id}_{timestamp}{source.suffix}"
        destination = self.config.audio_incoming / new_filename

        shutil.copy2(source, destination)
        return destination

    def move_to_processing(self, file_path: Path) -> Path:
        """처리 중 상태로 이동"""
        destination = self.config.audio_processing / file_path.name
        shutil.move(str(file_path), str(destination))
        return destination

    def archive_audio(self, file_path: Path) -> Path:
        """처리 완료 후 아카이브"""
        date_path = self._get_date_path(self.config.audio_archived)
        destination = date_path / file_path.name
        shutil.move(str(file_path), str(destination))
        return destination

    def save_transcript(
        self,
        customer_id: str,
        call_id: str,
        transcript_data: dict
    ) -> Path:
        """텍스트 변환 결과 저장"""
        date_path = self._get_date_path(self.config.transcripts)
        filename = f"{customer_id}_{call_id}.json"
        file_path = date_path / filename

        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(transcript_data, f, ensure_ascii=False, indent=2)

        return file_path

    def save_analysis(
        self,
        customer_id: str,
        call_id: str,
        analysis_data: dict
    ) -> Path:
        """분석 결과 저장"""
        date_path = self._get_date_path(self.config.analysis)
        filename = f"{customer_id}_{call_id}_analysis.json"
        file_path = date_path / filename

        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(analysis_data, f, ensure_ascii=False, indent=2)

        return file_path

    def get_pending_audio_files(self) -> List[Path]:
        """처리 대기 중인 음성 파일 목록"""
        extensions = [".mp3", ".wav", ".m4a", ".ogg", ".flac"]
        files = []
        for ext in extensions:
            files.extend(self.config.audio_incoming.glob(f"*{ext}"))
        return sorted(files, key=lambda x: x.stat().st_mtime)

    def get_processing_audio_files(self) -> List[Path]:
        """처리 중인 음성 파일 목록"""
        extensions = [".mp3", ".wav", ".m4a", ".ogg", ".flac"]
        files = []
        for ext in extensions:
            files.extend(self.config.audio_processing.glob(f"*{ext}"))
        return list(files)

    def export_customer_data(
        self,
        customer_id: str,
        export_format: str = "json"
    ) -> Path:
        """고객 데이터 내보내기"""
        export_data = {
            "customer_id": customer_id,
            "exported_at": datetime.now().isoformat(),
            "transcripts": [],
            "analyses": []
        }

        for transcript_file in self.config.transcripts.rglob(f"{customer_id}_*.json"):
            with open(transcript_file, "r", encoding="utf-8") as f:
                export_data["transcripts"].append(json.load(f))

        for analysis_file in self.config.analysis.rglob(f"{customer_id}_*_analysis.json"):
            with open(analysis_file, "r", encoding="utf-8") as f:
                export_data["analyses"].append(json.load(f))

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"export_{customer_id}_{timestamp}.json"
        export_path = self.config.exports / filename

        with open(export_path, "w", encoding="utf-8") as f:
            json.dump(export_data, f, ensure_ascii=False, indent=2)

        return export_path

    def cleanup_temp(self, max_age_hours: int = 24):
        """임시 파일 정리"""
        now = datetime.now()
        for file_path in self.config.temp.iterdir():
            if file_path.is_file():
                age = now.timestamp() - file_path.stat().st_mtime
                if age > max_age_hours * 3600:
                    file_path.unlink()
