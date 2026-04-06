import os

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # DB
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost/argus_dev"

    # Anthropic
    anthropic_api_key: str = ""

    # AI 모델 — 절대 하드코딩 금지, 환경변수에서 로드
    grading_model: str = "claude-sonnet-4-6"
    explanation_model: str = "claude-sonnet-4-6"

    # 신뢰도 게이트
    trust_threshold: float = 0.75

    # SLA (시간 단위)
    sla_high_risk_hours: int = 12
    sla_normal_hours: int = 24

    # 교사 인증
    teacher_password: str = "changeme"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
