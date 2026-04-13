"""Student submission grading pipeline orchestration."""

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from db import AsyncSessionLocal
from models import GradingResult, Submission, TeacherQueue
from services.deterministic_grading import judge_final_answer
from services.job_queue import enqueue_job
from services.trust_gate import calculate_trust

logger = logging.getLogger(__name__)


@dataclass
class PipelineInput:
    problem_content: str
    answer: str
    reference_solution: str
    rubric: dict[str, Any]
    student_answer: str


async def run_grading_pipeline(
    submission_id: int,
    app_state,
    image_bytes: bytes | None = None,
    image_content_type: str | None = None,
) -> None:
    """Deterministic grading pipeline; feedback runs through durable jobs."""
    try:
        pipeline_input = await _prepare_input(
            submission_id=submission_id,
            app_state=app_state,
            image_bytes=image_bytes,
            image_content_type=image_content_type,
        )
        await _persist_deterministic_output(submission_id, pipeline_input)
        logger.info(
            f"채점 완료 submission_id={submission_id} "
            f"answer={pipeline_input.answer}"
        )
    except Exception as e:
        logger.error(f"채점 파이프라인 오류 submission_id={submission_id}: {e}")
        await _mark_submission_error(submission_id)


async def _prepare_input(
    submission_id: int,
    app_state,
    image_bytes: bytes | None,
    image_content_type: str | None,
) -> PipelineInput:
    """Load submission/problem and run OCR before releasing the DB session."""
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Submission)
            .options(selectinload(Submission.problem))
            .where(Submission.id == submission_id)
        )
        submission = result.scalar_one()
        problem = submission.problem
        student_answer = submission.student_answer

        if submission.input_type == "image" and image_bytes:
            ocr_svc = app_state.ocr_service
            ocr_text = await ocr_svc.recognize(
                image_bytes, image_content_type or "image/jpeg"
            )
            existing_prefix = submission.student_answer or ""
            student_answer = (
                existing_prefix + "[풀이 과정]\n" + ocr_text
                if existing_prefix
                else ocr_text
            )
            submission.student_answer = student_answer
            submission.ocr_raw_text = ocr_text
            await db.commit()

        return PipelineInput(
            problem_content=problem.content,
            answer=problem.answer,
            reference_solution=problem.reference_solution,
            rubric=problem.rubric,
            student_answer=student_answer,
        )


async def _persist_deterministic_output(submission_id: int, pipeline_input: PipelineInput) -> None:
    """Persist deterministic pass/fail score and enqueue feedback generation."""
    total_score = int(pipeline_input.rubric.get("total_score", 1))
    answer_verdict = judge_final_answer(
        student_answer=pipeline_input.student_answer,
        problem_answer=pipeline_input.answer,
    )
    ai_score = total_score if answer_verdict.is_correct else 0
    trust = calculate_trust(
        ai_score=ai_score,
        total_score=total_score,
    )

    placeholder_feedback = {
        "solution_status": "pending",
        "has_mistakes": False,
        "student_mistakes": [],
        "correct_approach": [],
        "key_concept": "",
    }
    grading_steps = [{
        "step": 1,
        "earned": ai_score,
        "max": total_score,
        "reason": answer_verdict.reason,
    }]

    async with AsyncSessionLocal() as db:
        grading_record = GradingResult(
            submission_id=submission_id,
            ai_score=ai_score,
            ai_feedback=json.dumps(placeholder_feedback, ensure_ascii=False),
            grading_steps=json.dumps(grading_steps, ensure_ascii=False),
            feedback_status="pending",
            solution_status=None,
            answer_verdict=answer_verdict.verdict,
            sbert_similarity=0.0,   # SBERT 제거 — 컬럼 유지용 기본값
            trust_score=0.0,        # hallucination_batch 완료 후 갱신
            trust_level="low",      # hallucination_batch 완료 후 갱신
            hallucination_status="pending",
        )
        db.add(grading_record)

        now = datetime.now(timezone.utc)
        if trust.auto_approve:
            # 만점·고신뢰도 → 자동 승인: 큐에 action='approve' 사전 설정
            queue_record = TeacherQueue(
                submission_id=submission_id,
                queue_type=trust.queue_type,
                sla_deadline=trust.sla_deadline,
                action="approve",
                reviewed_at=now,
            )
            final_status = "approved"
            logger.info(f"자동 승인 submission_id={submission_id} score={ai_score}/{total_score}")
        else:
            # 오답·저신뢰도 → 교사 검토 대기
            queue_record = TeacherQueue(
                submission_id=submission_id,
                queue_type=trust.queue_type,
                sla_deadline=trust.sla_deadline,
            )
            final_status = "graded"

        db.add(queue_record)

        result = await db.execute(select(Submission).where(Submission.id == submission_id))
        submission = result.scalar_one()
        submission.status = final_status
        await db.commit()

    await enqueue_job(
        "feedback",
        submission_id=submission_id,
        payload={
            "answer_verdict": answer_verdict.verdict,
            "student_values": answer_verdict.student_values,
            "answer_values": answer_verdict.answer_values,
            "verdict_reason": answer_verdict.reason,
        },
    )

async def _mark_submission_error(submission_id: int) -> None:
    """Mark a submission as errored without raising secondary failures."""
    try:
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(Submission).where(Submission.id == submission_id)
            )
            sub = result.scalar_one_or_none()
            if sub:
                sub.status = "error"
                await db.commit()
    except Exception:
        pass
