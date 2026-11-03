#!/usr/bin/env bash
# RED · M17 — «Codex exit != 0 -> wrapper FAILURE», ejercida SIN enmascaramiento.
#
# El caso del encargo vacio NO ejercia M17: producia 0 eventos, luego no habia thread_id y el
# wrapper abortaba por la barrera «no hay thread_id». Otra barrera mataba al mutante.
#
# CONDICION USADA (Codex REAL, contrato ACTUAL, coste 0): un --encargo que excede el limite de
# 1048576 caracteres. Codex emite `thread.started` (hay thread_id) y DESPUES falla en `turn/start`
# con exit 1. La API rechaza por LONGITUD, no procesa tokens: no hay coste.
#
# COMO SE EVITA EL ENMASCARAMIENTO: con exit!=0 tampoco hay `turn.completed`, asi que esa tercera
# barrera tambien abortaria. Por eso la RED no asevera «aborto», sino LA CAUSA EXACTA del aborto.
# Si se degrada la guarda del exit_code, el wrapper sigue abortando pero POR OTRO MOTIVO, y esta
# RED lo detecta. Es la leccion de las barreras redundantes, aplicada.
set -u
AURA_ROOT="79018b3b49da782a57367257ca1f1bd597c076cb"
D="$(cd "$(dirname "$0")" && pwd)"; S="${S:-$D/delegar.sh}"; M=/tmp/codex-mvp/m17-red
OK=0; KO=0
v(){ if [ "$2" = "$3" ]; then OK=$((OK+1)); echo "  PASS · $1"; else KO=$((KO+1)); echo "  FAIL · $1 (esperado=$3 real=$2)"; fi; }

rm -rf "$M"; mkdir -p "$M"
git init -q "$M" && git -C "$M" config user.email t@t && git -C "$M" config user.name t
echo x > "$M/a"; git -C "$M" add -A; git -C "$M" commit -qm base
R=$(git -C "$M" rev-list --max-parents=0 HEAD | head -1)
[ "$R" = "$AURA_ROOT" ] && { echo "ABORTAR: el fixture ES AURA"; exit 1; }
[ -n "$R" ] || { echo "ABORTAR: fixture no es repo git"; exit 1; }
echo "  fixture sintetico verificado: ${R:0:12} != AURA"

python3 -c "open('$M/enorme.txt','w').write('Repite esta frase de relleno sin analizarla. ' * 400000)"
ID="red-m17-$$"
"$S" --worktree "$M" --encargo "$M/enorme.txt" --delegacion-id "$ID" > "$M/o.txt" 2> "$M/e.txt"
RC=$?
EV="$M/.delegacion/$ID"

v "el wrapper devuelve FAILURE (exit 91)" "$RC" "91"
# LA ASERCION CAUSAL: el motivo del FAILURE es el exit code de Codex, no otra barrera.
v "el motivo del FAILURE es el exit code de Codex" \
  "$(grep -c 'codex termino con exit 1' "$M/e.txt")" "1"
v "NO aborta por la barrera de thread_id" "$(grep -c 'no hay thread_id' "$M/e.txt")" "0"
# La precondicion que faltaba: se llego lo bastante lejos como para tener hilo.
v "existe thread.started en los eventos reales" \
  "$(grep -c '"type":"thread.started"' "$EV/events.jsonl")" "1"
v "el manifest conserva un thread_id real (no null)" \
  "$(python3 -c "import json;print('si' if json.load(open('$EV/manifest.json'))['thread_id'] else 'no')")" "si"
v "el manifest conserva el exit_code real" \
  "$(python3 -c "import json;print(json.load(open('$EV/manifest.json'))['exit_code'])")" "1"
v "turn_completed es false: la sesion no termino" \
  "$(python3 -c "import json;print(json.load(open('$EV/manifest.json'))['turn_completed'])")" "False"
v "stderr real de Codex conservado" \
  "$(grep -c 'turn/start' "$EV/stderr.txt")" "1"

echo "  --- RED M17: $OK PASS · $KO FAIL"
[ "$KO" -eq 0 ]
