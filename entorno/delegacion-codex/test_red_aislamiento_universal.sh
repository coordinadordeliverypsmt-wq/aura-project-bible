#!/usr/bin/env bash
# RED · el aislamiento debe proteger TODAS las operaciones, no solo `review`.
#
# HALLAZGO QUE REPRODUCE (reauditoria 2026-08-30): `verificar_objetivo()` solo se invocaba en la rama
# review, asi que `exec` —la accion POR DEFECTO— aceptaba un worktree de AURA.
#
# ===============================================================================================
# CORREGIDA 2026-08-24 tras la auditoria independiente (GRAVE-3). VERSION ANTERIOR: INSEGURA.
# ===============================================================================================
# Sus cinco casos negativos invocaban el wrapper con `--worktree $AURA/...` REAL, sin
# `--solo-verificar` y SIN centinela: la unica red era el propio wrapper. El auditor lo demostro
# aplicando el mutante M13 —un mutante declarado de esta misma bateria— y midiendo CUATRO
# invocaciones con `--cd` sobre AURA. Sin su centinela habrian sido Codex real sobre AURA,
# incluido un `review`. Es el incidente que este proyecto ya sufrio dos veces.
#
# DOS CAMBIOS, y la garantia NO se debilita:
#
#  1. SUJETO = FIXTURE EQUIVALENTE, NO AURA. La identidad de AURA es su COMMIT RAIZ, no su ruta.
#     Un clon local en /tmp comparte ese commit raiz, luego ejerce EXACTAMENTE la misma guarda
#     sin que AURA sea jamas el sujeto de una ejecucion real. Se usa un WORKTREE del clon con las
#     fuentes de verdad ausentes: asi el unico motivo posible de rechazo es la IDENTIDAD, y
#     ninguna guarda anterior (marcador `docs`, toplevel) puede enmascararla. El auditor midio
#     que, contra el AURA real, los cuatro casos morian ANTES de llegar a la identidad.
#
#  2. CENTINELA OBLIGATORIO. `codex` se sustituye en el PATH por un centinela que deja marca y no
#     ejecuta nada. Al final se COMPRUEBA que no se invoco: no se supone. Si el wrapper fallara,
#     esta RED falla — no lanza Codex.
S="${S:?}"; f=0
ok(){ printf "  %-56s %s\n" "$1" "$2"; }; mal(){ printf "  %-56s %s <-- FALLO\n" "$1" "$2"; f=$((f+1)); }
AURA_ROOT=79018b3b49da782a57367257ca1f1bd597c076cb
AURA_REAL=/home/majo1230/Documentos/AURA/aura-project-bible
CLON=/tmp/codex-mvp/aura-clon
W=$(mktemp -d); trap 'rm -rf "$W"; git -C "$CLON" worktree remove --force "$W/aura_equiv" 2>/dev/null' EXIT

# --- centinela: ninguna invocacion real puede escaparse sin dejar rastro ------------------------
mkdir -p "$W/bin"; MARCA="$W/centinela.log"; : > "$MARCA"
cat > "$W/bin/codex" <<CEN
#!/usr/bin/env bash
case " \$* " in *" --version "*) echo "codex-cli 0.147.0-centinela"; exit 0 ;; esac
echo "INVOCACION: \$*" >> "$MARCA"
exit 0
CEN
chmod +x "$W/bin/codex"; export PATH="$W/bin:$PATH"

# --- fixture EQUIVALENTE a AURA: mismo commit raiz, sin fuentes de verdad, toplevel propio ------
[ -d "$CLON" ] || git clone --quiet --shared "$AURA_REAL" "$CLON" 2>/dev/null
EQ="$W/aura_equiv"
git -C "$CLON" worktree add --quiet --detach "$EQ" HEAD 2>/dev/null || { echo "SETUP FAIL: no se pudo crear el worktree equivalente"; exit 1; }
rm -rf "$EQ/docs" "$EQ/adr" "$EQ/decisiones" "$EQ/entorno"     # que la identidad NO quede enmascarada
RAIZ_EQ=$(git -C "$EQ" rev-list --max-parents=0 HEAD 2>/dev/null | head -1)
[ "$RAIZ_EQ" = "$AURA_ROOT" ] || { echo "SETUP FAIL: el fixture no comparte el commit raiz de AURA"; exit 1; }
[ "$(cd "$EQ" && pwd -P)" != "$AURA_REAL" ] || { echo "SETUP FAIL: el fixture ES AURA"; exit 1; }
ok "fixture equivalente: mismo commit raiz, NO es AURA" "${RAIZ_EQ:0:12}"

# --- fixture sintetico autorizado (control positivo) -------------------------------------------
SYN="$W/sintetico"; mkdir -p "$SYN"
( cd "$SYN" && git init -q . && git config user.email t@t && git config user.name t && echo x > a.txt && git add -A && git commit -qm b )
echo "no hagas nada" > "$W/e.txt"

probar(){ # $1=desc  $2=worktree  $3=esperado  $4..=args
  local d="$1" wt="$2" esp="$3"; shift 3
  local r; r=$(cd /var/tmp && "$S" --worktree "$wt" "$@" 2>&1 | head -1)
  case "$r" in FAILURE*) got=FAILURE ;; *) got=OK ;; esac
  [ "$got" = "$esp" ] && ok "$d" "$got" || mal "$d" "$got · $r"
}
probar "exec  · objetivo con la identidad de AURA"    "$EQ"   FAILURE --encargo "$W/e.txt"
probar "resume· objetivo con la identidad de AURA"    "$EQ"   FAILURE --encargo "$W/e.txt" --resume x
probar "review· objetivo con la identidad de AURA"    "$EQ"   FAILURE --review
probar "exec  · objetivo sintetico autorizado"        "$SYN"  OK      --solo-verificar

# --- la identidad debe sobrevivir a copiar el wrapper a otra ubicacion -------------------------
C="$W/copia_del_wrapper.sh"; cp "$S" "$C"
r=$(cd /var/tmp && "$C" --worktree "$EQ" --review 2>&1 | head -1)
case "$r" in FAILURE*) ok "wrapper COPIADO sigue rechazando la identidad" "FAILURE" ;;
             *) mal "wrapper COPIADO sigue rechazando la identidad" "$r" ;; esac

# --- el motivo del rechazo es la IDENTIDAD, no otra guarda -------------------------------------
r=$(cd /var/tmp && "$S" --worktree "$EQ" --encargo "$W/e.txt" 2>&1 | head -1)
case "$r" in *"commit raiz"*) ok "el rechazo lo produce la guarda de IDENTIDAD" "commit raiz" ;;
             *) mal "el rechazo lo produce la guarda de IDENTIDAD" "$r" ;; esac

# --- COMPROBADO, no supuesto: Codex no se invoco ------------------------------------------------
N=$(wc -l < "$MARCA")
[ "$N" -eq 0 ] && ok "el centinela confirma que Codex NO fue invocado" "0 invocaciones" \
                || mal "el centinela registro invocaciones de Codex" "$N: $(head -1 "$MARCA")"
# --- y ninguna de ellas pudo apuntar a AURA ----------------------------------------------------
G=$(grep -c "$AURA_REAL" "$MARCA" 2>/dev/null) || G=0
[ "$G" -eq 0 ] && ok "ninguna invocacion apunta al AURA real" "0" || mal "invocacion contra AURA real" "$G"

[ $f -eq 0 ] && { echo "PASS"; exit 0; } || { echo "FAIL · $f"; exit 1; }
