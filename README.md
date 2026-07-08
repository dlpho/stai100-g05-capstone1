# 🥔 WeatherTato: The Weather AI Assistant

WeatherTato is a localized conversational weather assistant tailored for farmers and agricultural workers in the Philippines. It operates under strict guardrail safety guidelines to translate weather data into objective facts for farmers to use

---

## 📋 Prerequisites
* **Python**: `3.12` (Mandatory version for dependency compatibility).

---

## 🛠️ Installation & Setup

1. **Clone the Repository**:
   ```bash
   git clone <repo_url>
   cd stai100-g05-capstone1
   ```

2. **Configure Environment Variables**:
   Create a `.env` file in the root directory based on the provided [.env.example](file:///c:/Users/Liana%20Ho/Documents/school/stai100-g05-capstone1/.env.example):
   ```ini
   # DeepSeek API Configuration
   DEEPSEEK_API_KEY=your-api-key
   DEEPSEEK_MODEL=deepseek-v4-flash
   DEEPSEEK_BASE_URL=https://api.deepseek.com

   # Backend Config (FastAPI server binding)
   BACKEND_HOST=0.0.0.0
   BACKEND_PORT=7860

   # Frontend Config (Streamlit connection endpoint)
   # Set this to the backend FastAPI container IP/domain in Proxmox (e.g. http://10.0.0.10:7860)
   BACKEND_URL=http://127.0.0.1:7860

   # MLflow Observability & Tracing (Optional)
   # Set to true to enable logging, or false to completely bypass MLflow
   ENABLE_MLFLOW=false
   # If using a separate container for MLflow in Proxmox, set this to http://<mlflow-container-ip>:5000
   MLFLOW_TRACKING_URI=http://127.0.0.1:5000
   MLFLOW_EXPERIMENT_NAME=WeatherTato
   ```

3. **Install Dependencies**:
   Ensure you have your virtual environment activated, then run:
   ```bash
   pip install -r requirements.txt
   ```

4. **Run Both Backend & Frontend (Quick Start)**:
   Launch both services sequentially with automatic health monitoring and cleanup using:
   ```bash
   python run.py
   ```
   *This starts the MLflow server, waits for it, starts the FastAPI backend, and then starts the Streamlit frontend. Terminating this command automatically shuts down all background processes.*

5. **Manual Startup (Optional)**:
   Alternatively, start manually in separate terminal windows:
   * **FastAPI Backend (Port 7860):**
     ```bash
     python backend/app/main.py
     ```
    * **Streamlit Frontend (Port 8000):**
      ```bash
      streamlit run frontend/app.py --server.port 8000
      ```

6. **Start MLflow Tracking UI**:
   In a separate terminal with the virtual environment activated, run:
   ```bash
   mlflow ui --backend-store-uri sqlite:///mlflow_data/mlflow_traces.db
   ```

---

## 🏛️ System Architecture

### A. High-Level Pipeline Diagram
The diagram below maps out the sequential execution flow across each of the 5 nodes in the LangGraph pipeline:

```mermaid
graph TD
    %% Define Node Styles
    classDef io fill:#f8fafc,stroke:#64748b,stroke-width:2px;
    classDef check fill:#fff1f2,stroke:#f43f5e,stroke-width:2px;
    classDef route fill:#fef9c3,stroke:#eab308,stroke-width:2px;
    classDef service fill:#eff6ff,stroke:#3b82f6,stroke-width:2px;
    classDef gen fill:#f0fdf4,stroke:#22c55e,stroke-width:2px;
    classDef rag fill:#fdf4ff,stroke:#a855f7,stroke-width:2px,stroke-dasharray: 5 5;

    %% Elements
    Input([Farmer Input Query]):::io
    
    subgraph Pipeline ["LangGraph ReAct Pipeline"]
        Node1[" 1. Guardrails Node<br/>Checks safety, injections,<br/>and agricultural disclaimers"]:::check
        
        Node2[" 2. Task Classifier<br/>Routes query intent<br/>(forecast, analytics, chat)"]:::route
        
        Node3[" 3. Tool Caller & Slot Extraction<br/>Extracts parameter slots &<br/>disambiguates coordinates"]:::service
        
        subgraph RAG [" RAG Pipeline"]
            Node4[" 4. Retrieval — Tool Execution<br/>Queries Open-Meteo API &<br/>aggregates data with Pandas"]:::service
            
            Node5[" 5. Generation Node<br/>Grounds response in retrieved<br/>telemetry & produces summary"]:::gen
        end
    end
    
    Output([Formatted Response]):::io

    %% Connections & Conditional Edges
    Input --> Node1
    
    Node1 -->|Safe / Valid| Node2
    Node1 -->|Violation / Disclaimer| Node5
    
    Node2 -->|Forecast / Analytics| Node3
    Node2 -->|General Chat / Off-Topic| Node5
    
    %% ReAct Loop (Reasoning + Acting)
    Node3 -->|Plan: Tool Call / Slots Filled| Node4
    Node4 -->|Act: Append ToolMessage Observation| Node3
    
    Node3 -->|Observe: No More Tool Calls / Location Missing| Node5
    Node5 --> Output
```

### B. Tech Stack
* **Frontend UI**: Streamlit (asynchronous chat interface with quick prompts).
* **Backend Framework**: FastAPI & Uvicorn (REST API endpoint services).
* **Graph Orchestrator**: LangGraph `StateGraph` (multi-node execution and routing).
* **Large Language Model**: DeepSeek-v4-flash / Chat (accessed via LangChain `ChatOpenAI`).
* **Geospatial Resolution**: Local coordinates database matching Philippine provinces, cities/municipalities, and barangay centroids processed offline from PSA/NAMRIA shapefiles using GeoPandas.
* **Weather Service**: Open-Meteo API (Forecast & Archive) utilizing `requests-cache` and `retry-requests`.
* **Observability (LLMOps)**: MLflow (autologs agent runs, node execution latency, token counts, and exceptions).

### C. Component Breakdown
* **`run.py`**: Local dev environment startup manager. Automatically boots MLflow, FastAPI, and Streamlit.
* **`frontend/app.py`**: Chat client user interface. Implements sample query shortcuts, session history rendering, and transmits the full conversation history to the backend on every turn to enable multi-turn memory.
* **`backend/app/main.py`**: FastAPI server configuration and CORS middleware setups.
* **`backend/app/api/routes.py`**: Exposes `/api/chat` router. Accepts the optional `history` payload from the frontend and maps it to LangChain `HumanMessage` / `AIMessage` instances seeded into `AgentState.messages` before graph invocation.
* **`backend/app/services/llm_service.py`**: Orchestration logic defining nodes, routing rules, guardrails, slot-extraction tools, and compiled state-graph compiler. All nodes (classifier, tool caller, generation) consume the `messages` list for full conversational context across turns.
* **`backend/app/services/location_search.py`**: Performs local geocoding checks against provincial, municipal, and barangay coordinate lists. Falls back to a flat keyword search across all municipalities if no province is matched hierarchically.
* **`backend/app/services/geopandas_handler.py`**: Preprocessing script that processes geographic shapefiles, extracts centroid geometry, and exports coordinates to database CSVs.
* **`backend/app/services/meteo_service.py`**: Calls weather services, performs exact Pandas computations (sums, peaks, averages), and outputs tabular Markdown.
* **`backend/app/models/schemas.py`**: Contains Pydantic models for incoming query validations (`UserQuery` with optional `history` list) and the conversational agent state (`AgentState` with `messages` list).

### D. Data Model & Flow
#### The Agent State (`AgentState` Schema)
The system maintains and updates an interactive conversation state across all nodes during a request cycle:
* `user_query` (str): Raw input prompt from the user.
* `intent` (str): Classified task category (`forecast`, `analytics`, `general`, `off-topic`).
* `messages` (list): Full ordered conversation history passed across all nodes as LangChain `HumanMessage`, `AIMessage`, and `ToolMessage` instances. Enables multi-turn memory across the entire execution graph.
* `tool_calls` (list): Extracted variable lists, dates, and matched location entities.
* `waiting_for_location` (bool): Toggled to true if the prompt wants weather details but lacks a location keyword.
* `weather_data_markdown` (str): Tabular Markdown containing weather telemetry and pre-computed stats.
* `error` (str): Safety blocker warnings, exceptions, or error details.
* `final_response` (str): Output string returned to the user interface.

#### The Message Data Flow
1. **User Query + History**: The Streamlit frontend sends the new user prompt alongside the full session chat history to `/api/chat`. The backend maps the history into LangChain message instances and seeds the `AgentState.messages` list before graph execution begins.
2. **Safety Guardrails**: The input enters the `guardrails` node. Prompt injections and queries requesting operational farming advice are blocked here.
3. **Intent Classification**: The `classifier` node routes the query into weather analytics, forecasts, or general chat intents. The full conversation history is injected into the classifier prompt to allow follow-up queries (e.g. answering a location slot request with just a city name) to be correctly classified in context.
4. **Slot Resolution**: The `tool_caller` node binds tool configurations and maps user questions to correct Open-Meteo variables. History messages are sequenced after the system instructions so the LLM can reconstruct incomplete multi-turn queries (e.g. combining a previous location-less question with a follow-up location reply).
5. **API Retrieval & Pre-calculation**: The `tool_execution` node resolves query locations into exact coordinate centroids using the local database, pulls telemetry from Open-Meteo, computes exact statistics using Pandas (e.g. total rain, average temperature) to prevent LLM hallucination, and renders a Markdown table.
6. **Fact-Grounded Generation**: The `generation` node invokes the LLM with the full message history plus the RAG Markdown table, enabling contextual, memory-aware plain-language summaries grounded in retrieved weather telemetry.

---

## 🧪 Automated Evaluation & Testing

WeatherTato implements an automated test suite that runs a **Golden Dataset** ([eval_dataset.json](file:///c:/Users/Liana%20Ho/Documents/school/stai100-g05-capstone1/eval_dataset.json)) of 16 test cases covering 4 key testing disciplines to guarantee chatbot correctness and verify corner cases.

### Running the Test Suite:
1. Ensure your virtual environment is activated and the active `.env` file has `ENABLE_MLFLOW=true`.
2. Run the evaluation script in your terminal:
   ```bash
   python evaluate.py
   ```
3. The script will execute each test query against the compiled LangGraph agent, calculate metrics, and output a terminal summary report.

### Inspecting Results:
* **Local CSV Report**: Stored in [evaluation_report.csv](file:///c:/Users/Liana%20Ho/Documents/school/stai100-g05-capstone1/mlflow_data/evaluation_report.csv) containing columns for case ID, query, expected intent, actual intent, correctness flag, and query latency (seconds).
* **MLflow UI Traces**: Start the MLflow server (`mlflow ui --backend-store-uri sqlite:///mlflow_data/mlflow_traces.db`) and open [http://localhost:5000](http://localhost:5000). Click into the `chatbot_automated_evaluation` run to see:
  - **Trace Trees**: Visual node-by-node execution trace blocks showing outputs and latency for each node inside LangGraph.
  - **Metric Charts**: Latency distributions and intent matching accuracy metrics.
  - **Summary Tables**: A formatted tabular evaluation list stored directly under the run artifacts.

---

## 🔗 Quick Links

- **Frontend (Streamlit):** [http://localhost:8000](http://localhost:8000)
- **Backend API (Swagger UI):** [http://localhost:7860/docs](http://localhost:7860/docs)
- **MLflow UI:** [http://localhost:5000](http://localhost:5000) *(Run `mlflow ui --backend-store-uri sqlite:///mlflow_data/mlflow_traces.db` in your terminal to start the server)*

---

## 📋 Module Ownership

| Team Member | Assigned Modules |
| :--- | :--- |
| **Denise Liana Ho**  | RAG, API Endpoint  |
| **Simon Anthony Libut** | Prompt Engineering, Guardrails  |
| **Jericho Migell Reyes** | Structured Outputs, Tool Use |