"""
main.py — FastAPI 엔트리포인트.

lifespan:
  - SBERT + HHEM detector를 서버 시작 시 1회 로드 → app.state에 상주
  - GradingService, FeedbackService, OCRService 인스턴스도 app.state에 보관
"""

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from config import settings
from services.embeddings import LocalEmbeddingModel
from services.grading_feedback import CombinedGradingFeedbackService
from services.hallucination_batch import HallucinationBatchService
from services.llm_client import LLMClient
from services.ocr import OCRService
from routers import submissions, teacher, feedback, problems
from routers import groups

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("ML 모델 로딩 시작...")

    # DB 테이블 자동 생성 (개발용)
    from db import engine
    from models.base import Base
    import models.group  # noqa: F401 — 테이블 등록
    import models.homework  # noqa: F401 — 테이블 등록
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("DB 테이블 동기화 완료")

    sbert = LocalEmbeddingModel(settings.embedding_model_name)
    app.state.sbert = sbert
    logger.info("SBERT 로딩 완료")

    # LLM 클라이언트 초기화
    # MLX provider: 무거운 모델을 lifespan에서 1회만 로드
    if settings.llm_provider == "mlx":
        logger.info(f"MLX 모델 로딩 시작: {settings.mlx_model_path}")
        from mlx_lm import load as mlx_load
        mlx_model, mlx_tokenizer = mlx_load(settings.mlx_model_path)
        app.state.mlx_model = mlx_model
        app.state.mlx_tokenizer = mlx_tokenizer
        llm_client = LLMClient(mlx_model=mlx_model, mlx_tokenizer=mlx_tokenizer)
        logger.info("MLX 모델 로딩 완료")
    else:
        llm_client = LLMClient()

    app.state.llm_client = llm_client
    app.state.combined_service = CombinedGradingFeedbackService(sbert, llm_client=llm_client)
    app.state.ocr_service = OCRService()

    # 배치 할루시네이션 검증 스케줄러 (ADR-026)
    hallucination_svc = HallucinationBatchService(llm_client=llm_client)
    app.state.hallucination_svc = hallucination_svc

    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        hallucination_svc.run_batch,
        trigger="interval",
        seconds=settings.hallucination_batch_interval_seconds,
        id="hallucination_batch",
        max_instances=1,        # 이전 배치가 끝나기 전에 중복 실행 방지
        misfire_grace_time=60,
    )
    scheduler.start()
    app.state.scheduler = scheduler
    logger.info(
        f"할루시네이션 배치 스케줄러 시작: {settings.hallucination_batch_interval_seconds}s 간격"
    )
    logger.info("서비스 인스턴스 초기화 완료. 서버 준비됨.")

    yield

    scheduler.shutdown(wait=False)
    logger.info("서버 종료.")


app = FastAPI(
    title="Argus — 교육자 HITL 채점 시스템",
    version="0.2.0",
    lifespan=lifespan,
)

import os

_ALLOWED_ORIGINS = os.getenv(
    "ALLOWED_ORIGINS",
    "http://localhost:5173,http://localhost:80,http://localhost",
).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=_ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(submissions.router)
app.include_router(teacher.router)
app.include_router(feedback.router)
app.include_router(problems.router)
app.include_router(groups.router)

# 학생 풀이 이미지 정적 서빙
_data_dir = Path(__file__).parent.parent / "data"
if _data_dir.exists():
    app.mount("/data", StaticFiles(directory=str(_data_dir)), name="data")

# 업로드 이미지 정적 서빙 (submissions.py가 backend/uploads/ 에 저장)
_uploads_dir = Path(__file__).parent / "uploads"
_uploads_dir.mkdir(exist_ok=True)
app.mount("/uploads", StaticFiles(directory=str(_uploads_dir)), name="uploads")


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "models": {
            "sbert": hasattr(app.state, "sbert"),
            "hhem": True,  # 제거됨 — 하위 호환성 유지
        },
    }
