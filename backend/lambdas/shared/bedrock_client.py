"""
bedrock_client.py — Thin, opinionated wrapper around AWS Bedrock.

Why this layer exists:
  - Single place for prompt caching, retries, observability.
  - Provider-agnostic surface (we can swap Claude → Llama by changing model_id only).
  - Cost & token tracking baked in.

Used by: chat, rag, agent lambdas.
"""

from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass, field
from typing import Any, Iterable

import boto3
from botocore.config import Config

logger = logging.getLogger(__name__)
logger.setLevel(os.environ.get("LOG_LEVEL", "INFO"))

# Pricing snapshot (USD per 1K tokens). Update when AWS bumps prices.
PRICING = {
    "anthropic.claude-3-5-sonnet-20241022-v2:0": {"in": 0.003, "out": 0.015},
    "anthropic.claude-3-5-haiku-20241022-v1:0":  {"in": 0.001, "out": 0.005},
    "anthropic.claude-3-haiku-20240307-v1:0":    {"in": 0.00025, "out": 0.00125},
    "meta.llama3-1-70b-instruct-v1:0":           {"in": 0.00099, "out": 0.00099},
}


@dataclass
class LLMResponse:
    text: str
    model: str
    tokens_in: int
    tokens_out: int
    latency_ms: int
    cost_usd: float
    stop_reason: str = "end_turn"
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    raw: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "response": self.text,
            "model": self.model,
            "tokens": {"input": self.tokens_in, "output": self.tokens_out},
            "latency_ms": self.latency_ms,
            "cost_usd": round(self.cost_usd, 6),
            "stop_reason": self.stop_reason,
            "tool_calls": self.tool_calls,
        }


class BedrockClient:
    """Wrapper around bedrock-runtime with retries, caching, and metrics."""

    def __init__(self, region: str | None = None, default_model: str | None = None):
        self.region = region or os.environ.get("AWS_REGION", "us-east-1")
        self.default_model = default_model or os.environ.get(
            "DEFAULT_MODEL_ID",
            "anthropic.claude-3-5-sonnet-20241022-v2:0",
        )
        self.client = boto3.client(
            "bedrock-runtime",
            region_name=self.region,
            config=Config(
                retries={"max_attempts": 3, "mode": "adaptive"},
                read_timeout=60,
                connect_timeout=10,
            ),
        )

    def invoke(
        self,
        messages: list[dict[str, Any]],
        system: str | list[dict[str, Any]] | None = None,
        model: str | None = None,
        max_tokens: int = 1024,
        temperature: float = 0.4,
        tools: list[dict[str, Any]] | None = None,
        cache_system: bool = True,
    ) -> LLMResponse:
        """
        Invoke an Anthropic Claude model on Bedrock.

        Prompt caching is enabled by default on the system prompt — this
        cuts latency ~80% and cost ~90% on repeated calls within the cache TTL.
        """
        model_id = model or self.default_model

        body: dict[str, Any] = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": messages,
        }

        # System prompt with cache_control for prompt caching
        if system is not None:
            if isinstance(system, str):
                body["system"] = (
                    [{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}]
                    if cache_system
                    else system
                )
            else:
                body["system"] = system

        if tools:
            body["tools"] = tools

        t0 = time.perf_counter()
        try:
            resp = self.client.invoke_model(
                modelId=model_id,
                body=json.dumps(body),
                contentType="application/json",
                accept="application/json",
            )
        except Exception as e:
            logger.exception("bedrock invoke failed: %s", e)
            raise

        latency_ms = int((time.perf_counter() - t0) * 1000)
        payload = json.loads(resp["body"].read())

        # Extract text + tool calls
        text_parts: list[str] = []
        tool_calls: list[dict[str, Any]] = []
        for block in payload.get("content", []):
            if block.get("type") == "text":
                text_parts.append(block["text"])
            elif block.get("type") == "tool_use":
                tool_calls.append(
                    {
                        "id": block.get("id"),
                        "name": block.get("name"),
                        "input": block.get("input"),
                    }
                )

        usage = payload.get("usage", {})
        tokens_in = usage.get("input_tokens", 0)
        tokens_out = usage.get("output_tokens", 0)
        # Cache hits are billed cheaper; track them when present.
        cache_read = usage.get("cache_read_input_tokens", 0)
        cache_write = usage.get("cache_creation_input_tokens", 0)

        cost = self._estimate_cost(model_id, tokens_in, tokens_out, cache_read, cache_write)

        return LLMResponse(
            text="".join(text_parts),
            model=model_id,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            latency_ms=latency_ms,
            cost_usd=cost,
            stop_reason=payload.get("stop_reason", "end_turn"),
            tool_calls=tool_calls,
            raw=payload,
        )

    def embed(self, text: str, model: str = "amazon.titan-embed-text-v2:0") -> list[float]:
        """Generate an embedding vector for a string. Used by RAG ingest + query."""
        resp = self.client.invoke_model(
            modelId=model,
            body=json.dumps({"inputText": text, "dimensions": 1024, "normalize": True}),
            contentType="application/json",
            accept="application/json",
        )
        return json.loads(resp["body"].read())["embedding"]

    @staticmethod
    def _estimate_cost(
        model_id: str,
        tokens_in: int,
        tokens_out: int,
        cache_read: int = 0,
        cache_write: int = 0,
    ) -> float:
        rates = PRICING.get(model_id, {"in": 0.003, "out": 0.015})
        regular_in = max(0, tokens_in - cache_read - cache_write)
        return (
            (regular_in / 1000) * rates["in"]
            + (cache_read / 1000) * rates["in"] * 0.1      # cache hit ~10% of input price
            + (cache_write / 1000) * rates["in"] * 1.25    # write is slightly more expensive
            + (tokens_out / 1000) * rates["out"]
        )


# Module-level singleton (Lambda re-uses the same container across invocations)
_default_client: BedrockClient | None = None


def get_client() -> BedrockClient:
    global _default_client
    if _default_client is None:
        _default_client = BedrockClient()
    return _default_client
