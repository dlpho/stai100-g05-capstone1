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
from services.meteo_service import fetch_monthly_weather, DEFAULT_WEATHER_VARS
from services.rag_service import retrieve_rrl_context
from services.correlation_service import correlations_by_province, WEATHER_VAR_MAP, compute_detailed_correlation
from langchain_core.runnables import RunnableConfig
from services.location_resolve import resolve_location_sqlite
from services.predict_service import predict_price, predict_yield, explain_prediction
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
            msg = "I can only answer questions related to historical weather conditions and palay crop yield and price, and their relationships. I cannot answer off-topic queries."
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
        allowed_actions = ["GET_CROP_DATA", "PREDICT_YIELD", "PREDICT_PRICE", "EXPLAIN_PREDICTION","DESCRIBE_CAPABILITIES"]
    elif topic in ["RELATIONSHIP"]:
        allowed_actions = ["ANALYZE_CORRELATION", "PREDICT_YIELD", "PREDICT_PRICE", "EXPLAIN_PREDICTION", "DESCRIBE_CAPABILITIES"]
    elif topic == "GENERAL":
        allowed_actions = ["DESCRIBE_CAPABILITIES"]
    else:
        allowed_actions = ["UNKNOWN"]

    SLOT_SYSTEM_PROMPT = build_slot_system_prompt(topic, allowed_actions, state.user_query, datetime.datetime.now().strftime("%Y-%m-%d"))

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
        "PREDICT_YIELD": {"location", "time_period", "crop_type"},
        "PREDICT_PRICE": {"location", "time_period", "crop_type"},
        "EXPLAIN_PREDICTION": {"location", "time_period", "crop_type"},
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
    elif action == "PREDICT_YIELD":
        required = ["location", "time_period", "crop_type"]
    elif action == "PREDICT_PRICE":
        required = ["location", "time_period", "crop_type"]
    elif action == "EXPLAIN_PREDICTION":
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

    loc_entity, status = resolve_location_sqlite(location_str)

    if status == "UNSUPPORTED_REGION":
        return {"error": "Unsupported location: We currently only support provinces in Region III."}
    elif status == "AMBIGUOUS":
        return {"is_ready_for_tools": False, "missing_slots": ["location"]}

    elif status == "NOT_FOUND":
        return {"error": f"Location '{location_str}' could not be resolved using the current Region III location database. WeatherTato currently supports locations contained in its Region III dataset."}

    return {"location": loc_entity}


# ---------------------------------------------------------------------------
# MODULE: TOOL USE — Geocoding & Weather Tools
# ---------------------------------------------------------------------------

# Removed _resolve_location and location_search dependency

@tool
def get_monthly_weather_tool(start_date: str, end_date: str, daily_vars: list[str] = None, config: RunnableConfig = None) -> str:
    """Gets historical monthly weather analytics data for the user's location.
    Args:
        start_date: Exact start date in YYYY-MM-DD (must be a past date).
        end_date: Exact end date in YYYY-MM-DD (must be a past date).
        daily_vars: List of daily variables to fetch. Allowed values: precipitation_sum, temperature_2m_mean, temperature_2m_max, temperature_2m_min, surface_pressure_mean, soil_moisture_0_to_100cm_mean. Leave empty for default core variables.
    """
    state: AgentState = config.get("configurable", {}).get("state")
    if not state or not state.location:
        return "Error: Location not provided or resolved."

    loc = state.location
    active_action = state.active_action

    if active_action == "GET_WEATHER_DATA":
        lat = loc.latitude
        lon = loc.longitude
    else:
        lat = loc.province_latitude
        lon = loc.province_longitude

    # Validate requested variables against allowed set
    validated_vars = []
    discarded_vars = []
    if daily_vars:
        if "ALL" in daily_vars:
            validated_vars = list(DEFAULT_WEATHER_VARS)
        else:
            for v in daily_vars:
                if v in DEFAULT_WEATHER_VARS:
                    validated_vars.append(v)
                else:
                    discarded_vars.append(v)
    if not validated_vars:
        validated_vars = list(DEFAULT_WEATHER_VARS)

    try:
        df = fetch_monthly_weather(float(lat), float(lon), start_date, end_date, daily_vars=validated_vars)
        if df.empty:
            return json.dumps({"markdown": f"No weather data found for the requested location from {start_date} to {end_date}.", "structured_data": {}})

        # Keep result compact to avoid overwhelming the LLM
        md_output = f"### Monthly Weather Data\n\n"
        if discarded_vars:
            md_output += f"**Warning:** The following requested variables are invalid and were discarded: {', '.join(discarded_vars)}\n\n"
        md_output += df.to_markdown(index=False)
        return md_output
    except Exception as e:
        return f"Error fetching weather data from Open-Meteo: {str(e)}"

@tool
def get_crop_data_tool(location: str, crop_type: str, time_period_value: str, config: RunnableConfig = None) -> str:
    """Gets historical crop production data for a location.
    Args:
        location: The name of the city, municipality, or province.
        crop_type: The type of crop (e.g. PALAY).
        time_period_value: The time period (e.g. 2024, Q3 2025).
    """
    state: AgentState = config.get("configurable", {}).get("state")
    if not state or not state.location:
        return "Error: Location not provided or resolved."

    resolved_prov = state.location.province
    md_output = f"| Metric | Value |\n|---|---|\n| {crop_type} Production in {resolved_prov} ({time_period_value}) | 1500 MT |"
    return md_output


def _parse_correlation_period(value: str) -> tuple[str, str]:
    """Best-effort (start_date, end_date) from a time-period string.

    A bare year (e.g. "2024") narrows the start; anything else falls back to the
    full available history so the correlation has enough monthly points.
    """
    v = (value or "").strip()
    m = re.match(r"^(\d{4})$", v)
    if m:
        y = int(m.group(1))
        return f"{y}-01-01", "2026-07-31"
    return "2012-01-01", "2026-07-31"


@tool
def analyze_correlation_tool(location: str, crop_type: str, weather_variables: List[str], time_period_value: str, config: RunnableConfig = None) -> str:
    """Analyzes the correlation between monthly weather and palay outcomes using a 4-month growing-season lag.
    Args:
        location: The location (province).
        crop_type: The type of crop (e.g. PALAY).
        weather_variables: Variables to correlate (ALL, RAINFALL, MEAN_TEMP, MAX_TEMP, MIN_TEMP, SURFACE_PRESSURE, SOIL_MOISTURE). Pass ["ALL"] to analyze all variables.
        time_period_value: The time period (e.g. "2024"). Uses full history when unspecified.
    """
    state: AgentState = config.get("configurable", {}).get("state")
    if not state or not state.location:
        return "Error: Location not provided or resolved."

    province = state.location.province
    if "ALL" in weather_variables:
        vars_ = list(DEFAULT_WEATHER_VARS)
    else:
        vars_ = [WEATHER_VAR_MAP[v] for v in weather_variables if v in WEATHER_VAR_MAP]
        if not vars_:
            vars_ = list(DEFAULT_WEATHER_VARS)

    start_date, end_date = _parse_correlation_period(time_period_value)

    details = compute_detailed_correlation(
        weather_vars=vars_,
        outcomes=["YIELD", "PRODUCTION", "PRICE"],
        start_date=start_date,
        end_date=end_date,
        province_name=province,
        selected_lag=4
    )

    obs_df = details["observations"]
    if obs_df.empty:
        return f"No correlation data available for {province} ({time_period_value})."

    r = details.get("correlations")
    if r is not None and "province" in r.index.names:
        r = r.droplevel("province")
        
    return (
        f"Correlation for {crop_type} in {province} ({start_date} to {end_date}, 4-month lag):\n"
        + (r.round(3).to_markdown(index=True) if r is not None else "N/A")
    )

@tool
def predict_yield_tool(location: str, target_year: int, target_month: int, config: RunnableConfig = None) -> str:
    """Predicts the palay (rice) yield (MT per Hectare) for a specific location and date.
    Args:
        location: The name of the province.
        target_year: The year for the prediction (e.g., 2024).
        target_month: The month for the prediction as an integer (1-12).
    """
    state: AgentState = config.get("configurable", {}).get("state")
    if not state or not state.location:
        return "Error: Location not provided or resolved."

    resolved_prov = state.location.province

    try:
        result = predict_yield(resolved_prov, target_year, target_month)

        return (f"| Metric | Value |\n"
                f"|---|---|\n"
                f"| Palay Yield Prediction ({resolved_prov}, {target_month}/{target_year}) | {result} MT/ha |")
    except Exception as e:
        return f"Could not generate yield prediction for {resolved_prov} on {target_year}-{target_month:02d}. Error: {e}"

@tool
def predict_price_tool(location: str, target_year: int, target_month: int, config: RunnableConfig = None) -> str:
    """Predicts the palay (rice) retail price (PHP per kg) for a specific location and date.
    Args:
        location: The name of the province.
        target_year: The year for the prediction (e.g., 2024).
        target_month: The month for the prediction as an integer (1-12).
    """
    state: AgentState = config.get("configurable", {}).get("state")
    if not state or not state.location:
        return "Error: Location not provided or resolved."

    resolved_prov = state.location.province

    try:
        result = predict_price(resolved_prov, target_year, target_month)

        return (f"| Metric | Value |\n"
                f"|---|---|\n"
                f"| Palay Price Prediction ({resolved_prov}, {target_month}/{target_year}) | ₱{result}/kg |")
    except Exception as e:
        return f"Could not generate price prediction for {resolved_prov} on {target_year}-{target_month:02d}. Error: {e}"

@tool
def explain_prediction_tool(model_type: str, target_year: int, target_month: int, config: RunnableConfig = None) -> str:
    """Explains the 'why' behind a prediction by calculating exact feature contributions.
    Args:
        model_type: The type of prediction to explain (e.g., 'yield' or 'price').
        target_year: The year for the prediction (e.g., 2024).
        target_month: The month for the prediction as an integer (1-12).
    """
    state: AgentState = config.get("configurable", {}).get("state")
    if not state or not state.location:
        return "Error: Location not provided or resolved."

    resolved_prov = state.location.province

    try:
        data = explain_prediction(model_type, resolved_prov, target_year, target_month)

        return json.dumps({
            "province": data.get("province", resolved_prov),
            "target_period": data.get("target_period", f"{target_year}-{target_month:02d}"),
            "predicted_value": data.get("predicted_value"),
            "baseline_average": data.get("baseline_average"),
            "positive_factors": data.get("factors_pushing_prediction_UP", []),
            "negative_factors": data.get("factors_pushing_prediction_DOWN", [])
        }, indent=2)
    except Exception as e:
        return f"Could not explain the {model_type} prediction for {resolved_prov} on {target_year}-{target_month:02d}. Error: {e}"

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
        get_monthly_weather_tool,
        get_crop_data_tool,
        analyze_correlation_tool,
        predict_yield_tool,
        predict_price_tool,
        explain_prediction_tool
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
        structured_payload = None

        for tool_call in state.tool_calls:
            name = tool_call["name"]
            args = tool_call["args"]
            tool_call_id = tool_call.get("id", "")

            print(f"\n=== EXECUTING TOOL {name} ===\n{json.dumps(args, indent=2)}\n================================\n")

            config = {"configurable": {"state": state}}

            # if name == "get_weather_analytics_tool":
                # md = get_weather_analytics_tool.invoke(args, config)
            if name == "get_monthly_weather_tool":
                md = get_monthly_weather_tool.invoke(args, config)
            elif name == "get_crop_data_tool":
                md = get_crop_data_tool.invoke(args, config)
            elif name == "analyze_correlation_tool":
                md = analyze_correlation_tool.invoke(args, config)
            elif name == "predict_yield_tool":
                md = predict_yield_tool.invoke(args, config)
            elif name == "predict_price_tool":
                md = predict_price_tool.invoke(args, config)
            elif name == "explain_prediction_tool":
                md = explain_prediction_tool.invoke(args, config)
            else:
                md = f"Unknown tool: {name}"

            messages.append(ToolMessage(content=str(md), tool_call_id=tool_call_id))

        return {"messages": messages, "tool_calls": [], "error": None}

    except Exception as e:
        messages = list(state.messages or [])
        for tool_call in state.tool_calls:
            messages.append(ToolMessage(content=f"Error executing tool: {e}", tool_call_id=tool_call.get("id", "")))
        return {"messages": messages, "error": f"Tool execution failed: {e}", "tool_calls": []}

# ---------------------------------------------------------------------------
# MODULE: RAG RETRIEVAL & GENERATION
# ---------------------------------------------------------------------------

def node_rag_retrieval(state: AgentState) -> dict:
    """Node 4.5 — Post-Analysis RAG Literature Retrieval."""
    if state.error:
        return state

    query = ""
    # Deterministic query formulation based on context
    if state.active_action == "ANALYZE_CORRELATION":
        vars_requested = "weather"
        if state.slots and state.slots.get("weather_variables"):
            vars_requested = " and ".join(state.slots["weather_variables"])

        outcome = state.slots.get("outcome_metric", "rice yield").lower()
        query = f"relationship between {vars_requested} and {outcome}"

    elif state.active_action == "PREDICT_YIELD" or state.active_action == "PREDICT_PRICE" or state.active_action == "EXPLAIN_PREDICTION":
        query = "predicting rice yield from weather variables"

    elif "price" in state.user_query.lower() or state.topic == "MARKET":
        query = "rice production and rice price supply shocks"

    else:
        query = "weather impact on rice yield and production"

    rag_context = retrieve_rrl_context(query)
    return {"rag_context": rag_context}


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

    # Extract tool results directly from messages
    raw_history = list(state.messages or [])
    resolved_tool_call_ids = {msg.tool_call_id for msg in raw_history if isinstance(msg, ToolMessage)}

    # We only care about the latest tool messages for generation context
    tool_results_md = []
    found_tool_turn = False
    for msg in reversed(raw_history):
        if isinstance(msg, ToolMessage):
            tool_results_md.append(msg.content)
            found_tool_turn = True
        elif isinstance(msg, AIMessage) and getattr(msg, "tool_calls", None):
            if found_tool_turn:
                break

    tool_results_md.reverse()
    tool_results_str = "\n\n".join(tool_results_md) if tool_results_md else "No analytical data available."

    rag_context_str = state.rag_context or "No literature context available."

    active_action = state.active_action or "UNKNOWN"
    loc = state.slots.get("location") if state.slots else "Not specified"
    period_dict = state.slots.get("time_period") if state.slots else {}
    period_str = period_dict.get("value", "Not specified") if period_dict else "Not specified"

    system_content = GENERATION_PROMPT.format(
        query=state.user_query,
        active_action=active_action,
        location=loc,
        time_period=period_str,
        tool_results=tool_results_str,
        rag_context=rag_context_str
    )

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
    if not state.is_ready_for_tools:
        return "clarification"
    return "tool_caller"

def router_after_tool_caller(state: AgentState) -> str:
    """Conditional edge router after ``node_tool_caller``."""
    if state.error and not state.error.startswith("{"):
        return "generation"
    if state.tool_calls:
        return "tool_execution"

    # Trigger RAG if action is analytical OR user asks for explanation
    explanation_keywords = ["why", "explain", "how does", "interpretation", "interpret", "reason", "impact"]
    needs_explanation = any(kw in state.user_query.lower() for kw in explanation_keywords)

    if state.active_action in ["ANALYZE_CORRELATION", "EXPLAIN_PREDICTION"] or needs_explanation:
        return "rag_retrieval"

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
workflow.add_node("rag_retrieval", node_rag_retrieval)
workflow.add_node("generation",    node_generation)
workflow.add_node("memory_update", node_memory_update)

workflow.add_edge(START, "guardrails")
workflow.add_conditional_edges("guardrails",    router_after_guardrails)
workflow.add_conditional_edges("task_extraction", router_after_task_extraction)
workflow.add_conditional_edges("location_resolution", router_after_location_resolution)
workflow.add_edge("clarification", "memory_update")
workflow.add_conditional_edges("tool_caller",   router_after_tool_caller)
workflow.add_edge("tool_execution", "tool_caller")  # ReAct loop back

workflow.add_edge("rag_retrieval", "generation")
workflow.add_edge("generation", "memory_update")
workflow.add_edge("memory_update", END)

memory = MemorySaver()
compiled_graph = workflow.compile(checkpointer=memory)
