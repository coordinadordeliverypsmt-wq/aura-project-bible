#!/usr/bin/env bash
# Uso: validar_k.sh K MODO [args]   MODO: qg | cp | pytest <rutas relativas a walking-skeleton> | collect
# Valida la INSTANTÁNEA del commit HEAD exportada con git archive (no el worktree, que lo contiene todo).
set -uo pipefail
K="$1"; MODO="$2"; shift 2
W=/home/majo1230/Documentos/AURA/aura-project-bible/.claude/worktrees/m3-entry
L=/home/majo1230/.claude/jobs/d6cb894c/tmp/integracion
SHA=$(git -C "$W" rev-parse HEAD)
D=$(mktemp -d -p "$L" "export-$K-XXXX")
git -C "$W" archive "$SHA" | tar -x -C "$D"
LOG="$L/validacion-$K-$MODO.log"
echo "commit $K $SHA exportado en $D" > "$LOG"
case "$MODO" in
  qg)      ( cd "$D/walking-skeleton" && timeout 3000 ./quality-gate.sh ) >> "$LOG" 2>&1; RC=$? ;;
  cpdatos) cp "$W/entorno/control-plane/estado.json" "$W/entorno/control-plane/eventos.jsonl" "$D/entorno/control-plane/"
           ( cd "$D/entorno/control-plane" && AURA_AUTOCONSTRUCCION_ESTADO=$(mktemp -d -p "$L") \
             timeout 1500 python3 -m pytest -q -p no:cacheprovider ) >> "$LOG" 2>&1; RC=$? ;;
  cp)      ( cd "$D/entorno/control-plane" && AURA_AUTOCONSTRUCCION_ESTADO=$(mktemp -d -p "$L") \
             timeout 1500 python3 -m pytest -q -p no:cacheprovider ) >> "$LOG" 2>&1; RC=$? ;;
  pytest)  ( cd "$D/walking-skeleton" && timeout 1500 python3 -m pytest -q -p no:cacheprovider "$@" ) >> "$LOG" 2>&1; RC=$? ;;
  collect) ( cd "$D/walking-skeleton" && python3 -m pytest --collect-only -q -p no:cacheprovider | tail -1
             cd "$D/entorno/control-plane" && python3 -m pytest --collect-only -q -p no:cacheprovider | tail -1 ) >> "$LOG" 2>&1; RC=$? ;;
esac
echo "RC=$RC" >> "$LOG"
echo "== validación commit $K ($MODO) RC=$RC"; grep -E "passed|failed|error|QUALITY GATE|^FAILED|^ERROR" "$LOG" | tail -12
rm -rf "$D"
