#!/usr/bin/env bash
# Se ejecuta EN EL NODO (lo invoca desplegar-nodo.sh por SSH). Registra el agente bajo runit.
#
# Con sudo sin contraseña: servicio de sistema /etc/sv/aura-nodo (arranca con el equipo, como cualquier
# servicio runit de antiX), ejecutado como el usuario sin privilegios mediante chpst.
# Sin sudo: runsvdir de USUARIO en ~/.aura-nodo/servicios, arrancado por `@reboot` en la crontab del
# usuario. Ambos son runit; ninguno usa systemd ni contenedores. Idempotente.
set -euo pipefail

USUARIO="$(id -un)"
DATOS="$HOME/.aura-nodo"
umask 077

escribir_servicio() {   # $1 = directorio del servicio; $2 = prefijo de ejecución (chpst o vacío)
  local sv="$1" pre="$2"
  mkdir -p "$sv/log"
  cat > "$sv/run" <<EOF
#!/bin/sh
exec 2>&1
cd "$DATOS/app" || exit 1
exec $pre env HOME="$HOME" AURA_NODO_DATOS="$DATOS" python3 -m aura_skeleton.nodo_agente
EOF
  mkdir -p "$DATOS/log"
  # svlogd rota: 3 ficheros de 1 MB como máximo. Solo eventos del agente, nunca audio ni imágenes.
  printf 's1000000\nn3\n' > "$DATOS/log/config"
  cat > "$sv/log/run" <<EOF
#!/bin/sh
exec $pre svlogd -tt "$DATOS/log"
EOF
  chmod 755 "$sv/run" "$sv/log/run"
}

if sudo -n true 2>/dev/null; then
  MODO=sistema
  TMP="$(mktemp -d)"
  escribir_servicio "$TMP/aura-nodo" "chpst -u $USUARIO"
  sudo -n rm -rf /etc/sv/aura-nodo
  sudo -n cp -r "$TMP/aura-nodo" /etc/sv/aura-nodo
  sudo -n chown -R root:root /etc/sv/aura-nodo
  sudo -n chmod 755 /etc/sv/aura-nodo /etc/sv/aura-nodo/log
  rm -rf "$TMP"
  [ -e /etc/service/aura-nodo ] || sudo -n ln -s /etc/sv/aura-nodo /etc/service/aura-nodo
  sleep 6; sudo -n sv restart aura-nodo >/dev/null 2>&1 || true
  sudo -n sv status aura-nodo
else
  MODO=usuario
  escribir_servicio "$DATOS/sv/aura-nodo" ""
  mkdir -p "$DATOS/servicios"
  [ -e "$DATOS/servicios/aura-nodo" ] || ln -s "$DATOS/sv/aura-nodo" "$DATOS/servicios/aura-nodo"
  LINEA="@reboot /usr/bin/runsvdir -P $DATOS/servicios"
  # Con pipefail, un `grep -v` sin líneas que conservar devuelve 1 y abortaría ANTES de añadir la nuestra
  # (hallazgo M-4 de la auditoría). Se construye en un fichero y solo se instala si no está vacío.
  CRON="$(mktemp)"
  { crontab -l 2>/dev/null || true; } | { grep -vF "$DATOS/servicios" || true; } > "$CRON"
  echo "$LINEA" >> "$CRON"
  [ -s "$CRON" ] && crontab "$CRON"
  rm -f "$CRON"
  # Arranca el runsvdir ahora si no corre ya (sin pgrep -f: comparamos la línea de órdenes exacta; la
  # salida de ps se captura entera antes de buscar, para que un SIGPIPE no dé un falso «no corre»).
  PROCESOS="$(ps -u "$USUARIO" -o args=)"
  if ! grep -qxF "runsvdir -P $DATOS/servicios" <<< "$PROCESOS"; then
    nohup /usr/bin/runsvdir -P "$DATOS/servicios" >/dev/null 2>&1 &
  fi
  sleep 6; SVDIR="$DATOS/servicios" sv restart aura-nodo >/dev/null 2>&1 || true
  SVDIR="$DATOS/servicios" sv status aura-nodo
fi
echo "runit: modo $MODO"
