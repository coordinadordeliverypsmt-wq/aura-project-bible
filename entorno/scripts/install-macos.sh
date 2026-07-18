#!/usr/bin/env bash
# Instalacion del stack real de AURA en macOS (local-first — acta D24). Requiere Homebrew.
set -euo pipefail
MODEL="${AURA_LLM_MODEL:-qwen2.5:3b}"
HERE="$(cd "$(dirname "$0")" && pwd)"
echo "==> AURA :: instalacion de stack (macOS)"
command -v brew >/dev/null || { echo "Instala Homebrew primero: https://brew.sh"; exit 1; }

echo "==> 1/4 Python venv + dependencias"
python3 -m venv "$HERE/../.venv" 2>/dev/null || true
source "$HERE/../.venv/bin/activate"
pip install -q --upgrade pip && pip install -q -r "$HERE/requirements-stack.txt"

echo "==> 2/4 NATS server"
command -v nats-server >/dev/null || brew install nats-server

echo "==> 3/4 Ollama (ADR-0010)"
command -v ollama >/dev/null || brew install ollama
brew services start ollama 2>/dev/null || (ollama serve >/dev/null 2>&1 &)

echo "==> 4/4 Modelo LLM: $MODEL"
ollama pull "$MODEL"
echo "==> LISTO. Verifica con: bash $HERE/verify-stack.sh"
