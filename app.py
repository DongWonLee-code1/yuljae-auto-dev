"""부동산 영업 데이터 자산화 시스템 - 메인 애플리케이션"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from src.api import router
from config.settings import settings

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="""
    ## 부동산 영업 데이터 자산화 시스템

    통화 녹음을 기반으로 고객 상담 데이터를 텍스트화하고,
    이를 분석하여 영업 인사이트(트리거 워드) 도출 및 상담 업무 자동화를 실현합니다.

    ### 주요 기능
    - **음성-텍스트 변환 (STT)**: 통화 녹음 파일을 텍스트로 변환
    - **트리거 워드 분석**: 구매의향, 긴급성, 예산 등 핵심 키워드 추출
    - **감성 분석**: 고객 감정 상태 파악
    - **상담 자동화**: 고객 프로필 관리 및 추천 액션 생성

    ### 데이터 저장 구조
    ```
    data/
    ├── audio/incoming/     # 신규 음성 파일 업로드
    ├── audio/processing/   # 처리 중인 파일
    ├── audio/archived/     # 처리 완료 아카이브
    ├── transcripts/        # 텍스트 변환 결과
    ├── analysis/           # 분석 결과
    └── exports/            # 내보내기 파일
    ```
    """,
    docs_url="/docs",
    redoc_url="/redoc"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api/v1", tags=["부동산 영업 데이터"])


@app.get("/")
async def root():
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "status": "running",
        "docs": "/docs"
    }


@app.get("/health")
async def health_check():
    return {"status": "healthy"}


if __name__ == "__main__":
    uvicorn.run(
        "app:app",
        host=settings.API_HOST,
        port=settings.API_PORT,
        reload=settings.DEBUG
    )
