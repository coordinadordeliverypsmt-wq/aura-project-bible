#!/usr/bin/env bash
# Despliega (o actualiza) el agente de nodo de AURA en un equipo remoto por SSH (DP-NODO-01 §5).
#
#   entorno/nodos/desplegar-nodo.sh USUARIO@HOST [NOMBRE_HUMANO]
#
# SSH es SOLO el canal de administración: copia código, crea la identidad y entrega la credencial. El
# runtime del nodo habla con HC-1 por NATS+TLS (ADR-0018). Reproducible e idempotente; se revierte con
# retirar-nodo.sh. Requiere haber ejecutado antes `red_hc1.py preparar` en HC-1.
#
# Variables: AURA_NODO_CLAVE (clave SSH de administración, por defecto ~/.ssh/aura_nodo01),
#            AURA_RED (material de red en HC-1, por defecto ~/.aura-red).
set -euo pipefail

DESTINO="${1:?uso: desplegar-nodo.sh USUARIO@HOST [NOMBRE]}"
NOMBRE="${2:-nodo-01}"
CLAVE="${AURA_NODO_CLAVE:-$HOME/.ssh/aura_nodo01}"
RED="${AURA_RED:-$HOME/.aura-red}"
AQUI="$(cd "$(dirname "$0")" && pwd)"
WS="$(cd "$AQUI/../../walking-skeleton" && pwd)"
[[ "$DESTINO" != -* ]] || { echo "destino inválido" >&2; exit 1; }
SSH=(ssh -i "$CLAVE" -o IdentitiesOnly=yes -o BatchMode=yes -o ConnectTimeout=10 -- "$DESTINO")

[ -f "$RED/pki/ca.crt" ] || { echo "falta $RED/pki/ca.crt: ejecuta red_hc1.py preparar" >&2; exit 1; }

# 1) Paquete: SOLO los módulos que el agente importa + nats-py (sin dependencias). Ni LLM, ni voz, ni Core.
PAQ="$(mktemp -d)"; trap 'rm -rf "$PAQ"' EXIT
python3 "$AQUI/empaquetar_nodo.py" "$WS" "$PAQ/app"
tar -C "$PAQ" -czf "$PAQ/app.tgz" app

# 2) Copia e instalación en espacio de usuario (~/.aura-nodo/app). La versión anterior se conserva hasta
#    que la nueva está completa: el cambio es un rename.
"${SSH[@]}" 'umask 077; mkdir -p ~/.aura-nodo && rm -rf ~/.aura-nodo/app.nueva && mkdir ~/.aura-nodo/app.nueva'
"${SSH[@]}" 'tar -xzf - -C ~/.aura-nodo/app.nueva --strip-components=1' < "$PAQ/app.tgz"
"${SSH[@]}" 'rm -rf ~/.aura-nodo/app.vieja; [ -d ~/.aura-nodo/app ] && mv ~/.aura-nodo/app ~/.aura-nodo/app.vieja; mv ~/.aura-nodo/app.nueva ~/.aura-nodo/app'

# 3) Identidad: la crea EL NODO (persistente, independiente de IP/hostname) y HC-1 solo la lee.
NODO_ID="$("${SSH[@]}" 'cd ~/.aura-nodo/app && AURA_NODO_DATOS=~/.aura-nodo python3 -m aura_skeleton.nodo_agente --identidad')"
[[ "$NODO_ID" =~ ^[0-9a-f]{32}$ ]] || { echo "identidad inválida devuelta por el nodo" >&2; exit 1; }
echo "nodo_id: $NODO_ID"

# 4) Alta en NATS y entrega de la credencial por la tubería SSH (nunca en disco intermedio ni en argv).
python3 "$AQUI/red_hc1.py" alta "$NODO_ID" | python3 -c 'import json,sys; sys.stdout.write(json.load(sys.stdin)["password"])' \
  | "${SSH[@]}" 'umask 077; cat > ~/.aura-nodo/credencial.tmp && mv ~/.aura-nodo/credencial.tmp ~/.aura-nodo/credencial'
"${SSH[@]}" 'umask 077; cat > ~/.aura-nodo/ca.crt' < "$RED/pki/ca.crt"
systemctl --user reload aura-nats.service   # SIGHUP: recarga usuarios sin cortar a los demás nodos

# 5) Configuración: servidores por NOMBRE mDNS primero; la IP actual es solo respaldo (configuración, no identidad).
HOST_HC1="$(hostname).local"
IP_HC1="$(ip -4 route get "${DESTINO#*@}" | sed -n 's/.* src \([0-9.]*\).*/\1/p')"
python3 - "$NODO_ID" "$NOMBRE" "$HOST_HC1" "$IP_HC1" <<'PY' | "${SSH[@]}" 'umask 077; cat > ~/.aura-nodo/nodo.conf'
import json, sys
nodo_id, nombre, host, ip = sys.argv[1:5]
print(json.dumps({"usuario": f"nodo-{nodo_id}", "nombre": nombre, "intervalo_s": 10,
                  "servidores": [f"tls://{host}:4222"] + ([f"tls://{ip}:4222"] if ip else [])}, indent=1))
PY

# 6) Supervisión por runit (sin systemd, sin contenedores).
"${SSH[@]}" 'bash -s' < "$AQUI/instalar-runit-nodo.sh"
echo "desplegado: $DESTINO ($NOMBRE, $NODO_ID)"
