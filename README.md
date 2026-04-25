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

## 라이선스

MIT License
