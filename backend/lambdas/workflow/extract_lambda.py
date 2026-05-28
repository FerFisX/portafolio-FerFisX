"""
extract_lambda.py — Step Functions worker. Extrae entidades estructuradas
del payload usando un LLM con JSON output.

Ejemplo de uso (en el demo para Meru):
  - payload: webhook de una transacción on-chain.
  - LLM extrae: { category, amount, asset, counterparty, risk_score, confidence }
  - Step Functions enruta en base a category + confidence.
"""

from __future__ import annotations

import json
import re
from typing import Any

from shared.bedrock_client import get_client
from shared.observability import log, track_llm_call

EXTRACTION_SCHEMA = {
    "category": "ops | compliance | other",
    "amount": "número en USD o null",
    "asset": "ticker (USDC, USDT, DAI, BTC, ETH, etc.) o null",
    "counterparty": "nombre o address o null",
    "risk_score": "0.0 a 1.0",
    "confidence": "0.0 a 1.0 — qué tan seguro estás de la extracción",
}

SYSTEM = f"""Sos un extractor estructurado para una fintech de stablecoins.

Dado un payload (texto libre, JSON, log, etc.), devolvé un JSON EXACTAMENTE con este schema:

{json.dumps(EXTRACTION_SCHEMA, indent=2)}

Reglas:
- Solo JSON, sin markdown, sin explicación.
- Si un campo no se puede determinar, usá null.
- 'category' nunca es null — usá 'other' si no encaja en ops/compliance.
- 'confidence' refleja cuán seguro estás. Si el payload es ambiguo, bajalo (<0.7) — eso dispara human-review en el workflow."""


def _parse_json(text: str) -> dict[str, Any]:
    """Extract JSON from response even if model wraps it in fences."""
    text = text.strip()
    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if fence:
        text = fence.group(1)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Last-resort: grab first {...} block
        m = re.search(r"\{.*\}", text, re.DOTALL)
        if m:
            return json.loads(m.group(0))
        raise


def lambda_handler(event: dict[str, Any], context) -> dict[str, Any]:
    payload = event.get("payload", "")
    if not isinstance(payload, str):
        payload = json.dumps(payload, ensure_ascii=False)

    client = get_client()
    resp = client.invoke(
        messages=[{"role": "user", "content": f"Payload a extraer:\n\n{payload}"}],
        system=SYSTEM,
        max_tokens=400,
        temperature=0.1,
    )
    track_llm_call(
        model=resp.model, tokens_in=resp.tokens_in, tokens_out=resp.tokens_out,
        latency_ms=resp.latency_ms, cost_usd=resp.cost_usd, endpoint="extract",
    )

    try:
        parsed = _parse_json(resp.text)
    except Exception as e:
        log("extract_parse_failed", error=str(e), text=resp.text[:300])
        return {"confidence": 0.0, "category": "other", "error": "parse_failed"}

    # Normalize confidence
    confidence = float(parsed.get("confidence", 0.5))
    parsed["confidence"] = max(0.0, min(1.0, confidence))
    log("extract_done", category=parsed.get("category"), confidence=confidence)
    return parsed
