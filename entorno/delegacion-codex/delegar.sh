#!/usr/bin/env bash
# Delegación Claude Code -> Codex. MVP autorizado por el CEO el 2026-08-26.
#
# Qué es y qué NO es: una herramienta INTERNA de desarrollo para que el CEO deje de copiar prompts
# entre agentes. NO es el Orquestador de AURA, no toca el Communication Plane y no concede autoridad
# arquitectónica a nadie: Codex trabaja en un worktree aislado que no contiene Bible, ADR, decisiones
# ni el Control Plane, así que lo que no está montado no se modifica.
#
# FAIL-CLOSED: cualquier condición no verificada aborta. Un UNKNOWN nunca se convierte en PASS.
set -euo pipefail

CODEX=$(command -v codex || true)
# Identidad canonica de AURA, verificada el 2026-08-24 en el repo principal, en el worktree
# m3-entry, en walking-skeleton y en walking-skeleton/aura_skeleton. Un repo ajeno no la comparte.
AURA_ROOT_COMMIT="79018b3b49da782a57367257ca1f1bd597c076cb"

abortar() { echo "FAILURE: $1" >&2; exit 91; }

SOLO_VERIFICAR=0 ; DELEG_ID="" ; PARENT_ID="" ; WORKTREE="" ; MODELO="$(codex --version 2>/dev/null || echo UNKNOWN)" ; ENCARGO="" ; ACCION="exec" ; SESION=""
while [ $# -gt 0 ]; do case "$1" in
  --worktree) WORKTREE="${2:?}"; shift 2 ;;
  --encargo)  ENCARGO="${2:?}";  shift 2 ;;
  --resume)   ACCION="resume"; SESION="${2:?}"; shift 2 ;;
  --review)   ACCION="review"; shift ;;
  --solo-verificar) SOLO_VERIFICAR=1; shift ;;
  --delegacion-id) DELEG_ID="${2:?}"; shift 2 ;;
  --marca) export MARCA_DELEGACION="${2:?}"; shift 2 ;;
  --parent) PARENT_ID="${2:?}"; shift 2 ;;
  *) abortar "argumento desconocido: $1" ;;
esac; done

# --- precondiciones -----------------------------------------------------------------------------
[ -n "$CODEX" ]                || abortar "codex no esta instalado"
[ -n "$WORKTREE" ]             || abortar "falta --worktree"
[ -d "$WORKTREE" ]             || abortar "el worktree no existe: $WORKTREE"
# El CEO resolvio el 2026-08-26 NO exigir --modelo: la instalacion real lo rechaza. Codex
# autenticado con cuenta ChatGPT responde 400 «model not supported» ante -m, y tampoco reporta el
# modelo efectivo en su salida. La atribucion por modelo concreto NO es alcanzable con esta
# instalacion, y eso se registra como UNKNOWN — que no es PASS ni FAILURE, sino «no verificable».
true

# REGLA DURA DE AISLAMIENTO: el worktree de Codex no puede ser el que Claude esta usando, ni
# contener las fuentes de verdad. Si comparten arbol, dos agentes pueden tocar el mismo fichero.
WT_REAL=$(cd "$WORKTREE" && pwd -P)
AQUI=$(pwd -P)
[ "$WT_REAL" != "$AQUI" ]      || abortar "el worktree de Codex es el mismo que el actual: no esta aislado"
case "$AQUI" in "$WT_REAL"/*) abortar "el directorio actual esta DENTRO del worktree de Codex" ;; esac
case "$WT_REAL" in "$AQUI"/*) abortar "el worktree de Codex esta DENTRO del directorio actual: no esta aislado" ;; esac
# AURA es intocable como objetivo de delegacion. Se compara por ruta REAL resuelta, no por cadena.
# La identidad de AURA NO se deriva de donde vive el wrapper. `AURA_RAIZ`, calculado con
# `dirname "$0"`, quedaba inerte al copiar el script y ademas rechazaba repos sinteticos legitimos
# alegando que estaban «DENTRO de AURA». Se elimina: la unica identidad es el commit raiz del
# repositorio OBJETIVO, comprobado en verificar_objetivo().

for prohibido in docs adr decisiones entorno/control-plane; do
  [ -e "$WT_REAL/$prohibido" ] && abortar "el worktree expone una fuente de verdad: $prohibido"
done
true

# --- El objetivo de `review` se DEMUESTRA, no se supone ------------------------------------------
# Se ejecuta dentro del mismo subshell que invocara a Codex, porque `review` toma el repositorio del
# cwd y de ningun otro sitio. Si algo no cuadra, Codex NO llega a invocarse.
verificar_objetivo() {
  local wt="$1"
  ( cd "$wt" 2>/dev/null || { echo "FAILURE: no se puede entrar al worktree" >&2; exit 92; }
    local tope; tope=$(git rev-parse --show-toplevel 2>/dev/null || echo "")
    [ -n "$tope" ] || { echo "FAILURE: el objetivo no es un repositorio git: indemostrable" >&2; exit 93; }
    local real; real=$(cd "$tope" && pwd -P)
    [ "$real" = "$wt" ] || { echo "FAILURE: el repo detectado ($real) NO es el worktree autorizado ($wt)" >&2; exit 94; }
    # IDENTIDAD DE AURA: el commit raiz del repositorio OBJETIVO. No es dirname "$0", ni la ruta,
    # ni un marcador de ficheros. Es propiedad del REPOSITORIO: identica en el principal, en
    # cualquier worktree y en cualquier subdirectorio, y ausente en repos ajenos. Copiar el wrapper
    # a otra ubicacion ya no puede dejarla inerte, que era el defecto de la version anterior.
    local raiz_obj; raiz_obj=$(git rev-list --max-parents=0 HEAD 2>/dev/null | head -1)
    if [ "$raiz_obj" = "$AURA_ROOT_COMMIT" ]; then
      echo "FAILURE: el objetivo pertenece a AURA (commit raiz $AURA_ROOT_COMMIT)" >&2; exit 96
    fi
)
}

# --- UNA EJECUCION = UNA EVIDENCIA AISLADA ------------------------------------------------------
# El Quality Gate detecto que todas las delegaciones escribian en el mismo `.delegacion/` y se
# machacaban entre si: la evidencia del review real quedo sobrescrita por una prueba posterior, y con
# ella la posibilidad de auditar esa ejecucion.
#
# La identidad NO deriva del thread_id: se midio que `resume` puede conservarlo o cambiarlo, asi que
# no sirve como identidad estable. Se genera aqui, con independencia de Codex.
if [ -z "$DELEG_ID" ]; then
  DELEG_ID="$(date +%Y%m%dT%H%M%S)-$$-$(od -An -N2 -tu2 /dev/urandom | tr -d " ")"
fi
SALIDA="$WT_REAL/.delegacion/$DELEG_ID"
[ -e "$SALIDA" ] && abortar "el delegation_id ya existe: no se reutiliza ni se sobrescribe evidencia ($DELEG_ID)"
# El directorio se crea DESPUES de verificar el objetivo: antes, un review abortado dejaba una
# carpeta vacia y consumia un delegation_id sin producir evidencia. Lo señalo la auditoria.
# RUTA COMUN: el objetivo se verifica ANTES de cualquier invocacion de Codex, sea cual sea la
# operacion. Antes solo protegia `review`, asi que `exec` —la accion por defecto— aceptaba un
# worktree de AURA. No se duplica la comprobacion en tres sitios: se hace una vez, aqui.
verificar_objetivo "$WT_REAL" || exit $?
mkdir -p "$SALIDA"
if [ "$SOLO_VERIFICAR" = "1" ]; then
  verificar_objetivo "$WT_REAL" || exit $?
  echo "OK · objetivo demostrado: $WT_REAL (Codex NO invocado)"; exit 0
fi

SELLO=$(date -Iseconds)
JSONL="$SALIDA/events.jsonl"; ULTIMO="$SALIDA/last-message.txt"; META="$SALIDA/manifest.json"

# --- invocación ---------------------------------------------------------------------------------
COMUNES=(--ignore-user-config --sandbox workspace-write --cd "$WT_REAL" --json)
set +e
case "$ACCION" in
  exec)   [ -n "$ENCARGO" ] || abortar "falta --encargo"
          cp "$ENCARGO" "$SALIDA/prompt.txt" 2>/dev/null || true
          "$CODEX" exec "${COMUNES[@]}" -o "$ULTIMO" < "$ENCARGO" > "$JSONL" 2>"$SALIDA/stderr.txt" ;;
  resume) [ -n "$ENCARGO" ] || abortar "falta --encargo"
          cp "$ENCARGO" "$SALIDA/prompt.txt" 2>/dev/null || true
          # `codex exec resume` NO acepta los mismos flags que `codex exec`: rechaza --sandbox con
          # «unexpected argument». Los comunes van ANTES del subcomando (medido, 0.147.0).
          "$CODEX" exec "${COMUNES[@]}" -o "$ULTIMO" resume "$SESION" - < "$ENCARGO" > "$JSONL" 2>"$SALIDA/stderr.txt" ;;
  review) # `codex review` NO acepta --cd ni -C: se comprobo en su --help completo. `--base` y
          # `--commit` eligen el RANGO, no el REPOSITORIO. El repo lo decide el cwd, y punto.
          #
          # Por eso el objetivo no se supone: se DEMUESTRA. La invocacion ocurre en un SUBSHELL —el
          # cwd del proceso padre no cambia— y dentro se verifica con `git rev-parse` que el repo
          # detectado es exactamente el worktree autorizado. Si no coincide, no se invoca a Codex.
          # Asi fue como el MVP leyo AURA por accidente: review heredo el cwd sin que nadie lo comprobara.
          ( cd "$WT_REAL" && "$CODEX" review --uncommitted ) > "$JSONL" 2>"$SALIDA/stderr.txt" ;;
esac
CODIGO=$?
set -e

# --- verificación: exito de EJECUCION, que no es exito TECNICO ----------------------------------
# Codex no expone `is_error`. La señal es el evento terminal `turn.completed` junto a exit 0. Que
# Codex termine bien NO significa que el codigo este bien: eso lo decide Claude ejecutando pruebas.
# --- Sandbox: MEDIDO, no declarado ---------------------------------------------------------------
# El literal fijo anterior era falso y hay prueba material: un residuo historico declaraba
# «workspace-write» mientras su propio stderr reportaba «read-only». Aqui se lee lo que Codex dice
# haber usado; si no lo dice, se registra UNKNOWN y NO se infiere del valor solicitado.
# SEÑAL OBLIGATORIA vs OPCIONAL. Medido con Codex REAL: `codex exec --json` NO emite la linea
# `sandbox:`; `codex review` SI. Antes, el grep sin coincidencia devolvia 1 y bajo `pipefail` MATABA
# el wrapper, perdiendo el manifest entero aunque Codex hubiera terminado con exito. Una señal
# ausente NO puede ser un crash ni un valor inventado: se clasifica.
#
# El `if` aisla el fallo del pipeline sin recurrir a `|| true` indiscriminado, que ocultaria tambien
# los errores que SI deben abortar.
if SB_LINEA=$(sed 's/\x1b\[[0-9;]*m//g' "$SALIDA/stderr.txt" 2>/dev/null | grep -ao 'sandbox: *[a-z-]*' | head -1); then
  SB_OBS=$(printf '%s' "$SB_LINEA" | awk '{print $2}')
else
  SB_OBS=""
fi
[ -n "$SB_OBS" ] || SB_OBS="UNKNOWN"
if [ "$ACCION" = "review" ]; then
  # `codex review` NO acepta --sandbox: no hay valor solicitado que registrar. Inventarlo seria
  # exactamente el defecto que esta correccion elimina.
  SB_REQ="NOT_APPLICABLE: codex review no acepta --sandbox"
else
  SB_REQ="workspace-write"
fi
[ "$SB_OBS" = "UNKNOWN" ] && SB_ST="UNKNOWN" || SB_ST="OBSERVED"

THREAD=$(python3 - "$JSONL" <<'PY' 2>/dev/null || true
import json,sys
for l in open(sys.argv[1]):
    try: d=json.loads(l)
    except Exception: continue
    if d.get("type")=="thread.started": print(d.get("thread_id","")); break
PY
)
TERMINAL=$(grep -c '"type":"turn.completed"' "$JSONL" 2>/dev/null) || TERMINAL=0

DELEG_ID="$DELEG_ID" PARENT_ID="$PARENT_ID" SESION_PREV="$SESION" SB_REQ="$SB_REQ" SB_OBS="$SB_OBS" SB_ST="$SB_ST" python3 - "$META" "$SELLO" "$MODELO" "$WT_REAL" "$CODIGO" "$THREAD" "$TERMINAL" "$ACCION" "${ENCARGO:-}" <<'PY'
import json, sys, pathlib
meta, sello, modelo, wt, codigo, thread, terminal, accion, encargo = sys.argv[1:10]
d = {"instante": sello, "accion": accion, "worktree": wt,
     # El campo literal `sandbox` se ELIMINA: afirmaba un estado efectivo sin medirlo y podia
     # contradecir a sandbox_effective dentro del mismo documento. Solo quedan los cuatro campos
     # separados, cada uno con su significado exacto.
     "operation": accion,
     "parent_delegation_id": __import__("os").environ.get("PARENT_ID") or None,
     "previous_thread_id": __import__("os").environ.get("SESION_PREV") or None,
     "agent": "Codex", "codex_version": modelo,
     "sandbox_requested": __import__("os").environ.get("SB_REQ","UNKNOWN"),
     "sandbox_effective": __import__("os").environ.get("SB_OBS","UNKNOWN"),
     "sandbox_source": "stderr de Codex" if __import__("os").environ.get("SB_OBS","UNKNOWN") != "UNKNOWN" else "no observable",
     "sandbox_status": __import__("os").environ.get("SB_ST","NO_MEDIBLE"),
     "auth_method": "ChatGPT account",
     "model_requested": "UNKNOWN — la instalacion rechaza -m con esta autenticacion (medido)",
     "model_reported": "UNKNOWN — Codex no lo emite en su salida (medido)",
     "nota_events_jsonl": ("en la accion `review` este fichero NO contiene JSONL: `codex review` no "
       "soporta --json y emite texto plano. Limitacion conocida de la herramienta, no defecto del wrapper."),
     "nota_UNKNOWN": "UNKNOWN no es PASS ni FAILURE: es «no verificable con esta instalacion».",
     "coste": "UNKNOWN — Codex reporta tokens, no dinero.",
     "exit_code": int(codigo), "thread_id": thread or None,
     "turn_completed": int(terminal) > 0,
     "encargo": encargo or None}
pathlib.Path(meta).write_text(json.dumps(d, ensure_ascii=False, indent=2))
PY

[ "$CODIGO" -eq 0 ]            || abortar "codex termino con exit $CODIGO (ver $SALIDA/stderr.txt)"
[ "$ACCION" = "review" ] || [ -n "$THREAD" ] || abortar "no hay thread_id: la ejecucion no es trazable"
[ "$ACCION" = "review" ] || [ "$TERMINAL" -gt 0 ] || abortar "no hay evento turn.completed: la sesion no termino"
[ -s "$JSONL" ]                || abortar "el JSONL esta vacio"

echo "OK · id=$DELEG_ID accion=$ACCION thread=${THREAD:-n/a} exit=$CODIGO"
echo "   evidencia en $SALIDA/ (manifest.json · events.jsonl · last-message.txt · stderr.txt)"

# ================================================================================================
# REGLA DEL MVP sobre SIMULADORES (CEO, 2026-08-29 — tras el incidente que costo una reauditoria)
# ================================================================================================
# NO se usa un simulador para afirmar comportamiento que dependa de una señal especifica de Codex
# real. Los dobles sirven solo para probar logica interna que no dependa de comportamiento externo
# no reproducido.
#
# Si una garantia depende del formato real de stderr, de los eventos JSONL, de los exit codes, o del
# comportamiento de `resume` o `review`, DEBE existir al menos una prueba con CODEX REAL.
#
# Por que esta escrito aqui y no solo en un informe: un simulador fabricaba una linea `sandbox:` que
# `codex exec` NO emite. Cuatro RED daban PASS sobre un Codex que no existe, y el wrapper moria por
# `pipefail` en produccion perdiendo el manifest entero. El doble no fallo: mintio.
