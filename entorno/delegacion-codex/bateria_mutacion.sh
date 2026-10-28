#!/usr/bin/env bash
# BATERIA DE MUTACION DEL CODEX MVP — un solo comando, reproducible por un auditor.
#
#     ./bateria_mutacion.sh            # ejecuta las 18 mutaciones canonicas de mutantes.def
#     ./bateria_mutacion.sh M17        # ejecuta solo las indicadas
#
# NO MODIFICA LA PRODUCCION. Cada mutante se aplica a una COPIA del wrapper bajo
# /tmp/codex-mvp/bateria/<run>/<ID>/. delegar.sh no se toca en ningun momento: se comprueba al
# final comparando su sha256 antes y despues.
#
# CRITERIO DE DETECTADO — los dos a la vez, nunca uno solo:
#   (1) CONTROL: la RED PASA con la copia INTACTA. Sin esto, una RED averiada daria «detectado»
#       por avería y no por el mutante. Es el caso de control que este proyecto ya ha echado en
#       falta cuatro veces.
#   (2) MUTADO: la MISMA RED FALLA con la copia mutada.
# Si el sed no cambia el fichero -> NO_APLICADO. Nunca DETECTADO: un patron que ya no existe
# deja la garantia sin red EN SILENCIO, y eso ya ocurrio dos veces en este proyecto.
set -u
AURA_ROOT_COMMIT="79018b3b49da782a57367257ca1f1bd597c076cb"
AQUI="$(cd "$(dirname "$0")" && pwd)"
WRAPPER="${WRAPPER:-$AQUI/delegar.sh}"   # parametrizable: permite auto-probar con sujetos de juguete
DEF="${DEF:-$AQUI/mutantes.def}"   # parametrizable: permite auto-probar la bateria
RUN="${RUN_ID:-$(date +%Y%m%dT%H%M%S)-$$}"
BASE="/tmp/codex-mvp/bateria/$RUN"
mkdir -p "$BASE"

SHA_ANTES=$(sha256sum "$WRAPPER" | cut -c1-16)
echo "== BATERIA DE MUTACION · CODEX MVP =="
echo "   run           : $RUN"
echo "   wrapper       : $WRAPPER (sha $SHA_ANTES)"
echo "   evidencia     : $BASE/"
echo "   produccion    : NO se modifica (se muta una copia por mutante)"
echo

# --- guardas de seguridad, antes de nada --------------------------------------------------------
# Ninguna RED puede tomar AURA como sujeto. Las que prueban objetivos prohibidos usan
# --solo-verificar y un centinela; aqui se verifica ademas que el repo que aloja al wrapper no se
# ofrece nunca como fixture.
if git -C "$AQUI" rev-parse --show-toplevel >/dev/null 2>&1; then
  RAIZ_AQUI=$(git -C "$AQUI" rev-list --max-parents=0 HEAD 2>/dev/null | head -1)
  if [ "$RAIZ_AQUI" = "$AURA_ROOT_COMMIT" ]; then
    echo "   [i] el wrapper vive DENTRO de AURA (root ${RAIZ_AQUI:0:12}). Los fixtures son sinteticos"
    echo "       bajo /tmp/codex-mvp/ y ninguna RED usa este repo como objetivo."
  fi
fi

SELECC="$*"
declare -A CONTROL_CACHE=()

# --- control: una RED averiada no puede producir un DETECTADO -----------------------------------
control() {  # $1 = nombre de la RED
  local red="$1"
  if [ -n "${CONTROL_CACHE[$red]:-}" ]; then echo "${CONTROL_CACHE[$red]}"; return; fi
  local log="$BASE/control-${red//\//_}.log"
  ( cd "$AQUI" && S="$WRAPPER" timeout 500 "./$red" ) < /dev/null > "$log" 2>&1
  local rc=$?
  [ $rc -eq 0 ] && CONTROL_CACHE[$red]="PASS" || CONTROL_CACHE[$red]="FAIL"
  echo "${CONTROL_CACHE[$red]}"
}

TOT=0; DET=0; SUP=0; NOAP=0; SINCTRL=0; INVAL=0; NOEJ=0
RESUMEN="$BASE/resumen.tsv"; : > "$RESUMEN"

# --- recorrido de la declaracion ----------------------------------------------------------------
ID=""; GAR=""; TRA=""; REDS=""; DIF=""; TER=""; PUNTO=""; INVOCA=""; FIRMA=""
procesar() {
  [ -n "$ID" ] || return 0
  if [ -n "$SELECC" ]; then case " $SELECC " in *" $ID "*) ;; *) return 0 ;; esac; fi
  TOT=$((TOT+1))
  local dir="$BASE/$ID"; mkdir -p "$dir"
  local copia="$dir/delegar.sh"
  cp "$WRAPPER" "$copia"; chmod +x "$copia"

  # 1 · aplicar la transformacion semantica a la COPIA
  sed -i -E "$TRA" "$copia" 2>"$dir/sed.err" || true
  if cmp -s "$copia" "$WRAPPER"; then
    echo "  NO_APLICADO · $ID — el patron no existe: la garantia se queda SIN RED en silencio"
    echo "$ID	NO_APLICADO	$GAR" >> "$RESUMEN"; NOAP=$((NOAP+1)); ID=""; return 0
  fi
  diff -u "$WRAPPER" "$copia" > "$dir/mutacion.diff" 2>/dev/null || true

  # 1.bis · VALIDEZ DEL MUTANTE — obligatorio. Un mutante que rompe la sintaxis no degrada el
  # wrapper: lo DESTRUYE, y entonces CUALQUIER RED falla contra el por averia, no por la garantia.
  # Clasificarlo DETECTADO es un falso positivo. Asi entraron M8, M9 y M15 (auditoria 2026-08-24).
  if ! bash -n "$copia" 2>"$dir/sintaxis.err"; then
    echo "  MUTANTE_INVALIDO · $ID — rompe la sintaxis: $(head -1 "$dir/sintaxis.err")"
    echo "$ID\tMUTANTE_INVALIDO\t$GAR" >> "$RESUMEN"; INVAL=$((INVAL+1)); ID=""; return 0
  fi
  # 1.ter · TOPE DE DIFF — el diff debe contener SOLO la transformacion prevista. M8 y M15 cambiaban
  # 438 lineas (el patron casaba la cadena vacia y se antepuso al fichero entero) y nadie lo noto.
  local nlin; nlin=$(grep -c '^[+-][^+-]' "$dir/mutacion.diff" 2>/dev/null) || nlin=0
  local tope="${DIF:-12}"
  if [ "$nlin" -gt "$tope" ]; then
    echo "  MUTANTE_INVALIDO · $ID — el diff cambia $nlin lineas (tope $tope): excede la transformacion prevista"
    echo "$ID\tMUTANTE_INVALIDO\t$GAR" >> "$RESUMEN"; INVAL=$((INVAL+1)); ID=""; return 0
  fi

  # 2 · control + mutado sobre cada RED declarada
  local veredicto="SUPERVIVIENTE" ctrl_ok=0 detalle=""
  for red in $REDS; do
    local c; c=$(control "$red")
    if [ "$c" != "PASS" ]; then detalle="$detalle $red:CONTROL_FAIL"; continue; fi
    ctrl_ok=1
    local log="$dir/mutado-${red//\//_}.log"
    ( cd "$AQUI" && S="$copia" timeout 500 "./$red" ) < /dev/null > "$log" 2>&1
    local rc_mut=$?
    if [ $rc_mut -ne 0 ]; then
      # ANTI-ENMASCARAMIENTO (2026-08-24, FASE 4). Que la RED falle NO basta: debe fallar HABIENDO
      # EJERCIDO la garantia. Si el mutante rompe el SETUP, la RED aborta antes de evaluar sus
      # aserciones y el fallo no dice nada sobre la garantia atacada. Es el defecto que la auditoria
      # encontro en M1: moria por la guarda de M2 y sus 8 aserciones nunca se ejecutaban.
      # Criterio medible: el mutado debe producir al menos la mitad de las lineas de asercion que
      # el control. Muchas menos = aborto temprano = NO EJERCIDO, nunca DETECTADO.
      local lc lm
      lc=$(wc -l < "$BASE/control-${red//\//_}.log"); lm=$(wc -l < "$log")
      if [ "$lc" -gt 2 ] && [ $((lm * 2)) -lt "$lc" ]; then
        # ============================================================================================
        # EXCEPCION TERMINAL — REESCRITA 2026-08-24 tras demostrarse que la version anterior era un
        # FALSO POSITIVO. Aquella concedia TERMINAL_EJERCIDO con solo ver la asercion TER marcada
        # FALLO. Pero si el mutante MATA el sujeto, TODAS las aserciones fallan, incluida esa: la
        # condicion se cumplia TRIVIALMENTE. Formalmente, P(TER falla | ataca la garantia terminal)
        # = P(TER falla | muere por otra causa) = 1 -> poder discriminante NULO. Lo detecto la propia
        # meta-RED escrita para impedirlo, y se reprodujo 2/2.
        #
        # Ahora se exigen TRES evidencias A LA VEZ, y la excepcion se deniega si falta cualquiera:
        #
        #   E1 · PRECEDENCIA — la asercion TER es la PRIMERA que falla. Si algo falla antes, la
        #        muerte tiene otra causa. Necesaria, NO suficiente por si sola.
        #   E2 · CAUSALIDAD  — el proceso muere EN EL PUNTO ATACADO. Se ejecuta la copia mutada bajo
        #        `bash -x` y la ULTIMA instruccion trazada debe pertenecer al constructo que la
        #        transformacion modifica (`PUNTO:`). Esta es la evidencia que separa las hipotesis:
        #        un mutante que mata antes deja una traza que NO termina ahi.
        #   E3 · FIRMA       — el modo de morir (codigo de salida) coincide con el declarado
        #        (`FIRMA:`), no con «una muerte cualquiera».
        #
        # E4 (control adversarial) no vive aqui sino en la meta-RED: un caso permanente que mata el
        # sujeto ANTES del punto TER y que debe quedar ROJO si esta logica vuelve a degradarse.
        # ============================================================================================
        if [ -n "$TER" ]; then
          local e1="no" e2="no" e3="no" primera traza ultima rc_mut_real
          # E1 · ¿es TER la PRIMERA asercion marcada FALLO?
          primera=$(grep -m1 -E 'FALLO|FAIL' "$log" 2>/dev/null || true)
          case "$primera" in *"$TER"*) e1="si" ;; esac
          # E2 · ¿murio en el punto atacado?
          if [ -n "$PUNTO" ]; then
            traza="$dir/traza.txt"
            # `bash -x -c "<ruta>"` trazaria el comando EXTERNO, no las lineas internas del script:
            # el hijo se ejecuta como proceso aparte y sin -x. Hay que invocar `bash -x <script>`
            # para que la traza contenga las instrucciones del sujeto, que es lo que E2 necesita.
            local cmd="${INVOCA:-\$MUT}"; cmd="${cmd//\$MUT/bash -x $copia}"
            ( cd "$dir" && eval "$cmd" ) >/dev/null 2>"$traza"; rc_mut_real=$?
            ultima=$(grep '^+' "$traza" 2>/dev/null | tail -1 || true)
            case "$ultima" in *"$PUNTO"*) e2="si" ;; esac
            # E3 · ¿la firma de terminacion es la declarada?
            [ -z "$FIRMA" ] || [ "$rc_mut_real" = "$FIRMA" ] && e3="si"
          fi
          if [ "$e1" = "si" ] && [ "$e2" = "si" ] && [ "$e3" = "si" ]; then
            veredicto="DETECTADO"
            detalle="$detalle $red:TERMINAL_EJERCIDO(E1+E2+E3; muere en «$PUNTO»)"; break
          fi
          detalle="$detalle $red:TER_DENEGADO(E1=$e1 E2=$e2 E3=$e3)"
        fi
        veredicto="NO_EJERCIDO"; detalle="$detalle "
        detalle="$detalle $red:aserciones $lm de $lc"; break
      fi
      veredicto="DETECTADO"; detalle="$detalle $red:FALLA"; break
    else detalle="$detalle $red:PASA"; fi
  done

  if [ "$ctrl_ok" -eq 0 ]; then
    veredicto="SIN_CONTROL"; SINCTRL=$((SINCTRL+1))
    echo "  SIN_CONTROL · $ID — la RED no pasa ni con el codigo intacto: no se puede concluir"
  elif [ "$veredicto" = "NO_EJERCIDO" ]; then
    NOEJ=$((NOEJ+1)); echo "  NO_EJERCIDO · $ID — la RED aborta antes de evaluar la garantia:$detalle"
  elif [ "$veredicto" = "DETECTADO" ]; then
    DET=$((DET+1)); echo "  DETECTADO   · $ID —$detalle"
  else
    SUP=$((SUP+1)); echo "  SUPERVIVIENTE · $ID —$detalle"
  fi
  printf '%s\t%s\t%s\n' "$ID" "$veredicto" "$GAR" >> "$RESUMEN"
  echo "$veredicto" > "$dir/veredicto"
  ID=""
}

while IFS= read -r linea <&3; do
  case "$linea" in
    "== "*) procesar; ID="${linea#== }"; GAR=""; TRA=""; REDS=""; DIF=""; TER=""; PUNTO=""; INVOCA=""; FIRMA="" ;;
    "GAR: "*) GAR="${linea#GAR: }" ;;
    "TRA: "*) TRA="${linea#TRA: }" ;;
    "RED: "*) REDS="${linea#RED: }" ;;
    "DIF: "*) DIF="${linea#DIF: }" ;;
    "TER: "*) TER="${linea#TER: }" ;;
    "PUNTO: "*) PUNTO="${linea#PUNTO: }" ;;
    "INVOCA: "*) INVOCA="${linea#INVOCA: }" ;;
    "FIRMA: "*) FIRMA="${linea#FIRMA: }" ;;
  esac
done 3< "$DEF"
procesar

# --- integridad de la produccion ----------------------------------------------------------------
SHA_DESPUES=$(sha256sum "$WRAPPER" | cut -c1-16)
echo
echo "== RESULTADO =="
echo "   declarados $TOT · DETECTADOS $DET · SUPERVIVIENTES $SUP · NO_APLICADOS $NOAP · SIN_CONTROL $SINCTRL · INVALIDOS $INVAL · NO_EJERCIDOS $NOEJ"
echo "   wrapper de produccion: $SHA_ANTES -> $SHA_DESPUES $([ "$SHA_ANTES" = "$SHA_DESPUES" ] && echo '(INTACTO)' || echo '(MODIFICADO: FALLO GRAVE)')"
echo "   evidencia por mutante en $BASE/<ID>/ (mutacion.diff · control-*.log · mutado-*.log · veredicto)"
[ "$SHA_ANTES" = "$SHA_DESPUES" ] || exit 3
[ "$SUP" -eq 0 ] && [ "$NOAP" -eq 0 ] && [ "$SINCTRL" -eq 0 ] && [ "$INVAL" -eq 0 ] && [ "$NOEJ" -eq 0 ]
