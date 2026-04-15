#!/bin/bash
cd /Users/Aniket/Desktop/Experiments/job-hunter
exec python3 -m uvicorn backend.main:app --host 0.0.0.0 --port 8000
