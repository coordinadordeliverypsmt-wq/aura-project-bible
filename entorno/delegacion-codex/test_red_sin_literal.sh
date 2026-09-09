#!/usr/bin/env bash
# RED · GRAVE-B · el manifest NO puede contener un campo `sandbox` literal que afirme un estado
# efectivo. Solo los cuatro campos separados: requested/effective/source/status.
S="${S:?}"; M=/tmp/codex-mvp; f=0
ok(){ printf "  %-54s %s\n" "$1" "$2"; }; mal(){ printf "  %-54s %s <-- FALLO\n" "$1" "$2"; f=$((f+1)); }
A="$M/authorized"; rm -rf "$A/.delegacion"; mkdir -p "$M/bin"
printf '#!/usr/bin/env bash\necho "{\\"type\\":\\"thread.started\\",\\"thread_id\\":\\"x\\"}"\necho "{\\"type\\":\\"turn.completed\\"}"\necho "sandbox: read-only" >&2\nexit 0\n' > "$M/bin/codex"; chmod +x "$M/bin/codex"
ID=$(cd /var/tmp && PATH="$M/bin:$PATH" "$S" --worktree "$A" --review 2>&1 | grep -o 'id=[^ ]*' | cut -d= -f2)
[ -n "$ID" ] || { echo "FAIL · sin id"; exit 1; }
MAN="$A/.delegacion/$ID/manifest.json"
tiene=$(python3 -c "import json;print('SI' if 'sandbox' in json.load(open('$MAN')) else 'NO')" 2>/dev/null)
[ "$tiene" = "NO" ] && ok "NO existe el campo literal 'sandbox'" "ok" || mal "NO existe el campo literal 'sandbox'" "existe con valor $(python3 -c "import json;print(json.load(open('$MAN')).get('sandbox'))")"
for c in sandbox_requested sandbox_effective sandbox_source sandbox_status; do
  v=$(python3 -c "import json;print(json.load(open('$MAN')).get('$c','AUSENTE'))" 2>/dev/null)
  [ "$v" != "AUSENTE" ] && ok "existe $c" "$v" || mal "existe $c" "AUSENTE"; done
r=$(python3 -c "import json;print(json.load(open('$MAN')).get('sandbox_requested'))" 2>/dev/null)
case "$r" in *NOT_APPLICABLE*|*"no aplica"*) ok "review: requested = NOT_APPLICABLE" "$r" ;; *) mal "review: requested = NOT_APPLICABLE" "$r" ;; esac
[ $f -eq 0 ] && { echo "PASS"; exit 0; } || { echo "FAIL · $f"; exit 1; }
