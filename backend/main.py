"""
main.py — FastAPI 엔트리포인트.

lifespan:
  - SBERT + HHEM detector를 서버 시작 시 1회 로드 → app.state에 상주
  - GradingService, ExplanationService 인스턴스도 app.state에 보관
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sentence_transformers import SentenceTransformer

from services.hallucination import load_hhem_detector
from services.grading import GradingService
from services.explanation import ExplanationService
from routers import submissions, teacher, feedback

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
    app.state.explanation_service = ExplanationService(sbert)
    logger.info("서비스 인스턴스 초기화 완료. 서버 준비됨.")

    yield

    logger.info("서버 종료.")


app = FastAPI(
    title="Argus — 교육자 HITL 채점 시스템",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(submissions.router)
app.include_router(teacher.router)
app.include_router(feedback.router)


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "models": {
            "sbert": hasattr(app.state, "sbert"),
            "hhem": hasattr(app.state, "hhem"),
        },
    }
