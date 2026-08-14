import os
import sys
import json
import time
import pytest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "backend", "app"))

from backend.app.services.llm_service import compiled_graph
from evals.llm_evals import get_llm, _judge_absolute

_RESULTS = []

@pytest.fixture(scope="module", autouse=True)
def write_metrics():
    yield
    out = os.path.join(os.path.dirname(__file__), "metrics_e2e.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump({"e2e": {"cases": _RESULTS, "n_cases": len(_RESULTS)}}, f, indent=2)

def test_e2e_latency_tokens_judge():
    query = "What was the rainfall in Pampanga last month?"
    config = {"configurable": {"thread_id": "test_e2e"}}
    
    t0 = time.time()
    
    # We invoke the graph with the query
    result = compiled_graph.invoke({"user_query": query}, config=config)
    
    elapsed = time.time() - t0
    
    # Extract final response from the last AIMessage or state
    final_response = result.get("final_response", "")
    
    # Try to extract token usage from the last AIMessage metadata
    tokens = None
    messages = result.get("messages", [])
    for msg in reversed(messages):
        if getattr(msg, "response_metadata", None):
            if "token_usage" in msg.response_metadata:
                tokens = msg.response_metadata["token_usage"].get("total_tokens")
                break
                
    # Use LLM judge to evaluate
    llm = get_llm()
    
    # Provide the final response and query to judge
    case = {
        "query": query,
        "context": "Context retrieved by the agent.",
        "answer": final_response
    }
    
    judge_result = _judge_absolute(llm, case)
    
    relevance_score = judge_result.get("relevance", 0)
    overall_score = judge_result.get("overall", 0)
    
    _RESULTS.append({
        "query": query,
        "elapsed_s": round(elapsed, 2),
        "tokens": tokens,
        "judge_scores": judge_result,
        "pass": elapsed < 30.0 and (type(relevance_score) in (int, float) and relevance_score >= 4)
    })
    
    # Assert latency
    assert elapsed < 30.0, f"Latency {elapsed} exceeded 30 seconds"
    
    # Assert judge score
    if type(relevance_score) in (int, float):
        assert relevance_score >= 4, f"Judge score {relevance_score} is below 4"

