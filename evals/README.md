# WeatherTato — Evaluation Suite

A three-layer evaluation suite (unit / trajectory / end-to-end) plus RAG-specific
metrics and an LLM-as-judge, per the project evaluation spec. All golden cases live in
`evals/golden_data.json`; results are written as `evals/metrics_*.json`.

## Run

```bash
cd <project-root>
python evals/run_evals.py --layer unit              # deterministic (no LLM)
python evals/run_evals.py --layer rag               # retrieval (needs Qwen3-Embedding-0.6B)
python evals/run_evals.py --layer llm --eval topic  # guardrail topic classifier (LLM)
python evals/run_evals.py --layer llm --eval judge  # LLM-as-judge
python evals/run_evals.py --layer all               # all of the above + summary
```

Trajectory and end-to-end layers require the full LangGraph agent and are scaffolded in
`llm_evals.py` (see "Layer 2 / 3" below). Run them from PyCharm against a live server.

---

## Quantitative metrics (≥3 required) with interpretation

### 1. Production model R² = 0.803 (vs Seasonal Avg 0.057)
The strongest headline. Lasso with 4-month-lagged weather explains ~80% of the
year-to-year variance in palay *production* volume, while the naive "average for this
month" explains almost none (0.057). Interpretation: weather acts on production mainly
through *area planted* (dry season → less area → less volume), so production is highly
weather-predictable. (Yield is far harder — see below.)

### 2. Guardrail precision/recall/F1
| check | precision | recall | F1 |
|---|---|---|---|
| prompt-injection detection | 1.00 | 1.00 | 1.00 |
| out-of-scope detection | 1.00 | 1.00 | 1.00 |
| PII redaction | 1.00 | 1.00 | 1.00 |

Interpretation: injection, out-of-scope, and PII redaction are all exact on the
golden set. (PII name redaction was previously case-sensitive — "My name is …" leaked —
fixed by adding `re.IGNORECASE` to `NAME_REGEX`.)

### 3. LLM topic-classifier accuracy = 1.00 (blocked + topic, n=9)
The few-shot DeepSeek classifier correctly routes WEATHER / CROP / RELATIONSHIP /
GENERAL (allowed) and ADVICE / FORECAST / OFF_TOPIC (blocked) on all 9 golden queries.

### 4. RAG retrieval — MRR = 0.875, recall@2 = 1.00, precision@2 = 0.50
After re-ingesting `knowledge.md` (the shipped `chroma_db` collection was empty, 0 docs),
retrieval always surfaces the relevant section (recall 1.0), usually at rank 1 (MRR 0.875).
Precision 0.5 is expected for top_k=2 with a single relevant section.

### 5. LLM-as-judge sanity
Absolute scoring separates a correct answer (5/5) from a hallucinated one (faithfulness
1/5) and an off-topic one (relevance 1/5). Pairwise comparison is content-consistent —
the judge picks the better answer in both presentation orders (no positional bias).

### Supporting model metrics (from `train_model.py` bench)
| target | MAE | RMSE | R² |
|---|---|---|---|
| production (MT) | 19,828 | 26,055 | **0.803** |
| yield (MT/ha) | 0.401 | 0.899 | 0.312 |
| price (PHP/kg) | 1.314 | 1.894 | 0.912 |

Yield is inherently the hardest target (per-hectare efficiency, only ~30% weather-driven);
price is persistence-dominated (prev-month baseline R²=0.917).

---

## Evaluative evidence — failures and edge cases

**Failure cases found by the suite (all since fixed):**
1. **Prediction tool was broken.** `predict_service.predict_yield/price` raised
   `KeyError: relative_humidity_2m_mean_1m/_2m/_3m not in index` — the shipped ridge
   models expected 12 weather variables while `relative_humidity_2m_mean` was dropped
   and never seeded. Fixed by rewriting `predict_service` to use the same 4-month lag
   feature engineering as `train_model.py` and the newly-trained Lasso models (and added
   `predict_production`).
2. **RAG collection was empty.** The committed `chroma_db` had 0 documents, so
   `retrieve_rrl_context` returned empty context. Re-ingested `knowledge.md` (8 chunks).
3. **PII name redaction was case-sensitive.** `NAME_REGEX` only matched lowercase
   `my name is` / `i am named`; "My name is Maria Santos" and "I am named Jose" leaked.
   Fixed with `re.IGNORECASE`.

**Edge / corner cases exercised:**
- **Ambiguous location** — "San Fernando" resolves to AMBIGUOUS (Pampanga vs La Union),
  correctly refusing to guess. (Recorded as an edge case in the golden data.)
- **Not-found / empty / numeric input** — "zzzzzz not a real place", `""`, "12345" all
  return NOT_FOUND without crashing.
- **Missing slot / unsupported location / runaway loop** — covered by the trajectory
  scaffold (`test_react_loop.py` cases 8–11): missing-location blocking, unsupported
  province ("Cebu"), and max-iteration termination.

---

## Mapping to the required evaluation spec

| Spec requirement | Where it lives |
|---|---|
| Unit evals — tool execution checks | `unit_evals.py` (`eval_sql_and_tools`) |
| Unit evals — retrieval quality (P/R/MRR) | `rag_evals.py` |
| Unit evals — generation groundedness | `judge_prompts.py` faithfulness criterion + `llm_evals.eval_judge` |
| Trajectory evals — step ordering / golden path | `llm_evals.eval_trajectory` (scaffold) + `golden_data.json["trajectories"]` |
| End-to-end — task success / latency / tokens | `llm_evals.eval_e2e` (scaffold) |
| End-to-end — policy & safety adherence | `unit_evals.eval_guardrails` + topic classifier |
| RAG — context recall/precision/faithfulness | `rag_evals.py` (recall/precision/MRR); faithfulness via judge |
| LLM-as-judge — absolute + pairwise + bias calibration | `judge_prompts.py` + `llm_evals.eval_judge` |
| Human evaluation | methodology below |

## Human evaluation (methodology)

To establish the golden dataset and catch subtle harms, run a blind annotation pass:
- Sample ~30 real queries from the trajectory/e2e logs (mix of success, failure, edge).
- Two independent raters score each answer 1–5 on correctness / completeness /
  faithfulness / relevance / clarity using the `ABSOLUTE_JUDGE_SYSTEM` rubric.
- Report inter-annotator agreement (Cohen's κ or Krippendorff's α); adjudicate ties.
- Use the agreed labels to (a) validate the LLM-judge's agreement with humans and
  (b) grow `golden_data.json` for regression testing.

## Notes

- Trajectory/e2e layers are stubs pending wiring to `compiled_graph`; they print an
  `NotImplementedError` with a pointer to the run pattern in `backend/test_react_loop.py`.
- Golden data and prompts are version-controlled; generated `metrics_*.json` are outputs.
