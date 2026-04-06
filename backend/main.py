"""
main.py — FastAPI 엔트리포인트.

lifespan:
  - HHEM + SBERT를 서버 시작 시 1회 로드 → app.state에 상주
  - 요청마다 로드하면 OOM 위험 (backend/CLAUDE.md 참조)
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sentence_transformers import SentenceTransformer

from services.hallucination import load_hhem_detector
from services.grading import GradingService
from services.explanation import ExplanationService

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """서버 시작 시 ML 모델 로드, 종료 시 정리."""
    logger.info("ML 모델 로딩 시작...")

    # SBERT (공유 인스턴스 — grading, explanation, hallucination 모두 사용)
    sbert = SentenceTransformer("all-MiniLM-L6-v2")
    app.state.sbert = sbert
    logger.info("SBERT 로딩 완료")

    # HHEM — HF Inference API 또는 SBERT fallback
    app.state.hhem = load_hhem_detector(sbert_model=sbert)
    logger.info("HHEM 탐지기 준비 완료")

    # 서비스 인스턴스 (의존성 주입 편의를 위해 app.state에 보관)
    app.state.grading_service = GradingService(sbert)
    app.state.explanation_service = ExplanationService(sbert)

    logger.info("모든 ML 모델 로딩 완료. 서버 준비됨.")
    yield

    logger.info("서버 종료. 리소스 정리 완료.")


app = FastAPI(
    title="Argus — 교육자 HITL 채점 시스템",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # Vite 개발 서버
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health():
    """서버 + ML 모델 상태 확인."""
    return {
        "status": "ok",
        "models": {
            "sbert": hasattr(app.state, "sbert"),
            "hhem": hasattr(app.state, "hhem"),
        },
    }
