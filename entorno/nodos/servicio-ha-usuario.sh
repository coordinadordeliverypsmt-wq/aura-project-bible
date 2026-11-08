#!/usr/bin/env bash
# Home Assistant de AURA como servicio de USUARIO de systemd, para que vuelva solo tras reiniciar HC-1.
# Medido 2026-10-04 y 2026-10-07: HA corre a mano (nohup, ~/aura-hogar/ha.pid) y NO arranca con el equipo; tras un
# reinicio la vía voz→TV quedaba muerta hasta relanzarlo a mano. Mismo patrón que instalar-hc1.sh (linger ya activo).
#
# Uso: servicio-ha-usuario.sh instalar   escribe la unidad y la HABILITA para el próximo arranque. NO la arranca: si HA ya
#                                        corre a mano, lanzar otra instancia chocaría en el puerto 8123.
#      servicio-ha-usuario.sh retirar    deshabilita y borra la unidad (HA vuelve a ser manual). Reversible.
# Sin sudo. Idempotente.
set -euo pipefail

HOGAR="${AURA_HOGAR:-$HOME/aura-hogar}"
UNIDADES="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user"
UNIDAD="$UNIDADES/aura-hogar-ha.service"

case "${1:-}" in
  instalar)
    [[ -x "$HOGAR/ha-venv/bin/hass" ]] || { echo "no existe $HOGAR/ha-venv/bin/hass (instalar-ha.sh)" >&2; exit 1; }
    [[ -d "$HOGAR/config" ]] || { echo "no existe $HOGAR/config" >&2; exit 1; }
    mkdir -p "$UNIDADES"
    cat > "$UNIDAD.nuevo" <<EOF
[Unit]
Description=AURA — Home Assistant local (hogar: TV de la sala)
After=network-online.target

[Service]
WorkingDirectory=$HOGAR
ExecStart=$HOGAR/ha-venv/bin/hass -c $HOGAR/config
Restart=on-failure
RestartSec=10

[Install]
WantedBy=default.target
EOF
    mv -f "$UNIDAD.nuevo" "$UNIDAD"
    systemd-analyze --user verify "$UNIDAD"
    systemctl --user daemon-reload
    systemctl --user enable aura-hogar-ha.service
    echo "instalada y habilitada (arrancará en el próximo arranque): $UNIDAD"
    ;;
  retirar)
    systemctl --user disable aura-hogar-ha.service 2>/dev/null || true
    rm -f "$UNIDAD"
    systemctl --user daemon-reload
    echo "retirada: Home Assistant vuelve a ser manual"
    ;;
  *) echo "uso: $0 instalar|retirar" >&2; exit 2 ;;
esac
