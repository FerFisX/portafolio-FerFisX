"""
run_evals.py — Eval harness for the chat agent.

Usage:
    python -m backend.evals.run_evals

Reads golden_set.jsonl, runs each query against the agent,
scores with LLM-as-judge, prints summary + writes report.

Exit code: 0 if all evals pass threshold (avg score >= 4.0), 1 otherwise.
This makes it CI-friendly: hook to GitHub Actions or CodePipeline.
"""

from __future__ import annotations

import json
import os
import sys
import time
from dataclasses import dataclass, asdict
from pathlib import Path

# Allow running from repo root
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lambdas"))

from shared.bedrock_client import get_client
from shared.prompts import EVAL_JUDGE_V1
from chat.handler import run_agent  # type: ignore

THRESHOLD = 4.0
HERE = Path(__file__).parent
GOLDEN = HERE / "golden_set.jsonl"
REPORT = HERE / "report.json"


@dataclass
class EvalResult:
    id: str
    question: str
    response: str
    scores: dict
    rationale: str
    latency_ms: int
    cost_usd: float


def judge(question: str, expected: dict, actual: str) -> dict:
    """LLM-as-judge: score the actual response against expected themes."""
    client = get_client()
    user = (
        f"Pregunta del usuario:\n{question}\n\n"
        f"Temas que la respuesta debería tocar (no exactos, semánticos):\n"
        f"{json.dumps(expected.get('expected_themes', []), ensure_ascii=False)}\n\n"
        f"Respuesta del agente:\n{actual}\n\n"
        "Devolvé el JSON con scores 1-5."
    )
    resp = client.invoke(
        messages=[{"role": "user", "content": user}],
        system=EVAL_JUDGE_V1,
        model="anthropic.claude-3-5-sonnet-20241022-v2:0",
        max_tokens=200,
        temperature=0.0,
    )
    try:
        return json.loads(resp.text.strip().strip("`").lstrip("json").strip())
    except Exception:
        return {"accuracy": 0, "relevance": 0, "tone": 0, "rationale": "parse_failed: " + resp.text[:200]}


def main() -> int:
    if not GOLDEN.exists():
        print(f"❌ Golden set not found at {GOLDEN}")
        return 1

    cases = [json.loads(line) for line in GOLDEN.read_text(encoding="utf-8").splitlines() if line.strip()]
    print(f"Running {len(cases)} eval cases...\n")

    results: list[EvalResult] = []
    for case in cases:
        print(f"  ▸ {case['id']}: {case['question'][:60]}...")
        t0 = time.perf_counter()
        try:
            agent_output = run_agent(case["question"], history=[])
            actual = agent_output["response"]
            cost = agent_output.get("cost_usd", 0)
        except Exception as e:
            actual = f"(error: {e})"
            cost = 0
        latency = int((time.perf_counter() - t0) * 1000)

        scores = judge(case["question"], case, actual)
        results.append(
            EvalResult(
                id=case["id"],
                question=case["question"],
                response=actual[:500],
                scores={k: v for k, v in scores.items() if k != "rationale"},
                rationale=scores.get("rationale", ""),
                latency_ms=latency,
                cost_usd=cost,
            )
        )

    # Aggregate
    score_keys = ["accuracy", "relevance", "tone"]
    avgs = {k: sum(r.scores.get(k, 0) for r in results) / len(results) for k in score_keys}
    overall = sum(avgs.values()) / len(avgs)
    total_cost = sum(r.cost_usd for r in results)

    print("\n────── Eval Report ──────")
    for k, v in avgs.items():
        print(f"  {k:10s}: {v:.2f} / 5")
    print(f"  {'overall':10s}: {overall:.2f} / 5  (threshold: {THRESHOLD})")
    print(f"  total cost: ${total_cost:.4f}")
    print("─" * 30)

    REPORT.write_text(
        json.dumps(
            {"averages": avgs, "overall": overall, "cases": [asdict(r) for r in results]},
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"Full report: {REPORT}")

    return 0 if overall >= THRESHOLD else 1


if __name__ == "__main__":
    sys.exit(main())
