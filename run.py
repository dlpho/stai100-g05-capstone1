import subprocess
import time
import sys
import os
import signal

def main():
    print("Starting WeatherTato Backend (FastAPI)...")

    # We need to set PYTHONPATH so that "app" package can be imported directly
    env = os.environ.copy()
    workspace_dir = os.path.abspath(os.path.dirname(__file__))
    backend_dir = os.path.join(workspace_dir, "backend")
    env["PYTHONPATH"] = backend_dir + os.pathsep + env.get("PYTHONPATH", "")

    backend_process = subprocess.Popen(
        [sys.executable, "-m", "app.main"],
        env=env
    )

    # Wait for backend to start up
    time.sleep(3)

    print("Starting WeatherTato Frontend (Streamlit)...")
    frontend_process = subprocess.Popen(
        [sys.executable, "-m", "streamlit", "run", "frontend/app.py", "--server.port", "8000", "--server.address", "0.0.0.0"]
    )

    try:
        frontend_process.wait()
    except KeyboardInterrupt:
        print("\nShutting down services...")
        backend_process.send_signal(signal.SIGTERM)
        frontend_process.send_signal(signal.SIGTERM)

if __name__ == "__main__":
    main()
