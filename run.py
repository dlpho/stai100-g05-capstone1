import sys
import os
import subprocess
import time
import urllib.request
import json

# Bypass all proxy settings for local requests
os.environ['no_proxy'] = '*'

def find_venv_exec(name):
    is_windows = os.name == 'nt'
    bin_dir = 'Scripts' if is_windows else 'bin'
    ext = '.exe' if is_windows else ''
    path = os.path.join('.venv', bin_dir, f"{name}{ext}")
    if os.path.exists(path):
        return path
    return name  # fallback to system command

def wait_for_backend(url, timeout=15):
    print("Waiting for FastAPI backend to start...")
    start_time = time.time()
    last_error = None
    while time.time() - start_time < timeout:
        try:
            with urllib.request.urlopen(url, timeout=2) as response:
                if response.status == 200:
                    data = json.loads(response.read().decode())
                    if data.get("status") == "ok":
                        print("Backend is healthy!")
                        return True
        except Exception as e:
            last_error = e
        time.sleep(1)
    
    if last_error:
        print(f"Connection diagnosis: {last_error}")
    return False

def main():
    python_exec = find_venv_exec("python")
    streamlit_exec = find_venv_exec("streamlit")
    
    backend_url = "http://127.0.0.1:7860/health"
    
    # Start backend
    print("Starting FastAPI backend...")
    backend_proc = subprocess.Popen([python_exec, "app/main.py"])
    
    try:
        if not wait_for_backend(backend_url):
            print("Error: Backend failed to start or did not respond to health check.")
            backend_proc.terminate()
            sys.exit(1)
            
        # Start frontend (Streamlit)
        print("Starting Streamlit frontend on port 8000...")
        # streamlit run ui/chat_app.py --server.port 8000
        subprocess.run([streamlit_exec, "run", "ui/chat_app.py", "--server.port", "8000"])
        
    except KeyboardInterrupt:
        print("\nShutting down services...")
    finally:
        print("Terminating backend process...")
        backend_proc.terminate()
        try:
            backend_proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            backend_proc.kill()
        print("Done.")

if __name__ == "__main__":
    main()
