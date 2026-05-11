# 율재부동산 영업 데이터 자산화 시스템

통화 녹음 기반 고객 상담 데이터를 AI로 분석하여 영업 인사이트(트리거 워드) 도출 및 상담 업무 자동화를 실현하는 통합 시스템.

## 시스템 아키텍처

```
통화 녹음 업로드
       │
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

### 테스트
# 부동산 영업 데이터 자산화 시스템

통화 녹음을 기반으로 고객 상담 데이터를 텍스트화하고, 이를 분석하여 영업 인사이트(트리거 워드) 도출 및 상담 업무 자동화를 실현하는 통합 시스템입니다.

## 주요 기능

### 1. 음성-텍스트 변환 (STT)
- OpenAI Whisper 기반 고품질 한국어 음성 인식
- MP3, WAV, M4A, OGG, FLAC 형식 지원
- 세그먼트별 타임스탬프 및 신뢰도 제공

### 2. 트리거 워드 분석
- **구매의향**: 계약, 매수, 분양, 청약 등
- **긴급성**: 급함, 빨리, 당장, 이사 등
- **예산**: 예산, 대출, 자금 등
- **위치선호**: 역세권, 학군, 교통 등
- **우려사항**: 하자, 소음, 관리비 등
- **경쟁사**: 다른 곳, 비교, 견적 등
- **협상**: 네고, 할인, 조건 등

### 3. 감성 분석
- BERT 기반 한국어 감성 분류
- 긍정/중립/부정 판별
- 대화 흐름별 감성 추이 분석

### 4. 상담 자동화
- 고객 상태 자동 분류 (신규/관심/핫리드/협상중/계약완료)
- 추천 액션 생성 (후속전화, 자료발송, 방문예약 등)
- 상담 요약 자동 생성

## 데이터 저장 구조

```
data/
├── audio/
│   ├── incoming/        # 신규 음성 파일 업로드
│   ├── processing/      # 처리 중
│   └── archived/        # 처리 완료 (날짜별)
├── transcripts/         # 텍스트 변환 결과 (날짜별)
├── analysis/            # 분석 결과 (날짜별)
└── exports/             # 내보내기 파일
```

자세한 내용은 [DATA_STORAGE_SPEC.md](docs/DATA_STORAGE_SPEC.md) 참조

## 설치

```bash
# 의존성 설치
pip install -r requirements.txt

# 환경 설정
cp .env.example .env
# .env 파일 수정

# 서버 실행
python app.py
```

## API 사용법

### 음성 파일 업로드
```bash
curl -X POST "http://localhost:8000/api/v1/audio/upload" \
  -F "file=@recording.mp3"
```

### 전체 처리 (변환 + 분석)
```bash
curl -X POST "http://localhost:8000/api/v1/process" \
  -H "Content-Type: application/json" \
  -d '{
    "file_id": "업로드된_파일_ID",
    "customer_id": "CUST001",
    "customer_name": "홍길동"
  }'
```

### API 문서
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## 프로젝트 구조

```
├── app.py              # 메인 애플리케이션
├── config/             # 설정
│   └── settings.py
├── src/
│   ├── stt/            # 음성-텍스트 변환
│   ├── analysis/       # 트리거 분석, 감성 분석
│   ├── automation/     # 상담 자동화
│   ├── api/            # REST API
│   └── utils/          # 유틸리티
├── tests/              # 테스트
└── docs/               # 문서
```

## 테스트

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
| 웹 API | FastAPI + Uvicorn |
| 데이터베이스 | SQLite + SQLAlchemy 2.0 |
| 대시보드 | Streamlit + Plotly |
| CLI | Typer + Rich |
| 테스트 | pytest |
## 라이선스

MIT License
