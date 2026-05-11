"""트리거 워드 추출 및 분석 모듈"""
from dataclasses import dataclass
from typing import List, Dict, Set, Optional
from enum import Enum
from konlpy.tag import Okt
import re


class TriggerCategory(str, Enum):
    """트리거 워드 카테고리"""
    PURCHASE_INTENT = "구매의향"
    URGENCY = "긴급성"
    BUDGET = "예산"
    LOCATION = "위치선호"
    CONCERN = "우려사항"
    COMPETITOR = "경쟁사언급"
    TIMELINE = "시기"
    NEGOTIATION = "협상"


@dataclass
class TriggerWord:
    """트리거 워드 정보"""
    word: str
    category: TriggerCategory
    weight: float
    context: str
    position: int


@dataclass
class TriggerAnalysisResult:
    """트리거 분석 결과"""
    triggers: List[TriggerWord]
    category_scores: Dict[TriggerCategory, float]
    intent_score: float
    urgency_score: float
    key_phrases: List[str]


class TriggerWordAnalyzer:
    """트리거 워드 분석기"""

    TRIGGER_PATTERNS = {
        TriggerCategory.PURCHASE_INTENT: [
            ("계약", 0.9), ("구매", 0.85), ("사고 싶", 0.8), ("관심", 0.6),
            ("매수", 0.9), ("입주", 0.75), ("전세", 0.7), ("월세", 0.7),
            ("투자", 0.8), ("분양", 0.85), ("청약", 0.9)
        ],
        TriggerCategory.URGENCY: [
            ("급하", 0.9), ("빨리", 0.8), ("당장", 0.95), ("이번 주", 0.85),
            ("오늘", 0.9), ("내일", 0.85), ("이사", 0.7), ("만료", 0.8),
            ("곧", 0.6), ("서둘러", 0.85)
        ],
        TriggerCategory.BUDGET: [
            ("예산", 0.9), ("억", 0.7), ("만원", 0.6), ("가격", 0.7),
            ("비싸", 0.6), ("싸", 0.6), ("대출", 0.75), ("자금", 0.8),
            ("할부", 0.7), ("현금", 0.8)
        ],
        TriggerCategory.LOCATION: [
            ("역세권", 0.85), ("학군", 0.9), ("교통", 0.7), ("편의시설", 0.7),
            ("공원", 0.6), ("근처", 0.5), ("동네", 0.6), ("위치", 0.7),
            ("접근성", 0.75), ("환경", 0.6)
        ],
        TriggerCategory.CONCERN: [
            ("걱정", 0.8), ("불안", 0.85), ("문제", 0.7), ("하자", 0.9),
            ("소음", 0.75), ("층간", 0.8), ("주차", 0.65), ("보안", 0.7),
            ("관리비", 0.7), ("노후", 0.75)
        ],
        TriggerCategory.COMPETITOR: [
            ("다른 곳", 0.8), ("다른 업체", 0.9), ("비교", 0.75), ("견적", 0.8),
            ("알아보", 0.6), ("둘러보", 0.6), ("여러 군데", 0.7)
        ],
        TriggerCategory.TIMELINE: [
            ("언제", 0.6), ("시기", 0.7), ("기간", 0.65), ("개월", 0.6),
            ("내년", 0.7), ("올해", 0.75), ("분기", 0.7), ("상반기", 0.75),
            ("하반기", 0.75)
        ],
        TriggerCategory.NEGOTIATION: [
            ("깎아", 0.9), ("할인", 0.85), ("네고", 0.95), ("조정", 0.7),
            ("협의", 0.75), ("가능", 0.5), ("더", 0.4), ("조건", 0.6)
        ],
    }

    def __init__(self):
        self.okt = Okt()
        self._compile_patterns()

    def _compile_patterns(self):
        """정규식 패턴 컴파일"""
        self.compiled_patterns = {}
        for category, words in self.TRIGGER_PATTERNS.items():
            self.compiled_patterns[category] = [
                (re.compile(rf"(.{{0,20}}{word}.{{0,20}})"), weight, word)
                for word, weight in words
            ]

    def extract_triggers(self, text: str) -> List[TriggerWord]:
        """텍스트에서 트리거 워드 추출"""
        triggers = []

        for category, patterns in self.compiled_patterns.items():
            for pattern, weight, word in patterns:
                for match in pattern.finditer(text):
                    triggers.append(TriggerWord(
                        word=word,
                        category=category,
                        weight=weight,
                        context=match.group(1).strip(),
                        position=match.start()
                    ))

        triggers.sort(key=lambda x: (-x.weight, x.position))
        return triggers

    def calculate_category_scores(
        self,
        triggers: List[TriggerWord]
    ) -> Dict[TriggerCategory, float]:
        """카테고리별 점수 계산"""
        scores = {cat: 0.0 for cat in TriggerCategory}
        counts = {cat: 0 for cat in TriggerCategory}

        for trigger in triggers:
            scores[trigger.category] += trigger.weight
            counts[trigger.category] += 1

        for cat in scores:
            if counts[cat] > 0:
                scores[cat] = min(1.0, scores[cat] / max(counts[cat], 1))

        return scores

    def extract_key_phrases(self, text: str, top_n: int = 10) -> List[str]:
        """핵심 문구 추출"""
        nouns = self.okt.nouns(text)
        noun_counts = {}
        for noun in nouns:
            if len(noun) >= 2:
                noun_counts[noun] = noun_counts.get(noun, 0) + 1

        sorted_nouns = sorted(
            noun_counts.items(),
            key=lambda x: x[1],
            reverse=True
        )
        return [noun for noun, _ in sorted_nouns[:top_n]]

    def analyze(self, text: str) -> TriggerAnalysisResult:
        """전체 트리거 분석 수행"""
        triggers = self.extract_triggers(text)
        category_scores = self.calculate_category_scores(triggers)
        key_phrases = self.extract_key_phrases(text)

        intent_score = (
            category_scores[TriggerCategory.PURCHASE_INTENT] * 0.4 +
            category_scores[TriggerCategory.BUDGET] * 0.3 +
            category_scores[TriggerCategory.TIMELINE] * 0.2 +
            category_scores[TriggerCategory.NEGOTIATION] * 0.1
        )

        urgency_score = (
            category_scores[TriggerCategory.URGENCY] * 0.6 +
            category_scores[TriggerCategory.TIMELINE] * 0.4
        )

        return TriggerAnalysisResult(
            triggers=triggers,
            category_scores=category_scores,
            intent_score=min(1.0, intent_score),
            urgency_score=min(1.0, urgency_score),
            key_phrases=key_phrases
        )
