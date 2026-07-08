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

## 7. Automated Correctness & Performance Evaluation Methodology

To transition from manual testing to a production-grade verification pipeline, WeatherTato incorporates an automated evaluation framework powered by MLflow and local SQLite logging. The system measures two primary vectors: **Correctness (Functional Quality)** and **Performance (System Efficiency)**.

### A. The 4 Correctness Disciplines
Functional verification is conducted across 4 disciplines (comprising 19 test cases in the Golden Dataset):

1. **Guardrails & Safety**:
   - **Objective**: Verify that direct agricultural advice queries (e.g., planting times, fertilizer amounts, crop choice recommendations) are rejected with standard disclaimers, and prompt injections are blocked.
   - **Assertion**: Checks if the response contains canned refusal phrases (e.g., `"cannot provide"`, `"weather assistant"`) or if the safety node throws a policy error.
2. **Intent Classification**:
   - **Objective**: Verify the accuracy of the intent classifier routing (`analytics`, `forecast`, `general`, `off-topic`).
   - **Assertion**: Compares the graph's `intent` state output against the ground-truth intent label.
3. **Location Resolution & Hierarchy**:
   - **Objective**: Verify geocoding coordinate lookup accuracy (provinces, municipalities, and barangays) and location slot-filling.
   - **Assertion**:
     - For specified locations: Coordinates must not fall back to Manila default coordinates (`14.5995`, `120.9842`).
     - For queries missing location: The state variable `waiting_for_location` must evaluate to `True`.
4. **RAG Grounding & Faithfulness**:
   - **Objective**: Verify that weather summaries are strictly grounded in retrieved Open-Meteo context and telemetry statistics are accurately translated.
   - **Assertion**:
     - *Numeric Reference Check*: Compares floats extracted from the retrieved Markdown table against text in the response. If values are zero, it allows qualitative terms (`"no rain"`, `"dry"`, `"none"`).
     - *Interpretation Mappings*: Asserts that appropriate plain-language category keywords (e.g. `Breezy`, `Very Hot`, `Heavy`) appear in the output.

---

### B. Advanced Performance & Stress-Testing Methodology
In addition to correctness, the evaluation framework measures system metrics under specific stress scenarios:

#### 1. Latency vs. User Prompt Length
* **Measurement**: Tracks query response latency (seconds) as input prompt length scales (from short 5-word queries to long 150-word farmer stories describing soil conditions, crop types, and history before asking the weather question).
* **Significance**: Identifies LLM attention overhead and latency scaling characteristics. High prompt-length latency indicates a need for aggressive input trimming or chunking in guardrail filters.

#### 2. Open-Meteo API Cache Efficiency
* **Measurement**: Measures the latency delta between a **Cache Miss** (first external API call, requiring network roundtrips to Open-Meteo) and a **Cache Hit** (subsequent call for the same coordinates and variables cached in the local SQLite requests-cache database).
* **Significance**: Validates that cache latency remains under **5ms** compared to network fetches of **800ms - 1500ms**, protecting the backend from external API rate-limiting and downtime.

#### 3. Concurrent Load & Throughput Stress
* **Measurement**: Simulates concurrent users hitting the FastAPI `/api/chat` route simultaneously (using evaluation worker threads) and records:
  - Average response times.
  - Server transaction throughput (requests/sec).
  - Rate-limit thresholds or thread lock occurrences.
* **Significance**: Assures the FastAPI async routing model behaves correctly under multi-user capstone presentation stress.

#### 4. Token Cost Optimization Tracking
* **Measurement**: Auto-logs input and output token consumption for every run.
* **Significance**: Enables calculation of query costs under different model bindings (e.g. DeepSeek-v4-flash vs. GPT-4), identifying expensive nodes in the LangGraph execution tree.
