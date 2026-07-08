from langgraph.graph import StateGraph, START, END
from langchain_openai import ChatOpenAI
from backend.app.models.schemas import AgentState, LocationEntity
from backend.app.core.guardrails import detect_prompt_injection, remove_pii, is_weather_related, requests_farming_advice
from backend.app.core.config import settings
from backend.app.services.meteo_service import get_weather_analytics, get_weather_forecast
from backend.app.services.location_search import search_location
from typing import Dict, Any
import json
import re
import datetime

# Initialize LLM
llm = ChatOpenAI(
    model=settings.DEEPSEEK_MODEL,
    api_key=settings.DEEPSEEK_API_KEY,
    base_url=settings.DEEPSEEK_BASE_URL,
    temperature=0
)

# Prompts
INTENT_PROMPT = """Classify the user's intent into ONE of the following categories:
- `analytics`: Wants historical weather data (past dates).
- `forecast`: Wants future weather predictions (future dates).
- `general`: Asking general questions about what you can do.
- `off-topic`: Anything else.

Return ONLY the category name.
User Query: {query}"""

SLOT_PROMPT = """You are a slot extraction assistant for a weather information system in the Philippines.
Today's Date: {today} ({weekday}).

The user's intent is: {intent}

Extract the following information from the weather query:
- location: Try to identify the specific location mentioned.
- start_date: Format as YYYY-MM-DD if present.
- end_date: Format as YYYY-MM-DD if present.
- daily_vars: List of valid daily variables requested (e.g., ["temperature_2m_max", "precipitation_sum"]). If vague, default to ["temperature_2m_max", "temperature_2m_min", "precipitation_sum"].

Date Resolution Rules (for start_date and end_date):
1. Convert all time periods to exact YYYY-MM-DD formats.
2. If the user asks about a specific year (e.g. 'in 2023'), start_date is YYYY-01-01 and end_date is YYYY-12-31.
3. If the user asks about a range of years (e.g. 'from 2021 to 2023'), start_date is 2021-01-01 and end_date is 2023-12-31.
4. If the user asks about a specific month or month range (e.g. 'from Jan to March 2024'), resolve the exact start and end days for those months.
5. Resolve relative dates ('yesterday', 'last month', 'last year') relative to today's date ({today}).
6. If the query is about historical weather, start_date and end_date cannot exceed today's date ({today}). Cap historical dates at yesterday.
7. If no specific dates are mentioned and it is a forecast, default to {today}.

Return a JSON object:
{{
  "location": "location string or empty",
  "start_date": "YYYY-MM-DD or empty",
  "end_date": "YYYY-MM-DD or empty",
  "daily_vars": [],
}}

User Query: {query}
"""

GENERATION_PROMPT = """You are WeatherAI, a reliable localized weather assistant for agricultural workers and farmers who benefit from info of weather.
Translate API data into plain, simple, and accessible language.

RULES & STRICT LIMITATIONS:
1. Be concise. Use simple language. No technical jargon.
2. Put severe weather warnings (typhoons, extreme heat) at the very top.
3. Base answers ONLY on provided data. If data is missing or incomplete, state it clearly. NEVER invent or guess data.
4. YOU ARE A DATA TRANSLATOR, NOT A CONSULTANT. 
- NEVER give farming advice, recommend crops, or tell users when to plant/irrigate.
- Example of acceptable response: "Heavy rainfall (50mm) is expected tomorrow. Please factor this into your operations."

OUTPUT PROTOCOL:
FORMAT D: GENERAL
- Provide a direct, concise answer in 1-3 sentences.

PLAIN LANGUAGE INTERPRETATION (STRICTLY REQUIRED):
Describe measurements in plain words first, followed by the raw number in parentheses.
- Rain: None (0mm) -> Light (1-10mm) -> Moderate (11-30mm) -> Heavy (31-60mm) -> Very Heavy (>60mm)
- Temp: Cool (<20°C) -> Warm (20-29°C) -> Hot (30-35°C) -> Very Hot (>35°C)
- Wind: Calm (0-20km/h) -> Breezy (21-40km/h) -> Windy (41-60km/h) -> Strong (>60km/h)
- Humidity: Low (<50%) -> Comfortable (50-70%) -> High (71-85%) -> Very High (>85%)

Examples:
- "Heavy (45mm)" NOT "45mm"
- "Very Hot (37.2°C)" NOT "37.2°C"

User Query: {query}

Weather Data Context:
{weather_data}
"""

# Nodes
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

def node_classifier(state: AgentState):
    if state.error:
        return state
        
    prompt = INTENT_PROMPT.format(query=state.user_query)
    response = llm.invoke(prompt)
    intent = response.content.strip().lower()
    
    # Ensure it's one of the expected intents
    if intent not in ["analytics", "forecast", "general", "off-topic"]:
        intent = "general"
        
    return {"intent": intent}

def node_slot_extraction(state: AgentState):
    if state.error or state.intent not in ["analytics", "forecast"]:
        return state
        
    today_dt = datetime.datetime.now()
    today_str = today_dt.strftime("%Y-%m-%d")
    weekday_str = today_dt.strftime("%A")
    
    slot_defs = (
        "- location: Try to identify the specific location mentioned.\n"
        "- start_date: Exact start date in YYYY-MM-DD.\n"
        "- end_date: Exact end date in YYYY-MM-DD.\n"
        '- daily_vars: List of valid daily variables requested. If vague, default to ["temperature_2m_max", "temperature_2m_min", "precipitation_sum"].\n\n'
        "Allowed Daily Variables: precipitation_sum, rain_sum, sunshine_duration, temperature_2m_max, temperature_2m_min, temperature_2m_mean, wind_speed_10m_max, et0_fao_evapotranspiration, soil_moisture_0_to_100cm_mean, vapour_pressure_deficit_max, relative_humidity_2m_mean, relative_humidity_2m_max, soil_temperature_0_to_100cm_mean"
    )
        
    prompt = SLOT_PROMPT.format(
        today=today_str,
        weekday=weekday_str,
        intent=state.intent,
        slot_definitions=slot_defs,
        query=state.user_query
    )
    response = llm.invoke(prompt)
    try:
        # Simple extraction of JSON from response
        text = response.content
        md_match = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', text, re.DOTALL)
        if md_match:
            text = md_match.group(1).strip()
        data = json.loads(text)
        print("LLM JSON Result:", json.dumps(data, indent=2))
        
        location_str = data.get("location", "")
        start_date = data.get("start_date", "")
        end_date = data.get("end_date", "")
        daily_vars = data.get("daily_vars", ["temperature_2m_max", "precipitation_sum"])
        
        if not location_str:
            return {"waiting_for_location": True}
            
        # Parse location string to lat/long using location_search
        ref_lines = search_location(location_str)
        if ref_lines:
            first_match = ref_lines[0]
            # parse `[level] name | parent | ... | lat | long`
            parts = [p.strip() for p in first_match.split("|")]
            if len(parts) >= 6:
                lat = parts[-2]
                lon = parts[-1]
                loc_entity = LocationEntity(latitude=lat, longitude=lon, barangay=location_str)
            else:
                lat = "14.5995"
                lon = "120.9842"
                loc_entity = LocationEntity(latitude=lat, longitude=lon, barangay=location_str)
        else:
            # Fallback coordinates if location search fails but location was provided
            loc_entity = LocationEntity(latitude="14.5995", longitude="120.9842", barangay=location_str)
            
        # Temporarily store vars in state (adding them via returned dict, but they need to be on the model)
        # We can pass them through start_date/end_date for simplicity or extend the model
        return {
            "location": loc_entity,
            "start_date": start_date,
            "end_date": end_date,
            "daily_vars": daily_vars, # Will need to add these to State schema if needed, but for now we'll process here
            # Hack for state passage:
            "error": json.dumps({"daily": daily_vars}) if not state.error else state.error
        }
    except Exception as e:
        return {"error": f"Failed to extract parameters: {e}"}

def node_tool_execution(state: AgentState):
    if state.error and not state.error.startswith("{"):
        return state
    if state.waiting_for_location:
        return state
        
    try:
        lat = float(state.location.latitude)
        lon = float(state.location.longitude)
        
        # Extract vars from the hack
        vars_dict = json.loads(state.error) if state.error and state.error.startswith("{") else {"daily": []}
        print(f"\n=== TOOL EXECUTION VARS JSON ===\n{json.dumps(vars_dict, indent=2)}\n================================\n")
        
        daily_vars = vars_dict.get("daily", ["temperature_2m_max", "precipitation_sum"])
        
        if state.intent == "analytics":
            sd = state.start_date or "2023-01-01"
            ed = state.end_date or "2023-01-31"
            md = get_weather_analytics(lat, lon, sd, ed, daily_vars)
            return {"weather_data_markdown": md, "error": None} # clear the hack
        elif state.intent == "forecast":
            md = get_weather_forecast(lat, lon, daily_vars)
            return {"weather_data_markdown": md, "error": None}
    except Exception as e:
        return {"error": f"Tool execution failed: {e}"}
        
    return state

def node_generation(state: AgentState):
    if state.error and not state.error.startswith("{"):
        return {"final_response": state.error}
        
    if state.waiting_for_location:
        return {"final_response": "Please state the specific location for the weather data."}
        
    if state.intent == "off-topic":
        return {"final_response": "I can only answer questions related to weather conditions and forecasts."}
        
    if state.intent == "general" and not state.weather_data_markdown:
        prompt = GENERATION_PROMPT.format(query=state.user_query, weather_data="No data available for general queries.")
    else:
        prompt = GENERATION_PROMPT.format(query=state.user_query, weather_data=state.weather_data_markdown or "")
        
    response = llm.invoke(prompt)
    return {"final_response": response.content}


# Edge routing functions
def router_after_guardrails(state: AgentState):
    if state.error:
        return "generation"
    return "classifier"
    
def router_after_classifier(state: AgentState):
    if state.intent in ["analytics", "forecast"]:
        return "slot_extraction"
    return "generation"
    
def router_after_slots(state: AgentState):
    if state.error and not state.error.startswith("{"):
        return "generation"
    if state.waiting_for_location:
        return "generation"
    return "tool_execution"

# Build Graph
workflow = StateGraph(AgentState)
workflow.add_node("guardrails", node_guardrails)
workflow.add_node("classifier", node_classifier)
workflow.add_node("slot_extraction", node_slot_extraction)
workflow.add_node("tool_execution", node_tool_execution)
workflow.add_node("generation", node_generation)

workflow.add_edge(START, "guardrails")
workflow.add_conditional_edges("guardrails", router_after_guardrails)
workflow.add_conditional_edges("classifier", router_after_classifier)
workflow.add_conditional_edges("slot_extraction", router_after_slots)
workflow.add_edge("tool_execution", "generation")
workflow.add_edge("generation", END)

compiled_graph = workflow.compile()
