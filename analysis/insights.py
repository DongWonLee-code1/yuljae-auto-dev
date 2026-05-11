"""
부동산 영업 상담 인사이트를 Claude API로 생성하는 모듈.
트리거 워드 분석 결과를 바탕으로 구체적인 영업 액션 플랜을 도출.
"""
import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional

import anthropic

from config import settings


INSIGHT_SYSTEM_PROMPT = """당신은 15년 경력의 부동산 영업 전문 컨설턴트 AI입니다.
통화 분석 데이터를 바탕으로 영업 담당자가 즉시 실행할 수 있는 구체적인 액션 플랜을 제공합니다.
응답은 반드시 JSON 형식으로만 작성하세요."""


@dataclass
class ActionItem:
    action: str
    priority: str  # high / medium / low
    deadline: str
    channel: str  # 전화 / 문자 / 카카오 / 방문 / 이메일


@dataclass
class CallInsight:
    transcript_id: str
    summary: str
    customer_profile: dict
    property_interests: list[str]
    pain_points: list[str]
    recommended_properties: list[str]
    action_items: list[ActionItem]
    follow_up_script: str
    risk_factors: list[str]
    estimated_deal_probability: int
    estimated_deal_timeline: str
    analyzed_at: datetime = field(default_factory=datetime.utcnow)


class InsightGenerator:
    def __init__(self):
        self.client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

    def generate(
        self,
        transcript_id: str,
        transcript_text: str,
        trigger_analysis: Optional[dict] = None,
        customer_history: Optional[list[dict]] = None,
    ) -> CallInsight:
        response = self._call_claude(transcript_text, trigger_analysis, customer_history)
        parsed = self._parse_response(response)
        return CallInsight(transcript_id=transcript_id, **parsed)

    def generate_weekly_report(self, calls_data: list[dict]) -> dict:
        """주간 영업 인사이트 리포트 생성."""
        summary_json = json.dumps(calls_data, ensure_ascii=False)
        response = self.client.messages.create(
            model=settings.claude_model,
            max_tokens=settings.claude_analysis_max_tokens,
            system=[
                {
                    "type": "text",
                    "text": INSIGHT_SYSTEM_PROMPT,
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            messages=[
                {
                    "role": "user",
                    "content": f"""다음 주간 통화 데이터를 분석하여 팀 영업 인사이트 리포트를 작성하세요.

## 주간 통화 데이터
{summary_json}

## 리포트 형식 (JSON)
{{
  "period_summary": "기간 요약",
  "total_calls": 숫자,
  "hot_leads_count": 숫자,
  "top_trigger_words": ["워드1", "워드2"],
  "most_common_intent": "주요 의향",
  "average_opportunity_score": 숫자,
  "team_insights": ["인사이트1", "인사이트2"],
  "market_signals": ["시장 신호1", "신호2"],
  "recommended_strategies": ["전략1", "전략2"],
  "urgent_follow_ups": ["즉시 팔로업 필요 고객 정보"],
  "training_recommendations": ["팀 교육 권고사항"]
}}""",
                }
            ],
        )
        return self._safe_parse_json(response.content[0].text)

    def _call_claude(
        self,
        text: str,
        trigger_analysis: Optional[dict],
        customer_history: Optional[list[dict]],
    ) -> str:
        trigger_context = ""
        if trigger_analysis:
            trigger_context = f"\n## 트리거 분석 결과\n```json\n{json.dumps(trigger_analysis, ensure_ascii=False, indent=2)}\n```"

        history_context = ""
        if customer_history:
            history_context = f"\n## 고객 이전 상담 이력\n```json\n{json.dumps(customer_history, ensure_ascii=False, indent=2)}\n```"

        response = self.client.messages.create(
            model=settings.claude_model,
            max_tokens=settings.claude_analysis_max_tokens,
            system=[
                {
                    "type": "text",
                    "text": INSIGHT_SYSTEM_PROMPT,
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            messages=[
                {
                    "role": "user",
                    "content": f"""다음 부동산 상담 통화를 분석하여 영업 인사이트를 제공하세요.
{trigger_context}{history_context}

## 통화 내용
{text}

## 분석 형식 (JSON)
{{
  "summary": "통화 핵심 요약 (2-3문장)",
  "customer_profile": {{
    "estimated_budget": "예상 예산",
    "property_type": "관심 물건 유형",
    "area_preference": "선호 지역",
    "move_in_timeline": "입주 시기",
    "transaction_type": "거래 유형 (매매/전세/월세)",
    "decision_maker": true/false,
    "investment_purpose": true/false
  }},
  "property_interests": ["관심 물건 조건1", "조건2"],
  "pain_points": ["고객 불편사항/우려사항1", "사항2"],
  "recommended_properties": ["추천 물건 유형 또는 조건1", "조건2"],
  "action_items": [
    {{
      "action": "구체적 액션",
      "priority": "high/medium/low",
      "deadline": "오늘/내일/이번주/다음주",
      "channel": "전화/문자/카카오/방문/이메일"
    }}
  ],
  "follow_up_script": "팔로업 연락 시 사용할 스크립트 (구체적으로)",
  "risk_factors": ["거래 성사 리스크1", "리스크2"],
  "estimated_deal_probability": 0~100,
  "estimated_deal_timeline": "즉시/1개월/3개월/6개월/1년이상/미정"
}}""",
                }
            ],
        )
        return response.content[0].text

    def _parse_response(self, raw: str) -> dict:
        data = self._safe_parse_json(raw)
        action_items = [
            ActionItem(**item) for item in data.get("action_items", [])
            if all(k in item for k in ["action", "priority", "deadline", "channel"])
        ]
        return {
            "summary": data.get("summary", "분석 결과 없음"),
            "customer_profile": data.get("customer_profile", {}),
            "property_interests": data.get("property_interests", []),
            "pain_points": data.get("pain_points", []),
            "recommended_properties": data.get("recommended_properties", []),
            "action_items": action_items,
            "follow_up_script": data.get("follow_up_script", ""),
            "risk_factors": data.get("risk_factors", []),
            "estimated_deal_probability": int(data.get("estimated_deal_probability", 0)),
            "estimated_deal_timeline": data.get("estimated_deal_timeline", "미정"),
        }

    def _safe_parse_json(self, raw: str) -> dict:
        try:
            start = raw.find("{")
            end = raw.rfind("}") + 1
            return json.loads(raw[start:end])
        except (json.JSONDecodeError, ValueError):
            return {}
