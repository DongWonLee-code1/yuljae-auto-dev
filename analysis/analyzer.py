"""
부동산 상담 분석 엔진 (Claude API 기반)
Real Estate Consultation Analyzer using Claude API

화자 분리된 텍스트에서 구조화된 데이터 추출
"""

import json
import os
import uuid
from datetime import datetime
from pathlib import Path

from anthropic import Anthropic

from analysis.models import (
    AnalysisResult,
    CustomerInfo,
    LocationInfo,
    NegotiationInfo,
    PriceInfo,
    TimelineInfo,
)
from voice.models import TranscriptionResult

EXTRACTION_PROMPT = """당신은 부동산 상담 통화 내용을 분석하는 전문가입니다.
아래 화자 분리된 통화 녹취록에서 핵심 정보를 추출하여 JSON 형식으로 반환하세요.

중요: 원문에 명시되지 않은 정보는 null로 남기세요. 추측하지 마세요.
각 카테고리별 trigger_quotes 필드에는 해당 정보가 언급된 원문 발화를 1-3개 포함하세요.

반드시 아래 JSON 스키마를 정확히 따르세요:

```json
{
  "price": {
    "sale_price": "매매가 (예: '20억', '5억 5천') 또는 null",
    "jeonse_price": "전세가 또는 null",
    "deposit": "보증금 또는 null",
    "monthly_rent": "월세 또는 null",
    "price_range_min": "희망 가격 최소 또는 null",
    "price_range_max": "희망 가격 최대 또는 null",
    "negotiable": true/false 또는 null,
    "negotiation_details": "가격 협상 세부사항 또는 null",
    "trigger_quotes": ["관련 원문 발화 1", "관련 원문 발화 2"]
  },
  "location": {
    "district": "구/군 (예: '서초구') 또는 null",
    "neighborhood": "동 (예: '반포동') 또는 null",
    "complex_name": "아파트 단지명 또는 null",
    "nearby_stations": ["역 이름"],
    "is_station_area": true/false 또는 null,
    "preferred_areas": ["선호 지역"],
    "excluded_areas": ["제외 희망 지역"],
    "trigger_quotes": ["관련 원문 발화"]
  },
  "timeline": {
    "contract_date_preference": "희망 계약 시점 또는 null",
    "move_in_date": "입주 희망일 또는 null",
    "urgency_level": "urgent/normal/flexible 또는 null",
    "current_contract_end": "현재 계약 만료일 또는 null",
    "viewing_availability": "매물 보기 가능 시간 또는 null",
    "trigger_quotes": ["관련 원문 발화"]
  },
  "negotiation": {
    "must_have_conditions": ["필수 조건"],
    "nice_to_have_conditions": ["희망 조건"],
    "deal_breakers": ["거래 불가 조건"],
    "special_requests": ["특별 요청"],
    "concerns": ["고객 우려사항"],
    "trigger_quotes": ["관련 원문 발화"]
  },
  "customer": {
    "age_group": "연령대 추정 (예: '30대') 또는 null",
    "family_composition": "가족 구성 (예: '신혼부부', '자녀 2명') 또는 null",
    "current_residence": "현재 거주지 또는 null",
    "occupation_hint": "직업 힌트 또는 null",
    "budget_capacity": "예산 여력 추정 또는 null",
    "decision_maker": "의사결정자 또는 null",
    "trigger_quotes": ["관련 원문 발화"]
  },
  "summary": "상담 내용 1-2문장 요약",
  "follow_up_needed": true/false,
  "follow_up_actions": ["필요한 후속 조치"]
}
```

---
통화 녹취록:
{transcript}
---

JSON만 반환하세요. 다른 설명은 포함하지 마세요."""


class ConsultationAnalyzer:
    """부동산 상담 분석기"""

    def __init__(self, api_key: str | None = None):
        """
        Args:
            api_key: Anthropic API 키 (없으면 ANTHROPIC_API_KEY 환경변수 사용)
        """
        self.client = Anthropic(api_key=api_key or os.getenv("ANTHROPIC_API_KEY"))
        self.model = "claude-sonnet-4-20250514"

    def analyze(self, transcription: TranscriptionResult) -> AnalysisResult:
        """
        전사 결과를 분석하여 구조화된 데이터 추출

        Args:
            transcription: 화자 분리된 전사 결과

        Returns:
            AnalysisResult: 추출된 구조화 데이터
        """
        transcript_text = transcription.to_readable_text()
        prompt = EXTRACTION_PROMPT.format(transcript=transcript_text)

        response = self.client.messages.create(
            model=self.model,
            max_tokens=4096,
            messages=[{"role": "user", "content": prompt}],
        )

        response_text = response.content[0].text.strip()
        if response_text.startswith("```"):
            lines = response_text.split("\n")
            lines = lines[1:-1] if lines[-1] == "```" else lines[1:]
            response_text = "\n".join(lines)

        data = json.loads(response_text)

        consultation_id = f"CONSULT-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"

        return AnalysisResult(
            consultation_id=consultation_id,
            source_file=transcription.file_name,
            duration_seconds=transcription.audio_duration_ms // 1000,
            speaker_count=transcription.speaker_count,
            price=PriceInfo(**data.get("price", {})),
            location=LocationInfo(**data.get("location", {})),
            timeline=TimelineInfo(**data.get("timeline", {})),
            negotiation=NegotiationInfo(**data.get("negotiation", {})),
            customer=CustomerInfo(**data.get("customer", {})),
            summary=data.get("summary", ""),
            follow_up_needed=data.get("follow_up_needed", False),
            follow_up_actions=data.get("follow_up_actions", []),
        )

    def analyze_text(self, transcript_text: str, file_name: str = "unknown", duration_ms: int = 0, speaker_count: int = 2) -> AnalysisResult:
        """
        텍스트 직접 분석 (TranscriptionResult 없이)

        Args:
            transcript_text: 화자 분리된 전사 텍스트
            file_name: 원본 파일명
            duration_ms: 통화 시간 (밀리초)
            speaker_count: 화자 수

        Returns:
            AnalysisResult: 추출된 구조화 데이터
        """
        prompt = EXTRACTION_PROMPT.format(transcript=transcript_text)

        response = self.client.messages.create(
            model=self.model,
            max_tokens=4096,
            messages=[{"role": "user", "content": prompt}],
        )

        response_text = response.content[0].text.strip()
        if response_text.startswith("```"):
            lines = response_text.split("\n")
            lines = lines[1:-1] if lines[-1] == "```" else lines[1:]
            response_text = "\n".join(lines)

        data = json.loads(response_text)

        consultation_id = f"CONSULT-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"

        return AnalysisResult(
            consultation_id=consultation_id,
            source_file=file_name,
            duration_seconds=duration_ms // 1000,
            speaker_count=speaker_count,
            price=PriceInfo(**data.get("price", {})),
            location=LocationInfo(**data.get("location", {})),
            timeline=TimelineInfo(**data.get("timeline", {})),
            negotiation=NegotiationInfo(**data.get("negotiation", {})),
            customer=CustomerInfo(**data.get("customer", {})),
            summary=data.get("summary", ""),
            follow_up_needed=data.get("follow_up_needed", False),
            follow_up_actions=data.get("follow_up_actions", []),
        )

    def save_result(
        self,
        result: AnalysisResult,
        output_dir: str = "outputs",
        formats: list[str] | None = None,
    ) -> list[str]:
        """
        분석 결과 저장

        Args:
            result: 분석 결과
            output_dir: 출력 디렉토리
            formats: 출력 형식 목록 ("json", "csv")

        Returns:
            생성된 파일 경로 목록
        """
        if formats is None:
            formats = ["json", "csv"]

        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        base_name = Path(result.source_file).stem
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        saved_files = []

        if "json" in formats:
            json_path = output_path / f"{base_name}_analysis_{timestamp}.json"
            with open(json_path, "w", encoding="utf-8") as f:
                json.dump(result.model_dump(), f, ensure_ascii=False, indent=2, default=str)
            saved_files.append(str(json_path))

        if "csv" in formats:
            import csv

            csv_path = output_path / f"{base_name}_analysis_{timestamp}.csv"
            with open(csv_path, "w", encoding="utf-8-sig", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(result.csv_headers())
                writer.writerow(result.to_csv_row())
            saved_files.append(str(csv_path))

        return saved_files
