"""Utilities for resolving and sanitizing MLX model directories."""

from __future__ import annotations

import json
import logging
from pathlib import Path

from huggingface_hub import snapshot_download

logger = logging.getLogger(__name__)

# Known tensor that surfaced shape conflicts in mixed snapshots.
_PROBE_KEY = "language_model.model.per_layer_model_projection.weight"


def resolve_mlx_model_path(model_ref: str) -> str:
    """Return a local model directory path for mlx_lm.load()."""
    if not model_ref:
        return model_ref

    local = Path(model_ref).expanduser()
    if local.exists():
        _sanitize_mixed_snapshot(local)
        return str(local)

    if "/" not in model_ref:
        return model_ref

    downloaded = Path(snapshot_download(repo_id=model_ref))
    _sanitize_mixed_snapshot(downloaded)
    return str(downloaded)


def _sanitize_mixed_snapshot(model_dir: Path) -> None:
    """Handle mixed single-file + sharded snapshots with inconsistent tensor shapes."""
    index_path = model_dir / "model.safetensors.index.json"
    single_path = model_dir / "model.safetensors"
    if not index_path.exists() or not single_path.exists():
        return

    try:
        from safetensors import safe_open

        index = json.loads(index_path.read_text(encoding="utf-8"))
        shard_name = index.get("weight_map", {}).get(_PROBE_KEY)
        if not shard_name:
            return

        shard_path = model_dir / shard_name
        if not shard_path.exists():
            return

        with safe_open(str(single_path), framework="pt") as single_f:
            if _PROBE_KEY not in single_f.keys():
                return
            single_shape = tuple(single_f.get_slice(_PROBE_KEY).get_shape())

        with safe_open(str(shard_path), framework="pt") as shard_f:
            if _PROBE_KEY not in shard_f.keys():
                return
            shard_shape = tuple(shard_f.get_slice(_PROBE_KEY).get_shape())

        if single_shape == shard_shape:
            return

        backup = model_dir / "model.safetensors.conflict.bak"
        if backup.exists():
            backup.unlink()
        single_path.rename(backup)
        logger.warning(
            "Detected mixed MLX snapshot with incompatible tensor shape: single=%s shard=%s. "
            "Moved %s -> %s to force sharded load.",
            single_shape,
            shard_shape,
            single_path,
            backup,
        )
    except Exception as exc:
        logger.warning("Failed to sanitize MLX snapshot at %s: %s", model_dir, exc)
