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

    desc = store.save_embedding_index(index)
    assert desc.blob_name.endswith("_embeddings.json")
    assert (tmp_path / desc.blob_name).exists()

    loaded = store.load_embedding_indices({sid}, model="test-model")
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


def test_save_embedding_index_returns_descriptor(tmp_path: Path) -> None:
    """save_embedding_index returns an EmbeddingDescriptor with model info."""
    store = ShardedArtifactStore(storage_dir=tmp_path)
    index = EmbeddingIndex(
        shard_id=ShardId("lib"),
        embeddings=[[1.0]],
        chunk_ids=["lib/a.py:f"],
        dimension=1,
        model="my-model",
    )

    desc = store.save_embedding_index(index)

    assert desc.shard_id == ShardId("lib")
    assert desc.model == "my-model"
    assert desc.dimension == 1
    assert desc.blob_name.endswith("_embeddings.json")


def test_different_models_produce_different_blobs(tmp_path: Path) -> None:
    """Switching models creates a different blob file, not overwriting."""
    store = ShardedArtifactStore(storage_dir=tmp_path)
    sid = ShardId("src")

    idx1 = EmbeddingIndex(
        shard_id=sid,
        embeddings=[[1.0, 0.0]],
        chunk_ids=["src/a.py:f"],
        dimension=2,
        model="model-a",
    )
    idx2 = EmbeddingIndex(
        shard_id=sid,
        embeddings=[[0.0, 1.0, 0.0]],
        chunk_ids=["src/a.py:f"],
        dimension=3,
        model="model-b",
    )

    desc1 = store.save_embedding_index(idx1)
    desc2 = store.save_embedding_index(idx2)

    assert desc1.blob_name != desc2.blob_name
    assert (tmp_path / desc1.blob_name).exists()
    assert (tmp_path / desc2.blob_name).exists()
