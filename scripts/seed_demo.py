"""
seed_demo.py — AI-HUB TS_3 손글씨 이미지를 추출하여 demo submissions를 DB에 삽입.

사용법:
    cd /Users/yebin/workSpace/Argus
    source .venv/bin/activate
    python scripts/seed_demo.py

효과:
    - data/demo/images/ 에 손글씨 JPEG 저장
    - DB에 submissions + grading_results + teacher_queue 삽입
    - 교사 대시보드에서 즉시 검토 가능한 demo 상태 구성
"""

import asyncio
import json
import os
import sys
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

DATABASE_URL = os.getenv(
    "DATABASE_URL", "postgresql+asyncpg://yebin@localhost/argus_dev"
)

BASE_DIR = Path(__file__).parent.parent
TS3_DIR = BASE_DIR / "data" / "AI_HUB" / "3.개방데이터" / "1.데이터" / "Training" / "01.원천데이터"
TL3_DIR = BASE_DIR / "data" / "AI_HUB" / "3.개방데이터" / "1.데이터" / "Training" / "02.라벨링데이터"
DEMO_IMG_DIR = BASE_DIR / "data" / "demo" / "images"

# 학년별 대표 문제 설정 (DB id, problem_title, 원천/라벨 ZIP 이름)
DEMO_PROBLEMS = [
    {
        "db_id": 7,
        "title": "21169_50030",
        "label": "초등학교 3학년 · 세 자리 수의 덧셈",
        "ts3_zip": "TS_3.손글씨풀이_초등학교_3학년.zip",
        "tl3_zip": "TL_3.손글씨풀이_초등학교_3학년.zip",
        "grade_dir": "초등3",
    },
    {
        "db_id": 11054,
        "title": "27082_90417",
        "label": "초등학교 6학년 · 분수 나눗셈",
        "ts3_zip": "TS_3.손글씨풀이_초등학교_6학년.zip",
        "tl3_zip": "TL_3.손글씨풀이_초등학교_6학년.zip",
        "grade_dir": "초등6",
    },
    {
        "db_id": 15230,
        "title": "21711_51446",
        "label": "중학교 1학년 · 소수와 합성수",
        "ts3_zip": "TS_3.손글씨풀이_중학교_1학년.zip",
        "tl3_zip": "TL_3.손글씨풀이_중학교_1학년.zip",
        "grade_dir": "중1",
    },
    {
        "db_id": 22878,
        "title": "11963_116258",
        "label": "중학교 3학년 · 제곱근과 도형",
        "ts3_zip": "TS_3.손글씨풀이_중학교_3학년.zip",
        "tl3_zip": "TL_3.손글씨풀이_중학교_3학년.zip",
        "grade_dir": "중3",
    },
    {
        "db_id": 27056,
        "title": "25772_84222",
        "label": "고등학교 공통수학 · 다항식",
        "ts3_zip": "TS_3.손글씨풀이_고등학교_공통수학.zip",
        "tl3_zip": "TL_3.손글씨풀이_고등학교_공통수학.zip",
        "grade_dir": "고등",
    },
]

# 가상 학생 3명
DEMO_STUDENTS = [
    {"name": "김민준", "id": "20240001"},
    {"name": "이서연", "id": "20240002"},
    {"name": "박지호", "id": "20240003"},
]

# mock AI feedback (문제별로 동일 구조, 내용은 generic)
def make_ai_feedback(is_correct: bool, domain: str) -> str:
    if is_correct:
        return json.dumps(
            {
                "student_mistakes": [],
                "correct_approach": [
                    {
                        "step": 1,
                        "title": "핵심 개념 파악",
                        "content": f"{domain} 개념을 정확히 이해하고 적용했습니다.",
                    }
                ],
                "key_concept": f"{domain}의 기본 원리를 올바르게 적용",
            },
            ensure_ascii=False,
        )
    else:
        return json.dumps(
            {
                "student_mistakes": [
                    {"step": 1, "description": f"{domain} 과정에서 계산 오류가 발생했습니다."}
                ],
                "correct_approach": [
                    {
                        "step": 1,
                        "title": "개념 재확인",
                        "content": f"{domain}의 절차를 순서대로 다시 적용합니다.",
                    },
                    {
                        "step": 2,
                        "title": "풀이 검산",
                        "content": "최종 답을 원래 조건에 대입하여 검산합니다.",
                    },
                ],
                "key_concept": f"{domain} — 단계별 절차를 놓치지 않도록 주의",
            },
            ensure_ascii=False,
        )


def extract_images(problem: dict) -> list[dict]:
    """TS_3 ZIP에서 해당 problem의 이미지를 추출하여 로컬 저장 후 메타 반환."""
    ts3_path = TS3_DIR / problem["ts3_zip"]
    tl3_path = TL3_DIR / problem["tl3_zip"]
    pid = problem["title"]

    if not ts3_path.exists():
        print(f"  [SKIP] {ts3_path.name} 없음")
        return []

    dest_dir = DEMO_IMG_DIR / problem["grade_dir"]
    dest_dir.mkdir(parents=True, exist_ok=True)

    # TL_3에서 OCR 텍스트 수집 (student_answer 용)
    ocr_texts: dict[str, str] = {}
    if tl3_path.exists():
        with zipfile.ZipFile(tl3_path) as zf:
            for fname in zf.namelist():
                if pid in fname and fname.endswith(".json"):
                    data = json.loads(zf.read(fname))
                    # answer_info 첫 번째 항목의 answer_text
                    ai = data.get("answer_info", [])
                    if ai:
                        # student writing text (not model answer)
                        student_writing = ai[0].get("answer_text", "")
                        base = Path(fname).name.replace(".json", "")
                        ocr_texts[base] = student_writing

    results = []
    with zipfile.ZipFile(ts3_path) as zf:
        all_files = [f for f in zf.namelist() if pid in f]
        o_files = [f for f in all_files if "_O." in f][:2]
        x_files = [f for f in all_files if "_X." in f][:1]

        for fpath in o_files + x_files:
            fname = Path(fpath).name
            dest = dest_dir / fname
            if not dest.exists():
                dest.write_bytes(zf.read(fpath))

            base = fname.replace(".jpeg", "")
            is_correct = "_O." in fname
            results.append(
                {
                    "image_path": str(dest.relative_to(BASE_DIR)),
                    "ocr_text": ocr_texts.get(base, ""),
                    "is_correct": is_correct,
                }
            )

    print(f"  → {len(results)}개 이미지 추출 ({dest_dir})")
    return results


async def seed_demo() -> None:
    engine = create_async_engine(DATABASE_URL, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    now = datetime.now(timezone.utc)

    async with async_session() as session:
        # 기존 demo 데이터 정리 (student_id가 2024로 시작하는 것)
        await session.execute(
            text(
                """
                DELETE FROM feedback_log
                WHERE submission_id IN (
                    SELECT id FROM submissions WHERE student_id LIKE '2024%'
                )
                """
            )
        )
        await session.execute(
            text(
                """
                DELETE FROM teacher_queue
                WHERE submission_id IN (
                    SELECT id FROM submissions WHERE student_id LIKE '2024%'
                )
                """
            )
        )
        await session.execute(
            text(
                """
                DELETE FROM grading_results
                WHERE submission_id IN (
                    SELECT id FROM submissions WHERE student_id LIKE '2024%'
                )
                """
            )
        )
        await session.execute(
            text("DELETE FROM submissions WHERE student_id LIKE '2024%'")
        )
        await session.commit()
        print("[INFO] 기존 demo 데이터 정리 완료")

        # 문제별 domain 조회
        domains: dict[int, str] = {}
        rows = await session.execute(
            text("SELECT id, domain FROM problems WHERE id = ANY(:ids)"),
            {"ids": [p["db_id"] for p in DEMO_PROBLEMS]},
        )
        for r in rows:
            domains[r[0]] = r[1]

        student_idx = 0
        total = 0

        for problem in DEMO_PROBLEMS:
            print(f"\n[{problem['label']}] (db_id={problem['db_id']})")
            images = extract_images(problem)
            if not images:
                continue

            domain = domains.get(problem["db_id"], "수학")

            for img in images:
                student = DEMO_STUDENTS[student_idx % len(DEMO_STUDENTS)]
                student_idx += 1

                is_correct = img["is_correct"]
                ai_score = 1 if is_correct else 0
                trust_score = 0.88 if is_correct else 0.52
                trust_level = "high" if is_correct else "low"
                queue_type = "score_only" if is_correct else "full_review"

                # 제출 시각 분산 (0~48시간 전)
                submitted_at = now - timedelta(hours=total * 4 + 2)
                sla_deadline = submitted_at + timedelta(hours=24)

                # submissions 삽입
                result = await session.execute(
                    text(
                        """
                        INSERT INTO submissions
                            (problem_id, student_answer, submitted_at, status,
                             input_type, ocr_raw_text, image_path,
                             student_name, student_id)
                        VALUES
                            (:problem_id, :student_answer, :submitted_at, 'graded',
                             'image', :ocr_raw_text, :image_path,
                             :student_name, :student_id)
                        RETURNING id
                        """
                    ),
                    {
                        "problem_id": problem["db_id"],
                        "student_answer": img["ocr_text"] or "(손글씨 이미지 제출)",
                        "submitted_at": submitted_at,
                        "ocr_raw_text": img["ocr_text"],
                        "image_path": img["image_path"],
                        "student_name": student["name"],
                        "student_id": student["id"],
                    },
                )
                submission_id = result.scalar_one()

                # grading_results 삽입
                await session.execute(
                    text(
                        """
                        INSERT INTO grading_results
                            (submission_id, ai_score, ai_feedback,
                             sbert_similarity, hhem_score, inconsistency_rate,
                             trust_score, trust_level, graded_at)
                        VALUES
                            (:submission_id, :ai_score, :ai_feedback,
                             :sbert_similarity, :hhem_score, :inconsistency_rate,
                             :trust_score, :trust_level, :graded_at)
                        """
                    ),
                    {
                        "submission_id": submission_id,
                        "ai_score": ai_score,
                        "ai_feedback": make_ai_feedback(is_correct, domain),
                        "sbert_similarity": 0.82 if is_correct else 0.41,
                        "hhem_score": 0.90 if is_correct else 0.60,
                        "inconsistency_rate": 0.05 if is_correct else 0.38,
                        "trust_score": trust_score,
                        "trust_level": trust_level,
                        "graded_at": submitted_at + timedelta(seconds=3),
                    },
                )

                # teacher_queue 삽입 (일부는 미검토, 일부는 검토 완료)
                action = None
                teacher_score = None
                teacher_feedback = None
                reviewed_at = None

                # 첫 번째 이미지(O)는 이미 approve 처리, 나머지는 pending
                if total == 0:
                    action = "approve"
                    teacher_score = ai_score
                    teacher_feedback = None
                    reviewed_at = submitted_at + timedelta(minutes=15)

                await session.execute(
                    text(
                        """
                        INSERT INTO teacher_queue
                            (submission_id, queue_type, sla_deadline,
                             action, teacher_score, teacher_feedback, reviewed_at,
                             queued_at)
                        VALUES
                            (:submission_id, :queue_type, :sla_deadline,
                             :action, :teacher_score, :teacher_feedback, :reviewed_at,
                             :queued_at)
                        """
                    ),
                    {
                        "submission_id": submission_id,
                        "queue_type": queue_type,
                        "sla_deadline": sla_deadline,
                        "action": action,
                        "teacher_score": teacher_score,
                        "teacher_feedback": teacher_feedback,
                        "reviewed_at": reviewed_at,
                        "queued_at": submitted_at + timedelta(seconds=5),
                    },
                )

                status_str = f"{'정답' if is_correct else '오답'} / trust={trust_level}"
                print(f"  submission_id={submission_id} {student['name']} ({status_str})")
                total += 1

        await session.commit()
        print(f"\n[완료] demo submissions {total}개 삽입")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(seed_demo())
