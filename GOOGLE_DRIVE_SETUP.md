# 구글 드라이브 & 시트 자동화 파이프라인 설정 가이드

이 가이드는 서비스 계정(Service Account)을 사용하여 구글 드라이브 파이프라인을 설정하는 방법을 설명합니다.

## 전체 구조

```
스마트폰 녹음 → 구글 드라이브 자동 동기화 → 파이프라인 감지
                                              ↓
                    ┌─────────────────────────────────────────────┐
                    │  drive_pipeline.py (서버에서 백그라운드 실행)   │
                    │                                             │
                    │  1. 처리 대기(To-Do) 폴더 확인               │
                    │  2. 새 .m4a 파일 다운로드                    │
                    │  3. voice_run.py 분석 실행                  │
                    │  4. 구글 시트에 데이터 추가                   │
                    │  5. 처리 완료(Done) 폴더로 이동               │
                    └─────────────────────────────────────────────┘
```

---

## 1단계: Google Cloud 프로젝트 생성

### 1.1 Google Cloud Console 접속
1. [Google Cloud Console](https://console.cloud.google.com/) 접속
2. 상단의 프로젝트 선택 드롭다운 클릭
3. "새 프로젝트" 클릭
4. 프로젝트 이름 입력 (예: `yuljae-real-estate`)
5. "만들기" 클릭

### 1.2 API 활성화
1. 좌측 메뉴에서 "API 및 서비스" → "라이브러리" 클릭
2. 다음 API를 검색하여 각각 **활성화**:
   - **Google Drive API**
   - **Google Sheets API**

---

## 2단계: 서비스 계정 생성

### 2.1 서비스 계정 만들기
1. 좌측 메뉴 "API 및 서비스" → "사용자 인증 정보" 클릭
2. 상단 "+ 사용자 인증 정보 만들기" → "서비스 계정" 선택
3. 서비스 계정 세부정보 입력:
   - **서비스 계정 이름**: `drive-pipeline` (자유롭게 지정)
   - **서비스 계정 ID**: 자동 생성됨 (예: `drive-pipeline@프로젝트ID.iam.gserviceaccount.com`)
   - **서비스 계정 설명**: `부동산 상담 녹음 자동 처리`
4. "만들기 및 계속" 클릭
5. 역할 선택은 건너뛰기 (구글 드라이브는 폴더 공유로 권한 부여)
6. "완료" 클릭

### 2.2 JSON 키 파일 다운로드
1. 생성된 서비스 계정 이메일 클릭
2. 상단 "키" 탭 클릭
3. "키 추가" → "새 키 만들기" 클릭
4. **JSON** 선택 → "만들기"
5. JSON 파일이 자동 다운로드됨
6. 이 파일을 프로젝트 루트에 `credentials.json`으로 저장

**중요**: 이 파일은 절대 Git에 커밋하지 마세요! (`.gitignore`에 이미 추가되어 있습니다)

---

## 3단계: 구글 드라이브 폴더 설정

### 3.1 폴더 구조 생성
구글 드라이브에서 다음 폴더 구조를 생성하세요:

```
📁 부동산_상담_녹음/
├── 📁 처리대기_To-Do    ← 스마트폰 녹음 자동 동기화 대상
└── 📁 처리완료_Done     ← 분석 완료 파일 보관
```

### 3.2 서비스 계정에 폴더 공유
1. "처리대기_To-Do" 폴더 우클릭 → "공유"
2. 서비스 계정 이메일 입력 (예: `drive-pipeline@프로젝트ID.iam.gserviceaccount.com`)
3. 권한: **편집자** 선택
4. "전송" 클릭
5. "처리완료_Done" 폴더도 동일하게 공유

### 3.3 폴더 ID 확인
폴더 ID는 URL에서 확인할 수 있습니다:

```
https://drive.google.com/drive/folders/1AbCdEfGhIjKlMnOpQrStUvWxYz
                                        └─────────────────────────┘
                                              이 부분이 폴더 ID
```

---

## 4단계: 구글 시트 설정

### 4.1 마스터 관리대장 스프레드시트 생성
1. [Google Sheets](https://sheets.google.com/) 접속
2. "새 스프레드시트" 생성
3. 이름 변경: `부동산_상담_마스터_관리대장`

### 4.2 서비스 계정에 시트 공유
1. 우측 상단 "공유" 클릭
2. 서비스 계정 이메일 입력
3. 권한: **편집자** 선택
4. "전송" 클릭

### 4.3 스프레드시트 ID 확인
스프레드시트 ID는 URL에서 확인할 수 있습니다:

```
https://docs.google.com/spreadsheets/d/1AbCdEfGhIjKlMnOpQrStUvWxYz/edit
                                       └─────────────────────────┘
                                             이 부분이 스프레드시트 ID
```

---

## 5단계: 환경 변수 설정

`.env` 파일을 생성하고 다음 내용을 입력하세요:

```bash
# API Keys
ASSEMBLYAI_API_KEY=your_assemblyai_key
ANTHROPIC_API_KEY=your_anthropic_key

# Google Drive Pipeline
GOOGLE_SERVICE_ACCOUNT_PATH=credentials.json
GOOGLE_DRIVE_TODO_FOLDER_ID=1AbCdEfGhIjKlMnOpQrStUvWxYz  # 처리대기 폴더
GOOGLE_DRIVE_DONE_FOLDER_ID=2BcDeFgHiJkLmNoPqRsTuVwXyZ  # 처리완료 폴더
GOOGLE_SHEETS_SPREADSHEET_ID=3CdEfGhIjKlMnOpQrStUvWxYzA # 스프레드시트
GOOGLE_SHEETS_SHEET_NAME=상담기록
```

---

## 6단계: 실행

### 설치
```bash
pip install -r requirements.txt
```

### 1회 실행 (테스트용)
```bash
python drive_pipeline.py
```

### 주기적 감시 모드 (운영용)
```bash
# 5분마다 확인 (기본값)
python drive_pipeline.py --watch

# 10분마다 확인
python drive_pipeline.py --watch --interval 600
```

### 백그라운드 실행 (Linux 서버)
```bash
# nohup으로 백그라운드 실행
nohup python drive_pipeline.py --watch > pipeline.log 2>&1 &

# 또는 systemd 서비스로 등록 (권장)
```

---

## 7단계: systemd 서비스 등록 (선택사항)

서버에서 안정적으로 운영하려면 systemd 서비스로 등록하세요.

### 서비스 파일 생성
```bash
sudo nano /etc/systemd/system/drive-pipeline.service
```

```ini
[Unit]
Description=Real Estate Consultation Drive Pipeline
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/yuljae-auto-dev
Environment="PATH=/home/ubuntu/.local/bin:/usr/bin"
EnvironmentFile=/home/ubuntu/yuljae-auto-dev/.env
ExecStart=/home/ubuntu/.local/bin/python drive_pipeline.py --watch
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

### 서비스 활성화
```bash
sudo systemctl daemon-reload
sudo systemctl enable drive-pipeline
sudo systemctl start drive-pipeline

# 상태 확인
sudo systemctl status drive-pipeline

# 로그 확인
journalctl -u drive-pipeline -f
```

---

## 문제 해결

### "Permission denied" 오류
- 서비스 계정에 폴더/시트가 올바르게 공유되었는지 확인
- 공유 시 "편집자" 권한인지 확인

### "API not enabled" 오류
- Google Cloud Console에서 Drive API와 Sheets API가 활성화되었는지 확인

### "Invalid credentials" 오류
- `credentials.json` 파일 경로가 올바른지 확인
- JSON 키 파일이 손상되지 않았는지 확인

### 파일이 감지되지 않음
- 처리 대기 폴더 ID가 정확한지 확인
- 파일 확장자가 지원되는 형식인지 확인 (.m4a, .mp3, .wav 등)

---

## 스마트폰 녹음 자동 동기화 설정

### Android (추천: FolderSync)
1. Play Store에서 "FolderSync" 앱 설치
2. Google Drive 계정 연결
3. 폴더 쌍 설정:
   - 로컬: 통화 녹음 폴더 (보통 `/DCIM/CallRecording` 또는 `/Recordings`)
   - 원격: 처리대기_To-Do 폴더
4. 동기화 유형: "로컬에서 원격으로"
5. 자동 동기화 스케줄 설정 (예: 30분마다)

### iPhone
- 아이폰은 통화 녹음이 기본 지원되지 않음
- 외부 녹음 앱 사용 시 해당 앱의 클라우드 동기화 기능 활용

---

## 데이터 출력 형식

파이프라인 실행 후 구글 시트에 다음 컬럼이 자동 생성됩니다:

| 카테고리 | 컬럼 |
|----------|------|
| 기본 | 상담ID, 처리일시, 원본파일, 통화시간, 화자수, 요약 |
| 가격 | 매매가, 전세가, 보증금, 월세, 희망가격, 협상가능여부 |
| 위치 | 구/동, 단지명, 인근역, 역세권여부, 선호/제외지역 |
| 일정 | 희망계약시점, 입주희망일, 긴급도, 계약만료일 |
| 협상 | 필수조건, 희망조건, 거래불가조건, 우려사항 |
| 고객 | 연령대, 가족구성, 현거주지, 의사결정자 |
