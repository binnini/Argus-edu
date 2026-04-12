"""
tests/test_e2e_timing.py — E2E 응답 시간 및 SLA 검증.

실제 서버(localhost:8000)에 텍스트 제출을 보내고
채점 완료까지 걸리는 시간을 측정하여 SLA 기준과 비교한다.

SLA 기준 (ADR-019 / config.py):
  - HIGH trust (점수 바로 공개): 12시간 내 교사 검토
  - NORMAL trust:                24시간 내 교사 검토
  - E2E 채점 완료 시간 목표:    60초 이내 (MLX gemma4:e4b 기준 ~27s)

실행:
  pytest tests/test_e2e_timing.py -v --timeout=300 -s
"""

import time

import pytest
import requests

from conftest import BASE_URL, TEACHER_PASSWORD

TEACHER_HEADERS = {"X-Teacher-Password": TEACHER_PASSWORD}

# SLA 임계값
GRADING_TIMEOUT_SOFT = 60    # 60초: 단일 제출 채점 완료 목표
GRADING_TIMEOUT_HARD = 120   # 120초: 절대 초과 불허
SLA_HIGH_HOURS  = 12
SLA_NORMAL_HOURS = 24


def get_first_problem_id() -> int:
    resp = requests.get(f"{BASE_URL}/api/v1/problems")
    assert resp.status_code == 200
    problems = resp.json().get("problems", [])
    assert problems, "DB에 문제가 없습니다"
    return problems[0]["id"]


def submit_and_wait(problem_id: int, student_answer: str, student_name: str = "타이밍테스트") -> tuple[dict, float]:
    """제출 → 채점 완료 대기. (응답 데이터, 소요 시간(s)) 반환."""
    t0 = time.time()
    resp = requests.post(
        f"{BASE_URL}/api/v1/submissions",
        json={
            "problem_id": problem_id,
            "student_answer": student_answer,
            "student_name": student_name,
            "student_id": "timing_test",
        },
    )
    assert resp.status_code == 202, f"제출 실패: {resp.status_code} {resp.text}"
    submission_id = resp.json()["submission_id"]

    deadline = time.time() + GRADING_TIMEOUT_HARD
    while time.time() < deadline:
        r = requests.get(f"{BASE_URL}/api/v1/submissions/{submission_id}")
        data = r.json()
        if data.get("status") in ("graded", "approved", "rejected", "error"):
            elapsed = time.time() - t0
            return data, elapsed
        time.sleep(2)

    pytest.fail(f"채점이 {GRADING_TIMEOUT_HARD}초 내에 완료되지 않았습니다")


@pytest.mark.timeout(GRADING_TIMEOUT_HARD + 10)
def test_grading_latency_single():
    """단일 제출 E2E 채점 시간이 GRADING_TIMEOUT_SOFT(60s) 이내인지 확인."""
    problem_id = get_first_problem_id()
    data, elapsed = submit_and_wait(problem_id, "정답입니다.", "latency_test_1")

    print(f"\n  채점 완료 시간: {elapsed:.1f}s (목표: {GRADING_TIMEOUT_SOFT}s 이내)")
    print(f"  status: {data.get('status')}, trust_level: {data.get('trust_level')}")

    assert data["status"] != "error", f"채점 파이프라인 오류: {data}"
    if elapsed > GRADING_TIMEOUT_SOFT:
        pytest.xfail(
            f"채점 시간 {elapsed:.1f}s > 목표 {GRADING_TIMEOUT_SOFT}s — "
            "허용 범위 초과이지만 절대 한계({GRADING_TIMEOUT_HARD}s)는 통과"
        )


@pytest.mark.timeout(GRADING_TIMEOUT_HARD + 10)
def test_grading_latency_wrong_answer():
    """오답 제출 시 채점 시간 확인 (low trust → full_review 큐)."""
    problem_id = get_first_problem_id()
    data, elapsed = submit_and_wait(problem_id, "모르겠습니다.", "latency_test_2")

    print(f"\n  채점 완료 시간: {elapsed:.1f}s")
    print(f"  status: {data.get('status')}, trust_level: {data.get('trust_level')}, queue_type: {data.get('queue_type', 'N/A')}")

    assert data["status"] != "error", f"채점 파이프라인 오류: {data}"


@pytest.mark.timeout(30)
def test_sla_deadline_set():
    """교사 큐 항목에 SLA deadline이 올바르게 설정됐는지 확인."""
    from datetime import datetime, timezone, timedelta

    resp = requests.get(f"{BASE_URL}/api/v1/teacher/queue", headers=TEACHER_HEADERS)
    assert resp.status_code == 200

    queue = resp.json().get("queue", [])
    if not queue:
        pytest.skip("교사 큐가 비어 있습니다 — 먼저 제출 테스트를 실행하세요")

    now = datetime.now(tz=timezone.utc)

    # 최근 1시간 내 큐에 들어온 항목만 검증 (오래된 기존 데이터 제외)
    recent_items = []
    for item in queue:
        queued_str = item.get("queued_at", "")
        if queued_str:
            try:
                queued_at = datetime.fromisoformat(queued_str.replace("Z", "+00:00"))
                if (now - queued_at).total_seconds() < 3600:
                    recent_items.append(item)
            except ValueError:
                pass

    if not recent_items:
        pytest.skip("최근 1시간 내 큐 항목이 없습니다 — latency 테스트를 먼저 실행하세요")

    for item in recent_items[:5]:
        sla_str = item.get("sla_deadline")
        assert sla_str, f"sla_deadline 없음: {item['submission_id']}"

        sla = datetime.fromisoformat(sla_str.replace("Z", "+00:00"))
        hours_until = (sla - now).total_seconds() / 3600

        trust_level = item.get("trust_level", "low")
        expected_max = SLA_HIGH_HOURS if trust_level == "high" else SLA_NORMAL_HOURS

        print(f"\n  submission_id={item['submission_id']} trust={trust_level} "
              f"SLA={sla_str} ({hours_until:.1f}h 남음)")

        assert hours_until > 0, f"최근 항목인데 SLA 기한이 이미 지났습니다: {sla_str}"
        assert hours_until <= expected_max + 1, (
            f"SLA 기한이 너무 김: {hours_until:.1f}h > {expected_max}h "
            f"(trust_level={trust_level})"
        )


@pytest.mark.timeout(30)
def test_queue_item_has_hallucination_fields():
    """교사 큐 항목에 할루시네이션 검증 필드가 있는지 확인 (ADR-026)."""
    resp = requests.get(f"{BASE_URL}/api/v1/teacher/queue", headers=TEACHER_HEADERS)
    assert resp.status_code == 200

    queue = resp.json().get("queue", [])
    if not queue:
        pytest.skip("교사 큐가 비어 있습니다")

    item = queue[0]
    assert "hallucination_status" in item, "hallucination_status 필드 없음"
    assert item["hallucination_status"] in ("pending", "running", "done", "failed"), (
        f"hallucination_status 값 오류: {item['hallucination_status']}"
    )
    # score는 done 상태에서만 non-null
    if item["hallucination_status"] == "done":
        assert item.get("hallucination_score") is not None, (
            "status=done인데 hallucination_score가 None"
        )
        score = item["hallucination_score"]
        assert 0.0 <= score <= 1.0, f"hallucination_score 범위 오류: {score}"

    print(f"\n  hallucination_status={item['hallucination_status']} "
          f"score={item.get('hallucination_score')}")


@pytest.mark.timeout(GRADING_TIMEOUT_HARD * 3 + 10)
def test_concurrent_grading_latency():
    """동시 3건 제출 시 각 채점 완료 시간 측정 (순차 처리 확인)."""
    import threading

    problem_id = get_first_problem_id()
    results: list[tuple[int, float, str]] = []
    errors: list[str] = []

    def worker(idx: int):
        try:
            t0 = time.time()
            resp = requests.post(
                f"{BASE_URL}/api/v1/submissions",
                json={
                    "problem_id": problem_id,
                    "student_answer": f"동시 테스트 {idx}",
                    "student_name": f"concurrent_{idx}",
                    "student_id": f"ct_{idx}",
                },
            )
            if resp.status_code != 202:
                errors.append(f"제출 실패 {idx}: {resp.status_code}")
                return
            sid = resp.json()["submission_id"]
            deadline = time.time() + GRADING_TIMEOUT_HARD * 3
            while time.time() < deadline:
                r = requests.get(f"{BASE_URL}/api/v1/submissions/{sid}")
                d = r.json()
                if d.get("status") in ("graded", "approved", "rejected", "error"):
                    results.append((idx, time.time() - t0, d.get("status", "?")))
                    return
                time.sleep(3)
            errors.append(f"타임아웃 {idx}")
        except Exception as e:
            errors.append(f"예외 {idx}: {e}")

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(3)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=GRADING_TIMEOUT_HARD * 3 + 5)

    assert not errors, f"동시 제출 오류: {errors}"
    assert len(results) == 3, f"결과 수 부족: {len(results)}/3"

    print("\n  동시 3건 채점 결과:")
    for idx, elapsed, status in sorted(results):
        print(f"    [{idx}] {elapsed:.1f}s — {status}")

    max_elapsed = max(e for _, e, _ in results)
    # MLX 단일 GPU 직렬화: 3건 × ~27s = ~81s 예상
    assert max_elapsed < GRADING_TIMEOUT_HARD * 3, (
        f"동시 3건 최대 소요 {max_elapsed:.1f}s가 한계를 초과했습니다"
    )
