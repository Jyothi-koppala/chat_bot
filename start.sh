#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"

PYTHON=""
if command -v python3.11 >/dev/null 2>&1; then
  PYTHON="python3.11"
elif command -v python3 >/dev/null 2>&1; then
  PYTHON="python3"
else
  echo "ERROR: Python 3.11+ not found."
  exit 1
fi

command -v node >/dev/null 2>&1 || { echo "ERROR: Node.js 18+ not found."; exit 1; }
command -v npm >/dev/null 2>&1 || { echo "ERROR: npm not found."; exit 1; }
command -v ollama >/dev/null 2>&1 || { echo "ERROR: Ollama not found."; exit 1; }

if [ ! -f backend/.venv/bin/python ]; then
  echo "> Creating Python virtual environment..."
  "$PYTHON" -m venv backend/.venv
fi

backend/.venv/bin/python -m pip install -q -r backend/requirements.txt

if [ ! -f backend/.env ]; then
  cp backend/.env.example backend/.env
fi

mkdir -p pdf

if ! ollama list >/dev/null 2>&1; then
  echo "> Ollama is not responding. Start Ollama and retry."
  exit 1
fi

if ! ollama list | grep -qi '^llama3.2'; then
  ollama pull llama3.2
fi

if [ ! -d frontend/node_modules ]; then
  (cd frontend && npm install)
fi
(cd frontend && npm run build)

cd backend
exec .venv/bin/python -m uvicorn main:app --host 0.0.0.0 --port 8000
