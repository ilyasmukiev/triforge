"""Lazy-loaded model2vec embedder singleton (potion-base-8M, 256-dim)."""
from __future__ import annotations

from collections.abc import Sequence
from functools import lru_cache

import numpy as np
from model2vec import StaticModel

DEFAULT_MODEL_NAME = "minishlab/potion-base-8M"
EMBED_DIM = 256


@lru_cache(maxsize=1)
def _model(model_name: str = DEFAULT_MODEL_NAME) -> StaticModel:
    return StaticModel.from_pretrained(model_name)


def embed(text: str) -> np.ndarray:
    """Single text → 1-D float32 vector of length EMBED_DIM."""
    v = _model().encode([text])[0].astype(np.float32, copy=False)
    return v


def embed_batch(texts: Sequence[str]) -> np.ndarray:
    """Batch encode → 2-D float32 matrix (N × EMBED_DIM)."""
    return _model().encode(list(texts)).astype(np.float32, copy=False)
