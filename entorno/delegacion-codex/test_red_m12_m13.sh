#!/usr/bin/env bash
# RED · aisla M12 (identidad del REPOSITORIO, no del wrapper) y M13 (verificar_objetivo es la UNICA
# barrera que decide). Ninguna prueba invoca Codex sobre AURA: los objetivos son sinteticos y hay un
# centinela que distingue `codex --version` (consulta local) de una invocacion de trabajo.
S="${S:?}"; f=0
ok(){ printf "  %-56s %s\n" "$1" "$2"; }; mal(){ printf "  %-56s %s <-- FALLO\n" "$1" "$2"; f=$((f+1)); }
D=$(mktemp -d); trap 'rm -rf "$D"' EXIT
CENT="$D/INVOCADO"; mkdir -p "$D/bin"
cat > "$D/bin/codex" <<CENTINELA
#!/usr/bin/env bash
case "\$1" in exec|review) touch "$CENT" ;; esac
echo '{"type":"thread.started","thread_id":"c"}'; echo '{"type":"turn.completed"}'
echo "sandbox: workspace-write" >&2; exit 0
CENTINELA
chmod +x "$D/bin/codex"

# ---------- M12 · fixture: el WRAPPER vive DENTRO de un repo sintetico ----------
# Si la identidad se derivase de `dirname "$0"`, seria la del repo sintetico que aloja al wrapper, y
# ese mismo repo quedaria rechazado "por ser AURA". Con la identidad correcta —del repositorio
# OBJETIVO— el sintetico se acepta. El objetivo NUNCA es AURA.
mkdir -p "$D/host"; ( cd "$D/host" && git init -q . && git config user.email t@t && git config user.name t && echo x > a.txt && git add -A && git commit -qm b )
cp "$S" "$D/host/wrapper.sh"; cp "$(dirname "$S")/verificar.sh" "$D/host/verificar.sh" 2>/dev/null
r=$(cd /var/tmp && J="$D/host" PATH="$D/bin:$PATH" "$D/host/wrapper.sh" --worktree "$D/host" --review --solo-verificar 2>&1 | head -1)
case "$r" in FAILURE*) mal "M12 · wrapper alojado en el objetivo: se acepta" "$r" ;; *) ok "M12 · wrapper alojado en el objetivo: se acepta" "OK" ;; esac

# ---------- M13 · fixture donde verificar_objetivo es la UNICA barrera ----------
# Subdirectorio de un repo sintetico: es git valido, no es AURA, no tiene marcadores prohibidos, no
# esta en relacion de ruta con el cwd. La UNICA condicion que lo rechaza es que el toplevel del repo
# no coincide con el worktree declarado — es decir, verificar_objetivo().
mkdir -p "$D/repo/sub"; ( cd "$D/repo" && git init -q . && git config user.email t@t && git config user.name t && echo y > sub/b.txt && git add -A && git commit -qm b )
rm -f "$CENT"
r=$(cd /var/tmp && PATH="$D/bin:$PATH" "$S" --worktree "$D/repo/sub" --review 2>&1 | head -1)
case "$r" in FAILURE*) ok "M13 · subdirectorio rechazado por verificar_objetivo" "FAILURE" ;; *) mal "M13 · subdirectorio rechazado por verificar_objetivo" "$r" ;; esac
[ -e "$CENT" ] && mal "M13 · Codex NO fue invocado" "SE INVOCO" || ok "M13 · Codex NO fue invocado" "no se invoco"
[ $f -eq 0 ] && { echo "PASS"; exit 0; } || { echo "FAIL · $f"; exit 1; }
