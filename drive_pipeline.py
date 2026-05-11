#!/usr/bin/env python3
"""
구글 드라이브 & 구글 시트 자동화 파이프라인
Google Drive & Google Sheets Automation Pipeline

스마트폰 통화 녹음 파일이 구글 드라이브에 동기화되면 자동으로:
1. 처리 대기(To-Do) 폴더에서 새 .m4a 파일 탐색 및 다운로드
2. voice_run.py 분석 엔진 실행 → 텍스트/JSON 추출
3. 추출 데이터를 마스터 관리대장(Google Sheets)에 자동 추가
4. 처리 완료 파일을 완료(Done) 폴더로 이동

Usage:
    python drive_pipeline.py                    # 1회 실행
    python drive_pipeline.py --watch            # 주기적 폴링 (기본 5분)
    python drive_pipeline.py --watch --interval 300  # 5분마다 확인
"""

import argparse
import json
import os
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
import io

# 프로젝트 모듈 임포트
sys.path.insert(0, str(Path(__file__).parent))
from config.settings import Settings
from voice.assemblyai_client import AssemblyAIClient
from voice.formatters import OutputFormatter
from analysis.analyzer import ConsultationAnalyzer


# Google API 스코프
SCOPES = [
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/spreadsheets",
]

# 지원 오디오 확장자
AUDIO_EXTENSIONS = {".m4a", ".mp3", ".wav", ".flac", ".ogg", ".webm"}


class GoogleDriveClient:
    """구글 드라이브 API 클라이언트"""

    def __init__(self, credentials_path: str):
        """
        Args:
            credentials_path: 서비스 계정 JSON 키 파일 경로
        """
        credentials = service_account.Credentials.from_service_account_file(
            credentials_path, scopes=SCOPES
        )
        self.drive_service = build("drive", "v3", credentials=credentials)
        self.sheets_service = build("sheets", "v4", credentials=credentials)

    def list_audio_files(self, folder_id: str) -> list[dict]:
        """
        폴더 내 오디오 파일 목록 조회

        Args:
            folder_id: 구글 드라이브 폴더 ID

        Returns:
            파일 정보 딕셔너리 목록 [{"id": ..., "name": ..., "mimeType": ...}, ...]
        """
        query = f"'{folder_id}' in parents and trashed = false"
        results = (
            self.drive_service.files()
            .list(
                q=query,
                spaces="drive",
                fields="files(id, name, mimeType, createdTime, size)",
                orderBy="createdTime desc",
            )
            .execute()
        )

        files = results.get("files", [])
        audio_files = [
            f
            for f in files
            if Path(f["name"]).suffix.lower() in AUDIO_EXTENSIONS
        ]
        return audio_files

    def download_file(self, file_id: str, destination_path: str) -> str:
        """
        파일 다운로드

        Args:
            file_id: 구글 드라이브 파일 ID
            destination_path: 저장할 로컬 경로

        Returns:
            저장된 파일 경로
        """
        request = self.drive_service.files().get_media(fileId=file_id)
        fh = io.BytesIO()
        downloader = MediaIoBaseDownload(fh, request)

        done = False
        while not done:
            status, done = downloader.next_chunk()

        fh.seek(0)
        with open(destination_path, "wb") as f:
            f.write(fh.read())

        return destination_path

    def move_file(self, file_id: str, source_folder_id: str, dest_folder_id: str):
        """
        파일을 다른 폴더로 이동

        Args:
            file_id: 파일 ID
            source_folder_id: 원본 폴더 ID
            dest_folder_id: 대상 폴더 ID
        """
        self.drive_service.files().update(
            fileId=file_id,
            addParents=dest_folder_id,
            removeParents=source_folder_id,
            fields="id, parents",
        ).execute()

    def append_to_sheet(
        self, spreadsheet_id: str, sheet_name: str, values: list[list]
    ):
        """
        구글 시트에 데이터 추가

        Args:
            spreadsheet_id: 스프레드시트 ID
            sheet_name: 시트 이름 (탭 이름)
            values: 추가할 행 데이터 [[row1], [row2], ...]
        """
        range_name = f"{sheet_name}!A:A"
        body = {"values": values}

        self.sheets_service.spreadsheets().values().append(
            spreadsheetId=spreadsheet_id,
            range=range_name,
            valueInputOption="USER_ENTERED",
            insertDataOption="INSERT_ROWS",
            body=body,
        ).execute()

    def ensure_sheet_headers(
        self, spreadsheet_id: str, sheet_name: str, headers: list[str]
    ):
        """
        시트에 헤더가 없으면 추가

        Args:
            spreadsheet_id: 스프레드시트 ID
            sheet_name: 시트 이름
            headers: 헤더 목록
        """
        range_name = f"{sheet_name}!1:1"
        result = (
            self.sheets_service.spreadsheets()
            .values()
            .get(spreadsheetId=spreadsheet_id, range=range_name)
            .execute()
        )

        existing_values = result.get("values", [])
        if not existing_values or not existing_values[0]:
            body = {"values": [headers]}
            self.sheets_service.spreadsheets().values().update(
                spreadsheetId=spreadsheet_id,
                range=range_name,
                valueInputOption="RAW",
                body=body,
            ).execute()


class DrivePipeline:
    """구글 드라이브 기반 자동화 파이프라인"""

    def __init__(
        self,
        credentials_path: str,
        todo_folder_id: str,
        done_folder_id: str,
        spreadsheet_id: str,
        sheet_name: str = "상담기록",
    ):
        """
        Args:
            credentials_path: 서비스 계정 JSON 키 파일 경로
            todo_folder_id: 처리 대기 폴더 ID
            done_folder_id: 처리 완료 폴더 ID
            spreadsheet_id: 마스터 관리대장 스프레드시트 ID
            sheet_name: 데이터를 기록할 시트 이름
        """
        self.drive_client = GoogleDriveClient(credentials_path)
        self.todo_folder_id = todo_folder_id
        self.done_folder_id = done_folder_id
        self.spreadsheet_id = spreadsheet_id
        self.sheet_name = sheet_name

        self.settings = Settings()
        self.transcriber = AssemblyAIClient(self.settings)
        self.analyzer = ConsultationAnalyzer()
        self.formatter = OutputFormatter(self.settings.output_dir)

        self._processed_files: set[str] = set()

    def _get_sheet_headers(self) -> list[str]:
        """시트 헤더 정의"""
        return [
            "상담ID",
            "처리일시",
            "원본파일",
            "통화시간(초)",
            "화자수",
            "요약",
            "후속조치필요",
            "후속조치항목",
            # 가격 정보
            "매매가",
            "전세가",
            "보증금",
            "월세",
            "희망가격_최소",
            "희망가격_최대",
            "가격협상가능",
            "가격협상상세",
            "가격_원문",
            # 위치 정보
            "구/군",
            "동",
            "단지명",
            "인근역",
            "역세권여부",
            "선호지역",
            "제외지역",
            "위치_원문",
            # 일정 정보
            "희망계약시점",
            "입주희망일",
            "긴급도",
            "현계약만료일",
            "매물보기가능시간",
            "일정_원문",
            # 협상 정보
            "필수조건",
            "희망조건",
            "거래불가조건",
            "특별요청",
            "우려사항",
            "협상_원문",
            # 고객 정보
            "연령대",
            "가족구성",
            "현거주지",
            "직업힌트",
            "예산여력",
            "의사결정자",
            "고객_원문",
        ]

    def _analysis_to_row(self, analysis) -> list:
        """AnalysisResult를 시트 행으로 변환"""
        p = analysis.price
        loc = analysis.location
        t = analysis.timeline
        n = analysis.negotiation
        c = analysis.customer

        def join_list(lst: list) -> str:
            return "; ".join(lst) if lst else ""

        def bool_to_yn(val: Optional[bool]) -> str:
            if val is None:
                return ""
            return "Y" if val else "N"

        return [
            analysis.consultation_id,
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            analysis.source_file,
            analysis.duration_seconds,
            analysis.speaker_count,
            analysis.summary,
            bool_to_yn(analysis.follow_up_needed),
            join_list(analysis.follow_up_actions),
            # 가격
            p.sale_price or "",
            p.jeonse_price or "",
            p.deposit or "",
            p.monthly_rent or "",
            p.price_range_min or "",
            p.price_range_max or "",
            bool_to_yn(p.negotiable),
            p.negotiation_details or "",
            join_list(p.trigger_quotes),
            # 위치
            loc.district or "",
            loc.neighborhood or "",
            loc.complex_name or "",
            join_list(loc.nearby_stations),
            bool_to_yn(loc.is_station_area),
            join_list(loc.preferred_areas),
            join_list(loc.excluded_areas),
            join_list(loc.trigger_quotes),
            # 일정
            t.contract_date_preference or "",
            t.move_in_date or "",
            t.urgency_level or "",
            t.current_contract_end or "",
            t.viewing_availability or "",
            join_list(t.trigger_quotes),
            # 협상
            join_list(n.must_have_conditions),
            join_list(n.nice_to_have_conditions),
            join_list(n.deal_breakers),
            join_list(n.special_requests),
            join_list(n.concerns),
            join_list(n.trigger_quotes),
            # 고객
            c.age_group or "",
            c.family_composition or "",
            c.current_residence or "",
            c.occupation_hint or "",
            c.budget_capacity or "",
            c.decision_maker or "",
            join_list(c.trigger_quotes),
        ]

    def process_file(self, file_info: dict) -> dict:
        """
        단일 파일 처리

        Args:
            file_info: {"id": ..., "name": ...}

        Returns:
            처리 결과 {"success": bool, "analysis": ..., "error": ...}
        """
        file_id = file_info["id"]
        file_name = file_info["name"]

        print(f"  📥 다운로드 중: {file_name}")

        with tempfile.TemporaryDirectory() as temp_dir:
            local_path = os.path.join(temp_dir, file_name)
            self.drive_client.download_file(file_id, local_path)
            print(f"  🎙️ 전사 및 분석 중...")

            try:
                transcription = self.transcriber.transcribe_file(local_path)
                self.formatter.save(transcription)
                analysis = self.analyzer.analyze(transcription)
                self.analyzer.save_result(analysis)

                print(f"  📊 구글 시트에 기록 중...")
                row_data = self._analysis_to_row(analysis)
                self.drive_client.append_to_sheet(
                    self.spreadsheet_id, self.sheet_name, [row_data]
                )

                print(f"  📁 완료 폴더로 이동 중...")
                self.drive_client.move_file(
                    file_id, self.todo_folder_id, self.done_folder_id
                )

                return {"success": True, "analysis": analysis, "file_name": file_name}

            except Exception as e:
                return {"success": False, "error": str(e), "file_name": file_name}

    def run_once(self) -> list[dict]:
        """
        1회 실행: 대기 폴더의 모든 파일 처리

        Returns:
            처리 결과 목록
        """
        print(f"\n{'='*60}")
        print(f"🔍 처리 대기 폴더 확인 중... [{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}]")
        print(f"{'='*60}")

        audio_files = self.drive_client.list_audio_files(self.todo_folder_id)

        if not audio_files:
            print("📭 처리할 새 파일이 없습니다.")
            return []

        print(f"📂 {len(audio_files)}개 파일 발견:")
        for f in audio_files:
            print(f"   - {f['name']}")

        self.drive_client.ensure_sheet_headers(
            self.spreadsheet_id, self.sheet_name, self._get_sheet_headers()
        )

        results = []
        for idx, file_info in enumerate(audio_files, 1):
            print(f"\n[{idx}/{len(audio_files)}] 처리 중: {file_info['name']}")

            result = self.process_file(file_info)
            results.append(result)

            if result["success"]:
                print(f"  ✅ 완료: {result['analysis'].consultation_id}")
                print(f"     요약: {result['analysis'].summary[:50]}...")
            else:
                print(f"  ❌ 실패: {result['error']}")

        success_count = sum(1 for r in results if r["success"])
        print(f"\n{'='*60}")
        print(f"📊 처리 완료: 성공 {success_count}/{len(results)}")
        print(f"{'='*60}")

        return results

    def watch(self, interval_seconds: int = 300):
        """
        주기적 폴링 모드

        Args:
            interval_seconds: 확인 주기 (초, 기본 5분)
        """
        print(f"👀 감시 모드 시작 (주기: {interval_seconds}초)")
        print("   종료하려면 Ctrl+C를 누르세요.\n")

        try:
            while True:
                self.run_once()
                print(f"\n⏰ 다음 확인: {interval_seconds}초 후...")
                time.sleep(interval_seconds)
        except KeyboardInterrupt:
            print("\n\n🛑 감시 모드 종료")


def main():
    parser = argparse.ArgumentParser(
        description="구글 드라이브 & 구글 시트 자동화 파이프라인"
    )
    parser.add_argument(
        "--credentials",
        type=str,
        default=os.getenv("GOOGLE_SERVICE_ACCOUNT_PATH", "credentials.json"),
        help="서비스 계정 JSON 키 파일 경로",
    )
    parser.add_argument(
        "--todo-folder",
        type=str,
        default=os.getenv("GOOGLE_DRIVE_TODO_FOLDER_ID"),
        help="처리 대기 폴더 ID",
    )
    parser.add_argument(
        "--done-folder",
        type=str,
        default=os.getenv("GOOGLE_DRIVE_DONE_FOLDER_ID"),
        help="처리 완료 폴더 ID",
    )
    parser.add_argument(
        "--spreadsheet",
        type=str,
        default=os.getenv("GOOGLE_SHEETS_SPREADSHEET_ID"),
        help="마스터 관리대장 스프레드시트 ID",
    )
    parser.add_argument(
        "--sheet-name",
        type=str,
        default=os.getenv("GOOGLE_SHEETS_SHEET_NAME", "상담기록"),
        help="시트(탭) 이름",
    )
    parser.add_argument(
        "--watch",
        action="store_true",
        help="주기적 폴링 모드 활성화",
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=300,
        help="폴링 주기 (초, 기본 300초=5분)",
    )

    args = parser.parse_args()

    required_vars = {
        "처리 대기 폴더 ID": args.todo_folder,
        "처리 완료 폴더 ID": args.done_folder,
        "스프레드시트 ID": args.spreadsheet,
    }
    missing = [k for k, v in required_vars.items() if not v]
    if missing:
        print(f"❌ 필수 설정 누락: {', '.join(missing)}")
        print("\n환경 변수 또는 명령줄 인자로 설정해주세요.")
        print("자세한 설정 방법은 GOOGLE_DRIVE_SETUP.md를 참고하세요.")
        sys.exit(1)

    if not os.path.exists(args.credentials):
        print(f"❌ 서비스 계정 키 파일을 찾을 수 없습니다: {args.credentials}")
        print("\n서비스 계정 설정 방법은 GOOGLE_DRIVE_SETUP.md를 참고하세요.")
        sys.exit(1)

    pipeline = DrivePipeline(
        credentials_path=args.credentials,
        todo_folder_id=args.todo_folder,
        done_folder_id=args.done_folder,
        spreadsheet_id=args.spreadsheet,
        sheet_name=args.sheet_name,
    )

    if args.watch:
        pipeline.watch(interval_seconds=args.interval)
    else:
        pipeline.run_once()


if __name__ == "__main__":
    main()
