# stai100-g05-capstone1
- [group master docs](https://docs.google.com/document/d/1MIx3Yz2JKJ0vJe9jvgeRk3OjS7KXhUzn9Og1oPNU-Dw/edit?usp=sharing)

## Environment Setuo
to follow

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