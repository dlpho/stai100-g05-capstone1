from fastapi import FastAPI
import uvicorn
from backend.app.api.routes import router

app = FastAPI(title="WeatherAI Backend", version="1.0.0")

app.include_router(router, prefix="/api")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=7860)
