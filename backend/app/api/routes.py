from fastapi import APIRouter
from app.models.schemas import UserQuery
from app.services.llm_service import compiled_graph
from app.core.env import ENABLE_MLFLOW
import logging

logger = logging.getLogger(__name__)
router = APIRouter()

@router.post("/chat")
def chat_endpoint(query: UserQuery):
    graph_input = {
        "user_query": query.user_query, 
        "waiting_for_location": False, 
        "error": None
    }
    
    if ENABLE_MLFLOW:
        try:
            import mlflow
            with mlflow.start_run(run_name="agent_execution"):
                response = compiled_graph.invoke(graph_input)
        except Exception as e:
            logger.error(f"MLflow tracing failed: {e}. Executing graph invocation directly without MLflow.")
            response = compiled_graph.invoke(graph_input)
    else:
        response = compiled_graph.invoke(graph_input)
    
    return {
        "response": response.get("final_response"),
        "intent": response.get("intent"),
        "waiting_for_location": response.get("waiting_for_location")
    }

