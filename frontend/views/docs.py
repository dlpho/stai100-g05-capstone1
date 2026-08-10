import streamlit as st

st.markdown("# Documentation")
st.markdown("Welcome to the WeatherTato documentation. Here you can find information about what you can do with the assistant.")

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
