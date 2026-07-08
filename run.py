import subprocess
import time
import sys
import os
import signal

def main():
    print("Starting WeatherAI Backend (FastAPI)...")
    
    # We need to set PYTHONPATH so that backend.app can be imported
    env = os.environ.copy()
    env["PYTHONPATH"] = os.path.abspath(os.path.dirname(__file__))
    
    backend_process = subprocess.Popen(
        [sys.executable, "backend/app/main.py"],
        env=env
    )
    
    # Wait for backend to start up
    time.sleep(3)
    
    print("Starting WeatherAI Frontend (Streamlit)...")
    frontend_process = subprocess.Popen(
        [sys.executable, "-m", "streamlit", "run", "frontend/app.py", "--server.port", "8000"]
    )
    
    try:
        frontend_process.wait()
    except KeyboardInterrupt:
        print("\nShutting down services...")
        backend_process.send_signal(signal.SIGTERM)
        frontend_process.send_signal(signal.SIGTERM)
        
if __name__ == "__main__":
    main()
