#!/usr/bin/env bash
# Rollback de instalar-hc1.sh: para y elimina los dos servicios de usuario. El material de red (~/.aura-red:
# CA, credenciales, registro) se CONSERVA salvo que se pase --borrar-datos (no se destruye sin pedirlo).
set -euo pipefail
UNIDADES="$HOME/.config/systemd/user"
RED="${AURA_RED:-$HOME/.aura-red}"
systemctl --user disable --now aura-receptor-nodos.service aura-nats.service 2>/dev/null || true
rm -f "$UNIDADES/aura-receptor-nodos.service" "$UNIDADES/aura-nats.service"
systemctl --user daemon-reload
if [ "${1:-}" = "--borrar-datos" ]; then rm -rf "$RED"; echo "borrado $RED"; fi
echo "HC-1: servicios de red de AURA retirados"
