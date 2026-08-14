"""
WeatherTato — LangGraph ReAct Agent Orchestration
"""
import datetime
import json
import re
from typing import Dict, Any, Optional, List

from langgraph.graph import StateGraph, START, END
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import MemorySaver
from langchain_core.tools import tool
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage, SystemMessage

from models.schemas import AgentState, LocationEntity, TaskExtraction
from core.guardrails import is_prompt_injection, is_out_of_scope, remove_pii, is_on_topic
from core.prompts import (
    build_slot_system_prompt,
    build_clarification_prompt,
    build_tool_caller_prompt,
    build_memory_summary_prompt,
    GENERATION_PROMPT,
)
from services.meteo_service import get_weather_analytics, get_weather_forecast
from services.location_search import search_location
from core.env import DEEPSEEK_API_KEY, DEEPSEEK_MODEL, DEEPSEEK_BASE_URL

# Initialize LLM
llm = ChatOpenAI(
    model=DEEPSEEK_MODEL,
    api_key=DEEPSEEK_API_KEY,
    base_url=DEEPSEEK_BASE_URL,
    temperature=0,
)

# ---------------------------------------------------------------------------
# GUARDRAILS NODE (MODULE 4)
# - GUARD 1: apply PII redaction via regex patterns
# - GUARD 2: detect prompt injection & out-of-scope queries via phrase matching
# - GUARD 3: topic restriction via LLM + topic description
# * see @core/guardrails.py for more information
# ---------------------------------------------------------------------------
def node_guardrails(state: AgentState) -> dict:
    """Node 1 — Safety guardrails applied to every incoming query."""

    query = state.user_query

    # GUARD 1: redacting PII
    clean_query = remove_pii(query)
    
    # GUARD 2: detecting prompt injection & out-of-scope queries
    if is_prompt_injection(clean_query):
        return {"error": "Sorry, it seems your question may violate the system guidelines. Please rephrase your question.", "user_query": clean_query, "tool_iteration_count": 0}
    if is_out_of_scope(clean_query):
        return {"error": "Sorry, I can provide weather and palay-related information, correlations, and model estimates, but I cannot recommend what actions to take.", "user_query": clean_query, "tool_iteration_count": 0}
        
    # GUARD 3: topic restriction (based on is_on_topic function)
    result = is_on_topic(clean_query, llm, state.messages)
    topic = result.get("topic", "UNKNOWN")
    if result.get("fallback"):
        if topic == "FORECAST":
            msg = "I can only analyze historical weather data and past correlations. I cannot provide future weather forecasts."
        elif topic == "ADVICE":
            msg = "I can provide data analysis, but I cannot give direct farming advice or crop recommendations."
        else:
            msg = "I can only answer questions related to historical weather conditions and palay/corn crop yield and price, and their relationships. I cannot answer off-topic queries."
        return {"error": msg, "user_query": clean_query, "topic": topic, "tool_iteration_count": 0}
    return {"user_query": clean_query, "topic": topic, "tool_iteration_count": 0}


# ---------------------------------------------------------------------------
# TASK + SLOT EXTRACTION NODE (MODULE 2)
# ---------------------------------------------------------------------------

def node_task_extraction(state: AgentState) -> dict:
    """Node 2 — Extracts task and slots from the user query."""
    if state.error:
        return {}

    topic = state.topic
    # Deterministically choose allowed actions based on topic
    if topic == "WEATHER":
        allowed_actions = ["GET_WEATHER_DATA", "DESCRIBE_CAPABILITIES"]
    elif topic in ["CROP", "CROP_OUTCOMES"]:
        allowed_actions = ["GET_CROP_DATA", "PREDICT_OUTCOME", "DESCRIBE_CAPABILITIES"]
    elif topic in ["RELATIONSHIP", "WEATHER_CROP_RELATIONSHIP"]:
        allowed_actions = ["ANALYZE_CORRELATION", "PREDICT_OUTCOME", "DESCRIBE_CAPABILITIES"]
    elif topic == "GENERAL":
        allowed_actions = ["DESCRIBE_CAPABILITIES"]
    else:
        allowed_actions = ["UNKNOWN"]
    
    SLOT_SYSTEM_PROMPT = build_slot_system_prompt(topic, allowed_actions, state.user_query)

    messages = [SystemMessage(content=SLOT_SYSTEM_PROMPT)]
    if state.messages:
        conversational_history = []
        for msg in state.messages:
            if isinstance(msg, HumanMessage):
                conversational_history.append(msg)
            elif isinstance(msg, AIMessage) and msg.content and not getattr(msg, "tool_calls", None):
                conversational_history.append(AIMessage(content=msg.content))
        messages.extend(conversational_history[-4:])
    messages.append(HumanMessage(content=state.user_query))

    try:
        response = llm.invoke(messages)
        text = response.content.strip()
        md_match = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', text, re.DOTALL)
        if md_match:
            text = md_match.group(1).strip()
        # Find the first JSON object in the response
        json_match = re.search(r'\{.*\}', text, re.DOTALL)
        if not json_match:
            raise ValueError("No JSON object found in extraction response")
        data = json.loads(json_match.group())
        
        extraction_result = TaskExtraction(**data)
        confidence = extraction_result.confidence
        print(f"Extraction confidence: {confidence:.2f}")
        
        # Low-confidence fallback — treat as UNKNOWN and request clarification
        if confidence < 0.5:
            return {
                "active_action": "UNKNOWN",
                "slots": dict(state.slots or {}),
                "missing_slots": ["clarification"],
                "is_ready_for_tools": False
            }
        
        # Extract new slots
        if hasattr(extraction_result.slots, "model_dump"):
            new_slots = extraction_result.slots.model_dump(exclude_none=True)
        else:
            new_slots = extraction_result.slots.dict(exclude_none=True)
            
        action = extraction_result.action
    except Exception as e:
        print(f"Extraction failed: {e}")
        return {"error": "Failed to extract required information from your query."}

    # Define which slots to retain based on the active action
    allowed_slots_for_action = {
        "GET_WEATHER_DATA": {"location", "time_period", "weather_variables"},
        "GET_CROP_DATA": {"location", "time_period", "crop_type", "outcome_metric"},
        "ANALYZE_CORRELATION": {"location", "time_period", "weather_variables", "crop_type", "outcome_metric"},
        "PREDICT_OUTCOME": {"location", "time_period", "weather_variables", "crop_type", "outcome_metric"},
    }.get(action, set())

    # Inherit only the slots relevant to the new action
    current_slots = {k: v for k, v in (state.slots or {}).items() if k in allowed_slots_for_action}
    
    if "time_period" in new_slots and "time_period" in allowed_slots_for_action:
        current_slots["time_period"] = new_slots["time_period"]
        
    for k, v in new_slots.items():
        if k in allowed_slots_for_action and k != "time_period" and v is not None:
            if isinstance(v, list) and not v:
                continue # don't overwrite with empty list
            current_slots[k] = v

    missing_slots = []
    if action == "GET_WEATHER_DATA":
        required = ["location", "time_period", "weather_variables"]
    elif action == "GET_CROP_DATA":
        required = ["location", "time_period", "crop_type", "outcome_metric"]
    elif action == "ANALYZE_CORRELATION":
        required = ["location", "time_period", "weather_variables", "crop_type", "outcome_metric"]
    elif action == "PREDICT_OUTCOME":
        required = ["location", "time_period", "crop_type"]
    elif action == "DESCRIBE_CAPABILITIES" or action == "UNKNOWN":
        required = []
    else:
        required = []

    for req in required:
        val = current_slots.get(req)
        if not val:
            missing_slots.append(req)
        elif req == "weather_variables" and isinstance(val, list) and len(val) == 0:
            missing_slots.append(req)
            
    is_ready = len(missing_slots) == 0

    return {
        "active_action": action,
        "slots": current_slots,
        "missing_slots": missing_slots,
        "is_ready_for_tools": is_ready
    }


def node_clarification(state: AgentState) -> dict:
    """Node for clarifying missing slots."""
    if not state.missing_slots:
        return {}
    
    clarification_system = build_clarification_prompt(state.active_action, state.missing_slots)
    messages = [SystemMessage(content=clarification_system)]
    if state.messages and isinstance(state.messages[-1], HumanMessage):
        messages.append(state.messages[-1])
    else:
        messages.append(HumanMessage(content=state.user_query))
        
    response = llm.invoke(messages)
    
    final_messages = list(state.messages or [])
    if not (final_messages and isinstance(final_messages[-1], HumanMessage) and final_messages[-1].content == state.user_query):
        final_messages.append(HumanMessage(content=state.user_query))
    final_messages.append(AIMessage(content=response.content))
    
    return {"final_response": response.content, "messages": final_messages}


def node_location_resolution(state: AgentState) -> dict:
    """Node 2.5 — Lightweight location resolution stub."""
    if state.error or not state.is_ready_for_tools or state.active_action == "DESCRIBE_CAPABILITIES":
        return {}
        
    location_str = state.slots.get("location")
    if not location_str:
        return {}
        
    loc_upper = location_str.upper()
    supported_provinces = ["PAMPANGA", "BULACAN", "NUEVA ECIJA", "TARLAC", "BATAAN", "ZAMBALES", "AURORA"]
    
    is_supported = any(prov in loc_upper for prov in supported_provinces)
    
    if not is_supported:
        return {"error": "Unsupported location: We currently only support provinces in Region III."}
        
    mock_entity = LocationEntity(
        latitude="15.0",
        longitude="120.0", 
        barangay=location_str
    )
    
    return {"location": mock_entity}


# ---------------------------------------------------------------------------
# MODULE: TOOL USE — Geocoding & Weather Tools
# ---------------------------------------------------------------------------

def _resolve_location(location_str: str) -> LocationEntity | None:
    """Resolve a free-text location string to lat/lon via the offline PSGC geocoder."""
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


@tool
def get_crop_data_tool(location: str, crop_type: str, time_period_value: str) -> str:
    """Gets historical crop production data for a location.
    Args:
        location: The name of the city, municipality, or province.
        crop_type: The type of crop (e.g. PALAY or CORN).
        time_period_value: The time period (e.g. 2024, Q3 2025).
    """
    return f"| Metric | Value |\n|---|---|\n| {crop_type} Production in {location} ({time_period_value}) | 1500 MT |"


@tool
def analyze_correlation_tool(location: str, crop_type: str, weather_variables: List[str], time_period_value: str) -> str:
    """Analyzes the correlation between weather variables and crop outcomes.
    Args:
        location: The location.
        crop_type: The type of crop.
        weather_variables: List of weather variables to correlate.
        time_period_value: The time period.
    """
    vars_str = ", ".join(weather_variables)
    return f"Correlation Analysis for {crop_type} in {location} ({time_period_value}):\nStrong positive correlation found with {vars_str}."


@tool
def predict_outcome_tool(location: str, crop_type: str, time_period_value: str, weather_variables: Optional[List[str]] = None) -> str:
    """Predicts crop outcomes. If `weather_variables` is omitted, the model will deterministically use the fixed POC default feature set. Explicitly supplied variables will override the defaults.
    Args:
        location: The location.
        crop_type: The type of crop.
        time_period_value: The time period.
        weather_variables: Optional list of weather variables.
    """
    vars_used = weather_variables if weather_variables else ["precipitation_sum", "temperature_2m_mean"]
    vars_str = ", ".join(vars_used)
    return f"Prediction for {crop_type} in {location} ({time_period_value}):\nBased on {vars_str}, the estimated yield is 4.2 MT/ha."


# ---------------------------------------------------------------------------
# MODULE: REACT LOOP — Tool Caller Node (Reason step)
# ---------------------------------------------------------------------------

def node_tool_caller(state: AgentState) -> dict:
    """Node 3 — ReAct Reason step: LLM decides which tools to call."""
    if state.error or not state.is_ready_for_tools or state.active_action == "DESCRIBE_CAPABILITIES":
        return state

    iteration_count = state.tool_iteration_count + 1
    if iteration_count > 3:
        print("[ReAct] Max iterations reached. Terminating loop cleanly.")
        return {"tool_calls": [], "tool_iteration_count": iteration_count}

    today_dt = datetime.datetime.now()
    today_str = today_dt.strftime("%Y-%m-%d")
    weekday_str = today_dt.strftime("%A")

    tools = [
        get_weather_analytics_tool,
        get_weather_forecast_tool,
        get_crop_data_tool,
        analyze_correlation_tool,
        predict_outcome_tool
    ]
    llm_with_tools = llm.bind_tools(tools)

    system_instructions = build_tool_caller_prompt(today_str, weekday_str, state.active_action)

    clean_history = [msg for msg in (state.messages or []) if not isinstance(msg, SystemMessage)]

    messages = [SystemMessage(content=system_instructions)]
    
    # Context Summary injection
    if state.summary:
        messages.append(SystemMessage(content=f"Previous Context Summary:\n{state.summary}"))
        
    messages.extend(clean_history)
    if not (clean_history and isinstance(clean_history[-1], HumanMessage) and clean_history[-1].content == state.user_query):
        messages.append(HumanMessage(content=state.user_query))

    response = llm_with_tools.invoke(messages)
    messages.append(response)

    if response.tool_calls:
        print("LLM Tool Calls:", json.dumps(response.tool_calls, indent=2))
        return {"messages": messages, "tool_calls": response.tool_calls, "tool_iteration_count": iteration_count}

    return {"messages": messages, "tool_calls": [], "tool_iteration_count": iteration_count}


# ---------------------------------------------------------------------------
# MODULE: REACT LOOP — Tool Execution Node (Act step)
# ---------------------------------------------------------------------------

def node_tool_execution(state: AgentState) -> dict:
    """Node 4 — ReAct Act step: executes tool calls and appends observations."""
    if state.error and not state.error.startswith("{"):
        return state
    if not state.tool_calls:
        return state

    try:
        messages = list(state.messages or [])
        md_list = []

        for tool_call in state.tool_calls:
            name = tool_call["name"]
            args = tool_call["args"]
            tool_call_id = tool_call.get("id", "")

            print(f"\n=== EXECUTING TOOL {name} ===\n{json.dumps(args, indent=2)}\n================================\n")

            if name == "get_weather_analytics_tool":
                md = get_weather_analytics_tool.invoke(args)
            elif name == "get_weather_forecast_tool":
                md = get_weather_forecast_tool.invoke(args)
            elif name == "get_crop_data_tool":
                md = get_crop_data_tool.invoke(args)
            elif name == "analyze_correlation_tool":
                md = analyze_correlation_tool.invoke(args)
            elif name == "predict_outcome_tool":
                md = predict_outcome_tool.invoke(args)
            else:
                md = f"Unknown tool: {name}"

            messages.append(ToolMessage(content=md, tool_call_id=tool_call_id))
            md_list.append(md)

        combined_md = "\n\n".join(md_list)
        return {"messages": messages, "weather_data_markdown": combined_md, "tool_calls": [], "error": None}

    except Exception as e:
        messages = list(state.messages or [])
        for tool_call in state.tool_calls:
            messages.append(ToolMessage(content=f"Error executing tool: {e}", tool_call_id=tool_call.get("id", "")))
        return {"messages": messages, "error": f"Tool execution failed: {e}", "tool_calls": []}




# ---------------------------------------------------------------------------
# MODULE: RAG GENERATION — Generation Node
# ---------------------------------------------------------------------------

def node_generation(state: AgentState) -> dict:
    """Node 5 — Response generation with three distinct output modes."""
    if state.error and not state.error.startswith("{"):
        return {"final_response": state.error}

    if state.waiting_for_location:
        return {"final_response": "Please state the specific location for the weather data."}

    if state.intent == "off-topic":
        return {"final_response": "I can only answer questions related to weather conditions and forecasts."}

    weather_data = state.weather_data_markdown or "No data available."
    system_content = GENERATION_PROMPT.format(query=state.user_query, weather_data=weather_data)

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

    if not (safe_history and isinstance(safe_history[-1], HumanMessage) and safe_history[-1].content == state.user_query):
        safe_history.append(HumanMessage(content=state.user_query))

    messages = [SystemMessage(content=system_content)] 
    
    # Context Summary injection
    if state.summary:
        messages.append(SystemMessage(content=f"Previous Context Summary:\n{state.summary}"))
        
    messages.extend(safe_history)
    response = llm.invoke(messages)
    
    # Append the AI response to the state messages so it is remembered in the sliding window buffer
    final_messages = list(state.messages or [])
    if not (final_messages and isinstance(final_messages[-1], HumanMessage) and final_messages[-1].content == state.user_query):
        final_messages.append(HumanMessage(content=state.user_query))
    final_messages.append(AIMessage(content=response.content))
    
    return {"final_response": response.content, "messages": final_messages}

# ---------------------------------------------------------------------------
# MODULE: MEMORY — Context Summarization & Sliding Window
# ---------------------------------------------------------------------------

def node_memory_update(state: AgentState) -> dict:
    """Node 6 — Updates the sliding window and summarizes older messages."""
    if state.error:
        return state

    messages = list(state.messages or [])
    
    # Keep the recent 10 messages in the sliding window buffer
    # If the buffer has more than 10 messages, summarize the older ones
    if len(messages) > 10:
        older_messages = messages[:-10]
        recent_messages = messages[-10:]
        
        summary_prompt = build_memory_summary_prompt(older_messages, state.summary or "")
        
        response = llm.invoke(summary_prompt)
        new_summary = response.content.strip()
        
        return {"messages": recent_messages, "summary": new_summary}
        
    return {"messages": messages}



# ---------------------------------------------------------------------------
# MODULE: REACT GRAPH — Edge Routers & Compiled Graph
# ---------------------------------------------------------------------------

def router_after_guardrails(state: AgentState) -> str:
    """Conditional edge router after ``node_guardrails``."""
    return "generation" if state.error else "task_extraction"


def router_after_task_extraction(state: AgentState) -> str:
    """Conditional edge router after ``node_task_extraction``."""
    if state.error:
        return "generation"
    if not state.is_ready_for_tools:
        return "clarification"
    if state.active_action == "DESCRIBE_CAPABILITIES":
        return "generation"
    return "location_resolution"


def router_after_location_resolution(state: AgentState) -> str:
    """Conditional edge router after ``node_location_resolution``."""
    if state.error:
        return "generation"
    return "tool_caller"


def router_after_tool_caller(state: AgentState) -> str:
    """Conditional edge router after ``node_tool_caller``."""
    if state.error and not state.error.startswith("{"):
        return "generation"
    if state.tool_calls:
        return "tool_execution"
    return "generation"


# ---------------------------------------------------------------------------
# MODULE 7: REACT / STATE GRAPH AGENT — Graph Assembly
# ---------------------------------------------------------------------------

workflow = StateGraph(AgentState)
workflow.add_node("guardrails",    node_guardrails)
workflow.add_node("task_extraction", node_task_extraction)
workflow.add_node("location_resolution", node_location_resolution)
workflow.add_node("clarification", node_clarification)
workflow.add_node("tool_caller",   node_tool_caller)
workflow.add_node("tool_execution", node_tool_execution)
workflow.add_node("generation",    node_generation)
workflow.add_node("memory_update", node_memory_update)

workflow.add_edge(START, "guardrails")
workflow.add_conditional_edges("guardrails",    router_after_guardrails)
workflow.add_conditional_edges("task_extraction", router_after_task_extraction)
workflow.add_conditional_edges("location_resolution", router_after_location_resolution)
workflow.add_edge("clarification", "memory_update")
workflow.add_conditional_edges("tool_caller",   router_after_tool_caller)
workflow.add_edge("tool_execution", "tool_caller")  # ReAct loop back

workflow.add_edge("generation", "memory_update")
workflow.add_edge("memory_update", END)

memory = MemorySaver()
compiled_graph = workflow.compile(checkpointer=memory)
