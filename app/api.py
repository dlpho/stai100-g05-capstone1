import os
import sys
from typing import Optional, List, Dict, Any
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from langchain_openai import ChatOpenAI

# Ensure app path is in Python path for running standalone
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.append(current_dir)

# Load environment variables
load_dotenv(os.path.join(current_dir, "..", ".env"))

# Retrieve DeepSeek configuration
api_key = os.getenv("DEEPSEEK_API_KEY")
model_name = os.getenv("DEEPSEEK_MODEL", "deepseek-v4-flash")
base_url = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")

if not api_key:
    # Use a dummy API key for testing/compiling if none found
    api_key = "sk-placeholder"

# Initialize LangChain LLM
llm = ChatOpenAI(
    api_key=api_key,
    model=model_name,
    base_url=base_url
)

# Import agent (after setting sys.path and initializing LLM)
from core.agent import WeatherAgent

app = FastAPI(title="Weather AI Assistant API")
agent = WeatherAgent(llm)

class ChatRequest(BaseModel):
    question: str
    session_id: str = "default"
    selected_location: Optional[Dict[str, Any]] = None

class ChatResponse(BaseModel):
    status: str
    answer: Optional[str] = None
    location: Optional[str] = None
    candidates: Optional[List[Dict[str, Any]]] = None

@app.post("/api/chat", response_model=ChatResponse)
def chat(request: ChatRequest):
    """
    Handles user chat inquiries. Uses coordinate/RAG analysis and processes location ambiguity.
    """
    try:
        result = agent.process_query(
            question=request.question,
            session_id=request.session_id,
            selected_location=request.selected_location
        )
        
        if result.get("status") == "ambiguous":
            return ChatResponse(
                status="ambiguous",
                candidates=result.get("candidates")
            )
        return ChatResponse(
            status="success",
            answer=result.get("answer"),
            location=result.get("location")
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
def health_check():
    """
    Health check endpoint to verify the server is running.
    """
    return {"status": "ok"}

