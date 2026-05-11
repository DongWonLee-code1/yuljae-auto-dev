"""
AssemblyAI 클라이언트
AssemblyAI Client for Transcription with Speaker Diarization
"""

from datetime import datetime
from pathlib import Path

import assemblyai as aai

from config.settings import Settings
from .models import TranscriptionResult, Utterance


class AssemblyAIClient:
    """AssemblyAI SDK 래퍼 (화자 분리 지원)"""

    def __init__(self, settings: Settings):
        self.settings = settings
        aai.settings.api_key = settings.assemblyai_api_key

        self.config = aai.TranscriptionConfig(
            speaker_labels=True,  # 화자 분리 활성화
            speakers_expected=settings.speaker_count,
            language_code=settings.language_code,
            punctuate=settings.punctuate,
            format_text=settings.format_text,
        )

        self.transcriber = aai.Transcriber(config=self.config)

    def transcribe_file(self, file_path: str) -> TranscriptionResult:
        """
        오디오 파일을 화자 분리와 함께 전사

        Args:
            file_path: 오디오 파일 경로 (.m4a, .mp3, .wav 등)

        Returns:
            TranscriptionResult: 전사 결과
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"파일을 찾을 수 없습니다: {file_path}")

        file_size_mb = path.stat().st_size / (1024 * 1024)
        if file_size_mb > self.settings.max_file_size_mb:
            raise ValueError(
                f"파일이 너무 큽니다: {file_size_mb:.1f}MB "
                f"(최대: {self.settings.max_file_size_mb}MB)"
            )

        transcript = self.transcriber.transcribe(str(path))

        if transcript.status == aai.TranscriptStatus.error:
            raise RuntimeError(f"전사 실패: {transcript.error}")

        return self._convert_to_result(transcript, path.name)

    def transcribe_url(
        self, audio_url: str, file_name: str = "remote_audio"
    ) -> TranscriptionResult:
        """URL에서 오디오 전사 (클라우드 스토리지용)"""
        transcript = self.transcriber.transcribe(audio_url)

        if transcript.status == aai.TranscriptStatus.error:
            raise RuntimeError(f"전사 실패: {transcript.error}")

        return self._convert_to_result(transcript, file_name)

    def _convert_to_result(
        self, transcript: aai.Transcript, file_name: str
    ) -> TranscriptionResult:
        """AssemblyAI 응답을 내부 데이터 모델로 변환"""
        utterances = []

        for utt in transcript.utterances or []:
            speaker_key = utt.speaker  # "A", "B" 등
            speaker_label = f"화자 {speaker_key}"

            utterances.append(
                Utterance(
                    speaker=speaker_key,
                    speaker_label=speaker_label,
                    text=utt.text,
                    start_ms=utt.start,
                    end_ms=utt.end,
                    confidence=utt.confidence,
                )
            )

        audio_duration_ms = 0
        if transcript.audio_duration:
            audio_duration_ms = int(transcript.audio_duration * 1000)

        return TranscriptionResult(
            file_name=file_name,
            audio_duration_ms=audio_duration_ms,
            processed_at=datetime.now(),
            utterances=utterances,
            raw_text=transcript.text or "",
            speaker_count=len(set(u.speaker for u in utterances)),
            language_code=self.settings.language_code,
        )
