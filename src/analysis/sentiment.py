"""감성 분석 모듈"""
from dataclasses import dataclass
from typing import List, Tuple
from enum import Enum
from transformers import pipeline, AutoTokenizer, AutoModelForSequenceClassification
import torch


class Sentiment(str, Enum):
    """감성 분류"""
    POSITIVE = "긍정"
    NEUTRAL = "중립"
    NEGATIVE = "부정"


@dataclass
class SentimentResult:
    """감성 분석 결과"""
    sentiment: Sentiment
    confidence: float
    positive_score: float
    neutral_score: float
    negative_score: float


@dataclass
class ConversationSentiment:
    """대화 전체 감성 분석 결과"""
    overall_sentiment: Sentiment
    overall_confidence: float
    segment_sentiments: List[Tuple[str, SentimentResult]]
    sentiment_trend: List[float]
    positive_ratio: float
    negative_ratio: float


class SentimentAnalyzer:
    """감성 분석기"""

    def __init__(self, model_name: str = "klue/bert-base"):
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self._load_model(model_name)

    def _load_model(self, model_name: str):
        """모델 로드"""
        try:
            self.classifier = pipeline(
                "sentiment-analysis",
                model="snunlp/KR-FinBert-SC",
                device=0 if self.device == "cuda" else -1
            )
        except Exception:
            self.classifier = None

    def analyze_text(self, text: str) -> SentimentResult:
        """단일 텍스트 감성 분석"""
        if not self.classifier:
            return self._rule_based_analysis(text)

        result = self.classifier(text[:512])[0]

        label = result["label"].lower()
        score = result["score"]

        if "positive" in label or "긍정" in label:
            return SentimentResult(
                sentiment=Sentiment.POSITIVE,
                confidence=score,
                positive_score=score,
                neutral_score=(1 - score) * 0.5,
                negative_score=(1 - score) * 0.5
            )
        elif "negative" in label or "부정" in label:
            return SentimentResult(
                sentiment=Sentiment.NEGATIVE,
                confidence=score,
                positive_score=(1 - score) * 0.5,
                neutral_score=(1 - score) * 0.5,
                negative_score=score
            )
        else:
            return SentimentResult(
                sentiment=Sentiment.NEUTRAL,
                confidence=score,
                positive_score=(1 - score) * 0.5,
                neutral_score=score,
                negative_score=(1 - score) * 0.5
            )

    def _rule_based_analysis(self, text: str) -> SentimentResult:
        """규칙 기반 감성 분석 (폴백)"""
        positive_words = ["좋", "감사", "만족", "훌륭", "최고", "추천", "괜찮", "네"]
        negative_words = ["싫", "불만", "문제", "별로", "안좋", "걱정", "힘들", "어렵"]

        pos_count = sum(1 for w in positive_words if w in text)
        neg_count = sum(1 for w in negative_words if w in text)

        total = pos_count + neg_count + 1
        pos_score = pos_count / total
        neg_score = neg_count / total
        neu_score = 1 - pos_score - neg_score

        if pos_score > neg_score and pos_score > 0.2:
            sentiment = Sentiment.POSITIVE
            confidence = pos_score
        elif neg_score > pos_score and neg_score > 0.2:
            sentiment = Sentiment.NEGATIVE
            confidence = neg_score
        else:
            sentiment = Sentiment.NEUTRAL
            confidence = neu_score

        return SentimentResult(
            sentiment=sentiment,
            confidence=confidence,
            positive_score=pos_score,
            neutral_score=neu_score,
            negative_score=neg_score
        )

    def analyze_conversation(
        self,
        segments: List[str]
    ) -> ConversationSentiment:
        """대화 전체 감성 분석"""
        segment_results = []
        sentiment_scores = []

        for segment in segments:
            result = self.analyze_text(segment)
            segment_results.append((segment, result))

            score = result.positive_score - result.negative_score
            sentiment_scores.append(score)

        if not segment_results:
            return ConversationSentiment(
                overall_sentiment=Sentiment.NEUTRAL,
                overall_confidence=0.5,
                segment_sentiments=[],
                sentiment_trend=[],
                positive_ratio=0.0,
                negative_ratio=0.0
            )

        positive_count = sum(
            1 for _, r in segment_results
            if r.sentiment == Sentiment.POSITIVE
        )
        negative_count = sum(
            1 for _, r in segment_results
            if r.sentiment == Sentiment.NEGATIVE
        )
        total = len(segment_results)

        avg_score = sum(sentiment_scores) / len(sentiment_scores)
        avg_confidence = sum(r.confidence for _, r in segment_results) / total

        if avg_score > 0.1:
            overall = Sentiment.POSITIVE
        elif avg_score < -0.1:
            overall = Sentiment.NEGATIVE
        else:
            overall = Sentiment.NEUTRAL

        return ConversationSentiment(
            overall_sentiment=overall,
            overall_confidence=avg_confidence,
            segment_sentiments=segment_results,
            sentiment_trend=sentiment_scores,
            positive_ratio=positive_count / total,
            negative_ratio=negative_count / total
        )
