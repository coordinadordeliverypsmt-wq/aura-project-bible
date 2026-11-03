#!/usr/bin/env bash
# RED · GRAVE-A · una señal OPCIONAL ausente no puede matar la ejecucion ni perder la evidencia.
#
# REGLA DEL MVP (CEO 2026-08-29, tras el incidente): NO se usa un simulador para afirmar
# comportamiento que depende de una señal especifica de Codex real. Esta prueba invoca a CODEX REAL
# porque la garantia depende del formato real de su stderr — y fue precisamente un simulador que
# fabricaba una linea inexistente lo que hizo que 4 RED dieran PASS sobre un Codex que no existe.
#
# HECHO MEDIDO: `codex exec --json` NO emite la linea `sandbox:`; `codex review` (sin --json) SI.
S="${S:?}"; f=0
ok(){ printf "  %-54s %s\n" "$1" "$2"; }; mal(){ printf "  %-54s %s <-- FALLO\n" "$1" "$2"; f=$((f+1)); }
W=$(mktemp -d); trap 'rm -rf "$W"' EXIT
( cd "$W" && git init -q . && git config user.email t@t && git config user.name t && echo base > a.txt && git add -A && git commit -qm b )
echo "Di unicamente la palabra: listo. No hagas nada mas." > "$W/e.txt"
salida=$(cd /var/tmp && "$S" --worktree "$W" --encargo "$W/e.txt" 2>&1); codigo=$?
ID=$(echo "$salida" | grep -o 'id=[^ ]*' | cut -d= -f2)
[ "$codigo" -eq 0 ] && ok "el wrapper NO muere: exit 0" "ok" || mal "el wrapper NO muere: exit 0" "exit $codigo · $salida"
[ -n "$ID" ] && ok "emite delegation_id" "$ID" || { mal "emite delegation_id" "ninguno"; echo "FAIL · $((f))"; exit 1; }
MAN="$W/.delegacion/$ID/manifest.json"
[ -s "$MAN" ] && ok "manifest.json ESCRITO pese a la señal ausente" "ok" || mal "manifest.json ESCRITO pese a la señal ausente" "no existe"
g(){ python3 -c "import json;print(json.load(open('$MAN')).get('$1','AUSENTE'))" 2>/dev/null; }
[ -n "$(g thread_id)" ] && [ "$(g thread_id)" != "None" ] && ok "conserva thread_id" "$(g thread_id)" || mal "conserva thread_id" "$(g thread_id)"
[ "$(g exit_code)" = "0" ] && ok "conserva exit_code" "0" || mal "conserva exit_code" "$(g exit_code)"
for art in events.jsonl last-message.txt stderr.txt prompt.txt; do
  [ -e "$W/.delegacion/$ID/$art" ] && ok "conserva $art" "ok" || mal "conserva $art" "falta"; done
# la señal ausente se clasifica, no se inventa
sb=$(sed 's/\x1b\[[0-9;]*m//g' "$W/.delegacion/$ID/stderr.txt" | grep -c 'sandbox:' || true)
ok "linea 'sandbox:' presente en stderr de exec (Codex REAL)" "$sb ocurrencias"
[ "$(g sandbox_effective)" = "UNKNOWN" ] && ok "sandbox_effective = UNKNOWN (no inventado)" "ok" || mal "sandbox_effective = UNKNOWN" "$(g sandbox_effective)"
[ "$(g sandbox_status)" = "UNKNOWN" ] && ok "sandbox_status = UNKNOWN" "ok" || mal "sandbox_status = UNKNOWN" "$(g sandbox_status)"
[ $f -eq 0 ] && { echo "PASS"; exit 0; } || { echo "FAIL · $f"; exit 1; }
