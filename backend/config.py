import os

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # DB
    database_url: str = "postgresql+asyncpg://argus@localhost/argus"

    # Anthropic
    anthropic_api_key: str = ""

    # LLM 제공자 — "anthropic" | "ollama" | "mlx"
    llm_provider: str = "anthropic"

    # 배치 할루시네이션 검증 간격 (초) — APScheduler
    hallucination_batch_interval_seconds: int = 300  # 5분

    # Ollama (llm_provider="ollama" 시 사용)
    ollama_base_url: str = "http://localhost:11434"

    # MLX (llm_provider="mlx" 시 사용)
    mlx_model_path: str = "unsloth/gemma-4-E4B-it-MLX-8bit"
    mlx_grading_model_path: str = ""
    mlx_feedback_model_path: str = ""
    mlx_hallucination_model_path: str = ""
    mlx_max_tokens: int = 4096  # thinking 비활성화 시에도 수식 풀이 여유 확보

    # AI 모델 — 절대 하드코딩 금지, 환경변수에서 로드
    # 현재 운영 경로는 FEEDBACK_MODEL + HALLUCINATION_MODEL 사용
    # (GRADING_MODEL은 레거시 LLM 채점 경로 호환용)
    embedding_model_name: str = "sentence-transformers/all-MiniLM-L6-v2"
    grading_model: str = "claude-sonnet-4-6"
    feedback_model: str = "claude-sonnet-4-6"
    hallucination_model: str = ""
    ocr_model: str = "pix2tex"  # pix2tex | mathpix | got_ocr

    # OCR 모델 경로 (got_ocr 사용 시)
    got_ocr_model_path: str = ""
    got_ocr_worker_python: str = (
        "/opt/homebrew/Caskroom/miniconda/base/envs/argus-gotocr/bin/python"
    )
    # Mathpix API 인증 (mathpix 사용 시)
    mathpix_app_id: str = ""
    mathpix_app_key: str = ""

    # 이미지 업로드
    upload_dir: str = "uploads"
    allowed_image_content_types: set[str] = {"image/jpeg", "image/png", "image/webp", "image/gif"}
    max_image_size_bytes: int = 10 * 1024 * 1024

    # 신뢰도 게이트
    trust_threshold: float = 0.75

    # LLM 타임아웃 (초) — Ollama 로컬 모델은 thinking으로 느릴 수 있음
    # gemma4:26b 풀이 설명 프롬프트 실측 ~2분 → 300초로 여유 확보
    llm_timeout_seconds: float = 300.0

    # Durable job lock 복구 기준 (초)
    job_stale_after_seconds: int = 600

    # SLA (시간 단위)
    sla_high_risk_hours: int = 12
    sla_normal_hours: int = 24

    # 교사 인증
    teacher_password: str = "changeme"

    model_config = {
        "env_file": ("../.env", ".env"),  # backend/ 또는 루트 모두 탐색
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }


settings = Settings()
