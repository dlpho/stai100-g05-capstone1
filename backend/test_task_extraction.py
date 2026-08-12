import os
import sys

# Ensure backend directory is in the python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), 'app')))

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, AIMessage
from app.core.guardrails import is_on_topic
from app.services.llm_service import node_task_extraction, node_guardrails
from app.models.schemas import AgentState
from app.core.env import DEEPSEEK_API_KEY, DEEPSEEK_MODEL, DEEPSEEK_BASE_URL

# Initialize LLM
llm = ChatOpenAI(
    model=DEEPSEEK_MODEL,
    api_key=DEEPSEEK_API_KEY,
    base_url=DEEPSEEK_BASE_URL,
    temperature=0,
)

def main():
    print("=" * 60)
    print("Task + Slot Extraction Node CLI Tester")
    print("Simulates a conversation to test extraction & slot merging.")
    print("Type 'quit' or 'exit' to stop.")
    print("=" * 60)
    
    # Maintain conversation state across turns
    messages = []
    slots = {}
    
    while True:
        try:
            query = input("\nUser Query: ")
        except (KeyboardInterrupt, EOFError):
            break
            
        if query.strip().lower() in ["quit", "exit"]:
            break
            
        # 1. Initialize State
        state = AgentState(
            user_query=query,
            messages=messages,
            slots=slots
        )
        
        # 2. Run Guardrails (sets state.topic)
        guardrail_result = node_guardrails(state)
        
        if "error" in guardrail_result:
            print(f"\n[Guardrail BLOCKED]")
            print(f"Error: {guardrail_result['error']}")
            messages.append(HumanMessage(content=query))
            messages.append(AIMessage(content=guardrail_result['error']))
            continue
            
        state.topic = guardrail_result.get("topic")
        print(f"\n[Guardrail Output] Topic: {state.topic}")
        
        # 3. Run Task Extraction
        extraction_result = node_task_extraction(state)
        
        if "error" in extraction_result:
            print(f"\n[Extraction ERROR]")
            print(f"Error: {extraction_result['error']}")
            messages.append(HumanMessage(content=query))
            messages.append(AIMessage(content=extraction_result['error']))
            continue
            
        active_action = extraction_result.get("active_action")
        slots = extraction_result.get("slots", {})
        missing_slots = extraction_result.get("missing_slots", [])
        is_ready = extraction_result.get("is_ready_for_tools", False)
        
        print("\n[Task + Slot Extraction Result]")
        print(f"Active Action: {active_action}")
        print(f"Merged Slots: {slots}")
        print(f"Missing Slots: {missing_slots}")
        print(f"Is Ready For Tools: {is_ready}")
        
        messages.append(HumanMessage(content=query))
        if not is_ready:
            print(">> ROUTE TO: clarification")
            clarification_msg = f"I am missing: {', '.join(missing_slots)}"
            messages.append(AIMessage(content=clarification_msg))
            print(f"Assistant: {clarification_msg}")
        elif active_action == "DESCRIBE_CAPABILITIES":
            print(">> ROUTE TO: generation (bypassing tools)")
            messages.append(AIMessage(content="[General generation simulated]"))
        else:
            print(">> ROUTE TO: tool_caller")
            messages.append(AIMessage(content="[Tool execution simulated]"))


if __name__ == "__main__":
    main()
