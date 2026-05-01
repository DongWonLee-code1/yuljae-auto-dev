from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class CustomerBase(BaseModel):
    phone_number: str
    name: Optional[str] = None
    email: Optional[str] = None
    notes: Optional[str] = None


class CustomerResponse(CustomerBase):
    id: int
    is_vip: bool
    estimated_budget: Optional[str]
    preferred_area: Optional[str]
    transaction_type: Optional[str]
    tags: list[str]
    created_at: datetime

    class Config:
        from_attributes = True


class CallRecordResponse(BaseModel):
    id: int
    phone_number: str
    agent_name: str
    call_date: datetime
    duration_seconds: float
    status: str
    created_at: datetime

    class Config:
        from_attributes = True


class TranscriptResponse(BaseModel):
    id: int
    call_id: int
    text: str
    language: str
    word_count: Optional[int]
    created_at: datetime

    class Config:
        from_attributes = True


class TriggerAnalysisResponse(BaseModel):
    id: int
    transcript_id: int
    found_triggers: dict
    category_scores: dict
    dominant_intent: str
    customer_sentiment: str
    urgency_level: str
    opportunity_score: int
    raw_text_excerpt: list[str]
    created_at: datetime

    class Config:
        from_attributes = True


class InsightResponse(BaseModel):
    id: int
    transcript_id: int
    summary: str
    customer_profile: dict
    property_interests: list[str]
    pain_points: list[str]
    recommended_properties: list[str]
    action_items: list[dict]
    follow_up_script: str
    risk_factors: list[str]
    estimated_deal_probability: int
    estimated_deal_timeline: str
    created_at: datetime

    class Config:
        from_attributes = True


class FollowUpCreate(BaseModel):
    customer_id: int
    action: str
    channel: str = Field(..., pattern="^(전화|문자|카카오|방문|이메일)$")
    priority: str = Field(default="medium", pattern="^(high|medium|low)$")
    due_date: Optional[datetime] = None
    script: Optional[str] = ""
    call_record_id: Optional[int] = None


class FollowUpResponse(BaseModel):
    id: int
    customer_id: int
    action: str
    channel: str
    priority: str
    due_date: Optional[datetime]
    script: Optional[str]
    status: str
    completed_at: Optional[datetime]
    notes: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class ProcessCallResponse(BaseModel):
    call_id: int
    message: str
    status: str


class HotLeadResponse(BaseModel):
    call_id: int
    phone_number: str
    customer_name: Optional[str]
    opportunity_score: int
    dominant_intent: str
    urgency_level: str
    call_date: str


class TriggerStatsResponse(BaseModel):
    period_days: int
    trigger_counts: dict[str, int]


class WeeklyReportResponse(BaseModel):
    report: dict
