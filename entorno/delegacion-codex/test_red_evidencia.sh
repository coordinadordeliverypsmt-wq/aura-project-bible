#!/usr/bin/env bash
# RED · UNA EJECUCION = UNA EVIDENCIA AISLADA.
# No basta con que existan dos carpetas: se comprueba CONTENIDO CRUZADO, que es lo que fallaba.
S="${S:?}"; M=/tmp/codex-mvp; f=0
ok(){ printf "  %-52s %s\n" "$1" "$2"; }; mal(){ printf "  %-52s %s <-- FALLO\n" "$1" "$2"; f=$((f+1)); }
A="$M/authorized"; rm -rf "$A/.delegacion"
# Simulador propio de ESTA prueba: compartir uno global hacia que otra RED lo sobrescribiera y este
# caso fallara por el fixture, no por la garantia.
printf '#!/usr/bin/env bash\necho "{\\"type\\":\\"thread.started\\",\\"thread_id\\":\\"sim-$$\\"}"\necho "{\\"type\\":\\"turn.completed\\"}"\necho "MARCA=${MARCA_DELEGACION:-ninguna} sandbox: workspace-write" >&2\nexit 0\n' > "$M/bin/codex"; chmod +x "$M/bin/codex"
# Dos delegaciones simuladas: el `codex` de $M/bin no consume cuota y deja marca propia.
D1=$(cd /var/tmp && PATH="$M/bin:$PATH" "$S" --worktree "$A" --review --marca DELEGACION_UNO 2>&1 | grep -o 'id=[^ ]*' | cut -d= -f2)
D2=$(cd /var/tmp && PATH="$M/bin:$PATH" "$S" --worktree "$A" --review --marca DELEGACION_DOS 2>&1 | grep -o 'id=[^ ]*' | cut -d= -f2)
[ -n "$D1" ] && [ -n "$D2" ] || { echo "FAIL · no se obtuvieron delegation_id"; exit 1; }
[ "$D1" != "$D2" ] && ok "delegation_id distintos" "$D1 / $D2" || mal "delegation_id distintos" "iguales"
for d in "$D1" "$D2"; do [ -d "$A/.delegacion/$d" ] || mal "existe .delegacion/$d" "no"; done
# CONTENIDO CRUZADO: A no puede contener rastro de B, ni al reves
grep -rq DELEGACION_DOS "$A/.delegacion/$D1" 2>/dev/null && mal "A NO contiene eventos de B" "contaminado" || ok "A NO contiene eventos de B" "limpio"
grep -rq DELEGACION_UNO "$A/.delegacion/$D2" 2>/dev/null && mal "B NO contiene eventos de A" "contaminado" || ok "B NO contiene eventos de A" "limpio"
grep -rq DELEGACION_UNO "$A/.delegacion/$D1" 2>/dev/null && ok "A conserva SU marca tras ejecutar B" "intacta" || mal "A conserva SU marca tras ejecutar B" "PERDIDA"
for art in manifest.json stderr.txt events.jsonl; do
  [ -s "$A/.delegacion/$D1/$art" ] && ok "A conserva $art" "ok" || mal "A conserva $art" "falta o vacio"; done
# reutilizar un delegation_id debe FALLAR
r=$(cd /var/tmp && PATH="$M/bin:$PATH" "$S" --worktree "$A" --review --delegacion-id "$D1" 2>&1 | head -1)
case "$r" in FAILURE*) ok "reutilizar delegation_id -> FAILURE" "ok" ;; *) mal "reutilizar delegation_id -> FAILURE" "$r" ;; esac
[ $f -eq 0 ] && { echo "PASS"; exit 0; } || { echo "FAIL · $f"; exit 1; }
