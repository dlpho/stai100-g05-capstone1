"""
WeatherTato — Streamlit Chat Frontend
"""
import streamlit as st
import requests
import os
from dotenv import load_dotenv
from datetime import datetime

# Load environment variables
load_dotenv(override=True)

BACKEND_URL = os.getenv("BACKEND_URL", "http://127.0.0.1:7860")
MAX_HISTORY_MESSAGES = 3

logo = "frontend/assets/logo.png"
title = "WeatherTato"


# ==========================================
# PAGE FUNCTIONS
# ==========================================

def page_chat():
    """Renders the main chat interface for interacting with the WeatherTato assistant."""
    st.logo(logo)
    col1, col2 = st.columns([1, 10], vertical_alignment="center")
    with col1:
        st.image(logo)
    with col2:
        st.title(title)
        st.markdown("<div style='margin-top: -15px;'><i>Your all-in-one AI weather assistant!</i></div>", unsafe_allow_html=True)
    
    import uuid
    if "session_id" not in st.session_state:
        st.session_state.session_id = str(uuid.uuid4())
    if "messages" not in st.session_state:
        st.session_state.messages = []

    # Render chat history
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
            if message.get("error_detail"):
                st.error(message["error_detail"], icon=":material/error:")

    # Pick up any pending quick-prompt from session state
    new_prompt = None
    if "pending_prompt" not in st.session_state:
        st.session_state.pending_prompt = None

    if st.session_state.pending_prompt:
        new_prompt = st.session_state.pending_prompt
        st.session_state.pending_prompt = None

    if chat_prompt := st.chat_input("Ask WeatherTato a question..."):
        new_prompt = chat_prompt

    if new_prompt:
        # Append and show User message
        st.session_state.messages.append({"role": "user", "content": new_prompt})
        with st.chat_message("user"):
            st.markdown(new_prompt)
            
        # Get and show Assistant response
        with st.chat_message("assistant"):
            message_placeholder = st.empty()
            error_detail = None
            with st.spinner("Analyzing your request..."):
                try:
                    response = requests.post(
                        f"{BACKEND_URL}/api/chat",
                        json={
                            "user_query": new_prompt, 
                            "session_id": st.session_state.session_id
                        },
                        timeout=60
                    )
                    response.raise_for_status()
                    data = response.json()
                    reply = data.get("response") or "Sorry, I couldn't process that at the moment. Please try again."
                    error_detail = data.get("error_detail")
                    
                except requests.exceptions.ConnectionError:
                    reply = "Sorry, I couldn't process that at the moment. Please try again."
                    error_detail = f"Could not connect to backend at {BACKEND_URL}. Make sure the server is running."
                except requests.exceptions.RequestException as e:
                    reply = "Sorry, I couldn't process that at the moment. Please try again."
                    raw = e.response.text if hasattr(e, "response") and e.response is not None else str(e)
                    error_detail = raw
                    
            message_placeholder.markdown(reply)
            if error_detail:
                st.error(error_detail, icon=":material/error:")
            st.session_state.messages.append({
                "role": "assistant", 
                "content": reply,
                "error_detail": error_detail
            })
            
        st.rerun()


def docs():
    """Renders the documentation page detailing WeatherTato's capabilities, limitations, and architecture."""
    st.logo(logo)
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


def samples():
    """Renders the sample queries page, allowing users to test predefined prompts."""
    st.logo(logo)
    st.title("Sample Queries")
    st.markdown("Click any sample query below to instantly test it in the chat! These queries exhibit the full range of WeatherTato's analytical capabilities.")
    
    st.markdown("#### Historical Weather & Extremes")
    c1, c2 = st.columns(2)
    with c1:
        if st.button("What was the total rainfall and peak temperature in Nueva Ecija from June to October 2023?", use_container_width=True):
            st.session_state.pending_prompt = "What was the total rainfall and peak temperature in Nueva Ecija from June to October 2023?"
            st.switch_page(page_chat_obj)
        if st.button("Which year had the highest recorded rainfall in Aurora between 2010 and 2020?", use_container_width=True):
            st.session_state.pending_prompt = "Which year had the highest recorded rainfall in Aurora between 2010 and 2020?"
            st.switch_page(page_chat_obj)
    with c2:
        if st.button("What was the average temperature and evapotranspiration in Nueva Ecija during Q3 2023?", use_container_width=True):
            st.session_state.pending_prompt = "What was the average temperature and evapotranspiration in Nueva Ecija during Q3 2023?"
            st.switch_page(page_chat_obj)
        if st.button("What kind of agricultural and weather data can you analyze for me?", use_container_width=True):
            st.session_state.pending_prompt = "What kind of agricultural and weather data can you analyze for me?"
            st.switch_page(page_chat_obj)

    st.markdown("#### Crop Yield & Analytics")
    c3, c4 = st.columns(2)
    with c3:
        if st.button("What was the recorded palay yield in Metric Tons per Hectare for Pampanga in 2022?", use_container_width=True):
            st.session_state.pending_prompt = "What was the recorded palay yield in Metric Tons per Hectare for Pampanga in 2022?"
            st.switch_page(page_chat_obj)
    with c4:
        if st.button("Compare the palay production volume of Pampanga and Tarlac during the 2022 wet season.", use_container_width=True):
            st.session_state.pending_prompt = "Compare the palay production volume of Pampanga and Tarlac during the 2022 wet season."
            st.switch_page(page_chat_obj)

    st.markdown("#### Machine Learning & Correlation")
    c5, c6 = st.columns(2)
    with c5:
        if st.button("Predict the palay yield for Bulacan in 2024 based on the antecedent growing season weather.", use_container_width=True):
            st.session_state.pending_prompt = "Predict the palay yield for Bulacan in 2024 based on the antecedent growing season weather."
            st.switch_page(page_chat_obj)
        if st.button("How did extreme heat days correlate with palay production in Tarlac between 2015 and 2023?", use_container_width=True):
            st.session_state.pending_prompt = "How did extreme heat days correlate with palay production in Tarlac between 2015 and 2023?"
            st.switch_page(page_chat_obj)
    with c6:
        if st.button("Based on climatic conditions, predict the retail price of palay in Zambales for 2024.", use_container_width=True):
            st.session_state.pending_prompt = "Based on climatic conditions, predict the retail price of palay in Zambales for 2024."
            st.switch_page(page_chat_obj)
        if st.button("According to literature, how does prolonged heat stress impact palay yield?", use_container_width=True):
            st.session_state.pending_prompt = "According to literature, how does prolonged heat stress impact palay yield?"
            st.switch_page(page_chat_obj)


def settings():
    """Renders the settings page for managing application preferences and chat sessions."""
    st.logo(logo)
    st.title("Settings")
    
    st.markdown("#### Preferences")
    wide_mode = st.toggle("Wide mode", value=st.session_state.get("wide_mode", True))
    if wide_mode != st.session_state.get("wide_mode", True):
        st.session_state.wide_mode = wide_mode
        st.rerun()

    st.markdown("#### Session Management")
    if st.button("Restart Session", use_container_width=True, type="primary"):
        st.session_state.messages = []
        import uuid
        st.session_state.session_id = str(uuid.uuid4())
        st.success("Chat history cleared and new backend session started!")
        


# ==========================================
# PAGE CONFIGURATION & ROUTING
# ==========================================

# 1. Setup page config
st.set_page_config(
    page_title="WeatherTato", 
    page_icon="frontend/assets/logo.png", 
    layout="wide" if st.session_state.get("wide_mode", True) else "centered"
)

# 2. Define pages
page_chat_obj = st.Page(page_chat, title="Chat", icon=":material/chat:", default=True)
samples_obj = st.Page(samples, title="Sample Queries", icon=":material/lightbulb:")
docs_obj = st.Page(docs, title="Documentation", icon=":material/menu_book:")
settings_obj = st.Page(settings, title="Preferences", icon=":material/settings:")

pages = {
    "WeatherTato": [
        page_chat_obj,
        samples_obj,
        docs_obj,
    ],
    "Settings": [
        settings_obj
    ]
}

# 3. Initialize router and run
pg = st.navigation(pages)

with st.sidebar:
    st.caption(f"Current Date & Time: {datetime.now().strftime('%b %d, %Y %I:%M %p')}")
    # st.caption("Created by Group 5 STAI100 - S09")

pg.run()