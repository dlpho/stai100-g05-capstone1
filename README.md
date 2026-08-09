# 🥔 WeatherTato: The Weather AI Assistant

WeatherTato is a localized conversational weather assistant tailored for farmers and agricultural workers in the Philippines. It operates under strict guardrail safety guidelines to translate weather data into objective facts for farmers to use

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
     python backend/app/main.py
     ```
    * **Streamlit Frontend (Port 8000):**
      ```bash
      streamlit run frontend/app.py --server.port 8000
      ```

---

## 🏛️ Architecture Overview

The system uses a LangGraph state graph with MLflow observability.

### Module Specifications

- Guardrails
- Task Classifier
- Slot Extraction & Disambiguation
- Tool Execution (Open-Meteo)
- Generation

---

## 📋 Module Ownership

| Team Member | Assigned Modules |
| :--- | :--- |
| **Denise Liana Ho**  | RAG, API Endpoint  |
| **Simon Anthony Libut** | Prompt Engineering, Guardrails  |
| **Jericho Migell Reyes** | Structured Outputs, Tool Use |