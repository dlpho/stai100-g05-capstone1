import os
import json
import uuid
import sys

# Ensure backend directory is in path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), 'app')))

from app.services.llm_service import compiled_graph

def run_test(test_name: str, query: str):
    print(f"\n{'='*80}")
    print(f"TEST: {test_name}")
    print(f"QUERY: '{query}'")
    print(f"{'='*80}")
    
    thread_id = str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}}
    state = {"user_query": query}
    
    for event in compiled_graph.stream(state, config):
        for key, value in event.items():
            print(f"\n--- Node: {key} ---")
            if "error" in value and value["error"]:
                print(f"ERROR: {value['error']}")
            
            if key == "tool_caller":
                if "tool_calls" in value and value["tool_calls"]:
                    calls = value["tool_calls"]
                    for call in calls:
                        print(f"  -> Selected Tool: {call.get('name')}")
                        print(f"  -> Arguments: {call.get('args')}")
                else:
                    print("  -> No tools selected.")
                print(f"  -> Iteration count: {value.get('tool_iteration_count', 0)}")
                
            if key == "tool_execution":
                if "weather_data_markdown" in value:
                    print(f"  -> Tool Observation:\n{value['weather_data_markdown']}")
            
            if key == "location_resolution":
                if "location" in value:
                    loc = value["location"]
                    print(f"  -> Resolved Location: {loc.barangay} -> (lat: {loc.latitude}, lon: {loc.longitude})")

            if key == "generation":
                print(f"FINAL RESPONSE:\n{value.get('final_response', '')}")

    return thread_id

def main():
    # 6. Multi-step query
    run_test("Genuine Multi-step ReAct", "First get the weather for Pampanga from 2023-01-01 to 2023-01-31, and then based on that, predict the palay yield for Pampanga in 2024.")
    
    # 11. Max iteration termination
    run_test("Max iteration test attempt", "Please run a weather analysis for Pampanga from 2023-01-01 to 2023-01-31. Then predict the palay yield for Pampanga in 2024. Then check correlation for palay in Pampanga in 2024. Keep running more analysis on Pampanga indefinitely.")

if __name__ == "__main__":
    main()
