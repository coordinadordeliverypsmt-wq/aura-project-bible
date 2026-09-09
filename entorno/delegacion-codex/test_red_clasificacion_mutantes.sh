#!/usr/bin/env bash
# RED · de la LOGICA DE CLASIFICACION de bateria_mutacion.sh (meta-prueba).
#
# ============================================================================================
# REESCRITA 2026-08-24. La version anterior era NO DETERMINISTA y por eso no valia como guardian.
# ============================================================================================
# Usaba `test_red_señales_reales.sh` —que invoca CODEX REAL— para probar logica de clasificacion.
# Su veredicto cambiaba con el estado de la cuota: el mismo caso dio DETECTADO (2/2 con cuota) y
# SIN_CONTROL al agotarse. Una prueba cuyo resultado depende de un servicio externo no puede
# custodiar una regla metodologica.
#
# EL DEFECTO QUE CUSTODIA. La regla TER anterior concedia TERMINAL_EJERCIDO con solo ver la asercion
# TER marcada FALLO. Pero si el mutante MATA el sujeto, TODAS las aserciones fallan, incluida esa:
# la condicion se cumplia TRIVIALMENTE. Formalmente
#     P(TER falla | ataca la garantia terminal) = P(TER falla | muere por otra causa) = 1
# luego su poder discriminante era NULO. El caso B de abajo lo reproduce y DEBE quedar rojo si la
# regla vuelve a degradarse a «TER fallo».
#
# AHORA TERMINAL_EJERCIDO exige TRES evidencias simultaneas:
#   E1 PRECEDENCIA — la asercion TER es la PRIMERA que falla
#   E2 CAUSALIDAD  — la traza `bash -x` demuestra que el proceso murio EN EL PUNTO ATACADO
#   E3 FIRMA       — el codigo de salida coincide con el declarado
# mas E4, el control adversarial permanente, que es el caso B de esta misma RED.
#
# TODO ES DETERMINISTA: sujeto de juguete propio, sin red, sin Codex, sin inferencia, sin thread_id,
# sin delegation_id, sin reloj y sin depender del estado del repositorio.
set -u
D="$(cd "$(dirname "$0")" && pwd)"; f=0
ok(){ printf "  %-56s %s\n" "$1" "$2"; }; mal(){ printf "  %-56s %s <-- FALLO\n" "$1" "$2"; f=$((f+1)); }
SAL=$(mktemp); trap 'rm -f "$SAL"' EXIT

WRAPPER="$D/metared/sujeto.sh" DEF="$D/metared/casos.def" \
  timeout 600 "$D/bateria_mutacion.sh" </dev/null > "$SAL" 2>&1

ver(){ grep -E "· $1( |$)|· $1 —" "$SAL" | grep -oE '^  [A-Z_]+' | tr -d ' ' | head -1; }
esperado(){ # $1=caso  $2=veredicto esperado  $3=descripcion
  local got; got=$(ver "$1")
  [ "$got" = "$2" ] && ok "$3" "$got" || mal "$3" "esperado=$2 obtenido=${got:-nada}"
}
esperado A_TERMINAL_LEGITIMO      DETECTADO        "A · TER correcto y muerte en el punto atacado"
esperado B_MUERTE_PREMATURA       NO_EJERCIDO      "B · muerte ANTES del punto TER (control adversarial)"
esperado C_TER_EQUIVOCADO         NO_EJERCIDO      "C · TER apunta a una asercion que no falla primero"
esperado D_INOCUO                 SUPERVIVIENTE    "D · mutacion inocua: la RED pasa -> SUPERVIVIENTE"
esperado E_SINTAXIS_ROTA          MUTANTE_INVALIDO "E · transformacion que rompe la sintaxis"
esperado F_TERMINAL_SIN_CAUSALIDAD NO_EJERCIDO     "F · ataca lo terminal pero muere antes por otra causa"

# --- la evidencia concreta, no solo el veredicto ------------------------------------------------
grep -q 'A_TERMINAL_LEGITIMO.*E1+E2+E3' "$SAL" \
  && ok "A concede la excepcion por las TRES evidencias" "E1+E2+E3" \
  || mal "A concede la excepcion por las TRES evidencias" "no consta"
grep -q 'B_MUERTE_PREMATURA.*E2=no' "$SAL" \
  && ok "B se deniega por CAUSALIDAD (E2), no por sintoma" "E2=no" \
  || mal "B se deniega por CAUSALIDAD (E2), no por sintoma" "$(grep -o 'B_MUERTE_PREMATURA.*' "$SAL"|head -1|cut -c1-60)"
grep -q 'C_TER_EQUIVOCADO.*E1=no' "$SAL" \
  && ok "C se deniega por PRECEDENCIA (E1)" "E1=no" \
  || mal "C se deniega por PRECEDENCIA (E1)" "no consta"
# --- D no puede declararse EQUIVALENTE de forma automatica -------------------------------------
grep -q 'D_INOCUO.*EQUIVALENTE' "$SAL" \
  && mal "D NO se reclasifica automaticamente como EQUIVALENTE" "la bateria lo declaro equivalente" \
  || ok "D NO se reclasifica automaticamente como EQUIVALENTE" "solo SUPERVIVIENTE"
# --- determinismo: dos ejecuciones deben coincidir ---------------------------------------------
S2=$(mktemp)
WRAPPER="$D/metared/sujeto.sh" DEF="$D/metared/casos.def" \
  timeout 600 "$D/bateria_mutacion.sh" </dev/null > "$S2" 2>&1
a=$(grep -oE '· [A-Z_]+ —' "$SAL" | sort); b=$(grep -oE '· [A-Z_]+ —' "$S2" | sort)
[ "$a" = "$b" ] && ok "la clasificacion es DETERMINISTA (2 ejecuciones iguales)" "identicas" \
                || mal "la clasificacion es DETERMINISTA (2 ejecuciones iguales)" "difieren"
rm -f "$S2"

[ $f -eq 0 ] && { echo "PASS"; exit 0; } || { echo "FAIL · $f"; exit 1; }
