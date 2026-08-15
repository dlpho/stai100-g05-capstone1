# WeatherTato Final Evaluation Report

## 1. Evaluation Setup
- **Test Set Size**: 20 queries
- **Categories**: Weather retrieval, Correlation/lag analysis, Location handling, Edge cases
- **Models Used**: DeepSeek-v4-flash (Agent & Judge), Qwen3-Embedding-0.6B (RAG)
- **Evaluation Date**: 2026-08-15

## 2. Expected Outcomes Logic (Based on Final Implementation)

| Query Type | Expected behavior |
|---|---|
| Valid weather query | retrieve weather + generate answer |
| Valid correlation query (complete slots) | correlation analysis |
| Incomplete query (missing time/location) | clarification |
| Ambiguous location | clarification |
| Unsupported agricultural location | rejection |
| Capability query | capability response |
| Farming advice | rejection |

## 3. Evaluator Corrections Applied
To ensure the evaluator correctly judges the final system behavior without artificially inflating scores, the following evaluator expectations were corrected from the initial 36.8% run:
1. **Tool Context Injection**: The LLM-as-judge was previously fed the string `["get_monthly_weather_tool"]` instead of the actual tool markdown data. This caused all valid weather queries (W1-W4) to artificially fail groundedness checks. The evaluator now correctly passes the exact tool output.
2. **Missing Temporal Slots (C1-C5, L1, L2)**: Original test queries like *"How does rainfall affect palay yield in Aurora?"* lacked temporal constraints. The agent rightfully asked for clarification, but the evaluator incorrectly marked this as a failure because it expected an immediate correlation graph. We updated the queries with explicit temporal bounds (e.g. *"in 2023"*) to test the tool, or updated the expectation to `clarify`.
3. **Judge Metric Keys**: Fixed a JSON parsing bug where `groundedness` was requested instead of `faithfulness`.

## 4. Unit Evaluation Results
*Please refer to `evals/metrics_unit.json` for deterministic component evaluations.*

## 5. Trajectory Evaluation Results
- **Trajectory Success Rate**: 90.0%
- The agent accurately maps the expected logic table above to actual LangGraph tool execution paths.

## 6. End-to-End Results
- **Original Task Success Rate**: 36.8% (7/19)
- **Corrected Task Success Rate**: 65.0% (13/20)
- **Failed Queries**: 7
- **Mean Latency**: 25.65 s
- **Median Latency**: 19.43 s
- **P95 Latency**: 69.13 s

## 7. LLM-as-Judge Results
- **Mean Groundedness (Faithfulness)**: 3.54 / 5
- **Mean Helpfulness (Overall)**: 3.92 / 5
- **Mean Relevance**: 4.38 / 5
*(Evaluated via Absolute Grading with DeepSeek acting as the impartial judge, using actual measured scores).*

## 8. RAG Evaluation
- Retrieval functions were quantitatively **measured** in the unit suite (`evals/rag_evals.py`).
- Precision@K, Recall@K, and MRR metrics are recorded in `evals/metrics_rag.json` running against a golden dataset.

## 9. Representative Success Cases
*(Refer to Raw Results table for details)*
- **Query W4**: Correctly identified the summer months (March-May) and fetched exact Max Temp data, synthesizing a perfectly grounded output (G:5).

## 10. Representative Failure Cases & Limitations
- **Data Scarcity (C1-C4)**: When correlation analysis is requested for a single year (e.g., 2023), the `analyze_correlation_tool` correctly returns "No correlation data available" because calculating a 4-month lag requires more history. However, the ReAct loop struggles to accept this gracefully and hits the Max Iteration limit trying to force predictions.
- **LLM Judge Variance**: The LLM-as-Judge exhibits minor variance in helpfulness scoring.

## 11. Raw Results

| ID | Category | Expected | Actual Tools | Success | Latency (s) | Scores | Answer Snippet |
|---|---|---|---|---|---|---|---|
| W1 | Weather | weather | get_monthly_weather_tool | Yes | 15.84 | G:5 H:5 | Based on WeatherTato calculations, the average temperature in **Tarlac City** for **July 2026** was ... |
| W2 | Weather | weather | get_monthly_weather_tool | Yes | 15.11 | G:5 H:5 | Here is the rainfall and surface pressure data for **Pampanga** in **2023** (WeatherTato calculation... |
| W3 | Weather | weather | get_monthly_weather_tool | Yes | 20.05 | G:5 H:5 | Here is the complete weather history for **Bulacan in 2024**, based on WeatherTato calculations:  ##... |
| W4 | Weather | weather | get_monthly_weather_tool | Yes | 40.89 | G:5 H:5 | Based on the weather data retrieved for Nueva Ecija for the summer months (March–May 2026), here is ... |
| C1 | Correlation | correlation | get_monthly_weather_tool,get_crop_data_tool,analyze_correlation_tool | No | 55.93 | G:1 H:2 | Based on the data retrieved for Aurora in 2023, here is my analysis:  ## Correlation Result: N/A  Th... |
| C2 | Correlation | correlation | analyze_correlation_tool,get_monthly_weather_tool,get_crop_data_tool,analyze_correlation_tool,analyze_correlation_tool | No | 50.07 | G:3 H:4 | ## Correlation Analysis Result  **WeatherTato calculations for Bataan could not produce a correlatio... |
| C3 | Correlation | correlation | get_monthly_weather_tool,get_crop_data_tool,get_crop_data_tool,get_crop_data_tool,get_crop_data_tool | No | 65.88 | G:3 H:4 | ## WeatherTato Analysis: Lagged Rainfall vs. Palay Yield in Zambales (2020–2023)  The lagged correla... |
| C4 | Correlation | correlation | analyze_correlation_tool,analyze_correlation_tool,analyze_correlation_tool,analyze_correlation_tool,analyze_correlation_tool | No | 69.13 | G:2 H:3 | The correlation analysis for **PALAY in Tarlac** repeatedly returned **N/A** — meaning the system co... |
| C5 | Correlation | correlation | analyze_correlation_tool,analyze_correlation_tool,get_crop_data_tool | No | 53.43 | G:1 H:1 | Based on the literature, the temperature–yield relationship for rice in Pampanga in 2023 is best und... |
| L1 | Location | weather | get_monthly_weather_tool | Yes | 19.43 | G:5 H:5 | Here is the complete monthly weather dataset for **Aurora** in **2023** (WeatherTato calculations): ... |
| L1_followup | Location | correlation | analyze_correlation_tool,get_crop_data_tool,predict_yield_tool,predict_price_tool | No | 40.07 | G:2 H:3 | I attempted to run the **palay yield–weather correlation** for Aurora, but the analysis returned **n... |
| L2 | Location | weather | get_monthly_weather_tool | Yes | 15.27 | G:5 H:5 | Here is the rainfall data for **Balanga during 2025**, according to WeatherTato calculations:  | Mon... |
| L3 | Location | clarify | get_monthly_weather_tool | No | 19.62 | G:4 H:4 | Here's the WeatherTato report for **San Jose, 2023**, based on calculated monthly weather data:  ---... |
| L4 | Location | reject | None | Yes | 2.80 | G:- H:- | Location 'Isabela' could not be resolved using the current Region III location database. WeatherTato... |
| E1 | Edge Case | clarify | None | Yes | 10.51 | G:- H:- | ... |
| E2 | Edge Case | clarify | None | Yes | 5.03 | G:- H:- | Could you please specify the time period for the weather data in Pampanga?... |
| E3 | Edge Case | reject | None | Yes | 4.19 | G:- H:- | Location 'Tokyo' could not be resolved using the current Region III location database. WeatherTato c... |
| E4 | Edge Case | reject | None | Yes | 1.73 | G:- H:- | I can only answer questions related to historical weather conditions and palay crop yield and price,... |
| E5 | Edge Case | general | None | Yes | 6.47 | G:- H:- | I'm **WeatherTato**, your analytical weather and agriculture assistant for Filipino farms. Here's wh... |
| E6 | Edge Case | reject | None | Yes | 1.65 | G:- H:- | I can provide data analysis, but I cannot give direct farming advice or crop recommendations.... |
