"""
WeatherTato — API Route Handler
"""
import logging
import sqlite3
from fastapi import APIRouter

from models.schemas import UserQuery
from services.llm_service import compiled_graph
from core.env import ENABLE_MLFLOW, MLFLOW_TRACKING_URI, MLFLOW_EXPERIMENT_NAME

logger = logging.getLogger(__name__)
router = APIRouter()

def get_db():
    conn = sqlite3.connect("data/weathertato.db", check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


if ENABLE_MLFLOW:
    try:
        import mlflow
        mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)
        mlflow.set_experiment(MLFLOW_EXPERIMENT_NAME)
    except Exception as e:
        logger.warning(f"[MLflow Warning] Failed to initialize MLflow tracking: {e}")


def run_agent(query: UserQuery) -> dict:
    """Hydrate conversation history and invoke the LangGraph agent."""
    from langchain_core.messages import HumanMessage, AIMessage
    config = {"configurable": {"thread_id": query.session_id}}
    
    # Map input history list to LangChain message instances
    messages = []
    for msg in query.history or []:
        if msg.role == "user":
            messages.append(HumanMessage(content=msg.content))
        elif msg.role == "assistant":
            messages.append(AIMessage(content=msg.content))
            
    graph_input = {
        "user_query": query.user_query, 
        "waiting_for_location": False, 
        "error": None,
        "messages": messages
    }
    
    try:
        if ENABLE_MLFLOW:
            try:
                import mlflow
                response = compiled_graph.invoke(graph_input, config=config)
            except Exception as mlflow_err:
                logger.error(f"MLflow tracing failed: {mlflow_err}. Executing graph invocation directly without MLflow.")
                response = compiled_graph.invoke(graph_input, config=config)
        else:
            response = compiled_graph.invoke(graph_input, config=config)

        return {
            "response": response.get("final_response"),
            "intent": response.get("intent"),
            "waiting_for_location": response.get("waiting_for_location"),
            "error_detail": None
        }
    except Exception as e:
        logger.error(f"Graph execution failed: {e}", exc_info=True)
        return {
            "response": "Sorry, I couldn't process that at the moment. Please try again.",
            "intent": None,
            "waiting_for_location": False,
            "error_detail": str(e)
        }


@router.post("/chat")
def chat_endpoint(query: UserQuery) -> dict:
    """Handle a single chat turn from the Streamlit frontend."""
    if ENABLE_MLFLOW:
        try:
            import mlflow
            exp = mlflow.set_experiment(MLFLOW_EXPERIMENT_NAME)
            with mlflow.start_run(experiment_id=exp.experiment_id, run_name="agent_execution"):
                return run_agent(query)
        except Exception as e:
            logger.warning(f"[MLflow Warning] MLflow tracking failed: {e}")
            return run_agent(query)
    return run_agent(query)
