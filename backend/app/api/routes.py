from fastapi import APIRouter
from fastapi.middleware.cors import CORSMiddleware
import mlflow
from app.models.schemas import UserQuery
from app.services.llm_service import compiled_graph

router = APIRouter()

router.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@router.post("/chat")
def chat_endpoint(query: UserQuery):
    with mlflow.start_run(run_name="agent_execution"):
        response = compiled_graph.invoke({"user_query": query.user_query, "waiting_for_location": False, "error": None})

        return {
            "response": response.get("final_response"),
            "intent": response.get("intent"),
            "waiting_for_location": response.get("waiting_for_location")
        }
