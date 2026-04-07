"""
tests/conftest.py — 통합 테스트 공통 설정
"""

import pytest
import requests

BASE_URL = "http://localhost:8000"
TEACHER_PASSWORD = "argus-dev"


@pytest.fixture(scope="session")
def session():
    """재사용 가능한 requests 세션."""
    s = requests.Session()
    yield s
    s.close()


@pytest.fixture(scope="session")
def teacher_headers():
    """교사 인증 헤더."""
    return {"X-Teacher-Password": TEACHER_PASSWORD}
