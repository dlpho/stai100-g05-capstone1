import os
import sys
import json
import argparse
import subprocess

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "backend", "app"))
sys.path.insert(0, os.path.dirname(__file__))


def run_unit():
    """Executes the Layer 1 unit evaluations (guardrails, heuristics, routing)."""
    from unit_evals import main
    main()


def run_rag():
    """Executes the Layer 2 RAG evaluations (retrieval precision/recall/MRR)."""
    from rag_evals import main
    main()


def run_llm(which):
    """Executes the Layer 3 LLM-dependent evaluations (topic classifier, LLM-as-judge)."""
    from llm_evals import main
    main(which)


def run_trajectory():
    """Executes the agent trajectory evaluations using pytest."""
    import pytest
    print("Running Trajectory Evals...")
    pytest.main(["-v", os.path.join(os.path.dirname(__file__), "test_trajectory.py")])


def run_e2e():
    """Executes the end-to-end task success evaluations using pytest."""
    import pytest
    print("Running E2E Evals...")
    pytest.main(["-v", os.path.join(os.path.dirname(__file__), "test_e2e.py")])


def summarize():
    """Compiles individual evaluation metrics JSON files into a single summary report."""
    here = os.path.dirname(__file__)
    summary = {}
    files = (
        "metrics_unit.json", 
        "metrics_rag.json", 
        "metrics_topic.json", 
        "metrics_judge.json",
        "metrics_trajectory.json",
        "metrics_e2e.json"
    )
    for f in files:
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
    ap.add_argument("--layer", default="unit", choices=["unit", "rag", "llm", "trajectory", "e2e", "all"])
    ap.add_argument("--eval", default="topic", choices=["topic", "judge", "trajectory", "e2e"])
    a = ap.parse_args()

    if a.layer == "unit":
        run_unit()
    elif a.layer == "rag":
        run_rag()
    elif a.layer == "llm":
        run_llm(a.eval)
    elif a.layer == "trajectory":
        run_trajectory()
    elif a.layer == "e2e":
        run_e2e()
    elif a.layer == "all":
        run_unit()
        run_rag()
        run_llm("topic")
        run_llm("judge")
        run_trajectory()
        run_e2e()
        summarize()
