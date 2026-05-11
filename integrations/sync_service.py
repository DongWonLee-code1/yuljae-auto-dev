"""
통합 동기화 서비스
- Google Drive에서 음성 파일 가져오기
- 분석 후 Google Sheets와 Firebase에 자동 저장
"""

import os
import logging
from typing import Optional
from datetime import datetime

from .google_drive import GoogleDriveClient
from .google_sheets import GoogleSheetsClient
from .firebase_client import FirebaseClient

logger = logging.getLogger(__name__)


class SyncService:
    def __init__(
        self,
        google_credentials: Optional[str] = None,
        firebase_credentials: Optional[str] = None,
        drive_folder_id: Optional[str] = None,
        sheets_id: Optional[str] = None,
    ):
        """
        통합 동기화 서비스 초기화

        Args:
            google_credentials: Google 서비스 계정 JSON 경로
            firebase_credentials: Firebase 서비스 계정 JSON 경로
            drive_folder_id: Google Drive 폴더 ID
            sheets_id: Google Sheets 문서 ID
        """
        self.drive_folder_id = drive_folder_id or os.getenv("GOOGLE_DRIVE_FOLDER_ID")
        self.sheets_id = sheets_id or os.getenv("GOOGLE_SHEETS_ID")

        self.drive_client = None
        self.sheets_client = None
        self.firebase_client = None

        self._processed_files: set = set()

        if google_credentials or os.getenv("GOOGLE_APPLICATION_CREDENTIALS"):
            try:
                self.drive_client = GoogleDriveClient(google_credentials)
                self.sheets_client = GoogleSheetsClient(google_credentials)
                logger.info("Google 클라이언트 초기화 완료")
            except Exception as e:
                logger.warning(f"Google 클라이언트 초기화 실패: {e}")

        if firebase_credentials or os.getenv("FIREBASE_CREDENTIALS"):
            try:
                self.firebase_client = FirebaseClient(firebase_credentials)
                logger.info("Firebase 클라이언트 초기화 완료")
            except Exception as e:
                logger.warning(f"Firebase 클라이언트 초기화 실패: {e}")

    def sync_from_drive(self, local_directory: str = "./data/audio/incoming") -> list[str]:
        """
        Google Drive에서 새 음성 파일 동기화

        Args:
            local_directory: 로컬 저장 디렉토리

        Returns:
            다운로드된 파일 경로 목록
        """
        if not self.drive_client:
            logger.error("Google Drive 클라이언트가 초기화되지 않았습니다")
            return []

        if not self.drive_folder_id:
            logger.error("GOOGLE_DRIVE_FOLDER_ID가 설정되지 않았습니다")
            return []

        try:
            downloaded = self.drive_client.sync_folder(
                self.drive_folder_id,
                local_directory,
                self._processed_files
            )
            logger.info(f"{len(downloaded)}개 파일 다운로드 완료")
            return downloaded
        except Exception as e:
            logger.error(f"Drive 동기화 실패: {e}")
            return []

    def save_to_sheets(self, analysis_data: dict) -> bool:
        """
        분석 결과를 Google Sheets에 저장

        Args:
            analysis_data: 분석 결과 데이터

        Returns:
            성공 여부
        """
        if not self.sheets_client:
            logger.warning("Google Sheets 클라이언트가 초기화되지 않았습니다")
            return False

        if not self.sheets_id:
            logger.error("GOOGLE_SHEETS_ID가 설정되지 않았습니다")
            return False

        try:
            self.sheets_client.append_analysis_result(self.sheets_id, analysis_data)
            logger.info("Google Sheets 저장 완료")
            return True
        except Exception as e:
            logger.error(f"Sheets 저장 실패: {e}")
            return False

    def save_to_firebase(self, analysis_data: dict) -> Optional[str]:
        """
        분석 결과를 Firebase에 저장

        Args:
            analysis_data: 분석 결과 데이터

        Returns:
            생성된 문서 ID 또는 None
        """
        if not self.firebase_client:
            logger.warning("Firebase 클라이언트가 초기화되지 않았습니다")
            return None

        try:
            doc_id = self.firebase_client.save_analysis(analysis_data)
            logger.info(f"Firebase 저장 완료: {doc_id}")
            return doc_id
        except Exception as e:
            logger.error(f"Firebase 저장 실패: {e}")
            return None

    def save_analysis(self, analysis_data: dict) -> dict:
        """
        분석 결과를 모든 저장소에 저장

        Args:
            analysis_data: 분석 결과 데이터

        Returns:
            저장 결과 {"sheets": bool, "firebase": str|None}
        """
        results = {
            "sheets": self.save_to_sheets(analysis_data),
            "firebase": self.save_to_firebase(analysis_data),
            "timestamp": datetime.now().isoformat(),
        }

        logger.info(f"분석 결과 저장 완료: {results}")
        return results

    def get_customer_history_from_firebase(self, phone_number: str) -> list[dict]:
        """
        Firebase에서 고객 상담 이력 조회

        Args:
            phone_number: 고객 연락처

        Returns:
            상담 이력 목록
        """
        if not self.firebase_client:
            return []

        return self.firebase_client.get_customer_history(phone_number)

    def get_all_records_from_sheets(self) -> list[dict]:
        """
        Google Sheets에서 모든 레코드 조회

        Returns:
            레코드 목록
        """
        if not self.sheets_client or not self.sheets_id:
            return []

        return self.sheets_client.get_all_records(self.sheets_id)

    def update_dashboard_stats(self, stats: dict):
        """
        Firebase Realtime Database에 대시보드 통계 업데이트

        Args:
            stats: 통계 데이터
        """
        if not self.firebase_client:
            logger.warning("Firebase 클라이언트가 없어 대시보드 업데이트 스킵")
            return

        try:
            self.firebase_client.update_realtime_dashboard(stats)
            logger.info("대시보드 통계 업데이트 완료")
        except Exception as e:
            logger.error(f"대시보드 업데이트 실패: {e}")

    def setup_sheets(self):
        """Google Sheets 초기 설정 (헤더 생성)"""
        if not self.sheets_client or not self.sheets_id:
            logger.error("Google Sheets 설정 불가")
            return

        try:
            self.sheets_client.create_analysis_sheet(self.sheets_id)
            logger.info("Google Sheets 초기 설정 완료")
        except Exception as e:
            logger.error(f"Sheets 설정 실패: {e}")
