import sys
import os
import io
import json

# Force UTF-8 encoding for stdout
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from services.llm_service import compiled_graph
from models.schemas import AgentState
from langchain_core.messages import HumanMessage

def run_test():
    config = {"configurable": {"thread_id": "test_bug_followup_multiple_turns"}}
    
    print("\n" + "="*80)
    print("TEST SEQUENCE 1: September -> October -> Soil Moisture")
    print("="*80 + "\n")
    
    # Q1
    q1 = "What was the weather in Nueva Ecija in September 2023?"
    print(f"\n[QUERY 1]: {q1}")
    state1 = AgentState(user_query=q1, messages=[HumanMessage(content=q1)])
    result1 = compiled_graph.invoke(state1, config=config)
    print(f"\n[RESPONSE 1]\n{result1.get('final_response')}")
    
    # Q2
    q2 = "What was the weather in Nueva Ecija in October 2023?"
    print(f"\n[QUERY 2]: {q2}")
    state2 = AgentState(
        user_query=q2,
        messages=result1.get("messages", []),
        summary=result1.get("summary", ""),
        slots=result1.get("slots", {})
    )
    result2 = compiled_graph.invoke(state2, config=config)
    print(f"\n[RESPONSE 2]\n{result2.get('final_response')}")
    
    # Q3
    q3 = "What was the soil moisture?"
    print(f"\n[QUERY 3]: {q3}")
    state3 = AgentState(
        user_query=q3,
        messages=result2.get("messages", []),
        summary=result2.get("summary", ""),
        slots=result2.get("slots", {})
    )
    result3 = compiled_graph.invoke(state3, config=config)
    print(f"\n[RESPONSE 3]\n{result3.get('final_response')}")
    
    print("\n" + "="*80)
    print("TEST SEQUENCE 2: September -> Soil Moisture")
    print("="*80 + "\n")
    
    config2 = {"configurable": {"thread_id": "test_bug_followup_two_turns"}}
    
    # Q1
    q1_seq2 = "What was the weather in Nueva Ecija in September 2023?"
    print(f"\n[QUERY 1]: {q1_seq2}")
    state1_seq2 = AgentState(user_query=q1_seq2, messages=[HumanMessage(content=q1_seq2)])
    result1_seq2 = compiled_graph.invoke(state1_seq2, config=config2)
    print(f"\n[RESPONSE 1]\n{result1_seq2.get('final_response')}")
    
    # Q2
    q2_seq2 = "What about soil moisture?"
    print(f"\n[QUERY 2]: {q2_seq2}")
    state2_seq2 = AgentState(
        user_query=q2_seq2,
        messages=result1_seq2.get("messages", []),
        summary=result1_seq2.get("summary", ""),
        slots=result1_seq2.get("slots", {})
    )
    result2_seq2 = compiled_graph.invoke(state2_seq2, config=config2)
    print(f"\n[RESPONSE 2]\n{result2_seq2.get('final_response')}")

if __name__ == "__main__":
    run_test()
