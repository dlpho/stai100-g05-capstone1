import subprocess
import time
import sys
import os
import signal
from dotenv import load_dotenv

# Load env file in the workspace root
load_dotenv()

def main():
    # We need to set PYTHONPATH so that "app" package can be imported directly
    env = os.environ.copy()
    workspace_dir = os.path.abspath(os.path.dirname(__file__))
    backend_dir = os.path.join(workspace_dir, "backend")
    env["PYTHONPATH"] = backend_dir + os.pathsep + env.get("PYTHONPATH", "")

    # Dynamic MLflow process management
    enable_mlflow = os.getenv("ENABLE_MLFLOW", "false").lower() in ("true", "1", "t")
    mlflow_tracking_uri = os.getenv("MLFLOW_TRACKING_URI", "http://127.0.0.1:5000")
    
    start_local_mlflow = False
    if enable_mlflow:
        from urllib.parse import urlparse
        try:
            parsed = urlparse(mlflow_tracking_uri)
            if parsed.hostname in ("127.0.0.1", "localhost", "0.0.0.0"):
                start_local_mlflow = True
        except Exception:
            pass

    mlflow_process = None
    if start_local_mlflow:
        from urllib.parse import urlparse
        parsed = urlparse(mlflow_tracking_uri)
        host = parsed.hostname or "127.0.0.1"
        port = str(parsed.port or 5000)
        print(f"Starting local MLflow Tracking Server on {host}:{port}...")
        os.makedirs("mlflow_data", exist_ok=True)
        mlflow_process = subprocess.Popen(
            [
                sys.executable, "-m", "mlflow", "server",
                "--host", host,
                "--port", port,
                "--backend-store-uri", "sqlite:///mlflow_data/mlflow.db",
                "--default-artifact-root", "./mlflow_data/artifacts"
            ],
            env=env
        )
        # Wait for MLflow to start up
        time.sleep(3)
    elif enable_mlflow:
        print(f"Using remote MLflow Tracking Server at: {mlflow_tracking_uri}")

    print("Starting WeatherTato Backend (FastAPI)...")
    backend_log = open("backend.log", "w", encoding="utf-8")
    backend_process = subprocess.Popen(
        [sys.executable, "-m", "app.main"],
        env=env,
        stdout=backend_log,
        stderr=backend_log
    )
    
    # Wait for backend to start up
    time.sleep(2)
    
    print("Starting WeatherTato Frontend (Streamlit)...")
    frontend_process = subprocess.Popen(
        [sys.executable, "-m", "streamlit", "run", "frontend/app.py", "--server.port", "8000", "--server.address", "0.0.0.0"]
    )

    try:
        frontend_process.wait()
    except KeyboardInterrupt:
        print("\nShutting down services...")
        backend_process.send_signal(signal.SIGTERM)
        if mlflow_process:
            mlflow_process.send_signal(signal.SIGTERM)
        frontend_process.send_signal(signal.SIGTERM)

if __name__ == "__main__":
    main()
