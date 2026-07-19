#!/usr/bin/env bash
# Preparacion del USB secundario + liberacion de espacio interno (acta D31).
# EJECUTAR CON SUDO:  sudo ./liberar-recursos.sh
# Cada bloque verifica antes de actuar. Nada destructivo sin comprobacion previa.
set -uo pipefail
[ "$(id -u)" -eq 0 ] || { echo "Ejecutar con sudo."; exit 1; }
USUARIO="${SUDO_USER:-majo1230}"

echo "=========================================================="
echo " 1. FORMATEO DEL USB SECUNDARIO -> ext4, etiqueta AURORA_BAK"
echo "=========================================================="
# Seguridad: localizar por ETIQUETA actual, nunca por /dev/sdX (el reboot los renombra).
DEV="$(lsblk -nro PATH,LABEL | awk '$2=="EDILBERTO"{print $1; exit}')"
if [ -z "$DEV" ]; then
  echo "  [SALTADO] No se encuentra ningun dispositivo con etiqueta EDILBERTO."
  echo "            (Si ya lo formateaste, es lo esperado.)"
else
  SZ_B=$(blockdev --getsize64 "$DEV" 2>/dev/null || echo 0)
  SZ_G=$(( SZ_B / 1000000000 ))
  ROOT_DEV="$(findmnt -nro SOURCE /)"
  # Triple verificacion: no es el disco raiz, no es AURORA_EXT, y el tamano cuadra (~4 GB)
  if [ "$DEV" = "$ROOT_DEV" ]; then echo "  [ABORTADO] $DEV es el disco raiz."; exit 1; fi
  if lsblk -nro LABEL "$DEV" | grep -q AURORA_EXT; then echo "  [ABORTADO] $DEV es el USB principal."; exit 1; fi
  if [ "$SZ_G" -gt 6 ]; then echo "  [ABORTADO] $DEV mide ${SZ_G}GB, se esperaba ~4GB."; exit 1; fi
  echo "  Dispositivo: $DEV (${SZ_G} GB, etiqueta EDILBERTO)  -> verificado"
  umount "$DEV" 2>/dev/null
  mkfs.ext4 -F -L AURORA_BAK "$DEV" >/dev/null 2>&1 && echo "  [OK] Formateado a ext4 con etiqueta AURORA_BAK"
  mkdir -p /media/"$USUARIO"/AURORA_BAK
  # Se comprueba el PUNTO DE MONTAJE, no el identificador: una entrada previa por UUID
  # apunta al mismo destino y anadir otra por LABEL genera un montaje duplicado en el arranque.
  if grep -qE "^[^#]*[[:space:]]/media/$USUARIO/AURORA_BAK[[:space:]]" /etc/fstab; then
    echo "  [OK] /media/$USUARIO/AURORA_BAK ya configurado en fstab (no se duplica)"
  else
    echo 'LABEL=AURORA_BAK /media/'"$USUARIO"'/AURORA_BAK ext4 defaults,nofail,x-systemd.device-timeout=10 0 2' >> /etc/fstab
  fi
  mount -a 2>/dev/null
  chown "$USUARIO":"$USUARIO" /media/"$USUARIO"/AURORA_BAK 2>/dev/null
  sudo -u "$USUARIO" mkdir -p /media/"$USUARIO"/AURORA_BAK/{backups,snapshots,logs,benchmarks,exportaciones,validacion}
  echo "  [OK] Montaje persistente por ETIQUETA + estructura creada"
fi

echo ""
echo "=========================================================="
echo " 2. MONTAJE PERSISTENTE DEL USB PRINCIPAL"
echo "=========================================================="
# Igual que arriba: se comprueba el destino, no el identificador. UUID y LABEL son
# ambos estables frente al renombrado sda->sdb; lo que rompe el arranque es tener DOS
# entradas para el mismo punto de montaje.
if grep -qE "^[^#]*[[:space:]]/media/$USUARIO/AURORA_EXT[[:space:]]" /etc/fstab; then
  echo "  [OK] Ya configurado en /etc/fstab (no se duplica)"
else
  echo 'LABEL=AURORA_EXT /media/'"$USUARIO"'/AURORA_EXT ext4 defaults,nofail,x-systemd.device-timeout=10 0 2' >> /etc/fstab
  echo "  [OK] Anadido a /etc/fstab por ETIQUETA"
fi

echo ""
echo "=========================================================="
echo " 3. LIBERACION DE ESPACIO INTERNO (seguro)"
echo "=========================================================="
ANTES=$(df -BM --output=avail / | tail -1 | tr -dc '0-9')
apt-get clean >/dev/null 2>&1 && echo "  [OK] Cache de apt purgada"
apt-get autoremove --purge -y >/dev/null 2>&1 && echo "  [OK] Paquetes huerfanos eliminados"
# Kernels antiguos: NUNCA el que esta en uso
ACTUAL="$(uname -r)"
for K in $(dpkg -l 'linux-image-[0-9]*' 2>/dev/null | awk '/^ii/{print $2}'); do
  if [ "$K" != "linux-image-$ACTUAL" ]; then
    echo "  - eliminando $K"; apt-get purge -y "$K" >/dev/null 2>&1
  fi
done
echo "  [OK] Kernel en uso conservado: $ACTUAL"
DESPUES=$(df -BM --output=avail / | tail -1 | tr -dc '0-9')
echo "  ESPACIO LIBERADO: $(( (DESPUES - ANTES) )) MB"

echo ""
echo "=========================================================="
echo " 4. TIMESHIFT — conservar solo los 2 snapshots mas recientes"
echo "=========================================================="
CONSERVAR=2
if ! command -v timeshift >/dev/null; then
  echo "  [ABORTADO] timeshift no esta instalado."
else
  ANTES_TS=$(df -BM --output=avail / | tail -1 | tr -dc '0-9')
  echo "  Ocupacion actual: $(du -xsh /timeshift 2>/dev/null | cut -f1)"
  # Los nombres son marcas de tiempo (AAAA-MM-DD_HH-MM-SS): el orden alfabetico es cronologico.
  TODOS="$(ls -1 /timeshift/snapshots/ 2>/dev/null | sort)"
  TOTAL=$(echo "$TODOS" | grep -c .)
  if [ "$TOTAL" -le "$CONSERVAR" ]; then
    echo "  [SALTADO] Hay $TOTAL snapshot(s); se conservan $CONSERVAR o menos. Nada que borrar."
  else
    BORRAR="$(echo "$TODOS" | head -n -"$CONSERVAR")"
    MANTENER="$(echo "$TODOS" | tail -n "$CONSERVAR")"
    echo "  Se CONSERVAN (los $CONSERVAR mas recientes):"; echo "$MANTENER" | sed 's/^/    + /'
    echo "  Se ELIMINAN:";                                  echo "$BORRAR"   | sed 's/^/    - /'
    echo ""
    for S in $BORRAR; do
      # Se usa el CLI de timeshift, NO rm -rf: los snapshots comparten enlaces duros
      # y una base de datos interna; borrarlos a mano corrompe el estado de restauracion.
      timeshift --delete --snapshot "$S" --yes >/dev/null 2>&1 \
        && echo "  [OK] eliminado $S" || echo "  [FALLO] no se pudo eliminar $S"
    done
    DESPUES_TS=$(df -BM --output=avail / | tail -1 | tr -dc '0-9')
    echo ""
    echo "  ESPACIO LIBERADO POR TIMESHIFT: $(( DESPUES_TS - ANTES_TS )) MB"
    echo "  Snapshots restantes: $(ls -1 /timeshift/snapshots/ 2>/dev/null | wc -l)"
  fi
fi

echo ""
echo "=========================================================="
df -h / | tail -1
lsblk -o NAME,SIZE,FSTYPE,LABEL,MOUNTPOINT | grep -E "sd|mmcblk0p2"
