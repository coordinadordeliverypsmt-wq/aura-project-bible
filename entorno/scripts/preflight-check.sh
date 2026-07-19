#!/usr/bin/env bash
# Preflight Check del entorno de AURA (acta D27).
# Ningun Sprint/Milestone comienza sin estado APTO.
# PRINCIPIO: se verifica el DISPOSITIVO REAL que respalda cada ruta, nunca la
# variable de entorno ni el archivo de configuracion. Una variable puede apuntar
# a una ruta que existe en el disco equivocado: ese fue el fallo de 2026-07-19.
set -uo pipefail

USB_LABEL="AURORA_EXT"
EXPECTED_MOUNT="/media/$USER/AURORA_EXT"
MIN_INT_GB=2      # margen minimo disco interno
MIN_USB_GB=1      # margen minimo USB
AUTOFIX=${AUTOFIX:-1}

PROBLEMAS=(); CORREGIDOS=(); MANUAL=(); RIESGOS=()
ok(){   echo "  [ OK ] $1"; }
warn(){ echo "  [WARN] $1"; RIESGOS+=("$1"); }
bad(){  echo "  [FAIL] $1"; PROBLEMAS+=("$1"); }
fixed(){ echo "  [FIX ] $1"; CORREGIDOS+=("$1"); }
manual(){ MANUAL+=("$1"); }

gb(){ df -BG --output=avail "$1" 2>/dev/null | tail -1 | tr -dc '0-9'; }
devof(){ df --output=source "$1" 2>/dev/null | tail -1; }
usbdev(){ lsblk -nro PATH,LABEL 2>/dev/null | awk -v l="$USB_LABEL" '$2==l{print $1; exit}'; }

echo "==> PREFLIGHT CHECK — entorno AURA — $(date '+%Y-%m-%d %H:%M:%S')"
echo ""

# --- 1. USB presente y montado -------------------------------------------
echo "-- Almacenamiento USB --"
USB_DEV="$(usbdev)"
if [ -z "$USB_DEV" ]; then
  bad "USB '$USB_LABEL' no esta conectado al sistema"
  manual "Conectar fisicamente el disco USB etiquetado $USB_LABEL"
else
  ok "USB detectado: $USB_DEV (label $USB_LABEL)"
  USB_MNT="$(lsblk -nro MOUNTPOINT "$USB_DEV" 2>/dev/null | head -1)"
  if [ -z "$USB_MNT" ]; then
    bad "USB NO montado"
    if [ "$AUTOFIX" = "1" ] && command -v udisksctl >/dev/null; then
      udisksctl mount -b "$USB_DEV" >/dev/null 2>&1
      USB_MNT="$(lsblk -nro MOUNTPOINT "$USB_DEV" 2>/dev/null | head -1)"
      [ -n "$USB_MNT" ] && fixed "USB montado automaticamente en $USB_MNT"
    fi
    [ -z "$USB_MNT" ] && manual "sudo mount $USB_DEV $EXPECTED_MOUNT"
  else
    ok "USB montado en: $USB_MNT"
  fi
fi

# --- 2. El punto de montaje corresponde al dispositivo esperado ----------
if [ -n "${USB_MNT:-}" ]; then
  if [ "$USB_MNT" != "$EXPECTED_MOUNT" ]; then
    warn "USB montado en '$USB_MNT', se esperaba '$EXPECTED_MOUNT' (rutas configuradas pueden no coincidir)"
    manual "Persistencia: anadir a /etc/fstab -> LABEL=$USB_LABEL $EXPECTED_MOUNT ext4 defaults,nofail,x-systemd.device-timeout=10 0 2"
  else
    ok "Punto de montaje coincide con el esperado"
  fi
  if [ ! -w "$USB_MNT" ]; then
    bad "USB montado pero NO escribible por $USER (propietario: $(stat -c '%U' "$USB_MNT" 2>/dev/null))"
    manual "sudo chown $USER:$USER $USB_MNT"
  else
    ok "USB escribible por $USER"
  fi
fi

# --- 3. Espacio y margen --------------------------------------------------
echo ""; echo "-- Espacio disponible --"
INT_FREE=$(gb /)
[ "${INT_FREE:-0}" -ge "$MIN_INT_GB" ] && ok "Disco interno: ${INT_FREE}G libres (min ${MIN_INT_GB}G)" \
  || bad "Disco interno: ${INT_FREE}G libres, por debajo del minimo ${MIN_INT_GB}G"
if [ -n "${USB_MNT:-}" ]; then
  USB_FREE=$(gb "$USB_MNT")
  [ "${USB_FREE:-0}" -ge "$MIN_USB_GB" ] && ok "USB: ${USB_FREE}G libres (min ${MIN_USB_GB}G)" \
    || bad "USB: ${USB_FREE}G libres, por debajo del minimo ${MIN_USB_GB}G"
fi

# Reparacion automatica: limpiar SOLO regenerables si falta margen interno
if [ "${INT_FREE:-99}" -lt "$MIN_INT_GB" ] && [ "$AUTOFIX" = "1" ]; then
  find "$HOME/Documentos/AURA" -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null
  rm -rf "$HOME/.cache/pip" "$HOME/.npm/_npx" "$HOME/.npm/_cacache" \
         "$HOME/.cache/google-chrome" "$HOME/.cache/mozilla" 2>/dev/null
  NEW=$(gb /)
  [ "${NEW:-0}" -gt "${INT_FREE:-0}" ] && fixed "Cache regenerable purgada: ${INT_FREE}G -> ${NEW}G libres"
  INT_FREE=$NEW
fi

# --- 4. Ollama usa REALMENTE el USB --------------------------------------
echo ""; echo "-- Ollama --"
PID="$(pgrep -f 'ollama serve' | head -1)"
OLLAMA_DIR=""
if [ -n "$PID" ]; then
  ok "Ollama en ejecucion (PID $PID)"
  OLLAMA_DIR="$(tr '\0' '\n' < /proc/$PID/environ 2>/dev/null | sed -n 's/^OLLAMA_MODELS=//p')"
else
  warn "Ollama no esta en ejecucion"
  OLLAMA_DIR="${OLLAMA_MODELS:-}"
fi
[ -z "$OLLAMA_DIR" ] && OLLAMA_DIR="$HOME/.ollama/models"

if [ ! -d "$OLLAMA_DIR" ]; then
  bad "Ruta de modelos configurada NO existe: $OLLAMA_DIR"
else
  # LA COMPROBACION CLAVE: el dispositivo real, no la variable
  DEV_MODELS="$(devof "$OLLAMA_DIR")"
  if [ -n "${USB_DEV:-}" ] && [ "$DEV_MODELS" = "$USB_DEV" ]; then
    ok "Modelos en el USB (verificado por dispositivo: $DEV_MODELS)"
  else
    bad "Modelos NO estan en el USB: '$OLLAMA_DIR' reside en $DEV_MODELS (esperado $USB_DEV)"
    RIESGOS+=("Descargar modelos ahora consumiria disco INTERNO de forma silenciosa")
    manual "mv '$OLLAMA_DIR' $EXPECTED_MOUNT/ && reiniciar ollama con OLLAMA_MODELS=$EXPECTED_MOUNT/ollama_models"
  fi
fi

# --- 5. Modelos duplicados en disco interno ------------------------------
# Se comprueba si hay DATOS de modelo en interno, no la mera existencia del directorio:
# /usr/share/ollama/.ollama/models puede ser un SYMLINK al USB (configuracion correcta),
# en cuyo caso borrarlo destruiria la migracion. Nunca marcar por existencia del path.
DUP=0
SVC_MODELS=/usr/share/ollama/.ollama/models
if [ -e "$SVC_MODELS" ]; then
  DEV_SVC="$(devof "$SVC_MODELS")"
  if [ -L "$SVC_MODELS" ] && [ -n "${USB_DEV:-}" ] && [ "$DEV_SVC" = "$USB_DEV" ]; then
    ok "Store del servicio enlazado al USB: $SVC_MODELS -> $(readlink "$SVC_MODELS")"
  elif [ "$DEV_SVC" != "${USB_DEV:-}" ]; then
    SZ="$(du -xsh "$SVC_MODELS" 2>/dev/null | cut -f1)"
    bad "Modelos duplicados en disco interno: $SVC_MODELS ($SZ, dispositivo $DEV_SVC)"
    manual "Verificar copia funcional en USB y despues: sudo rm -rf $SVC_MODELS"
    DUP=1
  fi
fi
# Blobs sueltos de gran tamano en interno (excluye snapshots de Timeshift: son respaldos)
STRAY="$(find /usr /home /opt -xdev -name 'sha256-*' -size +100M 2>/dev/null | head -3)"
if [ -n "$STRAY" ]; then
  bad "Blobs de modelo en disco interno: $(echo "$STRAY" | tr '\n' ' ')"
  DUP=1
fi
[ "$DUP" = "0" ] && ok "Sin modelos duplicados en disco interno"

# --- 6. Swap --------------------------------------------------------------
echo ""; echo "-- Swap --"
SWAP_NAME="$(swapon --show=NAME --noheadings 2>/dev/null | head -1)"
if [ -z "$SWAP_NAME" ]; then
  bad "No hay swap activo (RAM insuficiente sin el)"
  manual "sudo swapon <archivo de swap>"
else
  DEV_SWAP="$(devof "$SWAP_NAME")"
  if [ -n "${USB_DEV:-}" ] && [ "$DEV_SWAP" = "$USB_DEV" ]; then
    ok "Swap activo en USB: $SWAP_NAME"
  else
    warn "Swap activo en disco INTERNO: $SWAP_NAME ($DEV_SWAP)"
    manual "sudo swapoff $SWAP_NAME && sudo rm $SWAP_NAME && sudo swapon $EXPECTED_MOUNT/swapfile_aurora"
  fi
fi

# --- Veredicto ------------------------------------------------------------
echo ""; echo "======================================================"
if [ ${#PROBLEMAS[@]} -eq 0 ]; then
  echo "ESTADO: APTO"; VEREDICTO=0
else
  echo "ESTADO: NO APTO  (${#PROBLEMAS[@]} problema(s) bloqueante(s))"; VEREDICTO=1
fi
echo "======================================================"
pr(){ [ ${#2} -eq 0 ] && return; }
[ ${#PROBLEMAS[@]} -gt 0 ] && { echo ""; echo "Problemas encontrados:";  printf '  - %s\n' "${PROBLEMAS[@]}"; }
[ ${#CORREGIDOS[@]} -gt 0 ] && { echo ""; echo "Corregidos automaticamente:"; printf '  - %s\n' "${CORREGIDOS[@]}"; }
[ ${#MANUAL[@]} -gt 0 ] && { echo ""; echo "Acciones manuales requeridas (root):"; printf '  $ %s\n' "${MANUAL[@]}"; }
[ ${#RIESGOS[@]} -gt 0 ] && { echo ""; echo "Riesgos abiertos:"; printf '  - %s\n' "${RIESGOS[@]}"; }
echo ""
exit $VEREDICTO
