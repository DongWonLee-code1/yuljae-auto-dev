"""
Slack 기반 음성 분석 자동화 봇.
지정된 채널에 오디오 파일이 업로드되면 자동으로 분석 파이프라인을 실행하고
결과를 스레드에 응답합니다.

Socket Mode를 사용하여 방화벽 문제 없이 안전하게 연결됩니다.
"""
import csv
import io
import logging
import os
import tempfile
from pathlib import Path

import httpx
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler

from config import settings
from automation.pipeline import ProcessingPipeline
from storage import Database

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

SUPPORTED_AUDIO_EXTENSIONS = {".m4a", ".mp3", ".mp4", ".wav", ".webm", ".ogg", ".mpeg", ".mpga"}

app = App(
    token=settings.slack_bot_token,
    signing_secret=settings.slack_signing_secret,
)


def is_audio_file(filename: str) -> bool:
    """오디오 파일인지 확인."""
    return Path(filename).suffix.lower() in SUPPORTED_AUDIO_EXTENSIONS


def download_slack_file(file_url: str, bot_token: str) -> bytes:
    """Slack 서버에서 파일 다운로드."""
    with httpx.Client() as client:
        response = client.get(
            file_url,
            headers={"Authorization": f"Bearer {bot_token}"},
            follow_redirects=True,
        )
        response.raise_for_status()
        return response.content


def format_analysis_message(result: dict, insight: dict) -> str:
    """분석 결과를 Slack 메시지 형식으로 포맷."""
    profile = insight.get("customer_profile", {})

    blocks = []

    # 헤더
    blocks.append(f"*📊 통화 분석 완료*")
    blocks.append("")

    # 요약
    blocks.append(f"*📝 요약*")
    blocks.append(insight.get("summary", "요약 없음"))
    blocks.append("")

    # 기회 점수
    score = result.get("opportunity_score", 0)
    score_emoji = "🔥" if score >= 80 else "✅" if score >= 60 else "📊"
    blocks.append(f"*{score_emoji} 기회 점수:* {score}/100")
    blocks.append(f"*🎯 주요 의향:* {result.get('dominant_intent', '미확인')}")
    blocks.append(f"*📈 거래 성사율:* {result.get('deal_probability', 0)}%")
    blocks.append("")

    # 고객 프로필
    if profile:
        blocks.append("*👤 고객 프로필*")
        if profile.get("estimated_budget"):
            blocks.append(f"• 예산: {profile['estimated_budget']}")
        if profile.get("area_preference"):
            blocks.append(f"• 선호 지역: {profile['area_preference']}")
        if profile.get("property_type"):
            blocks.append(f"• 관심 물건: {profile['property_type']}")
        if profile.get("transaction_type"):
            blocks.append(f"• 거래 유형: {profile['transaction_type']}")
        if profile.get("move_in_timeline"):
            blocks.append(f"• 입주 시기: {profile['move_in_timeline']}")
        blocks.append("")

    # 관심 조건
    interests = insight.get("property_interests", [])
    if interests:
        blocks.append("*🏠 관심 조건*")
        for item in interests[:5]:
            blocks.append(f"• {item}")
        blocks.append("")

    # 고객 우려사항
    pain_points = insight.get("pain_points", [])
    if pain_points:
        blocks.append("*⚠️ 고객 우려사항*")
        for item in pain_points[:3]:
            blocks.append(f"• {item}")
        blocks.append("")

    # 액션 아이템
    actions = insight.get("action_items", [])
    if actions:
        blocks.append("*✅ 다음 액션*")
        for action in actions[:3]:
            priority_emoji = "🔴" if action.get("priority") == "high" else "🟡" if action.get("priority") == "medium" else "🟢"
            blocks.append(f"{priority_emoji} [{action.get('deadline', '')}] {action.get('action', '')} ({action.get('channel', '')})")
        blocks.append("")

    # 리스크
    risks = insight.get("risk_factors", [])
    if risks:
        blocks.append("*🚨 리스크 요소*")
        for risk in risks[:3]:
            blocks.append(f"• {risk}")

    return "\n".join(blocks)


def generate_csv_content(result: dict, insight: dict, transcript_text: str) -> str:
    """분석 결과를 CSV 형식으로 생성."""
    output = io.StringIO()
    writer = csv.writer(output)

    # 헤더
    writer.writerow(["카테고리", "항목", "값"])

    # 기본 정보
    writer.writerow(["기본정보", "통화ID", result.get("call_id", "")])
    writer.writerow(["기본정보", "기회점수", result.get("opportunity_score", "")])
    writer.writerow(["기본정보", "주요의향", result.get("dominant_intent", "")])
    writer.writerow(["기본정보", "거래성사율", f"{result.get('deal_probability', 0)}%"])

    # 고객 프로필
    profile = insight.get("customer_profile", {})
    writer.writerow(["고객프로필", "예산", profile.get("estimated_budget", "")])
    writer.writerow(["고객프로필", "선호지역", profile.get("area_preference", "")])
    writer.writerow(["고객프로필", "물건유형", profile.get("property_type", "")])
    writer.writerow(["고객프로필", "거래유형", profile.get("transaction_type", "")])
    writer.writerow(["고객프로필", "입주시기", profile.get("move_in_timeline", "")])
    writer.writerow(["고객프로필", "의사결정자", "Y" if profile.get("decision_maker") else "N"])
    writer.writerow(["고객프로필", "투자목적", "Y" if profile.get("investment_purpose") else "N"])

    # 관심 조건
    for i, item in enumerate(insight.get("property_interests", []), 1):
        writer.writerow(["관심조건", f"조건{i}", item])

    # 우려사항
    for i, item in enumerate(insight.get("pain_points", []), 1):
        writer.writerow(["우려사항", f"사항{i}", item])

    # 추천 물건
    for i, item in enumerate(insight.get("recommended_properties", []), 1):
        writer.writerow(["추천물건", f"추천{i}", item])

    # 액션 아이템
    for i, action in enumerate(insight.get("action_items", []), 1):
        writer.writerow(["액션아이템", f"액션{i}", f"[{action.get('priority', '')}] {action.get('action', '')} - {action.get('deadline', '')} ({action.get('channel', '')})"])

    # 리스크
    for i, item in enumerate(insight.get("risk_factors", []), 1):
        writer.writerow(["리스크", f"리스크{i}", item])

    # 팔로업 스크립트
    writer.writerow(["팔로업", "스크립트", insight.get("follow_up_script", "")])

    # 요약
    writer.writerow(["요약", "내용", insight.get("summary", "")])

    return output.getvalue()


@app.event("file_shared")
def handle_file_shared(event: dict, client, say, logger):
    """파일 공유 이벤트 처리."""
    file_id = event.get("file_id")
    channel_id = event.get("channel_id")

    # 파일 정보 조회
    try:
        file_info = client.files_info(file=file_id)
        file_data = file_info["file"]
    except Exception as e:
        logger.error(f"파일 정보 조회 실패: {e}")
        return

    filename = file_data.get("name", "")

    # 오디오 파일인지 확인
    if not is_audio_file(filename):
        logger.info(f"오디오 파일이 아님, 스킵: {filename}")
        return

    # 파일이 공유된 메시지의 타임스탬프 (스레드 답장용)
    thread_ts = file_data.get("shares", {}).get("public", {}).get(channel_id, [{}])[0].get("ts")
    if not thread_ts:
        # private 채널인 경우
        thread_ts = file_data.get("shares", {}).get("private", {}).get(channel_id, [{}])[0].get("ts")

    logger.info(f"오디오 파일 감지: {filename} (channel: {channel_id})")

    # 처리 시작 메시지
    client.chat_postMessage(
        channel=channel_id,
        thread_ts=thread_ts,
        text=f"🎙️ *{filename}* 분석을 시작합니다...\n약 1-2분 정도 소요됩니다.",
    )

    try:
        # 파일 다운로드
        file_url = file_data.get("url_private_download")
        if not file_url:
            raise ValueError("파일 다운로드 URL을 찾을 수 없습니다.")

        audio_bytes = download_slack_file(file_url, settings.slack_bot_token)
        logger.info(f"파일 다운로드 완료: {len(audio_bytes)} bytes")

        # 파이프라인 실행
        pipeline = ProcessingPipeline()
        db = Database.get_session()

        try:
            result = pipeline.process_upload(
                db=db,
                audio_bytes=audio_bytes,
                filename=filename,
                phone_number="slack-upload",  # Slack에서는 전화번호 없음
                agent_name=f"slack:{channel_id}",
            )

            # 인사이트 조회
            insight_record = Database.get_insight_by_transcript(db, result["transcript_id"])
            insight = {
                "summary": insight_record.summary if insight_record else "",
                "customer_profile": insight_record.customer_profile if insight_record else {},
                "property_interests": insight_record.property_interests if insight_record else [],
                "pain_points": insight_record.pain_points if insight_record else [],
                "recommended_properties": insight_record.recommended_properties if insight_record else [],
                "action_items": insight_record.action_items if insight_record else [],
                "risk_factors": insight_record.risk_factors if insight_record else [],
                "follow_up_script": insight_record.follow_up_script if insight_record else "",
            }

            # 트랜스크립트 조회
            transcript_record = Database.get_transcript(db, result["transcript_id"])
            transcript_text = transcript_record.text if transcript_record else ""

        finally:
            db.close()

        # 분석 결과 메시지 전송
        message = format_analysis_message(result, insight)
        client.chat_postMessage(
            channel=channel_id,
            thread_ts=thread_ts,
            text=message,
        )

        # CSV 파일 생성 및 업로드
        csv_content = generate_csv_content(result, insight, transcript_text)
        csv_filename = f"분석결과_{Path(filename).stem}_{result['call_id']}.csv"

        client.files_upload_v2(
            channel=channel_id,
            thread_ts=thread_ts,
            content=csv_content,
            filename=csv_filename,
            title=f"📊 {filename} 분석 데이터",
            initial_comment="데이터베이스/엑셀 호환 CSV 파일입니다.",
        )

        logger.info(f"분석 완료: call_id={result['call_id']}, score={result['opportunity_score']}")

    except Exception as e:
        logger.exception(f"파일 처리 실패: {filename}")
        client.chat_postMessage(
            channel=channel_id,
            thread_ts=thread_ts,
            text=f"❌ 분석 중 오류가 발생했습니다.\n```{str(e)}```",
        )


@app.event("message")
def handle_message(event, logger):
    """일반 메시지 이벤트 (로깅용)."""
    pass  # file_shared만 처리


@app.command("/analyze")
def handle_analyze_command(ack, command, client, logger):
    """슬래시 커맨드로 수동 분석 트리거."""
    ack()

    channel_id = command["channel_id"]
    text = command.get("text", "").strip()

    if not text:
        client.chat_postMessage(
            channel=channel_id,
            text="사용법: `/analyze <파일URL>` 또는 채널에 오디오 파일을 직접 업로드하세요.",
        )
        return

    client.chat_postMessage(
        channel=channel_id,
        text=f"✅ 분석 요청을 받았습니다. 채널에 오디오 파일을 업로드하면 자동으로 분석됩니다.",
    )


def main():
    """봇 실행."""
    if not settings.slack_bot_token:
        raise ValueError("SLACK_BOT_TOKEN 환경 변수가 설정되지 않았습니다.")
    if not settings.slack_app_token:
        raise ValueError("SLACK_APP_TOKEN 환경 변수가 설정되지 않았습니다.")

    logger.info("Slack 봇 시작 (Socket Mode)")
    logger.info(f"지원 오디오 형식: {', '.join(SUPPORTED_AUDIO_EXTENSIONS)}")

    handler = SocketModeHandler(app, settings.slack_app_token)
    handler.start()


if __name__ == "__main__":
    main()
