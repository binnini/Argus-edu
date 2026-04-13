"""Database-backed durable priority jobs for background model work."""

import asyncio
import json
import logging
import socket
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from db import AsyncSessionLocal
from models import GradingResult, Job, Submission
from services.deterministic_grading import AnswerVerdict

logger = logging.getLogger(__name__)

JOB_PRIORITY = {
    "feedback": 50,
    "hallucination": 90,
}


async def enqueue_job(
    job_type: str,
    submission_id: int,
    payload: dict[str, Any] | None = None,
    priority: int | None = None,
) -> int:
    async with AsyncSessionLocal() as db:
        job = Job(
            job_type=job_type,
            priority=priority if priority is not None else JOB_PRIORITY.get(job_type, 100),
            submission_id=submission_id,
            payload=json.dumps(payload or {}, ensure_ascii=False),
        )
        db.add(job)
        await db.commit()
        await db.refresh(job)
        return job.id


class JobWorker:
    def __init__(self, app_state, poll_interval: float = 1.0) -> None:
        self._app_state = app_state
        self._poll_interval = poll_interval
        self._worker_id = f"{socket.gethostname()}:{id(self)}"
        self._stop = asyncio.Event()

    def stop(self) -> None:
        self._stop.set()

    async def run(self) -> None:
        logger.info("job worker started id=%s", self._worker_id)
        while not self._stop.is_set():
            try:
                job = await self._claim_next_job()
                if job is None:
                    await asyncio.wait_for(self._stop.wait(), timeout=self._poll_interval)
                    continue
                await self._run_job(job)
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.exception("job worker loop error: %s", e)
                await asyncio.sleep(self._poll_interval)
        logger.info("job worker stopped id=%s", self._worker_id)

    async def _claim_next_job(self) -> Job | None:
        now = datetime.now(timezone.utc)
        async with AsyncSessionLocal() as db:
            stale_before = now - timedelta(minutes=10)
            stale_result = await db.execute(
                select(Job).where(Job.status == "running", Job.locked_at < stale_before)
            )
            for stale in stale_result.scalars():
                stale.status = "pending" if stale.attempts < stale.max_attempts else "failed"
                stale.locked_at = None
                stale.locked_by = None

            stmt = (
                select(Job)
                .where(Job.status == "pending", Job.run_after <= now)
                .order_by(Job.priority.asc(), Job.created_at.asc())
                .limit(1)
                .with_for_update(skip_locked=True)
            )
            result = await db.execute(stmt)
            job = result.scalar_one_or_none()
            if job is None:
                return None
            job.status = "running"
            job.locked_at = now
            job.locked_by = self._worker_id
            job.attempts += 1
            await db.commit()
            await db.refresh(job)
            return job

    async def _run_job(self, job: Job) -> None:
        try:
            if job.job_type == "feedback":
                await self._handle_feedback(job)
            elif job.job_type == "hallucination":
                await self._handle_hallucination(job)
            else:
                raise ValueError(f"unknown job_type={job.job_type}")
        except Exception as e:
            await self._mark_failed_or_retry(job, e)
            return
        await self._mark_done(job.id)

    async def _handle_feedback(self, job: Job) -> None:
        payload = json.loads(job.payload or "{}")
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(Submission)
                .options(
                    selectinload(Submission.problem),
                    selectinload(Submission.grading_result),
                )
                .where(Submission.id == job.submission_id)
            )
            submission = result.scalar_one()
            problem = submission.problem
            gr = submission.grading_result
            if gr is None:
                raise ValueError(f"grading_result missing submission_id={submission.id}")

            gr.feedback_status = "running"
            await db.commit()

            answer_verdict = AnswerVerdict(
                verdict=payload.get("answer_verdict") or gr.answer_verdict or "uncertain",
                student_values=list(payload.get("student_values") or []),
                answer_values=list(payload.get("answer_values") or []),
                reason=payload.get("verdict_reason") or "저장된 정오 판정입니다.",
            )
            score = int(gr.ai_score)
            max_score = int(problem.rubric.get("total_score", 1))
            problem_data = {
                "content": problem.content,
                "answer": problem.answer,
                "reference_solution": problem.reference_solution,
                "student_answer": submission.student_answer,
            }
            grading_result_id = gr.id

        feedback = await self._app_state.feedback_review_service.generate(
            problem_content=problem_data["content"],
            answer=problem_data["answer"],
            reference_solution=problem_data["reference_solution"],
            student_answer=problem_data["student_answer"],
            answer_verdict=answer_verdict,
            score=score,
            max_score=max_score,
        )

        async with AsyncSessionLocal() as db:
            result = await db.execute(select(GradingResult).where(GradingResult.id == grading_result_id))
            gr = result.scalar_one()
            gr.ai_feedback = json.dumps(feedback.to_feedback_dict(), ensure_ascii=False)
            gr.solution_status = feedback.solution_status
            gr.feedback_status = "done"
            gr.hallucination_status = "pending"
            await db.commit()

        await enqueue_job(
            "hallucination",
            submission_id=job.submission_id,
            payload={"grading_result_id": grading_result_id},
        )

    async def _handle_hallucination(self, job: Job) -> None:
        payload = json.loads(job.payload or "{}")
        grading_result_id = payload.get("grading_result_id")
        hallucination_svc = getattr(self._app_state, "hallucination_svc", None)
        if hallucination_svc is None:
            raise RuntimeError("hallucination service is not configured")
        if grading_result_id is not None and hasattr(hallucination_svc, "run_one"):
            await hallucination_svc.run_one(int(grading_result_id))
        else:
            await hallucination_svc.run_batch(limit=1)

    async def _mark_done(self, job_id: int) -> None:
        async with AsyncSessionLocal() as db:
            job = await db.get(Job, job_id)
            if job:
                job.status = "done"
                job.locked_at = None
                job.locked_by = None
                await db.commit()

    async def _mark_failed_or_retry(self, job: Job, exc: Exception) -> None:
        logger.error("job failed id=%s type=%s: %s", job.id, job.job_type, exc)
        async with AsyncSessionLocal() as db:
            fresh = await db.get(Job, job.id)
            if fresh is None:
                return
            fresh.last_error = str(exc)
            fresh.locked_at = None
            fresh.locked_by = None
            if fresh.attempts >= fresh.max_attempts:
                fresh.status = "failed"
                if fresh.job_type == "feedback":
                    await self._mark_feedback_failed(db, fresh.submission_id)
            else:
                fresh.status = "pending"
                delay = min(60, 2 ** max(0, fresh.attempts - 1))
                fresh.run_after = datetime.now(timezone.utc) + timedelta(seconds=delay)
            await db.commit()

    async def _mark_feedback_failed(self, db, submission_id: int) -> None:
        result = await db.execute(
            select(GradingResult)
            .join(Submission, Submission.id == GradingResult.submission_id)
            .where(Submission.id == submission_id)
        )
        gr = result.scalar_one_or_none()
        if gr:
            gr.feedback_status = "failed"


async def queue_counts() -> dict[str, dict[str, int]]:
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Job.job_type, Job.status, func.count(Job.id)).group_by(Job.job_type, Job.status)
        )
        counts: dict[str, dict[str, int]] = {}
        for job_type, status, count in result.all():
            counts.setdefault(job_type, {})[status] = int(count)
        return counts
