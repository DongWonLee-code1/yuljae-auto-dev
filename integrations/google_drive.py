"""
Google Drive 연동 모듈
- 특정 폴더에서 음성 파일 자동 가져오기
- 처리된 파일 아카이브 이동
"""

import os
import io
from typing import Optional
from pathlib import Path
from datetime import datetime

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload


class GoogleDriveClient:
    SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]
    AUDIO_MIMETYPES = [
        "audio/mpeg",
        "audio/wav",
        "audio/mp3",
        "audio/x-wav",
        "audio/m4a",
        "audio/x-m4a",
    ]

    def __init__(self, credentials_path: Optional[str] = None):
        """
        Google Drive 클라이언트 초기화

        Args:
            credentials_path: 서비스 계정 JSON 키 파일 경로
                             환경변수 GOOGLE_APPLICATION_CREDENTIALS 사용 가능
        """
        self.credentials_path = credentials_path or os.getenv(
            "GOOGLE_APPLICATION_CREDENTIALS"
        )
        self.service = None
        self._initialize_service()

    def _initialize_service(self):
        """Google Drive API 서비스 초기화"""
        if not self.credentials_path:
            raise ValueError(
                "Google 서비스 계정 인증 정보가 필요합니다. "
                "GOOGLE_APPLICATION_CREDENTIALS 환경변수를 설정하거나 "
                "credentials_path를 제공하세요."
            )

        credentials = service_account.Credentials.from_service_account_file(
            self.credentials_path, scopes=self.SCOPES
        )
        self.service = build("drive", "v3", credentials=credentials)

    def list_audio_files(self, folder_id: str) -> list[dict]:
        """
        특정 폴더의 음성 파일 목록 조회

        Args:
            folder_id: Google Drive 폴더 ID

        Returns:
            파일 정보 목록 [{"id": ..., "name": ..., "mimeType": ...}, ...]
        """
        query_parts = [f"'{folder_id}' in parents", "trashed = false"]
        mimetype_conditions = " or ".join(
            [f"mimeType = '{mt}'" for mt in self.AUDIO_MIMETYPES]
        )
        query_parts.append(f"({mimetype_conditions})")
        query = " and ".join(query_parts)

        results = (
            self.service.files()
            .list(
                q=query,
                fields="files(id, name, mimeType, createdTime, size)",
                orderBy="createdTime desc",
            )
            .execute()
        )

        return results.get("files", [])

    def download_file(self, file_id: str, destination_path: str) -> str:
        """
        파일 다운로드

        Args:
            file_id: Google Drive 파일 ID
            destination_path: 저장할 로컬 경로

        Returns:
            저장된 파일 경로
        """
        request = self.service.files().get_media(fileId=file_id)
        Path(destination_path).parent.mkdir(parents=True, exist_ok=True)

        with open(destination_path, "wb") as f:
            downloader = MediaIoBaseDownload(f, request)
            done = False
            while not done:
                _, done = downloader.next_chunk()

        return destination_path

    def sync_folder(
        self, folder_id: str, local_directory: str, processed_tracker: Optional[set] = None
    ) -> list[str]:
        """
        Google Drive 폴더와 로컬 디렉토리 동기화

        Args:
            folder_id: Google Drive 폴더 ID
            local_directory: 로컬 저장 디렉토리
            processed_tracker: 이미 처리된 파일 ID 세트 (중복 방지)

        Returns:
            새로 다운로드된 파일 경로 목록
        """
        processed_tracker = processed_tracker or set()
        downloaded_files = []

        files = self.list_audio_files(folder_id)
        for file_info in files:
            file_id = file_info["id"]
            if file_id in processed_tracker:
                continue

            today = datetime.now()
            date_path = today.strftime("%Y/%m/%d")
            local_path = os.path.join(
                local_directory, date_path, file_info["name"]
            )

            self.download_file(file_id, local_path)
            downloaded_files.append(local_path)
            processed_tracker.add(file_id)

        return downloaded_files

    def get_folder_id_by_name(self, folder_name: str, parent_id: str = "root") -> Optional[str]:
        """
        폴더명으로 폴더 ID 조회

        Args:
            folder_name: 폴더명
            parent_id: 부모 폴더 ID (기본: root)

        Returns:
            폴더 ID 또는 None
        """
        query = (
            f"name = '{folder_name}' and "
            f"'{parent_id}' in parents and "
            f"mimeType = 'application/vnd.google-apps.folder' and "
            f"trashed = false"
        )

        results = (
            self.service.files()
            .list(q=query, fields="files(id, name)")
            .execute()
        )

        files = results.get("files", [])
        return files[0]["id"] if files else None
