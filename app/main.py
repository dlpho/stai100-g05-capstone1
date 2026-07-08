import os
import sys
import uvicorn

if __name__ == "__main__":
    # Ensure correct python path for submodules
    current_dir = os.path.dirname(os.path.abspath(__file__))
    if current_dir not in sys.path:
        sys.path.append(current_dir)
        
    print("Starting Weather AI Assistant FastAPI Backend...")
    # Port is 7860 as configured in front-end connectors
    uvicorn.run("api:app", host="0.0.0.0", port=7860, reload=False)
