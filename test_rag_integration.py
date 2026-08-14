import sys
import os

# Ensure we can import app modules
sys.path.append(os.path.join(os.getcwd(), 'backend', 'app'))

from services.rag_service import retrieve_rrl_context, get_chroma_collection
from models.schemas import AgentState
from services.llm_service import node_rag_retrieval, router_after_tool_caller

def run_tests():
    print("--- Test 1: Testing RRL Indexing & Basic Retrieval ---")
    # This will trigger ingestion if not done yet
    collection = get_chroma_collection()
    print(f"Collection '{collection.name}' loaded with {collection.count()} documents.")
    
    query = "relationship between temperature and rice yield"
    context = retrieve_rrl_context(query, top_k=2)
    print(f"\nRetrieval for '{query}':")
    print(context[:500] + "...\n")
    
    query = "rice production and rice price supply shocks"
    context = retrieve_rrl_context(query, top_k=2)
    print(f"Retrieval for '{query}':")
    print(context[:500] + "...\n")
    
    print("\n--- Test 2: Testing deterministic formulation in node_rag_retrieval ---")
    state = AgentState(
        user_query="How does extreme heat affect yield?",
        active_action="ANALYZE_CORRELATION",
        slots={"weather_variables": ["MAX_TEMP", "MEAN_TEMP"], "outcome_metric": "YIELD"}
    )
    res = node_rag_retrieval(state)
    print("Deterministically formulated RAG context returned by node:")
    print(res.get("rag_context", "")[:300] + "...\n")
    
    print("\n--- Test 3: Testing Bypass Routing logic ---")
    state.active_action = "GET_WEATHER_DATA"
    state.user_query = "What was the weather like?"
    route = router_after_tool_caller(state)
    print(f"Route for simple weather query: {route}")
    
    state.user_query = "Can you explain the weather impact on yield?"
    route = router_after_tool_caller(state)
    print(f"Route for weather query with explanation keyword: {route}")

if __name__ == "__main__":
    run_tests()
