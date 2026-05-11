"""상담 자동화 테스트"""
import pytest
from dataclasses import dataclass
from datetime import datetime
from src.automation.consultation import (
    ConsultationAutomation,
    CustomerProfile,
    CustomerStatus,
    ActionType
)
from src.analysis.trigger_words import TriggerCategory


@dataclass
class MockTriggerResult:
    intent_score: float = 0.5
    urgency_score: float = 0.5
    triggers: list = None
    key_phrases: list = None
    category_scores: dict = None

    def __post_init__(self):
        if self.triggers is None:
            self.triggers = []
        if self.key_phrases is None:
            self.key_phrases = []
        if self.category_scores is None:
            self.category_scores = {cat: 0.0 for cat in TriggerCategory}


@dataclass
class MockSentimentResult:
    overall_sentiment: str = "중립"


@pytest.fixture
def automation():
    return ConsultationAutomation()


class TestConsultationAutomation:
    """상담 자동화 테스트"""

    def test_update_customer_profile_new(self, automation):
        """신규 고객 프로필 생성"""
        trigger_result = MockTriggerResult(intent_score=0.3, urgency_score=0.2)
        sentiment_result = MockSentimentResult()

        profile = automation.update_customer_profile(
            "CUST001",
            trigger_result,
            sentiment_result,
            "테스트 상담 내용"
        )

        assert profile.customer_id == "CUST001"
        assert profile.status == CustomerStatus.NEW
        assert profile.total_contacts == 1

    def test_hot_lead_detection(self, automation):
        """핫리드 감지"""
        trigger_result = MockTriggerResult(intent_score=0.9, urgency_score=0.8)
        sentiment_result = MockSentimentResult()

        profile = automation.update_customer_profile(
            "CUST002",
            trigger_result,
            sentiment_result,
            "계약 급해요"
        )

        assert profile.status == CustomerStatus.HOT_LEAD

    def test_interested_customer(self, automation):
        """관심 고객 분류"""
        trigger_result = MockTriggerResult(intent_score=0.65, urgency_score=0.3)
        sentiment_result = MockSentimentResult()

        profile = automation.update_customer_profile(
            "CUST003",
            trigger_result,
            sentiment_result,
            "관심 있어요"
        )

        assert profile.status == CustomerStatus.INTERESTED

    def test_generate_actions_hot_lead(self, automation):
        """핫리드 추천 액션"""
        profile = CustomerProfile(
            customer_id="CUST004",
            intent_score=0.85,
            urgency_score=0.75
        )
        trigger_result = MockTriggerResult(
            intent_score=0.85,
            urgency_score=0.75,
            category_scores={cat: 0.0 for cat in TriggerCategory}
        )

        actions = automation.generate_recommended_actions(profile, trigger_result)

        action_types = [a.action_type for a in actions]
        assert ActionType.URGENT_RESPONSE in action_types

    def test_generate_consultation_summary(self, automation):
        """상담 요약 생성"""
        trigger_result = MockTriggerResult(
            intent_score=0.7,
            urgency_score=0.6,
            key_phrases=["아파트", "전세", "강남"]
        )

        class MockSentiment:
            class overall_sentiment:
                value = "긍정"

        summary = automation.generate_consultation_summary(
            "CALL001",
            "CUST005",
            "테스트 상담 내용입니다. 보내드리겠습니다.",
            trigger_result,
            MockSentiment(),
            120.0
        )

        assert summary.call_id == "CALL001"
        assert summary.customer_id == "CUST005"
        assert summary.duration == 120.0
        assert len(summary.key_topics) > 0

    def test_contact_count_increment(self, automation):
        """연락 횟수 증가"""
        trigger_result = MockTriggerResult()
        sentiment_result = MockSentimentResult()

        automation.update_customer_profile(
            "CUST006", trigger_result, sentiment_result, "첫 번째"
        )
        profile = automation.update_customer_profile(
            "CUST006", trigger_result, sentiment_result, "두 번째"
        )

        assert profile.total_contacts == 2
