#!/usr/bin/env bash
# RED · un SKIP no puede presentarse como PASS.
#
# DEFECTO QUE REPRODUCE (auditoria independiente 2026-08-24). En `test_red_identidad_aura.sh`, el
# CASO PURO DE IDENTIDAD —el unico que ejerce el rechazo por COMMIT RAIZ, y con el la garantia que
# protege M11— se construye con `git worktree add`. Si esa preparacion falla, la RED imprime
# «SKIP · no se pudo crear el worktree» y NO incrementa el contador de fallos: termina en PASS
# habiendo perdido en silencio su caso central.
#
# PASS != SKIP != FAIL. Que el sujeto no pueda prepararse significa que la garantia NO SE EJERCIO,
# y eso jamas puede presentarse como exito.
#
# COMO SE FUERZA LA CONDICION, sin tocar AURA: se antepone en PATH un `git` que delega en el real
# para TODO salvo `worktree add`, donde falla. Asi se reproduce exactamente el escenario sin romper
# el resto de la prueba ni modificar ningun repositorio.
set -u
D="$(cd "$(dirname "$0")" && pwd)"; f=0
ok(){ printf "  %-58s %s\n" "$1" "$2"; }; mal(){ printf "  %-58s %s <-- FALLO\n" "$1" "$2"; f=$((f+1)); }
T=$(mktemp -d); trap 'rm -rf "$T"' EXIT
REAL_GIT=$(command -v git)
mkdir -p "$T/bin"
cat > "$T/bin/git" <<GITEOF
#!/usr/bin/env bash
# delega en el git real salvo en \`worktree add\`, que se hace fallar a proposito
# worktree add puede venir precedido de -C ruta, asi que se busca la pareja en CUALQUIER
# posicion de los argumentos. Detectarla solo en los dos primeros dejaba pasar git -C X worktree add.
prev=""
for a in "\$@"; do
  if [ "\$prev" = "worktree" ] && [ "\$a" = "add" ]; then
    echo "fatal: (simulado) no se puede crear el worktree" >&2; exit 128
  fi
  prev="\$a"
done
exec "$REAL_GIT" "\$@"
GITEOF
chmod +x "$T/bin/git"

echo "  --- se fuerza el fallo de preparacion del sujeto ---"
SAL="$T/salida.txt"
PATH="$T/bin:$PATH" S="${S:-$D/delegar.sh}" timeout 300 "$D/test_red_identidad_aura.sh" </dev/null > "$SAL" 2>&1
RC=$?
VER=$(tail -1 "$SAL")

grep -q 'SKIP\|NO_EJERCIDA\|NOT_EXERCISED' "$SAL" \
  && ok "la RED detecta que no pudo preparar el sujeto" "$(grep -oE 'SKIP|NO_EJERCIDA|NOT_EXERCISED' "$SAL"|head -1)" \
  || mal "la RED detecta que no pudo preparar el sujeto" "no lo menciona"

# EL CORAZON: con el caso central sin ejercer, el veredicto NO puede ser PASS.
case "$VER" in
  PASS) mal "una garantia no ejercida NO se presenta como PASS" "veredicto=PASS (exit $RC)" ;;
  *)    ok  "una garantia no ejercida NO se presenta como PASS" "veredicto=$VER (exit $RC)" ;;
esac
[ "$RC" -ne 0 ] && ok "el exit code refleja que no se ejercio la garantia" "exit $RC" \
                || mal "el exit code refleja que no se ejercio la garantia" "exit 0"

echo "  --- y sin forzar el fallo, la RED debe seguir pasando ---"
S="${S:-$D/delegar.sh}" timeout 300 "$D/test_red_identidad_aura.sh" </dev/null >"$T/normal.txt" 2>&1
[ $? -eq 0 ] && ok "sin interferencia la RED pasa (no se rompio nada)" "PASS" \
             || mal "sin interferencia la RED pasa (no se rompio nada)" "$(tail -1 "$T/normal.txt")"

[ $f -eq 0 ] && { echo "PASS"; exit 0; } || { echo "FAIL · $f"; exit 1; }
