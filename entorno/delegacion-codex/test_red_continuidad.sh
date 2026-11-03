#!/usr/bin/env bash
# RED · la identidad de una delegacion pertenece al WRAPPER, no a Codex.
# Se midio que `resume` puede conservar o cambiar el thread_id: la continuidad no puede depender de el.
S="${S:?}"; M=/tmp/codex-mvp; f=0
ok(){ printf "  %-52s %s\n" "$1" "$2"; }; mal(){ printf "  %-52s %s <-- FALLO\n" "$1" "$2"; f=$((f+1)); }
A="$M/authorized"; rm -rf "$A/.delegacion"
printf '#!/usr/bin/env bash\nT=${THREAD_SIM:-t1}\necho "{\\"type\\":\\"thread.started\\",\\"thread_id\\":\\"$T\\"}"\necho "{\\"type\\":\\"turn.completed\\"}"\necho "sandbox: workspace-write" >&2\nexit 0\n' > "$M/bin/codex"; chmod +x "$M/bin/codex"
echo "encargo inicial" > "$A/e1.txt"; echo "continuacion" > "$A/e2.txt"
D1=$(cd /var/tmp && THREAD_SIM=t1 PATH="$M/bin:$PATH" "$S" --worktree "$A" --encargo "$A/e1.txt" 2>&1 | grep -o 'id=[^ ]*' | cut -d= -f2)
# resume con thread DISTINTO: es el caso que rompe la continuidad si depende del thread_id
D2=$(cd /var/tmp && THREAD_SIM=t2 PATH="$M/bin:$PATH" "$S" --worktree "$A" --encargo "$A/e2.txt" --resume t1 --parent "$D1" 2>&1 | grep -o 'id=[^ ]*' | cut -d= -f2)
[ -n "$D1" ] && [ -n "$D2" ] || { echo "FAIL · sin delegation_id"; exit 1; }
m2="$A/.delegacion/$D2/manifest.json"
g(){ python3 -c "import json;print(json.load(open('$m2')).get('$1','AUSENTE'))" 2>/dev/null; }
[ "$(g parent_delegation_id)" = "$D1" ] && ok "resume enlaza con la delegacion original" "$D1" || mal "resume enlaza con la delegacion original" "$(g parent_delegation_id)"
[ "$(g previous_thread_id)" = "t1" ] && ok "registra previous_thread_id" "t1" || mal "registra previous_thread_id" "$(g previous_thread_id)"
[ "$(g thread_id)" = "t2" ] && ok "registra el thread_id NUEVO" "t2" || mal "registra el thread_id NUEVO" "$(g thread_id)"
[ "$(g operation)" = "resume" ] && ok "registra la operacion" "resume" || mal "registra la operacion" "$(g operation)"
[ -s "$A/.delegacion/$D2/prompt.txt" ] && ok "resume conserva su encargo" "ok" || mal "resume conserva su encargo" "falta"
# la continuidad debe reconstruirse AUNQUE el thread cambie
[ "$(g previous_thread_id)" != "$(g thread_id)" ] && ok "continuidad NO depende de que el thread coincida" "t1 -> t2" || mal "continuidad NO depende del thread" "iguales"
[ $f -eq 0 ] && { echo "PASS"; exit 0; } || { echo "FAIL · $f"; exit 1; }
