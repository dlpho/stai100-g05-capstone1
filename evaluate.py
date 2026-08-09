import sys
import os
import json
import time
import pandas as pd

# Fix path to import app packages directly
workspace_dir = os.path.abspath(os.path.dirname(__file__))
backend_dir = os.path.join(workspace_dir, "backend")
sys.path.insert(0, backend_dir)

# Override environment to ensure MLflow logging is enabled
os.environ["ENABLE_MLFLOW"] = "true"

import mlflow
from backend.app.services.llm_service import compiled_graph
from backend.app.core.env import MLFLOW_TRACKING_URI, MLFLOW_EXPERIMENT_NAME

# Setup MLflow experiment
os.makedirs("mlflow_data", exist_ok=True)
mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)
mlflow.set_experiment(MLFLOW_EXPERIMENT_NAME)

# Load dataset
with open(os.path.join(workspace_dir, "eval_dataset.json"), "r", encoding="utf-8") as f:
    eval_cases = json.load(f)

print(f"Starting WeatherTato Chatbot Evaluation against {len(eval_cases)} test cases...")
results = []

# Create a parent evaluation run to group all test cases
with mlflow.start_run(run_name="chatbot_automated_evaluation") as parent_run:
    for i, case in enumerate(eval_cases):
        query = case["query"]
        expected_type = case["expected_type"]
        discipline = case["discipline"]
        
        print(f"[{i+1}/{len(eval_cases)}] Running '{query}' under [{discipline}]...")
        
        # Start a nested run for each test case to capture individual latency, parameters, and trace logs
        with mlflow.start_run(run_name=f"case_{i+1}_{expected_type}", nested=True):
            mlflow.log_param("case_number", i + 1)
            mlflow.log_param("query", query)
            mlflow.log_param("expected_type", expected_type)
            mlflow.log_param("discipline", discipline)
            
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
                
                # Check for safety refusals/disclaimers
                is_refusal = (
                    "cannot provide" in final_response.lower() 
                    or "blocked" in final_response.lower() 
                    or "safety" in final_response.lower() 
                    or "only answer" in final_response.lower()
                    or (error_state and "blocked" in str(error_state).lower())
                    or (error_state and "cannot provide" in str(error_state).lower())
                )
                
                # Evaluate correctness
                correct = False
                if expected_type == "refusal":
                    correct = is_refusal
                elif expected_type == "forecast":
                    correct = (actual_intent == "forecast") and (not is_refusal)
                elif expected_type == "analytics":
                    correct = (actual_intent == "analytics") and (not is_refusal)
                elif expected_type == "general":
                    correct = (actual_intent == "general") and (not is_refusal)
                elif expected_type == "off-topic":
                    correct = (actual_intent == "off-topic" or is_refusal)
                
                mlflow.log_metric("latency_seconds", latency)
                mlflow.log_metric("correctness", 1.0 if correct else 0.0)
                mlflow.log_text(final_response, "response.txt")
                
                results.append({
                    "Case": i + 1,
                    "Discipline": discipline,
                    "Query": query,
                    "Expected": expected_type,
                    "Actual Intent": actual_intent,
                    "Is Refusal": is_refusal,
                    "Is Waiting": is_waiting,
                    "Correctness": 1 if correct else 0,
                    "Latency (s)": round(latency, 3),
                    "Status": "Success"
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
                    "Is Refusal": False,
                    "Is Waiting": False,
                    "Correctness": 0,
                    "Latency (s)": round(latency, 3),
                    "Status": f"Failed: {e}"
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
