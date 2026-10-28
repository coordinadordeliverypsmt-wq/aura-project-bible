#!/usr/bin/env bash
# RED · el manifest no puede DECLARAR un sandbox que no ha medido.
# Se compara contra la EVIDENCIA REAL (stderr de Codex), no contra el valor esperado: esa es la
# diferencia entre medir y suponer. El residuo historico lo demostro en los hechos — declaraba
# «workspace-write» mientras su propio stderr reportaba «read-only».
S="${S:?}"; M=/tmp/codex-mvp; f=0
ok(){ printf "  %-52s %s\n" "$1" "$2"; }; mal(){ printf "  %-52s %s <-- FALLO\n" "$1" "$2"; f=$((f+1)); }
A="$M/authorized"; rm -rf "$A/.delegacion"
# El simulador reporta un sandbox CONCRETO por stderr; el manifest debe reflejarlo, no inventarlo.
printf '#!/usr/bin/env bash\necho "{\\"type\\":\\"thread.started\\",\\"thread_id\\":\\"sim\\"}"\necho "{\\"type\\":\\"turn.completed\\"}"\necho "sandbox: read-only" >&2\necho "workdir: $(pwd -P)" >&2\nexit 0\n' > "$M/bin/codex"; chmod +x "$M/bin/codex"
ID=$(cd /var/tmp && PATH="$M/bin:$PATH" "$S" --worktree "$A" --review 2>&1 | grep -o 'id=[^ ]*' | cut -d= -f2)
[ -n "$ID" ] || { echo "FAIL · sin delegation_id"; exit 1; }
MAN="$A/.delegacion/$ID/manifest.json"
obs=$(sed 's/\x1b\[[0-9;]*m//g' "$A/.delegacion/$ID/stderr.txt" | grep -ao 'sandbox: *[a-z-]*' | head -1 | awk '{print $2}')
dec=$(python3 -c "import json;d=json.load(open('$MAN'));print(d.get('sandbox_effective','AUSENTE'))" 2>/dev/null)
ok "sandbox OBSERVADO en stderr" "$obs"
[ "$dec" = "$obs" ] && ok "manifest.sandbox_effective coincide con lo observado" "$dec" || mal "manifest.sandbox_effective coincide con lo observado" "declara '$dec'"
for campo in sandbox_requested sandbox_effective sandbox_source sandbox_status; do
  v=$(python3 -c "import json;print(json.load(open('$MAN')).get('$campo','AUSENTE'))" 2>/dev/null)
  [ "$v" != "AUSENTE" ] && ok "existe $campo" "$v" || mal "existe $campo" "AUSENTE"; done
# review NO acepta --sandbox: no puede haber sandbox_requested con valor
r=$(python3 -c "import json;print(json.load(open('$MAN')).get('sandbox_requested'))" 2>/dev/null)
case "$r" in *NOT_APPLICABLE*|*"no aplica"*|*"N/A"*|*UNKNOWN*) ok "review: sandbox_requested no lo inventa" "$r" ;; *) mal "review: sandbox_requested no lo inventa" "$r" ;; esac
[ $f -eq 0 ] && { echo "PASS"; exit 0; } || { echo "FAIL · $f"; exit 1; }
