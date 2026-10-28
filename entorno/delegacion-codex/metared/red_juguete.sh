#!/usr/bin/env bash
# RED de juguete sobre metared/sujeto.sh. Aserciones en ORDEN, la terminal PRIMERO.
# Determinista: no toca red, ni Codex, ni el repositorio.
set -u
S="${S:?falta S=ruta al sujeto}"; f=0
ok(){ printf "  %-46s %s\n" "$1" "$2"; }; mal(){ printf "  %-46s %s <-- FALLO\n" "$1" "$2"; f=$((f+1)); }
OUT=$("$S" 2>/dev/null); RC=$?
# 1 · ASERCION TERMINAL: la garantia es que el sujeto COMPLETA sin morir.
# Si muere, las aserciones siguientes NO PUEDEN evaluarse —no hay salida que medir— y la RED
# termina aqui. Es el mismo escenario que en las RED reales: el conteo de aserciones cae, y es
# entonces cuando la bateria debe decidir si concede la excepcion TERMINAL o no.
if [ "$RC" -eq 0 ]; then
  ok "el sujeto NO muere: exit 0" "exit 0"
else
  mal "el sujeto NO muere: exit 0" "exit $RC"
  echo "FAIL · $f"; exit 1
fi
# 2..5 · el resto, que solo pueden evaluarse si el sujeto llego hasta el final
case "$OUT" in *PASO_1_OK*) ok "emite PASO_1_OK" "ok" ;; *) mal "emite PASO_1_OK" "ausente" ;; esac
case "$OUT" in *"GUARDA_OK eco=AUSENTE"*) ok "la guarda clasifica la ausencia" "AUSENTE" ;;
                                       *) mal "la guarda clasifica la ausencia" "no clasifica" ;; esac
case "$OUT" in *PASO_4_OK*) ok "emite PASO_4_OK" "ok" ;; *) mal "emite PASO_4_OK" "ausente" ;; esac
case "$OUT" in *FIN*) ok "emite FIN" "ok" ;; *) mal "emite FIN" "ausente" ;; esac
[ $f -eq 0 ] && { echo "PASS"; exit 0; } || { echo "FAIL · $f"; exit 1; }
