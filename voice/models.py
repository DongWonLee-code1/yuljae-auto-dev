"""
데이터 모델 정의
Data Models
"""

from datetime import datetime
from typing import List

from pydantic import BaseModel


class Utterance(BaseModel):
    """단일 발화 (화자의 한 번 말하기)"""

    speaker: str  # "A", "B" 등
    speaker_label: str  # "화자 A", "화자 B"
    text: str  # 전사된 텍스트
    start_ms: int  # 시작 시간 (밀리초)
    end_ms: int  # 종료 시간 (밀리초)
    confidence: float  # 신뢰도 (0-1)

    @property
    def start_formatted(self) -> str:
        """MM:SS 형식"""
        minutes = self.start_ms // 60000
        seconds = (self.start_ms % 60000) // 1000
        return f"{minutes:02d}:{seconds:02d}"

    @property
    def duration_ms(self) -> int:
        """발화 길이 (밀리초)"""
        return self.end_ms - self.start_ms


class TranscriptionResult(BaseModel):
    """전사 결과 (화자 분리 포함)"""

    file_name: str
    audio_duration_ms: int
    processed_at: datetime
    utterances: List[Utterance]
    raw_text: str  # 화자 구분 없는 전체 텍스트
    speaker_count: int
    language_code: str

    def to_readable_text(self) -> str:
        """사람이 읽기 좋은 형식으로 변환"""
        lines = []
        for u in self.utterances:
            lines.append(f'{u.speaker_label}: "{u.text}"')
        return "\n".join(lines)

    def to_timestamped_text(self) -> str:
        """타임스탬프 포함 형식 (키워드 분석용)"""
        lines = []
        for u in self.utterances:
            lines.append(f'[{u.start_formatted}] {u.speaker_label}: "{u.text}"')
        return "\n".join(lines)

    @property
    def duration_formatted(self) -> str:
        """총 시간을 분:초 형식으로"""
        minutes = self.audio_duration_ms // 60000
        seconds = (self.audio_duration_ms % 60000) // 1000
        return f"{minutes}분 {seconds}초"
