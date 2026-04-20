"""
main.py — FastAPI 엔트리포인트.

lifespan:
  - SBERT + HHEM detector를 서버 시작 시 1회 로드 → app.state에 상주
  - GradingService, FeedbackService, OCRService 인스턴스도 app.state에 보관
"""

import asyncio
import logging
import os
import subprocess
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from config import settings
from services.grading_feedback import CombinedGradingFeedbackService
from services.feedback_generation import FeedbackReviewService
from services.hallucination_batch import HallucinationBatchService
from services.job_queue import JobWorker, queue_counts
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
    logger.info("서비스 초기화 시작...")

    # DB 테이블 자동 생성 (개발용)
    from db import engine
    from models.base import Base
    import models.group  # noqa: F401 — 테이블 등록
    import models.homework  # noqa: F401 — 테이블 등록
    import models.job  # noqa: F401 — 테이블 등록
    import models.student  # noqa: F401 — 테이블 등록
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("DB 테이블 동기화 완료")

    # LLM 클라이언트 초기화
    # MLX provider는 첫 요청 시 모델을 지연 로딩한다.
    llm_client = LLMClient()

    app.state.llm_client = llm_client
    app.state.combined_service = CombinedGradingFeedbackService(llm_client=llm_client)
    app.state.feedback_review_service = FeedbackReviewService(llm_client=llm_client)
    app.state.ocr_service = OCRService()

    hallucination_svc = HallucinationBatchService(llm_client=llm_client)
    app.state.hallucination_svc = hallucination_svc

    job_worker = JobWorker(app.state)
    app.state.job_worker = job_worker
    app.state.job_worker_task = asyncio.create_task(job_worker.run())
    logger.info("durable job worker 시작")
    logger.info("서비스 인스턴스 초기화 완료. 서버 준비됨.")

    yield

    job_worker.stop()
    app.state.job_worker_task.cancel()
    try:
        await app.state.job_worker_task
    except asyncio.CancelledError:
        pass
    try:
        await app.state.llm_client.close()
    except Exception:
        logger.exception("LLM 클라이언트 종료 중 오류")
    try:
        await app.state.ocr_service.close()
    except Exception:
        logger.exception("OCR 서비스 종료 중 오류")
    logger.info("서버 종료.")


app = FastAPI(
    title="Argus — 교육자 HITL 채점 시스템",
    version="0.2.0",
    lifespan=lifespan,
)

_ALLOWED_ORIGINS = [
    origin.strip()
    for origin in settings.allowed_origins.split(",")
    if origin.strip()
]

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
    main_memory_mb = None
    children_memory_mb = None
    total_memory_mb = None
    child_processes = 0

    try:
        pid = os.getpid()
        rss_kb = subprocess.check_output(
            ["ps", "-o", "rss=", "-p", str(os.getpid())],
            text=True,
            timeout=1,
        ).strip()
        main_memory_mb = round(int(rss_kb) / 1024, 2) if rss_kb else None

        rows = subprocess.check_output(
            ["ps", "-axo", "pid=,ppid=,rss=,comm="],
            text=True,
            timeout=1,
        ).splitlines()
        child_rss_kb = 0
        for row in rows:
            parts = row.strip().split()
            if len(parts) < 4:
                continue
            pid_text, ppid_text, rss_text, comm = parts[0], parts[1], parts[2], parts[3]
            if int(ppid_text) == pid and comm != "ps" and int(pid_text) != pid:
                child_processes += 1
                child_rss_kb += int(rss_text)
        children_memory_mb = round(child_rss_kb / 1024, 2)
        if main_memory_mb is not None:
            total_memory_mb = round(main_memory_mb + children_memory_mb, 2)
    except Exception:
        main_memory_mb = None
        children_memory_mb = None
        total_memory_mb = None
        child_processes = 0

    try:
        queues = await queue_counts()
    except Exception:
        queues = {}

    return {
        "status": "ok",
        # Backward compatibility: keep previous field name for main process RSS.
        "memory_mb": main_memory_mb,
        "memory_children_mb": children_memory_mb,
        "memory_total_mb": total_memory_mb,
        "child_processes": child_processes,
        "queues": queues,
    }
