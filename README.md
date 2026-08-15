# 🥔 WeatherTato: The Weather AI Assistant

WeatherTato is a localized conversational weather assistant tailored for farmers and agricultural workers in the Philippines. It operates under strict guardrail safety guidelines to translate weather data into objective facts for farmers to use

---

## 📋 Prerequisites
* **Python**: `3.12` (for full dependency compatibility with LangGraph, MLflow, Pydantic v2, etc.)
* **DeepSeek API Key**

---

## 🛠️ Installation & Setup

### 1. Clone the Repository
```bash
git clone <repo_url>
cd stai100-g05-capstone1
```

### 2. Create a Python 3.12 Virtual Environment
This project **requires Python 3.12**. Use the `py` launcher to explicitly target the correct version:

**Windows (PowerShell):**
```powershell
# Create the virtual environment using Python 3.12
py -3.12 -m venv .venv312

# Activate it
.venv312\Scripts\activate
```

**macOS / Linux:**
```bash
python3.12 -m venv .venv312
source .venv312/bin/activate
```

> After activation, your prompt should show `(.venv312)`. Confirm the right Python is active:
> ```bash
> python --version   # Should output: Python 3.12.x
> pip --version      # Should reference .venv312
> ```

### 3. Install Dependencies
With your virtual environment activated:
```bash
pip install -r requirements.txt
```

### 4. Configure Environment Variables
Copy the example file and fill in credentials:
```bash
# Windows
copy .env.example .env

# macOS / Linux
cp .env.example .env
```

Then edit `.env` — the minimum required values are:
```ini
# DeepSeek API Configuration
DEEPSEEK_API_KEY=your-api-key-here
DEEPSEEK_MODEL=deepseek-v4-flash
DEEPSEEK_BASE_URL=https://api.deepseek.com

# Backend Config (FastAPI server binding)
BACKEND_HOST=0.0.0.0
BACKEND_PORT=7860

# Frontend Config (Streamlit connection endpoint)
BACKEND_URL=http://127.0.0.1:7860

# MLflow Observability & Tracing (Optional)
# Set to true to enable logging, or false if not needed
ENABLE_MLFLOW=false
MLFLOW_TRACKING_URI=sqlite:///mlflow_data/mlflow_traces.db
MLFLOW_EXPERIMENT_NAME=WeatherTato
```

### 5. Run Program
 (3 separate terminals, each with `.venv312` activated):

| Terminal | Command | URL |
| :--- | :--- | :--- |
| Backend | `python backend/app/main.py` | http://127.0.0.1:7860/docs |
| Frontend | `streamlit run frontend/app.py` | http://localhost:8000 |
| MLflow UI | `mlflow ui --backend-store-uri sqlite:///mlflow_data/mlflow_traces.db` | http://localhost:5000 |

---

## 🏛️ System Architecture

### A. High-Level Pipeline Diagram
The diagram below maps out the sequential execution flow of the LangGraph pipeline, explicitly detailing the ReAct loop, ML tool integration, and violation routing:

```mermaid
graph TD
    %% Define Node Styles
    classDef io fill:#f8fafc,stroke:#64748b,stroke-width:2px,color:#000;
    classDef check fill:#fff1f2,stroke:#f43f5e,stroke-width:2px,color:#000;
    classDef route fill:#fef9c3,stroke:#eab308,stroke-width:2px,color:#000;
    classDef reason fill:#e0e7ff,stroke:#6366f1,stroke-width:2px,color:#000;
    classDef act fill:#eff6ff,stroke:#3b82f6,stroke-width:2px,color:#000;
    classDef gen fill:#f0fdf4,stroke:#22c55e,stroke-width:2px,color:#000;
    classDef rag fill:#fdf4ff,stroke:#a855f7,stroke-width:2px,stroke-dasharray: 5 5,color:#000;

    %% Elements
    Input([User Query]):::io

    subgraph Pipeline ["LangGraph Multi-Agent Architecture"]
        Guard["🛡️ 1. Guardrails<br/>(PII, Prompt Injections, Scope)"]:::check
        
        Extract["🏷️ 2. Task Extraction<br/>(Action & Slot Parsing)"]:::route
        Clarify["❓ Clarification<br/>(Prompt for missing slots)"]:::route

        subgraph ReAct ["ReAct Loop (Reason & Act)"]
            ToolCaller["🧠 3. Tool Caller (Think/Reason)<br/>Decides which tools to invoke based on slots"]:::reason
            
            subgraph Tools ["Available Tools"]
                WTool["☁️ Weather Tool"]:::act
                CTool["🌾 Crop Tool"]:::act
                CorrTool["📊 Correlation Tool"]:::act
                PredTool["📈 Prediction (Lasso/Ridge)"]:::act
            end
            
            ToolExec["⚙️ 4. Tool Execution (Act)<br/>Runs the requested tool"]:::act
        end

        Gen["✍️ 5. Generation<br/>(Final Response Synthesis)"]:::gen
        RAG["📚 Controlled RAG<br/>(ChromaDB Literature Retrieval)"]:::rag
        Mem["💾 Memory Update<br/>(Sliding Window Summary)"]:::io
    end

    Output([Formatted Response]):::io

    %% Connections
    Input --> Guard

    %% Guardrail Routing
    Guard -->|Allowed| Extract
    Guard -->|Violation / Disclaimer<br/>(Bypasses Tools & RAG)| Gen

    %% Task Extraction Routing
    Extract -->|Missing Slots| Clarify
    Clarify --> Mem
    
    Extract -->|General / Off-topic| Gen
    Extract -->|Action Ready| ToolCaller

    %% ReAct Loop Logic
    ToolCaller -->|Yields Tool_Calls| ToolExec
    ToolExec -->|Weather Data| WTool
    ToolExec -->|Crop Data| CTool
    ToolExec -->|Correlation| CorrTool
    ToolExec -->|Predictions| PredTool
    
    WTool -->|Observation| ToolCaller
    CTool -->|Observation| ToolCaller
    CorrTool -->|Observation| ToolCaller
    PredTool -->|Observation| ToolCaller
    
    ToolCaller -->|No More Tools Required| Gen
    
    %% RAG & Gen
    Gen -.->|Fetches Context| RAG
    Gen --> Mem
    Mem --> Output
```

### B. Tech Stack
* **Frontend UI**: Streamlit (asynchronous chat interface with quick prompts).
* **Backend Framework**: FastAPI & Uvicorn (REST API endpoint services).
* **Graph Orchestrator**: LangGraph `StateGraph` (multi-node execution and routing).
* **Large Language Model**: DeepSeek Chat (`deepseek-v4-flash`) accessed via LangChain `ChatOpenAI` wrapper pointed at `https://api.deepseek.com`.
* **Geospatial Resolution**: Local coordinates database matching Philippine provinces, cities/municipalities, and barangay centroids processed offline from PSA/NAMRIA shapefiles using GeoPandas.
* **Weather Service**: Open-Meteo API (Forecast & Archive) utilizing `requests-cache` and `retry-requests`.
* **Machine Learning**: Scikit-Learn pipelines utilizing Ridge and Lasso regression to predict agricultural outcomes.
* **RAG System**: ChromaDB vector store paired with Qwen3-Embedding-0.6B to provide literature-grounded answers.
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
* **`backend/app/services/rag_service.py`**: Initializes and manages the local ChromaDB vector store for agricultural literature context retrieval.
* **`backend/app/services/train_model.py` / `train_model_ridge.py`**: Scripts to train and serialize Lasso and Ridge regression models for predictive crop analytics.
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
2. **Safety Guardrails**: The input enters the `guardrails` node. Prompt injections and queries requesting operational farming advice are blocked here. If a violation is detected, the query routes directly to the Generation node to output a refusal/disclaimer, completely bypassing the ReAct loop and RAG retrieval.
3. **Task Extraction & Routing**: The query is routed to `task_extraction` to parse the required action (e.g., `PREDICT_OUTCOME`) and extract parameter slots (e.g., Location, Crop Type, Date). If slots are missing, it routes to a `Clarification` node to ask the user. If complete, it routes to the ReAct loop.
4. **ReAct Loop (Reason & Act)**: The agent enters an iterative loop:
   - **Think/Reason (Tool Caller)**: The LLM analyzes the slots and decides which tool to call.
   - **Act (Tool Execution)**: The system executes the selected tool (e.g., fetching weather, querying SQLite crop data, running the Ridge/Lasso predictive models).
   - **Observe**: The tool returns an observation to the LLM, and the loop repeats until the LLM decides it has enough information to formulate an answer.
5. **RAG & Generation**: The `generation` node takes the numerical observations from the ReAct loop, triggers a ChromaDB similarity search to fetch relevant agronomic literature (RAG), and synthesizes a grounded, plain-language response.
6. **Memory Update**: A sliding window summarization node prunes and compresses the chat history to prevent context overflow before returning the final response to the user.


---

## 🧪 Automated Evaluation & Testing

WeatherTato implements a comprehensive, multi-layered evaluation suite to guarantee chatbot correctness, safety, and End-to-End (E2E) trajectory success. All tests and reports are located in the `evals/` directory.

### Evaluation Layers:
1. **Layer 1: Unit & Component Testing (`run_evals.py`)**
   - **Unit**: Deterministic heuristic checks testing Guardrails (PII redaction, Prompt Injection), Location Resolution, and SQL/Tool constraints.
   - **RAG**: Assesses knowledge retrieval using Precision@K, Recall@K, and Mean Reciprocal Rank (MRR) against a curated literature collection.
   - **LLM-Judge**: Topic classification guardrails and basic absolute grading (LLM-as-judge) for isolated prompts.
2. **Layer 2: End-to-End Pipeline Evaluation (`run_final_e2e.py`)**
   - Evaluates the agent's full ReAct trajectory (extracting slots, calling tools in correct sequence, synthesizing final answer).
   - Simulates complete user queries across all supported capabilities (Weather, Correlation, Edge Cases, Follow-ups).
   - Applies LLM-as-Judge to score the final generated answers for **Faithfulness (Groundedness)** and **Helpfulness (Overall)** based strictly on the actual tool observations returned during execution.

### Running the Test Suite:
1. Ensure your virtual environment is activated and the active `.env` file has `DEEPSEEK_API_KEY` configured.
2. **To run the component-level evaluations:**
   ```bash
   python evals/run_evals.py --layer all
   ```
   *(Or target a specific layer: `python evals/run_evals.py --layer unit`)*
   - **Checking Correctness**: Review `metrics_unit.json` and `metrics_rag.json` generated in the `evals/` folder.

3. **To run the End-to-End evaluation:**
   ```bash
   python evals/run_final_e2e.py
   ```
   - **Checking Correctness**: Open `evals/final_evaluation_report.md`. This comprehensive markdown report contains the Task Success Rate, Trajectory Success Rate, Latency stats, and a raw results table showing the exact tools called and judge scores for every test query.
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
