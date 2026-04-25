"""통화 녹음 음성-텍스트 변환 모듈"""
import whisper
from pydub import AudioSegment
from pathlib import Path
from dataclasses import dataclass
from typing import List, Optional
import tempfile
import os


@dataclass
class TranscriptSegment:
    """텍스트 변환 세그먼트"""
    start: float
    end: float
    text: str
    confidence: float


@dataclass
class TranscriptionResult:
    """전체 텍스트 변환 결과"""
    full_text: str
    segments: List[TranscriptSegment]
    language: str
    duration: float
    audio_path: str


class CallTranscriber:
    """통화 녹음 텍스트 변환기"""

    def __init__(self, model_name: str = "large-v3"):
        self.model = whisper.load_model(model_name)
        self.supported_formats = [".mp3", ".wav", ".m4a", ".ogg", ".flac"]

    def _convert_to_wav(self, audio_path: str) -> str:
        """오디오 파일을 WAV 형식으로 변환"""
        audio = AudioSegment.from_file(audio_path)
        audio = audio.set_frame_rate(16000).set_channels(1)

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            audio.export(tmp.name, format="wav")
            return tmp.name

    def transcribe(
        self,
        audio_path: str,
        language: str = "ko"
    ) -> TranscriptionResult:
        """통화 녹음 파일을 텍스트로 변환

        Args:
            audio_path: 오디오 파일 경로
            language: 언어 코드 (기본값: 한국어)

        Returns:
            TranscriptionResult: 변환 결과
        """
        path = Path(audio_path)
        if path.suffix.lower() not in self.supported_formats:
            raise ValueError(f"지원하지 않는 형식: {path.suffix}")

        wav_path = self._convert_to_wav(audio_path)

        try:
            result = self.model.transcribe(
                wav_path,
                language=language,
                task="transcribe",
                verbose=False
            )

            segments = [
                TranscriptSegment(
                    start=seg["start"],
                    end=seg["end"],
                    text=seg["text"].strip(),
                    confidence=seg.get("no_speech_prob", 0.0)
                )
                for seg in result["segments"]
            ]

            audio = AudioSegment.from_wav(wav_path)
            duration = len(audio) / 1000.0

            return TranscriptionResult(
                full_text=result["text"].strip(),
                segments=segments,
                language=result["language"],
                duration=duration,
                audio_path=audio_path
            )
        finally:
            if os.path.exists(wav_path):
                os.remove(wav_path)

    def transcribe_batch(
        self,
        audio_paths: List[str],
        language: str = "ko"
    ) -> List[TranscriptionResult]:
        """여러 오디오 파일 일괄 변환"""
        return [self.transcribe(path, language) for path in audio_paths]
