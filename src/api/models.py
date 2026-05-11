"""API 데이터 모델"""
from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Any
from datetime import datetime
from enum import Enum


class CustomerStatusEnum(str, Enum):
    NEW = "신규"
    INTERESTED = "관심"
    HOT_LEAD = "핫리드"
    NEGOTIATING = "협상중"
    CONTRACTED = "계약완료"
    LOST = "이탈"


class TriggerCategoryEnum(str, Enum):
    PURCHASE_INTENT = "구매의향"
    URGENCY = "긴급성"
    BUDGET = "예산"
    LOCATION = "위치선호"
    CONCERN = "우려사항"
    COMPETITOR = "경쟁사언급"
    TIMELINE = "시기"
    NEGOTIATION = "협상"


class AudioUploadResponse(BaseModel):
    """음성 파일 업로드 응답"""
    file_id: str
    filename: str
    status: str
    message: str


class TranscriptionRequest(BaseModel):
    """텍스트 변환 요청"""
    file_id: str
    customer_id: str
    language: str = "ko"


class TranscriptionResponse(BaseModel):
    """텍스트 변환 응답"""
    call_id: str
    customer_id: str
    full_text: str
    duration: float
    segments: List[Dict[str, Any]]
    language: str


class TriggerWordResponse(BaseModel):
    """트리거 워드 응답"""
    word: str
    category: TriggerCategoryEnum
    weight: float
    context: str


class AnalysisRequest(BaseModel):
    """분석 요청"""
    call_id: str
    customer_id: str
    transcript: str


class AnalysisResponse(BaseModel):
    """분석 응답"""
    call_id: str
    customer_id: str
    triggers: List[TriggerWordResponse]
    category_scores: Dict[str, float]
    intent_score: float
    urgency_score: float
    key_phrases: List[str]
    sentiment: str
    sentiment_confidence: float


class CustomerProfileResponse(BaseModel):
    """고객 프로필 응답"""
    customer_id: str
    name: Optional[str]
    status: CustomerStatusEnum
    budget_range: Optional[str]
    preferred_locations: List[str]
    requirements: List[str]
    concerns: List[str]
    intent_score: float
    urgency_score: float
    last_contact: Optional[datetime]
    total_contacts: int


class RecommendedActionResponse(BaseModel):
    """추천 액션 응답"""
    action_type: str
    priority: int
    reason: str
    deadline: Optional[datetime]


class ConsultationSummaryResponse(BaseModel):
    """상담 요약 응답"""
    call_id: str
    customer_id: str
    timestamp: datetime
    duration: float
    key_topics: List[str]
    customer_requests: List[str]
    agent_promises: List[str]
    next_steps: List[str]
    sentiment_summary: str
    intent_level: str
    urgency_level: str
    recommended_actions: List[RecommendedActionResponse]


class ProcessCallRequest(BaseModel):
    """통화 처리 전체 요청"""
    file_id: str
    customer_id: str
    customer_name: Optional[str] = None
    language: str = "ko"


class ProcessCallResponse(BaseModel):
    """통화 처리 전체 응답"""
    call_id: str
    transcription: TranscriptionResponse
    analysis: AnalysisResponse
    customer_profile: CustomerProfileResponse
    consultation_summary: ConsultationSummaryResponse


class BatchProcessRequest(BaseModel):
    """일괄 처리 요청"""
    file_ids: List[str]
    customer_mappings: Dict[str, str]
    language: str = "ko"


class BatchProcessResponse(BaseModel):
    """일괄 처리 응답"""
    total: int
    processed: int
    failed: int
    results: List[ProcessCallResponse]
    errors: List[Dict[str, str]]


class DashboardStats(BaseModel):
    """대시보드 통계"""
    total_calls: int
    total_customers: int
    hot_leads: int
    avg_intent_score: float
    avg_urgency_score: float
    top_trigger_words: List[Dict[str, Any]]
    sentiment_distribution: Dict[str, int]
    calls_by_date: Dict[str, int]
