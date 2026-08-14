import streamlit as st

st.markdown("# 📖 WeatherTato Documentation")
st.markdown("Welcome to WeatherTato! This agentic AI assistant is specialized in analyzing the impact of historical weather on palay (rice) agriculture in Central Luzon.")

st.markdown("### ❓ Questions You Can Ask")
st.markdown("""
* **Historical Weather:** Ask about past weather trends (e.g., *"What was the monthly temperature in Nueva Ecija in 2023?"*)
* **Crop Analytics:** Query agricultural data (e.g., *"What was the palay yield in Pampanga in 2022?"*)
* **Correlation Analysis:** Ask how weather affects crops (e.g., *"How does rainfall correlate with palay production in Tarlac?"*)
* **Yield Prediction:** Request machine-learning forecasts for current/past seasons (e.g., *"Predict the palay yield for Bulacan in 2024 based on the weather."*)
""")

st.warning("⚠️ **Note:** WeatherTato does NOT provide future weather forecasts or direct farming/agronomic advice. It is strictly an analytical tool for historical and statistical insights.")

st.markdown("### 📊 Supported Variables")
st.markdown("""
* **Agricultural:** Palay Yield (MT/ha), Production Volume (MT), Retail Price (PHP/kg)
* **Temperature:** Maximum, Minimum, and Mean Temperature
* **Precipitation:** Rainfall sum, Extreme Rain Days
* **Soil & Environment:** Soil Moisture, Surface Pressure, Shortwave Radiation
* **Wind:** Maximum Wind Gusts
* **Evapotranspiration (ET0):** Crop water loss metrics
""")

st.markdown("### 📍 Supported Locations (Region III Scope)")
st.markdown("""
While the chatbot can technically retrieve weather for any location in the Philippines, **crop analytics and yield predictions are strictly limited to Region III (Central Luzon):**
* Aurora
* Bataan
* Bulacan
* Nueva Ecija
* Pampanga
* Tarlac
* Zambales
""")

st.markdown("### 🧠 How It Works (Backend Architecture)")
st.markdown("""
Behind the scenes, WeatherTato runs on a sophisticated **LangGraph** orchestration pipeline:
1. **Guardrails:** Intercepts prompt injections, redacts PII, and forces LLM classification to block unsupported topics.
2. **Intent Extraction:** Uses DeepSeek-V4-Flash to dynamically extract your desired location, time period, and analytical intent.
3. **Data Science Tools:** Instead of hallucinating numbers, the agent invokes dedicated Python tools to query SQLite databases, fetch Open-Meteo APIs, run Pearson correlations, or invoke Scikit-Learn **Lasso regression models** for yield predictions.
4. **Literature Grounding (RAG):** When finalizing the answer, the agent cross-references its statistical calculations against a ChromaDB vector store of agronomic literature, synthesizing raw data with published agricultural research.
""")
