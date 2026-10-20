#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
[ -x .venv/bin/uvicorn ] || { echo "Corré primero ./run.sh (crea el entorno) o: python3 -m venv .venv && .venv/bin/pip install -r backend/requirements-dev.txt" >&2; exit 1; }
trap 'kill 0' EXIT
.venv/bin/uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8765 --reload &
(cd frontend && npm run dev)
