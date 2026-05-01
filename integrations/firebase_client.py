"""
Firebase 연동 모듈
- Firestore: 상담 데이터 실시간 저장
- Realtime Database: 대시보드 실시간 업데이트
"""

import os
from typing import Optional, Any
from datetime import datetime

import firebase_admin
from firebase_admin import credentials, firestore, db


class FirebaseClient:
    def __init__(
        self,
        credentials_path: Optional[str] = None,
        database_url: Optional[str] = None,
        project_id: Optional[str] = None,
    ):
        """
        Firebase 클라이언트 초기화

        Args:
            credentials_path: Firebase 서비스 계정 JSON 키 파일 경로
            database_url: Realtime Database URL
            project_id: Firebase 프로젝트 ID
        """
        self.credentials_path = credentials_path or os.getenv(
            "FIREBASE_CREDENTIALS"
        )
        self.database_url = database_url or os.getenv("FIREBASE_DATABASE_URL")
        self.project_id = project_id or os.getenv("FIREBASE_PROJECT_ID")

        self._initialize_app()
        self.firestore_db = firestore.client()

    def _initialize_app(self):
        """Firebase 앱 초기화"""
        if firebase_admin._apps:
            return

        if not self.credentials_path:
            raise ValueError(
                "Firebase 인증 정보가 필요합니다. "
                "FIREBASE_CREDENTIALS 환경변수를 설정하세요."
            )

        cred = credentials.Certificate(self.credentials_path)
        options = {}
        if self.database_url:
            options["databaseURL"] = self.database_url
        if self.project_id:
            options["projectId"] = self.project_id

        firebase_admin.initialize_app(cred, options)

    def save_analysis(self, analysis_data: dict) -> str:
        """
        분석 결과를 Firestore에 저장

        Args:
            analysis_data: 분석 결과 데이터

        Returns:
            생성된 문서 ID
        """
        collection = self.firestore_db.collection("consultations")

        doc_data = {
            **analysis_data,
            "created_at": firestore.SERVER_TIMESTAMP,
            "updated_at": firestore.SERVER_TIMESTAMP,
        }

        doc_ref = collection.add(doc_data)
        return doc_ref[1].id

    def save_customer(self, customer_data: dict) -> str:
        """
        고객 정보를 Firestore에 저장

        Args:
            customer_data: 고객 데이터

        Returns:
            문서 ID
        """
        collection = self.firestore_db.collection("customers")

        phone = customer_data.get("phone_number", "")
        existing = collection.where("phone_number", "==", phone).limit(1).get()

        if existing:
            doc_ref = existing[0].reference
            doc_ref.update({
                **customer_data,
                "updated_at": firestore.SERVER_TIMESTAMP,
            })
            return doc_ref.id

        doc_data = {
            **customer_data,
            "created_at": firestore.SERVER_TIMESTAMP,
            "updated_at": firestore.SERVER_TIMESTAMP,
            "consultation_count": 1,
        }
        doc_ref = collection.add(doc_data)
        return doc_ref[1].id

    def get_customer_history(self, phone_number: str) -> list[dict]:
        """
        고객의 상담 이력 조회

        Args:
            phone_number: 고객 연락처

        Returns:
            상담 이력 목록
        """
        collection = self.firestore_db.collection("consultations")
        docs = (
            collection.where("phone_number", "==", phone_number)
            .order_by("created_at", direction=firestore.Query.DESCENDING)
            .get()
        )

        return [{"id": doc.id, **doc.to_dict()} for doc in docs]

    def update_realtime_dashboard(self, stats: dict):
        """
        Realtime Database에 대시보드 통계 업데이트

        Args:
            stats: 대시보드 통계 데이터
        """
        if not self.database_url:
            raise ValueError("Realtime Database URL이 설정되지 않았습니다.")

        ref = db.reference("/dashboard/stats")
        ref.set({
            **stats,
            "last_updated": datetime.now().isoformat(),
        })

    def get_daily_stats(self, date: Optional[str] = None) -> dict:
        """
        일별 통계 조회

        Args:
            date: 조회 날짜 (YYYY-MM-DD), 없으면 오늘

        Returns:
            통계 데이터
        """
        if date is None:
            date = datetime.now().strftime("%Y-%m-%d")

        start = datetime.strptime(date, "%Y-%m-%d")
        end = datetime.strptime(date, "%Y-%m-%d").replace(
            hour=23, minute=59, second=59
        )

        collection = self.firestore_db.collection("consultations")
        docs = (
            collection.where("created_at", ">=", start)
            .where("created_at", "<=", end)
            .get()
        )

        total_calls = len(docs)
        sentiments = {"positive": 0, "neutral": 0, "negative": 0}
        trigger_word_counts = {}

        for doc in docs:
            data = doc.to_dict()

            sentiment = data.get("sentiment", "neutral")
            if sentiment in sentiments:
                sentiments[sentiment] += 1

            for word in data.get("trigger_words", []):
                trigger_word_counts[word] = trigger_word_counts.get(word, 0) + 1

        return {
            "date": date,
            "total_calls": total_calls,
            "sentiment_distribution": sentiments,
            "top_trigger_words": sorted(
                trigger_word_counts.items(), key=lambda x: x[1], reverse=True
            )[:10],
        }

    def stream_consultations(self, callback):
        """
        상담 데이터 실시간 스트리밍

        Args:
            callback: 데이터 변경 시 호출될 콜백 함수
        """
        collection = self.firestore_db.collection("consultations")

        def on_snapshot(doc_snapshot, changes, read_time):
            for change in changes:
                if change.type.name == "ADDED":
                    callback("added", change.document.id, change.document.to_dict())
                elif change.type.name == "MODIFIED":
                    callback("modified", change.document.id, change.document.to_dict())
                elif change.type.name == "REMOVED":
                    callback("removed", change.document.id, None)

        return collection.on_snapshot(on_snapshot)

    def batch_save_analyses(self, analyses: list[dict]) -> list[str]:
        """
        여러 분석 결과를 배치로 저장

        Args:
            analyses: 분석 결과 목록

        Returns:
            생성된 문서 ID 목록
        """
        batch = self.firestore_db.batch()
        collection = self.firestore_db.collection("consultations")
        doc_ids = []

        for analysis in analyses:
            doc_ref = collection.document()
            doc_ids.append(doc_ref.id)
            batch.set(doc_ref, {
                **analysis,
                "created_at": firestore.SERVER_TIMESTAMP,
                "updated_at": firestore.SERVER_TIMESTAMP,
            })

        batch.commit()
        return doc_ids
