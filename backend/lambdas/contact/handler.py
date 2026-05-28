"""
contact/handler.py — Contact form submission.

Flow:
  - Validate input.
  - Spam-check with quick heuristics (length, link count).
  - Send email via SES.
  - Optionally summarize with Claude (so I get a TL;DR in my inbox).
"""

from __future__ import annotations

import json
import os
import re
from typing import Any

import boto3

from shared.bedrock_client import get_client
from shared.observability import log, track_llm_call

SES = boto3.client("ses")
FROM_EMAIL = os.environ.get("FROM_EMAIL", "noreply@example.com")
TO_EMAIL = os.environ.get("TO_EMAIL", "adrian@example.com")

CORS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "POST, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type",
    "Content-Type": "application/json",
}


def _looks_like_spam(message: str, email: str) -> bool:
    if len(message) < 10 or len(message) > 4000:
        return True
    if len(re.findall(r"https?://", message)) > 3:
        return True
    if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
        return True
    return False


def _summarize(name: str, message: str) -> str:
    """Quick TL;DR using cheap model."""
    try:
        client = get_client()
        resp = client.invoke(
            messages=[
                {
                    "role": "user",
                    "content": (
                        f"Resumí este mensaje de contacto en una línea (máximo 25 palabras), "
                        f"clasificá la intención (oportunidad / consulta / spam) y sugerí prioridad "
                        f"(alta/media/baja). De: {name}.\n\n{message}"
                    ),
                }
            ],
            system="Sos un clasificador de leads. Respondé en una sola línea formato: 'INTENCIÓN | PRIORIDAD | resumen'.",
            model="anthropic.claude-3-5-haiku-20241022-v1:0",
            max_tokens=80,
            temperature=0.2,
        )
        track_llm_call(
            model=resp.model, tokens_in=resp.tokens_in, tokens_out=resp.tokens_out,
            latency_ms=resp.latency_ms, cost_usd=resp.cost_usd, endpoint="contact",
        )
        return resp.text.strip()
    except Exception as e:
        log("summarize_failed", error=str(e))
        return "(no summary)"


def lambda_handler(event: dict[str, Any], context) -> dict[str, Any]:
    if event.get("requestContext", {}).get("http", {}).get("method") == "OPTIONS":
        return {"statusCode": 204, "headers": CORS, "body": ""}

    try:
        body = json.loads(event.get("body") or "{}")
        name = (body.get("name") or "").strip()[:200]
        email = (body.get("email") or "").strip().lower()[:200]
        company = (body.get("company") or "").strip()[:200]
        message = (body.get("message") or "").strip()[:4000]

        if not all([name, email, message]):
            return {"statusCode": 400, "headers": CORS, "body": json.dumps({"error": "missing fields"})}
        if _looks_like_spam(message, email):
            return {"statusCode": 400, "headers": CORS, "body": json.dumps({"error": "invalid input"})}

        summary = _summarize(name, message)

        subject = f"[adrian.ai] Nuevo contacto: {name} ({company or 'sin empresa'})"
        text = (
            f"TL;DR (Claude Haiku):\n{summary}\n\n"
            f"───────────────────\n"
            f"De: {name} <{email}>\n"
            f"Empresa: {company or '—'}\n\n"
            f"Mensaje:\n{message}\n"
        )

        SES.send_email(
            Source=FROM_EMAIL,
            Destination={"ToAddresses": [TO_EMAIL]},
            Message={
                "Subject": {"Data": subject, "Charset": "UTF-8"},
                "Body": {"Text": {"Data": text, "Charset": "UTF-8"}},
            },
            ReplyToAddresses=[email],
        )
        log("contact_sent", name=name, email=email, has_company=bool(company))

        return {"statusCode": 200, "headers": CORS, "body": json.dumps({"ok": True})}
    except Exception as e:
        log("contact_error", error=str(e))
        return {"statusCode": 500, "headers": CORS, "body": json.dumps({"error": "internal error"})}
