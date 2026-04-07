"""
tests/test_integration.py — Argus 통합 테스트

모든 테스트는 실제 HTTP 요청을 localhost:8000에 보낸다.
Ollama 파이프라인(채점+설명 3회) 완료까지 최대 600초 폴링.
"""

import time
import warnings

import pytest
import requests

from conftest import BASE_URL, TEACHER_PASSWORD

TEACHER_HEADERS = {"X-Teacher-Password": TEACHER_PASSWORD}

# ── 헬퍼 ────────────────────────────────────────────────────────


def wait_until_graded(submission_id: int, timeout: int = 600, interval: int = 5) -> dict:
    """
    submission이 'graded' 또는 'approved'/'rejected' 상태가 될 때까지 폴링.
    최대 timeout초 대기. 초과 시 pytest.fail().
    """
    deadline = time.time() + timeout
    while time.time() < deadline:
        resp = requests.get(f"{BASE_URL}/api/v1/submissions/{submission_id}")
        assert resp.status_code == 200, f"폴링 실패: {resp.status_code} {resp.text}"
        data = resp.json()
        status = data.get("status")
        if status in ("graded", "approved", "rejected", "error"):
            return data
        time.sleep(interval)
    pytest.fail(
        f"submission_id={submission_id}이 {timeout}초 내에 graded 상태에 도달하지 못했습니다."
    )


def submit_answer(problem_id: int, student_answer: str) -> int:
    """답변 제출 후 submission_id 반환."""
    resp = requests.post(
        f"{BASE_URL}/api/v1/submissions",
        json={"problem_id": problem_id, "student_answer": student_answer},
    )
    assert resp.status_code == 202, f"제출 실패: {resp.status_code} {resp.text}"
    data = resp.json()
    assert data["status"] == "pending"
    return data["submission_id"]


def find_queue_item(submission_id: int) -> dict | None:
    """교사 큐에서 특정 submission_id 항목 반환. 없으면 None."""
    resp = requests.get(
        f"{BASE_URL}/api/v1/teacher/queue",
        headers=TEACHER_HEADERS,
    )
    assert resp.status_code == 200, f"큐 조회 실패: {resp.status_code}"
    for item in resp.json().get("queue", []):
        if item["submission_id"] == submission_id:
            return item
    return None


# ── 기본 테스트 ─────────────────────────────────────────────────


@pytest.mark.timeout(30)
def test_health():
    """GET /health → 200, sbert/hhem 모두 true."""
    resp = requests.get(f"{BASE_URL}/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["models"]["sbert"] is True, "SBERT가 로드되지 않았습니다"
    assert data["models"]["hhem"] is True, "HHEM이 로드되지 않았습니다"


@pytest.mark.timeout(30)
def test_problems_list():
    """GET /api/v1/problems → 문제 15개."""
    resp = requests.get(f"{BASE_URL}/api/v1/problems")
    assert resp.status_code == 200
    problems = resp.json()["problems"]
    assert len(problems) == 15, f"문제 수가 15개가 아님: {len(problems)}개"


@pytest.mark.timeout(30)
def test_problem_no_answer_leak():
    """GET /api/v1/problems/1 → answer, reference_solution 필드 없음 (학생 노출 금지)."""
    resp = requests.get(f"{BASE_URL}/api/v1/problems/1")
    assert resp.status_code == 200
    data = resp.json()
    assert "answer" not in data, "answer 필드가 노출됩니다 — 보안 위반!"
    assert "reference_solution" not in data, "reference_solution 필드가 노출됩니다 — 보안 위반!"
    # 허용 필드 확인
    for field in ("id", "title", "content", "domain", "difficulty", "total_score"):
        assert field in data, f"필수 필드 없음: {field}"


@pytest.mark.timeout(30)
def test_teacher_auth_missing():
    """GET /api/v1/teacher/queue (헤더 없음) → 401."""
    resp = requests.get(f"{BASE_URL}/api/v1/teacher/queue")
    assert resp.status_code == 401, f"헤더 없음인데 {resp.status_code} 반환"


@pytest.mark.timeout(30)
def test_teacher_auth_wrong():
    """GET /api/v1/teacher/queue (틀린 비밀번호) → 401."""
    resp = requests.get(
        f"{BASE_URL}/api/v1/teacher/queue",
        headers={"X-Teacher-Password": "wrong-password-12345"},
    )
    assert resp.status_code == 401, f"틀린 비밀번호인데 {resp.status_code} 반환"


# ── E2E 테스트 ──────────────────────────────────────────────────


@pytest.mark.timeout(700)
def test_e2e_normal_flow():
    """
    정상 흐름 E2E:
    정답 수준 답변 제출 → graded 대기 → explanation=None 확인
    → 교사 큐 존재 확인 → approve → approved + explanation 존재 확인
    """
    # 1) 제출
    sid = submit_answer(
        problem_id=1,
        student_answer=(
            "f(x) = x³ - 3x² + 1을 미분하면 f'(x) = 3x² - 6x = 3x(x-2)이다. "
            "f'(x) = 0에서 x = 0 또는 x = 2. "
            "f(0) = 1, f(2) = 8 - 12 + 1 = -3, f(3) = 27 - 27 + 1 = 1. "
            "따라서 [0, 3]에서 최솟값은 f(2) = -3이다."
        ),
    )

    # 2) graded 대기
    data = wait_until_graded(sid)
    assert data["status"] in ("graded", "approved"), f"예상치 않은 상태: {data['status']}"

    # 3) 승인 전 explanation=None 확인 (풀이 설명 차단 정책)
    # graded 상태일 때만 확인 (이미 approved면 다른 테스트에서 처리된 경우)
    if data["status"] == "graded":
        assert data["explanation"] is None, (
            f"승인 전인데 explanation이 노출됩니다: {data['explanation'][:50]}..."
        )

    # 4) 교사 큐에 해당 submission 존재 확인
    queue_item = find_queue_item(sid)
    assert queue_item is not None, f"submission_id={sid}가 교사 큐에 없습니다"
    queue_id = queue_item["queue_id"]

    # 5) 교사 승인
    action_resp = requests.post(
        f"{BASE_URL}/api/v1/teacher/queue/{queue_id}/action",
        json={"action": "approve"},
        headers=TEACHER_HEADERS,
    )
    assert action_resp.status_code == 200, f"승인 실패: {action_resp.status_code} {action_resp.text}"
    action_data = action_resp.json()
    assert action_data["action"] == "approve"

    # 6) approved 상태 + explanation 존재 확인
    final_resp = requests.get(f"{BASE_URL}/api/v1/submissions/{sid}")
    assert final_resp.status_code == 200
    final = final_resp.json()
    assert final["teacher_approved"] is True, "teacher_approved가 True가 아닙니다"
    assert final["explanation"] is not None, "approved 후에도 explanation이 None입니다"
    assert len(final["explanation"]) > 0, "explanation이 빈 문자열입니다"


@pytest.mark.timeout(700)
def test_e2e_low_trust():
    """
    Low 신뢰도 케이스:
    명백히 틀린 답변 제출 → graded 대기 → trust_level/queue_type 확인 (soft assert).
    deterministic하지 않으므로 실패해도 경고만 출력.
    """
    sid = submit_answer(
        problem_id=2,
        student_answer="모르겠습니다. 답은 100입니다. 계산 과정 없음.",
    )

    data = wait_until_graded(sid)
    assert data["status"] in ("graded", "approved", "rejected"), (
        f"예상치 않은 상태: {data['status']}"
    )

    # 교사 큐에서 trust 정보 확인 (soft assert — LLM은 deterministic하지 않음)
    queue_item = find_queue_item(sid)
    if queue_item is None:
        warnings.warn(
            f"[SOFT] submission_id={sid}가 교사 큐에 없습니다 (이미 처리됐거나 high trust 분류)",
            UserWarning,
        )
        return

    trust_level = queue_item.get("trust_level")
    queue_type = queue_item.get("queue_type")

    if trust_level != "low":
        warnings.warn(
            f"[SOFT] 오답인데 trust_level={trust_level} (low 예상). LLM 비결정성으로 허용.",
            UserWarning,
        )
    if queue_type != "full_review":
        warnings.warn(
            f"[SOFT] 오답인데 queue_type={queue_type} (full_review 예상). LLM 비결정성으로 허용.",
            UserWarning,
        )

    # 최소한 큐 항목이 존재함을 확인 (이 시점엔 action=None이어야 함)
    assert queue_item.get("queue_id") is not None, "queue_id가 없습니다"


@pytest.mark.timeout(700)
def test_explanation_blocked_before_approval():
    """
    풀이 설명 차단 정책:
    제출 → graded 대기 → explanation=None 확인 (교사 승인 전).
    """
    sid = submit_answer(
        problem_id=3,
        student_answer=(
            "적분 ∫(0→2) (3x² - 2x) dx = [x³ - x²](0→2) = (8 - 4) - 0 = 4"
        ),
    )

    data = wait_until_graded(sid)
    # graded 상태(아직 교사 미처리)여야 함
    if data["status"] == "graded":
        assert data["explanation"] is None, (
            "HITL 정책 위반: 교사 승인 전에 explanation이 노출됩니다!"
        )
    # approved면 다른 테스트가 승인한 것 — 패스
    elif data["status"] in ("approved", "rejected"):
        pass  # 이미 처리된 경우는 검증 불가


@pytest.mark.timeout(700)
def test_teacher_modify():
    """
    교사 수정 흐름:
    제출 → graded 대기 → modify 액션(점수+풀이) → approved 상태 확인.
    """
    sid = submit_answer(
        problem_id=4,
        student_answer="도함수를 구하면 f'(x) = 2x - 4이고, f'(x)=0에서 x=2. f(2)=0이다.",
    )

    data = wait_until_graded(sid)
    assert data["status"] in ("graded", "approved"), f"예상치 않은 상태: {data['status']}"

    queue_item = find_queue_item(sid)
    assert queue_item is not None, f"submission_id={sid}가 교사 큐에 없습니다"
    queue_id = queue_item["queue_id"]

    # 수정 액션
    action_resp = requests.post(
        f"{BASE_URL}/api/v1/teacher/queue/{queue_id}/action",
        json={
            "action": "modify",
            "teacher_score": 2,
            "teacher_explanation": "풀이 방향은 맞으나 f(2) 계산이 틀렸습니다. f(2) = 4 - 8 + c 형태로 재계산 필요.",
        },
        headers=TEACHER_HEADERS,
    )
    assert action_resp.status_code == 200, f"수정 실패: {action_resp.status_code} {action_resp.text}"
    action_data = action_resp.json()
    assert action_data["action"] == "modify"

    # 최종 상태 확인
    final_resp = requests.get(f"{BASE_URL}/api/v1/submissions/{sid}")
    assert final_resp.status_code == 200
    final = final_resp.json()
    assert final["status"] == "approved", f"수정 후 상태가 approved가 아님: {final['status']}"
    assert final["teacher_approved"] is True


@pytest.mark.timeout(30)
def test_feedback_summary():
    """
    GET /api/v1/teacher/feedback/summary → 200, 필수 필드 존재 확인.
    """
    resp = requests.get(
        f"{BASE_URL}/api/v1/teacher/feedback/summary",
        headers=TEACHER_HEADERS,
    )
    assert resp.status_code == 200, f"피드백 요약 실패: {resp.status_code}"
    data = resp.json()

    required_fields = [
        "total_reviewed",
        "approved",
        "modified",
        "rejected",
        "approval_rate",
        "avg_score_delta",
        "low_trust_detection_precision",
    ]
    for field in required_fields:
        assert field in data, f"필수 필드 없음: {field}"

    # 값 타입 검증
    assert isinstance(data["total_reviewed"], int)
    assert isinstance(data["approved"], int)
    assert 0.0 <= data["approval_rate"] <= 1.0, f"approval_rate 범위 오류: {data['approval_rate']}"
