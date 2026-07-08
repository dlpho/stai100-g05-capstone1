import streamlit as st
import requests
import json
import os

st.set_page_config(page_title="WeatherTato for Farmers", page_icon="🌦️", layout="wide")

st.title("🥔 WeatherTato: The Weather AI Assistant")
st.markdown("A localized conversational weather assistant tailored for farmers, agricultural workers, and delivery riders.")

st.sidebar.header("Example Queries")
st.sidebar.markdown("- What is the weather like in Quezon City tomorrow?")
st.sidebar.markdown("- Did it rain heavily in Davao last week?")
st.sidebar.markdown("- Give me the temperature and wind speed for Manila next Monday.")

if "messages" not in st.session_state:
    st.session_state.messages = []

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

if prompt := st.chat_input("Ask a weather question..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        message_placeholder = st.empty()

        with st.spinner("Fetching data and analyzing..."):
            try:
                response = requests.post(
                    f"{os.getenv('BACKEND_URL', "http://localhost:7860")}/api/chat",
                    json={"user_query": prompt},
                    timeout=30
                )
                response.raise_for_status()
                data = response.json()
                reply = data.get("response", "No response generated.")

            except requests.exceptions.RequestException as e:
                reply = f"Error communicating with backend: {e}"

        message_placeholder.markdown(reply)
        st.session_state.messages.append({"role": "assistant", "content": reply})
