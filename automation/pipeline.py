"""
통화 녹음 처리 자동화 파이프라인.
STT → 트리거 워드 추출 → 인사이트 생성 → 팔로업 자동 등록까지 전 과정을 자동화.
Google Drive, Google Sheets, Firebase 연동 지원.
"""
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, TYPE_CHECKING

from sqlalchemy.orm import Session

from config import settings
from storage import Database
from transcription import TranscriptionProcessor
from analysis import TriggerWordExtractor, InsightGenerator

if TYPE_CHECKING:
    from integrations.sync_service import SyncService


logger = logging.getLogger(__name__)


class ProcessingPipeline:
    def __init__(self, enable_cloud_sync: bool = True):
        self.transcriber = TranscriptionProcessor()
        self.trigger_extractor = TriggerWordExtractor()
        self.insight_generator = InsightGenerator()

        self.sync_service = None
        if enable_cloud_sync:
            try:
                from integrations.sync_service import SyncService
                self.sync_service = SyncService()
                logger.info("클라우드 동기화 서비스 활성화")
            except ImportError:
                logger.info("클라우드 연동 패키지 미설치 (로컬 모드)")
            except Exception as e:
                logger.warning(f"클라우드 동기화 초기화 실패 (로컬 모드로 진행): {e}")

    def process_upload(
        self,
        db: Session,
        audio_bytes: bytes,
        filename: str,
        phone_number: str,
        agent_name: str = "",
    ) -> dict:
        """업로드된 오디오를 저장하고 전체 분석 파이프라인을 실행."""
        # 1. 오디오 파일 저장
        saved_path = self.transcriber.save_audio(audio_bytes, filename)
        logger.info("오디오 저장: %s", saved_path)

        # 2. 통화 기록 생성
        stt_result = self.transcriber.process_file(saved_path)
        call_record = Database.create_call_record(
            db,
            phone_number=phone_number,
            audio_file_path=str(saved_path),
            audio_file_hash=stt_result.file_hash,
            agent_name=agent_name,
            duration_seconds=stt_result.duration_seconds,
        )
        Database.update_call_status(db, call_record.id, "processing")
        logger.info("통화 기록 생성: call_id=%d", call_record.id)

        # 3. 트랜스크립트 저장
        transcript = Database.save_transcript(
            db,
            call_id=call_record.id,
            text=stt_result.text,
            language=stt_result.language,
            segments=stt_result.segments,
        )
        logger.info("트랜스크립트 저장: transcript_id=%d", transcript.id)

        # 4. 트리거 워드 분석
        trigger_result = self.trigger_extractor.extract(
            transcript_id=str(transcript.id),
            text=stt_result.text,
        )
        trigger_record = Database.save_trigger_analysis(
            db,
            transcript_id=transcript.id,
            found_triggers=trigger_result.found_triggers,
            category_scores=trigger_result.category_scores,
            dominant_intent=trigger_result.dominant_intent,
            customer_sentiment=trigger_result.customer_sentiment,
            urgency_level=trigger_result.urgency_level,
            opportunity_score=trigger_result.opportunity_score,
            raw_text_excerpt=trigger_result.raw_text_excerpt,
        )
        logger.info(
            "트리거 분석 완료: score=%d, intent=%s",
            trigger_result.opportunity_score,
            trigger_result.dominant_intent,
        )

        # 5. 영업 인사이트 생성
        insight_result = self.insight_generator.generate(
            transcript_id=str(transcript.id),
            transcript_text=stt_result.text,
            trigger_analysis={
                "dominant_intent": trigger_result.dominant_intent,
                "opportunity_score": trigger_result.opportunity_score,
                "urgency_level": trigger_result.urgency_level,
                "found_triggers": trigger_result.found_triggers,
            },
        )
        insight_record = Database.save_insight(
            db,
            transcript_id=transcript.id,
            summary=insight_result.summary,
            customer_profile=insight_result.customer_profile,
            property_interests=insight_result.property_interests,
            pain_points=insight_result.pain_points,
            recommended_properties=insight_result.recommended_properties,
            action_items=[
                {
                    "action": a.action,
                    "priority": a.priority,
                    "deadline": a.deadline,
                    "channel": a.channel,
                }
                for a in insight_result.action_items
            ],
            follow_up_script=insight_result.follow_up_script,
            risk_factors=insight_result.risk_factors,
            estimated_deal_probability=insight_result.estimated_deal_probability,
            estimated_deal_timeline=insight_result.estimated_deal_timeline,
        )
        logger.info(
            "인사이트 생성 완료: deal_prob=%d%%", insight_result.estimated_deal_probability
        )

        # 6. 고객 프로필 자동 업데이트
        customer_profile = insight_result.customer_profile
        if call_record.customer_id and customer_profile:
            Database.update_customer(
                db,
                call_record.customer_id,
                estimated_budget=customer_profile.get("estimated_budget"),
                preferred_area=customer_profile.get("area_preference"),
                transaction_type=customer_profile.get("transaction_type"),
            )

        # 7. 팔로업 자동 등록 (기회 점수 높은 경우)
        follow_ups_created = []
        if (
            call_record.customer_id
            and trigger_result.opportunity_score >= settings.min_opportunity_score
        ):
            follow_ups_created = self._auto_create_follow_ups(
                db,
                customer_id=call_record.customer_id,
                call_record_id=call_record.id,
                action_items=insight_result.action_items,
                follow_up_script=insight_result.follow_up_script,
            )
            logger.info("팔로업 %d건 자동 생성", len(follow_ups_created))

        Database.update_call_status(db, call_record.id, "completed")

        # 8. 클라우드 동기화 (Google Sheets & Firebase)
        cloud_sync_result = None
        if self.sync_service:
            cloud_data = {
                "customer_id": str(call_record.customer_id or ""),
                "customer_name": customer_profile.get("name", "") if customer_profile else "",
                "phone_number": phone_number,
                "call_duration": str(stt_result.duration_seconds),
                "trigger_words": trigger_result.found_triggers,
                "sentiment": trigger_result.customer_sentiment,
                "sentiment_score": str(trigger_result.opportunity_score),
                "interest_level": trigger_result.urgency_level,
                "recommended_action": insight_result.action_items[0].action if insight_result.action_items else "",
                "summary": insight_result.summary,
                "audio_file": str(saved_path),
                "dominant_intent": trigger_result.dominant_intent,
                "deal_probability": insight_result.estimated_deal_probability,
            }
            cloud_sync_result = self.sync_service.save_analysis(cloud_data)
            logger.info("클라우드 동기화 완료: %s", cloud_sync_result)

        return {
            "call_id": call_record.id,
            "transcript_id": transcript.id,
            "opportunity_score": trigger_result.opportunity_score,
            "dominant_intent": trigger_result.dominant_intent,
            "follow_ups_created": len(follow_ups_created),
            "deal_probability": insight_result.estimated_deal_probability,
            "cloud_sync": cloud_sync_result,
        }

    def process_file_path(
        self,
        db: Session,
        file_path: str,
        phone_number: str,
        agent_name: str = "",
    ) -> dict:
        """로컬 파일 경로로 파이프라인 실행."""
        with open(file_path, "rb") as f:
            audio_bytes = f.read()
        return self.process_upload(
            db=db,
            audio_bytes=audio_bytes,
            filename=Path(file_path).name,
            phone_number=phone_number,
            agent_name=agent_name,
        )

    def _auto_create_follow_ups(
        self,
        db: Session,
        customer_id: int,
        call_record_id: int,
        action_items: list,
        follow_up_script: str,
    ) -> list:
        created = []
        deadline_map = {
            "오늘": timedelta(hours=3),
            "내일": timedelta(days=1),
            "이번주": timedelta(days=3),
            "다음주": timedelta(days=7),
        }
        for item in action_items[:3]:  # 최대 3개 자동 등록
            delta = deadline_map.get(item.deadline, timedelta(days=2))
            fu = Database.create_follow_up(
                db,
                customer_id=customer_id,
                action=item.action,
                channel=item.channel,
                priority=item.priority,
                due_date=datetime.utcnow() + delta,
                script=follow_up_script if item.priority == "high" else "",
                call_record_id=call_record_id,
            )
            created.append(fu)
        return created

    def batch_process_directory(
        self,
        db: Session,
        directory: str,
        phone_number_map: Optional[dict[str, str]] = None,
        agent_name: str = "",
    ) -> list[dict]:
        """디렉토리 내 모든 오디오 파일 일괄 처리."""
        results = []
        audio_extensions = {".mp3", ".wav", ".m4a", ".webm", ".ogg", ".mp4"}
        for path in Path(directory).iterdir():
            if path.suffix.lower() not in audio_extensions:
                continue
            phone = (phone_number_map or {}).get(path.stem, "000-0000-0000")
            try:
                result = self.process_file_path(
                    db=db,
                    file_path=str(path),
                    phone_number=phone,
                    agent_name=agent_name,
                )
                results.append({"file": path.name, "success": True, **result})
                logger.info("처리 완료: %s", path.name)
            except Exception as e:
                logger.error("처리 실패: %s - %s", path.name, e)
                results.append({"file": path.name, "success": False, "error": str(e)})
        return results

    def sync_and_process_from_drive(
        self,
        db: Session,
        phone_number_map: Optional[dict[str, str]] = None,
        agent_name: str = "",
        local_directory: str = "./data/audio/incoming",
    ) -> list[dict]:
        """
        Google Drive에서 새 파일을 동기화하고 처리.

        Args:
            db: 데이터베이스 세션
            phone_number_map: 파일명 → 전화번호 매핑
            agent_name: 상담원 이름
            local_directory: 로컬 저장 디렉토리

        Returns:
            처리 결과 목록
        """
        if not self.sync_service:
            logger.error("클라우드 동기화가 활성화되지 않았습니다")
            return []

        downloaded = self.sync_service.sync_from_drive(local_directory)
        if not downloaded:
            logger.info("새로 다운로드된 파일 없음")
            return []

        logger.info(f"Google Drive에서 {len(downloaded)}개 파일 다운로드")

        results = []
        for file_path in downloaded:
            filename = Path(file_path).stem
            phone = (phone_number_map or {}).get(filename, "000-0000-0000")
            try:
                result = self.process_file_path(
                    db=db,
                    file_path=file_path,
                    phone_number=phone,
                    agent_name=agent_name,
                )
                results.append({"file": Path(file_path).name, "success": True, **result})
                logger.info("처리 완료: %s", file_path)
            except Exception as e:
                logger.error("처리 실패: %s - %s", file_path, e)
                results.append({"file": Path(file_path).name, "success": False, "error": str(e)})

        return results

    def get_records_from_sheets(self) -> list[dict]:
        """Google Sheets에서 모든 분석 기록 조회."""
        if not self.sync_service:
            return []
        return self.sync_service.get_all_records_from_sheets()

    def get_customer_history(self, phone_number: str) -> list[dict]:
        """Firebase에서 고객 상담 이력 조회."""
        if not self.sync_service:
            return []
        return self.sync_service.get_customer_history_from_firebase(phone_number)
