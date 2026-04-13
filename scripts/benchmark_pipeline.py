#!/usr/bin/env python3
"""Benchmark Argus deterministic grading and queued feedback pipeline.

Examples:
    python scripts/benchmark_pipeline.py --users 1 --wait-feedback --output tests/benchmark_pipeline_smoke.csv
    python scripts/benchmark_pipeline.py --users 1,3,5,10 --wait-feedback
    python scripts/benchmark_pipeline.py --users 1,3,5 --wait-hallucination --problem-count 5
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import statistics
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import requests
from requests import RequestException

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))

from sqlalchemy import select  # noqa: E402

from db import AsyncSessionLocal  # noqa: E402
from models import GradingResult, Job, Submission  # noqa: E402

DEFAULT_BASE_URL = "http://localhost:8000"
TERMINAL_STATUSES = {"graded", "approved", "rejected", "error"}
GRADING_TARGET_S = 1.0
FEEDBACK_TARGET_S = 30.0


@dataclass
class BenchmarkRow:
    scenario: str
    n_users: int
    problem_id: int | None
    submission_id: int | None
    submit_latency_s: float | None
    grading_latency_s: float | None
    feedback_total_latency_s: float | None
    e2e_feedback_latency_s: float | None
    hallucination_latency_s: float | None
    e2e_hallucination_latency_s: float | None
    final_status: str | None
    feedback_status: str | None
    hallucination_status: str | None
    score: int | None
    max_score: int | None
    memory_start_mb: float | None
    memory_end_mb: float | None
    feedback_pending_max: int
    feedback_running_max: int
    hallucination_pending_max: int
    error: str


def now_iso() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def parse_server_dt(raw: str | None) -> datetime | None:
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None


def elapsed_s(start: datetime | None, end: datetime | None) -> float | None:
    if start is None or end is None:
        return None
    return (end - start).total_seconds()


def get_health(base_url: str) -> dict[str, Any]:
    resp = requests.get(f"{base_url}/health", timeout=15)
    resp.raise_for_status()
    return resp.json()


def get_problems(base_url: str, limit: int) -> list[dict[str, Any]]:
    resp = requests.get(f"{base_url}/api/v1/problems?page=1&page_size={limit}", timeout=10)
    resp.raise_for_status()
    problems = resp.json().get("problems", [])
    if not problems:
        raise RuntimeError("No problems available in DB")
    return problems


def submit_answer(base_url: str, problem_id: int, idx: int) -> tuple[int, float]:
    t0 = time.perf_counter()
    resp = requests.post(
        f"{base_url}/api/v1/submissions",
        json={
            "problem_id": problem_id,
            "student_answer": "풀이 과정: 정답을 계산했습니다.",
            "final_answer": "__benchmark_wrong_answer_999999__",
            "student_name": f"bench_{idx}",
            "student_id": f"b{int(time.time()) % 1000000:06d}{idx:02d}",
        },
        timeout=10,
    )
    elapsed = time.perf_counter() - t0
    if resp.status_code != 202:
        raise RuntimeError(f"submit failed status={resp.status_code} body={resp.text[:300]}")
    return int(resp.json()["submission_id"]), elapsed


def get_submission(base_url: str, submission_id: int) -> dict[str, Any]:
    resp = requests.get(f"{base_url}/api/v1/submissions/{submission_id}", timeout=15)
    resp.raise_for_status()
    return resp.json()


def queue_metric(health: dict[str, Any], job_type: str, status: str) -> int:
    return int(health.get("queues", {}).get(job_type, {}).get(status, 0) or 0)


async def reset_running_jobs() -> int:
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Job).where(Job.status == "running"))
        jobs = list(result.scalars())
        for job in jobs:
            job.status = "pending" if job.attempts < job.max_attempts else "failed"
            job.locked_at = None
            job.locked_by = None

            gr_result = await db.execute(
                select(GradingResult)
                .join(Submission, Submission.id == GradingResult.submission_id)
                .where(Submission.id == job.submission_id)
            )
            gr = gr_result.scalar_one_or_none()
            if gr is None:
                continue
            if job.job_type == "feedback":
                gr.feedback_status = "pending" if job.status == "pending" else "failed"
            elif job.job_type == "hallucination":
                gr.hallucination_status = "pending" if job.status == "pending" else "failed"
        await db.commit()
        return len(jobs)


def wait_submission(
    base_url: str,
    submission_id: int,
    wait_feedback: bool,
    wait_hallucination: bool,
    timeout_s: float,
) -> tuple[dict[str, Any], dict[str, int], str]:
    deadline = time.perf_counter() + timeout_s
    poll_interval_s = 1.0
    health_sample_interval_s = 3.0
    next_health_sample_at = 0.0
    transient_errors = 0
    last_transient_error = ""
    backlog_max = {
        "feedback_pending": 0,
        "feedback_running": 0,
        "hallucination_pending": 0,
    }

    last_data: dict[str, Any] = {}
    while time.perf_counter() < deadline:
        try:
            last_data = get_submission(base_url, submission_id)

            now = time.perf_counter()
            if now >= next_health_sample_at:
                try:
                    health = get_health(base_url)
                    backlog_max["feedback_pending"] = max(
                        backlog_max["feedback_pending"], queue_metric(health, "feedback", "pending")
                    )
                    backlog_max["feedback_running"] = max(
                        backlog_max["feedback_running"], queue_metric(health, "feedback", "running")
                    )
                    backlog_max["hallucination_pending"] = max(
                        backlog_max["hallucination_pending"], queue_metric(health, "hallucination", "pending")
                    )
                except RequestException as exc:
                    transient_errors += 1
                    last_transient_error = str(exc)
                next_health_sample_at = now + health_sample_interval_s

            if last_data.get("status") in TERMINAL_STATUSES and not wait_feedback and not wait_hallucination:
                return last_data, backlog_max, ""
            if wait_feedback and last_data.get("feedback_status") == "done":
                if not wait_hallucination:
                    return last_data, backlog_max, ""
            if wait_hallucination:
                if last_data.get("hallucination_status") in ("done", "failed"):
                    return last_data, backlog_max, ""
        except RequestException as exc:
            transient_errors += 1
            last_transient_error = str(exc)
        except Exception as exc:
            return last_data, backlog_max, str(exc)
        time.sleep(poll_interval_s)

    timeout_detail = "timeout"
    if transient_errors:
        timeout_detail = (
            f"timeout (transient_request_errors={transient_errors}, "
            f"last_error={last_transient_error[:200]})"
        )
    return last_data, backlog_max, timeout_detail


def run_scenario(
    base_url: str,
    n_users: int,
    problem_ids: list[int],
    wait_feedback: bool,
    wait_hallucination: bool,
    timeout_s: float,
) -> list[BenchmarkRow]:
    memory_start = get_health(base_url).get("memory_mb")
    scenario = f"users_{n_users}_problems_{len(problem_ids)}"

    submitted: list[tuple[int, int, int, float]] = []
    rows: list[BenchmarkRow] = []

    with ThreadPoolExecutor(max_workers=n_users) as pool:
        futures = {}
        for i in range(n_users):
            problem_id = problem_ids[i % len(problem_ids)]
            futures[pool.submit(submit_answer, base_url, problem_id, i)] = (i, problem_id)
        for future in as_completed(futures):
            idx, problem_id = futures[future]
            try:
                sid, submit_latency = future.result()
                submitted.append((idx, sid, problem_id, submit_latency))
            except Exception as exc:
                rows.append(
                    BenchmarkRow(
                        scenario=scenario,
                        n_users=n_users,
                        problem_id=problem_id,
                        submission_id=None,
                        submit_latency_s=None,
                        grading_latency_s=None,
                        feedback_total_latency_s=None,
                        e2e_feedback_latency_s=None,
                        hallucination_latency_s=None,
                        e2e_hallucination_latency_s=None,
                        final_status=None,
                        feedback_status=None,
                        hallucination_status=None,
                        score=None,
                        max_score=None,
                        memory_start_mb=memory_start,
                        memory_end_mb=None,
                        feedback_pending_max=0,
                        feedback_running_max=0,
                        hallucination_pending_max=0,
                        error=str(exc),
                    )
                )

    with ThreadPoolExecutor(max_workers=max(1, min(n_users, 16))) as pool:
        futures = {
            pool.submit(wait_submission, base_url, sid, wait_feedback, wait_hallucination, timeout_s): (
                idx,
                sid,
                problem_id,
                submit_latency,
            )
            for idx, sid, problem_id, submit_latency in submitted
        }
        for future in as_completed(futures):
            _idx, sid, problem_id, submit_latency = futures[future]
            data, backlog, error = future.result()
            memory_end = get_health(base_url).get("memory_mb")
            submitted_at = parse_server_dt(data.get("submitted_at"))
            graded_at = parse_server_dt(data.get("graded_at"))
            feedback_done_at = parse_server_dt(data.get("feedback_completed_at"))
            hallucination_done_at = parse_server_dt(data.get("hallucination_completed_at"))

            grading_latency = elapsed_s(submitted_at, graded_at)
            feedback_total = elapsed_s(graded_at, feedback_done_at)
            hallucination_latency = elapsed_s(feedback_done_at, hallucination_done_at)
            e2e_feedback = elapsed_s(submitted_at, feedback_done_at)
            e2e_hallucination = elapsed_s(submitted_at, hallucination_done_at)
            rows.append(
                BenchmarkRow(
                    scenario=scenario,
                    n_users=n_users,
                    problem_id=problem_id,
                    submission_id=sid,
                    submit_latency_s=round(submit_latency, 4),
                    grading_latency_s=round(grading_latency, 4) if grading_latency is not None else None,
                    feedback_total_latency_s=round(feedback_total, 4) if feedback_total is not None else None,
                    e2e_feedback_latency_s=round(e2e_feedback, 4) if e2e_feedback is not None else None,
                    hallucination_latency_s=round(hallucination_latency, 4) if hallucination_latency is not None else None,
                    e2e_hallucination_latency_s=round(e2e_hallucination, 4) if e2e_hallucination is not None else None,
                    final_status=data.get("status"),
                    feedback_status=data.get("feedback_status"),
                    hallucination_status=data.get("hallucination_status"),
                    score=data.get("score"),
                    max_score=data.get("max_score"),
                    memory_start_mb=memory_start,
                    memory_end_mb=memory_end,
                    feedback_pending_max=backlog["feedback_pending"],
                    feedback_running_max=backlog["feedback_running"],
                    hallucination_pending_max=backlog["hallucination_pending"],
                    error=error,
                )
            )

    return sorted(rows, key=lambda r: (r.submission_id is None, r.submission_id or 0))


def summarize(rows: list[BenchmarkRow]) -> None:
    ok_rows = [r for r in rows if not r.error]
    grading = [r.grading_latency_s for r in ok_rows if r.grading_latency_s is not None]
    feedback = [r.feedback_total_latency_s for r in ok_rows if r.feedback_total_latency_s is not None]
    hallucination = [
        r.hallucination_latency_s
        for r in ok_rows
        if r.hallucination_latency_s is not None
    ]
    print(f"\nRows: {len(rows)}  ok: {len(ok_rows)}  errors: {len(rows) - len(ok_rows)}")
    if grading:
        print(
            "Grading latency "
            f"p50={statistics.median(grading):.3f}s max={max(grading):.3f}s "
            f"target={GRADING_TARGET_S:.1f}s"
        )
    if feedback:
        print(
            "Feedback total latency "
            f"p50={statistics.median(feedback):.3f}s max={max(feedback):.3f}s "
            f"target={FEEDBACK_TARGET_S:.1f}s"
        )
    if hallucination:
        print(
            "Hallucination latency "
            f"p50={statistics.median(hallucination):.3f}s max={max(hallucination):.3f}s"
        )
    for row in rows:
        status = "ERR" if row.error else "OK"
        print(
            f"[{status}] sid={row.submission_id} "
            f"grading={row.grading_latency_s}s feedback={row.feedback_total_latency_s}s "
            f"hallucination={row.hallucination_latency_s}s "
            f"status={row.final_status} feedback_status={row.feedback_status} "
            f"hallucination_status={row.hallucination_status} error={row.error}"
        )


def write_csv(path: Path, rows: list[BenchmarkRow]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(asdict(rows[0]).keys()))
        writer.writeheader()
        for row in rows:
            writer.writerow(asdict(row))


def parse_users(raw: str) -> list[int]:
    return [int(part.strip()) for part in raw.split(",") if part.strip()]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--users", default="1")
    parser.add_argument("--problem-count", type=int, default=1)
    parser.add_argument("--problem-ids", default="")
    parser.add_argument("--wait-feedback", action="store_true")
    parser.add_argument("--wait-hallucination", action="store_true")
    parser.add_argument("--reset-running-jobs", action="store_true")
    parser.add_argument("--timeout", type=float, default=180.0)
    parser.add_argument("--output", default=f"tests/benchmark_pipeline_{now_iso()}.csv")
    args = parser.parse_args()

    all_rows: list[BenchmarkRow] = []
    if args.wait_hallucination:
        args.wait_feedback = True
    if args.reset_running_jobs:
        reset_count = asyncio.run(reset_running_jobs())
        print(f"Reset running jobs: {reset_count}")
    try:
        health = get_health(args.base_url)
        print(f"Health: {health}")
    except Exception as exc:
        print(f"Server health check failed: {exc}", file=sys.stderr)
        return 2

    all_problems = get_problems(args.base_url, max(1, args.problem_count))
    if args.problem_ids.strip():
        wanted = {int(p.strip()) for p in args.problem_ids.split(",") if p.strip()}
        selected = [p for p in all_problems if int(p.get("id")) in wanted]
        if not selected:
            raise RuntimeError(f"No matching problems for --problem-ids={args.problem_ids}")
    else:
        selected = all_problems[: max(1, args.problem_count)]
    problem_ids = [int(p["id"]) for p in selected]
    print(f"Problems selected ({len(problem_ids)}): {problem_ids}")

    for n_users in parse_users(args.users):
        print(
            f"\nRunning scenario users={n_users} "
            f"problems={len(problem_ids)} "
            f"wait_feedback={args.wait_feedback} wait_hallucination={args.wait_hallucination}"
        )
        rows = run_scenario(
            args.base_url,
            n_users,
            problem_ids,
            args.wait_feedback,
            args.wait_hallucination,
            args.timeout,
        )
        all_rows.extend(rows)
        summarize(rows)

    if all_rows:
        output = Path(args.output)
        write_csv(output, all_rows)
        print(f"\nCSV written: {output}")

    if any(row.error for row in all_rows):
        return 1
    if any(
        row.grading_latency_s is not None and row.grading_latency_s > GRADING_TARGET_S
        for row in all_rows
    ):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
