from __future__ import annotations
import numpy as np
import pytest

from triforge._embedder import EMBED_DIM, embed, embed_batch


@pytest.mark.slow
def test_embed_single_returns_256dim_vector() -> None:
    v = embed("hello world")
    assert isinstance(v, np.ndarray)
    assert v.shape == (EMBED_DIM,)
    assert v.dtype == np.float32


@pytest.mark.slow
def test_embed_batch_returns_matrix() -> None:
    m = embed_batch(["a", "b", "c"])
    assert m.shape == (3, EMBED_DIM)


@pytest.mark.slow
def test_same_text_same_vector() -> None:
    v1 = embed("identical")
    v2 = embed("identical")
    assert np.allclose(v1, v2)
