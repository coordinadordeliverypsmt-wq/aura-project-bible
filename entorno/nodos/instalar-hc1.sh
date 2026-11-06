#!/usr/bin/env bash
# Prepara HC-1 para recibir nodos (DP-NODO-01 §5): PKI + nats.conf + dos servicios de USUARIO de systemd
# (HC-1 ya usa systemd; el NODO no). Idempotente. Se revierte con retirar-hc1.sh.
#
#   entorno/nodos/instalar-hc1.sh [RUTA_WALKING_SKELETON]
#
# El receptor ejecuta el código de la ruta indicada (por defecto, el walking-skeleton de este checkout).
set -euo pipefail

AQUI="$(cd "$(dirname "$0")" && pwd)"
WS="$(cd "${1:-$AQUI/../../walking-skeleton}" && pwd)"
RED="${AURA_RED:-$HOME/.aura-red}"
NATS_BIN="$(command -v nats-server || echo "$HOME/.local/bin/nats-server")"
UNIDADES="$HOME/.config/systemd/user"

[ -x "$NATS_BIN" ] || { echo "no se encuentra nats-server" >&2; exit 1; }
AURA_RED="$RED" python3 "$AQUI/red_hc1.py" preparar
"$NATS_BIN" -t -c "$RED/nats/nats.conf"

mkdir -p "$UNIDADES"
cat > "$UNIDADES/aura-nats.service" <<EOF
[Unit]
Description=AURA — bus de red NATS para nodos (ADR-0018, E2)

[Service]
ExecStart=$NATS_BIN -c $RED/nats/nats.conf
ExecReload=/bin/kill -HUP \$MAINPID
Restart=on-failure
RestartSec=2

[Install]
WantedBy=default.target
EOF

cat > "$UNIDADES/aura-receptor-nodos.service" <<EOF
[Unit]
Description=AURA — receptor de latidos de nodos
After=aura-nats.service
# Wants, NO Requires: con Requires, parar el bus paraba también el receptor y no volvía (medido en la
# prueba física 3, 2026-10-04). El receptor reconecta solo; solo necesita que se intente arrancar el bus.
Wants=aura-nats.service

[Service]
WorkingDirectory=$WS
Environment=AURA_RED=$RED
ExecStart=/usr/bin/python3 -m aura_skeleton --receptor-nodos
Restart=always
RestartSec=3

[Install]
WantedBy=default.target
EOF

systemctl --user daemon-reload
# Sin linger, los servicios de usuario solo arrancan al iniciar sesión: tras un reinicio de HC-1 sin sesión
# los nodos no tendrían a quién latir (hallazgo M-5). Se intenta activarlo; si la política lo impide, se dice.
if loginctl enable-linger "$USER" 2>/dev/null; then echo "linger: activado"; else
  echo "AVISO: no se pudo activar linger; tras reiniciar HC-1 la red de nodos espera al inicio de sesión" >&2; fi
systemctl --user enable --now aura-nats.service aura-receptor-nodos.service
sleep 2
systemctl --user --no-pager --lines=0 status aura-nats.service aura-receptor-nodos.service | grep -E "●|Active:"
