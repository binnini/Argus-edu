"""
hallucination.py — HHEM-2.1-Open 기반 할루시네이션 탐지 서비스.

로컬 실행 불가 이슈 (ADR-011 참조):
  HHEM-2.1-Open의 커스텀 코드가 transformers 4.x / 5.x 모두와 호환 문제 발생.
  → Hugging Face Inference API로 대체.

HF Inference API 미설정 시 (HF_TOKEN 없음):
  SBERT 코사인 유사도만으로 fallback 스코어 반환.
"""

import logging
import os
from dataclasses import dataclass

logger = logging.getLogger(__name__)

HHEM_MODEL_ID = "vectara/hallucination_evaluation_model"
HF_TOKEN = os.getenv("HF_TOKEN", "")


@dataclass
class HHEMOutput:
    score: float          # 팩추얼 일관성 스코어 (0~1, 높을수록 신뢰)
    label: str            # "consistent" | "hallucinated" | "fallback"
    source: str           # "hf_api" | "sbert_fallback"


class HallucinationDetector:
    """
    HHEM-2.1-Open 래퍼 (HF Inference API 사용).
    HF_TOKEN 없을 경우 SBERT fallback 사용.
    """

    def __init__(self, sbert_model=None) -> None:
        """
        sbert_model: SentenceTransformer — HF API 실패 시 fallback용.
        """
        self._sbert = sbert_model
        self._use_api = bool(HF_TOKEN)

        if self._use_api:
            logger.info("HHEM: HF Inference API 모드")
        else:
            logger.warning(
                "HF_TOKEN 미설정 — SBERT fallback 모드 사용. "
                ".env에 HF_TOKEN을 설정하면 HHEM 정밀도가 높아집니다."
            )

    def score(self, premise: str, hypothesis: str) -> HHEMOutput:
        """팩추얼 일관성 스코어 계산."""
        if self._use_api:
            return self._score_via_hf_api(premise, hypothesis)
        return self._score_via_sbert_fallback(premise, hypothesis)

    def score_grading(self, reference_solution: str, grading_reason: str) -> HHEMOutput:
        return self.score(premise=reference_solution, hypothesis=grading_reason)

    def score_explanation(self, reference_solution: str, explanation_text: str) -> HHEMOutput:
        return self.score(premise=reference_solution, hypothesis=explanation_text)

    def _score_via_hf_api(self, premise: str, hypothesis: str) -> HHEMOutput:
        """HF Inference API 호출."""
        try:
            from huggingface_hub import InferenceClient
            client = InferenceClient(token=HF_TOKEN)
            result = client.text_classification(
                f"{premise} </s> {hypothesis}",
                model=HHEM_MODEL_ID,
            )
            # result: [{"label": "consistent"/"hallucinated", "score": float}]
            top = result[0]
            label = top["label"].lower()
            raw_score = top["score"]
            final_score = raw_score if label == "consistent" else 1.0 - raw_score
            return HHEMOutput(
                score=round(float(final_score), 4),
                label=label,
                source="hf_api",
            )
        except Exception as e:
            logger.warning(f"HF API 호출 실패, SBERT fallback 사용: {e}")
            return self._score_via_sbert_fallback(premise, hypothesis)

    def _score_via_sbert_fallback(self, premise: str, hypothesis: str) -> HHEMOutput:
        """
        SBERT 코사인 유사도 기반 fallback.
        정밀도는 HHEM보다 낮지만 로컬에서 항상 실행 가능.
        """
        if self._sbert is None:
            logger.warning("SBERT 모델 없음 — 기본값 0.5 반환")
            return HHEMOutput(score=0.5, label="fallback", source="sbert_fallback")

        try:
            import numpy as np
            embeddings = self._sbert.encode(
                [premise, hypothesis],
                convert_to_numpy=True,
                normalize_embeddings=True,
            )
            sim = float(np.dot(embeddings[0], embeddings[1]))
            sim = max(0.0, min(1.0, sim))
            label = "consistent" if sim >= 0.7 else "hallucinated"
            return HHEMOutput(score=round(sim, 4), label=label, source="sbert_fallback")
        except Exception as e:
            logger.warning(f"SBERT fallback 실패: {e}")
            return HHEMOutput(score=0.5, label="fallback", source="sbert_fallback")


def load_hhem_detector(sbert_model=None) -> HallucinationDetector:
    """
    HallucinationDetector 인스턴스 생성.
    main.py lifespan에서 1회 호출.
    """
    detector = HallucinationDetector(sbert_model=sbert_model)
    return detector
