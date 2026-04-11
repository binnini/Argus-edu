"""
tests/test_integration.py — Argus Phase 8 통합 테스트

모든 테스트는 실제 HTTP 요청을 localhost:8000에 보낸다.
Ollama 파이프라인(채점+피드백 3회) 완료까지 최대 900초 폴링.
"""

import io
import struct
import time
import warnings
import zlib

import pytest
import requests

from conftest import BASE_URL, TEACHER_PASSWORD

TEACHER_HEADERS = {"X-Teacher-Password": TEACHER_PASSWORD}

# ── 헬퍼 ────────────────────────────────────────────────────────


def wait_until_graded(submission_id: int, timeout: int = 900, interval: int = 5) -> dict:
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


def submit_answer(
    problem_id: int,
    student_answer: str,
    student_name: str = "테스트학생",
    student_id: str = "99999999",
) -> int:
    """답변 제출 후 submission_id 반환."""
    resp = requests.post(
        f"{BASE_URL}/api/v1/submissions",
        json={
            "problem_id": problem_id,
            "student_answer": student_answer,
            "student_name": student_name,
            "student_id": student_id,
        },
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


def _make_dummy_png(width: int = 10, height: int = 10) -> bytes:
    """PIL 없이 순수 표준 라이브러리로 흰 배경 PNG를 생성한다."""

    def _pack_chunk(chunk_type: bytes, data: bytes) -> bytes:
        length = struct.pack(">I", len(data))
        crc = struct.pack(">I", zlib.crc32(chunk_type + data) & 0xFFFFFFFF)
        return length + chunk_type + data + crc

    # IHDR: width, height, bit depth=8, color type=2(RGB), compress/filter/interlace=0
    ihdr_data = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    ihdr_chunk = _pack_chunk(b"IHDR", ihdr_data)

    # IDAT: 흰색 픽셀(255,255,255) 채우기
    raw_rows = b""
    for _ in range(height):
        # 각 행 앞에 filter type 0 (None)
        raw_rows += b"\x00" + b"\xFF\xFF\xFF" * width
    compressed = zlib.compress(raw_rows)
    idat_chunk = _pack_chunk(b"IDAT", compressed)

    iend_chunk = _pack_chunk(b"IEND", b"")

    png_signature = b"\x89PNG\r\n\x1a\n"
    return png_signature + ihdr_chunk + idat_chunk + iend_chunk


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
    """GET /api/v1/problems → 페이지네이션 응답, total 필드 존재."""
    resp = requests.get(f"{BASE_URL}/api/v1/problems")
    assert resp.status_code == 200
    data = resp.json()
    assert "problems" in data, "problems 필드 없음"
    assert "total" in data, "total 필드 없음"
    assert "page" in data, "page 필드 없음"
    assert "page_size" in data, "page_size 필드 없음"
    # 기본 page_size=30 → problems 최대 30개
    assert len(data["problems"]) <= 30, f"기본 page_size 초과: {len(data['problems'])}개"
    # 전체 문제 수
    assert data["total"] > 0, "문제가 0개입니다"
    assert data["page"] == 1
    assert data["page_size"] == 30


@pytest.mark.timeout(30)
def test_problems_pagination():
    """GET /api/v1/problems?page=2&page_size=10 → 2페이지 결과."""
    resp = requests.get(f"{BASE_URL}/api/v1/problems?page=2&page_size=10")
    assert resp.status_code == 200
    data = resp.json()
    assert data["page"] == 2
    assert data["page_size"] == 10
    assert len(data["problems"]) <= 10


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


@pytest.mark.timeout(1000)
def test_e2e_normal_flow():
    """
    정상 흐름 E2E:
    정답 수준 답변 제출 → graded 대기 → feedback=None 확인
    → 교사 큐 존재 확인 → approve → approved + feedback 존재 확인
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

    # 3) 승인 전 feedback=None 확인 (풀이 설명 차단 정책)
    # graded 상태일 때만 확인 (이미 approved면 다른 테스트에서 처리된 경우)
    if data["status"] == "graded":
        assert data["feedback"] is None, (
            f"승인 전인데 feedback이 노출됩니다: {str(data['feedback'])[:50]}..."
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

    # 6) approved 상태 + feedback 존재 및 구조 확인
    final_resp = requests.get(f"{BASE_URL}/api/v1/submissions/{sid}")
    assert final_resp.status_code == 200
    final = final_resp.json()
    assert final["teacher_approved"] is True, "teacher_approved가 True가 아닙니다"
    assert final["feedback"] is not None, "approved 후에도 feedback이 None입니다"
    assert isinstance(final["feedback"], dict), "feedback이 dict가 아닙니다"
    for key in ("student_mistakes", "correct_approach", "key_concept"):
        assert key in final["feedback"], f"feedback에 '{key}' 키가 없습니다"


@pytest.mark.timeout(1000)
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


@pytest.mark.timeout(1000)
def test_feedback_blocked_before_approval():
    """
    풀이 피드백 차단 정책:
    제출 → graded 대기 → feedback=None 확인 (교사 승인 전).
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
        assert data["feedback"] is None, (
            "HITL 정책 위반: 교사 승인 전에 feedback이 노출됩니다!"
        )
    # approved면 다른 테스트가 승인한 것 — 패스
    elif data["status"] in ("approved", "rejected"):
        pass  # 이미 처리된 경우는 검증 불가


@pytest.mark.timeout(1000)
def test_teacher_modify():
    """
    교사 수정 흐름:
    제출 → graded 대기 → modify 액션(점수+teacher_feedback) → approved 상태 확인.
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

    # 수정 액션 — teacher_feedback 필드로 교사 의견 전달
    action_resp = requests.post(
        f"{BASE_URL}/api/v1/teacher/queue/{queue_id}/action",
        json={
            "action": "modify",
            "teacher_score": 2,
            "teacher_feedback": "풀이 방향은 맞으나 f(2) 계산이 틀렸습니다. f(2) = 4 - 8 + c 형태로 재계산 필요.",
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


# ── Phase 8 신규 테스트 ──────────────────────────────────────────


@pytest.mark.timeout(1000)
def test_feedback_structure():
    """
    feedback 구조 검증:
    정답 수준 답변 제출 → graded 대기 → 교사 승인 → feedback 필드 구조 상세 검증.
    - feedback["student_mistakes"]: list
    - feedback["correct_approach"]: list, 각 항목에 step/title/content 키 존재
    - feedback["key_concept"]: 비어있지 않은 str
    """
    sid = submit_answer(
        problem_id=5,
        student_answer=(
            "등비수열 {aₙ}의 공비를 r이라 하면 a₁=2, a₃=18이므로 "
            "a₃ = a₁ · r² = 2r² = 18, r² = 9, r = 3 (r > 0). "
            "따라서 a₅ = a₁ · r⁴ = 2 · 81 = 162."
        ),
    )

    # graded 대기
    data = wait_until_graded(sid)
    assert data["status"] in ("graded", "approved"), f"예상치 않은 상태: {data['status']}"

    # 교사 큐에서 queue_id 획득
    queue_item = find_queue_item(sid)
    assert queue_item is not None, f"submission_id={sid}가 교사 큐에 없습니다"
    queue_id = queue_item["queue_id"]

    # 교사 승인
    action_resp = requests.post(
        f"{BASE_URL}/api/v1/teacher/queue/{queue_id}/action",
        json={"action": "approve"},
        headers=TEACHER_HEADERS,
    )
    assert action_resp.status_code == 200, (
        f"승인 실패: {action_resp.status_code} {action_resp.text}"
    )

    # 승인 후 feedback 구조 검증
    final_resp = requests.get(f"{BASE_URL}/api/v1/submissions/{sid}")
    assert final_resp.status_code == 200
    final = final_resp.json()

    assert final["teacher_approved"] is True, "teacher_approved가 True가 아닙니다"
    feedback = final["feedback"]
    assert feedback is not None, "approved 후에도 feedback이 None입니다"
    assert isinstance(feedback, dict), f"feedback이 dict가 아닙니다: {type(feedback)}"

    # student_mistakes: list
    assert "student_mistakes" in feedback, "feedback에 'student_mistakes' 키가 없습니다"
    assert isinstance(feedback["student_mistakes"], list), (
        f"student_mistakes가 list가 아닙니다: {type(feedback['student_mistakes'])}"
    )

    # correct_approach: list, 각 항목에 step/title/content 키 존재
    assert "correct_approach" in feedback, "feedback에 'correct_approach' 키가 없습니다"
    assert isinstance(feedback["correct_approach"], list), (
        f"correct_approach가 list가 아닙니다: {type(feedback['correct_approach'])}"
    )
    for idx, step_item in enumerate(feedback["correct_approach"]):
        assert isinstance(step_item, dict), (
            f"correct_approach[{idx}]가 dict가 아닙니다: {type(step_item)}"
        )
        for key in ("step", "title", "content"):
            assert key in step_item, (
                f"correct_approach[{idx}]에 '{key}' 키가 없습니다: {step_item}"
            )

    # key_concept: 비어있지 않은 str
    assert "key_concept" in feedback, "feedback에 'key_concept' 키가 없습니다"
    assert isinstance(feedback["key_concept"], str), (
        f"key_concept가 str가 아닙니다: {type(feedback['key_concept'])}"
    )
    assert len(feedback["key_concept"].strip()) > 0, "key_concept가 빈 문자열입니다"


@pytest.mark.timeout(30)
def test_image_upload_pipeline():
    """
    이미지 업로드 파이프라인 확인:
    POST /api/v1/submissions/image 엔드포인트 존재 여부 확인.
    pix2tex 미설치 상태를 고려하여 202 또는 4xx 응답만 허용 (500 불허).

    - 작은 흰 배경 더미 PNG(10x10px)를 표준 라이브러리로 직접 생성해 전송
    - 202: submission_id 존재 확인
    - 4xx: detail 메시지 존재 확인
    - OCR 엔진 미설치로 인한 에러는 soft assert로 경고 처리
    """
    dummy_png = _make_dummy_png(width=10, height=10)

    resp = requests.post(
        f"{BASE_URL}/api/v1/submissions/image",
        data={"problem_id": "1", "student_name": "테스트학생", "student_id": "99999998"},
        files={"image": ("test_dummy.png", io.BytesIO(dummy_png), "image/png")},
    )

    # 서버 내부 오류(5xx)는 절대 허용하지 않음
    assert resp.status_code < 500, (
        f"서버 내부 오류 발생: {resp.status_code} {resp.text[:200]}"
    )

    if resp.status_code == 202:
        data = resp.json()
        assert "submission_id" in data, (
            f"202 응답에 submission_id가 없습니다: {data}"
        )
    elif 400 <= resp.status_code < 500:
        data = resp.json()
        assert "detail" in data, (
            f"4xx 응답에 detail 메시지가 없습니다: {data}"
        )
        # OCR 엔진 미설치 등 정상 예외는 soft assert
        warnings.warn(
            f"[SOFT] 이미지 업로드 4xx 응답 (OCR 미설치 가능성): "
            f"status={resp.status_code}, detail={data.get('detail', '')}",
            UserWarning,
        )
    else:
        pytest.fail(
            f"예상치 못한 응답 코드: {resp.status_code} {resp.text[:200]}"
        )


# ── Phase 8 추가 테스트 (학생 이력 / 교사 현황 / 문제 CRUD) ──────


@pytest.mark.timeout(1000)
def test_student_history():
    """
    학생 제출 이력 조회:
    제출 → graded 대기 → GET /api/v1/submissions?student_id=... → 이력 포함 확인.
    """
    student_id = "88888801"
    sid = submit_answer(
        problem_id=1,
        student_answer="f'(x) = 3x² - 6x이고, f'(x)=0에서 x=0 또는 x=2이다. f(2)=-3이므로 최솟값은 -3.",
        student_name="이력테스트",
        student_id=student_id,
    )

    # graded 대기
    wait_until_graded(sid)

    # 이력 조회
    resp = requests.get(f"{BASE_URL}/api/v1/submissions?student_id={student_id}")
    assert resp.status_code == 200, f"이력 조회 실패: {resp.status_code} {resp.text}"
    data = resp.json()
    assert "submissions" in data, "submissions 필드 없음"
    assert isinstance(data["submissions"], list), "submissions가 list가 아닙니다"
    assert len(data["submissions"]) >= 1, "제출 이력이 0건입니다"

    # 방금 제출한 항목 확인
    ids = [s["submission_id"] for s in data["submissions"]]
    assert sid in ids, f"submission_id={sid}가 이력에 없습니다"

    # 각 항목 필드 검증
    for item in data["submissions"]:
        for field in ("submission_id", "problem_title", "problem_domain", "status", "input_type", "submitted_at"):
            assert field in item, f"이력 항목에 '{field}' 필드 없음"


@pytest.mark.timeout(30)
def test_teacher_submissions_overview():
    """
    GET /api/v1/teacher/submissions → 제출 현황 목록, 페이지네이션 포함.
    """
    resp = requests.get(
        f"{BASE_URL}/api/v1/teacher/submissions",
        headers=TEACHER_HEADERS,
    )
    assert resp.status_code == 200, f"제출 현황 조회 실패: {resp.status_code} {resp.text}"
    data = resp.json()
    assert "submissions" in data, "submissions 필드 없음"
    assert "total" in data, "total 필드 없음"
    assert "page" in data, "page 필드 없음"
    assert "page_size" in data, "page_size 필드 없음"
    assert isinstance(data["submissions"], list)

    # 각 항목 필드 검증
    for item in data["submissions"]:
        for field in ("submission_id", "problem_id", "problem_title", "student_name", "status", "submitted_at"):
            assert field in item, f"제출 현황 항목에 '{field}' 필드 없음"


@pytest.mark.timeout(30)
def test_teacher_submissions_filter():
    """
    GET /api/v1/teacher/submissions?status=pending → status 필터 동작 확인.
    """
    resp = requests.get(
        f"{BASE_URL}/api/v1/teacher/submissions?status=pending",
        headers=TEACHER_HEADERS,
    )
    assert resp.status_code == 200
    data = resp.json()
    for item in data["submissions"]:
        assert item["status"] == "pending", f"필터 결과에 pending 아닌 항목: {item['status']}"


@pytest.mark.timeout(30)
def test_teacher_problem_crud():
    """
    문제 CRUD:
    POST → GET(목록) → PUT(수정) → DELETE 흐름 검증.
    """
    # 1) 문제 등록
    create_resp = requests.post(
        f"{BASE_URL}/api/v1/teacher/problems",
        json={
            "title": "테스트_문제_CRUD_001",
            "content": "테스트용 문제입니다. $x^2 + 1 = 0$ 의 해를 구하시오.",
            "answer": "해 없음",
            "reference_solution": "1단계: 판별식 확인",
            "rubric": {
                "total_score": 2,
                "steps": [
                    {"step": 1, "description": "판별식 계산", "score": 1},
                    {"step": 2, "description": "결론", "score": 1},
                ],
            },
            "domain": "수학",
            "difficulty": 1,
        },
        headers=TEACHER_HEADERS,
    )
    assert create_resp.status_code == 201, f"문제 등록 실패: {create_resp.status_code} {create_resp.text}"
    created = create_resp.json()
    assert "id" in created, "등록 응답에 id 없음"
    problem_id = created["id"]

    # 2) 교사 문제 목록에서 확인
    list_resp = requests.get(
        f"{BASE_URL}/api/v1/teacher/problems",
        headers=TEACHER_HEADERS,
    )
    assert list_resp.status_code == 200
    titles = [p["title"] for p in list_resp.json().get("problems", [])]
    assert "테스트_문제_CRUD_001" in titles, "등록된 문제가 목록에 없습니다"

    # 3) 수정
    update_resp = requests.put(
        f"{BASE_URL}/api/v1/teacher/problems/{problem_id}",
        json={"title": "테스트_문제_CRUD_001_수정", "difficulty": 2},
        headers=TEACHER_HEADERS,
    )
    assert update_resp.status_code == 200, f"문제 수정 실패: {update_resp.status_code} {update_resp.text}"
    updated = update_resp.json()
    assert updated["title"] == "테스트_문제_CRUD_001_수정"
    assert updated["difficulty"] == 2

    # 4) 삭제
    delete_resp = requests.delete(
        f"{BASE_URL}/api/v1/teacher/problems/{problem_id}",
        headers=TEACHER_HEADERS,
    )
    assert delete_resp.status_code == 200, f"문제 삭제 실패: {delete_resp.status_code} {delete_resp.text}"
    delete_data = delete_resp.json()
    assert delete_data["deleted"] is True, "deleted가 True가 아닙니다"


@pytest.mark.timeout(30)
def test_teacher_queue_trust_filter():
    """
    GET /api/v1/teacher/queue?trust_level=high → trust_level 필터 동작 확인.
    """
    resp = requests.get(
        f"{BASE_URL}/api/v1/teacher/queue?trust_level=high",
        headers=TEACHER_HEADERS,
    )
    assert resp.status_code == 200
    data = resp.json()
    for item in data["queue"]:
        assert item["trust_level"] == "high", (
            f"필터 결과에 high 아닌 항목: {item['trust_level']}"
        )


@pytest.mark.timeout(30)
def test_queue_item_has_image_fields():
    """
    GET /api/v1/teacher/queue → 각 항목에 input_type, image_path 필드 존재.
    """
    resp = requests.get(
        f"{BASE_URL}/api/v1/teacher/queue",
        headers=TEACHER_HEADERS,
    )
    assert resp.status_code == 200
    data = resp.json()
    for item in data["queue"]:
        assert "input_type" in item, f"queue 항목에 input_type 없음: {item.get('queue_id')}"
        assert "image_path" in item, f"queue 항목에 image_path 없음: {item.get('queue_id')}"
