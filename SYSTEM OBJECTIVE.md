# SYSTEM OBJECTIVE
You are an expert AI Architect. Build a "Weather Agentic AI for Filipino Farmers" using the LangGraph framework. The agent will retrieve data via the Open-Meteo API, process it using Pandas, and generate plain-language summaries using DeepSeek (flash). 

# CORE TECHNOLOGIES & REQUIREMENTS
- **Framework:** LangGraph (State graph orchestration)
- **Backend:** FastAPI (REST API endpoint on Port 7860)
- **Frontend:** Streamlit (Streaming chat UI on Port 8000, sidebar with example queries, loading indicators)
- **LLM:** DeepSeek (flash)
- **Observability:** MLflow (Log traces, latency, token usage, and errors)
- **Validation:** Pydantic (Strict schema validation for structured outputs)

# THE PIPELINE FLOW (LANGGRAPH STATE)
1. **Input Guardrails:** Scan user query for PII or prompt hijacking. Block if malicious.
2. **Task Classifier (Router):** Classify the intent into one of 4 categories:
   - `analytics` (Historical data)
   - `forecast` (Future data)
   - `general` (Asking what the AI can do)
   - `off-topic` (Block and return graceful exit)
3. **Slot Extraction & Intent Mapping (Disambiguation):** For `analytics` and `forecast`, extract the required parameters (`location`, `start_date`, `end_date`). 
   - **Crucial Rule:** The LLM must map natural language (e.g., "heat and rain") to specific Open-Meteo variables (e.g., `temperature_2m_max`, `precipitation_sum`). If vague, default to a standard set.
   - **Missing Location Rule:** If the user asks a general weather question but does NOT provide a location, the system MUST use LangGraph's state to pause and ask: "Please state the specific location for the weather data."
   - Assume a placeholder function exists that translates a location string into `latitude` and `longitude`.
4. **Tool Execution:** Call the Open-Meteo API based on the extracted slots using `openmeteo_requests`, `requests_cache`, and `retry_requests`.
5. **Data Processing (Markdown Output):** Use `pandas` to aggregate the raw NumPy/JSON API response. You MUST convert the final aggregated Pandas DataFrame to a Markdown string using `.to_markdown()` before passing it as context to the LLM. 
6. **RAG Generation:** Inject the Markdown summary into the system prompt context. 
7. **Streaming Output:** Stream the final DeepSeek generation through the FastAPI endpoint to the Streamlit UI.

# TOOL DEFINITIONS (STRICT SCHEMAS)
You must implement the Open-Meteo tools using `requests_cache.CachedSession` and `retry` for robust API calls. 

1. **`weather_analytics` (Historical):** - **Endpoint:** `https://archive-api.open-meteo.com/v1/archive`
   - **Parameters:** `latitude`, `longitude`, `start_date`, `end_date`, `daily` (list of variables), `hourly` (list of variables).
   - **Allowed Daily Variables:** `precipitation_sum`, `rain_sum`, `sunshine_duration`, `temperature_2m_max`, `temperature_2m_min`, `temperature_2m_mean`, `wind_speed_10m_max`, `et0_fao_evapotranspiration`, `soil_moisture_0_to_100cm_mean`, `vapour_pressure_deficit_max`, `relative_humidity_2m_mean`, `relative_humidity_2m_max`, `soil_temperature_0_to_100cm_mean`.
   - **Allowed Hourly Variables:** `wind_speed_10m`, `wind_direction_10m`, `wind_gusts_10m`.
   - **Logic:** The Python backend converts the data to Pandas dataframes, calculates macro behaviors (peaks/averages), and outputs a Markdown string.

2. **`weather_forecast` (Future):** - **Endpoint:** `https://api.open-meteo.com/v1/forecast`
   - **Parameters:** Same parameters and mapping logic as above, but for future dates.

# PROMPT ENGINEERING & CONSTRAINTS
- **Persona:** You are an objective weather AI. 
- **Strict Limitation:** You exist ONLY to inform the farmer of data. You must NEVER tell them what to do, what to plant, or provide agricultural advice.
- Apply few-shot examples and chain-of-thought prompting to ensure reliable tool parameter extraction and variable mapping.

# MLFLOW INTEGRATION REQUIREMENT
When executing the LangGraph compiled state graph in your FastAPI route, you MUST wrap the invocation in an MLflow run to ensure proper tracing. Use this exact pattern:
```python
with mlflow.start_run(run_name="agent_execution"):
    response = compiled_graph.invoke({"user_query": query})
DIRECTORY STRUCTURE TO GENERATE
stai100-g05-capstone1/
├── backend/
│   ├── app/
│   │   ├── api/routes.py

│   │   ├── core/config.py

│   │   ├── services/
│   │   │   ├── llm_service.py

│   │   │   ├── meteo_service.py

│   │   ├── models/schemas.py

│   │   └── main.py

│   ├── requirements.txt

│   └── .env.example
├── frontend/
│   ├── app.py

│   └── requirements.txt

└── README.md

EXECUTION INSTRUCTIONS
Please execute these phases sequentially.

Generate requirements.txt files.

Implement meteo_service.py with caching, timezone handling (tz_convert), and Pandas-to-Markdown conversion.

Implement schemas.py and llm_service.py with the LangGraph state, routing, missing location enforcement, and intent mapping. (Map API variables by name string, not static array index).

Implement routes.py (including the MLflow snippet) and main.py (Port 7860).

Implement frontend/app.py (Port 8000).

Write README.md similar to the following:

====
# 🌦️ WeatherAI: Philippine Weather AI Assistant

WeatherAI is a localized conversational weather assistant tailored for farmers, agricultural workers, dispatchers, and delivery riders in the Philippines. It operates under strict guardrail safety guidelines to translate weather data into objective facts without providing operational agricultural advice.

---

## 🛠️ Installation & Setup

1. **Clone the Repository**:
   ```bash
   git clone <repo_url>
   cd stai100-g05-capstone1
   ```

2. **Configure Environment Variables**:
   Create a `.env` file in the root directory (based on `.env.example`):
   ```ini
   DEEPSEEK_API_KEY=your-api-key
   DEEPSEEK_MODEL=deepseek-v4-flash
   DEEPSEEK_BASE_URL=https://api.deepseek.com
   ```

3. **Install Dependencies**:
   Ensure you have virtualenv activated, then run:
   ```bash
   pip install -r requirements.txt
   ```

4. **Run Both Backend & Frontend (Quick Start)**:
   Launch both services sequentially with automatic health monitoring and cleanup using:
   ```bash
   python run.py
   ```
   *This starts the backend in the background, waits for it to become healthy, launches the frontend in your terminal, and automatically terminates the backend process when you Ctrl+C to exit.*

5. **Manual Startup (Optional)**:
   Alternatively, start manually in separate terminal windows:
   * **FastAPI Backend (Port 7860):**
     ```bash
     python app/main.py
     ```
    * **Streamlit Frontend (Port 8000):**
      ```bash
      streamlit run ui/chat_app.py --server.port 8000
      ```

---

## 🏛️ Architecture Overview


### Module Specifications

---

## 📋 Module Ownership

| Team Member | Assigned Modules |
| :--- | :--- |
| **Denise Liana Ho**  | RAG, API Endpoint  |
| **Simon Anthony Libut** | Prompt Engineering, Guardrails  |
| **Jericho Migell Reyes** | Structured Outputs, Tool Use |


====


System prompt for the actual LLM should be something like this

You are WeatherAI, a reliable localized weather assistant for agricultural workers and farmers who benefit from info of weather
  Translate API data into plain, simple, and accessible language.

  RULES & STRICT LIMITATIONS:
    1. Be concise. Use simple language. No technical jargon.
    2. Put severe weather warnings (typhoons, extreme heat) at the very top.
    3. Base answers ONLY on provided data. If data is missing or incomplete, state it clearly. NEVER invent or guess data.
    4. YOU ARE A DATA TRANSLATOR, NOT A CONSULTANT. 
    - NEVER give farming advice, recommend crops, or tell users when to plant/irrigate.
    - Example of acceptable response: "Heavy rainfall (50mm) is expected tomorrow. Please factor this into your operations."


OUTPUT PROTOCOL:

Format A?
Format B ?
Format C - ?
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