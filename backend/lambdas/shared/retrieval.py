"""
retrieval.py — In-memory vector retrieval con numpy.

Por qué numpy en vez de OpenSearch Serverless:
  - Para una KB chica (<5k chunks) numpy en RAM gana en latencia (50ms vs 200ms).
  - Costo: $0. OpenSearch Serverless cuesta $350+/mes por sus 2 OCUs mínimas.
  - Cero infra nueva: el índice vive como dos archivos en S3.

Trade-off:
  - No escala más allá de unos 50k chunks (RAM Lambda).
  - No tiene BM25 nativo — implementamos un keyword-match cheap como complemento.
  - Si el índice supera 10MB, considerá usar S3 Select o switch a vector DB.

Estructura del índice en S3:
  s3://<KB_BUCKET>/_index/vectors.npy   ← matriz (N, 1024) float32
  s3://<KB_BUCKET>/_index/chunks.json   ← lista de {text, source, metadata}

Carga: una sola vez por cold start (cacheado a nivel módulo).
"""

from __future__ import annotations

import io
import json
import logging
import os
import re
from dataclasses import dataclass
from typing import Any

import boto3
import numpy as np

from .bedrock_client import get_client

logger = logging.getLogger(__name__)

KB_BUCKET = os.environ.get("KB_BUCKET", "")
INDEX_VECTORS_KEY = "_index/vectors.npy"
INDEX_CHUNKS_KEY = "_index/chunks.json"

s3 = boto3.client("s3")


@dataclass
class Chunk:
    text: str
    source: str
    score: float
    metadata: dict[str, Any]


# Module-level cache. Lambda re-uses the container across invocations,
# so the index loads once per cold start and stays warm.
_vectors: np.ndarray | None = None
_chunks: list[dict[str, Any]] | None = None


def _load_index() -> tuple[np.ndarray, list[dict[str, Any]]] | None:
    """Lazy-load the index from S3. Returns None if not built yet."""
    global _vectors, _chunks
    if _vectors is not None and _chunks is not None:
        return _vectors, _chunks
    if not KB_BUCKET:
        logger.warning("KB_BUCKET not set; retrieval disabled.")
        return None
    try:
        # vectors.npy
        vec_obj = s3.get_object(Bucket=KB_BUCKET, Key=INDEX_VECTORS_KEY)
        _vectors = np.load(io.BytesIO(vec_obj["Body"].read()))
        # chunks.json
        ch_obj = s3.get_object(Bucket=KB_BUCKET, Key=INDEX_CHUNKS_KEY)
        _chunks = json.loads(ch_obj["Body"].read().decode("utf-8"))
        logger.info("index loaded: %d chunks, dim=%d", len(_chunks), _vectors.shape[1])
        return _vectors, _chunks
    except s3.exceptions.NoSuchKey:
        logger.warning("Index not built yet (no %s in bucket)", INDEX_VECTORS_KEY)
        return None
    except Exception as e:
        logger.exception("failed to load index: %s", e)
        return None


def _keyword_score(query: str, text: str) -> float:
    """Tiny BM25-ish boost: rewards exact-term matches (tickers, IDs, code)."""
    q_terms = [t for t in re.findall(r"\w+", query.lower()) if len(t) >= 3]
    if not q_terms:
        return 0.0
    text_lower = text.lower()
    hits = sum(1 for t in q_terms if t in text_lower)
    return hits / len(q_terms)


def hybrid_search(query: str, top_k: int = 4) -> list[Chunk]:
    """
    Hybrid: cosine similarity (vector) + keyword score (BM25-lite).
    Final score = 0.7 * cosine + 0.3 * keyword.
    """
    loaded = _load_index()
    if loaded is None:
        return []
    vectors, chunks = loaded

    # Embed query
    bedrock = get_client()
    q_vec = np.asarray(bedrock.embed(query), dtype=np.float32)
    q_norm = np.linalg.norm(q_vec)
    if q_norm > 0:
        q_vec = q_vec / q_norm

    # Cosine (vectors are pre-normalized at ingest time → dot product = cosine)
    cosine = vectors @ q_vec  # shape (N,)

    # Keyword boost per chunk
    kw = np.array([_keyword_score(query, c["text"]) for c in chunks], dtype=np.float32)

    final = 0.7 * cosine + 0.3 * kw

    # Top-K
    k = min(top_k, len(final))
    top_idx = np.argpartition(-final, k - 1)[:k]
    top_idx = top_idx[np.argsort(-final[top_idx])]

    return [
        Chunk(
            text=chunks[i]["text"],
            source=chunks[i].get("source", "unknown"),
            score=float(final[i]),
            metadata=chunks[i].get("metadata", {}),
        )
        for i in top_idx
    ]


def format_context(chunks: list[Chunk]) -> str:
    """Render retrieved chunks into a <kb_context> block for the LLM."""
    if not chunks:
        return ""
    parts = ["<kb_context>"]
    for i, c in enumerate(chunks, 1):
        parts.append(f"[{i}] source={c.source} score={c.score:.3f}")
        parts.append(c.text.strip())
        parts.append("")
    parts.append("</kb_context>")
    return "\n".join(parts)
