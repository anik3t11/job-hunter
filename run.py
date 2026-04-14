#!/usr/bin/env python3
"""
Job Hunter — entry point.
Run with: python run.py
"""
import subprocess
import sys
import os
import webbrowser
import threading
import time


def install_requirements():
    req_path = os.path.join(os.path.dirname(__file__), "requirements.txt")
    print("Checking dependencies...")
    subprocess.check_call(
        [sys.executable, "-m", "pip", "install", "-r", req_path, "-q"]
    )
    print("Dependencies ready.")


def open_browser():
    time.sleep(2.0)
    webbrowser.open("http://localhost:8000")


if __name__ == "__main__":
    install_requirements()

    # Thread to open browser after server starts
    t = threading.Thread(target=open_browser, daemon=True)
    t.start()

    print("\n🎯 Job Hunter starting at http://localhost:8000\n")
    print("Press Ctrl+C to stop.\n")

    import uvicorn
    uvicorn.run(
        "backend.main:app",
        host="0.0.0.0",
        port=8000,
        reload=False,
        log_level="warning",
    )
