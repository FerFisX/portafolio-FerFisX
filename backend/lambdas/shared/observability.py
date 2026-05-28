"""
observability.py — Structured logging + CloudWatch EMF metrics.

EMF (Embedded Metric Format) lets Lambda emit metrics by simply printing
a structured log line. No extra API call, no extra cost, no extra latency.

We track:
  - llm.tokens.input / output
  - llm.latency_ms
  - llm.cost_usd
  - llm.cache_hit_rate (calculated from token deltas)
  - agent.tool_calls (count of tool invocations per request)
  - rag.retrieved_chunks

These metrics drive CloudWatch dashboards and alarms (e.g. cost spike).
"""

from __future__ import annotations

import json
import logging
import os
import sys
import time
from contextlib import contextmanager
from typing import Any

NAMESPACE = "AdrianAI/Portafolio"

# Configure root logger for structured JSON logs
_logger = logging.getLogger("adrian")
_logger.setLevel(os.environ.get("LOG_LEVEL", "INFO"))
if not _logger.handlers:
    h = logging.StreamHandler(sys.stdout)
    h.setFormatter(logging.Formatter("%(message)s"))
    _logger.addHandler(h)


def log(event: str, **fields: Any) -> None:
    """Emit a structured JSON log line."""
    payload = {"event": event, "ts": time.time(), **fields}
    _logger.info(json.dumps(payload, default=str))


def emit_metric(name: str, value: float, unit: str = "None", **dimensions: str) -> None:
    """
    Emit a CloudWatch metric via EMF. Just print a structured JSON line and
    CloudWatch will pick it up. Zero extra cost.
    """
    emf = {
        "_aws": {
            "Timestamp": int(time.time() * 1000),
            "CloudWatchMetrics": [
                {
                    "Namespace": NAMESPACE,
                    "Dimensions": [list(dimensions.keys())] if dimensions else [[]],
                    "Metrics": [{"Name": name, "Unit": unit}],
                }
            ],
        },
        name: value,
        **dimensions,
    }
    print(json.dumps(emf))


def track_llm_call(
    model: str,
    tokens_in: int,
    tokens_out: int,
    latency_ms: int,
    cost_usd: float,
    endpoint: str = "chat",
) -> None:
    """Emit the full metric set for a single LLM call."""
    dims = {"model": model, "endpoint": endpoint}
    emit_metric("llm.tokens.input", tokens_in, "Count", **dims)
    emit_metric("llm.tokens.output", tokens_out, "Count", **dims)
    emit_metric("llm.latency_ms", latency_ms, "Milliseconds", **dims)
    emit_metric("llm.cost_usd", cost_usd, "None", **dims)
    log("llm_call", model=model, tokens_in=tokens_in, tokens_out=tokens_out,
        latency_ms=latency_ms, cost_usd=cost_usd, endpoint=endpoint)


@contextmanager
def timed(label: str):
    """Time a code block and emit it as a metric."""
    t0 = time.perf_counter()
    try:
        yield
    finally:
        ms = int((time.perf_counter() - t0) * 1000)
        emit_metric(f"{label}.duration_ms", ms, "Milliseconds")
        log("timed", label=label, duration_ms=ms)
