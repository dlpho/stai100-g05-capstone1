from langgraph.graph import StateGraph, START, END
from langchain_openai import ChatOpenAI
from langchain_core.tools import tool
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage, SystemMessage
from app.models.schemas import AgentState, LocationEntity
from app.core.guardrails import detect_prompt_injection, remove_pii, requests_farming_advice
from app.services.meteo_service import get_weather_analytics, get_weather_forecast
from app.services.location_search import search_location
import json
import re
import datetime

from app.core.env import (
    DEEPSEEK_API_KEY,
    DEEPSEEK_MODEL,
    DEEPSEEK_BASE_URL,
)

# Initialize LLM
llm = ChatOpenAI(
    model=DEEPSEEK_MODEL,
    api_key=DEEPSEEK_API_KEY,
    base_url=DEEPSEEK_BASE_URL,
    temperature=0,
)


# --- MODULE 6: GUARDRAILS ---
def node_guardrails(state: AgentState):
    query = state.user_query
    clean_query = remove_pii(query)
    
    if detect_prompt_injection(clean_query):
        return {"error": "Request blocked due to policy violation.", "user_query": clean_query}
        
    if not is_weather_related(clean_query) and not requests_farming_advice(clean_query):
        # Allow classification to handle non-weather general queries if needed, but the requirements say block
        # Actually, let the classifier route to off-topic
        pass
        
    if requests_farming_advice(clean_query):
        return {"error": "I am a weather assistant and cannot provide farming, planting, or crop management advice.", "user_query": clean_query}
        
    return {"user_query": clean_query}


# --- MODULE 1: PROMPT ENGINEERING (Few-Shot Classifier System Prompt) ---
# --- MODULE 2: STRUCTURED OUTPUTS (Intent Classifier JSON) ---
# Classifier Prompts
# ── 1. Define Categories ─────────────────────────────────────────────────
WEATHER_INTENTS = {
    "analytics": "User wants historical weather data for past dates (e.g., 'What was the weather like in Cebu last year?', 'Give me the temperature on 2025-05-10')",
    "forecast":  "User wants future weather predictions or forecasts (e.g., 'What is the forecast for Manila tomorrow?', 'Will it rain next week?')",
    "general":   "User is asking general questions about what the assistant can do (e.g., 'What can you help me with?', 'How do I use this system?')",
    "off-topic": "Anything unrelated to weather or the assistant (e.g., 'Who won the World Cup?', 'Write a python script')",
}

_intents_str = "\n".join([f"- {k}: {v}" for k, v in WEATHER_INTENTS.items()])

# ── 2. System Prompt ──────────────────────────────────────────────────────
INTENT_SYSTEM_PROMPT = (
    "You are an intent classifier for a weather information assistant.\n\n"
    "Classify the user's message into EXACTLY ONE of these intents:\n"
    f"{_intents_str}\n\n"
    "Respond with ONLY a JSON object in this exact format:\n"
    '{"intent": "INTENT_NAME", "confidence": 0.95, "reasoning": "brief reason"}\n\n'
    "Rules:\n"
    "- intent must be one of the intent names above\n"
    "- confidence is a float between 0 and 1\n"
    "- choose the most likely intent if the message could fit multiple"
)

# ── 3. Few-Shot Examples ──────────────────────────────────────────────────
FEW_SHOT_EXAMPLES = [
    {"role": "user",      "content": "What is the forecast for Manila City tomorrow?"},
    {"role": "assistant", "content": '{"intent": "forecast", "confidence": 0.98, "reasoning": "User explicitly wants a future weather forecast"}'},
    {"role": "user",      "content": "Give me the temperature in Cebu on 2025-05-10."},
    {"role": "assistant", "content": '{"intent": "analytics", "confidence": 0.96, "reasoning": "User is asking for weather data on a specific historical date"}'},
    {"role": "user",      "content": "What can you help me with?"},
    {"role": "assistant", "content": '{"intent": "general", "confidence": 0.97, "reasoning": "User is asking about the assistant\'s capabilities"}'},
    {"role": "user",      "content": "Who won the World Cup in 2022?"},
    {"role": "assistant", "content": '{"intent": "off-topic", "confidence": 0.95, "reasoning": "User asking a general question unrelated to weather"}'},
]

def node_classifier(state: AgentState):
    if state.error:
        return state
        
    # Compile prompt with few-shots
    intent_prompt = INTENT_SYSTEM_PROMPT + "\n\n### Examples:\n"
    for ex in FEW_SHOT_EXAMPLES:
        role = "User" if ex["role"] == "user" else "Assistant"
        intent_prompt += f"{role}: {ex['content']}\n"
    intent_prompt += f"\nUser: {state.user_query}\nAssistant: "
    
    response = llm.invoke(intent_prompt)
    try:
        text = response.content
        md_match = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', text, re.DOTALL)
        if md_match:
            text = md_match.group(1).strip()
        data = json.loads(text)
        intent = data.get("intent", "").lower()
        print("Classifier LLM JSON Result:", json.dumps(data, indent=2))
    except Exception as e:
        print(f"Failed to parse classifier intent JSON: {e}. Fallback to string search.")
        intent = "general"
        text_lower = response.content.lower()
        for key in WEATHER_INTENTS.keys():
            if key in text_lower:
                intent = key
                break
                
    # Ensure it's one of the expected intents
    if intent not in ["analytics", "forecast", "general", "off-topic"]:
        intent = "general"
        
    return {"intent": intent}


# --- MODULE 1: PROMPT ENGINEERING (Tool Caller) ---

def _resolve_location(location_str: str):
    if not location_str:
        return None
    ref_lines = search_location(location_str)
    if ref_lines:
        first_match = ref_lines[0]
        parts = [p.strip() for p in first_match.split("|")]
        if len(parts) >= 6:
            return LocationEntity(latitude=parts[-2], longitude=parts[-1], barangay=location_str)
    return LocationEntity(latitude="14.5995", longitude="120.9842", barangay=location_str)

@tool
def get_weather_analytics_tool(location: str, start_date: str, end_date: str, daily_vars: list[str], granularity: str = "day", inner_aggregation: str = "mean", find_extreme: str = "none") -> str:
    """Gets historical weather analytics data for a location.
    Args:
        location: The name of the city, municipality, or province.
        start_date: Exact start date in YYYY-MM-DD (must be a past date).
        end_date: Exact end date in YYYY-MM-DD (must be a past date).
        daily_vars: List of daily variables. Allowed values: precipitation_sum, rain_sum, sunshine_duration, temperature_2m_max, temperature_2m_min, temperature_2m_mean, wind_speed_10m_max, et0_fao_evapotranspiration, soil_moisture_0_to_100cm_mean, vapour_pressure_deficit_max, relative_humidity_2m_mean, relative_humidity_2m_max, soil_temperature_0_to_100cm_mean. Return [] if none specified.
        granularity: 'day', 'month', or 'year'. Default 'day'.
        inner_aggregation: 'mean', 'max', or 'min'. Default 'mean'.
        find_extreme: 'highest', 'lowest', or 'none'. Default 'none'.
    """
    loc = _resolve_location(location)
    if not loc:
        return "Error: Location not provided."
    if not daily_vars:
        daily_vars = ["temperature_2m_max", "temperature_2m_min", "precipitation_sum", "wind_speed_10m_max"]
    return get_weather_analytics(float(loc.latitude), float(loc.longitude), start_date, end_date, daily_vars, granularity, inner_aggregation, find_extreme)

@tool
def get_weather_forecast_tool(location: str, daily_vars: list[str]) -> str:
    """Gets future weather forecast for a location. 
    Dates are always for the upcoming week from today.
    Args:
        location: The name of the city, municipality, or province.
        daily_vars: List of daily variables. Allowed values: precipitation_sum, rain_sum, sunshine_duration, temperature_2m_max, temperature_2m_min, temperature_2m_mean, wind_speed_10m_max, et0_fao_evapotranspiration, soil_moisture_0_to_100cm_mean, vapour_pressure_deficit_max, relative_humidity_2m_mean, relative_humidity_2m_max, soil_temperature_0_to_100cm_mean. Return [] if none specified.
    """
    loc = _resolve_location(location)
    if not loc:
        return "Error: Location not provided."
    if not daily_vars:
        daily_vars = ["temperature_2m_max", "temperature_2m_min", "precipitation_sum", "wind_speed_10m_max"]
    return get_weather_forecast(float(loc.latitude), float(loc.longitude), daily_vars)

def node_tool_caller(state: AgentState):
    if state.error or state.intent not in ["analytics", "forecast"]:
        return state
        
    import datetime
    import json
    today_dt = datetime.datetime.now()
    today_str = today_dt.strftime("%Y-%m-%d")
    weekday_str = today_dt.strftime("%A")
    
    tools = [get_weather_analytics_tool, get_weather_forecast_tool]
    llm_with_tools = llm.bind_tools(tools)
    
    prompt = (
        f"Today's Date: {today_str} ({weekday_str}).\n"
        f"The user intent is: {state.intent}\n\n"
        "Rules:\n"
        "1. Convert all time periods to exact YYYY-MM-DD formats.\n"
        "2. Resolve relative dates ('yesterday', 'last month') relative to today's date.\n"
        "3. If historical, dates cannot exceed today. Cap them at yesterday.\n"
        "4. If the user did not specify a location, DO NOT call any tool. Return a regular text response asking for the location.\n\n"
        f"User Query: {state.user_query}"
    )
    
    response = llm_with_tools.invoke(prompt)
    if response.tool_calls:
        print("LLM Tool Calls:", json.dumps(response.tool_calls, indent=2))
        return {"tool_calls": response.tool_calls}
    else:
        return {"waiting_for_location": True}

# --- MODULE 8: TOOL USE (Weather API Integrations) ---
def node_tool_execution(state: AgentState):
    if state.error and not state.error.startswith("{"):
        return state
    if state.waiting_for_location:
        return state
        
    if not state.tool_calls:
        return state
        
    import json
    try:
        tool_call = state.tool_calls[0] # Just execute the first one
        name = tool_call["name"]
        args = tool_call["args"]
        
        print(f"""
=== EXECUTING TOOL {name} ===
{json.dumps(args, indent=2)}
================================
""")
        
        md = ""
        if name == "get_weather_analytics_tool":
            md = get_weather_analytics_tool.invoke(args)
        elif name == "get_weather_forecast_tool":
            md = get_weather_forecast_tool.invoke(args)
        
        return {"weather_data_markdown": md, "error": None}
    except Exception as e:
        return {"error": f"Tool execution failed: {e}"}


# Generation Prompts (Final Prompt)
GENERATION_PROMPT = """You are WeatherTato, a reliable weather assistant for agricultural workers and farmers who benefit from info of weather.
Translate API data into plain, simple, and accessible language.
````

FEW_SHOT_EXAMPLES = [
    {"role": "user",      "content": "What is the forecast for Manila City tomorrow?"},
    {"role": "assistant", "content": '{"intent": "forecast", "confidence": 0.98, "reasoning": "User explicitly wants a future weather forecast"}'},
    {"role": "user",      "content": "Give me the temperature in Cebu on 2025-05-10."},
    {"role": "assistant", "content": '{"intent": "analytics", "confidence": 0.96, "reasoning": "User is asking for weather data on a specific historical date"}'},
    {"role": "user",      "content": "What can you help me with?"},
    {"role": "assistant", "content": '{"intent": "general", "confidence": 0.97, "reasoning": "User is asking about the assistant\'s capabilities"}'},
    {"role": "user",      "content": "Who won the World Cup in 2022?"},
    {"role": "assistant", "content": '{"intent": "off-topic", "confidence": 0.95, "reasoning": "User asking a general question unrelated to weather"}'},
]

def node_classifier(state: AgentState):
    if state.error:
        return state

    # Build prompt from system instructions + few-shot examples
    intent_prompt = INTENT_SYSTEM_PROMPT + "\n\n### Examples:\n"
    for ex in FEW_SHOT_EXAMPLES:
        role = "User" if ex["role"] == "user" else "Assistant"
        intent_prompt += f"{role}: {ex['content']}\n"

    # Inject conversation history so follow-up messages are classified in context
    if state.messages:
        intent_prompt += "\n### Conversation History:\n"
        for msg in state.messages:
            if isinstance(msg, SystemMessage):
                continue
            role = "User" if isinstance(msg, HumanMessage) else "Assistant"
            intent_prompt += f"{role}: {msg.content}\n"

    intent_prompt += f"\nUser: {state.user_query}\nAssistant: "

    response = llm.invoke(intent_prompt)
    try:
        text = response.content
        md_match = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', text, re.DOTALL)
        if md_match:
            text = md_match.group(1).strip()
        data = json.loads(text)
        intent = data.get("intent", "").lower()
        print("Classifier LLM JSON Result:", json.dumps(data, indent=2))
    except Exception as e:
        print(f"Failed to parse classifier intent JSON: {e}. Fallback to string search.")
        intent = "general"
        text_lower = response.content.lower()
        for key in WEATHER_INTENTS.keys():
            if key in text_lower:
                intent = key
                break

    if intent not in ["analytics", "forecast", "general", "off-topic"]:
        intent = "general"

    return {"intent": intent}


# --- MODULE: TOOL USE — Geocoding & Weather Tools ---

def _resolve_location(location_str: str):
    """Resolve a location string to lat/lon via the offline Philippine CSV geocoder."""
    if not location_str:
        return None
    ref_lines = search_location(location_str)
    if ref_lines:
        parts = [p.strip() for p in ref_lines[0].split("|")]
        if len(parts) >= 4:
            return LocationEntity(latitude=parts[-2], longitude=parts[-1], barangay=location_str)
    # Default to Manila coordinates when location cannot be resolved
    return LocationEntity(latitude="14.5995", longitude="120.9842", barangay=location_str)


@tool
def get_weather_analytics_tool(location: str, start_date: str, end_date: str, daily_vars: list[str], granularity: str = "day", inner_aggregation: str = "mean", find_extreme: str = "none") -> str:
    """Gets historical weather analytics data for a location.
    Args:
        location: The name of the city, municipality, or province.
        start_date: Exact start date in YYYY-MM-DD (must be a past date).
        end_date: Exact end date in YYYY-MM-DD (must be a past date).
        daily_vars: List of daily variables. Allowed values: precipitation_sum, rain_sum, sunshine_duration, temperature_2m_max, temperature_2m_min, temperature_2m_mean, wind_speed_10m_max, et0_fao_evapotranspiration, soil_moisture_0_to_100cm_mean, vapour_pressure_deficit_max, relative_humidity_2m_mean, relative_humidity_2m_max, soil_temperature_0_to_100cm_mean. Return [] if none specified.
        granularity: 'day', 'month', or 'year'. Default 'day'.
        inner_aggregation: 'mean', 'max', or 'min'. Default 'mean'.
        find_extreme: 'highest', 'lowest', or 'none'. Default 'none'.
    """
    loc = _resolve_location(location)
    if not loc:
        return "Error: Location not provided."
    if not daily_vars:
        daily_vars = ["temperature_2m_max", "temperature_2m_min", "precipitation_sum", "wind_speed_10m_max"]
    return get_weather_analytics(float(loc.latitude), float(loc.longitude), start_date, end_date, daily_vars, granularity, inner_aggregation, find_extreme)


@tool
def get_weather_forecast_tool(location: str, daily_vars: list[str]) -> str:
    """Gets future weather forecast for a location.
    Dates are always for the upcoming week from today.
    Args:
        location: The name of the city, municipality, or province.
        daily_vars: List of daily variables. Allowed values: precipitation_sum, rain_sum, sunshine_duration, temperature_2m_max, temperature_2m_min, temperature_2m_mean, wind_speed_10m_max, et0_fao_evapotranspiration, soil_moisture_0_to_100cm_mean, vapour_pressure_deficit_max, relative_humidity_2m_mean, relative_humidity_2m_max, soil_temperature_0_to_100cm_mean. Return [] if none specified.
    """
    loc = _resolve_location(location)
    if not loc:
        return "Error: Location not provided."
    if not daily_vars:
        daily_vars = ["temperature_2m_max", "temperature_2m_min", "precipitation_sum", "wind_speed_10m_max"]
    return get_weather_forecast(float(loc.latitude), float(loc.longitude), daily_vars)


# --- MODULE: REACT LOOP — Tool Caller Node ---

def node_tool_caller(state: AgentState):
    if state.error or state.intent not in ["analytics", "forecast"]:
        return state

    today_dt = datetime.datetime.now()
    today_str = today_dt.strftime("%Y-%m-%d")
    weekday_str = today_dt.strftime("%A")

    tools = [get_weather_analytics_tool, get_weather_forecast_tool]
    llm_with_tools = llm.bind_tools(tools)

    system_instructions = (
        f"Today's Date: {today_str} ({weekday_str}).\n"
        f"The user intent is: {state.intent}\n\n"
        "Rules:\n"
        "1. Convert all time periods to exact YYYY-MM-DD formats.\n"
        "2. Resolve relative dates ('yesterday', 'last month') relative to today's date.\n"
        "3. If historical, dates cannot exceed today. Cap them at yesterday.\n"
        "4. Today is in the year 2026. Therefore, any date in 2024 or 2025 is in the past. You must call get_weather_analytics_tool for these past dates.\n"
        "5. If a query asks for weather on a single specific day in the past, set BOTH start_date and end_date to that same day in YYYY-MM-DD format.\n"
        "6. You must invoke the tools when you have the location and dates. Do not answer directly without calling the tools first.\n"
        "7. If the user did not specify a location, DO NOT call any tool. Ask for the location.\n\n"
        "Example of historical query for a single day:\n"
        "Query: 'What was the temperature in Cebu on 2025-05-10?'\n"
        "Tool Call: get_weather_analytics_tool(location='Cebu', start_date='2025-05-10', end_date='2025-05-10', daily_vars=['temperature_2m_max', 'temperature_2m_min'])\n"
    )

    # Strip stale SystemMessages from history — they must only appear at position 0
    clean_history = [msg for msg in (state.messages or []) if not isinstance(msg, SystemMessage)]

    # Build execution list; avoid duplicating the current query if already at end of history
    messages = [SystemMessage(content=system_instructions)]
    messages.extend(clean_history)
    if not (clean_history and isinstance(clean_history[-1], HumanMessage) and clean_history[-1].content == state.user_query):
        messages.append(HumanMessage(content=state.user_query))

    response = llm_with_tools.invoke(messages)
    messages.append(response)

    if response.tool_calls:
        print("LLM Tool Calls:", json.dumps(response.tool_calls, indent=2))
        return {"messages": messages, "tool_calls": response.tool_calls, "waiting_for_location": False}

    # No tool calls — check whether a location was at least mentioned
    has_location = len(search_location(state.user_query)) > 0
    if not has_location:
        return {"messages": messages, "tool_calls": [], "waiting_for_location": True}
    return {"messages": messages, "tool_calls": [], "waiting_for_location": False, "final_response": response.content}


# --- MODULE: REACT LOOP — Tool Execution Node ---

def node_tool_execution(state: AgentState):
    if state.error and not state.error.startswith("{"):
        return state
    if state.waiting_for_location or not state.tool_calls:
        return state

    try:
        messages = list(state.messages or [])
        md_list = []
        resolved_locs = []

        for tool_call in state.tool_calls:
            name = tool_call["name"]
            args = tool_call["args"]
            tool_call_id = tool_call.get("id", "")

            print(f"\n=== EXECUTING TOOL {name} ===\n{json.dumps(args, indent=2)}\n================================\n")

            if name == "get_weather_analytics_tool":
                md = get_weather_analytics_tool.invoke(args)
            elif name == "get_weather_forecast_tool":
                md = get_weather_forecast_tool.invoke(args)
            else:
                md = f"Unknown tool: {name}"

            messages.append(ToolMessage(content=md, tool_call_id=tool_call_id))
            md_list.append(md)

            loc = _resolve_location(args.get("location", ""))
            if loc:
                resolved_locs.append(loc)

        combined_md = "\n\n".join(md_list)
        final_loc = resolved_locs[0] if resolved_locs else None
        return {"messages": messages, "weather_data_markdown": combined_md, "location": final_loc, "tool_calls": [], "error": None}

    except Exception as e:
        # Reply to all pending tool call IDs with the error to satisfy API message constraints
        messages = list(state.messages or [])
        for tool_call in state.tool_calls:
            messages.append(ToolMessage(content=f"Error executing tool: {e}", tool_call_id=tool_call.get("id", "")))
        return {"messages": messages, "error": f"Tool execution failed: {e}", "tool_calls": []}


# --- MODULE: RAG GENERATION — System Prompt & Generation Node ---

GENERATION_PROMPT = """You are WeatherTato, a concise weather assistant for Filipino farmers and agricultural workers.

STRICT RULES:
1. Keep the ENTIRE response to 4 sentences or fewer (excluding any ALERT).
2. If there is severe weather (very heavy rain >60mm, strong winds >60km/h, extreme heat >35°C), lead with a bold "⚠️ ALERT: [condition]." on its own line.
3. Describe values in plain words FIRST, raw number in parentheses second — e.g. "Heavy (45mm)", "Very Hot (37.2°C)", "Calm (12 km/h)".
   Scales: Rain: None(0) Light(1-10) Moderate(11-30) Heavy(31-60) Very Heavy(>60) mm | Temp: Cool(<20) Warm(20-29) Hot(30-35) Very Hot(>35) °C | Wind: Calm(0-20) Breezy(21-40) Windy(41-60) Strong(>60) km/h | Humidity: Low(<50) Comfortable(50-70) High(71-85) Very High(>85) %
4. Base answers ONLY on the provided data. Never invent or guess values.
5. NEVER give farming advice, crop recommendations, or planting/irrigation guidance.
6. NEVER tell the user you don't have weather data loaded yet.
7. NEVER tell the user that you're an AI language model.
Be natural and focus on answering the user's query in the most helpful way possible.

User Query: {query}

Weather Data Context:
{weather_data}
"""

def node_generation(state: AgentState):
    if state.error and not state.error.startswith("{"):
        return {"final_response": state.error}

    if state.waiting_for_location:
        return {"final_response": "Please state the specific location for the weather data."}

    if state.intent == "off-topic":
        return {"final_response": "I can only answer questions related to weather conditions and forecasts."}

    weather_data = state.weather_data_markdown or "No data available."
    system_content = GENERATION_PROMPT.format(query=state.user_query, weather_data=weather_data)

    # Build a safe history: drop SystemMessages and any AIMessage whose tool_calls
    # have no matching ToolMessage reply (dangling calls crash the API).
    raw_history = list(state.messages or [])
    resolved_tool_call_ids = {msg.tool_call_id for msg in raw_history if isinstance(msg, ToolMessage)}

    safe_history = []
    for msg in raw_history:
        if isinstance(msg, SystemMessage):
            continue
        if isinstance(msg, AIMessage) and getattr(msg, "tool_calls", None):
            pending_ids = {tc["id"] for tc in msg.tool_calls}
            if not pending_ids.issubset(resolved_tool_call_ids):
                continue
        safe_history.append(msg)

    # Append current query only if not already the last message
    if not (safe_history and isinstance(safe_history[-1], HumanMessage) and safe_history[-1].content == state.user_query):
        safe_history.append(HumanMessage(content=state.user_query))

    messages = [SystemMessage(content=system_content)] + safe_history
    response = llm.invoke(messages)
    return {"final_response": response.content}


# --- MODULE: REACT GRAPH — Edge Routers & Compiled Graph ---

def router_after_guardrails(state: AgentState):
    return "generation" if state.error else "classifier"


def router_after_classifier(state: AgentState):
    if state.intent in ["analytics", "forecast"]:
        return "tool_caller"
    return "generation"

def router_after_tool_caller(state: AgentState):
    if state.error and not state.error.startswith("{"):
        return "generation"
    if state.waiting_for_location:
        return "generation"
    if state.tool_calls:
        return "tool_execution"
    return "generation"


# --- MODULE 7: REACT / STATE GRAPH AGENT ---
# Build Graph
workflow = StateGraph(AgentState)
workflow.add_node("guardrails", node_guardrails)
workflow.add_node("classifier", node_classifier)
workflow.add_node("tool_caller", node_tool_caller)

workflow.add_node("tool_execution", node_tool_execution)
workflow.add_node("generation",    node_generation)

workflow.add_edge(START, "guardrails")
workflow.add_conditional_edges("guardrails",    router_after_guardrails)
workflow.add_conditional_edges("classifier",    router_after_classifier)
workflow.add_conditional_edges("tool_caller",   router_after_tool_caller)
workflow.add_edge("tool_execution", "tool_caller")  # ReAct loop back

workflow.add_edge("generation", END)

compiled_graph = workflow.compile()
