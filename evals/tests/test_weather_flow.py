import sys
import os
import io

# Force UTF-8 encoding for stdout to avoid charmap errors on Windows
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# Add backend directory to sys.path so we can import services
backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from services.llm_service import compiled_graph
from models.schemas import AgentState
from langchain_core.messages import HumanMessage

def run_test(query: str):
    print(f"\n{'='*80}")
    print(f"TEST QUERY: {query}")
    print(f"{'='*80}\n")
    
    state = AgentState(user_query=query, messages=[HumanMessage(content=query)])
    config = {"configurable": {"thread_id": f"test_{hash(query)}"}}
    
    result = compiled_graph.invoke(state, config=config)
    
    print("\n[RESULT]")
    print(f"Action: {result.get('active_action')}")
    print(f"Slots: {result.get('slots')}")
    print(f"Missing Slots: {result.get('missing_slots')}")
    print(f"Error: {result.get('error')}")
    
    if result.get("final_response"):
        print(f"\n[FINAL RESPONSE]\n{result.get('final_response')}")
        
    return result

if __name__ == "__main__":
    queries = [
        "Analyze how weather is associated with palay yield in Nueva Ecija from 2012 to 2024. Report the correlation coefficient and strongest lag for each variable, and explain the relationship.",
        "What is the correlation between rainfall and yield in Nueva Ecija?",
        "Can you get weather data for Nueva Ecija 2023 September?",
        "Can you get weather data for Isabela 2023 September?",
        "Analyze weather and palay yield in Isabela in 2023.",
    ]
    
    for q in queries:
        run_test(q)
