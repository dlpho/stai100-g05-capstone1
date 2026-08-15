import sys
import os
import io

# Force UTF-8 encoding for stdout
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from services.llm_service import compiled_graph
from models.schemas import AgentState
from langchain_core.messages import HumanMessage

def run_test():
    config = {"configurable": {"thread_id": "test_bug_followup_2"}}
    
    # Q1
    q1 = "What was the weather in Nueva Ecija during September 2023?"
    print(f"\n{'='*80}\nTEST QUERY 1: {q1}\n{'='*80}\n")
    state1 = AgentState(user_query=q1, messages=[HumanMessage(content=q1)])
    result1 = compiled_graph.invoke(state1, config=config)
    print(f"\n[FINAL RESPONSE 1]\n{result1.get('final_response')}")
    
    # Inspect state messages
    print("\n--- MESSAGES AFTER Q1 ---")
    for i, msg in enumerate(result1.get("messages", [])):
        tc = getattr(msg, 'tool_calls', None)
        print(f"{i}: {type(msg).__name__} (tool_calls={tc})")
        if type(msg).__name__ == "ToolMessage":
            print(f"  ToolMessage content: {msg.content[:100]}...")

    # Q2
    q2 = "What was the soil moisture in Nueva Ecija in September 2023?"
    print(f"\n{'='*80}\nTEST QUERY 2: {q2}\n{'='*80}\n")
    state2 = AgentState(
        user_query=q2, 
        messages=result1.get("messages", []),
        summary=result1.get("summary", ""),
        slots=result1.get("slots", {})
    )
    result2 = compiled_graph.invoke(state2, config=config)
    print(f"\n[FINAL RESPONSE 2]\n{result2.get('final_response')}")
    
    print("\n--- MESSAGES AFTER Q2 ---")
    for i, msg in enumerate(result2.get("messages", [])):
        tc = getattr(msg, 'tool_calls', None)
        print(f"{i}: {type(msg).__name__} (tool_calls={tc})")
        if type(msg).__name__ == "ToolMessage":
            print(f"  ToolMessage content: {msg.content[:100]}...")

if __name__ == "__main__":
    run_test()
