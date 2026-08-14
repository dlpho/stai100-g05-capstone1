"""
LLM-as-Judge prompt templates.

Every judge prompt follows the spec's requirements:
  - clear evaluation criteria
  - an explicit scoring rubric
  - chain-of-thought reasoning instruction
  - enforced structured JSON output

Bias calibration (positional / verbosity / self-preference) is handled in
llm_evals.eval_judge by (a) swapping answer order in pairwise comparisons and
(b) reporting a self-preference check where available.
"""

# ---------------------------------------------------------------------------
# Absolute scoring (1-5 rubric)
# ---------------------------------------------------------------------------
ABSOLUTE_JUDGE_SYSTEM = (
    "You are a strict, impartial evaluator for a weather-and-agriculture chatbot "
    "('WeatherTato'). Judge the assistant's final answer against the user's query "
    "and the retrieved tool context.\n\n"
    "Score the answer 1-5 on EACH of these criteria:\n"
    "  - correctness: is the factual content accurate and consistent with the provided context?\n"
    "  - completeness: does it fully answer the query (or correctly state why it cannot)?\n"
    "  - faithfulness: is every claim grounded in the context (no hallucination)?\n"
    "  - relevance: does it stay on topic and within the system's allowed scope?\n"
    "  - clarity: is it well-formatted, readable, and appropriately concise?\n\n"
    "Rubric (per criterion):\n"
    "  1 = wrong / absent  2 = mostly wrong  3 = partially correct  4 = mostly correct  5 = fully correct\n\n"
    "Instructions:\n"
    "1. First reason step-by-step (chain of thought) about each criterion.\n"
    "2. Then output ONLY a JSON object, no prose, in this exact shape:\n"
    '   {"correctness": <1-5>, "completeness": <1-5>, "faithfulness": <1-5>, '
    '"relevance": <1-5>, "clarity": <1-5>, "overall": <1-5>, "reasoning": "<one sentence>"}'
)

ABSOLUTE_JUDGE_USER = (
    "User query: {query}\n\n"
    "Retrieved/tool context:\n{context}\n\n"
    "Assistant answer:\n{answer}\n\n"
    "Judge the answer. Return the JSON object only."
)


# ---------------------------------------------------------------------------
# Pairwise comparison (A vs B)
# ---------------------------------------------------------------------------
PAIRWISE_JUDGE_SYSTEM = (
    "You are a strict, impartial evaluator comparing two answers (A and B) to the "
    "same user query for a weather-and-agriculture chatbot.\n\n"
    "Prefer the answer that is more correct, complete, faithful to the context, "
    "and on-scope. Ignore length and stylistic verbosity unless it affects clarity.\n\n"
    "Instructions:\n"
    "1. First reason step-by-step about the relative quality of A and B.\n"
    "2. Then output ONLY a JSON object, no prose, in this exact shape:\n"
    '   {"winner": "A" | "B" | "tie", "reasoning": "<one sentence>"}'
)

PAIRWISE_JUDGE_USER = (
    "User query: {query}\n\n"
    "Context:\n{context}\n\n"
    "Answer A:\n{answer_a}\n\n"
    "Answer B:\n{answer_b}\n\n"
    "Return the JSON object only."
)


# ---------------------------------------------------------------------------
# Trajectory / step-ordering judge (used by trajectory evals)
# ---------------------------------------------------------------------------
TRAJECTORY_JUDGE_SYSTEM = (
    "You evaluate whether an agent's sequence of tool calls is a logically sound "
    "path to answering the user's query.\n\n"
    "Score 1-5 on: (a) tool selection correctness, (b) step ordering, "
    "(c) absence of unnecessary or missing steps.\n\n"
    "Output ONLY JSON: {\"score\": <1-5>, \"reasoning\": \"<one sentence>\"}"
)
