"""
seed.py — data/problems/aihub_*.json 파일을 읽어 PostgreSQL DB에 삽입하는 스크립트.

기존 problems 데이터를 삭제(truncate cascade)하고 새 데이터를 삽입한다.

사용법:
    cd /Users/yebin/workSpace/Argus
    source .venv/bin/activate
    python scripts/seed.py
"""

import asyncio
import json
import os
import sys
from pathlib import Path

# backend/ 디렉토리를 경로에 추가
sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from models import Problem
from models.base import Base

DATABASE_URL = os.getenv(
    "DATABASE_URL", "postgresql+asyncpg://yebin@localhost/argus_dev"
)

DATA_DIR = Path(__file__).parent.parent / "data" / "problems"


def build_problem(data: dict) -> Problem:
    """JSON 데이터 → Problem ORM 객체 변환."""
    ref_sol = data["reference_solution"]
    # reference_solution이 dict면 JSON 문자열로 변환
    if isinstance(ref_sol, dict):
        ref_sol = json.dumps(ref_sol, ensure_ascii=False)

    return Problem(
        title=str(data["title"]),
        content=data["content"],
        answer=str(data["answer"])[:500],  # answer 컬럼 길이 대비 안전 처리
        reference_solution=ref_sol,
        rubric=data["rubric"],
        domain=data.get("domain", "고등학교_공통수학"),
        difficulty=data.get("difficulty", 3),
        source=data.get("source"),
    )


async def seed() -> None:
    engine = create_async_engine(DATABASE_URL, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    # aihub_*.json 파일 수집
    problem_files = sorted(DATA_DIR.glob("aihub_*.json"))
    if not problem_files:
        print(f"[ERROR] aihub_*.json 파일 없음: {DATA_DIR}")
        return

    problems: list[Problem] = []
    for file_path in problem_files:
        with open(file_path, encoding="utf-8") as f:
            data_list = json.load(f)
        for data in data_list:
            problems.append(build_problem(data))
        print(f"[INFO] {file_path.name}: {len(data_list)}개 로드")

    async with async_session() as session:
        # 기존 데이터 삭제 (cascade)
        await session.execute(text("TRUNCATE TABLE problems RESTART IDENTITY CASCADE"))
        await session.commit()
        print("[INFO] 기존 problems 데이터 삭제 완료")

        # 배치 삽입 (1000개씩)
        batch_size = 1000
        for i in range(0, len(problems), batch_size):
            batch = problems[i : i + batch_size]
            session.add_all(batch)
            await session.commit()
            print(f"[INFO] {i + len(batch)}/{len(problems)} 삽입 완료")

        print(f"[INFO] 총 {len(problems)}개 문제 삽입 완료")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(seed())
