"""
분석 결과 데이터 모델
Analysis Result Data Models

데이터베이스/엑셀 호환 형식을 위한 구조화된 모델
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class PriceInfo(BaseModel):
    """가격 관련 정보 (PRICE)"""

    sale_price: Optional[str] = Field(None, description="매매가 (예: '20억', '5억 5천')")
    jeonse_price: Optional[str] = Field(None, description="전세가")
    deposit: Optional[str] = Field(None, description="보증금")
    monthly_rent: Optional[str] = Field(None, description="월세")
    price_range_min: Optional[str] = Field(None, description="희망 가격 최소")
    price_range_max: Optional[str] = Field(None, description="희망 가격 최대")
    negotiable: Optional[bool] = Field(None, description="가격 조정 가능 여부")
    negotiation_details: Optional[str] = Field(None, description="가격 협상 세부사항")
    trigger_quotes: list[str] = Field(default_factory=list, description="가격 관련 원문 발화")


class LocationInfo(BaseModel):
    """위치 관련 정보 (LOCATION)"""

    district: Optional[str] = Field(None, description="구/군 (예: '서초구', '강남구')")
    neighborhood: Optional[str] = Field(None, description="동 (예: '반포동', '압구정동')")
    complex_name: Optional[str] = Field(None, description="아파트 단지명")
    nearby_stations: list[str] = Field(default_factory=list, description="인근 역")
    is_station_area: Optional[bool] = Field(None, description="역세권 여부")
    preferred_areas: list[str] = Field(default_factory=list, description="선호 지역 목록")
    excluded_areas: list[str] = Field(default_factory=list, description="제외 희망 지역")
    trigger_quotes: list[str] = Field(default_factory=list, description="위치 관련 원문 발화")


class TimelineInfo(BaseModel):
    """시간/일정 관련 정보 (TIMELINE)"""

    contract_date_preference: Optional[str] = Field(None, description="희망 계약 시점")
    move_in_date: Optional[str] = Field(None, description="입주 희망일")
    urgency_level: Optional[str] = Field(None, description="급한 정도 ('urgent'/'normal'/'flexible')")
    current_contract_end: Optional[str] = Field(None, description="현재 계약 만료일")
    viewing_availability: Optional[str] = Field(None, description="매물 보기 가능 시간")
    trigger_quotes: list[str] = Field(default_factory=list, description="시간 관련 원문 발화")


class NegotiationInfo(BaseModel):
    """협상/요구 조건 (NEGOTIATION)"""

    must_have_conditions: list[str] = Field(default_factory=list, description="필수 조건")
    nice_to_have_conditions: list[str] = Field(default_factory=list, description="희망 조건")
    deal_breakers: list[str] = Field(default_factory=list, description="거래 불가 조건")
    special_requests: list[str] = Field(default_factory=list, description="특별 요청사항")
    concerns: list[str] = Field(default_factory=list, description="고객 우려사항")
    trigger_quotes: list[str] = Field(default_factory=list, description="협상 관련 원문 발화")


class CustomerInfo(BaseModel):
    """고객 정보 (CUSTOMER INFO) - 추정 가능한 경우"""

    age_group: Optional[str] = Field(None, description="연령대 추정 ('20대'/'30대'/'40대'/...)")
    family_composition: Optional[str] = Field(None, description="가족 구성 (예: '신혼부부', '자녀 2명')")
    current_residence: Optional[str] = Field(None, description="현재 거주지")
    occupation_hint: Optional[str] = Field(None, description="직업 힌트")
    budget_capacity: Optional[str] = Field(None, description="예산 여력 추정")
    decision_maker: Optional[str] = Field(None, description="의사결정자 (본인/배우자/부모님 등)")
    trigger_quotes: list[str] = Field(default_factory=list, description="고객 정보 관련 원문 발화")


class AnalysisResult(BaseModel):
    """전체 분석 결과 (데이터베이스/엑셀 호환)"""

    consultation_id: str = Field(description="상담 고유 ID")
    analyzed_at: datetime = Field(default_factory=datetime.now)
    source_file: str = Field(description="원본 파일명")
    duration_seconds: int = Field(description="통화 시간 (초)")
    speaker_count: int = Field(description="화자 수")

    price: PriceInfo = Field(default_factory=PriceInfo)
    location: LocationInfo = Field(default_factory=LocationInfo)
    timeline: TimelineInfo = Field(default_factory=TimelineInfo)
    negotiation: NegotiationInfo = Field(default_factory=NegotiationInfo)
    customer: CustomerInfo = Field(default_factory=CustomerInfo)

    summary: str = Field(default="", description="상담 요약 (1-2문장)")
    follow_up_needed: bool = Field(default=False, description="후속 조치 필요 여부")
    follow_up_actions: list[str] = Field(default_factory=list, description="필요한 후속 조치 목록")

    def to_flat_dict(self) -> dict:
        """
        데이터베이스/엑셀 삽입용 평탄화된 딕셔너리
        중첩 구조를 단일 레벨로 변환
        """
        flat = {
            "consultation_id": self.consultation_id,
            "analyzed_at": self.analyzed_at.isoformat(),
            "source_file": self.source_file,
            "duration_seconds": self.duration_seconds,
            "speaker_count": self.speaker_count,
            "summary": self.summary,
            "follow_up_needed": self.follow_up_needed,
            "follow_up_actions": "; ".join(self.follow_up_actions),
        }

        for field_name, prefix in [
            ("price", "price"),
            ("location", "loc"),
            ("timeline", "time"),
            ("negotiation", "nego"),
            ("customer", "cust"),
        ]:
            field_obj = getattr(self, field_name)
            for key, value in field_obj.model_dump().items():
                if key == "trigger_quotes":
                    flat[f"{prefix}_quotes"] = "; ".join(value) if value else ""
                elif isinstance(value, list):
                    flat[f"{prefix}_{key}"] = "; ".join(value) if value else ""
                elif isinstance(value, bool):
                    flat[f"{prefix}_{key}"] = "Y" if value else "N"
                else:
                    flat[f"{prefix}_{key}"] = value or ""

        return flat

    def to_csv_row(self) -> list:
        """CSV 행으로 변환"""
        flat = self.to_flat_dict()
        return list(flat.values())

    @staticmethod
    def csv_headers() -> list[str]:
        """CSV 헤더 목록"""
        sample = AnalysisResult(
            consultation_id="",
            source_file="",
            duration_seconds=0,
            speaker_count=0,
        )
        return list(sample.to_flat_dict().keys())
