"""
WeatherTato — Streamlit Chat Frontend
"""
import streamlit as st
import requests
import os
from dotenv import load_dotenv

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
    st.logo(logo)
    col1, col2 = st.columns([1, 10], vertical_alignment="center")
    with col1:
        st.image(logo)
    with col2:
        st.title(title)
        st.markdown("<div style='margin-top: -15px;'><i>Your all-in-one AI weather assistant!</i></div>", unsafe_allow_html=True)
    
    if "messages" not in st.session_state:
        st.session_state.messages = []

    # Render chat history
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

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
            with st.spinner("Analyzing request and fetching weather telemetry..."):
                try:
                    full_history = st.session_state.messages[:-1]
                    history = full_history[-MAX_HISTORY_MESSAGES:]
                    response = requests.post(
                        f"{BACKEND_URL}/api/chat",
                        json={"user_query": new_prompt, "history": history},
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
                with st.expander("⚠️ Error details", expanded=False):
                    st.code(error_detail, language="text")
            st.session_state.messages.append({"role": "assistant", "content": reply})
            
        st.rerun()


def docs():
    st.logo(logo)
    st.title("📚 Documentation")
    st.markdown("### ❓ Questions You Can Ask")
    st.markdown("""
    * **Forecasts:** Ask about upcoming conditions (e.g., *"Will it rain tomorrow in Davao?"*)
    * **Historical Analytics:** Ask about past weather trends (e.g., *"What was the monthly temperature in Cebu in 2024?"*)
    * **Extreme Weather:** Find peak records (e.g., *"Which year had the highest rainfall in Makati?"*)
    """)
    
    st.markdown("### 📊 Supported Variables")
    st.markdown("""
    * **Temperature:** Peak, minimum, and mean temperature
    * **Rainfall:** Precipitation sum
    * **Wind Speed:** Daily wind gusts & speed
    * **Soil Health:** Soil moisture (0-100cm depth) & Soil temperature
    * **Air Quality/Comfort:** Relative humidity
    * **Evapotranspiration (ET0):** Crop water loss metrics
    """)
    
    st.markdown("### 📍 Supported Locations")
    st.markdown("""
    You can query coordinates at any level in the Philippines:
    * **Barangay** (e.g., *Barangay Poblacion, Alicia, Bohol*)
    * **Municipality / City** (e.g., *Makati City*)
    * **Province** (e.g., *Pangasinan*)
    """)


def samples():
    st.logo(logo)
    st.title("💡 Sample Queries")
    st.markdown("Click any sample query below to instantly test it in the chat!")
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Hey WeatherTato, what can you help me with?", use_container_width=True):
            st.session_state.pending_prompt = "Hey WeatherTato, what can you help me with?"
            st.switch_page(page_chat_obj)
        if st.button("What is the weather like in Manila tomorrow?", use_container_width=True):
            st.session_state.pending_prompt = "What is the weather like in Manila tomorrow?"
            st.switch_page(page_chat_obj)
            
    with col2:
        if st.button("Give me the soil temperature, wind speed, and soil moisture for Barangay Poblacion, Alicia, Bohol.", use_container_width=True):
            st.session_state.pending_prompt = "Give me the soil temperature, wind speed, and soil moisture for Barangay Poblacion, Alicia, Bohol."
            st.switch_page(page_chat_obj)
        if st.button("What is the year with the most rainfall in 2023 to 2026 in Makati City?", use_container_width=True):
            st.session_state.pending_prompt = "What is the year with the most rainfall in 2023 to 2026 in Makati City?"
            st.switch_page(page_chat_obj)


def settings():
    st.logo(logo)
    st.title("Settings")
    
    st.markdown("### Session Management")
    if st.button("Restart Session", use_container_width=True, type="primary"):
        st.session_state.messages = []
        st.success("Chat history cleared!")
        
    st.markdown("### UI Controls")
    wide_mode = st.toggle("Wide mode", value=st.session_state.get("wide_mode", True))
    if wide_mode != st.session_state.get("wide_mode", True):
        st.session_state.wide_mode = wide_mode
        st.rerun()


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
    st.caption("Created by Group 5 STAI100 - S09")

pg.run()
