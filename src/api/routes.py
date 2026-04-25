"""API 라우트 정의"""
from fastapi import APIRouter, UploadFile, File, HTTPException, BackgroundTasks
from typing import List
import uuid
import aiofiles
from pathlib import Path

from .models import (
    AudioUploadResponse,
    TranscriptionRequest,
    TranscriptionResponse,
    AnalysisRequest,
    AnalysisResponse,
    ProcessCallRequest,
    ProcessCallResponse,
    BatchProcessRequest,
    BatchProcessResponse,
    CustomerProfileResponse,
    ConsultationSummaryResponse,
    DashboardStats,
    TriggerWordResponse,
    RecommendedActionResponse,
    TriggerCategoryEnum
)
from ..stt import CallTranscriber
from ..analysis import TriggerWordAnalyzer, SentimentAnalyzer
from ..automation import ConsultationAutomation
from ..utils import FileStorageManager

router = APIRouter()

storage = FileStorageManager()
transcriber = None
trigger_analyzer = TriggerWordAnalyzer()
sentiment_analyzer = None
automation = ConsultationAutomation()


def get_transcriber():
    global transcriber
    if transcriber is None:
        transcriber = CallTranscriber()
    return transcriber


def get_sentiment_analyzer():
    global sentiment_analyzer
    if sentiment_analyzer is None:
        sentiment_analyzer = SentimentAnalyzer()
    return sentiment_analyzer


@router.post("/audio/upload", response_model=AudioUploadResponse)
async def upload_audio(file: UploadFile = File(...)):
    """음성 파일 업로드

    지원 형식: mp3, wav, m4a, ogg, flac
    """
    allowed_extensions = [".mp3", ".wav", ".m4a", ".ogg", ".flac"]
    ext = Path(file.filename).suffix.lower()

    if ext not in allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail=f"지원하지 않는 파일 형식입니다. 지원 형식: {allowed_extensions}"
        )

    file_id = str(uuid.uuid4())
    filename = f"{file_id}{ext}"
    file_path = storage.config.audio_incoming / filename

    async with aiofiles.open(file_path, "wb") as f:
        content = await file.read()
        await f.write(content)

    return AudioUploadResponse(
        file_id=file_id,
        filename=filename,
        status="uploaded",
        message="파일이 성공적으로 업로드되었습니다."
    )


@router.post("/transcribe", response_model=TranscriptionResponse)
async def transcribe_audio(request: TranscriptionRequest):
    """음성 파일을 텍스트로 변환"""
    files = list(storage.config.audio_incoming.glob(f"{request.file_id}.*"))
    if not files:
        raise HTTPException(status_code=404, detail="파일을 찾을 수 없습니다.")

    audio_path = files[0]
    processing_path = storage.move_to_processing(audio_path)

    try:
        result = get_transcriber().transcribe(
            str(processing_path),
            language=request.language
        )

        call_id = str(uuid.uuid4())

        transcript_data = {
            "call_id": call_id,
            "customer_id": request.customer_id,
            "full_text": result.full_text,
            "duration": result.duration,
            "language": result.language,
            "segments": [
                {
                    "start": seg.start,
                    "end": seg.end,
                    "text": seg.text,
                    "confidence": seg.confidence
                }
                for seg in result.segments
            ]
        }

        storage.save_transcript(request.customer_id, call_id, transcript_data)
        storage.archive_audio(processing_path)

        return TranscriptionResponse(**transcript_data)

    except Exception as e:
        storage.move_to_processing(processing_path)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/analyze", response_model=AnalysisResponse)
async def analyze_transcript(request: AnalysisRequest):
    """텍스트 분석 수행"""
    trigger_result = trigger_analyzer.analyze(request.transcript)
    sentiment_result = get_sentiment_analyzer().analyze_text(request.transcript)

    triggers = [
        TriggerWordResponse(
            word=t.word,
            category=TriggerCategoryEnum(t.category.value),
            weight=t.weight,
            context=t.context
        )
        for t in trigger_result.triggers[:20]
    ]

    analysis_data = {
        "call_id": request.call_id,
        "customer_id": request.customer_id,
        "triggers": [t.dict() for t in triggers],
        "category_scores": {k.value: v for k, v in trigger_result.category_scores.items()},
        "intent_score": trigger_result.intent_score,
        "urgency_score": trigger_result.urgency_score,
        "key_phrases": trigger_result.key_phrases,
        "sentiment": sentiment_result.sentiment.value,
        "sentiment_confidence": sentiment_result.confidence
    }

    storage.save_analysis(request.customer_id, request.call_id, analysis_data)

    return AnalysisResponse(**analysis_data)


@router.post("/process", response_model=ProcessCallResponse)
async def process_call(request: ProcessCallRequest):
    """통화 녹음 전체 처리 (변환 + 분석 + 프로필 업데이트)"""
    transcription_req = TranscriptionRequest(
        file_id=request.file_id,
        customer_id=request.customer_id,
        language=request.language
    )
    transcription = await transcribe_audio(transcription_req)

    analysis_req = AnalysisRequest(
        call_id=transcription.call_id,
        customer_id=request.customer_id,
        transcript=transcription.full_text
    )
    analysis = await analyze_transcript(analysis_req)

    class MockTriggerResult:
        def __init__(self, analysis):
            self.intent_score = analysis.intent_score
            self.urgency_score = analysis.urgency_score
            self.triggers = []
            self.key_phrases = analysis.key_phrases
            self.category_scores = {
                TriggerCategoryEnum(k): v
                for k, v in analysis.category_scores.items()
            }

    class MockSentimentResult:
        def __init__(self, analysis):
            from ..analysis import Sentiment
            self.overall_sentiment = Sentiment(analysis.sentiment)

    trigger_result = MockTriggerResult(analysis)
    sentiment_result = MockSentimentResult(analysis)

    profile = automation.update_customer_profile(
        request.customer_id,
        trigger_result,
        sentiment_result,
        transcription.full_text
    )

    if request.customer_name:
        profile.name = request.customer_name

    actions = automation.generate_recommended_actions(profile, trigger_result)

    summary = automation.generate_consultation_summary(
        transcription.call_id,
        request.customer_id,
        transcription.full_text,
        trigger_result,
        sentiment_result,
        transcription.duration
    )

    return ProcessCallResponse(
        call_id=transcription.call_id,
        transcription=transcription,
        analysis=analysis,
        customer_profile=CustomerProfileResponse(
            customer_id=profile.customer_id,
            name=profile.name,
            status=profile.status.value,
            budget_range=profile.budget_range,
            preferred_locations=profile.preferred_locations,
            requirements=profile.requirements,
            concerns=profile.concerns,
            intent_score=profile.intent_score,
            urgency_score=profile.urgency_score,
            last_contact=profile.last_contact,
            total_contacts=profile.total_contacts
        ),
        consultation_summary=ConsultationSummaryResponse(
            call_id=summary.call_id,
            customer_id=summary.customer_id,
            timestamp=summary.timestamp,
            duration=summary.duration,
            key_topics=summary.key_topics,
            customer_requests=summary.customer_requests,
            agent_promises=summary.agent_promises,
            next_steps=summary.next_steps,
            sentiment_summary=summary.sentiment_summary,
            intent_level=summary.intent_level,
            urgency_level=summary.urgency_level,
            recommended_actions=[
                RecommendedActionResponse(
                    action_type=a.action_type.value,
                    priority=a.priority,
                    reason=a.reason,
                    deadline=a.deadline
                )
                for a in actions
            ]
        )
    )


@router.get("/customers/{customer_id}", response_model=CustomerProfileResponse)
async def get_customer(customer_id: str):
    """고객 프로필 조회"""
    if customer_id not in automation.customers:
        raise HTTPException(status_code=404, detail="고객을 찾을 수 없습니다.")

    profile = automation.customers[customer_id]
    return CustomerProfileResponse(
        customer_id=profile.customer_id,
        name=profile.name,
        status=profile.status.value,
        budget_range=profile.budget_range,
        preferred_locations=profile.preferred_locations,
        requirements=profile.requirements,
        concerns=profile.concerns,
        intent_score=profile.intent_score,
        urgency_score=profile.urgency_score,
        last_contact=profile.last_contact,
        total_contacts=profile.total_contacts
    )


@router.get("/customers", response_model=List[CustomerProfileResponse])
async def list_customers():
    """모든 고객 목록 조회"""
    return [
        CustomerProfileResponse(
            customer_id=p.customer_id,
            name=p.name,
            status=p.status.value,
            budget_range=p.budget_range,
            preferred_locations=p.preferred_locations,
            requirements=p.requirements,
            concerns=p.concerns,
            intent_score=p.intent_score,
            urgency_score=p.urgency_score,
            last_contact=p.last_contact,
            total_contacts=p.total_contacts
        )
        for p in automation.customers.values()
    ]


@router.get("/dashboard/stats", response_model=DashboardStats)
async def get_dashboard_stats():
    """대시보드 통계 조회"""
    customers = list(automation.customers.values())
    total_customers = len(customers)

    if total_customers == 0:
        return DashboardStats(
            total_calls=0,
            total_customers=0,
            hot_leads=0,
            avg_intent_score=0.0,
            avg_urgency_score=0.0,
            top_trigger_words=[],
            sentiment_distribution={},
            calls_by_date={}
        )

    hot_leads = sum(1 for c in customers if c.status.value == "핫리드")
    total_calls = sum(c.total_contacts for c in customers)
    avg_intent = sum(c.intent_score for c in customers) / total_customers
    avg_urgency = sum(c.urgency_score for c in customers) / total_customers

    return DashboardStats(
        total_calls=total_calls,
        total_customers=total_customers,
        hot_leads=hot_leads,
        avg_intent_score=round(avg_intent, 2),
        avg_urgency_score=round(avg_urgency, 2),
        top_trigger_words=[],
        sentiment_distribution={},
        calls_by_date={}
    )


@router.get("/pending-files")
async def get_pending_files():
    """처리 대기 중인 파일 목록"""
    files = storage.get_pending_audio_files()
    return {
        "count": len(files),
        "files": [
            {
                "filename": f.name,
                "file_id": f.stem,
                "size": f.stat().st_size,
                "uploaded_at": f.stat().st_mtime
            }
            for f in files
        ]
    }
