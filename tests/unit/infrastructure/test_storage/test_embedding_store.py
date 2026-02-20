"""Tests for embedding index persistence in ShardedArtifactStore."""

from __future__ import annotations

from pathlib import Path

from argus.domain.context.value_objects import EmbeddingIndex, ShardId
from argus.infrastructure.storage.artifact_store import ShardedArtifactStore


def test_save_and_load_embedding_index(tmp_path: Path) -> None:
    store = ShardedArtifactStore(storage_dir=tmp_path)
    sid = ShardId("src/utils")

    index = EmbeddingIndex(
        shard_id=sid,
        embeddings=[[1.0, 0.0], [0.0, 1.0]],
        chunk_ids=["src/utils/a.py:func_a", "src/utils/b.py:func_b"],
        dimension=2,
        model="test-model",
    )

    blob_name = store.save_embedding_index(index)
    assert blob_name.endswith("_embeddings.json")
    assert (tmp_path / blob_name).exists()

    loaded = store.load_embedding_indices({sid})
    assert len(loaded) == 1
    assert loaded[0].shard_id == sid
    assert loaded[0].embeddings == [[1.0, 0.0], [0.0, 1.0]]
    assert loaded[0].chunk_ids == [
        "src/utils/a.py:func_a",
        "src/utils/b.py:func_b",
    ]
    assert loaded[0].dimension == 2
    assert loaded[0].model == "test-model"


def test_load_embedding_indices_missing_shard(tmp_path: Path) -> None:
    store = ShardedArtifactStore(storage_dir=tmp_path)
    loaded = store.load_embedding_indices({ShardId("nonexistent")})
    assert loaded == []
