"""
WeatherTato — Input Safety & Guardrails Utilities
"""
import re
import json
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage


# Regex for simple PII matching, for redaction
EMAIL_REGEX = r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"
# Philippine phone number pattern
PHONE_REGEX = (
    r"(?<!\d)"
    r"(?:09\d{2}[\s-]?\d{3}[\s-]?\d{4}"
    r"|\+639\d{2}[\s-]?\d{3}[\s-]?\d{4})"
    r"(?!\d)"
)
NAME_REGEX = (
    r"\b(?:my\s+name\s+is|i\s+am\s+named|i'm\s+named)"
)

# Phrase-level prompt injection and jailbreak patterns, for detection
# NOTE: avoid single-word patterns for false positives
INJECTION_PATTERNS = [
    "ignore previous instructions",
    "ignore all previous instructions",
    "ignore your instructions",
    "disregard previous instructions",
    "disregard all previous instructions",
    "forget previous instructions",
    "forget all previous instructions",
    "override your instructions",
    "override previous instructions",
    "follow these new instructions",
    "new instructions",
    "system prompt",
    "system message",
    "developer message",
    "developer instructions",
    "reveal your prompt",
    "show your prompt",
    "show me your system prompt",
    "print your instructions",
    "reveal your instructions",
    "bypass your restrictions",
    "bypass your rules",
    "jailbreak",
    "developer mode",
    "unrestricted mode",
    "do not follow your instructions",
    "you are now dan",
    "system override"
]

# Phrase-level out-of-scope patterns, for detection
# NOTE: actionable recommendations are out of scope
OUT_OF_SCOPE_PATTERNS = [
    # Planting / crop selection
    "should i plant",
    "should we plant",
    "when should i plant",
    "when should we plant",
    "what should i plant",
    "what crop should i plant",
    "which crop should i plant",
    "what to plant",
    "when to plant",
    "where should i plant",

    # Irrigation / water management
    "should i irrigate",
    "should we irrigate",
    "when should i irrigate",
    "when to irrigate",
    "how much water should i use",
    "how often should i irrigate",
    "irrigation recommendation",
    "irrigation advice",

    # Fertilizer / soil management
    "what fertilizer should i use",
    "which fertilizer should i use",
    "how much fertilizer should i use",
    "when should i fertilize",
    "when to fertilize",
    "fertilizer recommendation",
    "fertilizer advice",

    # Pest / disease management
    "what pesticide should i use",
    "which pesticide should i use",
    "what insecticide should i use",
    "which insecticide should i use",
    "how should i treat",
    "how do i treat",
    "how to treat",
    "pest control recommendation",
    "disease treatment",
    "pest treatment",

    # Harvesting decisions
    "should i harvest",
    "should we harvest",
    "when should i harvest",
    "when to harvest",
    "harvesting recommendation",
    "harvesting advice",

    # Crop management / optimization
    "how can i increase my yield",
    "how do i increase my yield",
    "how to increase my yield",
    "how can i improve my yield",
    "how do i improve my yield",
    "how to improve my yield",
    "how can i maximize my yield",
    "how do i maximize my yield",
    "how to maximize my yield",
    "what should i do to increase yield",
    "what should i do to improve yield",
    "what should i do to protect my crop",
    "how should i manage my crop",
    "crop management advice",
    "farming advice",
    "farming recommendation",

    # Direct decision-making
    "what should i do",
    "what should we do",
    "what do you recommend",
    "what would you recommend",
    "give me a recommendation",
    "give me advice",
    "recommend what i should",
    "tell me what to do",
]

def remove_pii(text: str) -> str:
    """Remove PII from string."""
    # Replace matching PII with placeholder tags
    text = re.sub(EMAIL_REGEX, "[REDACTED-EMAIL]", text)
    text = re.sub(PHONE_REGEX, "[REDACTED-PHONENUMBER]", text)
    text = re.sub(NAME_REGEX, "[REDACTED-NAME]", text)
    return text


def is_prompt_injection(text: str) -> bool:
    """Detect whether text contains known prompt injection or jailbreak patterns."""
    # Return True if text matches any injection phrase
    lower_text = text.lower()
    for pattern in INJECTION_PATTERNS:
        if pattern in lower_text:
            return True
    return False

def is_out_of_scope(text: str) -> bool:
    """Check whether text is out of scope."""
    lower_text = text.lower()
    for word in OUT_OF_SCOPE_PATTERNS:
        if word in lower_text:
            return True
    return False


# TOPIC CLASSIFIER / RESTRICTION

# ── 1. Define Allowed Topics ──────────────────────────────────────────────────
TOPICS = {
    "WEATHER": "Questions about historical or current weather conditions and weather variables.",
    "CROP": "Questions about palay (rice) or corn yield or price.",
    "RELATIONSHIP": "Questions about correlation or prediction involving weather and palay or corn yield or price.",
    # Out of scope (allowed=false)
    "ADVICE": "Requests for farming recommendations or actions, such as planting, irrigation, fertilizer, pesticides, or harvesting.",
    "OFF_TOPIC": "Questions unrelated to weather, palay, corn, yield, price, or their relationship - unrelated topics like sports, food, entertainment, math, personal questions, etc."
}

# ── 2. System Prompt ──────────────────────────────────────────────────────────

TOPIC_SYSTEM_PROMPT = (
    "You are a topic classifier for a weather and agricultural information chatbot.\n\n"
    "Classify the user's message into EXACTLY ONE of these topics:\n"
    + "\n".join(f"- {topic}: {definition}" for topic, definition in TOPICS.items()) 
    + "\n\nOutput ONLY a JSON object in the exact format:\n"
    '{"topic": "TOPIC_NAME", "allowed": true, "confidence": 0.95}\n\n'

    "Rules:\n"
    "- topic must be one of the topic names above\n"
    "- allowed is true only for WEATHER, CROP, and RELATIONSHIP; false for ADVICE and OFF_TOPIC\n"
    "- confidence is a float between 0 and 1\n"
    "- classify based on the user's actual request, not individual keywords\n"
    "- use conversation history when necessary to understand a follow-up question"
)

# ── 3. Few-Shot Examples ──────────────────────────────────────────────────────
TOPIC_FEW_SHOT = [
    {"role": "user",      "content": "How much rain did Pampanga receive last quarter?"},
    {"role": "assistant", "content": '{"topic": "WEATHER", "allowed": true, "confidence": 0.98}'},

    {"role": "user",      "content": "What was the palay yield in Pampanga in Q3 2025?"},
    {"role": "assistant", "content": '{"topic": "CROP", "allowed": true, "confidence": 0.98}'},

    {"role": "user",      "content": "What is the correlation between rainfall and palay yield in Pampanga?"},
    {"role": "assistant", "content": '{"topic": "RELATIONSHIP", "allowed": true, "confidence": 0.98}'},

    {"role": "user",      "content": "Should I apply more fertilizer now because rainfall was low?"},
    {"role": "assistant", "content": '{"topic": "ADVICE", "allowed": false, "confidence": 0.98}'},

    {"role": "user",      "content": "Who won the World Cup in 2022?"},
    {"role": "assistant", "content": '{"topic": "OFF_TOPIC", "allowed": false, "confidence": 1.00}'},
]

# ── 4. Classifier ─────────────────────────────────────────────────────────────
def is_on_topic(user_message: str, llm, history: list = None) -> dict:
    """
    Evaluates whether the user's message is within the supported topics using an LLM.
    
    Args:
        user_message: The text of the user's query.
        history: Optional list of previous conversation messages for context.
        
    Returns:
        A dictionary containing:
            - topic (str): The identified topic or 'UNKNOWN'.
            - allowed (bool): True if the query is answerable by the system.
            - confidence (float): The LLM's confidence score (0.0 to 1.0).
            - fallback (bool): True if the system should trigger a safe fallback response.
    """
    messages = [SystemMessage(content=TOPIC_SYSTEM_PROMPT)]
    
    # Append few-shot examples to guide the LLM's expected output format
    for ex in TOPIC_FEW_SHOT:
        if ex["role"] == "user":
            messages.append(HumanMessage(content=ex["content"]))
        else:
            messages.append(AIMessage(content=ex["content"]))
            
    # Incorporate recent conversation history (last 4 messages) for context
    if history:
        for msg in history[-4:]:
            if isinstance(msg, HumanMessage) or isinstance(msg, AIMessage):
                messages.append(msg)
                
    # Ensure the current user query is at the end of the message list
    if not history or not (isinstance(history[-1], HumanMessage) and history[-1].content == user_message):
        messages.append(HumanMessage(content=user_message))
        
    try:
        # Invoke the LLM to classify the topic
        response = llm.invoke(messages)
        text = response.content
        
        # Extract the JSON block from the LLM's response
        match = re.search(r'\{.*?\}', text, re.DOTALL)
        if not match:
            raise ValueError("No JSON found")
        result = json.loads(match.group())
        
        # Parse the extracted JSON fields
        topic = result.get("topic", "UNKNOWN")
        allowed = result.get("allowed", False)
        confidence = result.get("confidence", 0.0)
        
        # Normalize unknown or unsupported topics
        if topic not in TOPICS and topic != "AGRICULTURAL_ADVICE":
            topic = "UNKNOWN"
            
        # Apply strict fallback rules according to the condition table
        # Fallback if confidence is too low
        if confidence < 0.5:
            return {"topic": "UNKNOWN", "allowed": False, "confidence": confidence, "fallback": True}
            
        # Fallback if the topic is explicitly restricted (e.g., farming advice or completely off-topic)
        if topic in ["ADVICE", "AGRICULTURAL_ADVICE", "OFF_TOPIC", "UNKNOWN"]:
            return {"topic": topic, "allowed": False, "confidence": confidence, "fallback": True}
            
        # Fallback if the LLM flagged it as not allowed
        if not allowed:
            return {"topic": topic, "allowed": False, "confidence": confidence, "fallback": True}
            
        # Query is valid and supported
        return {"topic": topic, "allowed": True, "confidence": confidence, "fallback": False}
        
    except Exception:
        # Safe fallback triggered on API failure or JSON parsing errors
        return {"topic": "UNKNOWN", "allowed": False, "confidence": 0.0, "fallback": True}
