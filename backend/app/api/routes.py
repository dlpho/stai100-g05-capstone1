from fastapi import APIRouter
import mlflow
from models.schemas import UserQuery
from services.llm_service import compiled_graph
from core.env import ENABLE_MLFLOW, MLFLOW_TRACKING_URI, MLFLOW_EXPERIMENT_NAME

router = APIRouter()

if ENABLE_MLFLOW:
    try:
        mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)
        mlflow.set_experiment(MLFLOW_EXPERIMENT_NAME)
    except Exception as e:
        print(f"[MLflow Warning] Failed to initialize MLflow tracking: {e}")

def run_agent(query: UserQuery):
    response = compiled_graph.invoke({"user_query": query.user_query, "waiting_for_location": False, "error": None})
    return {
        "response": response.get("final_response"),
        "intent": response.get("intent"),
        "waiting_for_location": response.get("waiting_for_location")
    }

@router.post("/chat")
def chat_endpoint(query: UserQuery):
    if ENABLE_MLFLOW:
        try:
            with mlflow.start_run(run_name="agent_execution"):
                return run_agent(query)
        except Exception as e:
            print(f"[MLflow Warning] MLflow tracking failed: {e}")
            return run_agent(query)
    return run_agent(query)
