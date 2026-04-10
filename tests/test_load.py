"""
tests/test_load.py — Argus 부하 및 용량 테스트

실행 방법:
    # 전체 부하 테스트 (Claude API 과금 발생)
    pytest tests/test_load.py -v -m load --timeout=300

    # 메모리 안정성만 (API 과금 없음)
    pytest tests/test_load.py -v -m memory --timeout=600

    # 전체 실행
    pytest tests/test_load.py -v --timeout=600

목적:
    - ADR-019 기준: Mac Mini M4에서 학교 교실 1개(30명) 동시 수업 대응 가능성 검증
    - 텍스트 제출 동시 30명, 이미지 제출 동시 10명 처리 여부 확인
    - 장기 운영 시 메모리 누수 여부 확인
"""

import io
import struct
import time
import threading
import warnings
import zlib
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field

import pytest
import requests

from conftest import BASE_URL, TEACHER_PASSWORD

TEACHER_HEADERS = {"X-Teacher-Password": TEACHER_PASSWORD}


# ── 마커 등록 ────────────────────────────────────────────────────

def pytest_configure(config):
    config.addinivalue_line("markers", "load: Claude API 호출이 포함된 부하 테스트")
    config.addinivalue_line("markers", "memory: 메모리 안정성 테스트 (API 호출 없음)")


# ── 헬퍼 ────────────────────────────────────────────────────────

@dataclass
class SubmitResult:
    submission_id: int | None = None
    status_code: int = 0
    elapsed_submit: float = 0.0       # 제출 응답까지 (초)
    elapsed_graded: float = 0.0       # graded 상태까지 (초)
    error: str = ""


def _make_dummy_png(width: int = 10, height: int = 10) -> bytes:
    def _chunk(t, d):
        return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xFFFFFFFF)

    raw = b"".join(b"\x00" + b"\xff\xff\xff" * width for _ in range(height))
    return (
        b"\x89PNG\r\n\x1a\n"
        + _chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
        + _chunk(b"IDAT", zlib.compress(raw))
        + _chunk(b"IEND", b"")
    )


def _submit_text(problem_id: int, answer: str, timeout: int = 30) -> SubmitResult:
    """텍스트 답변 제출 → submission_id 반환."""
    result = SubmitResult()
    t0 = time.time()
    try:
        resp = requests.post(
            f"{BASE_URL}/api/v1/submissions",
            json={"problem_id": problem_id, "student_answer": answer},
            timeout=timeout,
        )
        result.elapsed_submit = time.time() - t0
        result.status_code = resp.status_code
        if resp.status_code == 202:
            result.submission_id = resp.json()["submission_id"]
    except Exception as e:
        result.error = str(e)
    return result


def _submit_image(problem_id: int, timeout: int = 30) -> SubmitResult:
    """이미지 제출 → submission_id 반환."""
    result = SubmitResult()
    t0 = time.time()
    try:
        resp = requests.post(
            f"{BASE_URL}/api/v1/submissions/image",
            data={"problem_id": str(problem_id)},
            files={"image": ("dummy.png", io.BytesIO(_make_dummy_png()), "image/png")},
            timeout=timeout,
        )
        result.elapsed_submit = time.time() - t0
        result.status_code = resp.status_code
        if resp.status_code == 202:
            result.submission_id = resp.json()["submission_id"]
    except Exception as e:
        result.error = str(e)
    return result


def _wait_graded(submission_id: int, timeout: int = 900) -> dict:
    """graded/approved/error 상태까지 폴링."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        resp = requests.get(f"{BASE_URL}/api/v1/submissions/{submission_id}", timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            if data.get("status") in ("graded", "approved", "rejected", "error"):
                return data
        time.sleep(3)
    return {"status": "timeout"}


def _server_memory_mb() -> float:
    """GET /health 에서 메모리 정보 반환 (없으면 -1)."""
    try:
        data = requests.get(f"{BASE_URL}/health", timeout=5).json()
        return float(data.get("memory_mb", -1))
    except Exception:
        return -1.0


# ── 서버 사전 확인 ────────────────────────────────────────────────

@pytest.fixture(scope="module", autouse=True)
def require_server():
    """부하 테스트 전 서버 헬스 확인."""
    try:
        resp = requests.get(f"{BASE_URL}/health", timeout=5)
        assert resp.status_code == 200, f"서버 응답 이상: {resp.status_code}"
    except Exception as e:
        pytest.skip(f"서버 미기동 — 부하 테스트 건너뜀: {e}")


# ── 응답 시간 기준선 ──────────────────────────────────────────────

@pytest.mark.timeout(60)
def test_single_submit_response_time():
    """
    단일 텍스트 제출 응답 시간 기준선 측정.
    제출 API 자체(202 응답)가 2초 이내여야 함.
    """
    result = _submit_text(
        problem_id=1,
        answer="f'(x) = 3x^2 - 6x = 0에서 x=0 또는 x=2이므로 최솟값은 f(2) = -3이다.",
    )
    assert result.status_code == 202, f"제출 실패: {result.status_code} {result.error}"
    assert result.elapsed_submit < 2.0, (
        f"제출 응답이 2초 초과: {result.elapsed_submit:.2f}s (서버 과부하 또는 동기 처리 의심)"
    )
    print(f"\n단일 제출 응답 시간: {result.elapsed_submit:.3f}s")


# ── 동시 접속 테스트 (텍스트) ────────────────────────────────────

@pytest.mark.load
@pytest.mark.timeout(300)
@pytest.mark.parametrize("n_users", [5, 10, 20])
def test_concurrent_text_submit(n_users: int):
    """
    N명 동시 텍스트 제출 — 전원 202 수신 및 제출 시간 분포 검증.

    ADR-019 기준: 텍스트 제출 30~50명 동시 처리 가능.
    graded 대기는 하지 않음 (Claude API 비용 최소화).
    """
    answers = [
        f"f'(x) = 3x^2 - 6x = 0에서 x=0 또는 x=2. 최솟값은 f(2) = -3이다. (제출 #{i})"
        for i in range(n_users)
    ]

    results: list[SubmitResult] = []
    wall_start = time.time()

    with ThreadPoolExecutor(max_workers=n_users) as pool:
        futures = [
            pool.submit(_submit_text, (i % 10) + 1, answers[i])
            for i in range(n_users)
        ]
        for f in as_completed(futures):
            results.append(f.result())

    wall_elapsed = time.time() - wall_start

    success = [r for r in results if r.status_code == 202]
    failed  = [r for r in results if r.status_code != 202]
    times   = sorted(r.elapsed_submit for r in success)

    print(f"\n[동시 {n_users}명 텍스트 제출]")
    print(f"  성공: {len(success)}/{n_users}  실패: {len(failed)}")
    if times:
        print(f"  응답시간 — 최소:{times[0]:.2f}s  중앙:{times[len(times)//2]:.2f}s  최대:{times[-1]:.2f}s")
    print(f"  전체 wall time: {wall_elapsed:.2f}s")

    assert len(failed) == 0, (
        f"{len(failed)}건 제출 실패 — "
        f"codes: {[r.status_code for r in failed]}, errors: {[r.error for r in failed]}"
    )
    # 모든 제출 응답이 5초 이내 (서버가 동기 처리하지 않는지 확인)
    assert times[-1] < 5.0, (
        f"최대 제출 응답 시간 5초 초과: {times[-1]:.2f}s — 서버 블로킹 의심"
    )


# ── 동시 접속 테스트 (이미지) ─────────────────────────────────────

@pytest.mark.load
@pytest.mark.timeout(120)
@pytest.mark.parametrize("n_users", [3, 5, 10])
def test_concurrent_image_submit(n_users: int):
    """
    N명 동시 이미지 제출 — 서버 오류(5xx) 없이 처리되는지 검증.

    OCR은 MPS 직렬 큐잉이므로 n_users가 클수록 큐잉 대기 발생.
    ADR-019/020 기준: 이미지 제출 10~15명 동시 처리 쾌적.
    5xx 응답은 절대 허용하지 않음.
    """
    results: list[SubmitResult] = []
    wall_start = time.time()

    with ThreadPoolExecutor(max_workers=n_users) as pool:
        futures = [pool.submit(_submit_image, (i % 10) + 1) for i in range(n_users)]
        for f in as_completed(futures):
            results.append(f.result())

    wall_elapsed = time.time() - wall_start

    server_errors = [r for r in results if r.status_code >= 500]
    accepted      = [r for r in results if r.status_code == 202]
    client_errors = [r for r in results if 400 <= r.status_code < 500]

    print(f"\n[동시 {n_users}명 이미지 제출]")
    print(f"  202 수락: {len(accepted)}  4xx(OCR미설치 등): {len(client_errors)}  5xx: {len(server_errors)}")
    print(f"  wall time: {wall_elapsed:.2f}s")

    assert len(server_errors) == 0, (
        f"서버 내부 오류 {len(server_errors)}건 — "
        f"status: {[r.status_code for r in server_errors]}"
    )

    if client_errors:
        warnings.warn(
            f"[SOFT] {len(client_errors)}건 4xx 응답 (OCR 엔진 미설치 가능성)",
            UserWarning,
        )


# ── E2E + graded 대기 (소규모) ────────────────────────────────────

@pytest.mark.load
@pytest.mark.timeout(600)
def test_concurrent_e2e_graded_5():
    """
    5명 동시 제출 → 전원 graded 상태 도달 시간 측정.

    Claude API를 실제 호출하므로 과금 발생.
    ADR-019 기준: 30명 동시 교실 운영을 위한 파이프라인 처리량 검증.
    """
    n_users = 5
    answers = [
        "f'(x) = 3x^2 - 6x = 0, x=0 또는 x=2. 최솟값 f(2) = -3.",
        "∫(0→2)(3x²-2x)dx = [x³-x²](0→2) = 4.",
        "등비수열 a₁=2, r²=9이므로 r=3, a₅=2·81=162.",
        "sin²θ + cos²θ = 1을 이용하면 tanθ = sinθ/cosθ = 3/4.",
        "이차방정식 x²-5x+6=0 → (x-2)(x-3)=0 → x=2 또는 x=3.",
    ]

    submit_results: list[SubmitResult] = []
    wall_start = time.time()

    # 동시 제출
    with ThreadPoolExecutor(max_workers=n_users) as pool:
        futures = [
            pool.submit(_submit_text, i + 1, answers[i])
            for i in range(n_users)
        ]
        for f in as_completed(futures):
            submit_results.append(f.result())

    submit_wall = time.time() - wall_start
    success = [r for r in submit_results if r.submission_id is not None]
    assert len(success) == n_users, f"제출 실패 {n_users - len(success)}건"

    # 병렬로 graded 대기
    graded_results: list[dict] = []
    with ThreadPoolExecutor(max_workers=n_users) as pool:
        futures = [pool.submit(_wait_graded, r.submission_id, 500) for r in success]
        for f in as_completed(futures):
            graded_results.append(f.result())

    total_wall = time.time() - wall_start
    graded_ok  = [r for r in graded_results if r.get("status") in ("graded", "approved")]
    timed_out  = [r for r in graded_results if r.get("status") == "timeout"]

    print(f"\n[{n_users}명 동시 E2E]")
    print(f"  제출 wall time:    {submit_wall:.2f}s")
    print(f"  전체(graded까지):  {total_wall:.2f}s")
    print(f"  graded 성공:       {len(graded_ok)}/{n_users}")
    print(f"  timeout:           {len(timed_out)}/{n_users}")

    assert len(timed_out) == 0, f"{len(timed_out)}건이 타임아웃 내에 graded 미도달"
    assert len(graded_ok) == n_users, f"graded 상태 미도달: {n_users - len(graded_ok)}건"


# ── 메모리 안정성 ────────────────────────────────────────────────

@pytest.mark.memory
@pytest.mark.timeout(600)
def test_memory_stability_repeated_submit():
    """
    50회 반복 제출(텍스트) 후 서버 메모리 누수 확인.

    /health 엔드포인트에 memory_mb 필드가 없으면 soft warning.
    메모리 증가가 초기 대비 50% 이상이면 누수 의심으로 실패.
    """
    n_repeat = 50
    answer   = "f'(x) = 3x^2 - 6x = 0에서 x=0 또는 x=2. 최솟값은 f(2) = -3."

    mem_before = _server_memory_mb()
    if mem_before < 0:
        warnings.warn(
            "[SOFT] /health에 memory_mb 필드 없음 — 메모리 누수 검증 불가",
            UserWarning,
        )

    errors = 0
    for i in range(n_repeat):
        result = _submit_text(problem_id=(i % 10) + 1, answer=answer)
        if result.status_code != 202:
            errors += 1
        time.sleep(0.2)  # 서버 부하 최소화

    mem_after = _server_memory_mb()

    print(f"\n[메모리 안정성 — {n_repeat}회 반복]")
    print(f"  제출 오류: {errors}/{n_repeat}")
    print(f"  메모리 before: {mem_before:.0f} MB  after: {mem_after:.0f} MB")

    assert errors == 0, f"반복 제출 중 {errors}건 오류 발생"

    if mem_before > 0 and mem_after > 0:
        growth_rate = (mem_after - mem_before) / mem_before
        print(f"  메모리 증가율: {growth_rate*100:.1f}%")
        assert growth_rate < 0.5, (
            f"메모리 50% 이상 증가 ({mem_before:.0f}→{mem_after:.0f} MB) — 누수 의심"
        )


@pytest.mark.memory
@pytest.mark.timeout(120)
def test_health_endpoint_stability():
    """
    /health 30회 반복 호출 — 응답 일관성 및 모델 상태 안정성 확인.
    간헐적 실패(모델 언로드 등) 탐지 목적.
    """
    failures = []
    for i in range(30):
        try:
            resp = requests.get(f"{BASE_URL}/health", timeout=5)
            data = resp.json()
            if resp.status_code != 200 or data.get("status") != "ok":
                failures.append(f"#{i}: status={resp.status_code} body={data}")
        except Exception as e:
            failures.append(f"#{i}: {e}")
        time.sleep(0.5)

    print(f"\n[헬스 안정성] 30회 중 실패: {len(failures)}")
    assert len(failures) == 0, f"헬스 체크 실패:\n" + "\n".join(failures)
