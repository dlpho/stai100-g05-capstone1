import streamlit as st
import requests

# FastAPI server URL
BACKEND_URL = "http://localhost:7860"

st.set_page_config(page_title="WeatherAI", layout="wide")
st.title("🌦️ WeatherAI Chatbot")
st.caption("Ask about weather forecasts, rainfall history, crop alerts, and field work windows anywhere within the Philippines.")

# Initialize persistent session states
if "messages" not in st.session_state:
    st.session_state.messages = []
if "candidates" not in st.session_state:
    st.session_state.candidates = None
if "pending_question" not in st.session_state:
    st.session_state.pending_question = ""

# Sidebar — question guide + session controls
with st.sidebar:
    st.header("💬 What can I ask?")
    st.caption("All queries must include a location in the **Philippines** (e.g. *Bacarra, Ilocos Norte*).")

    with st.expander("🌤️ General Weather Forecast"):
        st.markdown(
            "Current conditions, temperature, rain, wind, and humidity for the next 14 days.\n\n"
            "**Examples:**\n"
            "- *What is the weather in Laoag City this week?*\n"
            "- *Will it be hot tomorrow in Cebu?*\n"
            "- *Give me a 7-day forecast for Davao.*"
        )

    with st.expander("💧 Irrigation & Rainfall Forecast"):
        st.markdown(
            "Upcoming rainfall and shower amounts to plan irrigation schedules.\n\n"
            "**Examples:**\n"
            "- *Will there be enough rain for irrigation in Ilocos Norte next week?*\n"
            "- *How much rainfall is expected in Batangas over 2 weeks?*\n"
            "- *Is rain coming soon for my crops in Nueva Ecija?*"
        )

    with st.expander("🌾 Crop Stress & Disease Alert"):
        st.markdown(
            "Heat stress, cold stress, and fungal/pest risk based on temperature and max humidity.\n\n"
            "**Examples:**\n"
            "- *Is there a risk of heat stress for crops in Pampanga?*\n"
            "- *What are the crop alert conditions in Bukidnon?*\n"
            "- *Will humidity be high enough to cause disease in my fields?*"
        )

    with st.expander("🚜 Field Work Suitability"):
        st.markdown(
            "Suitable dry windows for harvesting, land preparation, and planting.\n\n"
            "**Examples:**\n"
            "- *Which days next week are good for harvesting in Isabela?*\n"
            "- *When can I do land preparation in Cagayan Valley?*\n"
            "- *Are there dry days for planting in Laguna?*"
        )

    with st.expander("🌧️ Historical Rainfall"):
        st.markdown(
            "Past monthly rainfall totals and rainy day counts for any date range.\n\n"
            "**Examples:**\n"
            "- *How much did it rain in Ilocos Norte last year?*\n"
            "- *What were the rainy months in Leyte in 2023?*\n"
            "- *Rainfall data for Quezon City from January to June 2024.*"
        )

    with st.expander("🌡️ Historical Temperature"):
        st.markdown(
            "Monthly average highs and lows for any past date range.\n\n"
            "**Examples:**\n"
            "- *What were the average temperatures in Baguio last year?*\n"
            "- *How hot was it in Cebu in summer 2023?*\n"
            "- *Temperature range in Davao from 2022 to 2023.*"
        )

    with st.expander("📅 Historical Climate Summary"):
        st.markdown(
            "Combined monthly overview of temperature and rainfall for any past period.\n\n"
            "**Examples:**\n"
            "- *Give me a historical weather overview for Iloilo in 2023.*\n"
            "- *What was the climate like in Zamboanga last year?*\n"
            "- *Summarize the weather in Metro Manila from 2022 to 2023.*"
        )

    st.divider()
    if st.button("🔄 Reset Conversation"):
        st.session_state.messages = []
        st.session_state.candidates = None
        st.session_state.pending_question = ""
        st.success("Session reset.")
        st.rerun()

# Display chat history log
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# Handler for ambiguous location resolution
if st.session_state.candidates:
    st.warning("Multiple locations match your request. Please select a specific area below:")
    
    for idx, cand in enumerate(st.session_state.candidates):
        # Format candidate display label
        addr_parts = []
        for key in ["barangay", "municipality_city", "province", "region"]:
            if cand.get(key):
                addr_parts.append(cand[key])
        addr_str = ", ".join(addr_parts)
        
        # Display coordinate selection buttons
        if st.button(f"📍 {addr_str} (Lat: {cand.get('latitude')}, Lng: {cand.get('longitude')})", key=f"cand_{idx}"):
            payload = {
                "question": st.session_state.pending_question,
                "selected_location": cand
            }
            
            with st.spinner("Processing selected location..."):
                try:
                    res = requests.post(f"{BACKEND_URL}/api/chat", json=payload)
                    if res.status_code == 200:
                        data = res.json()
                        st.session_state.messages.append({"role": "user", "content": st.session_state.pending_question})
                        
                        # print(data.get('location'))
                        
                        ans_text = data.get('answer')
                        st.session_state.messages.append({"role": "assistant", "content": ans_text})
                    else:
                        st.error(f"Backend error: {res.text}")
                except Exception as e:
                    st.error(f"Connection failure: {str(e)}")
            
            # Reset ambiguity loop parameters
            st.session_state.candidates = None
            st.session_state.pending_question = ""
            st.rerun()

else:
    # Accept standard user chat inquiry
    user_query = st.chat_input("Enter your weather or crop stress query...")
    if user_query:
        payload = {
            "question": user_query
        }
        
        with st.spinner("Getting your response..."):
            try:
                res = requests.post(f"{BACKEND_URL}/api/chat", json=payload)
                if res.status_code == 200:
                    data = res.json()
                    
                    if data.get("status") == "ambiguous":
                        st.session_state.candidates = data.get("candidates")
                        st.session_state.pending_question = user_query
                        st.rerun()
                    else:
                        st.session_state.messages.append({"role": "user", "content": user_query})
                        
                        ans_text = f"**Location Resolved:** {data.get('location')}\n\n{data.get('answer')}"
                        st.session_state.messages.append({"role": "assistant", "content": ans_text})
                        st.rerun()
                else:
                    st.error(f"Backend error: {res.text}")
            except Exception as e:
                st.error(f"Connection failure: {str(e)}")
