"""
Layer 2 + 3 + LLM-as-Judge (LLM-dependent evaluations).

Runnable now (needs DEEPSEEK_API_KEY in the env):
  --eval topic       Topic-classifier guardrail accuracy vs golden labels
  --eval judge       LLM-as-judge absolute scoring + pairwise (with position swap)

Scaffolded (need the full LangGraph agent / running server — see README):
  --eval trajectory  Golden-path trajectory matching
  --eval e2e         End-to-end task success + latency + token cost
"""
import os
import re
import sys
import json
import time

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "backend", "app"))

from langchain_openai import ChatOpenAI
from core.env import DEEPSEEK_API_KEY, DEEPSEEK_MODEL, DEEPSEEK_BASE_URL
from core.guardrails import is_on_topic
from judge_prompts import (
    ABSOLUTE_JUDGE_SYSTEM, ABSOLUTE_JUDGE_USER,
    PAIRWISE_JUDGE_SYSTEM, PAIRWISE_JUDGE_USER,
)

OUT_DIR = os.path.dirname(__file__)


def get_llm():
    return ChatOpenAI(model=DEEPSEEK_MODEL, api_key=DEEPSEEK_API_KEY,
                      base_url=DEEPSEEK_BASE_URL, temperature=0)


# ---------------------------------------------------------------------------
# Topic-classifier guardrail (Layer 1, but LLM-dependent)
# ---------------------------------------------------------------------------
TOPIC_CASES = [
    ("What was the rainfall in Pampanga last month?", "WEATHER", True),
    ("What was the palay yield in Nueva Ecija in 2023?", "CROP", True),
    ("Is there a correlation between rainfall and palay yield?", "RELATIONSHIP", True),
    ("What can you do?", "GENERAL", True),
    ("What kind of data can you analyze?", "GENERAL", True),
    ("Should I plant rice this month?", "ADVICE", False),
    ("Who won the World Cup in 2022?", "OFF_TOPIC", False),
    ("What will the weather be like tomorrow?", "FORECAST", False),
    ("When should I harvest my palay crop?", "ADVICE", False),
]


def _parse_json(text):
    m = re.search(r"\{.*\}", text, re.DOTALL)
    return json.loads(m.group()) if m else None


def eval_topic_classifier(llm):
    correct_blocked = 0
    correct_topic = 0
    per_case = []
    t0 = time.time()
    for query, expected_topic, expected_allowed in TOPIC_CASES:
        try:
            r = is_on_topic(query, llm, None)
        except Exception as e:
            per_case.append({"query": query, "error": f"{type(e).__name__}: {e}"})
            continue
        fallback = bool(r.get("fallback"))
        got_topic = r.get("topic")
        # correctly blocked if fallback matches "not allowed"
        blocked_ok = (fallback is True) == (not expected_allowed)
        topic_ok = (got_topic == expected_topic)
        correct_blocked += int(blocked_ok)
        correct_topic += int(topic_ok)
        per_case.append({"query": query, "expected_topic": expected_topic,
                         "got_topic": got_topic, "fallback": fallback,
                         "blocked_ok": blocked_ok, "topic_ok": topic_ok,
                         "confidence": r.get("confidence")})

    n = len(TOPIC_CASES)
    return {
        "blocked_accuracy": round(correct_blocked / n, 3),
        "topic_accuracy": round(correct_topic / n, 3),
        "elapsed_s": round(time.time() - t0, 1),
        "per_case": per_case,
        "n_cases": n,
    }


# ---------------------------------------------------------------------------
# LLM-as-judge
# ---------------------------------------------------------------------------
# (query, context, answer) triples: one good, one hallucinated, one off-topic
JUDGE_ABSOLUTE_CASES = [
    {
        "query": "What was the palay yield in Pampanga in 2023?",
        "context": "Pampanga palay yield 2023: mean 4.1 MT/ha (from fact_palay_production).",
        "answer": "The average palay yield in Pampanga in 2023 was about 4.1 metric tons per hectare.",
        "label": "good",
    },
    {
        "query": "What was the palay yield in Pampanga in 2023?",
        "context": "Pampanga palay yield 2023: mean 4.1 MT/ha (from fact_palay_production).",
        "answer": "The average palay yield in Pampanga in 2023 was 9.8 metric tons per hectare, and this is expected to double next year.",
        "label": "hallucinated",
    },
    {
        "query": "What was the palay yield in Pampanga in 2023?",
        "context": "Pampanga palay yield 2023: mean 4.1 MT/ha (from fact_palay_production).",
        "answer": "I can't help with that. The capital of France is Paris and the fastest animal is the cheetah.",
        "label": "off_topic",
    },
]


def _judge_absolute(llm, case):
    user = ABSOLUTE_JUDGE_USER.format(query=case["query"], context=case["context"], answer=case["answer"])
    resp = llm.invoke([("system", ABSOLUTE_JUDGE_SYSTEM), ("human", user)])
    return _parse_json(resp.content) or {"error": resp.content[:200]}


def _judge_pairwise(llm, case, swap=False):
    a, b = case["answer_a"], case["answer_b"]
    if swap:
        a, b = b, a
    user = PAIRWISE_JUDGE_USER.format(query=case["query"], context=case["context"], answer_a=a, answer_b=b)
    resp = llm.invoke([("system", PAIRWISE_JUDGE_SYSTEM), ("human", user)])
    parsed = _parse_json(resp.content) or {}
    return parsed.get("winner"), (parsed.get("reasoning") or resp.content)[:200]


def eval_judge(llm):
    t0 = time.time()
    absolute = []
    for c in JUDGE_ABSOLUTE_CASES:
        s = _judge_absolute(llm, c)
        absolute.append({"label": c["label"], "scores": s})

    # Pairwise: good vs hallucinated, scored both orders to check positional bias
    pairwise_case = {
        "query": "What was the palay yield in Pampanga in 2023?",
        "context": "Pampanga palay yield 2023: mean 4.1 MT/ha.",
        "answer_a": "The average palay yield in Pampanga in 2023 was about 4.1 metric tons per hectare.",
        "answer_b": "The average palay yield in Pampanga in 2023 was 9.8 metric tons per hectare and it will double next year.",
    }
    w1, r1 = _judge_pairwise(llm, pairwise_case, swap=False)
    w2, r2 = _judge_pairwise(llm, pairwise_case, swap=True)  # swapped order -> positional-bias check

    # positional bias: the "good" answer sits in position A in the original and
    # position B in the swapped run, so a content-consistent judge reports A then B.
    if w1 == "A" and w2 == "B":
        positional_bias = "content-consistent (correctly picks the good answer in both orders)"
    elif w1 == "A" and w2 == "A":
        positional_bias = "position-biased (always picks the first answer)"
    elif w1 == "B" and w2 == "B":
        positional_bias = "position-biased (always picks the second answer)"
    else:
        positional_bias = f"content-inconsistent (w1={w1}, w2={w2})"

    return {
        "absolute": absolute,
        "pairwise_original": {"winner": w1, "reasoning": r1},
        "pairwise_swapped": {"winner": w2, "reasoning": r2},
        "positional_bias": positional_bias,
        "elapsed_s": round(time.time() - t0, 1),
    }


def eval_trajectory():
    """Scaffold: run the full graph and match the tool-call sequence against
    golden_data.json['trajectories']. Needs the compiled graph (heavy import)."""
    from golden_data import _load  # noqa
    raise NotImplementedError(
        "Trajectory eval requires the running LangGraph agent. See README "
        "(run from backend/ with `python test_react_loop.py` pattern, or wire "
        "evals/llm_evals.py to compiled_graph.stream)."
    )


def main(which="topic"):
    llm = get_llm()
    if which == "topic":
        results = {"topic_classifier": eval_topic_classifier(llm)}
        fname = "metrics_topic.json"
    elif which == "judge":
        results = {"llm_judge": eval_judge(llm)}
        fname = "metrics_judge.json"
    else:
        raise SystemExit(f"unknown --eval {which}")

    out = os.path.join(OUT_DIR, fname)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    print(json.dumps(results, indent=2))
    print(f"\n[llm:{which}] wrote {out}")


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--eval", default="topic", choices=["topic", "judge", "trajectory", "e2e"])
    a = ap.parse_args()
    if a.eval in ("trajectory", "e2e"):
        eval_trajectory()
    main(a.eval)
