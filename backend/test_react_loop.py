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
    # 1. Weather query
    run_test("1. Weather Query", "What was the rainfall in Pampanga last week?")
    
    # 2. Crop query
    run_test("2. Crop Query", "How much palay was produced in Bulacan in 2023?")
    
    # 3. Correlation query
    run_test("3. Correlation Query", "Is there a correlation between temperature  yield in Nueva Ecija?")
    
    # 4. Prediction query (default variables)
    run_test("4. Prediction Query (Default vars)", "Predict the palay yield for Pampanga in Q3 2025.")
    
    # 5. Prediction query (explicit variables)
    run_test("5. Prediction Query (Explicit vars)", "Predict the palay yield in Bulacan using rainfall and humidity for next year.")
    
    # 6. Multi-step query
    run_test("6. Genuine Multi-step ReAct", "First get the weather for Pampanga last month, and then based on that, predict the palay yield for Pampanga.")
    
    # 7. Conversational follow-up (slot inheritance)
    thread_id = run_test("7. Follow-up Part 1", "What was the palay production in Nueva Ecija in 2023?")
    print("\n--- Sending follow-up to same thread ---")
    config = {"configurable": {"thread_id": thread_id}}
    state = {"user_query": "What about price?"}
    for event in compiled_graph.stream(state, config):
        for key, value in event.items():
            print(f"\n--- Node: {key} ---")
            if key == "tool_caller" and "tool_calls" in value and value["tool_calls"]:
                calls = value["tool_calls"]
                for call in calls:
                    print(f"  -> Selected Tool: {call.get('name')}")
                    print(f"  -> Arguments: {call.get('args')}")
            if key == "generation":
                print(f"FINAL RESPONSE:\n{value.get('final_response', '')}")
                
    # 8. Missing-slot blocking
    run_test("8. Missing-slot blocking", "What was the weather like?")
    
    # 9. Unsupported-location blocking
    run_test("9. Unsupported-location blocking", "What was the palay yield in Cebu?")
    
    # 10. Natural termination (No tool requested)
    run_test("10. Natural termination", "What can you do?")
    
    # Max iteration termination
    run_test("11. Max iteration test attempt", "I want you to analyze the weather for Pampanga, then check the crop yield, then predict the future, then check the correlation, and keep doing this in a loop until you run out of steps.")

if __name__ == "__main__":
    main()
