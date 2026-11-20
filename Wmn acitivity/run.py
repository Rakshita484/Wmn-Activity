#!/usr/bin/env python3
import os
import sys
import subprocess
import shutil

# Determine root folder directories
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
VENV_DIR = os.path.join(ROOT_DIR, ".venv")

# Determine correct paths based on OS
if sys.platform == "win32":
    VENV_PIP = os.path.join(VENV_DIR, "Scripts", "pip.exe")
    VENV_PYTHON = os.path.join(VENV_DIR, "Scripts", "python.exe")
    VENV_UVICORN = os.path.join(VENV_DIR, "Scripts", "uvicorn.exe")
else:
    VENV_PIP = os.path.join(VENV_DIR, "bin", "pip")
    VENV_PYTHON = os.path.join(VENV_DIR, "bin", "python")
    VENV_UVICORN = os.path.join(VENV_DIR, "bin", "uvicorn")

def log(msg):
    print(f"\033[94m[5G-WMN-LAUNCHER]\033[0m {msg}")

def check_requirements():
    """Verify standard python3 and pip are available on system."""
    if not shutil.which("python3") and not shutil.which("python"):
        print("\033[91mError: Python3 is not installed or not in PATH.\033[0m")
        sys.exit(1)

def setup_virtualenv():
    """Initialize virtual environment if not present."""
    if not os.path.exists(VENV_DIR):
        log(f"Virtual environment not found. Creating at: {VENV_DIR}")
        subprocess.check_call([sys.executable, "-m", "venv", VENV_DIR])
        log("Virtual environment created successfully.")
    else:
        log("Virtual environment already exists.")

def install_dependencies():
    """Upgrade pip and install requirements."""
    log("Installing dependencies in virtual environment...")
    
    # Upgrade pip first
    subprocess.check_call([VENV_PYTHON, "-m", "pip", "install", "--upgrade", "pip"])
    
    # Install backend dependencies
    req_file = os.path.join(ROOT_DIR, "backend", "requirements.txt")
    subprocess.check_call([VENV_PIP, "install", "-r", req_file])
    log("Dependencies successfully installed.")

def initialize_database():
    """Seed initial network slices and physical router topologies."""
    log("Initializing & Seeding SQLite Database topology...")
    
    # Run the database seeder module using venv python interpreter
    # We must add current directory to PYTHONPATH so it finds app package correctly
    env = os.environ.copy()
    env["PYTHONPATH"] = ROOT_DIR
    
    # Execute database seeder script in database.py
    seed_cmd = [VENV_PYTHON, "-c", "from backend.app.database import init_db; init_db()"]
    subprocess.check_call(seed_cmd, cwd=ROOT_DIR, env=env)
    log("Database seed verify complete.")

def start_server():
    """Launch FastAPI application server."""
    log("Launching FastAPI and MCP Orchestration Server...")
    log("Open browser and navigate to: \033[92mhttp://localhost:8000\033[0m")
    
    env = os.environ.copy()
    env["PYTHONPATH"] = ROOT_DIR
    
    # Launch uvicorn
    # uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --reload
    uvicorn_cmd = [
        VENV_UVICORN, 
        "backend.app.main:app", 
        "--host", "0.0.0.0", 
        "--port", "8000",
        "--reload"
    ]
    
    try:
        subprocess.run(uvicorn_cmd, cwd=ROOT_DIR, env=env, check=True)
    except KeyboardInterrupt:
        log("Server stopped by user request.")

def main():
    print("=" * 60)
    print("  5G Wireless Mesh Slicing & MCP Management Server Launcher  ")
    print("=" * 60)
    
    check_requirements()
    setup_virtualenv()
    install_dependencies()
    initialize_database()
    start_server()

if __name__ == "__main__":
    main()
