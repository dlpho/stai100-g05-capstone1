import sys
import os
import io

# Force UTF-8 encoding for stdout
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from services.llm_service import llm
from core.prompts import GENERATION_PROMPT
from langchain_core.messages import SystemMessage, HumanMessage

q2 = "What was the soil moisture in Nueva Ecija in September 2023?"

md_table = """### Monthly Weather Data

|   year |   month |   precipitation_sum |   temperature_2m_mean |   temperature_2m_max |   temperature_2m_min |   surface_pressure_mean |   soil_moisture_0_to_100cm_mean |   extreme_rain_days |   extreme_heat_days |
|-------:|--------:|--------------------:|----------------------:|---------------------:|---------------------:|------------------------:|--------------------------------:|--------------------:|--------------------:|
|   2023 |       9 |               442.7 |               26.2917 |              30.9567 |              23.5333 |                 1002.25 |                        0.394117 |                   0 |                   0 |"""

prompt = GENERATION_PROMPT.format(
    query=q2,
    active_action="GET_WEATHER_DATA",
    location="Nueva Ecija, Region III",
    time_period="September 2023",
    tool_results=md_table,
    rag_context=""
)

messages = [
    SystemMessage(content=prompt),
    HumanMessage(content=q2)
]

print("Invoking Generation LLM...")
response = llm.invoke(messages)
print("\n[GENERATION LLM RESPONSE]")
print(response.content)
