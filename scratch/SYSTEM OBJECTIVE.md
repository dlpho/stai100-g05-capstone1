# SYSTEM OBJECTIVE

You are an expert AI Architect. Build **WeatherTato** — a Weather Agentic AI for Filipino Farmers — using the LangGraph framework. The agent retrieves data via the Open-Meteo API, processes it using Pandas, and generates plain-language summaries using DeepSeek (flash). It maintains a session-scoped conversational memory buffer so users can resolve follow-up questions across multiple turns without repeating themselves.

---

# CORE TECHNOLOGIES & REQUIREMENTS

| Layer | Technology |
| :--- | :--- |
| **Framework** | LangGraph (`StateGraph` orchestration, ReAct loop) |
| **Backend** | FastAPI (REST API on Port 7860) |
| **Frontend** | Streamlit (Chat UI on Port 8000; sidebar docs, quick-start prompts, loading indicators) |
| **LLM** | DeepSeek v4 Flash (via LangChain `ChatOpenAI`) |
| **Geocoder** | Offline CSV lookup derived from PSA/NAMRIA shapefiles via GeoPandas |
| **Weather API** | Open-Meteo Forecast & Archive REST APIs with `requests-cache` + `retry-requests` |
| **Observability** | MLflow (auto-traces, latency, token usage, and errors per run) |
| **Validation** | Pydantic (strict schema for `AgentState`, `UserQuery`, and tool outputs) |
| **Python** | 3.12 |

---

# THE PIPELINE FLOW (LANGGRAPH STATE)

```
User Query + History
        │
        ▼
1. Guardrails Node
        │ safe / blocked ──────────────────────────────────────► Generation Node
        ▼ safe
2. Task Classifier Node
        │ general / off-topic ─────────────────────────────────► Generation Node
        ▼ analytics / forecast
3. Tool Caller Node  ◄────────────────────────────────────────────────┐
        │ tool call ready                                              │
        ▼                                                              │
4. Tool Execution Node ───────────────────────── ToolMessage appended─┘
        │ loop complete
        ▼
5. Generation Node
        │
        ▼
   Final Response
```

### Node Descriptions

1. **Guardrails Node**
   - Strips PII (regex-based redaction tags).
   - Detects and blocks prompt injection / system hijacking keywords.
   - Intercepts farming-advice requests (planting, irrigation, crop management) and reroutes to a predefined refusal in Generation.
   - Passes the clean query into `AgentState.user_query`.

2. **Task Classifier Node**
   - Sends a few-shot prompt (with injected conversation history) to the LLM.
   - Returns a structured JSON: `{ intent, confidence, reasoning }`.
   - Maps to one of four intents: `analytics`, `forecast`, `general`, `off-topic`.
   - History context is injected so bare follow-up messages (e.g. just a city name) are correctly classified as slot fills rather than off-topic.

3. **Tool Caller Node** *(ReAct — Think/Act)*
   - Extracts `location`, `date range`, and `daily_vars` from the user query using the LLM with bound tools.
   - Strips stale `SystemMessage`s from history before building each invocation to prevent message-position API violations on loop iterations.
   - **Missing Location Rule:** If no location is found, sets `waiting_for_location = True` and routes to Generation to ask the user.
   - On location present: invokes `get_weather_forecast_tool` or `get_weather_analytics_tool`.
   - Appends `AIMessage(tool_calls)` to `AgentState.messages` and returns `tool_calls` list.

4. **Tool Execution Node** *(ReAct — Observe)*
   - Resolves location string → `(latitude, longitude)` via offline Philippine CSV geocoder (province → municipality → barangay hierarchy with keyword fallback).
   - Calls Open-Meteo Forecast or Archive API.
   - Converts JSON → Pandas DataFrame → Markdown table (deterministic aggregation: sums, peaks, averages).
   - Wraps result in `ToolMessage` and appends to `AgentState.messages`.
   - Returns to Tool Caller to decide if another tool invocation is needed.

5. **Generation Node** *(RAG — Augmented Generation)*
   - Constructs a safe message list: filters dangling unresolved `AIMessage(tool_calls)` and deduplicates `HumanMessage` entries to prevent API rejections.
   - Injects `SystemMessage(GENERATION_PROMPT)` + cleaned history + current `HumanMessage` + Markdown weather data context.
   - LLM generates a plain-language summary (≤ 4 sentences) with `⚠️ ALERT` for severe conditions.
   - **Error wrapping:** any unhandled exception in the graph is caught at the route level and returns a friendly `"Sorry, I couldn't process that at the moment."` with the raw error in a separate `error_detail` field.

---

# CONVERSATIONAL MEMORY

WeatherTato maintains a **session-scoped sliding window buffer** of up to **3 messages** per session:

- Stored exclusively in Streamlit `st.session_state` — never written to disk.
- The frontend transmits the buffer as `history: List[{role, content}]` in every `/api/chat` POST request.
- `routes.py` maps the history to LangChain `HumanMessage` / `AIMessage` instances and seeds `AgentState.messages` before graph invocation.
- All nodes (Classifier, Tool Caller, Generation) consume `state.messages` for multi-turn context.
- After each assistant reply the buffer is trimmed: `st.session_state.messages = st.session_state.messages[-3:]`.
- Session ends when the user closes the tab or restarts via the sidebar button.

---

# TOOL DEFINITIONS

### `get_weather_analytics_tool` (Historical)
- **Endpoint:** `https://archive-api.open-meteo.com/v1/archive`
- **Parameters:** `location` (str), `start_date` (YYYY-MM-DD), `end_date` (YYYY-MM-DD), `daily_vars` (list), `granularity` (`day`/`month`/`year`), `inner_aggregation` (`mean`/`max`/`min`), `find_extreme` (`highest`/`lowest`/`none`)
- **Allowed Variables:** `precipitation_sum`, `rain_sum`, `sunshine_duration`, `temperature_2m_max`, `temperature_2m_min`, `temperature_2m_mean`, `wind_speed_10m_max`, `et0_fao_evapotranspiration`, `soil_moisture_0_to_100cm_mean`, `vapour_pressure_deficit_max`, `relative_humidity_2m_mean`, `relative_humidity_2m_max`, `soil_temperature_0_to_100cm_mean`

### `get_weather_forecast_tool` (Future)
- **Endpoint:** `https://api.open-meteo.com/v1/forecast`
- **Parameters:** `location` (str), `daily_vars` (list) — same variable set as above, always for the upcoming 7-day window from today.

---

# GENERATION SYSTEM PROMPT (CURRENT)

```
You are WeatherTato, a concise weather assistant for Filipino farmers and agricultural workers.

STRICT RULES:
1. Keep the ENTIRE response to 4 sentences or fewer (excluding any ALERT).
2. If there is severe weather (very heavy rain >60mm, strong winds >60km/h, extreme heat >35°C),
   lead with a bold "⚠️ ALERT: [condition]." on its own line.
3. Describe values in plain words FIRST, raw number in parentheses second.
   Scales: Rain: None(0) Light(1-10) Moderate(11-30) Heavy(31-60) Very Heavy(>60) mm
           Temp: Cool(<20) Warm(20-29) Hot(30-35) Very Hot(>35) °C
           Wind: Calm(0-20) Breezy(21-40) Windy(41-60) Strong(>60) km/h
           Humidity: Low(<50) Comfortable(50-70) High(71-85) Very High(>85) %
4. Base answers ONLY on the provided data. Never invent or guess values.
5. NEVER give farming advice, crop recommendations, or planting/irrigation guidance.
6. NEVER tell the user you don't have weather data loaded yet.
7. NEVER tell the user that you're an AI language model.
Be natural and focus on answering the user's query in the most helpful way possible.

User Query: {query}

Weather Data Context:
{weather_data}
```

---

# MLFLOW INTEGRATION

All graph invocations in `routes.py` are wrapped in a top-level `try/except`. Inside, if `ENABLE_MLFLOW=true`, the invocation is additionally wrapped in `mlflow.start_run()`:

```python
try:
    if ENABLE_MLFLOW:
        with mlflow.start_run(run_name="agent_execution"):
            response = compiled_graph.invoke(graph_input)
    else:
        response = compiled_graph.invoke(graph_input)
    return {"response": response.get("final_response"), "error_detail": None}
except Exception as e:
    return {"response": "Sorry, I couldn't process that at the moment.", "error_detail": str(e)}
```

---

# DIRECTORY STRUCTURE

```
stai100-g05-capstone1/
├── backend/
│   └── app/
│       ├── api/routes.py           # /api/chat endpoint, history mapping, error wrapping
│       ├── core/
│       │   ├── env.py              # Environment variable loading
│       │   └── guardrails.py       # PII redaction, injection detection, topic filters
│       ├── services/
│       │   ├── llm_service.py      # LangGraph nodes, tools, GENERATION_PROMPT, compiled_graph
│       │   ├── meteo_service.py    # Open-Meteo API calls, Pandas aggregation, Markdown output
│       │   ├── location_search.py  # Offline CSV geocoder (province → city → barangay)
│       │   └── geopandas_handler.py# Shapefile → centroid CSV preprocessing
│       ├── models/schemas.py       # AgentState, UserQuery, MessageDict, LocationEntity
│       └── main.py                 # FastAPI app, CORS, MLflow init, uvicorn (Port 7860)
├── frontend/
│   └── app.py                      # Streamlit chat UI, session buffer, quick prompts (Port 8000)
├── run.py                          # Process manager: MLflow → FastAPI → Streamlit
├── evaluate.py                     # Automated test suite (golden dataset, MLflow logging)
├── eval_dataset.json               # 19 test cases across 4 disciplines
├── METHODOLOGY.md                  # Testing protocols and benchmark results
├── SYSTEM OBJECTIVE.md             # This file
├── requirements.txt
├── .env.example
└── README.md
```

---

# MODULE OWNERSHIP

| Team Member | Assigned Modules |
| :--- | :--- |
| **Denise Liana Ho** | Memory / Context Buffer, RAG Pipeline, API Endpoint |
| **Simon Anthony Libut** | Prompt Engineering, Guardrails |
| **Jericho Migell Reyes** | Structured Outputs, Tool Use |