#!/usr/bin/env bash
# SUJETO DE JUGUETE para probar la LOGICA DE CLASIFICACION de bateria_mutacion.sh.
#
# No es un doble de `delegar.sh` ni pretende serlo: reproduce solo la FORMA que importa —una guarda
# terminal que aisla el fallo de un pipeline bajo `set -euo pipefail`—, que es el constructo cuya
# degradacion origino la categoria TERMINAL_EJERCIDO.
#
# Es DETERMINISTA por construccion: sin red, sin inferencia, sin ficheros externos, sin reloj, sin
# aleatoriedad. Dos ejecuciones producen exactamente la misma salida.
set -euo pipefail
echo "PASO_1_OK"
echo "PASO_2_OK"
# GUARDA TERMINAL — el `if` aisla el fallo del pipeline. `grep` sin coincidencia devuelve 1; sin el
# `if`, bajo pipefail eso MATA el proceso. Es el analogo exacto de delegar.sh:146.
if VAL=$(printf 'nada\n' | grep -o 'zzz' | head -1); then
  ECO="$VAL"
else
  ECO="AUSENTE"
fi
echo "GUARDA_OK eco=$ECO"
echo "PASO_4_OK"
echo "FIN"
