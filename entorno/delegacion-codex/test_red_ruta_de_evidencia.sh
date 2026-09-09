#!/usr/bin/env bash
# RED · la evidencia de CADA delegacion vive en SU PROPIO directorio (garantia de M1).
#
# POR QUE EXISTE ESTA RED (FASE 6, 2026-08-24). `test_red_evidencia.sh` tambien cubre esta garantia,
# pero NO PUEDE EJERCERLA bajo el mutante M1: al colapsar `SALIDA` a `.delegacion/` sin el id, la
# SEGUNDA invocacion choca con la guarda de reutilizacion (la de M2) y aborta. La RED se queda sin
# delegation_id y muere en el SETUP: ejecuta 1 de 9 aserciones y ninguna mide el aislamiento. El
# veredicto «DETECTADO» era falso — lo destapo el criterio anti-enmascaramiento.
#
# EL DISEÑO QUE LO RESUELVE, y que no necesita ninguna excepcion:
#   · cada asercion hace SU PROPIA invocacion sobre SU PROPIO fixture, asi que ninguna es «la
#     segunda» y la guarda de reutilizacion nunca se dispara;
#   · ninguna asercion aborta la RED: todas se evaluan siempre, luego el conteo se mantiene alto y
#     el veredicto sale por causalidad, no por excepcion.
#
# SEGURIDAD: fixtures sinteticos bajo /tmp/codex-mvp/. Centinela obligatorio: Codex NUNCA se invoca.
set -u
AURA_ROOT=79018b3b49da782a57367257ca1f1bd597c076cb
S="${S:?falta S=ruta a delegar.sh}"; f=0
ok(){ printf "  %-58s %s\n" "$1" "$2"; }; mal(){ printf "  %-58s %s <-- FALLO\n" "$1" "$2"; f=$((f+1)); }
T=$(mktemp -d); trap 'rm -rf "$T"' EXIT
mkdir -p "$T/bin"; MARCA="$T/centinela.log"; : > "$MARCA"
cat > "$T/bin/codex" <<CEN
#!/usr/bin/env bash
case " \$* " in *" --version "*) echo "codex-cli 0.147.0-centinela"; exit 0 ;; esac
echo "INVOCACION: \$*" >> "$MARCA"
for a in "\$@"; do case "\$a" in -o) shift; printf 'ok' > "\$1" 2>/dev/null;; esac; done
printf '{"type":"thread.started","thread_id":"t"}\n{"type":"turn.completed"}\n'
echo "sandbox: workspace-write" >&2
exit 0
CEN
chmod +x "$T/bin/codex"; export PATH="$T/bin:$PATH"

nuevo_fixture(){ # $1 = nombre -> imprime la ruta de un repo sintetico recien creado
  local d="$T/$1"; mkdir -p "$d"
  ( cd "$d" && git init -q . && git config user.email t@t && git config user.name t \
    && echo x > a.txt && git add -A && git commit -qm b ) >/dev/null 2>&1
  local raiz; raiz=$(git -C "$d" rev-list --max-parents=0 HEAD 2>/dev/null | head -1)
  [ "$raiz" = "$AURA_ROOT" ] && { echo "FIXTURE ES AURA" >&2; exit 1; }
  echo "$d"
}
echo "no hagas nada" > "$T/e.txt"

# --- 1 · la evidencia se escribe DENTRO de un subdirectorio con el delegation_id ---------------
W1=$(nuevo_fixture repo1); ID1="prueba-uno"
( cd /var/tmp && "$S" --worktree "$W1" --encargo "$T/e.txt" --delegacion-id "$ID1" ) >/dev/null 2>&1
[ -f "$W1/.delegacion/$ID1/manifest.json" ] \
  && ok "la evidencia vive en .delegacion/<delegation_id>/" "$ID1" \
  || mal "la evidencia vive en .delegacion/<delegation_id>/" "no existe $ID1/manifest.json"

# --- 2 · y NO suelta en .delegacion/ ------------------------------------------------------------
[ -f "$W1/.delegacion/manifest.json" ] \
  && mal "la evidencia NO se escribe suelta en .delegacion/" "hay manifest.json suelto" \
  || ok "la evidencia NO se escribe suelta en .delegacion/" "limpio"

# --- 3 · el directorio de la delegacion contiene sus cuatro artefactos --------------------------
n=0; for x in manifest.json events.jsonl stderr.txt prompt.txt; do [ -f "$W1/.delegacion/$ID1/$x" ] && n=$((n+1)); done
[ "$n" -eq 4 ] && ok "el directorio de la delegacion conserva sus 4 artefactos" "4/4" \
               || mal "el directorio de la delegacion conserva sus 4 artefactos" "$n/4"

# --- 4 · dos delegaciones en fixtures distintos NO comparten ruta -------------------------------
W2=$(nuevo_fixture repo2); ID2="prueba-dos"
( cd /var/tmp && "$S" --worktree "$W2" --encargo "$T/e.txt" --delegacion-id "$ID2" ) >/dev/null 2>&1
r1=$(ls -d "$W1/.delegacion/"*/ 2>/dev/null | head -1); r2=$(ls -d "$W2/.delegacion/"*/ 2>/dev/null | head -1)
[ -n "$r1" ] && [ -n "$r2" ] && [ "$(basename "$r1")" != "$(basename "$r2")" ] \
  && ok "dos delegaciones distintas ocupan rutas distintas" "$(basename "$r1") / $(basename "$r2")" \
  || mal "dos delegaciones distintas ocupan rutas distintas" "r1='$r1' r2='$r2'"

# --- 5 · la ruta de evidencia DEPENDE del delegation_id ----------------------------------------
# El corazon de la garantia: cambiar el id debe cambiar la ruta. Si no, todas escriben en el mismo sitio.
W3=$(nuevo_fixture repo3)
( cd /var/tmp && "$S" --worktree "$W3" --encargo "$T/e.txt" --delegacion-id "id-alfa" ) >/dev/null 2>&1
W4=$(nuevo_fixture repo4)
( cd /var/tmp && "$S" --worktree "$W4" --encargo "$T/e.txt" --delegacion-id "id-beta" ) >/dev/null 2>&1
a=$(ls "$W3/.delegacion/" 2>/dev/null | head -1); b=$(ls "$W4/.delegacion/" 2>/dev/null | head -1)
{ [ "$a" = "id-alfa" ] && [ "$b" = "id-beta" ]; } \
  && ok "la ruta de evidencia deriva del delegation_id" "$a / $b" \
  || mal "la ruta de evidencia deriva del delegation_id" "obtenido '$a' / '$b'"

# --- 6 · el centinela confirma que Codex no se invoco de forma real -----------------------------
grep -q 'aura-project-bible' "$MARCA" 2>/dev/null \
  && mal "ninguna invocacion apunta a AURA" "$(grep -c 'aura-project-bible' "$MARCA")" \
  || ok "ninguna invocacion apunta a AURA" "0"

[ $f -eq 0 ] && { echo "PASS"; exit 0; } || { echo "FAIL · $f"; exit 1; }
