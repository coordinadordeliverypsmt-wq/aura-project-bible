#!/bin/bash
# AURA por voz: Enter para hablar por el micrófono, la respuesta suena por el altavoz.
# Con --continuo AURA escucha siempre y acude al oír «Oye Aurora» (Bible 6.2: todo en local, sin disco).
# Campaña de presencia (CEO, 2026-09-26). Los modelos viven en la USB AURORA_EXT; nada se descarga.
# El hogar real es OPCIONAL: si hay un Home Assistant local con token, AURA lo usa; si no, lo dice.
set -euo pipefail
USB=/media/$USER/AURORA_EXT
[ -d "$USB" ] || { echo "AURA: falta la USB AURORA_EXT (voz Piper y modelo Whisper)."; exit 1; }
export AURA_STACK_REAL=1
export AURA_LLM_MODEL="${AURA_LLM_MODEL:-qwen2.5:0.5b}"
export AURA_PIPER_VOICE="$USB/piper_voices/es_MX-ald-medium.onnx"
export HF_HUB_CACHE="$USB/hf_cache/hub"
export HF_HUB_OFFLINE=1                      # local-first (D24): el modelo no se descarga nunca
export AURA_VOSK_MODEL="$USB/vosk-model-small-es-0.42"   # palabra de activación (--continuo)
if [ -r "$HOME/aura-hogar/secretos/ha_token" ]; then
  export AURA_HA_URL=http://127.0.0.1:8123
  AURA_HA_TOKEN=$(cat "$HOME/aura-hogar/secretos/ha_token"); export AURA_HA_TOKEN
fi
# Ganancia del micrófono MEDIDA (E2E físico 2026-10-04, `evidencia-voz-accion/diagnostico-stt-ganancia.json`): a 27 %
# la voz se transcribió 3/3; a 150 % la entrada quedaba recortada (74 % de muestras al tope en silencio) y nada se
# entendía. Algo ajeno a AURA la había subido: el lanzador la fija. Ajustable con AURA_GANANCIA_MICRO.
pactl set-source-volume @DEFAULT_SOURCE@ "${AURA_GANANCIA_MICRO:-27%}" 2>/dev/null || echo "AURA: no pude fijar la ganancia del micrófono"
cd "$(dirname "$0")/../../walking-skeleton"
exec python3 -m aura_skeleton --escuchar "$@"
