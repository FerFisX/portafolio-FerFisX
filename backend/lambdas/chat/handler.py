"""
chat/handler.py — Main conversational agent endpoint.

Flow:
  1. Receive {session_id, message} from API Gateway.
  2. Load conversation history from DynamoDB.
  3. Run hybrid retrieval (BM25 + vector) on the user message → top-K chunks.
  4. Call Claude on Bedrock with cached system prompt + KB context + tools.
  5. If model returns tool_use → execute tool, append result, call again.
  6. Persist final exchange to DynamoDB.
  7. Return response + citations + cost/latency metrics.
"""

from __future__ import annotations

import json
import os
import time
from typing import Any

import boto3

from shared.bedrock_client import get_client
from shared.observability import emit_metric, log, track_llm_call
from shared.prompts import AGENT_TOOLS, PROMPT_VERSION, SYSTEM_PROMPT
from shared.retrieval import format_context, hybrid_search

# ────────────────────────────────────────────────────────────────────────────
# Dynamo table for sessions
# ────────────────────────────────────────────────────────────────────────────
SESSIONS_TABLE = os.environ.get("SESSIONS_TABLE", "")
MAX_HISTORY = 10  # last N exchanges to keep in context

_ddb = boto3.resource("dynamodb")
_table = _ddb.Table(SESSIONS_TABLE) if SESSIONS_TABLE else None


# ────────────────────────────────────────────────────────────────────────────
# Tool implementations (executed locally when the LLM requests them)
# ────────────────────────────────────────────────────────────────────────────

def _tool_search_kb(query: str, top_k: int = 4) -> dict[str, Any]:
    chunks = hybrid_search(query, top_k=top_k)
    return {
        "chunks": [
            {"text": c.text[:600], "source": c.source, "score": round(c.score, 3)}
            for c in chunks
        ],
        "count": len(chunks),
    }


def _tool_list_demos() -> dict[str, Any]:
    return {
        "demos": [
            {"name": "Agente conversacional con tool use", "status": "live", "stack": "Bedrock+RAG+Tools"},
            {"name": "RAG sobre stablecoins", "status": "live", "stack": "numpy in-RAM + Titan"},
            {"name": "Router multimodelo", "status": "live", "stack": "Claude/GPT/Llama"},
            {"name": "Workflow Step Functions", "status": "live", "stack": "SFN+EventBridge"},
            {"name": "Eval framework", "status": "live", "stack": "Pytest+LLM-as-judge"},
            {"name": "Bot interno fintech (Meru)", "status": "live", "stack": "Slack+RAG"},
        ]
    }


def _tool_get_arch(component: str) -> dict[str, Any]:
    details = {
        "bedrock": {
            "service": "AWS Bedrock",
            "models": ["claude-3-5-sonnet", "claude-3-5-haiku", "titan-embed-v2"],
            "features": ["prompt caching", "tool use", "streaming"],
            "why": "API unificada, sin lock-in a un solo provider.",
        },
        "vector-store": {
            "service": "Custom numpy + S3",
            "use_case": "cosine similarity en RAM (Lambda) + keyword boost",
            "embedding_dim": 1024,
            "storage": "s3://<kb>/_index/vectors.npy + chunks.json",
            "why": "$0/mes vs $350/mes de OpenSearch Serverless. Latencia ~50ms. Escala hasta ~50k chunks. Para KBs chicas es el sweet spot.",
        },
        "lambda": {
            "service": "AWS Lambda",
            "runtime": "Python 3.12",
            "memory_mb": 1024,
            "why": "Escala a cero, paga por uso. Cold start ~300ms con SnapStart.",
        },
        "step-functions": {
            "service": "Step Functions",
            "use_case": "Workflow visual estilo n8n/Make: webhook → LLM → validación → Slack",
            "why": "State machine declarativa, retries built-in, visualización gratis.",
        },
        "dynamodb": {
            "service": "DynamoDB",
            "use_case": "Sesiones del chat, historial conversacional, TTL automático",
            "why": "Latencia <10ms p99, billing on-demand, integración trivial con Lambda.",
        },
    }
    return details.get(component.lower(), {"error": f"componente '{component}' no encontrado"})


TOOL_REGISTRY = {
    "search_knowledge_base": _tool_search_kb,
    "list_demos": _tool_list_demos,
    "get_architecture_detail": _tool_get_arch,
}


def _exec_tool(name: str, args: dict[str, Any]) -> Any:
    fn = TOOL_REGISTRY.get(name)
    if not fn:
        return {"error": f"unknown tool: {name}"}
    try:
        return fn(**args)
    except Exception as e:
        log("tool_error", tool=name, error=str(e))
        return {"error": str(e)}


# ────────────────────────────────────────────────────────────────────────────
# Session persistence
# ────────────────────────────────────────────────────────────────────────────

def _load_history(session_id: str) -> list[dict[str, Any]]:
    if not _table or not session_id:
        return []
    try:
        item = _table.get_item(Key={"session_id": session_id}).get("Item")
        if not item:
            return []
        return json.loads(item.get("history", "[]"))[-MAX_HISTORY * 2:]
    except Exception:
        log("history_load_failed", session_id=session_id)
        return []


def _save_history(session_id: str, history: list[dict[str, Any]]) -> None:
    if not _table or not session_id:
        return
    try:
        _table.put_item(
            Item={
                "session_id": session_id,
                "history": json.dumps(history[-MAX_HISTORY * 2:]),
                "ttl": int(time.time()) + 7 * 24 * 3600,  # 7-day TTL
                "updated_at": int(time.time()),
            }
        )
    except Exception:
        log("history_save_failed", session_id=session_id)


# ────────────────────────────────────────────────────────────────────────────
# Main agent loop with tool-use
# ────────────────────────────────────────────────────────────────────────────

def run_agent(user_message: str, history: list[dict[str, Any]]) -> dict[str, Any]:
    """Tool-use agent loop. Max 3 tool-call rounds to bound cost/latency."""
    client = get_client()

    # Step 1: cheap retrieval pass before the model even runs.
    # This gives the model context for ~80% of queries without needing a tool call.
    initial_chunks = hybrid_search(user_message, top_k=4)
    kb_block = format_context(initial_chunks)
    citations = list({c.source for c in initial_chunks})

    # Build messages: history + new user message (with kb context injected)
    user_content = (
        f"{kb_block}\n\n{user_message}" if kb_block else user_message
    )
    messages = list(history) + [{"role": "user", "content": user_content}]

    total_tokens_in = 0
    total_tokens_out = 0
    total_cost = 0.0
    total_latency = 0
    rounds = 0
    final_text = ""

    for _ in range(3):  # bounded tool-use loop
        rounds += 1
        resp = client.invoke(
            messages=messages,
            system=SYSTEM_PROMPT,
            tools=AGENT_TOOLS,
            max_tokens=1024,
            temperature=0.4,
            cache_system=True,
        )
        total_tokens_in += resp.tokens_in
        total_tokens_out += resp.tokens_out
        total_cost += resp.cost_usd
        total_latency += resp.latency_ms

        if resp.stop_reason != "tool_use":
            final_text = resp.text
            break

        # Execute requested tools, append results, loop
        assistant_blocks: list[dict[str, Any]] = []
        if resp.text:
            assistant_blocks.append({"type": "text", "text": resp.text})
        for call in resp.tool_calls:
            assistant_blocks.append(
                {
                    "type": "tool_use",
                    "id": call["id"],
                    "name": call["name"],
                    "input": call["input"],
                }
            )
        messages.append({"role": "assistant", "content": assistant_blocks})

        tool_results: list[dict[str, Any]] = []
        for call in resp.tool_calls:
            result = _exec_tool(call["name"], call["input"])
            # If the search tool ran, accumulate citations
            if call["name"] == "search_knowledge_base":
                for c in result.get("chunks", []):
                    if c.get("source") and c["source"] not in citations:
                        citations.append(c["source"])
            tool_results.append(
                {
                    "type": "tool_result",
                    "tool_use_id": call["id"],
                    "content": json.dumps(result, ensure_ascii=False)[:4000],
                }
            )
        messages.append({"role": "user", "content": tool_results})

    track_llm_call(
        model=resp.model,
        tokens_in=total_tokens_in,
        tokens_out=total_tokens_out,
        latency_ms=total_latency,
        cost_usd=total_cost,
        endpoint="chat",
    )
    emit_metric("agent.tool_rounds", rounds, "Count", endpoint="chat")
    emit_metric("rag.retrieved_chunks", len(initial_chunks), "Count")

    return {
        "response": final_text or "(respuesta vacía)",
        "citations": citations,
        "model": resp.model,
        "tokens": {"input": total_tokens_in, "output": total_tokens_out},
        "latency_ms": total_latency,
        "cost_usd": round(total_cost, 6),
        "tool_rounds": rounds,
        "prompt_version": PROMPT_VERSION,
    }


# ────────────────────────────────────────────────────────────────────────────
# Lambda entrypoint
# ────────────────────────────────────────────────────────────────────────────

def lambda_handler(event: dict[str, Any], context) -> dict[str, Any]:
    cors_headers = {
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "POST, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type, Authorization",
        "Content-Type": "application/json",
    }

    # CORS preflight
    if event.get("requestContext", {}).get("http", {}).get("method") == "OPTIONS":
        return {"statusCode": 204, "headers": cors_headers, "body": ""}

    try:
        body = json.loads(event.get("body") or "{}")
        session_id: str = body.get("session_id") or ""
        message: str = (body.get("message") or "").strip()
        if not message:
            return {
                "statusCode": 400,
                "headers": cors_headers,
                "body": json.dumps({"error": "message required"}),
            }
        if len(message) > 2000:
            return {
                "statusCode": 400,
                "headers": cors_headers,
                "body": json.dumps({"error": "message too long (max 2000 chars)"}),
            }

        history = _load_history(session_id)
        result = run_agent(message, history)

        # Persist
        new_history = history + [
            {"role": "user", "content": message},
            {"role": "assistant", "content": result["response"]},
        ]
        _save_history(session_id, new_history)

        return {"statusCode": 200, "headers": cors_headers, "body": json.dumps(result, ensure_ascii=False)}

    except Exception as e:
        log("handler_error", error=str(e))
        return {
            "statusCode": 500,
            "headers": cors_headers,
            "body": json.dumps({"error": "internal error", "detail": str(e)[:200]}),
        }
