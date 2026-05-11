"""
데이터베이스 연결 및 CRUD 작업 관리.
"""
from contextlib import contextmanager
from datetime import datetime, timedelta
from typing import Generator, Optional

from sqlalchemy import create_engine, desc
from sqlalchemy.orm import Session, sessionmaker

from config import settings
from .models import (
    Base, CallRecord, Customer, FollowUp, InsightRecord,
    Transcript, TriggerWordAnalysis,
)


engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False} if "sqlite" in settings.database_url else {},
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db() -> None:
    Base.metadata.create_all(bind=engine)


@contextmanager
def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


class Database:
    # ── Session Helper ────────────────────────────────────────
    @staticmethod
    def get_session() -> Session:
        """새 DB 세션 반환. 사용 후 close() 필요."""
        init_db()
        return SessionLocal()

    # ── Customer ──────────────────────────────────────────────
    @staticmethod
    def get_or_create_customer(db: Session, phone_number: str) -> Customer:
        customer = db.query(Customer).filter(Customer.phone_number == phone_number).first()
        if not customer:
            customer = Customer(phone_number=phone_number)
            db.add(customer)
            db.flush()
        return customer

    @staticmethod
    def update_customer(db: Session, customer_id: int, **kwargs) -> Optional[Customer]:
        customer = db.query(Customer).filter(Customer.id == customer_id).first()
        if customer:
            for key, value in kwargs.items():
                if hasattr(customer, key):
                    setattr(customer, key, value)
        return customer

    @staticmethod
    def list_customers(
        db: Session, skip: int = 0, limit: int = 50, is_vip: Optional[bool] = None
    ) -> list[Customer]:
        q = db.query(Customer)
        if is_vip is not None:
            q = q.filter(Customer.is_vip == is_vip)
        return q.order_by(desc(Customer.updated_at)).offset(skip).limit(limit).all()

    # ── CallRecord ────────────────────────────────────────────
    @staticmethod
    def create_call_record(
        db: Session,
        phone_number: str,
        audio_file_path: str,
        audio_file_hash: str,
        agent_name: str = "",
        call_date: Optional[datetime] = None,
        duration_seconds: float = 0.0,
    ) -> CallRecord:
        customer = Database.get_or_create_customer(db, phone_number)
        record = CallRecord(
            customer_id=customer.id,
            phone_number=phone_number,
            agent_name=agent_name,
            call_date=call_date or datetime.utcnow(),
            audio_file_path=audio_file_path,
            audio_file_hash=audio_file_hash,
            duration_seconds=duration_seconds,
            status="pending",
        )
        db.add(record)
        db.flush()
        return record

    @staticmethod
    def get_call_record(db: Session, call_id: int) -> Optional[CallRecord]:
        return db.query(CallRecord).filter(CallRecord.id == call_id).first()

    @staticmethod
    def update_call_status(db: Session, call_id: int, status: str) -> None:
        record = db.query(CallRecord).filter(CallRecord.id == call_id).first()
        if record:
            record.status = status

    @staticmethod
    def list_call_records(
        db: Session, skip: int = 0, limit: int = 50, status: Optional[str] = None
    ) -> list[CallRecord]:
        q = db.query(CallRecord)
        if status:
            q = q.filter(CallRecord.status == status)
        return q.order_by(desc(CallRecord.call_date)).offset(skip).limit(limit).all()

    # ── Transcript ────────────────────────────────────────────
    @staticmethod
    def save_transcript(
        db: Session,
        call_id: int,
        text: str,
        language: str = "ko",
        segments: Optional[list] = None,
    ) -> Transcript:
        transcript = Transcript(
            call_id=call_id,
            text=text,
            language=language,
            word_count=len(text.split()),
            segments=segments or [],
        )
        db.add(transcript)
        db.flush()
        return transcript

    @staticmethod
    def get_transcript(db: Session, transcript_id: int) -> Optional[Transcript]:
        return db.query(Transcript).filter(Transcript.id == transcript_id).first()

    # ── TriggerWordAnalysis ───────────────────────────────────
    @staticmethod
    def save_trigger_analysis(
        db: Session,
        transcript_id: int,
        found_triggers: dict,
        category_scores: dict,
        dominant_intent: str,
        customer_sentiment: str,
        urgency_level: str,
        opportunity_score: int,
        raw_text_excerpt: list,
    ) -> TriggerWordAnalysis:
        analysis = TriggerWordAnalysis(
            transcript_id=transcript_id,
            found_triggers=found_triggers,
            category_scores=category_scores,
            dominant_intent=dominant_intent,
            customer_sentiment=customer_sentiment,
            urgency_level=urgency_level,
            opportunity_score=opportunity_score,
            raw_text_excerpt=raw_text_excerpt,
        )
        db.add(analysis)
        db.flush()
        return analysis

    # ── InsightRecord ─────────────────────────────────────────
    @staticmethod
    def save_insight(
        db: Session,
        transcript_id: int,
        summary: str,
        customer_profile: dict,
        property_interests: list,
        pain_points: list,
        recommended_properties: list,
        action_items: list,
        follow_up_script: str,
        risk_factors: list,
        estimated_deal_probability: int,
        estimated_deal_timeline: str,
    ) -> InsightRecord:
        insight = InsightRecord(
            transcript_id=transcript_id,
            summary=summary,
            customer_profile=customer_profile,
            property_interests=property_interests,
            pain_points=pain_points,
            recommended_properties=recommended_properties,
            action_items=action_items,
            follow_up_script=follow_up_script,
            risk_factors=risk_factors,
            estimated_deal_probability=estimated_deal_probability,
            estimated_deal_timeline=estimated_deal_timeline,
        )
        db.add(insight)
        db.flush()
        return insight

    @staticmethod
    def get_insight_by_transcript(db: Session, transcript_id: int) -> Optional[InsightRecord]:
        return db.query(InsightRecord).filter(InsightRecord.transcript_id == transcript_id).first()

    # ── FollowUp ──────────────────────────────────────────────
    @staticmethod
    def create_follow_up(
        db: Session,
        customer_id: int,
        action: str,
        channel: str,
        priority: str = "medium",
        due_date: Optional[datetime] = None,
        script: str = "",
        call_record_id: Optional[int] = None,
    ) -> FollowUp:
        follow_up = FollowUp(
            customer_id=customer_id,
            call_record_id=call_record_id,
            action=action,
            channel=channel,
            priority=priority,
            due_date=due_date or datetime.utcnow() + timedelta(days=1),
            script=script,
        )
        db.add(follow_up)
        db.flush()
        return follow_up

    @staticmethod
    def list_pending_follow_ups(
        db: Session, skip: int = 0, limit: int = 50
    ) -> list[FollowUp]:
        return (
            db.query(FollowUp)
            .filter(FollowUp.status == "pending")
            .order_by(FollowUp.priority.desc(), FollowUp.due_date)
            .offset(skip)
            .limit(limit)
            .all()
        )

    @staticmethod
    def complete_follow_up(db: Session, follow_up_id: int, notes: str = "") -> None:
        fu = db.query(FollowUp).filter(FollowUp.id == follow_up_id).first()
        if fu:
            fu.status = "completed"
            fu.completed_at = datetime.utcnow()
            fu.notes = notes

    # ── Analytics ─────────────────────────────────────────────
    @staticmethod
    def get_hot_leads(db: Session, min_score: int = 60, limit: int = 20) -> list[dict]:
        results = (
            db.query(CallRecord, TriggerWordAnalysis, Customer)
            .join(Transcript, CallRecord.id == Transcript.call_id)
            .join(TriggerWordAnalysis, Transcript.id == TriggerWordAnalysis.transcript_id)
            .join(Customer, CallRecord.customer_id == Customer.id)
            .filter(TriggerWordAnalysis.opportunity_score >= min_score)
            .order_by(desc(TriggerWordAnalysis.opportunity_score))
            .limit(limit)
            .all()
        )
        return [
            {
                "call_id": call.id,
                "phone_number": call.phone_number,
                "customer_name": customer.name,
                "opportunity_score": analysis.opportunity_score,
                "dominant_intent": analysis.dominant_intent,
                "urgency_level": analysis.urgency_level,
                "call_date": call.call_date.isoformat(),
            }
            for call, analysis, customer in results
        ]

    @staticmethod
    def get_trigger_word_stats(db: Session, days: int = 30) -> dict:
        since = datetime.utcnow() - timedelta(days=days)
        analyses = (
            db.query(TriggerWordAnalysis)
            .join(Transcript)
            .join(CallRecord)
            .filter(CallRecord.call_date >= since)
            .all()
        )
        all_triggers: dict[str, int] = {}
        for a in analyses:
            for category, words in (a.found_triggers or {}).items():
                for word in words:
                    all_triggers[word] = all_triggers.get(word, 0) + 1
        return dict(sorted(all_triggers.items(), key=lambda x: x[1], reverse=True)[:50])
