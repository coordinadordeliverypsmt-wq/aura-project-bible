#!/usr/bin/env bash
# Espera a que la maquina alcance los umbrales de memoria declarados en el DP de comparacion.
# No baja los umbrales: si no se alcanzan, es un resultado.
while true; do
  A=$(awk '/MemAvailable/{print int($2/1024)}' /proc/meminfo)
  S=$(awk '/SwapFree/{print int($2/1024)}' /proc/meminfo)
  if [ "$A" -ge 1400 ] && [ "$S" -ge 600 ]; then
    echo "UMBRAL OK disponible=${A}MB swap_libre=${S}MB"
    break
  fi
  sleep 30
done
