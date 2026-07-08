import streamlit as st
import requests
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv(override=True)

BACKEND_URL = os.getenv("BACKEND_URL", "http://127.0.0.1:7860")

# Conversation buffer: number of recent messages sent to the backend as LLM context.
# The full chat history is always displayed on screen (scrollable).
# Only the last MAX_HISTORY_MESSAGES are included in each API request to limit token usage.
# Session-isolated — stored only in st.session_state, never written to disk.
MAX_HISTORY_MESSAGES = 3


# MODULE 10 - CHAT UI
st.set_page_config(page_title="WeatherTato", page_icon="🌦️", layout="wide")

# --- SIDEBAR DOCUMENTATION ---
with st.sidebar:
    st.markdown("# WeatherTato Assistant")
    st.markdown("A gramular weather advisor tailored for Filipino farmers, agricultural workers, and delivery riders.")
    
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
    
    st.markdown("---")
    if st.button("🔄 Restart Session", use_container_width=True):
        st.session_state.messages = []
        st.rerun()


# --- MAIN INTERFACE ---
st.title("🥔 WeatherTato: AI Weather Assistant")
st.markdown("##### What can I help you with?.")

if "messages" not in st.session_state:
    st.session_state.messages = []

# Render chat history
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# Quick Start Cards (Only show if there is no conversation history)
# Persist quick-prompt selection across st.rerun() so the message gets processed
if "pending_prompt" not in st.session_state:
    st.session_state.pending_prompt = None

new_prompt = None
if not st.session_state.messages:
    st.markdown("<br><br>", unsafe_allow_html=True)
    st.markdown("### 💡 Ask a question to start:")
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Hey WeatherTato, what can you help me with?", use_container_width=True):
            st.session_state.pending_prompt = "Hey WeatherTato, what can you help me with?"
        if st.button("What is the weather like in Manila tomorrow?", use_container_width=True):
            st.session_state.pending_prompt = "What is the weather like in Manila tomorrow?"
            
    with col2:
        if st.button("Give me the soil temperature, wind speed, and soil moisture for Barangay Poblacion, Alicia, Bohol.", use_container_width=True):
            st.session_state.pending_prompt = "Give me the soil temperature, wind speed, and soil moisture for Barangay Poblacion, Alicia, Bohol."
        if st.button("What is the year with the most rainfall in 2023 to 2026 in Makati City?", use_container_width=True):
            st.session_state.pending_prompt = "What is the year with the most rainfall in 2023 to 2026 in Makati City?"

# Pick up any pending quick-prompt from session state
if st.session_state.pending_prompt:
    new_prompt = st.session_state.pending_prompt
    st.session_state.pending_prompt = None


# Chat Input Box
if chat_prompt := st.chat_input("Ask WeatherTato a question..."):
    new_prompt = chat_prompt

# Process message if submitted
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
                # Send only the last MAX_HISTORY_MESSAGES of history as context (excluding latest user msg)
                full_history = st.session_state.messages[:-1]
                history = full_history[-MAX_HISTORY_MESSAGES:]
                response = requests.post(
                    f"{BACKEND_URL}/api/chat",
                    json={
                        "user_query": new_prompt,
                        "history": history
                    },
                    timeout=45
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
        # Full history kept in session_state for display — no trimming here.
        # Context is limited at the API call level (see history slice above).

        
    # Force streamlit rerun to clear the sample buttons now that messages exist
    st.rerun()
