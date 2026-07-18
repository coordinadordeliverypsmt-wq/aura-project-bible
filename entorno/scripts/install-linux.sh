#!/usr/bin/env bash
# Instalacion del stack real de AURA en Linux (local-first, open source — acta D24).
# Idempotente donde es posible. No requiere claves de terceros.
set -euo pipefail
NATS_VER="v2.10.22"
MODEL="${AURA_LLM_MODEL:-qwen2.5:3b}"
HERE="$(cd "$(dirname "$0")" && pwd)"
echo "==> AURA :: instalacion de stack (Linux)"

echo "==> 1/5 Python venv + dependencias"
python3 -m venv "$HERE/../.venv" 2>/dev/null || true
# shellcheck disable=SC1091
source "$HERE/../.venv/bin/activate"
pip install -q --upgrade pip
pip install -q -r "$HERE/requirements-stack.txt"

echo "==> 2/5 NATS server ($NATS_VER)"
if ! command -v nats-server >/dev/null && [ ! -x "$HERE/../.bin/nats-server" ]; then
  mkdir -p "$HERE/../.bin"
  ARCH=$(uname -m); case "$ARCH" in x86_64) A=amd64;; aarch64|arm64) A=arm64;; *) A=amd64;; esac
  curl -fsSL "https://github.com/nats-io/nats-server/releases/download/$NATS_VER/nats-server-$NATS_VER-linux-$A.tar.gz" -o /tmp/nats.tgz
  tar xzf /tmp/nats.tgz -C /tmp && cp /tmp/nats-server-*/nats-server "$HERE/../.bin/nats-server" && chmod +x "$HERE/../.bin/nats-server"
fi

echo "==> 3/5 Ollama (runtime LLM local, ADR-0010)"
if ! command -v ollama >/dev/null; then
  curl -fsSL https://ollama.com/install.sh | sh
fi

echo "==> 4/5 Descargar modelo LLM: $MODEL (~2-4 GB, la descarga mas grande)"
ollama pull "$MODEL"

echo "==> 5/5 Modelos STT/TTS se descargan al primer uso (faster-whisper base, voz Piper es)."
echo "==> LISTO. Verifica con: bash $HERE/verify-stack.sh"
