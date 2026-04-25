# 데이터 저장 및 음성 파일 관리 명세서

## 1. 개요

부동산 영업 데이터 자산화 시스템의 데이터 저장 구조 및 음성 파일 입출력 위치를 정의합니다.

## 2. 디렉토리 구조

```
data/
├── audio/                      # 음성 파일 저장소
│   ├── incoming/               # 신규 업로드 대기 폴더
│   │   └── {customer_id}_{timestamp}.{ext}
│   ├── processing/             # 처리 중인 파일
│   │   └── {customer_id}_{timestamp}.{ext}
│   └── archived/               # 처리 완료 아카이브
│       └── {YYYY}/{MM}/{DD}/   # 날짜별 정리
│           └── {customer_id}_{timestamp}.{ext}
│
├── transcripts/                # 텍스트 변환 결과
│   └── {YYYY}/{MM}/{DD}/
│       └── {customer_id}_{call_id}.json
│
├── analysis/                   # 분석 결과
│   └── {YYYY}/{MM}/{DD}/
│       └── {customer_id}_{call_id}_analysis.json
│
├── exports/                    # 내보내기 파일
│   └── export_{customer_id}_{timestamp}.json
│
└── temp/                       # 임시 파일 (24시간 후 자동 삭제)
```

## 3. 음성 파일 입력 (Input)

### 3.1 지원 형식
- MP3 (.mp3)
- WAV (.wav)
- M4A (.m4a)
- OGG (.ogg)
- FLAC (.flac)

### 3.2 입력 방법

#### API 업로드
```bash
curl -X POST "http://localhost:8000/api/v1/audio/upload" \
  -F "file=@/path/to/recording.mp3"
```

#### 폴더 직접 복사
```bash
# 음성 파일을 incoming 폴더에 직접 복사
cp /path/to/recording.mp3 ./data/audio/incoming/
```

### 3.3 파일 명명 규칙
- 형식: `{customer_id}_{YYYYMMDD_HHMMSS}.{extension}`
- 예시: `CUST001_20240425_143022.mp3`

## 4. 데이터 출력 (Output)

### 4.1 텍스트 변환 결과 (JSON)
```json
{
  "call_id": "uuid",
  "customer_id": "CUST001",
  "full_text": "전체 변환 텍스트",
  "duration": 180.5,
  "language": "ko",
  "segments": [
    {
      "start": 0.0,
      "end": 5.2,
      "text": "세그먼트 텍스트",
      "confidence": 0.95
    }
  ]
}
```

### 4.2 분석 결과 (JSON)
```json
{
  "call_id": "uuid",
  "customer_id": "CUST001",
  "triggers": [
    {
      "word": "계약",
      "category": "구매의향",
      "weight": 0.9,
      "context": "계약하고 싶습니다"
    }
  ],
  "category_scores": {
    "구매의향": 0.85,
    "긴급성": 0.6,
    "예산": 0.7
  },
  "intent_score": 0.78,
  "urgency_score": 0.65,
  "key_phrases": ["아파트", "전세", "역세권"],
  "sentiment": "긍정",
  "sentiment_confidence": 0.82
}
```

## 5. 저장 경로 설정

### 5.1 환경 변수 설정 (.env)
```env
# 기본 데이터 경로
DATA_BASE_PATH=./data

# 개별 경로 설정 (선택사항)
AUDIO_INCOMING_PATH=./data/audio/incoming
AUDIO_ARCHIVED_PATH=./data/audio/archived
TRANSCRIPT_PATH=./data/transcripts
ANALYSIS_PATH=./data/analysis
```

### 5.2 코드에서 설정
```python
from src.utils import StorageConfig, FileStorageManager

# 기본 경로 사용
storage = FileStorageManager()

# 사용자 정의 경로
config = StorageConfig(base_path="/custom/path/data")
storage = FileStorageManager(config)
```

## 6. 파일 처리 흐름

```
1. 음성 파일 업로드
   └── incoming/ 폴더에 저장

2. 처리 시작
   └── processing/ 폴더로 이동

3. STT 변환
   └── transcripts/{날짜}/ 에 결과 저장

4. 분석 수행
   └── analysis/{날짜}/ 에 결과 저장

5. 처리 완료
   └── archived/{날짜}/ 로 음성 파일 이동
```

## 7. 보관 정책

| 데이터 유형 | 보관 기간 | 위치 |
|------------|----------|------|
| 원본 음성 파일 | 1년 | archived/ |
| 텍스트 변환 | 영구 | transcripts/ |
| 분석 결과 | 영구 | analysis/ |
| 임시 파일 | 24시간 | temp/ |

## 8. 백업 권장 사항

- **일일 백업**: transcripts/, analysis/
- **주간 백업**: archived/ (음성 파일)
- **백업 방법**: rsync, AWS S3, Google Cloud Storage 등

## 9. 외부 연동 (향후 확장)

### 9.1 클라우드 스토리지
- AWS S3
- Google Cloud Storage
- Azure Blob Storage

### 9.2 녹음 시스템 연동
- PBX 시스템 (Asterisk, FreeSWITCH)
- 클라우드 콜센터 (Amazon Connect, Twilio)
- CRM 시스템 (Salesforce, HubSpot)

## 10. 보안 고려사항

- 고객 개인정보 포함 파일은 암호화 저장 권장
- 접근 권한 관리 (RBAC)
- 감사 로그 기록
- GDPR/개인정보보호법 준수
