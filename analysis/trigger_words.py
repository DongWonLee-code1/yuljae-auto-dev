"""
부동산 상담 통화에서 영업 트리거 워드를 추출하는 모듈.
Claude API의 prompt caching을 활용하여 비용 효율적으로 분석.
"""
import json
from dataclasses import dataclass, field
from datetime import datetime

import anthropic

from config import settings


# 부동산 영업 트리거 워드 카테고리 정의
REAL_ESTATE_TRIGGER_CATEGORIES = {
    "매수의향": [
        "사고 싶다", "구매", "매수", "살 생각", "집 보고 싶다", "물건 봐도 될까요",
        "언제 볼 수 있나요", "가격이 얼마예요", "시세가 어떻게 돼요", "급매",
        "좋은 물건", "추천해주세요", "괜찮은 거 있나요",
    ],
    "매도의향": [
        "팔고 싶다", "매도", "처분", "내놓을까", "시세 알고 싶다", "얼마에 팔 수 있나요",
        "내놓으면", "급하게 팔아야", "이사 가야", "정리하고 싶다",
    ],
    "투자관심": [
        "갭투자", "투자", "수익률", "임대수익", "월세 받을", "시세차익", "재건축",
        "재개발", "호재", "개발계획", "규제", "GTX", "교통 호재",
    ],
    "계약임박": [
        "계약", "계약금", "중도금", "잔금", "등기", "입주", "이사 날짜", "보증금",
        "특약", "하자", "확인서", "도장", "싸인", "공인중개사",
    ],
    "자금조달": [
        "대출", "담보대출", "전세자금대출", "DSR", "LTV", "이자", "금리", "은행",
        "한도", "대출 가능", "아파트 담보", "주담대", "신용대출",
    ],
    "전세임차": [
        "전세", "전세금", "보증금", "전입신고", "확정일자", "전세 대출",
        "전세 구하는", "갱신", "계약갱신청구권", "전세 만료", "이사",
    ],
    "월세임차": [
        "월세", "월 임대료", "관리비 포함", "보증금 낮게", "월세로", "원룸", "오피스텔",
    ],
    "학군교통": [
        "학교", "학군", "초등학교 배정", "통학", "지하철", "역세권", "버스", "교통",
        "출퇴근", "강남까지", "서울 접근성",
    ],
    "불만우려": [
        "비싸다", "너무해요", "다시 생각", "연락 마세요", "다른 데 알아볼게요",
        "경쟁사", "다른 중개사", "글쎄요", "고민이에요", "어렵겠는데",
    ],
    "긍정신호": [
        "마음에 들어요", "좋아 보여요", "괜찮네요", "해볼게요", "연락 주세요",
        "다시 연락드릴게요", "내일 봐도 될까요", "가족이랑 상의하고",
    ],
}

SYSTEM_PROMPT = """당신은 부동산 영업 전문 AI 분석가입니다.
주어진 통화 내용에서 영업 트리거 워드와 고객 의향을 정밀하게 분석합니다.
반드시 JSON 형식으로만 응답하세요."""


@dataclass
class TriggerWordResult:
    transcript_id: str
    found_triggers: dict[str, list[str]]
    category_scores: dict[str, int]
    dominant_intent: str
    customer_sentiment: str
    urgency_level: str
    opportunity_score: int
    raw_text_excerpt: list[str]
    analyzed_at: datetime = field(default_factory=datetime.utcnow)


class TriggerWordExtractor:
    def __init__(self):
        self.client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        self._category_json = json.dumps(REAL_ESTATE_TRIGGER_CATEGORIES, ensure_ascii=False, indent=2)

    def extract(self, transcript_id: str, text: str) -> TriggerWordResult:
        response = self._call_claude(text)
        parsed = self._parse_response(response)
        return TriggerWordResult(
            transcript_id=transcript_id,
            **parsed,
        )

    def _call_claude(self, text: str) -> str:
        # 시스템 프롬프트와 카테고리 정의에 prompt caching 적용
        response = self.client.messages.create(
            model=settings.claude_model,
            max_tokens=2048,
            system=[
                {
                    "type": "text",
                    "text": SYSTEM_PROMPT,
                    "cache_control": {"type": "ephemeral"},
                },
                {
                    "type": "text",
                    "text": f"## 트리거 워드 카테고리 기준\n```json\n{self._category_json}\n```",
                    "cache_control": {"type": "ephemeral"},
                },
            ],
            messages=[
                {
                    "role": "user",
                    "content": f"""다음 부동산 통화 내용을 분석하세요.

## 통화 내용
{text}

## 요구사항
다음 JSON 형식으로 분석 결과를 반환하세요:
{{
  "found_triggers": {{
    "카테고리명": ["발견된 트리거 워드1", "트리거 워드2"]
  }},
  "category_scores": {{
    "카테고리명": 0~100 점수
  }},
  "dominant_intent": "주요 의향 (매수의향/매도의향/투자관심/전세임차/월세임차/정보수집)",
  "customer_sentiment": "고객 감성 (매우긍정/긍정/중립/부정/매우부정)",
  "urgency_level": "긴박도 (즉시/단기1개월이내/중기3개월이내/장기/미정)",
  "opportunity_score": 0~100,
  "raw_text_excerpt": ["트리거 워드가 포함된 원문 발췌 1", "발췌 2"]
}}""",
                }
            ],
        )
        return response.content[0].text

    def _parse_response(self, raw: str) -> dict:
        try:
            start = raw.find("{")
            end = raw.rfind("}") + 1
            data = json.loads(raw[start:end])
            return {
                "found_triggers": data.get("found_triggers", {}),
                "category_scores": data.get("category_scores", {}),
                "dominant_intent": data.get("dominant_intent", "정보수집"),
                "customer_sentiment": data.get("customer_sentiment", "중립"),
                "urgency_level": data.get("urgency_level", "미정"),
                "opportunity_score": int(data.get("opportunity_score", 0)),
                "raw_text_excerpt": data.get("raw_text_excerpt", []),
            }
        except (json.JSONDecodeError, ValueError):
            return {
                "found_triggers": {},
                "category_scores": {},
                "dominant_intent": "분석실패",
                "customer_sentiment": "중립",
                "urgency_level": "미정",
                "opportunity_score": 0,
                "raw_text_excerpt": [],
            }
