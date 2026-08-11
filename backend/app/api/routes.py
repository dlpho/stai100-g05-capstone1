import sqlite3
from fastapi import APIRouter
import mlflow
from app.models.schemas import UserQuery
from app.services.llm_service import compiled_graph

router = APIRouter()

def get_db():
    conn = sqlite3.connect("data/weathertato.db", check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()

@router.post("/chat")
def chat_endpoint(query: UserQuery):
    config = {"configurable": {"thread_id": query.session_id}}

    with mlflow.start_run(run_name=f"agent_execution_{query.session_id}", nested=True):
        response = compiled_graph.invoke({"user_query": query.user_query, "waiting_for_location": False, "error": None}, config=config)

        return {
            "response": response.get("final_response"),
            "intent": response.get("intent"),
            "waiting_for_location": response.get("waiting_for_location")
        }
