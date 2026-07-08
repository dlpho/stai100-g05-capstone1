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

The RAG (Retrieval-Augmented Generation) pipeline bypasses static databases to retrieve and process live environmental indicators dynamically:

```text
  [ User Question ]
          │
          ▼
   1. Input Guardrails (PII Check, Prompt Injection Check)
          │
          ▼
   2. Intent Classifier (app/core/rag_handler.py)
          ├── BOT_INFO: Bypass Location & RAG ───────────────────┐
          └── Weather Queries (Historical/Forecast/General)      │
                      │                                          │
                      ▼                                          │
   3. Weather Guardrails (Topic Check, Advice Check)             │
                      │                                          │
                      ▼                                          │
   4. Location Resolution (app/tools/location_search.py)         │
          ├── Unique: Coordinates Resolved (Lat/Lng)             │
          ├── Ambiguous: Return Choice List to UI                │
          └── None: Request Location Input                       │
                      │                                          │
                      ▼                                          │
   5. Weather API Query (app/tools/weather_api.py)               │
          ├── Historical: Open-Meteo Archive API                 │
          └── Forecast: Open-Meteo Forecast API                  │
                      │                                          │
                      ▼                                          │
   6. Pandas aggregation engine (app/core/rag_handler.py)        │
          ├── Computes stats (averages, totals, rainy days)      │
          └── Evaluates thresholds (disease/pest indexes)        │
                      │                                          │
                      ▼                                          │
   7. Compilation & Response Generation (app/core/agent.py) <────┘
          ├── Formats weather data into markdown tables (if RAG)
          └── Generates plain LLM response using safety prompt
                      │
                      ▼
                [ Final Answer ]
```

### Module Specifications

- **`app/tools/location_search.py`**: Searches geographic coordinate records hierarchically (Province -> Municipality -> Barangay) based on matching sub-tokens in the user question.
- **`app/tools/weather_api.py`**: Executes direct REST calls to Open-Meteo services without caching dependencies. Supports weather forecast (up to 14 days) and historical metrics. Configured with `"timezone": "auto"` to automatically align API data timestamps to the local timezone of the resolved coordinates.
- **`app/core/rag_handler.py`**: 
  - Classifies questions into specific categories (e.g., field work windows, crop alerts, and conversational bot info) using LLM intent classification.
  - Houses Pandas data pipelines that aggregate raw daily weather matrices.
  - Converts data into clean Markdown tables to save token usage.
- **`app/core/agent.py`**: Orchestrates input validation, intent classification routing (bypassing location/RAG for bot info queries), location resolution, RAG execution, and safety prompt assembly.

---

## 📋 Module Ownership

| Team Member | Assigned Modules |
| :--- | :--- |
| **Denise Liana Ho**  | RAG, API Endpoint  |
| **Simon Anthony Libut** | Prompt Engineering, Guardrails  |
| **Jericho Migell Reyes** | Structured Outputs, Tool Use |