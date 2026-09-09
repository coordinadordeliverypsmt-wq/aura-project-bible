#!/usr/bin/env bash
# RED · GRAVE-2 · la identidad de AURA es el ROOT COMMIT del repositorio objetivo, nunca la
# ubicacion del wrapper. Un repo sintetico legitimo debe aceptarse aunque el wrapper viva dentro.
# Solo --solo-verificar: Codex jamas se invoca. Fixtures bajo /tmp/codex-mvp/.
S="${S:?}"; f=0
ok(){ printf "  %-56s %s\n" "$1" "$2"; }; mal(){ printf "  %-56s %s <-- FALLO\n" "$1" "$2"; f=$((f+1)); }
M=/tmp/codex-mvp/g2; rm -rf "$M"; mkdir -p "$M/fuera"
mkdir -p "$M/repo/bin" && ( cd "$M/repo" && git init -q . && git config user.email t@t && git config user.name t && echo x > a.txt && git add -A && git commit -qm b )
R=$(git -C "$M/repo" rev-list --max-parents=0 HEAD | head -1)
[ "$R" != "79018b3b49da782a57367257ca1f1bd597c076cb" ] && ok "precondicion: root commit != AURA" "${R:0:12}..." || { echo "FAIL: colision"; exit 1; }
for x in docs adr decisiones entorno/control-plane; do [ -e "$M/repo/$x" ] && { mal "precondicion: sin marcadores" "tiene $x"; }; done
ok "precondicion: sin marcadores prohibidos" "ninguno"
cp "$S" "$M/repo/bin/w.sh"; cp "$S" "$M/fuera/w.sh"
p(){ (cd /var/tmp && "$1" --worktree "$M/repo" --review --solo-verificar 2>&1 | head -1); }
a=$(p "$M/repo/bin/w.sh"); b=$(p "$M/fuera/w.sh")
case "$a" in FAILURE*) mal "wrapper DENTRO del objetivo: aceptado" "$a" ;; *) ok "wrapper DENTRO del objetivo: aceptado" "OK" ;; esac
case "$b" in FAILURE*) mal "wrapper FUERA del objetivo: aceptado" "$b" ;; *) ok "wrapper FUERA del objetivo: aceptado" "OK" ;; esac
[ "${a%% *}" = "${b%% *}" ] && ok "el resultado NO depende de donde vive el wrapper" "identico" || mal "el resultado NO depende de donde vive el wrapper" "difieren"
[ $f -eq 0 ] && { echo "PASS"; exit 0; } || { echo "FAIL · $f"; exit 1; }
