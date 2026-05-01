"""
외부 서비스 연동 모듈
- Google Drive: 음성 파일 가져오기
- Google Sheets: 분석 결과 내보내기
- Firebase: 실시간 데이터베이스 저장
"""

from .google_drive import GoogleDriveClient
from .google_sheets import GoogleSheetsClient
from .firebase_client import FirebaseClient
from .sync_service import SyncService

__all__ = ["GoogleDriveClient", "GoogleSheetsClient", "FirebaseClient", "SyncService"]
