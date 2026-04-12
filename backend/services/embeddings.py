"""Local text embedding wrapper compatible with transformers 5.x."""

from __future__ import annotations

from typing import Protocol

import numpy as np
import torch
import torch.nn.functional as F
from transformers import AutoModel, AutoTokenizer


class EmbeddingModel(Protocol):
    """Minimal interface used by grading and hallucination services."""

    def encode(
        self,
        texts: list[str] | str,
        convert_to_numpy: bool = True,
        normalize_embeddings: bool = True,
    ) -> np.ndarray:
        """Encode text into sentence embeddings."""
        ...


class LocalEmbeddingModel:
    """Mean-pooling sentence embedding model loaded via transformers."""

    def __init__(self, model_name: str) -> None:
        self._tokenizer = AutoTokenizer.from_pretrained(model_name)
        self._model = AutoModel.from_pretrained(model_name)
        self._model.eval()

    def encode(
        self,
        texts: list[str] | str,
        convert_to_numpy: bool = True,
        normalize_embeddings: bool = True,
    ) -> np.ndarray:
        inputs = [texts] if isinstance(texts, str) else texts
        if not inputs:
            return np.array([])

        with torch.inference_mode():
            batch = self._tokenizer(
                inputs,
                padding=True,
                truncation=True,
                return_tensors="pt",
            )
            outputs = self._model(**batch)
            token_embeddings = outputs.last_hidden_state
            attention_mask = batch["attention_mask"].unsqueeze(-1).expand(token_embeddings.size())
            masked_embeddings = token_embeddings * attention_mask
            summed = masked_embeddings.sum(dim=1)
            counts = attention_mask.sum(dim=1).clamp(min=1e-9)
            embeddings = summed / counts
            if normalize_embeddings:
                embeddings = F.normalize(embeddings, p=2, dim=1)

        if convert_to_numpy:
            return embeddings.cpu().numpy()
        return embeddings
