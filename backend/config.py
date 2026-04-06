import os

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # DB
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost/argus_dev"

    # Anthropic
    anthropic_api_key: str = ""

    # LLM 제공자 — "anthropic" | "ollama"
    llm_provider: str = "anthropic"

    # Ollama (llm_provider="ollama" 시 사용)
    ollama_base_url: str = "http://localhost:11434"

    # AI 모델 — 절대 하드코딩 금지, 환경변수에서 로드
    # ollama 사용 시: GRADING_MODEL=gemma4:26b 등으로 변경
    grading_model: str = "claude-sonnet-4-6"
    explanation_model: str = "claude-sonnet-4-6"

    # 신뢰도 게이트
    trust_threshold: float = 0.75

    # LLM 타임아웃 (초) — Ollama 로컬 모델은 thinking으로 느릴 수 있음
    llm_timeout_seconds: float = 120.0

    # SLA (시간 단위)
    sla_high_risk_hours: int = 12
    sla_normal_hours: int = 24

    # 교사 인증
    teacher_password: str = "changeme"

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore",  # VITE_* 등 프론트엔드 전용 환경변수 무시
    }


settings = Settings()
