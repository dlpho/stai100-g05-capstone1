# 🌦️[agent_name]: Weather AI Assistant

TODO: project overview
intelligent conversational weather

## Installation & Setup



## Architecture Overview
TODO: system diagram here

## Module Ownership
### 📋 Module Ownership Table

| Team Member | Assigned Modules |
| :--- | :--- |
| **Denise Liana Ho**  | RAG, API Endpoint, LLMOps, Dockerization  |
| **Simon Anthony Libut** | Prompt Engineering, Memory, Guardrails, ReAct | 
| **Jericho Migell Reyes** | Structured Outputs, Disambiguation, SQL, Tool Use |



# delete later
- [group master docs](https://docs.google.com/document/d/1MIx3Yz2JKJ0vJe9jvgeRk3OjS7KXhUzn9Og1oPNU-Dw/edit?usp=sharing)

## Repository Structure
ideally, feel free to deviate
```text
stai100-g05-capstone1/
├── app/
│   ├── main.py          <-- LLMOps Init
│   ├── api.py           <-- FastAPI/REST
│   └── core/
│       ├── agent.py     <-- ReAct Loop
│       └── prompts.py   <-- System Prompts
│       └── memory.py    <-- Session Memory
│   └── tools/
│       └── weather_api.py <-- Weather API Integ
├── ui/
│   └── chat_app.py      <-- Streamlit UI
├── Dockerfile           <-- Container setup
├── requirements.txt
└── README.md
```