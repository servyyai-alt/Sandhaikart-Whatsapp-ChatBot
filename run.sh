#!/bin/bash
set -e

if [ -d "venv" ]; then
  source venv/bin/activate
fi

PORT="${PORT:-8000}"
uvicorn app.main:app --host 0.0.0.0 --port "$PORT"
