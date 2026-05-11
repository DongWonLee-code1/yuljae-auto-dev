"""
출력 포맷터
Output Formatters
"""

import json
from datetime import datetime
from pathlib import Path
from typing import List

from .models import TranscriptionResult


class OutputFormatter:
    """출력 파일 생성 담당"""

    def __init__(self, output_dir: str = "outputs"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def save(
        self,
        result: TranscriptionResult,
        output_format: str = "both",
        with_timestamps: bool = False,
    ) -> List[str]:
        """
        전사 결과를 파일로 저장

        Args:
            result: 전사 결과
            output_format: "json", "text", "both"
            with_timestamps: 텍스트에 타임스탬프 포함 여부

        Returns:
            생성된 파일 경로 목록
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        base_name = Path(result.file_name).stem
        output_paths = []

        if output_format in ["json", "both"]:
            json_path = self.output_dir / f"{base_name}_{timestamp}.json"
            self._save_json(result, json_path)
            output_paths.append(str(json_path))

        if output_format in ["text", "both"]:
            txt_path = self.output_dir / f"{base_name}_{timestamp}.txt"
            self._save_text(result, txt_path, with_timestamps)
            output_paths.append(str(txt_path))

        return output_paths

    def _save_json(self, result: TranscriptionResult, path: Path):
        """JSON 형식으로 저장 (프로그래밍 처리용)"""
        with open(path, "w", encoding="utf-8") as f:
            json.dump(
                result.model_dump(), f, ensure_ascii=False, indent=2, default=str
            )

    def _save_text(
        self, result: TranscriptionResult, path: Path, with_timestamps: bool
    ):
        """텍스트 형식으로 저장 (사람이 읽기 좋은 형식)"""
        with open(path, "w", encoding="utf-8") as f:
            f.write(f"# 파일: {result.file_name}\n")
            f.write(f"# 처리 시각: {result.processed_at}\n")
            f.write(f"# 총 시간: {result.duration_formatted}\n")
            f.write(f"# 화자 수: {result.speaker_count}\n")
            f.write("=" * 50 + "\n\n")

            if with_timestamps:
                f.write(result.to_timestamped_text())
            else:
                f.write(result.to_readable_text())
