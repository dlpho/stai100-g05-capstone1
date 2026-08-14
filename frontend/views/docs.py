import streamlit as st

st.markdown("# WeatherTato Capabilities & Limitations")
st.markdown("""
Welcome to the technical overview of WeatherTato. This guide outlines what the system is designed to do and the boundaries of its current implementation.
""")

st.markdown("### What WeatherTato CAN Handle")

col1, col2 = st.columns(2)
with col1:
    st.success("**Historical Weather Analysis**\n\nRetrieves and aggregates historical meteorological data (temperature, rainfall, soil moisture, etc.) for any location in the Philippines.")
    st.success("**Crop Yield Analytics**\n\nAccesses historical palay (rice) production volume, yield (MT/ha), and retail prices specifically for Region III (Central Luzon).")

with col2:
    st.success("**Statistical Correlation**\n\nCalculates Pearson correlation coefficients between lagged weather variables and agricultural outcomes over specified time periods.")
    st.success("**Machine Learning Prediction**\n\nUses Scikit-Learn Lasso regression models to predict palay yield and prices based on historical weather patterns.")

st.success("**Literature Grounding (RAG)**\n\nCross-references statistical findings with a curated vector database of agronomic literature to explain *why* certain correlations exist.")

st.markdown("---")

st.markdown("### What WeatherTato CANNOT Handle")

col3, col4 = st.columns(2)
with col3:
    st.error("**Future Weather Forecasts**\n\nThe system is strictly retrospective and analytical. It cannot predict if it will rain tomorrow or provide 7-day weather forecasts.")
    st.error("**Farming & Agronomic Advice**\n\nWeatherTato is an analytical tool, not an agronomist. It will not recommend fertilizer application rates, planting dates, or pest control strategies.")

with col4:
    st.error("**Outside Region III Crop Data**\n\nWhile weather can be queried nationwide, agricultural records (yield/production) are exclusively constrained to the provinces of Central Luzon.")
    st.error("**Non-Palay Crops**\n\nThe current database and predictive models are trained solely on Palay (rice). Corn and other crops are unsupported.")


st.markdown("---")

st.markdown("### Backend Architecture Overview")
st.markdown("""
WeatherTato operates on a **LangGraph** orchestration pipeline:
1. **Guardrails:** Intercepts unsupported queries (like farming advice or future forecasts) before they reach the execution engine.
2. **Intent Extraction:** Powered by DeepSeek-V4-Flash, the agent dynamically extracts locations, dates, and variables from natural language.
3. **Deterministic Tools:** Instead of hallucinating numbers, the agent invokes dedicated Python scripts to query SQLite databases or Open-Meteo APIs.
4. **Context Synthesis:** Final answers are synthesized by weaving together raw statistical data and retrieved agronomic literature.
""")
