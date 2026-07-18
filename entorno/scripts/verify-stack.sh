#!/usr/bin/env bash
# Verifica que TODOS los servicios del stack esten operativos antes de correr el Walking Skeleton (acta D24).
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
FAIL=0
ok(){ echo "  [ OK ] $1"; }
bad(){ echo "  [FAIL] $1"; FAIL=1; }

echo "==> Verificacion del stack de AURA"

# venv + libs
if [ -x "$HERE/../.venv/bin/python" ]; then
  PY="$HERE/../.venv/bin/python"
else PY="python3"; fi
for m in nats faster_whisper qdrant_client; do
  $PY -c "import $m" 2>/dev/null && ok "python: $m importable" || bad "python: $m NO importable (pip install)"
done

# NATS
NATSBIN="$(command -v nats-server || echo "$HERE/../.bin/nats-server")"
if [ -x "$NATSBIN" ] || command -v nats-server >/dev/null; then ok "nats-server disponible"; else bad "nats-server no encontrado"; fi
if (exec 3<>/dev/tcp/127.0.0.1/4222) 2>/dev/null; then ok "NATS escuchando en :4222"; exec 3>&- ; else echo "  [WARN] NATS no esta corriendo (arrancalo: nats-server -p 4222)"; fi

# Ollama
if command -v ollama >/dev/null; then
  ok "ollama instalado"
  if curl -fsS http://127.0.0.1:11434/api/tags >/dev/null 2>&1; then
    ok "Ollama respondiendo en :11434"
    MODELS=$(curl -fsS http://127.0.0.1:11434/api/tags | grep -o '"name"' | wc -l)
    [ "$MODELS" -gt 0 ] && ok "Ollama tiene $MODELS modelo(s)" || bad "Ollama sin modelos (ollama pull qwen2.5:3b)"
  else bad "Ollama no responde (arrancalo: ollama serve)"; fi
else bad "ollama no instalado"; fi

echo "==> RESULTADO: $([ $FAIL -eq 0 ] && echo 'STACK OPERATIVO — listo para el Walking Skeleton' || echo 'FALTAN COMPONENTES (ver arriba)')"
exit $FAIL
