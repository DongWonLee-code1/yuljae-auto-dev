"""
율재부동산 영업 데이터 자산화 시스템 FastAPI 애플리케이션.
"""
from fastapi import FastAPI, File, Form, HTTPException, UploadFile, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from config import settings
from storage import Database, init_db, get_db
from storage.models import CallRecord, Transcript, Customer, FollowUp
from transcription import TranscriptionProcessor
from analysis import TriggerWordExtractor, InsightGenerator
from automation.pipeline import ProcessingPipeline
from .schemas import (
    CallRecordResponse, CustomerResponse, FollowUpCreate, FollowUpResponse,
    HotLeadResponse, InsightResponse, ProcessCallResponse, TriggerAnalysisResponse,
    TriggerStatsResponse, TranscriptResponse, WeeklyReportResponse,
)


def create_app() -> FastAPI:
    app = FastAPI(
        title="율재부동산 영업 데이터 자산화 시스템",
        description="통화 녹음 분석, 트리거 워드 추출, 영업 인사이트 자동 생성",
        version="1.0.0",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    init_db()

    pipeline = ProcessingPipeline()

    def _get_db_session():
        with get_db() as db:
            yield db

    # ── 통화 처리 ─────────────────────────────────────────────

    @app.post("/calls/upload", response_model=ProcessCallResponse, tags=["통화 처리"])
    async def upload_and_process_call(
        audio_file: UploadFile = File(..., description="통화 녹음 파일 (mp3, wav, m4a, webm)"),
        phone_number: str = Form(..., description="고객 전화번호"),
        agent_name: str = Form(default="", description="담당 직원 이름"),
        db: Session = Depends(_get_db_session),
    ):
        """통화 녹음을 업로드하고 전체 분석 파이프라인을 실행합니다."""
        audio_bytes = await audio_file.read()
        if len(audio_bytes) > settings.max_audio_size_mb * 1024 * 1024:
            raise HTTPException(413, f"파일 크기 초과: 최대 {settings.max_audio_size_mb}MB")

        result = pipeline.process_upload(
            db=db,
            audio_bytes=audio_bytes,
            filename=audio_file.filename or "recording.mp3",
            phone_number=phone_number,
            agent_name=agent_name,
        )
        return ProcessCallResponse(
            call_id=result["call_id"],
            message="분석이 완료되었습니다.",
            status="completed",
        )

    @app.get("/calls", response_model=list[CallRecordResponse], tags=["통화 처리"])
    def list_calls(
        skip: int = 0,
        limit: int = 50,
        status: str | None = None,
        db: Session = Depends(_get_db_session),
    ):
        """통화 기록 목록 조회."""
        return Database.list_call_records(db, skip=skip, limit=limit, status=status)

    @app.get("/calls/{call_id}", response_model=CallRecordResponse, tags=["통화 처리"])
    def get_call(call_id: int, db: Session = Depends(_get_db_session)):
        """특정 통화 기록 조회."""
        record = Database.get_call_record(db, call_id)
        if not record:
            raise HTTPException(404, "통화 기록을 찾을 수 없습니다.")
        return record

    @app.get("/calls/{call_id}/transcript", response_model=TranscriptResponse, tags=["통화 처리"])
    def get_transcript(call_id: int, db: Session = Depends(_get_db_session)):
        """통화 트랜스크립트 조회."""
        call = db.query(CallRecord).filter(CallRecord.id == call_id).first()
        if not call or not call.transcript:
            raise HTTPException(404, "트랜스크립트를 찾을 수 없습니다.")
        return call.transcript

    @app.get("/calls/{call_id}/triggers", response_model=TriggerAnalysisResponse, tags=["통화 처리"])
    def get_trigger_analysis(call_id: int, db: Session = Depends(_get_db_session)):
        """트리거 워드 분석 결과 조회."""
        call = db.query(CallRecord).filter(CallRecord.id == call_id).first()
        if not call or not call.transcript or not call.transcript.trigger_analysis:
            raise HTTPException(404, "트리거 분석 결과를 찾을 수 없습니다.")
        return call.transcript.trigger_analysis

    @app.get("/calls/{call_id}/insight", response_model=InsightResponse, tags=["통화 처리"])
    def get_insight(call_id: int, db: Session = Depends(_get_db_session)):
        """영업 인사이트 조회."""
        call = db.query(CallRecord).filter(CallRecord.id == call_id).first()
        if not call or not call.transcript or not call.transcript.insight:
            raise HTTPException(404, "인사이트를 찾을 수 없습니다.")
        return call.transcript.insight

    # ── 고객 관리 ─────────────────────────────────────────────

    @app.get("/customers", response_model=list[CustomerResponse], tags=["고객 관리"])
    def list_customers(
        skip: int = 0,
        limit: int = 50,
        is_vip: bool | None = None,
        db: Session = Depends(_get_db_session),
    ):
        return Database.list_customers(db, skip=skip, limit=limit, is_vip=is_vip)

    @app.patch("/customers/{customer_id}/vip", tags=["고객 관리"])
    def toggle_vip(customer_id: int, is_vip: bool, db: Session = Depends(_get_db_session)):
        """고객 VIP 상태 변경."""
        customer = Database.update_customer(db, customer_id, is_vip=is_vip)
        if not customer:
            raise HTTPException(404, "고객을 찾을 수 없습니다.")
        return {"message": f"VIP 상태 {'설정' if is_vip else '해제'} 완료"}

    # ── 팔로업 관리 ───────────────────────────────────────────

    @app.post("/follow-ups", response_model=FollowUpResponse, tags=["팔로업 관리"])
    def create_follow_up(payload: FollowUpCreate, db: Session = Depends(_get_db_session)):
        """팔로업 항목 생성."""
        fu = Database.create_follow_up(
            db,
            customer_id=payload.customer_id,
            action=payload.action,
            channel=payload.channel,
            priority=payload.priority,
            due_date=payload.due_date,
            script=payload.script or "",
            call_record_id=payload.call_record_id,
        )
        return fu

    @app.get("/follow-ups/pending", response_model=list[FollowUpResponse], tags=["팔로업 관리"])
    def list_pending_follow_ups(
        skip: int = 0,
        limit: int = 50,
        db: Session = Depends(_get_db_session),
    ):
        return Database.list_pending_follow_ups(db, skip=skip, limit=limit)

    @app.patch("/follow-ups/{follow_up_id}/complete", tags=["팔로업 관리"])
    def complete_follow_up(
        follow_up_id: int,
        notes: str = "",
        db: Session = Depends(_get_db_session),
    ):
        Database.complete_follow_up(db, follow_up_id, notes=notes)
        return {"message": "팔로업 완료 처리되었습니다."}

    # ── 영업 분석 ─────────────────────────────────────────────

    @app.get("/analytics/hot-leads", response_model=list[HotLeadResponse], tags=["영업 분석"])
    def get_hot_leads(
        min_score: int = settings.min_opportunity_score,
        limit: int = 20,
        db: Session = Depends(_get_db_session),
    ):
        """영업 기회 점수 기준 핫 리드 목록 조회."""
        return Database.get_hot_leads(db, min_score=min_score, limit=limit)

    @app.get("/analytics/trigger-stats", response_model=TriggerStatsResponse, tags=["영업 분석"])
    def get_trigger_stats(days: int = 30, db: Session = Depends(_get_db_session)):
        """기간별 트리거 워드 빈도 통계."""
        stats = Database.get_trigger_word_stats(db, days=days)
        return TriggerStatsResponse(period_days=days, trigger_counts=stats)

    @app.get("/analytics/weekly-report", response_model=WeeklyReportResponse, tags=["영업 분석"])
    def get_weekly_report(db: Session = Depends(_get_db_session)):
        """주간 영업 인사이트 리포트 생성."""
        hot_leads = Database.get_hot_leads(db, min_score=0, limit=100)
        insight_gen = InsightGenerator()
        report = insight_gen.generate_weekly_report(hot_leads)
        return WeeklyReportResponse(report=report)

    @app.get("/health", tags=["시스템"])
    def health_check():
        return {"status": "ok", "service": settings.company_name}

    return app
