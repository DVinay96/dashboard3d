#!/usr/bin/env bash
# Levanta el dashboard en http://127.0.0.1:8765
cd "$(dirname "$0")"
exec python3 server.py
