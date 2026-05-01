"""
Google Sheets 연동 모듈
- 분석 결과 자동 업데이트
- 상담 데이터 실시간 조회
"""

import os
from typing import Optional, Any
from datetime import datetime

from google.oauth2 import service_account
from googleapiclient.discovery import build


class GoogleSheetsClient:
    SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

    def __init__(self, credentials_path: Optional[str] = None):
        """
        Google Sheets 클라이언트 초기화

        Args:
            credentials_path: 서비스 계정 JSON 키 파일 경로
        """
        self.credentials_path = credentials_path or os.getenv(
            "GOOGLE_APPLICATION_CREDENTIALS"
        )
        self.service = None
        self._initialize_service()

    def _initialize_service(self):
        """Google Sheets API 서비스 초기화"""
        if not self.credentials_path:
            raise ValueError(
                "Google 서비스 계정 인증 정보가 필요합니다."
            )

        credentials = service_account.Credentials.from_service_account_file(
            self.credentials_path, scopes=self.SCOPES
        )
        self.service = build("sheets", "v4", credentials=credentials)

    def append_analysis_result(
        self,
        spreadsheet_id: str,
        analysis_data: dict,
        sheet_name: str = "상담분석"
    ) -> dict:
        """
        분석 결과를 시트에 추가

        Args:
            spreadsheet_id: Google Sheets 문서 ID
            analysis_data: 분석 결과 데이터
            sheet_name: 시트명

        Returns:
            API 응답
        """
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        row = [
            timestamp,
            analysis_data.get("customer_id", ""),
            analysis_data.get("customer_name", ""),
            analysis_data.get("phone_number", ""),
            analysis_data.get("call_duration", ""),
            ", ".join(analysis_data.get("trigger_words", [])),
            analysis_data.get("sentiment", ""),
            analysis_data.get("sentiment_score", ""),
            analysis_data.get("interest_level", ""),
            analysis_data.get("recommended_action", ""),
            analysis_data.get("summary", ""),
            analysis_data.get("audio_file", ""),
        ]

        body = {"values": [row]}
        range_name = f"{sheet_name}!A:L"

        result = (
            self.service.spreadsheets()
            .values()
            .append(
                spreadsheetId=spreadsheet_id,
                range=range_name,
                valueInputOption="USER_ENTERED",
                insertDataOption="INSERT_ROWS",
                body=body,
            )
            .execute()
        )

        return result

    def create_analysis_sheet(self, spreadsheet_id: str, sheet_name: str = "상담분석") -> dict:
        """
        분석 결과용 시트 생성 및 헤더 설정

        Args:
            spreadsheet_id: Google Sheets 문서 ID
            sheet_name: 생성할 시트명

        Returns:
            API 응답
        """
        try:
            request_body = {
                "requests": [
                    {
                        "addSheet": {
                            "properties": {"title": sheet_name}
                        }
                    }
                ]
            }
            self.service.spreadsheets().batchUpdate(
                spreadsheetId=spreadsheet_id, body=request_body
            ).execute()
        except Exception:
            pass

        headers = [
            [
                "분석일시",
                "고객ID",
                "고객명",
                "연락처",
                "통화시간",
                "트리거워드",
                "감성",
                "감성점수",
                "관심도",
                "추천액션",
                "요약",
                "음성파일",
            ]
        ]

        self.service.spreadsheets().values().update(
            spreadsheetId=spreadsheet_id,
            range=f"{sheet_name}!A1:L1",
            valueInputOption="USER_ENTERED",
            body={"values": headers},
        ).execute()

        format_request = {
            "requests": [
                {
                    "repeatCell": {
                        "range": {
                            "sheetId": self._get_sheet_id(spreadsheet_id, sheet_name),
                            "startRowIndex": 0,
                            "endRowIndex": 1,
                        },
                        "cell": {
                            "userEnteredFormat": {
                                "backgroundColor": {"red": 0.2, "green": 0.4, "blue": 0.8},
                                "textFormat": {"bold": True, "foregroundColor": {"red": 1, "green": 1, "blue": 1}},
                            }
                        },
                        "fields": "userEnteredFormat(backgroundColor,textFormat)",
                    }
                }
            ]
        }

        return self.service.spreadsheets().batchUpdate(
            spreadsheetId=spreadsheet_id, body=format_request
        ).execute()

    def _get_sheet_id(self, spreadsheet_id: str, sheet_name: str) -> int:
        """시트명으로 시트 ID 조회"""
        spreadsheet = self.service.spreadsheets().get(
            spreadsheetId=spreadsheet_id
        ).execute()

        for sheet in spreadsheet.get("sheets", []):
            if sheet["properties"]["title"] == sheet_name:
                return sheet["properties"]["sheetId"]
        return 0

    def get_all_records(self, spreadsheet_id: str, sheet_name: str = "상담분석") -> list[dict]:
        """
        시트의 모든 레코드 조회

        Args:
            spreadsheet_id: Google Sheets 문서 ID
            sheet_name: 시트명

        Returns:
            레코드 목록
        """
        result = (
            self.service.spreadsheets()
            .values()
            .get(spreadsheetId=spreadsheet_id, range=f"{sheet_name}!A:L")
            .execute()
        )

        values = result.get("values", [])
        if len(values) < 2:
            return []

        headers = values[0]
        records = []
        for row in values[1:]:
            row_padded = row + [""] * (len(headers) - len(row))
            records.append(dict(zip(headers, row_padded)))

        return records

    def batch_append(
        self,
        spreadsheet_id: str,
        records: list[dict],
        sheet_name: str = "상담분석"
    ) -> dict:
        """
        여러 분석 결과를 한번에 추가

        Args:
            spreadsheet_id: Google Sheets 문서 ID
            records: 분석 결과 데이터 목록
            sheet_name: 시트명

        Returns:
            API 응답
        """
        rows = []
        for data in records:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            row = [
                timestamp,
                data.get("customer_id", ""),
                data.get("customer_name", ""),
                data.get("phone_number", ""),
                data.get("call_duration", ""),
                ", ".join(data.get("trigger_words", [])),
                data.get("sentiment", ""),
                data.get("sentiment_score", ""),
                data.get("interest_level", ""),
                data.get("recommended_action", ""),
                data.get("summary", ""),
                data.get("audio_file", ""),
            ]
            rows.append(row)

        body = {"values": rows}
        range_name = f"{sheet_name}!A:L"

        return (
            self.service.spreadsheets()
            .values()
            .append(
                spreadsheetId=spreadsheet_id,
                range=range_name,
                valueInputOption="USER_ENTERED",
                insertDataOption="INSERT_ROWS",
                body=body,
            )
            .execute()
        )
