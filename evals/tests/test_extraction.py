from langchain_core.messages import HumanMessage, AIMessage, ToolMessage, SystemMessage

# Simulate the exact state.messages going into Q2 generation
raw_history = [
    SystemMessage(content="instructions"),
    HumanMessage(content="Q1: How strong were wind gusts"),
    AIMessage(content="", tool_calls=[{"name": "get_monthly_weather_tool", "args": {}, "id": "123"}]),
    ToolMessage(content="### Monthly Weather Data\nSoil moisture is 0.394", tool_call_id="123"),
    HumanMessage(content="Q1: How strong were wind gusts"),
    AIMessage(content="I have the data now.", tool_calls=[]),
    HumanMessage(content="Q1: How strong were wind gusts"),
    AIMessage(content="Q1 Final Response"),
    HumanMessage(content="Q2: What was the soil moisture?"),
    AIMessage(content="I don't need to call a tool.", tool_calls=[])
]

tool_results_md = []
for msg in reversed(raw_history):
    if isinstance(msg, ToolMessage):
        tool_results_md.append(msg.content)
    elif isinstance(msg, AIMessage) and msg.tool_calls:
        break

print("Extracted:")
print(tool_results_md)
