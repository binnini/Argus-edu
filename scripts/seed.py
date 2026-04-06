"""
seed.py — data/problems/ JSON 파일을 읽어 PostgreSQL DB에 삽입하는 스크립트.

사용법:
    cd backend
    python ../scripts/seed.py
"""

import asyncio
import json
import os
import sys
from pathlib import Path

# backend/ 디렉토리를 경로에 추가
sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from models import Problem
from models.base import Base

DATABASE_URL = os.getenv(
    "DATABASE_URL", "postgresql+asyncpg://postgres:postgres@localhost/argus_dev"
)

DATA_DIR = Path(__file__).parent.parent / "data" / "problems"

PROBLEM_FILES = [
    DATA_DIR / "math2_differentiation.json",
    DATA_DIR / "math2_integration.json",
    DATA_DIR / "stats_probability.json",
]


def build_problem(data: dict) -> Problem:
    """JSON 데이터 → Problem ORM 객체 변환."""
    import json as json_module

    return Problem(
        title=data["id"],
        content=data["content"],
        answer=data["answer"],
        reference_solution=json_module.dumps(
            data["reference_solution"], ensure_ascii=False
        ),
        rubric=data["rubric"],
        domain=data["domain"],
        difficulty=data["difficulty"],
    )


async def seed() -> None:
    engine = create_async_engine(DATABASE_URL, echo=True)

    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    problems: list[Problem] = []
    for file_path in PROBLEM_FILES:
        if not file_path.exists():
            print(f"[WARN] 파일 없음: {file_path}")
            continue
        with open(file_path, encoding="utf-8") as f:
            data_list = json.load(f)
        for data in data_list:
            # test_answers는 DB에 저장하지 않음 (dataset.md 기준)
            problems.append(build_problem(data))
        print(f"[INFO] {file_path.name}: {len(data_list)}개 로드")

    async with async_session() as session:
        session.add_all(problems)
        await session.commit()
        print(f"[INFO] 총 {len(problems)}개 문제 삽입 완료")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(seed())
