"""
WeatherTato — FastAPI Application Entry Point
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import os
from core.env import ENABLE_MLFLOW, MLFLOW_TRACKING_URI, MLFLOW_EXPERIMENT_NAME
from api.routes import router

if ENABLE_MLFLOW:
    try:
        import mlflow
        os.makedirs("mlflow_data", exist_ok=True)
        mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)
        mlflow.set_experiment(MLFLOW_EXPERIMENT_NAME)
        mlflow.langchain.autolog()
        print(f"MLflow auto-tracing enabled. Tracking URI: {MLFLOW_TRACKING_URI}")
    except Exception as e:
        print(f"Failed to initialize MLflow tracing: {e}")

app = FastAPI(title="WeatherTato Backend", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api")

if __name__ == "__main__":
    host = os.getenv("BACKEND_HOST", "0.0.0.0")
    port = int(os.getenv("BACKEND_PORT", "7860"))
    uvicorn.run(app, host=host, port=port)
