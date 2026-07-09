import sys
import os
import json
import time
import re
import pandas as pd

# Fix path to import app packages directly
workspace_dir = os.path.abspath(os.path.dirname(__file__))
backend_dir = os.path.join(workspace_dir, "backend")
sys.path.insert(0, backend_dir)

# Override environment to ensure MLflow logging is enabled
os.environ["ENABLE_MLFLOW"] = "true"

import mlflow
from app.services.llm_service import compiled_graph
from app.core.env import MLFLOW_TRACKING_URI, MLFLOW_EXPERIMENT_NAME

# Setup MLflow experiment (checking for active server, falling back to local SQLite if offline)
use_local_db = False
if MLFLOW_TRACKING_URI.startswith("http"):
    import requests
    try:
        requests.get(MLFLOW_TRACKING_URI, timeout=1)
    except Exception:
        print(f"MLflow server at {MLFLOW_TRACKING_URI} is not running.")
        use_local_db = True

if use_local_db:
    local_uri = "sqlite:///mlflow_data/mlflow.db"
    print(f"Falling back to direct SQLite tracking database: {local_uri}")
    mlflow.set_tracking_uri(local_uri)
else:
    mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)

mlflow.set_experiment(MLFLOW_EXPERIMENT_NAME)

# Load dataset
with open(os.path.join(workspace_dir, "eval_dataset.json"), "r", encoding="utf-8") as f:
    eval_cases = json.load(f)

print(f"Starting WeatherTato Chatbot Evaluation against {len(eval_cases)} test cases...")
results = []

# List of plain language categories we expect in generation outputs
PLAIN_LANG_KEYWORDS = [
    "cool", "warm", "hot", "very hot",
    "calm", "breezy", "windy", "strong",
    "low", "comfortable", "high", "very high",
    "light", "moderate", "heavy", "very heavy"
]

# Create a parent evaluation run to group all test cases
with mlflow.start_run(run_name="chatbot_automated_evaluation") as parent_run:
    for i, case in enumerate(eval_cases):
        query = case["query"]
        expected_type = case["expected_type"]
        discipline = case["discipline"]
        expected_location_level = case.get("expected_location_level")
        verify_context = case.get("verify_context", False)
        
        print(f"[{i+1}/{len(eval_cases)}] Running '{query}' under [{discipline}]...")
        
        # Start a nested run for each test case to capture individual latency, parameters, and trace logs
        with mlflow.start_run(run_name=f"case_{i+1}_{expected_type}", nested=True):
            mlflow.log_param("case_number", i + 1)
            mlflow.log_param("query", query)
            mlflow.log_param("expected_type", expected_type)
            mlflow.log_param("discipline", discipline)
            if expected_location_level:
                mlflow.log_param("expected_location_level", expected_location_level)
            
            start_time = time.time()
            graph_input = {
                "user_query": query, 
                "waiting_for_location": False, 
                "error": None
            }
            
            try:
                # Invoke the LangGraph compiled state graph (which autologs trace and tokens via MLflow)
                res = compiled_graph.invoke(graph_input)
                latency = time.time() - start_time
                
                final_response = res.get("final_response", "") or ""
                actual_intent = res.get("intent", "") or ""
                is_waiting = res.get("waiting_for_location", False)
                error_state = res.get("error", "")
                weather_data = res.get("weather_data_markdown", "") or ""
                
                # Check for safety refusals/disclaimers
                is_refusal = (
                    "cannot provide" in final_response.lower() 
                    or "blocked" in final_response.lower() 
                    or "safety" in final_response.lower() 
                    or "only answer" in final_response.lower()
                    or "not provide" in final_response.lower()
                    or (error_state and "blocked" in str(error_state).lower())
                    or (error_state and "cannot provide" in str(error_state).lower())
                )
                
                # Determine Correctness based on disciplines and rules
                correct = True
                failure_reason = []

                # Rule 1: Type Correctness
                if expected_type == "refusal":
                    if not is_refusal:
                        correct = False
                        failure_reason.append("Expected guardrail refusal but was not triggered")
                elif expected_type == "off-topic":
                    if not (actual_intent == "off-topic" or is_refusal):
                        correct = False
                        failure_reason.append(f"Expected off-topic but intent was: {actual_intent}")
                else:
                    if is_refusal:
                        correct = False
                        failure_reason.append("Query was incorrectly refused by safety guardrails")
                    elif actual_intent != expected_type:
                        correct = False
                        failure_reason.append(f"Intent mismatch: Expected {expected_type}, got {actual_intent}")

                # Rule 2: Geocoding Location Resolution Correctness
                if correct and expected_location_level:
                    location_obj = res.get("location")
                    if expected_location_level == "missing":
                        if not is_waiting:
                            correct = False
                            failure_reason.append("Expected state to wait for location but it proceeded")
                    else:
                        if not location_obj:
                            correct = False
                            failure_reason.append("Location slot was not resolved")
                        else:
                            lat = location_obj.latitude
                            lng = location_obj.longitude
                            
                            # Manila coordinates are used as fallback defaults
                            is_manila_default = (lat == "14.5995" and lng == "120.9842")
                            
                            # If we expect a specific resolved location (excluding Manila queries themselves), 
                            # the coordinates must not be the fallback Manila values
                            if is_manila_default and "manila" not in query.lower():
                                correct = False
                                failure_reason.append(f"Location resolved incorrectly (fell back to Manila coordinates: {lat}, {lng})")

                # Rule 3: RAG Grounding & Context Faithfulness Correctness
                if correct and verify_context:
                    if not weather_data or "No data available" in weather_data:
                        correct = False
                        failure_reason.append("RAG context is empty or missing weather telemetry data")
                    else:
                        # Extract all numbers from weather table to check if they appear in final response
                        float_numbers = re.findall(r'\b\d+\.\d+\b', weather_data)
                        
                        # Filter out common test/default coordinates so they don't give false positives
                        coords_and_fallbacks = ["14.5995", "120.9842", "9.85", "124.2", "9.871", "124.218", "14.599", "120.984"]
                        float_numbers = [num for num in float_numbers if num not in coords_and_fallbacks]
                        
                        # Verify at least one float telemetry metric is cited in response
                        has_numeric_reference = False
                        response_lower = final_response.lower()
                        for num in float_numbers:
                            val = float(num)
                            # If value is zero, allow qualitative indicators like "no rain", "zero", or "dry"
                            if val == 0.0:
                                if any(kw in response_lower for kw in ["no rain", "zero", "0", "none", "dry", "clear"]):
                                    has_numeric_reference = True
                                    break
                            if (num in final_response 
                                or f"({num}" in final_response 
                                or f"{val:.1f}" in final_response 
                                or f"{val:.2f}" in final_response
                                or f"({round(val)}" in final_response):
                                has_numeric_reference = True
                                break
                                
                        if not has_numeric_reference and float_numbers:
                            correct = False
                            failure_reason.append("Response did not reference telemetry numbers from the context table")

                        # Verify at least one plain language descriptor was used (warm, breezy, heavy, comfortable, etc.)
                        response_lower = final_response.lower()
                        has_plain_lang_desc = any(desc in response_lower for desc in PLAIN_LANG_KEYWORDS)
                        
                        if not has_plain_lang_desc:
                            correct = False
                            failure_reason.append("Response lacked plain-language interpretations (e.g., Warm, Heavy, Breezy)")

                mlflow.log_metric("latency_seconds", latency)
                mlflow.log_metric("correctness", 1.0 if correct else 0.0)
                mlflow.log_text(final_response, "response.txt")
                if failure_reason:
                    mlflow.log_text("; ".join(failure_reason), "failure_reason.txt")
                
                results.append({
                    "Case": i + 1,
                    "Discipline": discipline,
                    "Query": query,
                    "Expected": expected_type,
                    "Actual Intent": actual_intent,
                    "Correctness": 1 if correct else 0,
                    "Latency (s)": round(latency, 3),
                    "Status": "Success" if correct else "Failed",
                    "Notes": "; ".join(failure_reason) if failure_reason else "Pass"
                })
            except Exception as e:
                latency = time.time() - start_time
                mlflow.log_metric("latency_seconds", latency)
                mlflow.log_metric("correctness", 0.0)
                mlflow.log_text(str(e), "error.txt")
                results.append({
                    "Case": i + 1,
                    "Discipline": discipline,
                    "Query": query,
                    "Expected": expected_type,
                    "Actual Intent": "error",
                    "Correctness": 0,
                    "Latency (s)": round(latency, 3),
                    "Status": "Failed",
                    "Notes": f"Execution error: {e}"
                })

    # Create Summary Dataframe
    df = pd.DataFrame(results)
    
    # Save detailed CSV locally
    mlflow_data_dir = os.path.join(workspace_dir, "mlflow_data")
    os.makedirs(mlflow_data_dir, exist_ok=True)
    report_csv = os.path.join(mlflow_data_dir, "evaluation_report.csv")
    df.to_csv(report_csv, index=False)
    
    # Log summary table and summary metrics to MLflow parent run
    accuracy = df["Correctness"].mean() * 100
    avg_latency = df["Latency (s)"].mean()
    
    mlflow.log_metric("overall_accuracy_percentage", accuracy)
    mlflow.log_metric("average_latency_seconds", avg_latency)
    mlflow.log_table(data=df, artifact_file="evaluation_summary_table.json")
    
    print("\n" + "="*50)
    print("WEATHERTATO EVALUATION RUN COMPLETED")
    print("="*50)
    print(f"Overall Correctness: {accuracy:.2f}%")
    print(f"Average Latency:     {avg_latency:.3f} seconds")
    print(f"Detailed CSV Report: {report_csv}")
    print(f"Parent Run ID:       {parent_run.info.run_id}")
    print("All traces, metrics, and summary tables have been successfully logged to MLflow.")
    print("="*50 + "\n")
