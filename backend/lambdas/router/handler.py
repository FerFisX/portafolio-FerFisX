"""
router/handler.py — Multi-model router.

Demo of how to route a request across multiple LLMs based on:
  - Complexity (token count, keywords)
  - Cost budget per request
  - Latency target

Returns side-by-side comparison so you can see quality vs cost tradeoff.
"""

from __future__ import annotations

import json
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

from shared.bedrock_client import get_client
from shared.observability import log, track_llm_call

CORS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "POST, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type",
    "Content-Type": "application/json",
}

# Tier the models by cost / capability
MODEL_TIERS = {
    "cheap":  "anthropic.claude-3-5-haiku-20241022-v1:0",
    "smart":  "anthropic.claude-3-5-sonnet-20241022-v2:0",
    "open":   "meta.llama3-1-70b-instruct-v1:0",
}


def _classify_complexity(prompt: str) -> str:
    """Heuristic complexity classifier — could be replaced by a tiny LLM call."""
    lower = prompt.lower()
    word_count = len(prompt.split())
    hard_terms = ["explica", "analiza", "diseña", "compara", "arquitectura", "código"]
    if word_count > 60 or any(t in lower for t in hard_terms):
        return "smart"
    return "cheap"


def _call_one(model_key: str, prompt: str) -> dict[str, Any]:
    client = get_client()
    model_id = MODEL_TIERS[model_key]
    t0 = time.perf_counter()
    try:
        resp = client.invoke(
            messages=[{"role": "user", "content": prompt}],
            system="Respondé conciso y útil. Máximo 150 palabras.",
            model=model_id,
            max_tokens=300,
            temperature=0.5,
        )
        track_llm_call(
            model=resp.model, tokens_in=resp.tokens_in, tokens_out=resp.tokens_out,
            latency_ms=resp.latency_ms, cost_usd=resp.cost_usd, endpoint="router",
        )
        return {
            "tier": model_key,
            "model": resp.model,
            "response": resp.text,
            "latency_ms": resp.latency_ms,
            "cost_usd": resp.cost_usd,
            "tokens": {"in": resp.tokens_in, "out": resp.tokens_out},
        }
    except Exception as e:
        log("router_model_failed", model=model_id, error=str(e))
        return {
            "tier": model_key,
            "model": model_id,
            "response": f"(falló: {e})",
            "latency_ms": int((time.perf_counter() - t0) * 1000),
            "cost_usd": 0.0,
            "error": str(e),
        }


def lambda_handler(event: dict[str, Any], context) -> dict[str, Any]:
    if event.get("requestContext", {}).get("http", {}).get("method") == "OPTIONS":
        return {"statusCode": 204, "headers": CORS, "body": ""}

    try:
        body = json.loads(event.get("body") or "{}")
        prompt = (body.get("prompt") or "").strip()
        mode = body.get("mode", "compare")  # "compare" | "auto"

        if not prompt:
            return {"statusCode": 400, "headers": CORS, "body": json.dumps({"error": "prompt required"})}

        if mode == "auto":
            choice = _classify_complexity(prompt)
            log("router_auto_choice", choice=choice, prompt_len=len(prompt))
            result = _call_one(choice, prompt)
            return {
                "statusCode": 200, "headers": CORS,
                "body": json.dumps({"mode": "auto", "selected_tier": choice, "result": result}),
            }

        # Compare mode — call all in parallel
        results: list[dict[str, Any]] = []
        with ThreadPoolExecutor(max_workers=3) as pool:
            futures = {pool.submit(_call_one, tier, prompt): tier for tier in MODEL_TIERS}
            for f in as_completed(futures):
                results.append(f.result())

        # Sort by tier for stable UI
        results.sort(key=lambda r: list(MODEL_TIERS.keys()).index(r["tier"]))

        return {
            "statusCode": 200, "headers": CORS,
            "body": json.dumps({"mode": "compare", "results": results}, ensure_ascii=False),
        }
    except Exception as e:
        log("router_error", error=str(e))
        return {"statusCode": 500, "headers": CORS, "body": json.dumps({"error": "internal", "detail": str(e)[:200]})}
