"""트리거 워드 분석 테스트"""
import pytest
from src.analysis.trigger_words import TriggerWordAnalyzer, TriggerCategory


@pytest.fixture
def analyzer():
    return TriggerWordAnalyzer()


class TestTriggerWordAnalyzer:
    """트리거 워드 분석기 테스트"""

    def test_extract_purchase_intent(self, analyzer):
        """구매의향 트리거 추출"""
        text = "저는 이 아파트를 계약하고 싶습니다. 매수 의향이 있어요."
        triggers = analyzer.extract_triggers(text)

        categories = [t.category for t in triggers]
        assert TriggerCategory.PURCHASE_INTENT in categories

    def test_extract_urgency(self, analyzer):
        """긴급성 트리거 추출"""
        text = "급하게 이사를 해야 해서 빨리 결정하고 싶어요."
        triggers = analyzer.extract_triggers(text)

        categories = [t.category for t in triggers]
        assert TriggerCategory.URGENCY in categories

    def test_extract_budget(self, analyzer):
        """예산 트리거 추출"""
        text = "예산은 5억 정도이고, 대출을 받을 예정입니다."
        triggers = analyzer.extract_triggers(text)

        categories = [t.category for t in triggers]
        assert TriggerCategory.BUDGET in categories

    def test_analyze_full(self, analyzer):
        """전체 분석 테스트"""
        text = """
        안녕하세요, 강남역 근처 아파트를 찾고 있습니다.
        예산은 10억 정도이고, 역세권이면 좋겠어요.
        급하게 이사해야 해서 이번 달 안에 계약하고 싶습니다.
        """
        result = analyzer.analyze(text)

        assert result.intent_score > 0
        assert result.urgency_score > 0
        assert len(result.triggers) > 0
        assert len(result.key_phrases) > 0

    def test_category_scores(self, analyzer):
        """카테고리 점수 계산"""
        text = "계약을 빨리 하고 싶어요. 예산은 충분합니다."
        result = analyzer.analyze(text)

        assert TriggerCategory.PURCHASE_INTENT in result.category_scores
        assert TriggerCategory.URGENCY in result.category_scores

    def test_empty_text(self, analyzer):
        """빈 텍스트 처리"""
        result = analyzer.analyze("")
        assert result.intent_score == 0
        assert result.urgency_score == 0

    def test_key_phrases_extraction(self, analyzer):
        """핵심 문구 추출"""
        text = "아파트 아파트 아파트 전세 전세 월세"
        phrases = analyzer.extract_key_phrases(text, top_n=3)

        assert "아파트" in phrases
        assert "전세" in phrases
