"""
부동산 영업 데이터 자산화 시스템 테스트.
외부 API 호출은 mock으로 대체하여 단위 테스트 실행.
"""
import json
import pytest
from datetime import datetime
from unittest.mock import MagicMock, patch
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from storage.models import Base
from storage.database import Database
from analysis.trigger_words import TriggerWordExtractor, REAL_ESTATE_TRIGGER_CATEGORIES
from analysis.insights import InsightGenerator, CallInsight, ActionItem
from transcription.processor import TranscriptionResult


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def in_memory_db():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()
    Base.metadata.drop_all(engine)


SAMPLE_TRANSCRIPT = """
상담사: 안녕하세요, 율재부동산입니다. 무엇을 도와드릴까요?
고객: 안녕하세요. 강남구 쪽에 아파트 매매 알아보고 있는데요.
상담사: 네, 예산은 어느 정도 생각하고 계세요?
고객: 한 15억 정도요. 학군이 좋은 곳이면 좋겠고요. 대출도 알아봐야 할 것 같아요.
상담사: 강남에 지금 괜찮은 급매 물건이 나와 있어요. 언제 보러 오실 수 있으세요?
고객: 이번 주 토요일에 볼 수 있을 것 같아요. 계약금은 얼마 정도 생각해야 하나요?
상담사: 통상적으로 매매가의 10% 정도입니다. 토요일 오전 10시 어떠세요?
고객: 좋아요. 연락 주세요. 가족이랑 상의하고 최종 결정할게요.
"""

MOCK_TRIGGER_RESPONSE = json.dumps({
    "found_triggers": {
        "매수의향": ["매매 알아보고", "급매 물건", "언제 보러"],
        "학군교통": ["학군이 좋은"],
        "자금조달": ["대출도 알아봐야"],
        "계약임박": ["계약금"],
        "긍정신호": ["좋아요", "연락 주세요", "가족이랑 상의하고"],
    },
    "category_scores": {
        "매수의향": 85,
        "학군교통": 70,
        "자금조달": 60,
        "계약임박": 75,
        "긍정신호": 80,
    },
    "dominant_intent": "매수의향",
    "customer_sentiment": "긍정",
    "urgency_level": "단기1개월이내",
    "opportunity_score": 82,
    "raw_text_excerpt": [
        "강남구 쪽에 아파트 매매 알아보고 있는데요",
        "이번 주 토요일에 볼 수 있을 것 같아요",
    ],
}, ensure_ascii=False)

MOCK_INSIGHT_RESPONSE = json.dumps({
    "summary": "강남구 15억 예산 아파트 매매 희망 고객. 학군 중시, 이번 주 토요일 방문 약속.",
    "customer_profile": {
        "estimated_budget": "15억",
        "property_type": "아파트",
        "area_preference": "강남구",
        "move_in_timeline": "협의",
        "transaction_type": "매매",
        "decision_maker": False,
        "investment_purpose": False,
    },
    "property_interests": ["강남구 아파트", "학군 우수", "15억 이하"],
    "pain_points": ["대출 필요", "가족 동의 필요"],
    "recommended_properties": ["강남구 학군 우수 아파트", "급매 물건 우선 제안"],
    "action_items": [
        {"action": "토요일 오전 10시 방문 확정 문자 발송", "priority": "high", "deadline": "오늘", "channel": "문자"},
        {"action": "15억대 강남 급매 물건 3건 정리 발송", "priority": "high", "deadline": "내일", "channel": "카카오"},
        {"action": "대출 상담사 연결 안내", "priority": "medium", "deadline": "이번주", "channel": "전화"},
    ],
    "follow_up_script": "안녕하세요 고객님, 율재부동산입니다. 토요일 오전 10시 방문 예약 확인드립니다. 좋은 물건 준비해 놓겠습니다!",
    "risk_factors": ["가족 동의 필요", "대출 한도 확인 필요"],
    "estimated_deal_probability": 72,
    "estimated_deal_timeline": "1개월",
}, ensure_ascii=False)


# ── Database Tests ─────────────────────────────────────────────────────────────

class TestDatabase:
    def test_get_or_create_customer_creates_new(self, in_memory_db):
        customer = Database.get_or_create_customer(in_memory_db, "010-1234-5678")
        in_memory_db.commit()
        assert customer.id is not None
        assert customer.phone_number == "010-1234-5678"

    def test_get_or_create_customer_returns_existing(self, in_memory_db):
        c1 = Database.get_or_create_customer(in_memory_db, "010-1234-5678")
        in_memory_db.commit()
        c2 = Database.get_or_create_customer(in_memory_db, "010-1234-5678")
        in_memory_db.commit()
        assert c1.id == c2.id

    def test_create_call_record(self, in_memory_db):
        record = Database.create_call_record(
            in_memory_db,
            phone_number="010-9999-8888",
            audio_file_path="/tmp/test.mp3",
            audio_file_hash="abc123",
            agent_name="홍길동",
            duration_seconds=120.0,
        )
        in_memory_db.commit()
        assert record.id is not None
        assert record.status == "pending"
        assert record.customer_id is not None

    def test_save_transcript(self, in_memory_db):
        call = Database.create_call_record(
            in_memory_db, "010-1111-2222", "/tmp/a.mp3", "hash1", duration_seconds=60.0
        )
        in_memory_db.commit()
        transcript = Database.save_transcript(in_memory_db, call.id, SAMPLE_TRANSCRIPT)
        in_memory_db.commit()
        assert transcript.id is not None
        assert transcript.call_id == call.id
        assert len(transcript.text) > 0

    def test_save_trigger_analysis(self, in_memory_db):
        call = Database.create_call_record(
            in_memory_db, "010-3333-4444", "/tmp/b.mp3", "hash2", duration_seconds=90.0
        )
        in_memory_db.commit()
        transcript = Database.save_transcript(in_memory_db, call.id, SAMPLE_TRANSCRIPT)
        in_memory_db.commit()
        analysis = Database.save_trigger_analysis(
            in_memory_db,
            transcript_id=transcript.id,
            found_triggers={"매수의향": ["매매"]},
            category_scores={"매수의향": 80},
            dominant_intent="매수의향",
            customer_sentiment="긍정",
            urgency_level="단기1개월이내",
            opportunity_score=82,
            raw_text_excerpt=["매매 알아보고"],
        )
        in_memory_db.commit()
        assert analysis.opportunity_score == 82
        assert analysis.dominant_intent == "매수의향"

    def test_get_hot_leads(self, in_memory_db):
        call = Database.create_call_record(
            in_memory_db, "010-5555-6666", "/tmp/c.mp3", "hash3", duration_seconds=150.0
        )
        in_memory_db.commit()
        transcript = Database.save_transcript(in_memory_db, call.id, SAMPLE_TRANSCRIPT)
        in_memory_db.commit()
        Database.save_trigger_analysis(
            in_memory_db,
            transcript_id=transcript.id,
            found_triggers={},
            category_scores={},
            dominant_intent="매수의향",
            customer_sentiment="긍정",
            urgency_level="단기",
            opportunity_score=85,
            raw_text_excerpt=[],
        )
        in_memory_db.commit()
        hot_leads = Database.get_hot_leads(in_memory_db, min_score=60, limit=10)
        assert len(hot_leads) >= 1
        assert hot_leads[0]["opportunity_score"] == 85

    def test_follow_up_lifecycle(self, in_memory_db):
        customer = Database.get_or_create_customer(in_memory_db, "010-7777-8888")
        in_memory_db.commit()
        fu = Database.create_follow_up(
            in_memory_db,
            customer_id=customer.id,
            action="방문 일정 확인",
            channel="전화",
            priority="high",
        )
        in_memory_db.commit()
        assert fu.status == "pending"

        pending = Database.list_pending_follow_ups(in_memory_db)
        assert any(f.id == fu.id for f in pending)

        Database.complete_follow_up(in_memory_db, fu.id, notes="방문 확정")
        in_memory_db.commit()
        assert fu.status == "completed"
        assert fu.completed_at is not None

    def test_update_customer(self, in_memory_db):
        customer = Database.get_or_create_customer(in_memory_db, "010-0000-1111")
        in_memory_db.commit()
        Database.update_customer(
            in_memory_db, customer.id,
            name="김철수",
            estimated_budget="15억",
            is_vip=True,
        )
        in_memory_db.commit()
        assert customer.name == "김철수"
        assert customer.estimated_budget == "15억"
        assert customer.is_vip is True


# ── TriggerWordExtractor Tests ─────────────────────────────────────────────────

class TestTriggerWordExtractor:
    def test_trigger_categories_defined(self):
        assert "매수의향" in REAL_ESTATE_TRIGGER_CATEGORIES
        assert "매도의향" in REAL_ESTATE_TRIGGER_CATEGORIES
        assert "투자관심" in REAL_ESTATE_TRIGGER_CATEGORIES
        assert "계약임박" in REAL_ESTATE_TRIGGER_CATEGORIES
        assert "자금조달" in REAL_ESTATE_TRIGGER_CATEGORIES

    @patch("analysis.trigger_words.anthropic.Anthropic")
    def test_extract_returns_trigger_result(self, mock_anthropic):
        mock_client = MagicMock()
        mock_anthropic.return_value = mock_client
        mock_client.messages.create.return_value = MagicMock(
            content=[MagicMock(text=MOCK_TRIGGER_RESPONSE)]
        )

        extractor = TriggerWordExtractor()
        result = extractor.extract("transcript_1", SAMPLE_TRANSCRIPT)

        assert result.transcript_id == "transcript_1"
        assert result.opportunity_score == 82
        assert result.dominant_intent == "매수의향"
        assert result.customer_sentiment == "긍정"
        assert "매수의향" in result.found_triggers
        assert len(result.raw_text_excerpt) > 0

    @patch("analysis.trigger_words.anthropic.Anthropic")
    def test_extract_handles_malformed_json(self, mock_anthropic):
        mock_client = MagicMock()
        mock_anthropic.return_value = mock_client
        mock_client.messages.create.return_value = MagicMock(
            content=[MagicMock(text="분석 결과를 찾을 수 없습니다.")]
        )

        extractor = TriggerWordExtractor()
        result = extractor.extract("transcript_err", "짧은 통화")

        assert result.opportunity_score == 0
        assert result.dominant_intent == "분석실패"


# ── InsightGenerator Tests ─────────────────────────────────────────────────────

class TestInsightGenerator:
    @patch("analysis.insights.anthropic.Anthropic")
    def test_generate_returns_insight(self, mock_anthropic):
        mock_client = MagicMock()
        mock_anthropic.return_value = mock_client
        mock_client.messages.create.return_value = MagicMock(
            content=[MagicMock(text=MOCK_INSIGHT_RESPONSE)]
        )

        generator = InsightGenerator()
        insight = generator.generate(
            transcript_id="t1",
            transcript_text=SAMPLE_TRANSCRIPT,
            trigger_analysis={"dominant_intent": "매수의향", "opportunity_score": 82},
        )

        assert insight.transcript_id == "t1"
        assert insight.estimated_deal_probability == 72
        assert len(insight.action_items) == 3
        assert insight.action_items[0].priority == "high"
        assert "강남" in insight.summary

    @patch("analysis.insights.anthropic.Anthropic")
    def test_generate_handles_empty_response(self, mock_anthropic):
        mock_client = MagicMock()
        mock_anthropic.return_value = mock_client
        mock_client.messages.create.return_value = MagicMock(
            content=[MagicMock(text="{}")]
        )

        generator = InsightGenerator()
        insight = generator.generate("t2", "테스트")
        assert insight.estimated_deal_probability == 0
        assert insight.summary == "분석 결과 없음"


# ── TranscriptionResult Tests ──────────────────────────────────────────────────

class TestTranscriptionResult:
    def test_transcription_result_creation(self):
        result = TranscriptionResult(
            file_path="/tmp/test.mp3",
            text="안녕하세요 테스트입니다",
            language="ko",
            duration_seconds=5.0,
            file_hash="abc" * 20,
        )
        assert result.text == "안녕하세요 테스트입니다"
        assert result.language == "ko"
        assert isinstance(result.created_at, datetime)
        assert result.segments == []
        assert result.metadata == {}
