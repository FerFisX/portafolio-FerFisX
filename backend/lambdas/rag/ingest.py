"""
rag/ingest.py — KB ingestion: walk all docs → chunk → embed → write index to S3.

Triggered by:
  - S3 ObjectCreated event on the KB bucket (any .md upload).
  - Manual: aws lambda invoke ...

Strategy:
  - Full rebuild on every trigger. KB es chica (~5MB de markdown).
  - El índice se sube atomicamente a `_index/vectors.npy` y `_index/chunks.json`.
  - El reader (retrieval.py) descarga ambos en el próximo cold start.

Idempotente: la misma KB produce el mismo índice (modulo el orden de listado de S3).
"""

from __future__ import annotations

import hashlib
import io
import json
import logging
import os
import re
from dataclasses import dataclass

import boto3
import numpy as np

from shared.bedrock_client import get_client
from shared.observability import emit_metric, log

logger = logging.getLogger(__name__)
logger.setLevel("INFO")

KB_BUCKET = os.environ.get("KB_BUCKET", "")
INDEX_VECTORS_KEY = "_index/vectors.npy"
INDEX_CHUNKS_KEY = "_index/chunks.json"

# Chunking config
MAX_CHARS = 2000      # ~500 tokens
OVERLAP_CHARS = 200   # ~50 tokens

s3 = boto3.client("s3")


@dataclass
class DocChunk:
    text: str
    source: str
    chunk_index: int
    content_hash: str


# ────────────────────────────────────────────────────────────────────────────
# Chunking (paragraph-aware, code-block atomic)
# ────────────────────────────────────────────────────────────────────────────

def semantic_chunk(text: str, source: str) -> list[DocChunk]:
    text = text.strip()
    if not text:
        return []

    parts: list[str] = []
    buf: list[str] = []
    in_code = False
    for line in text.split("\n"):
        if line.startswith("```"):
            in_code = not in_code
        buf.append(line)
        if not in_code and line.strip() == "":
            chunk = "\n".join(buf).strip()
            if chunk:
                parts.append(chunk)
            buf = []
    if buf:
        chunk = "\n".join(buf).strip()
        if chunk:
            parts.append(chunk)

    chunks: list[DocChunk] = []
    current = ""
    idx = 0
    for p in parts:
        if len(current) + len(p) + 2 > MAX_CHARS and current:
            chunks.append(_make_chunk(current, source, idx))
            idx += 1
            overlap = current[-OVERLAP_CHARS:] if len(current) > OVERLAP_CHARS else current
            current = overlap + "\n\n" + p
        else:
            current = (current + "\n\n" + p).strip() if current else p
    if current:
        chunks.append(_make_chunk(current, source, idx))
    return chunks


def _make_chunk(text: str, source: str, idx: int) -> DocChunk:
    h = hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]
    return DocChunk(text=text, source=source, chunk_index=idx, content_hash=h)


# ────────────────────────────────────────────────────────────────────────────
# Index build
# ────────────────────────────────────────────────────────────────────────────

def _list_kb_docs() -> list[str]:
    """List all .md / .txt files in the bucket, ignoring the index folder."""
    paginator = s3.get_paginator("list_objects_v2")
    keys: list[str] = []
    for page in paginator.paginate(Bucket=KB_BUCKET):
        for obj in page.get("Contents", []):
            k = obj["Key"]
            if k.startswith("_index/"):
                continue
            if k.endswith(".md") or k.endswith(".txt"):
                keys.append(k)
    return sorted(keys)


def _normalize(v: np.ndarray) -> np.ndarray:
    n = np.linalg.norm(v)
    return v / n if n > 0 else v


def build_index() -> dict:
    """Full rebuild. Walk all KB docs → chunk → embed → upload index."""
    bedrock = get_client()
    docs = _list_kb_docs()
    log("ingest_start", docs_count=len(docs))

    all_chunks: list[DocChunk] = []
    for key in docs:
        body = s3.get_object(Bucket=KB_BUCKET, Key=key)["Body"].read().decode("utf-8", errors="replace")
        source = key.split("/")[-1]
        chunks = semantic_chunk(body, source)
        all_chunks.extend(chunks)
        log("doc_chunked", source=source, chunks=len(chunks))

    if not all_chunks:
        log("no_chunks_found")
        return {"chunks": 0}

    # Embed in batch (one at a time — Titan v2 single-input API)
    vectors = np.zeros((len(all_chunks), 1024), dtype=np.float32)
    chunk_meta: list[dict] = []
    for i, c in enumerate(all_chunks):
        vec = np.asarray(bedrock.embed(c.text), dtype=np.float32)
        vectors[i] = _normalize(vec)
        chunk_meta.append({
            "text": c.text,
            "source": c.source,
            "metadata": {
                "chunk_index": c.chunk_index,
                "content_hash": c.content_hash,
                "char_count": len(c.text),
            },
        })

    # Persist index to S3 atomically (upload then they replace previous)
    vec_bytes = io.BytesIO()
    np.save(vec_bytes, vectors)
    vec_bytes.seek(0)
    s3.put_object(
        Bucket=KB_BUCKET,
        Key=INDEX_VECTORS_KEY,
        Body=vec_bytes.read(),
        ContentType="application/octet-stream",
    )
    s3.put_object(
        Bucket=KB_BUCKET,
        Key=INDEX_CHUNKS_KEY,
        Body=json.dumps(chunk_meta, ensure_ascii=False).encode("utf-8"),
        ContentType="application/json",
    )

    emit_metric("rag.chunks_indexed", len(all_chunks), "Count")
    log("ingest_done", chunks=len(all_chunks), docs=len(docs))
    return {"chunks": len(all_chunks), "docs": len(docs)}


# ────────────────────────────────────────────────────────────────────────────
# Lambda entrypoint
# ────────────────────────────────────────────────────────────────────────────

def lambda_handler(event: dict, context) -> dict:
    """
    Triggered on any .md/.txt upload to the KB bucket.
    We rebuild the full index every time — it's small (<5MB) and rebuild takes ~10s.
    """
    # Skip if the event itself is about the index file (avoid recursion)
    for record in event.get("Records", []):
        key = record.get("s3", {}).get("object", {}).get("key", "")
        if key.startswith("_index/"):
            log("skip_index_self_trigger", key=key)
            return {"statusCode": 200, "skipped": True}

    result = build_index()
    return {"statusCode": 200, **result}
