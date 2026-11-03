#!/usr/bin/env bash
# RED · GRAVE-1 · los tres casos que deben distinguirse, y que no pueden confundirse entre si:
#   A · Codex termina BIEN pero no reporta sandbox -> evidencia conservada + sandbox UNKNOWN
#   B · Codex termina con ERROR                    -> evidencia conservada + exit!=0 + FAILURE
#   C · el wrapper falla ANTES de Codex            -> FAILURE con su causa, sin evidencia de ejecucion
# El caso A con CODEX REAL vive en test_red_señales_reales.sh: la ausencia de la linea `sandbox:` en
# `codex exec` es una señal que solo el Codex real produce y no se sustituye por un doble. Aqui se
# cubren A (forma), B y C, cuyo comportamiento NO depende de una señal exclusiva de Codex real.
S="${S:?}"; f=0
ok(){ printf "  %-54s %s\n" "$1" "$2"; }; mal(){ printf "  %-54s %s <-- FALLO\n" "$1" "$2"; f=$((f+1)); }
D=$(mktemp -d); trap 'rm -rf "$D"' EXIT; mkdir -p "$D/bin" "$D/r"
( cd "$D/r" && git init -q . && git config user.email t@t && git config user.name t && echo x > a.txt && git add -A && git commit -qm b )
echo "t" > "$D/e.txt"
doble(){ printf '#!/usr/bin/env bash\ncase "$1" in exec|review) echo %s; echo %s; %s exit %s;; esac\nexit 0\n' \
  "'{\"type\":\"thread.started\",\"thread_id\":\"z\"}'" "'{\"type\":\"turn.completed\"}'" "$2" "$1" > "$D/bin/codex"; chmod +x "$D/bin/codex"; }
campo(){ python3 -c "import json;print(json.load(open('$1')).get('$2','AUSENTE'))" 2>/dev/null; }

# --- A · termina bien, SIN linea sandbox ---
rm -rf "$D/r/.delegacion"; doble 0 ''
r=$(cd /var/tmp && PATH="$D/bin:$PATH" "$S" --worktree "$D/r" --encargo "$D/e.txt" 2>&1 | head -1)
I=$(ls -1 "$D/r/.delegacion" 2>/dev/null | head -1); MAN="$D/r/.delegacion/$I/manifest.json"
case "$r" in OK*) ok "A · exito sin señal: no aborta" "OK" ;; *) mal "A · exito sin señal: no aborta" "$r" ;; esac
[ -s "$MAN" ] && ok "A · manifest conservado" "ok" || mal "A · manifest conservado" "falta"
[ "$(campo "$MAN" sandbox_effective)" = "UNKNOWN" ] && ok "A · sandbox_effective UNKNOWN" "ok" || mal "A · sandbox_effective UNKNOWN" "$(campo "$MAN" sandbox_effective)"
[ "$(campo "$MAN" sandbox_status)" = "UNKNOWN" ] && ok "A · sandbox_status UNKNOWN" "ok" || mal "A · sandbox_status UNKNOWN" "$(campo "$MAN" sandbox_status)"
# --- B · termina con ERROR ---
rm -rf "$D/r/.delegacion"; doble 7 'echo "sandbox: workspace-write" >&2;'
r=$(cd /var/tmp && PATH="$D/bin:$PATH" "$S" --worktree "$D/r" --encargo "$D/e.txt" 2>&1 | head -1)
I=$(ls -1 "$D/r/.delegacion" 2>/dev/null | head -1); MAN="$D/r/.delegacion/$I/manifest.json"
case "$r" in FAILURE*) ok "B · error de Codex -> FAILURE" "ok" ;; *) mal "B · error de Codex -> FAILURE" "$r" ;; esac
[ "$(campo "$MAN" exit_code)" = "7" ] && ok "B · exit_code conservado" "7" || mal "B · exit_code conservado" "$(campo "$MAN" exit_code)"
[ -s "$D/r/.delegacion/$I/stderr.txt" ] && ok "B · evidencia conservada pese al error" "ok" || mal "B · evidencia conservada pese al error" "falta"
[ "$(campo "$MAN" sandbox_effective)" = "workspace-write" ] && ok "B · sandbox medido, no inventado" "workspace-write" || mal "B · sandbox medido" "$(campo "$MAN" sandbox_effective)"
# --- C · el wrapper falla antes de Codex ---
rm -f "$D/INVOCADO"; doble 0 "touch $D/INVOCADO;"
r=$(cd /var/tmp && PATH="$D/bin:$PATH" "$S" --worktree "$D/no_existe" --encargo "$D/e.txt" 2>&1 | head -1)
case "$r" in FAILURE*) ok "C · falla antes de Codex -> FAILURE" "ok" ;; *) mal "C · falla antes de Codex" "$r" ;; esac
[ -e "$D/INVOCADO" ] && mal "C · Codex NO fue invocado" "SE INVOCO" || ok "C · Codex NO fue invocado" "no se invoco"
[ $f -eq 0 ] && { echo "PASS"; exit 0; } || { echo "FAIL · $f"; exit 1; }
