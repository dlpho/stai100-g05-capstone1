"""
WeatherTato — Environment Configuration Loader
"""
import os
from dotenv import load_dotenv

load_dotenv()

# Extract DeepSeek environment variables
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-v4-flash")
DEEPSEEK_BASE_URL = os.getenv(
    "DEEPSEEK_BASE_URL",
    "https://api.deepseek.com"
)

# Extract MLFlow environment variables
ENABLE_MLFLOW: bool = os.getenv("ENABLE_MLFLOW", "false").lower() in ("true", "1", "t")
MLFLOW_TRACKING_URI: str = os.getenv("MLFLOW_TRACKING_URI", "sqlite:///mlflow_data/mlflow_traces.db")
MLFLOW_EXPERIMENT_NAME: str = os.getenv("MLFLOW_EXPERIMENT_NAME", "WeatherTato")
