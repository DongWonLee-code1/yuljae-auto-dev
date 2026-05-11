# 율재부동산 영업 데이터 자산화 시스템

통화 녹음 기반 고객 상담 데이터를 AI로 분석하여 영업 인사이트(트리거 워드) 도출 및 상담 업무 자동화를 실현하는 통합 시스템.

## 시스템 아키텍처

```
통화 녹음 업로드 ◀──── Slack 채널 파일 업로드
       │                (자동 감지)
       ▼
┌─────────────────┐
│  STT 변환       │  OpenAI Whisper API (한국어 최적화)
│  transcription/ │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  트리거 워드    │  Claude Opus 4.7 + Prompt Caching
│  분석           │  9개 카테고리 분류 (매수/매도/투자/전세 등)
│  analysis/      │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  영업 인사이트  │  Claude Opus 4.7
│  생성           │  액션 플랜 + 팔로업 스크립트 자동 생성
└────────┬────────┘
         │
         ▼
┌─────────────────┐     ┌──────────────────┐
│  데이터베이스   │────▶│  자동 팔로업 등록  │
│  SQLite/        │     │  (기회점수 60↑)    │
│  SQLAlchemy     │     └──────────────────┘
└────────┬────────┘
         │
    ┌────┴────┐
    ▼         ▼
┌────────┐ ┌─────────────┐
│FastAPI │ │  Streamlit  │
│REST API│ │  대시보드   │
└────────┘ └─────────────┘
```

## 주요 기능

### 1. 통화 녹음 자동 분석 파이프라인
- MP3, WAV, M4A, WebM, OGG 형식 지원
- OpenAI Whisper를 통한 고정밀 한국어 STT
- 전체 파이프라인 자동 실행 (업로드 1회로 완전 자동화)

### 2. 트리거 워드 추출 (9개 카테고리)
| 카테고리 | 주요 트리거 워드 |
|---------|----------------|
| 매수의향 | 사고 싶다, 급매, 언제 보러, 시세가 어떻게 |
| 매도의향 | 팔고 싶다, 얼마에 팔 수 있나요, 처분 |
| 투자관심 | 갭투자, 재건축, 수익률, GTX, 호재 |
| 계약임박 | 계약금, 잔금, 입주, 특약, 등기 |
| 자금조달 | 대출, DSR, LTV, 주담대, 금리 |
| 전세임차 | 전세금, 보증금, 확정일자, 계약갱신청구권 |
| 월세임차 | 월세, 월 임대료, 보증금 낮게 |
| 학군교통 | 학군, 초등학교 배정, 역세권, 강남까지 |
| 긍정신호 | 마음에 들어요, 내일 봐도 될까요, 가족이랑 상의하고 |

### 3. AI 영업 인사이트
- 고객 프로필 자동 추출 (예산, 선호지역, 거래유형)
- 거래 성사 확률 및 예상 타임라인
- 우선순위별 액션 플랜 (채널: 전화/문자/카카오/방문/이메일)
- 팔로업 스크립트 자동 생성
- 리스크 요인 식별

### 4. 핫 리드 자동 분류
- 기회 점수 기반 우선순위 정렬 (기본값: 60점 이상)
- VIP 고객 관리
- 팔로업 자동 등록 (기회 점수 60점 이상 시)

### 5. Streamlit 대시보드
- 영업 현황 KPI (총 통화, 핫 리드, 대기 팔로업)
- 의향별/감성별 분포 차트
- 트리거 워드 빈도 분석 (워드 트리맵, 바 차트)
- 팔로업 우선순위 관리 (인앱 완료 처리)
- 고객 관리 및 VIP 설정

## 빠른 시작

### 설치
```bash
pip install -r requirements.txt
cp .env.example .env
# .env 파일에 API 키 입력
```

### 환경 변수 설정
```env
ANTHROPIC_API_KEY=your_anthropic_api_key
OPENAI_API_KEY=your_openai_api_key
```

### 실행

**API 서버**
```bash
python run.py api
# http://localhost:8000/docs 에서 API 문서 확인
```

**대시보드**
```bash
python run.py dashboard
# http://localhost:8501 에서 대시보드 확인
```

**단일 파일 분석**
```bash
python run.py analyze recording.mp3 010-1234-5678 --agent-name 홍길동
```

**배치 처리**
```bash
python run.py batch ./recordings/ --agent-name 홍길동
```

**Slack 봇 실행**
```bash
python slack_bot.py
```

## Slack App 설정 가이드

Slack 채널에 오디오 파일이 업로드되면 자동으로 분석하는 봇을 설정하는 방법입니다.

### 1. Slack App 생성

1. [Slack API](https://api.slack.com/apps) 페이지에서 **Create New App** 클릭
2. **From scratch** 선택
3. App Name: `율재 분석봇` (또는 원하는 이름)
4. Workspace 선택 후 **Create App**

### 2. Socket Mode 활성화

Socket Mode를 사용하면 공개 URL 없이도 이벤트를 수신할 수 있습니다.

1. 좌측 메뉴에서 **Socket Mode** 클릭
2. **Enable Socket Mode** 토글 ON
3. App-Level Token 생성:
   - Token Name: `socket-mode-token`
   - Scope: `connections:write` 추가
   - **Generate** 클릭
4. 생성된 `xapp-...` 토큰을 `.env` 파일의 `SLACK_APP_TOKEN`에 저장

### 3. OAuth & Permissions 설정

1. 좌측 메뉴에서 **OAuth & Permissions** 클릭
2. **Bot Token Scopes**에 다음 권한 추가:

| Scope | 설명 |
|-------|------|
| `channels:history` | 공개 채널 메시지 읽기 |
| `channels:read` | 공개 채널 목록 조회 |
| `chat:write` | 메시지 전송 |
| `files:read` | 파일 정보 읽기 (다운로드용) |
| `files:write` | 파일 업로드 (CSV 결과 첨부용) |
| `groups:history` | 비공개 채널 메시지 읽기 (선택) |
| `groups:read` | 비공개 채널 목록 조회 (선택) |

3. 페이지 상단 **Install to Workspace** 클릭
4. 권한 허용 후 생성된 `xoxb-...` 토큰을 `.env` 파일의 `SLACK_BOT_TOKEN`에 저장

### 4. Event Subscriptions 설정

1. 좌측 메뉴에서 **Event Subscriptions** 클릭
2. **Enable Events** 토글 ON
3. **Subscribe to bot events**에 다음 이벤트 추가:

| Event | 설명 |
|-------|------|
| `file_shared` | 파일 업로드 감지 (핵심 이벤트) |
| `message.channels` | 공개 채널 메시지 (선택) |
| `message.groups` | 비공개 채널 메시지 (선택) |

4. **Save Changes** 클릭

### 5. Signing Secret 확인

1. 좌측 메뉴에서 **Basic Information** 클릭
2. **App Credentials** 섹션에서 **Signing Secret** 복사
3. `.env` 파일의 `SLACK_SIGNING_SECRET`에 저장

### 6. 봇을 채널에 추가

1. Slack 워크스페이스에서 분석할 채널 열기
2. 채널 이름 클릭 → **통합** 탭
3. **앱 추가** 클릭 → 생성한 앱 추가

### 7. 환경 변수 최종 확인

```env
# .env 파일
SLACK_BOT_TOKEN=xoxb-your-bot-user-oauth-token
SLACK_APP_TOKEN=xapp-your-app-level-token
SLACK_SIGNING_SECRET=your-signing-secret
```

### 8. 봇 실행 및 테스트

```bash
# 봇 실행
python slack_bot.py

# 출력 예시:
# 2024-01-15 10:30:00 [INFO] slack_bot: Slack 봇 시작 (Socket Mode)
# 2024-01-15 10:30:00 [INFO] slack_bot: 지원 오디오 형식: .m4a, .mp3, .wav, ...
```

테스트:
1. 봇이 추가된 채널에 `.m4a` 또는 `.mp3` 파일 업로드
2. 봇이 자동으로 "분석을 시작합니다..." 메시지 전송
3. 1-2분 후 분석 결과가 스레드에 포맷팅된 메시지 + CSV 파일로 전송됨

### 작동 흐름

```
┌─────────────────────────────────────────────────────────────────┐
│  Slack 채널                                                      │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  👤 사용자: [consultation_20240115.m4a 업로드]            │    │
│  │                                                          │    │
│  │  └─ 🤖 봇: 🎙️ 분석을 시작합니다...                        │    │
│  │                                                          │    │
│  │  └─ 🤖 봇: 📊 통화 분석 완료                              │    │
│  │           📝 요약: 서초동 20억대 매물 관심 고객...         │    │
│  │           🔥 기회 점수: 85/100                            │    │
│  │           ...                                             │    │
│  │                                                          │    │
│  │  └─ 🤖 봇: [분석결과_consultation_20240115_42.csv 첨부]   │    │
│  └─────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────┘
```

### 테스트
```bash
pytest tests/ -v
```

## API 엔드포인트

| 메서드 | 경로 | 설명 |
|--------|------|------|
| POST | `/calls/upload` | 통화 녹음 업로드 및 분석 |
| GET | `/calls` | 통화 기록 목록 |
| GET | `/calls/{id}/transcript` | 트랜스크립트 조회 |
| GET | `/calls/{id}/triggers` | 트리거 분석 결과 |
| GET | `/calls/{id}/insight` | 영업 인사이트 |
| GET | `/analytics/hot-leads` | 핫 리드 목록 |
| GET | `/analytics/trigger-stats` | 트리거 워드 통계 |
| GET | `/analytics/weekly-report` | 주간 영업 리포트 |
| GET | `/follow-ups/pending` | 대기 팔로업 목록 |
| POST | `/follow-ups` | 팔로업 생성 |

## 프로젝트 구조

```
yuljae-auto-dev/
├── run.py                    # CLI 진입점
├── slack_bot.py              # Slack 자동화 봇 (Socket Mode)
├── config.py                 # 환경 설정
├── requirements.txt
├── transcription/
│   └── processor.py          # STT 처리 (Whisper API)
├── analysis/
│   ├── trigger_words.py      # 트리거 워드 추출 (Claude)
│   └── insights.py           # 영업 인사이트 생성 (Claude)
├── storage/
│   ├── models.py             # SQLAlchemy ORM 모델
│   └── database.py           # DB CRUD 작업
├── api/
│   ├── app.py                # FastAPI 애플리케이션
│   └── schemas.py            # Pydantic 스키마
├── automation/
│   └── pipeline.py           # 자동화 파이프라인
├── dashboard/
│   └── app.py                # Streamlit 대시보드
└── tests/
    └── test_pipeline.py      # 단위 테스트 (14개)
```

## 기술 스택

| 분야 | 기술 |
|------|------|
| STT | OpenAI Whisper API |
| AI 분석 | Anthropic Claude Opus 4.7 (Prompt Caching) |
| Slack 연동 | slack-bolt (Socket Mode) |
| 웹 API | FastAPI + Uvicorn |
| 데이터베이스 | SQLite + SQLAlchemy 2.0 |
| 대시보드 | Streamlit + Plotly |
| CLI | Typer + Rich |
| 테스트 | pytest |
