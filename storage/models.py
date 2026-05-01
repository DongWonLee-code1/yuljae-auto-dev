"""
부동산 영업 데이터 SQLAlchemy ORM 모델.
통화 기록, 트랜스크립트, 분석 결과, 고객 정보, 팔로업 관리.
"""
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Boolean, Column, DateTime, Float, ForeignKey, Integer,
    JSON, String, Text, func,
)
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


class Customer(Base):
    __tablename__ = "customers"

    id = Column(Integer, primary_key=True, index=True)
    phone_number = Column(String(20), unique=True, index=True, nullable=False)
    name = Column(String(100))
    email = Column(String(200))
    estimated_budget = Column(String(100))
    preferred_area = Column(String(200))
    transaction_type = Column(String(50))  # 매매/전세/월세
    is_vip = Column(Boolean, default=False)
    tags = Column(JSON, default=list)
    notes = Column(Text)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    calls = relationship("CallRecord", back_populates="customer")
    follow_ups = relationship("FollowUp", back_populates="customer")


class CallRecord(Base):
    __tablename__ = "call_records"

    id = Column(Integer, primary_key=True, index=True)
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=True)
    phone_number = Column(String(20), index=True)
    agent_name = Column(String(100))
    call_date = Column(DateTime, index=True, default=func.now())
    duration_seconds = Column(Float)
    audio_file_path = Column(String(500))
    audio_file_hash = Column(String(64), unique=True, index=True)
    status = Column(String(50), default="pending")  # pending/processing/completed/failed
    created_at = Column(DateTime, default=func.now())

    customer = relationship("Customer", back_populates="calls")
    transcript = relationship("Transcript", back_populates="call", uselist=False)


class Transcript(Base):
    __tablename__ = "transcripts"

    id = Column(Integer, primary_key=True, index=True)
    call_id = Column(Integer, ForeignKey("call_records.id"), nullable=False, unique=True)
    text = Column(Text, nullable=False)
    language = Column(String(10), default="ko")
    word_count = Column(Integer)
    segments = Column(JSON, default=list)
    created_at = Column(DateTime, default=func.now())

    call = relationship("CallRecord", back_populates="transcript")
    trigger_analysis = relationship("TriggerWordAnalysis", back_populates="transcript", uselist=False)
    insight = relationship("InsightRecord", back_populates="transcript", uselist=False)


class TriggerWordAnalysis(Base):
    __tablename__ = "trigger_word_analyses"

    id = Column(Integer, primary_key=True, index=True)
    transcript_id = Column(Integer, ForeignKey("transcripts.id"), nullable=False, unique=True)
    found_triggers = Column(JSON, default=dict)
    category_scores = Column(JSON, default=dict)
    dominant_intent = Column(String(100))
    customer_sentiment = Column(String(50))
    urgency_level = Column(String(50))
    opportunity_score = Column(Integer, default=0)
    raw_text_excerpt = Column(JSON, default=list)
    created_at = Column(DateTime, default=func.now())

    transcript = relationship("Transcript", back_populates="trigger_analysis")


class InsightRecord(Base):
    __tablename__ = "insight_records"

    id = Column(Integer, primary_key=True, index=True)
    transcript_id = Column(Integer, ForeignKey("transcripts.id"), nullable=False, unique=True)
    summary = Column(Text)
    customer_profile = Column(JSON, default=dict)
    property_interests = Column(JSON, default=list)
    pain_points = Column(JSON, default=list)
    recommended_properties = Column(JSON, default=list)
    action_items = Column(JSON, default=list)
    follow_up_script = Column(Text)
    risk_factors = Column(JSON, default=list)
    estimated_deal_probability = Column(Integer, default=0)
    estimated_deal_timeline = Column(String(50))
    created_at = Column(DateTime, default=func.now())

    transcript = relationship("Transcript", back_populates="insight")


class FollowUp(Base):
    __tablename__ = "follow_ups"

    id = Column(Integer, primary_key=True, index=True)
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=False)
    call_record_id = Column(Integer, ForeignKey("call_records.id"), nullable=True)
    action = Column(String(500), nullable=False)
    channel = Column(String(50))  # 전화/문자/카카오/방문/이메일
    priority = Column(String(20), default="medium")  # high/medium/low
    due_date = Column(DateTime)
    script = Column(Text)
    status = Column(String(50), default="pending")  # pending/completed/cancelled
    completed_at = Column(DateTime)
    notes = Column(Text)
    created_at = Column(DateTime, default=func.now())

    customer = relationship("Customer", back_populates="follow_ups")
