"""
율재부동산 영업 데이터 자산화 시스템 - Streamlit 대시보드.
실시간 영업 현황, 트리거 워드 분석, 핫 리드, 팔로업 관리를 통합 제공.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from datetime import datetime

from config import settings
from storage import Database, init_db, get_db
from storage.models import CallRecord, Customer, FollowUp, TriggerWordAnalysis, Transcript
from automation.pipeline import ProcessingPipeline


st.set_page_config(
    page_title=f"{settings.company_name} 영업 데이터 시스템",
    page_icon="🏢",
    layout="wide",
    initial_sidebar_state="expanded",
)

init_db()


@st.cache_resource
def get_pipeline():
    return ProcessingPipeline()


def render_sidebar():
    st.sidebar.title("🏢 율재부동산")
    st.sidebar.caption("영업 데이터 자산화 시스템 v1.0")
    st.sidebar.divider()
    page = st.sidebar.radio(
        "메뉴",
        ["📊 대시보드", "📞 통화 업로드", "🔥 핫 리드", "📝 팔로업 관리", "📈 트리거 분석", "👥 고객 관리"],
        label_visibility="collapsed",
    )
    return page


def render_dashboard():
    st.title("📊 영업 현황 대시보드")

    with get_db() as db:
        # 상단 KPI 카드
        col1, col2, col3, col4 = st.columns(4)

        total_calls = db.query(CallRecord).count()
        completed_calls = db.query(CallRecord).filter(CallRecord.status == "completed").count()
        hot_leads = Database.get_hot_leads(db, min_score=settings.min_opportunity_score, limit=100)
        pending_fus = db.query(FollowUp).filter(FollowUp.status == "pending").count()

        col1.metric("총 통화 건수", total_calls, help="전체 처리된 통화 수")
        col2.metric("분석 완료", completed_calls, help="AI 분석이 완료된 통화 수")
        col3.metric("핫 리드", len(hot_leads), delta=f"기준: {settings.min_opportunity_score}점↑")
        col4.metric("대기 팔로업", pending_fus, delta_color="inverse")

        st.divider()

        col_left, col_right = st.columns(2)

        with col_left:
            st.subheader("🎯 의향별 통화 분포")
            analyses = db.query(TriggerWordAnalysis).all()
            if analyses:
                intent_counts = {}
                for a in analyses:
                    intent = a.dominant_intent or "미분류"
                    intent_counts[intent] = intent_counts.get(intent, 0) + 1
                fig = px.pie(
                    values=list(intent_counts.values()),
                    names=list(intent_counts.keys()),
                    color_discrete_sequence=px.colors.qualitative.Set3,
                )
                fig.update_layout(margin=dict(t=0, b=0, l=0, r=0))
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("분석된 통화 데이터가 없습니다.")

        with col_right:
            st.subheader("📈 감성별 분포")
            if analyses:
                sentiment_counts = {}
                for a in analyses:
                    s = a.customer_sentiment or "중립"
                    sentiment_counts[s] = sentiment_counts.get(s, 0) + 1
                sentiment_colors = {
                    "매우긍정": "#2ecc71", "긍정": "#27ae60",
                    "중립": "#95a5a6",
                    "부정": "#e74c3c", "매우부정": "#c0392b",
                }
                fig = go.Figure(go.Bar(
                    x=list(sentiment_counts.keys()),
                    y=list(sentiment_counts.values()),
                    marker_color=[sentiment_colors.get(k, "#3498db") for k in sentiment_counts],
                ))
                fig.update_layout(margin=dict(t=0, b=0, l=0, r=0), xaxis_title="", yaxis_title="건수")
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("분석된 통화 데이터가 없습니다.")

        st.subheader("📋 최근 통화 기록")
        calls = Database.list_call_records(db, limit=10)
        if calls:
            data = []
            for c in calls:
                score = "–"
                intent = "–"
                if c.transcript and c.transcript.trigger_analysis:
                    score = c.transcript.trigger_analysis.opportunity_score
                    intent = c.transcript.trigger_analysis.dominant_intent
                data.append({
                    "ID": c.id,
                    "전화번호": c.phone_number,
                    "담당자": c.agent_name or "–",
                    "통화일시": c.call_date.strftime("%Y-%m-%d %H:%M"),
                    "상태": c.status,
                    "기회점수": score,
                    "주요의향": intent,
                })
            st.dataframe(pd.DataFrame(data), use_container_width=True, hide_index=True)
        else:
            st.info("통화 기록이 없습니다.")


def render_upload():
    st.title("📞 통화 녹음 업로드 및 분석")
    st.caption("통화 녹음 파일을 업로드하면 STT → 트리거 분석 → 인사이트 생성이 자동으로 실행됩니다.")

    with st.form("upload_form"):
        audio_file = st.file_uploader(
            "통화 녹음 파일 선택",
            type=["mp3", "wav", "m4a", "webm", "ogg"],
            help="최대 100MB",
        )
        col1, col2 = st.columns(2)
        phone_number = col1.text_input("고객 전화번호", placeholder="010-1234-5678")
        agent_name = col2.text_input("담당 직원 이름", placeholder="홍길동")
        submitted = st.form_submit_button("🚀 분석 시작", use_container_width=True, type="primary")

    if submitted and audio_file and phone_number:
        pipeline = get_pipeline()
        with st.spinner("AI 분석 중... (STT → 트리거 추출 → 인사이트 생성)"):
            try:
                with get_db() as db:
                    result = pipeline.process_upload(
                        db=db,
                        audio_bytes=audio_file.read(),
                        filename=audio_file.name,
                        phone_number=phone_number,
                        agent_name=agent_name,
                    )

                st.success("분석 완료!")
                m1, m2, m3, m4 = st.columns(4)
                m1.metric("통화 ID", result["call_id"])
                m2.metric("기회 점수", f"{result['opportunity_score']}점")
                m3.metric("주요 의향", result["dominant_intent"])
                m4.metric("자동 팔로업", f"{result['follow_ups_created']}건")

                with get_db() as db:
                    call = Database.get_call_record(db, result["call_id"])
                    if call and call.transcript:
                        with st.expander("📄 트랜스크립트 보기"):
                            st.text_area("", call.transcript.text, height=200, disabled=True)
                        if call.transcript.trigger_analysis:
                            ta = call.transcript.trigger_analysis
                            with st.expander("🎯 트리거 워드 분석"):
                                cols = st.columns(3)
                                cols[0].metric("기회 점수", ta.opportunity_score)
                                cols[1].metric("고객 감성", ta.customer_sentiment)
                                cols[2].metric("긴박도", ta.urgency_level)
                                if ta.found_triggers:
                                    st.write("**발견된 트리거 워드:**")
                                    for cat, words in ta.found_triggers.items():
                                        if words:
                                            st.write(f"- **{cat}**: {', '.join(words)}")
                        if call.transcript.insight:
                            ins = call.transcript.insight
                            with st.expander("💡 영업 인사이트"):
                                st.write("**요약:**", ins.summary)
                                st.write("**거래 성사 확률:**", f"{ins.estimated_deal_probability}%")
                                st.write("**예상 타임라인:**", ins.estimated_deal_timeline)
                                if ins.action_items:
                                    st.write("**액션 플랜:**")
                                    for item in ins.action_items:
                                        priority_icon = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(
                                            item.get("priority", "medium"), "🔵"
                                        )
                                        st.write(
                                            f"{priority_icon} [{item.get('channel')}] "
                                            f"{item.get('action')} (기한: {item.get('deadline')})"
                                        )
                                if ins.follow_up_script:
                                    st.write("**팔로업 스크립트:**")
                                    st.info(ins.follow_up_script)
            except Exception as e:
                st.error(f"처리 중 오류 발생: {e}")
    elif submitted:
        st.warning("파일과 전화번호를 모두 입력해주세요.")


def render_hot_leads():
    st.title("🔥 핫 리드 현황")
    st.caption(f"기회 점수 {settings.min_opportunity_score}점 이상 고객 목록")

    with get_db() as db:
        min_score = st.slider("최소 기회 점수", 0, 100, settings.min_opportunity_score)
        hot_leads = Database.get_hot_leads(db, min_score=min_score, limit=50)

    if not hot_leads:
        st.info("해당 기준의 핫 리드가 없습니다.")
        return

    df = pd.DataFrame(hot_leads)
    df["기회점수_bar"] = df["opportunity_score"]

    st.dataframe(
        df.rename(columns={
            "call_id": "통화ID", "phone_number": "전화번호",
            "customer_name": "고객명", "opportunity_score": "기회점수",
            "dominant_intent": "주요의향", "urgency_level": "긴박도", "call_date": "통화일시",
        }),
        use_container_width=True,
        hide_index=True,
        column_config={
            "기회점수": st.column_config.ProgressColumn("기회점수", min_value=0, max_value=100),
        },
    )

    # 점수 분포
    fig = px.histogram(df, x="opportunity_score", nbins=10, title="기회 점수 분포",
                       color_discrete_sequence=["#e74c3c"])
    fig.update_layout(xaxis_title="기회 점수", yaxis_title="건수", showlegend=False)
    st.plotly_chart(fig, use_container_width=True)


def render_follow_ups():
    st.title("📝 팔로업 관리")

    with get_db() as db:
        pending = Database.list_pending_follow_ups(db, limit=50)

    if not pending:
        st.success("모든 팔로업이 완료되었습니다!")
        return

    priority_order = {"high": 0, "medium": 1, "low": 2}
    priority_label = {"high": "🔴 긴급", "medium": "🟡 보통", "low": "🟢 여유"}
    channel_icon = {"전화": "📞", "문자": "💬", "카카오": "🟡", "방문": "🚶", "이메일": "📧"}

    for fu in sorted(pending, key=lambda x: priority_order.get(x.priority, 9)):
        with st.expander(
            f"{priority_label.get(fu.priority, fu.priority)} | "
            f"{channel_icon.get(fu.channel, '')} {fu.channel} | "
            f"고객ID {fu.customer_id} | "
            f"기한: {fu.due_date.strftime('%m/%d %H:%M') if fu.due_date else '미정'}",
            expanded=fu.priority == "high",
        ):
            st.write(f"**액션:** {fu.action}")
            if fu.script:
                st.write("**스크립트:**")
                st.info(fu.script)

            col1, col2 = st.columns([3, 1])
            notes = col1.text_input("완료 메모", key=f"note_{fu.id}", label_visibility="collapsed",
                                    placeholder="완료 내용 메모 (선택)")
            if col2.button("완료 처리", key=f"complete_{fu.id}", type="primary"):
                with get_db() as db:
                    Database.complete_follow_up(db, fu.id, notes=notes)
                st.success("완료 처리되었습니다!")
                st.rerun()


def render_trigger_analysis():
    st.title("📈 트리거 워드 분석")

    days = st.select_slider("분석 기간", options=[7, 14, 30, 60, 90], value=30)

    with get_db() as db:
        stats = Database.get_trigger_word_stats(db, days=days)

    if not stats:
        st.info(f"최근 {days}일간 분석된 트리거 워드가 없습니다.")
        return

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("🏆 Top 20 트리거 워드")
        top20 = dict(list(stats.items())[:20])
        fig = px.bar(
            x=list(top20.values()),
            y=list(top20.keys()),
            orientation="h",
            color=list(top20.values()),
            color_continuous_scale="Reds",
        )
        fig.update_layout(yaxis={"autorange": "reversed"}, showlegend=False,
                          xaxis_title="언급 횟수", yaxis_title="", coloraxis_showscale=False)
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.subheader("☁️ 워드 클라우드 (빈도 기반)")
        cloud_data = []
        for word, count in list(stats.items())[:30]:
            cloud_data.append({"word": word, "count": count})
        cloud_df = pd.DataFrame(cloud_data)
        fig = px.treemap(cloud_df, path=["word"], values="count",
                         color="count", color_continuous_scale="RdYlGn_r")
        fig.update_layout(margin=dict(t=0, b=0, l=0, r=0))
        st.plotly_chart(fig, use_container_width=True)

    st.subheader("전체 트리거 워드 통계")
    stats_df = pd.DataFrame(list(stats.items()), columns=["트리거 워드", "언급 횟수"])
    st.dataframe(stats_df, use_container_width=True, hide_index=True)


def render_customers():
    st.title("👥 고객 관리")

    with get_db() as db:
        col1, col2 = st.columns(2)
        show_vip = col1.checkbox("VIP 고객만 보기")
        customers = Database.list_customers(db, is_vip=True if show_vip else None, limit=100)

    if not customers:
        st.info("등록된 고객이 없습니다.")
        return

    data = []
    for c in customers:
        call_count = len(c.calls) if c.calls else 0
        data.append({
            "ID": c.id,
            "전화번호": c.phone_number,
            "이름": c.name or "–",
            "예산": c.estimated_budget or "–",
            "선호지역": c.preferred_area or "–",
            "거래유형": c.transaction_type or "–",
            "VIP": "⭐" if c.is_vip else "",
            "통화횟수": call_count,
            "등록일": c.created_at.strftime("%Y-%m-%d"),
        })

    st.dataframe(pd.DataFrame(data), use_container_width=True, hide_index=True)

    st.divider()
    st.subheader("VIP 설정 변경")
    with get_db() as db:
        col1, col2, col3 = st.columns(3)
        customer_id = col1.number_input("고객 ID", min_value=1, step=1)
        is_vip = col2.selectbox("VIP 여부", ["설정", "해제"])
        if col3.button("적용", type="primary"):
            Database.update_customer(db, int(customer_id), is_vip=(is_vip == "설정"))
            st.success(f"고객 ID {customer_id} VIP {is_vip} 완료")
            st.rerun()


def main():
    page = render_sidebar()

    page_map = {
        "📊 대시보드": render_dashboard,
        "📞 통화 업로드": render_upload,
        "🔥 핫 리드": render_hot_leads,
        "📝 팔로업 관리": render_follow_ups,
        "📈 트리거 분석": render_trigger_analysis,
        "👥 고객 관리": render_customers,
    }

    page_map[page]()


if __name__ == "__main__":
    main()
