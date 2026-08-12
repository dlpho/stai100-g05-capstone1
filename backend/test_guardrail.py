import os
import sys

# Ensure backend directory is in the python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), 'app')))

from langchain_openai import ChatOpenAI
from app.core.guardrails import is_prompt_injection, is_out_of_scope, remove_pii, is_on_topic
from app.core.env import DEEPSEEK_API_KEY, DEEPSEEK_MODEL, DEEPSEEK_BASE_URL

# Initialize LLM
llm = ChatOpenAI(
    model=DEEPSEEK_MODEL,
    api_key=DEEPSEEK_API_KEY,
    base_url=DEEPSEEK_BASE_URL,
    temperature=0,
)

class DummyAgentState:
    def __init__(self, user_query):
        self.user_query = user_query
        self.messages = []
        self.error = None
        self.intent = None

def node_guardrails(state: DummyAgentState) -> dict:
    """Simulates the guardrails node from llm_service.py."""
    query = state.user_query

    # GUARD 1: redacting PII
    clean_query = remove_pii(query)
    
    # GUARD 2: detecting prompt injection & out-of-scope queries
    if is_prompt_injection(clean_query):
        return {"error": "Sorry, it seems your question may violate the system guidelines. Please rephrase your question.", "user_query": clean_query}
    if is_out_of_scope(clean_query):
        return {"error": "Sorry, I can provide weather and palay-related information, correlations, and model estimates, but I cannot recommend what actions to take.", "user_query": clean_query}
        
    # GUARD 3: topic restriction (based on is_on_topic function)
    result = is_on_topic(clean_query, llm, state.messages)
    
    print(f"\n[Guardrail LLM Topic Classifier Output]")
    print(f"Topic: {result.get('topic')}")
    print(f"Allowed: {result.get('allowed')}")
    print(f"Confidence: {result.get('confidence')}")
    print(f"Fallback triggered: {result.get('fallback')}")
    
    if result.get("fallback"):
        return {"error": "I can only answer questions related to historical weather conditions and palay/corn crop yield and price, and their relationships. I cannot provide advice, weather forecasts, or answer off-topic queries.", "user_query": clean_query}
        
    return {"user_query": clean_query}

def main():
    print("=" * 50)
    print("Guardrail Node CLI Tester")
    print("Type 'quit' or 'exit' to stop.")
    print("=" * 50)
    
    while True:
        try:
            query = input("\nEnter query: ")
        except (KeyboardInterrupt, EOFError):
            break
            
        if query.strip().lower() in ["quit", "exit"]:
            break
            
        state = DummyAgentState(query)
        result = node_guardrails(state)
        
        print("\n[Node Output]")
        if "error" in result:
            print(f"BLOCKED - Error message: {result['error']}")
        else:
            print(f"PASSED  - Clean query: {result.get('user_query')}")
            
if __name__ == "__main__":
    main()
