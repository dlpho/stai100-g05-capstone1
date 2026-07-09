# II. Methodology

This section outlines the technical implementation, system architecture, data models, and configurations of the **WeatherTato** system. WeatherTato is a conversational assistant designed to bridge advanced weather telemetry and localized agricultural decision-making for Filipino farmers.

---

## 1. System Architecture & Diagram

WeatherTato uses a LangGraph-orchestrated ReAct (Reasoning and Action) state agent model with built-in guardrails, structured slot extraction, external API integrations, and robust MLflow autologging.

Here is the data flow and system integration flowchart:

```mermaid
graph TD
    %% Define Styles
    classDef client fill:#e0f2fe,stroke:#0369a1,stroke-width:2px;
    classDef server fill:#f3e8ff,stroke:#6b21a8,stroke-width:2px;
    classDef agent fill:#f0fdf4,stroke:#166534,stroke-width:2px;
    classDef database fill:#fef3c7,stroke:#92400e,stroke-width:2px;
    classDef ops fill:#ffedd5,stroke:#c2410c,stroke-width:2px;

    %% Elements
    User([User])
    UI["Streamlit Frontend (Port 8000)"]:::client
    API["FastAPI Backend (Port 7860)"]:::server
    
    subgraph LangGraph ["LangGraph Agent Orchestrator"]
        Guard["Guardrails Node"]:::agent
        Class["Classifier Node"]:::agent
        Slots["Tool Caller Node"]:::agent
        Exec["Tool Execution Node"]:::agent
        Gen["Generation Node"]:::agent
    end

    CSV[("Location DB (CSV)")]:::database
    Meteo["Open-Meteo API"]:::database
    MLflow["MLflow UI (Port 5000)"]:::ops

    %% Connections
    User -->|Queries & Views| UI
    UI -->|POST /api/chat| API
    API -->|Invokes Graph| Guard
    
    %% Graph Flow
    Guard -->|Valid Input| Class
    Guard -->|Invalid Input (Off-topic/Farming Advice)| Gen
    
    Class -->|Off-topic/General| Gen
    Class -->|Analytics/Forecast| Slots
    
    Slots -->|Queries Coordinates| CSV
    Slots -->|Location Missing| Gen
    Slots -->|Parameters Extracted| Exec
    
    Exec -->|Fetch Weather| Meteo
    Exec -->|Weather Data| Gen
    
    Gen -->|Final Response| API
    API -->|JSON Response| UI
    
    %% Observability
    LangGraph -.->|Autologs Traces, Latency & Tokens| MLflow
```

---

## 2. Technical Stack

The core technologies driving the application consist of:
* **Frontend:** Streamlit for a fast, responsive, and responsive chat UI with quick-action cards.
* **Backend:** FastAPI for asynchronous REST endpoint services.
* **Agentic Graph Orchestration:** LangGraph (StateGraph) for managing multi-node deterministic agent state routing.
* **Large Language Model Interface:** LangChain (ChatOpenAI wrapper) connected to the **DeepSeek API** (`deepseek-v4-flash` / `deepseek-chat`).
* **External Weather Telemetry:** Open-Meteo APIs (Forecast & Archive) utilizing `requests-cache` to throttle external network overhead.
* **Local Location Resolution:** Geocoding resolved against a localized database of Philippine municipal/barangay/provincial coordinates in CSV format.
* **LLMOps & Tracing:** MLflow tracking server for logging LLM token count, tracing agent latency, and debug logs (pre-configured, disabled by default in development environment).

---

## 3. Data Flow & Execution Model

The execution of a single user chat message follows these logical steps:
1. **User Input:** Streamlit captures the user query and POSTs a JSON payload `{"user_query": "..."}` to the FastAPI `/api/chat` route.
2. **State Initialization:** The FastAPI route creates an `AgentState` object and starts the LangGraph compiler.
3. **Node 1: Guardrails:**
   * Checks for prompt injections using regex.
   * Blocks non-weather questions.
   * **Strict Constraint:** Rejects requests for direct agricultural advice (e.g., "when to plant"), returning a canned disclaimer statement to prevent hallucinated advice.
4. **Node 2: Classifier:**
   * Classifies query intent into `forecast`, `analytics`, `general`, or `off-topic` using a few-shot system prompt.
5. **Node 3: Tool Caller (Slot Extraction):**
   * Prepares context (today's date, day of the week).
   * Binds tools (`get_weather_analytics_tool` and `get_weather_forecast_tool`) to the LLM.
   * If a location is missing, sets `waiting_for_location = True` and exits to Generation.
   * Generates a tool call arguments payload (`location`, `start_date`, `end_date`, variables).
6. **Node 4: Tool Execution:**
   * Resolves the string location to exact latitude and longitude by querying the local geocoding coordinate database (CSV).
   * Executes the corresponding Open-Meteo API wrapper.
   * Aggregates the returned raw JSON payload into structured markdown tables and statistical summaries.
7. **Node 5: Generation:**
   * Formulates a natural language response using a system prompt that mandates translating raw numbers into plain-language categories (e.g., `Rain: Light (3mm)`, `Wind: Breezy (24 km/h)`).
8. **Logging:** Autologs traces and telemetry to the local MLflow server on port `5000` (pre-configured, commented out/disabled by default).

---

## 4. Parameter Telemetry & Agricultural Relevance

WeatherTato tracks specific variables crucial for farming operations, divided into forecast and historical regimes.

### A. Weather Forecast Parameters (Next 14 Days)
The forecast system query pulls 14-day future projections from Open-Meteo for the following variables:

| Parameter | API Variable Name | Agricultural Relevance / Decisions |
| :--- | :--- | :--- |
| **Max Temperature** | `temperature_2m_max` | Heat stress threshold checks; planning harvesting and drying. |
| **Min Temperature** | `temperature_2m_min` | Frost checks (in highlands); germination rates. |
| **Rain Sum** | `rain_sum` | General crop watering requirements. |
| **Showers Sum** | `showers_sum` | Tracking localized sudden/convective rain events. |
| **Precipitation Sum** | `precipitation_sum` | Total water volume input; planning irrigation schedules. |
| **Max Wind Speed** | `wind_speed_10m_max` | Determining if pesticide/fertilizer spraying is safe. |
| **Max Relative Humidity**| `relative_humidity_2m_max` | Humidity peaks that favor mold, mildew, or fungal outbreaks. |

### B. Historical Data Parameters & Trends
For historical analytics, farmers can query weather trends over a month or several years. The system computes exact statistical metrics (means, sums, and isolates highest/lowest extremes) over these time buckets for the following variables:

| Parameter | API Variable Name | Agricultural Relevance / Decisions |
| :--- | :--- | :--- |
| **Precipitation Sum** | `precipitation_sum` | Summing seasonal water inputs to check for drought/flood patterns. |
| **Rain Sum** | `rain_sum` | General rainfall historical mapping. |
| **Sunshine Duration** | `sunshine_duration` | Calculating solar radiation for photosynthetic growth rates. |
| **Max Temperature** | `temperature_2m_max` | Historical heat waves and soil bake factors. |
| **Min Temperature** | `temperature_2m_min` | Cold front mapping and minimum metabolic crop thresholds. |
| **Mean Temperature** | `temperature_2m_mean` | Long-term thermal units (Growing Degree Days - GDD). |
| **Max Wind Speed** | `wind_speed_10m_max` | Assessing historical risk for lodging (crops falling over). |
| **Evapotranspiration** | `et0_fao_evapotranspiration` | Total crop water loss (FAO standard), crucial for water budgets. |
| **Mean Soil Moisture** | `soil_moisture_0_to_100cm_mean` | Volumetric water content at root depth (0-100cm) for hydration. |
| **Max Vapour Pressure Deficit**| `vapour_pressure_deficit_max` | Transpiration stress tracking; high VPD causes stomatal closure. |
| **Mean Relative Humidity**| `relative_humidity_2m_mean` | Average humidity patterns indicating crop comfort levels. |
| **Max Relative Humidity** | `relative_humidity_2m_max` | Peaks for crop disease risk mapping. |
| **Mean Soil Temperature** | `soil_temperature_0_to_100cm_mean`| Heat levels at root zones affecting nutrient uptake and root growth. |

---

## 5. Component Breakdown

The program files map to specific architectural modules:

| Component / Module | File Path | Description |
| :--- | :--- | :--- |
| **Orchestrator script** | [run.py](file:///c:/Users/Liana%20Ho/Documents/school/stai100-g05-capstone1/run.py) | Bootstraps MLflow, FastAPI, and Streamlit sequentially in a managed loop. |
| **User Interface** | [app.py](file:///c:/Users/Liana%20Ho/Documents/school/stai100-g05-capstone1/frontend/app.py) | Streamlit chat UI for interactive conversations. |
| **FastAPI Routes** | [routes.py](file:///c:/Users/Liana%20Ho/Documents/school/stai100-g05-capstone1/backend/app/api/routes.py) | Exposes `/api/chat` route with MLflow custom trace wraps. |
| **Application Server** | [main.py](file:///c:/Users/Liana%20Ho/Documents/school/stai100-g05-capstone1/backend/app/main.py) | Main backend server config with CORS and MLflow autolog initialization. |
| **Pydantic Schemas** | [schemas.py](file:///c:/Users/Liana%20Ho/Documents/school/stai100-g05-capstone1/backend/app/models/schemas.py) | Holds structured `UserQuery`, `AgentState`, and `LocationEntity` objects. |
| **LangGraph Core** | [llm_service.py](file:///c:/Users/Liana%20Ho/Documents/school/stai100-g05-capstone1/backend/app/services/llm_service.py) | Sets up graph nodes (Guardrails, Classifier, Tool Caller, Generation). |
| **Weather Fetcher** | [meteo_service.py](file:///c:/Users/Liana%20Ho/Documents/school/stai100-g05-capstone1/backend/app/services/meteo_service.py) | Makes requests to Open-Meteo and does client-side Pandas aggregations. |
| **Local Geocoder** | [location_search.py](file:///c:/Users/Liana%20Ho/Documents/school/stai100-g05-capstone1/backend/app/services/location_search.py)| Filters Philippine coordinates files locally based on query locations. |
| **Geospatial Preprocessing** | [geopandas_handler.py](file:///c:/Users/Liana%20Ho/Documents/school/stai100-g05-capstone1/backend/app/services/geopandas_handler.py) | Projects administrative shapefiles, calculates centroids, and generates coordinates CSVs. |
| **System Rules / Prompts** | `llm_service.py` | Contains few-shot examples, categorization formats, and plain language mappings. |

---

## 6. Preprocessing & Retrieval-Augmented Generation (RAG)

To support localized weather queries at high spatial granularity without relying on expensive online geocoding APIs or remote spatial vector stores, WeatherTato implements an offline geospatial data preprocessing pipeline coupled with structured tabular Markdown context injection.

### A. Coordinates Preprocessing Pipeline
The coordinates database is preprocessed offline from PSA/NAMRIA administrative shapefiles of the Philippines using [geopandas_handler.py](file:///c:/Users/Liana%20Ho/Documents/school/stai100-g05-capstone1/backend/app/services/geopandas_handler.py):
1. **Load Shapefiles**: The script loads official Shapefiles (`.shp`) for three levels of Philippine administration:
   - **Provinces & Districts** (ADM2)
   - **Municipalities & Cities** (ADM3)
   - **Barangays** (ADM4)
2. **Project Geometries**: To calculate accurate geometric centroids, the geographic coordinates are projected into the UTM Zone 51N projection (`EPSG:32651`), which is the standard spatial reference system for the Philippines.
3. **Centroid Extraction**: Centroids (geographic center points) are computed using the projected geometries.
4. **Reprojection & Export**: Centroid coordinates are re-projected back to standard Latitude/Longitude (`EPSG:4326` WGS 84) and saved into three CSV files (`philippines_provdists_coordinates_2023.csv`, `philippines_municities_coordinates_2023.csv`, `philippines_barangay_coordinates_2023.csv`) under the `data/` directory.

### B. Hierarchical Keyword Search (Location Retrieval)
When a user provides a query, the system extracts location entities using [location_search.py](file:///c:/Users/Liana%20Ho/Documents/school/stai100-g05-capstone1/backend/app/services/location_search.py):
1. **Clean Query**: Stopwords, common weather variables, and noisy terms are removed via `_clean_prompt` to isolate potential location names.
2. **Hierarchical Matching**: 
   - First, the query terms are matched against the provinces CSV database.
   - If a province matches, the search traverses downward to filter municipalities within that province.
   - Finally, barangays are matched and filtered under the matched parent municipality.
3. **Fallback**: If no match is found, the system defaults to Manila's coordinates (`14.5995, 120.9842`).

### C. Prevention of LLM Hallucinations (Pandas Summarization)
LLMs struggle with basic statistical arithmetic and aggregating raw numeric lists. To prevent mathematical hallucinations, [meteo_service.py](file:///c:/Users/Liana%20Ho/Documents/school/stai100-g05-capstone1/backend/app/services/meteo_service.py) pre-computes exact mathematical statistics:
- **Historical Analytics**: Performs timezone-aware (Asia/Manila) temporal groupings (daily, monthly, yearly) and executes aggregation math (`mean`, `max`, `min`). It also supports isolating specific extreme epochs (highest or lowest periods for target variables).
- **Forecast Summaries**: For the 14-day forecast, the backend computes exact sums (e.g., total precipitation/rain sum), absolute maximums/minimums (e.g., highest/lowest temperatures), and averages (e.g., mean temperatures or soil temperatures).
- **Tabular Grounding**: These metrics are compiled into Markdown tables using Pandas `.to_markdown()` and injected directly into the generation prompt context as the RAG grounding source.

### D. Observability & MLflow Configuration
The LangGraph agent execution is wrapped within an MLflow run.
- **Pre-configured Tracking**: Auto-logging of LangChain runs tracks token count, node latency, execution trace graphs, and exceptions.
- **Dynamic Configuration & Resilience**: MLflow tracking is controlled via the `ENABLE_MLFLOW` environment variable. If set to `true`, the system initializes MLflow auto-logging and wraps graph execution in a trace context. If the MLflow server is offline, the backend catches the exception and falls back to running the application without MLflow, avoiding runtime failures.
- **Proxmox & Multi-Container Networking**: By configuring `BACKEND_URL` and `MLFLOW_TRACKING_URI` in `.env`, components can be run in separate Proxmox containers (e.g. separating the Streamlit frontend, FastAPI backend, and MLflow tracking server). The `run.py` launcher is intelligent: it only spawns a local MLflow background service if `ENABLE_MLFLOW` is `true` and `MLFLOW_TRACKING_URI` targets localhost, avoiding port conflicts on remote nodes.

---

## 7. Automated Evaluation & Correctness Framework

To transition from manual ad-hoc testing to a rigorous, production-grade verification pipeline, WeatherTato incorporates an automated evaluation framework powered by MLflow. This system validates the chatbot's correctness, safety adherence, routing accuracy, and performance characteristics against a defined **Golden Dataset**.

### A. The 4 Evaluation Disciplines
Correctness is measured across 4 distinct disciplines (with 4 test cases per discipline, totaling 16 cases):

1. **Guardrails & Safety**:
   - **Objective**: Verify that prompt injections are blocked, and that any query requesting crop recommendations, planting times, or agricultural advice is refused.
   - **Measurement**: Ensures that the output triggers a safety refusal disclaimer ("cannot provide") or that the guardrails node flags an error.
2. **Intent Classification**:
   - **Objective**: Verify that queries are correctly routed to forecast, analytics, general instructions, or off-topic categories.
   - **Measurement**: Compares the output intent state of the graph against the ground-truth expected intent.
3. **Slot Extraction & Disambiguation**:
   - **Objective**: Verify coordinates lookup, slot validation (extracting lists of variables, start/end dates), and slot-filling prompts (if location is missing).
   - **Measurement**: Verifies if the agent pauses and asks for a location when none is provided, resolves relative dates, and extracts variables accurately.
4. **Tool Use & Grounded Generation**:
   - **Objective**: Verify that geocoding works correctly down to the barangay level, Open-Meteo fetches the proper metrics, and the LLM translates the tables into plain language based on the categorized criteria (light rain, hot weather, breezy, etc.).
   - **Measurement**: Validates coordinates match, tool nodes execute successfully, and the response is strictly grounded in data tables.

### B. Metrics Logged and Evaluated
During each evaluation run, the [evaluate.py](file:///c:/Users/Liana%20Ho/Documents/school/stai100-g05-capstone1/evaluate.py) script records:

| Metric | Measurement Method | Purpose |
| :--- | :--- | :--- |
| **Accuracy (Correctness)** | Binary intent/refusal match against expected behavior. | Evaluates routing and safety guardrails correctness. |
| **Latency (Seconds)** | High-precision time delta between start of input and generation. | Tracks system speed and isolates slow nodes. |
| **Token Usage** | Auto-logged OpenAI/DeepSeek usage metrics (prompt and completion tokens). | Monitors operational API costs. |
| **Trace Trees** | Visual node-by-node execution graphs inside the MLflow UI. | Acts as the "Proof of Correctness" for the LangGraph routing logic. |

All evaluation runs are saved locally as a CSV report under [evaluation_report.csv](file:///c:/Users/Liana%20Ho/Documents/school/stai100-g05-capstone1/mlflow_data/evaluation_report.csv) and uploaded to MLflow as a consolidated run summary table.
