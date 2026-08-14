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
    st.markdown("Here are 10 representative queries that exhibit the wide range of capabilities of WeatherTato. Try copying and pasting any of these into the chat!")
    
    st.markdown("""
1. **Historical Weather Data:** "What was the total rainfall and peak temperature in Nueva Ecija from June to October 2023?"
2. **Crop Yield Analytics:** "What was the recorded palay yield in Metric Tons per Hectare (MT/ha) for Pampanga in 2022?"
3. **Yield vs. Weather Correlation:** "How did the extreme heat days correlate with palay production in Tarlac between 2015 and 2023?"
4. **Machine Learning Yield Prediction:** "Predict the palay yield for Bulacan in 2024 based on the antecedent growing season weather."
5. **Machine Learning Price Prediction:** "Based on the climatic conditions, predict the retail price of palay in Zambales for 2024."
6. **Extremes and Anomalies:** "Which year had the highest recorded rainfall in Aurora between 2010 and 2020?"
7. **Multi-Variable Agronomic Analysis:** "How does soil moisture and shortwave radiation affect rice production in Bataan?"
8. **Literature-Grounded Explanations:** "According to literature, how does prolonged heat stress (extreme heat days) impact palay yield?"
9. **Complex Time Periods:** "What was the average temperature and evapotranspiration in Nueva Ecija during Q3 2023?"
10. **Agent Capabilities:** "What kind of agricultural and weather data can you analyze for me?"
    """)


def settings():
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