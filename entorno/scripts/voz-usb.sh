#!/usr/bin/env bash
# Lanzador de AURA con guardarrail de VOZ — Voice persistence opcion B (acta del CEO, 2026-09-16).
#
# Reutiliza el patron del acta D27 (`ollama-usb.sh`), cuya leccion esta escrita alli:
#   «Una variable de entorno no es una garantia: /media/.../AURORA_EXT existe igual con el USB
#    desmontado».
# Medido en HC-1: el directorio del punto de montaje sigue existiendo en el disco interno con la USB
# fuera, asi que comprobar la RUTA no prueba nada. Lo que prueba algo es comprobar el DISPOSITIVO.
#
# QUE COMPRUEBA, en orden:
#   1. la USB con la etiqueta declarada esta conectada        (lsblk por etiqueta)
#   2. esta montada donde se espera                           (mountpoint)
#   3. los modelos residen FISICAMENTE en ese dispositivo     (df --output=source)
#   4. los ficheros existen y son LEGIBLES                    (.onnx + .onnx.json + cache de Whisper)
#
# DIFERENCIA DELIBERADA CON D27. Ollama ESCRIBE en su almacen, por eso D27 exige `-w` y ABORTA. La voz
# solo LEE, y AURA ya sabe entregar los turnos en texto declarando «voz: NO DISPONIBLE». Abortar
# dejaria al usuario sin producto por culpa de un periferico. Por eso, por defecto, este lanzador
# DEGRADA CON HONESTIDAD: no exporta nada, lo dice, y arranca igual. `--exigir-voz` recupera el
# comportamiento estricto de D27 para quien quiera voz o nada.
#
# NO descarga, NO instala, NO copia y NO cambia de modelo. Solo mira y decide si puede exportar.
#
# Uso:
#   bash entorno/scripts/voz-usb.sh --verificar              # diagnostica y no lanza nada
#   bash entorno/scripts/voz-usb.sh                          # exporta si puede y arranca AURA
#   bash entorno/scripts/voz-usb.sh --exigir-voz             # aborta si no hay voz (estricto, D27)
set -uo pipefail

ETIQUETA="${AURA_VOZ_ETIQUETA:-AURORA_EXT}"
RAIZ="${AURA_VOZ_RAIZ:-/media/$USER/AURORA_EXT}"
VOZ_ONNX="$RAIZ/piper_voices/es_MX-ald-medium.onnx"
CACHE_HF="$RAIZ/hf_cache"

MODO_VERIFICAR=0
EXIGIR_VOZ=0
DEGRADAR_EXPLICITO=0
for arg in "$@"; do
  case "$arg" in
    --verificar)  MODO_VERIFICAR=1 ;;
    --exigir-voz) EXIGIR_VOZ=1 ;;
    --degradar)   DEGRADAR_EXPLICITO=1; EXIGIR_VOZ=0 ;;
  esac
done

FALLOS=()

# --- 1 y 2 · el DISPOSITIVO, no la ruta (la leccion de D27) -------------------------------------
# `AURA_VOZ_SIN_COMPROBAR_DISPOSITIVO=1` existe SOLO para las pruebas, que trabajan en directorios
# temporales y no pueden montar nada. Esta declarado y es visible en la llamada, en vez de escondido
# dentro del guardarrail: la misma correccion que `zona_permitida` tuvo que hacer cuando aceptaba
# `/tmp` de forma incondicional «para que las pruebas pasaran».
if [ "${AURA_VOZ_SIN_COMPROBAR_DISPOSITIVO:-0}" != "1" ]; then
  USB_DEV="$(lsblk -nro PATH,LABEL 2>/dev/null | awk -v l="$ETIQUETA" '$2==l{print $1; exit}')"
  if [ -z "$USB_DEV" ]; then
    FALLOS+=("el USB '$ETIQUETA' no esta conectado (ningun dispositivo lleva esa etiqueta)")
  elif ! mountpoint -q "$RAIZ"; then
    FALLOS+=("el USB '$ETIQUETA' no esta montado en $RAIZ")
  else
    DEV_REAL="$(df --output=source "$RAIZ" 2>/dev/null | tail -1)"
    if [ "$DEV_REAL" != "$USB_DEV" ]; then
      FALLOS+=("'$RAIZ' reside en el dispositivo $DEV_REAL, no en el USB ($USB_DEV): los modelos NO estan donde se declara")
    fi
  fi
fi

# --- 3 · los ficheros que la voz necesita, y que sean LEGIBLES ------------------------------------
# Piper exige el `.onnx` y su `.onnx.json` JUNTOS: sin el segundo aborta con un error ilegible sobre
# un fichero que el usuario nunca nombro.
[ -r "$VOZ_ONNX" ]        || FALLOS+=("falta o no es legible la voz Piper: $VOZ_ONNX")
[ -r "$VOZ_ONNX.json" ]   || FALLOS+=("falta o no es legible el .onnx.json de la voz: $VOZ_ONNX.json")
[ -d "$CACHE_HF" ]        || FALLOS+=("falta la cache de faster-whisper: $CACHE_HF")

# --- 4 · veredicto --------------------------------------------------------------------------------
if [ ${#FALLOS[@]} -eq 0 ]; then
  echo "VOZ DISPONIBLE (guardarrail D27 OK: modelos verificados en el dispositivo)"
  echo "  AURA_PIPER_VOICE=$VOZ_ONNX"
  echo "  HF_HOME=$CACHE_HF"
  echo "  HF_HUB_OFFLINE=1"
  export AURA_PIPER_VOICE="$VOZ_ONNX"
  export HF_HOME="$CACHE_HF"
  export HF_HUB_OFFLINE=1          # local-first (D24/ADR-0001): jamas se descarga un modelo al vuelo
  [ "$MODO_VERIFICAR" = "1" ] && exit 0
  exec python3 -m aura_skeleton "$@"
fi

echo "VOZ NO DISPONIBLE:"
for f in "${FALLOS[@]}"; do echo "  - $f"; done

if [ "$EXIGIR_VOZ" = "1" ]; then
  echo "ABORTADO: se pidio --exigir-voz y la voz no esta disponible."
  exit 1
fi

# Degradacion honesta: AURA arranca, lo declara en el BOOT y entrega los turnos SOLO EN TEXTO.
echo "AURA arrancara igualmente y entregara los turnos solo en texto (degradacion honesta)."
echo "No se descarga, no se copia y no se cambia de modelo: eso es una decision del CEO, no del arranque."

# **EL CODIGO DE SALIDA DE `--verificar` ES EL VEREDICTO, no el humor del lanzador.** Quien diagnostica
# necesita saber si hay voz; quien arranca necesita saber si puede seguir. Son dos preguntas distintas:
# `--verificar` responde la primera (0 = hay voz) y `--degradar` declara que la segunda tambien vale 0.
if [ "$MODO_VERIFICAR" = "1" ]; then
  [ "$DEGRADAR_EXPLICITO" = "1" ] && exit 0
  exit 1
fi
exec python3 -m aura_skeleton "$@"
