#!/usr/bin/env bash
# Rollback de desplegar-nodo.sh: detiene y quita el servicio runit del nodo y revoca su usuario en NATS.
# La IDENTIDAD del nodo (~/.aura-nodo/nodo/identidad.json) se conserva salvo --borrar-identidad: borrarla
# convertiría el equipo en «otro nodo» al volver a desplegarlo.
#
#   entorno/nodos/retirar-nodo.sh USUARIO@HOST [--borrar-identidad]
set -euo pipefail
DESTINO="${1:?uso: retirar-nodo.sh USUARIO@HOST [--borrar-identidad]}"
CLAVE="${AURA_NODO_CLAVE:-$HOME/.ssh/aura_nodo01}"
AQUI="$(cd "$(dirname "$0")" && pwd)"
[[ "$DESTINO" != -* ]] || { echo "destino inválido" >&2; exit 1; }
SSH=(ssh -i "$CLAVE" -o IdentitiesOnly=yes -o BatchMode=yes -o ConnectTimeout=10 -- "$DESTINO")

NODO_ID="$("${SSH[@]}" 'python3 -c "import json,os;print(json.load(open(os.path.expanduser(\"~/.aura-nodo/nodo/identidad.json\")))[\"nodo_id\"])"' 2>/dev/null || true)"
"${SSH[@]}" 'bash -s' <<'EOF'
set -u
if sudo -n true 2>/dev/null && [ -e /etc/service/aura-nodo ]; then
  sudo -n rm -f /etc/service/aura-nodo; sleep 6; sudo -n rm -rf /etc/sv/aura-nodo
fi
if [ -e ~/.aura-nodo/servicios/aura-nodo ]; then
  SVDIR=~/.aura-nodo/servicios sv down aura-nodo 2>/dev/null
  rm -f ~/.aura-nodo/servicios/aura-nodo
  crontab -l 2>/dev/null | grep -vF ".aura-nodo/servicios" | crontab -
fi
rm -rf ~/.aura-nodo/app ~/.aura-nodo/app.vieja ~/.aura-nodo/sv ~/.aura-nodo/credencial ~/.aura-nodo/nodo.conf
echo "nodo: servicio y código retirados"
EOF
if [ -n "$NODO_ID" ]; then python3 "$AQUI/red_hc1.py" baja "$NODO_ID"; systemctl --user reload aura-nats.service; fi
if [ "${2:-}" = "--borrar-identidad" ]; then "${SSH[@]}" 'rm -rf ~/.aura-nodo'; echo "identidad borrada"; fi
