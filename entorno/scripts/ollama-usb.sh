#!/usr/bin/env bash
# Lanzador de Ollama con guardarrail de almacenamiento (acta D27).
# Se NIEGA a arrancar si el directorio de modelos no reside fisicamente en el USB.
# Una variable de entorno no es una garantia: /media/.../AURORA_EXT existe
# igual con el USB desmontado, y en ese caso Ollama escribe en el disco interno.
set -uo pipefail
USB_LABEL="AURORA_EXT"
MODELS="/media/$USER/AURORA_EXT/ollama_models"

USB_DEV="$(lsblk -nro PATH,LABEL | awk -v l="$USB_LABEL" '$2==l{print $1; exit}')"
[ -z "$USB_DEV" ] && { echo "ABORTADO: el USB '$USB_LABEL' no esta conectado."; exit 1; }
mountpoint -q "/media/$USER/AURORA_EXT" || { echo "ABORTADO: el USB no esta montado en /media/$USER/AURORA_EXT."; exit 1; }
DEV_MODELS="$(df --output=source "$MODELS" 2>/dev/null | tail -1)"
[ "$DEV_MODELS" = "$USB_DEV" ] || { echo "ABORTADO: '$MODELS' reside en $DEV_MODELS, no en el USB ($USB_DEV)."; exit 1; }
[ -w "$MODELS" ] || { echo "ABORTADO: '$MODELS' no es escribible por $USER."; exit 1; }

echo "Guardarrail OK: modelos en $USB_DEV. Arrancando Ollama."
export OLLAMA_MODELS="$MODELS"
exec ollama serve
