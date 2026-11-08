#!/usr/bin/env bash
# Verificación TRAS REINICIO de HC-1 (RESULTADO-NODO-01 §5.2: «el arranque sin sesión no se ha observado»).
# SOLO LECTURA: no arranca, no para, no escribe nada fuera de su propio informe en stdout. No usa sudo.
#
# Uso:  entorno/nodos/verificar-tras-reinicio-hc1.sh [ARRANQUE_PREVIO]
#   ARRANQUE_PREVIO  salida de `who -b` / `uptime -s` ANTES de reiniciar (p.ej. "2026-10-04 04:24"). Si se da,
#                    se exige que el arranque actual sea posterior: así no se aprueba un «reinicio» que no ocurrió.
# Sale con 0 si todo lo exigible está bien; con 1 si algo falla (y dice qué).
set -uo pipefail

AQUI="$(cd "$(dirname "$0")" && pwd)"
RAIZ="$(cd "$AQUI/../.." && pwd)"
WS="$RAIZ/walking-skeleton"
RED="${AURA_RED:-$HOME/.aura-red}"
DATOS="${AURA_DATOS:-$HOME/.aura}"
HC1_MDNS="${HC1_MDNS:-$(hostname).local}"
FALLOS=0

ok()    { echo "  OK    $*"; }
falla() { echo "  FALLA $*"; FALLOS=$((FALLOS + 1)); }
aviso() { echo "  AVISO $*"; }

echo "== Verificación tras reinicio de HC-1 · $(date '+%F %T')"

arranque="$(uptime -s)"
echo "arranque actual (uptime -s): $arranque"
if [[ -n "${1:-}" ]]; then
  # A la misma precision (minuto): `who -b` da minutos y `uptime -s` segundos; comparar sin truncar daria por bueno
  # un «reinicio» dentro del mismo minuto que en realidad no ocurrio (medido al validar este script).
  if [[ "$(date -d "$(date -d "$arranque" '+%F %H:%M')" +%s)" -gt "$(date -d "$(date -d "$1" '+%F %H:%M')" +%s)" ]]; then
    ok "hubo reinicio: $1 -> $arranque"
  else falla "no consta reinicio: el arranque actual ($arranque) no es posterior a $1"; fi
fi

[[ "$(loginctl show-user "$USER" -p Linger --value 2>/dev/null)" == yes ]] && ok "linger activo (los servicios de usuario arrancan sin sesión)" || falla "linger desactivado"

for u in aura-nats.service aura-receptor-nodos.service; do
  activo="$(systemctl --user is-active "$u" 2>/dev/null)"; habil="$(systemctl --user is-enabled "$u" 2>/dev/null)"
  [[ "$activo" == active && "$habil" == enabled ]] && ok "$u: active/enabled" || falla "$u: $activo/$habil"
  desde="$(systemctl --user show "$u" -p ActiveEnterTimestamp --value 2>/dev/null)"
  [[ -n "$desde" ]] && echo "        activo desde: $desde"
done

if systemctl --user cat aura-hogar-ha.service >/dev/null 2>&1; then
  activo="$(systemctl --user is-active aura-hogar-ha.service 2>/dev/null)"
  [[ "$activo" == active ]] && ok "aura-hogar-ha.service: active" || falla "aura-hogar-ha.service: $activo"
else
  aviso "aura-hogar-ha.service no instalado: Home Assistant no arranca solo tras reiniciar"
fi
if (exec 3<>/dev/tcp/127.0.0.1/8123) 2>/dev/null; then ok "Home Assistant escucha en 127.0.0.1:8123"; else falla "Home Assistant no escucha en 8123"; fi

ss -ltn 2>/dev/null | grep -q ':4222 ' && ok "NATS escucha en 4222" || falla "NATS no escucha en 4222"

ip_mdns="$(cd "$WS" && python3 -c "
from aura_skeleton.adapters.resolutor_mdns import resolver_ipv4
print(resolver_ipv4('$HC1_MDNS') or '')" 2>/dev/null)"
ip_real="$(ip -4 -o addr show scope global | awk '{print $4}' | cut -d/ -f1 | head -1)"
[[ -n "$ip_mdns" && "$ip_mdns" == "$ip_real" ]] && ok "mDNS: $HC1_MDNS -> $ip_mdns (= IP real)" || falla "mDNS: '$ip_mdns' frente a IP real '$ip_real'"

# Latido NUEVO: la secuencia de nodo-01 tiene que crecer entre dos lecturas (un registro recargado no basta).
seq_de() { (cd "$WS" && AURA_RED="$RED" timeout 60 python3 -m aura_skeleton --nodos 2>/dev/null) | sed -n 's/.*secuencia \([0-9]*\).*/\1/p' | head -1; }
estado_nodo="$( (cd "$WS" && AURA_RED="$RED" timeout 60 python3 -m aura_skeleton --nodos 2>/dev/null) | grep -E 'nodo-01' | head -1)"
s1="$(seq_de)"; sleep 20; s2="$(seq_de)"
echo "        $estado_nodo"
[[ "$estado_nodo" == *ONLINE* ]] && ok "nodo-01 ONLINE" || falla "nodo-01 no está ONLINE"
[[ -n "$s1" && -n "$s2" && "$s2" -gt "$s1" ]] && ok "latido nuevo: secuencia $s1 -> $s2 en 20 s" || falla "sin latido nuevo (secuencia '$s1' -> '$s2')"

[[ -f "$RAIZ/entorno/control-plane/PARADA" ]] && ok "PARADA (a) del control-plane: armada (sin cambios)" || aviso "PARADA (a) NO está armada: ¿lo autorizó alguien?"
[[ -e "$DATOS/KILL" ]] && aviso "kill switch (b) $DATOS/KILL ARMADO" || ok "kill switch (b) sin armar (sin cambios)"

echo "== Resultado: $([[ $FALLOS -eq 0 ]] && echo PASS || echo "FAIL ($FALLOS)")"
[[ $FALLOS -eq 0 ]]
