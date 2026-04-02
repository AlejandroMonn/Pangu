#!/usr/bin/env bash
set -euo pipefail

MODEL="${1:-qwen3:8b}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

pkill -f "uvicorn main:app --host 0.0.0.0 --port 8000" >/dev/null 2>&1 || true
source "$HOME/.venvs/manager/bin/activate"
cd "$PROJECT_DIR"
nohup env OLLAMA_MODEL="$MODEL" uvicorn main:app --host 0.0.0.0 --port 8000 >/tmp/chaos-triage.log 2>&1 < /dev/null &
