#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

find_python() {
  for c in "${PYTHON:-}" python3.13 python3.12 python3.11 python3.10 python3; do
    [ -n "$c" ] && command -v "$c" >/dev/null 2>&1 \
      && "$c" -c 'import sys; sys.exit(sys.version_info < (3, 10))' 2>/dev/null \
      && { command -v "$c"; return 0; }
  done
  return 1
}

if [ ! -x .venv/bin/uvicorn ]; then
  PY=$(find_python) || { echo "Hace falta Python 3.10 o superior (podés indicarlo con PYTHON=/ruta/python)." >&2; exit 1; }
  echo "Creando el entorno de Python (.venv)…"
  "$PY" -m venv .venv
  .venv/bin/pip install -q -r backend/requirements.txt
fi

if [ ! -f frontend/dist/index.html ]; then
  command -v npm >/dev/null 2>&1 || {
    echo "Falta compilar el frontend y no hay Node/npm. Instala Node 20+ y corré: (cd frontend && npm ci && npm run build)" >&2
    exit 1
  }
  echo "Compilando el frontend…"
  (cd frontend && npm ci --silent && npm run build --silent)
fi

HOST="${HOST:-127.0.0.1}"
if [ "$HOST" != "127.0.0.1" ] && [ "${AUTH_MODE:-none}" = "none" ]; then
  echo "⚠  Estas exponiendo el servidor en $HOST sin autenticación (AUTH_MODE=none):" >&2
  echo "   cualquiera que llegue aca es super admin. Integra OIDC antes de abrirlo a una red." >&2
fi
exec .venv/bin/uvicorn app.main:app --app-dir backend --host "$HOST" --port "${PORT:-8765}"
