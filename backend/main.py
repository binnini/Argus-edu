"""
main.py — FastAPI 엔트리포인트.

lifespan:
  - SBERT + HHEM detector를 서버 시작 시 1회 로드 → app.state에 상주
  - GradingService, FeedbackService, OCRService 인스턴스도 app.state에 보관
"""

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sentence_transformers import SentenceTransformer

from services.hallucination import load_hhem_detector
from services.grading import GradingService
from services.feedback import FeedbackService
from services.ocr import OCRService
from routers import submissions, teacher, feedback, problems

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("ML 모델 로딩 시작...")

    sbert = SentenceTransformer("all-MiniLM-L6-v2")
    app.state.sbert = sbert
    logger.info("SBERT 로딩 완료")

    app.state.hhem = load_hhem_detector(sbert_model=sbert)
    logger.info("HHEM detector 준비 완료")

    app.state.grading_service = GradingService(sbert)
    app.state.feedback_service = FeedbackService(sbert)
    app.state.ocr_service = OCRService()
    logger.info("서비스 인스턴스 초기화 완료. 서버 준비됨.")

    yield

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

# 학생 풀이 이미지 정적 서빙
_data_dir = Path(__file__).parent.parent / "data"
if _data_dir.exists():
    app.mount("/data", StaticFiles(directory=str(_data_dir)), name="data")


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "models": {
            "sbert": hasattr(app.state, "sbert"),
            "hhem": hasattr(app.state, "hhem"),
        },
    }
