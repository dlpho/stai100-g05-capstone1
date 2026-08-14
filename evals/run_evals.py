"""
WeatherTato evaluation-suite CLI.

Usage (from project root):
  python evals/run_evals.py --layer unit            # deterministic component checks
  python evals/run_evals.py --layer rag             # retrieval quality (needs embedding model)
  python evals/run_evals.py --layer llm --eval topic   # guardrail topic classifier
  python evals/run_evals.py --layer llm --eval judge   # LLM-as-judge
  python evals/run_evals.py --layer all             # everything runnable, then a summary

Trajectory + end-to-end evals need the full LangGraph agent + a running server;
see README.md ("Layer 2 / 3").
"""
import os
import sys
import json
import argparse

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "backend", "app"))
sys.path.insert(0, os.path.dirname(__file__))


def run_unit():
    from unit_evals import main
    main()


def run_rag():
    from rag_evals import main
    main()


def run_llm(which):
    from llm_evals import main
    main(which)


def summarize():
    here = os.path.dirname(__file__)
    summary = {}
    for f in ("metrics_unit.json", "metrics_rag.json", "metrics_topic.json", "metrics_judge.json"):
        p = os.path.join(here, f)
        if os.path.exists(p):
            summary[f.replace("metrics_", "").replace(".json", "")] = json.load(open(p, encoding="utf-8"))
    out = os.path.join(here, "metrics_summary.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)
    print(json.dumps(summary, indent=2))
    print(f"\n[summary] wrote {out}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--layer", default="unit", choices=["unit", "rag", "llm", "all"])
    ap.add_argument("--eval", default="topic", choices=["topic", "judge", "trajectory", "e2e"])
    a = ap.parse_args()

    if a.layer == "unit":
        run_unit()
    elif a.layer == "rag":
        run_rag()
    elif a.layer == "llm":
        run_llm(a.eval)
    elif a.layer == "all":
        run_unit()
        run_rag()
        run_llm("topic")
        run_llm("judge")
        summarize()
