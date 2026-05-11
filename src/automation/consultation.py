"""상담 업무 자동화 모듈"""
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any
from enum import Enum
from datetime import datetime
import json


class CustomerStatus(str, Enum):
    """고객 상태"""
    NEW = "신규"
    INTERESTED = "관심"
    HOT_LEAD = "핫리드"
    NEGOTIATING = "협상중"
    CONTRACTED = "계약완료"
    LOST = "이탈"


class ActionType(str, Enum):
    """액션 유형"""
    FOLLOW_UP_CALL = "후속전화"
    SEND_INFO = "자료발송"
    SCHEDULE_VISIT = "방문예약"
    SEND_QUOTE = "견적발송"
    CONTRACT_PREP = "계약준비"
    URGENT_RESPONSE = "긴급응대"


@dataclass
class CustomerProfile:
    """고객 프로필"""
    customer_id: str
    name: Optional[str] = None
    phone: Optional[str] = None
    status: CustomerStatus = CustomerStatus.NEW
    budget_range: Optional[str] = None
    preferred_locations: List[str] = field(default_factory=list)
    requirements: List[str] = field(default_factory=list)
    concerns: List[str] = field(default_factory=list)
    intent_score: float = 0.0
    urgency_score: float = 0.0
    last_contact: Optional[datetime] = None
    total_contacts: int = 0
    notes: List[str] = field(default_factory=list)


@dataclass
class RecommendedAction:
    """추천 액션"""
    action_type: ActionType
    priority: int
    reason: str
    deadline: Optional[datetime] = None
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ConsultationSummary:
    """상담 요약"""
    call_id: str
    customer_id: str
    timestamp: datetime
    duration: float
    transcript: str
    key_topics: List[str]
    customer_requests: List[str]
    agent_promises: List[str]
    next_steps: List[str]
    sentiment_summary: str
    intent_level: str
    urgency_level: str


class ConsultationAutomation:
    """상담 업무 자동화"""

    ACTION_RULES = {
        "high_intent_high_urgency": [
            (ActionType.URGENT_RESPONSE, 1, "높은 구매의향과 긴급성 감지"),
            (ActionType.SCHEDULE_VISIT, 2, "즉시 방문 예약 권장"),
        ],
        "high_intent_low_urgency": [
            (ActionType.SEND_INFO, 1, "관심 고객 - 상세 정보 발송"),
            (ActionType.FOLLOW_UP_CALL, 2, "3일 내 후속 연락"),
        ],
        "negotiation_stage": [
            (ActionType.SEND_QUOTE, 1, "협상 단계 - 견적서 발송"),
            (ActionType.CONTRACT_PREP, 2, "계약 준비 착수"),
        ],
        "concerns_detected": [
            (ActionType.SEND_INFO, 1, "우려사항 해소 자료 발송"),
            (ActionType.FOLLOW_UP_CALL, 2, "우려사항 상담 후속 전화"),
        ],
        "competitor_mentioned": [
            (ActionType.URGENT_RESPONSE, 1, "경쟁사 언급 - 즉시 대응"),
            (ActionType.SEND_QUOTE, 2, "경쟁력 있는 견적 제안"),
        ],
    }

    def __init__(self):
        self.customers: Dict[str, CustomerProfile] = {}

    def update_customer_profile(
        self,
        customer_id: str,
        trigger_result: Any,
        sentiment_result: Any,
        transcript: str
    ) -> CustomerProfile:
        """고객 프로필 업데이트"""
        if customer_id not in self.customers:
            self.customers[customer_id] = CustomerProfile(customer_id=customer_id)

        profile = self.customers[customer_id]
        profile.intent_score = trigger_result.intent_score
        profile.urgency_score = trigger_result.urgency_score
        profile.last_contact = datetime.now()
        profile.total_contacts += 1

        for trigger in trigger_result.triggers:
            if trigger.category.value == "위치선호":
                if trigger.word not in profile.preferred_locations:
                    profile.preferred_locations.append(trigger.word)
            elif trigger.category.value == "우려사항":
                if trigger.context not in profile.concerns:
                    profile.concerns.append(trigger.context)
            elif trigger.category.value == "예산":
                profile.budget_range = trigger.context

        profile.status = self._determine_status(profile)

        return profile

    def _determine_status(self, profile: CustomerProfile) -> CustomerStatus:
        """고객 상태 결정"""
        if profile.intent_score >= 0.8 and profile.urgency_score >= 0.7:
            return CustomerStatus.HOT_LEAD
        elif profile.intent_score >= 0.6:
            return CustomerStatus.INTERESTED
        elif profile.intent_score >= 0.3:
            return CustomerStatus.NEW
        else:
            return CustomerStatus.NEW

    def generate_recommended_actions(
        self,
        profile: CustomerProfile,
        trigger_result: Any
    ) -> List[RecommendedAction]:
        """추천 액션 생성"""
        actions = []

        if profile.intent_score >= 0.7 and profile.urgency_score >= 0.7:
            for action_type, priority, reason in self.ACTION_RULES["high_intent_high_urgency"]:
                actions.append(RecommendedAction(
                    action_type=action_type,
                    priority=priority,
                    reason=reason
                ))
        elif profile.intent_score >= 0.5:
            for action_type, priority, reason in self.ACTION_RULES["high_intent_low_urgency"]:
                actions.append(RecommendedAction(
                    action_type=action_type,
                    priority=priority,
                    reason=reason
                ))

        category_scores = trigger_result.category_scores
        from .trigger_words import TriggerCategory

        if category_scores.get(TriggerCategory.NEGOTIATION, 0) > 0.5:
            for action_type, priority, reason in self.ACTION_RULES["negotiation_stage"]:
                actions.append(RecommendedAction(
                    action_type=action_type,
                    priority=priority + 10,
                    reason=reason
                ))

        if category_scores.get(TriggerCategory.CONCERN, 0) > 0.4:
            for action_type, priority, reason in self.ACTION_RULES["concerns_detected"]:
                actions.append(RecommendedAction(
                    action_type=action_type,
                    priority=priority + 20,
                    reason=reason
                ))

        if category_scores.get(TriggerCategory.COMPETITOR, 0) > 0.3:
            for action_type, priority, reason in self.ACTION_RULES["competitor_mentioned"]:
                actions.append(RecommendedAction(
                    action_type=action_type,
                    priority=priority,
                    reason=reason
                ))

        actions.sort(key=lambda x: x.priority)
        return actions

    def generate_consultation_summary(
        self,
        call_id: str,
        customer_id: str,
        transcript: str,
        trigger_result: Any,
        sentiment_result: Any,
        duration: float
    ) -> ConsultationSummary:
        """상담 요약 생성"""
        key_topics = trigger_result.key_phrases[:5]

        customer_requests = [
            t.context for t in trigger_result.triggers
            if t.category.value in ["구매의향", "위치선호", "예산"]
        ][:5]

        agent_promises = self._extract_promises(transcript)

        intent_level = (
            "높음" if trigger_result.intent_score >= 0.7
            else "중간" if trigger_result.intent_score >= 0.4
            else "낮음"
        )

        urgency_level = (
            "긴급" if trigger_result.urgency_score >= 0.7
            else "보통" if trigger_result.urgency_score >= 0.4
            else "여유"
        )

        return ConsultationSummary(
            call_id=call_id,
            customer_id=customer_id,
            timestamp=datetime.now(),
            duration=duration,
            transcript=transcript,
            key_topics=key_topics,
            customer_requests=customer_requests,
            agent_promises=agent_promises,
            next_steps=[],
            sentiment_summary=sentiment_result.overall_sentiment.value,
            intent_level=intent_level,
            urgency_level=urgency_level
        )

    def _extract_promises(self, transcript: str) -> List[str]:
        """에이전트 약속 추출"""
        promise_patterns = [
            "보내드리겠습니다",
            "연락드리겠습니다",
            "확인해보겠습니다",
            "안내해드리겠습니다",
            "준비하겠습니다"
        ]

        promises = []
        sentences = transcript.split(".")

        for sentence in sentences:
            for pattern in promise_patterns:
                if pattern in sentence:
                    promises.append(sentence.strip())
                    break

        return promises[:5]
