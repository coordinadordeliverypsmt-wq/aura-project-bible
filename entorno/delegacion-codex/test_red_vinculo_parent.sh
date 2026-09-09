#!/usr/bin/env bash
# RED · el wrapper acepta `--parent` y REGISTRA el vinculo entre delegaciones (garantia de M6).
#
# POR QUE EXISTE ESTA RED (FASE 6, 2026-08-24). `test_red_continuidad.sh` cubre esta garantia pero
# NO PUEDE EJERCERLA bajo el mutante M6: al eliminar el `case --parent`, el flag cae en
# `*) abortar "argumento desconocido"`, la RED no obtiene delegation_id y muere en el SETUP —
# 1 de 7 aserciones. Su «DETECTADO» historico era falso, y la justificacion escrita en el registro
# («abortan la obtencion de delegation_id pero ninguna RED da falso PASS») no se sostiene: no basta
# que la RED falle, debe fallar HABIENDO EJERCIDO la garantia.
#
# DISEÑO: cada asercion hace su propia invocacion sobre su propio fixture y NINGUNA aborta la RED.
# Asi el conteo se mantiene y el veredicto sale por causalidad, sin recurrir a la excepcion TER.
# Incluye una asercion de CONTROL INTERNO —el caso sin `--parent`— que debe seguir pasando con el
# mutante aplicado: demuestra que la RED no se rompe entera, solo lo que toca la garantia.
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
exit 0
CEN
chmod +x "$T/bin/codex"; export PATH="$T/bin:$PATH"
nuevo_fixture(){ local d="$T/$1"; mkdir -p "$d"
  ( cd "$d" && git init -q . && git config user.email t@t && git config user.name t \
    && echo x > a.txt && git add -A && git commit -qm b ) >/dev/null 2>&1
  [ "$(git -C "$d" rev-list --max-parents=0 HEAD 2>/dev/null|head -1)" = "$AURA_ROOT" ] && { echo "ES AURA">&2; exit 1; }
  echo "$d"; }
campo(){ python3 -c "
import json,sys
try: print(json.load(open(sys.argv[1])).get(sys.argv[2]))
except Exception: print('SIN_MANIFEST')" "$1" "$2" 2>/dev/null; }
echo "no hagas nada" > "$T/e.txt"

# --- 1 · el wrapper ACEPTA --parent (no lo rechaza como argumento desconocido) -----------------
W1=$(nuevo_fixture r1)
r=$( cd /var/tmp && "$S" --worktree "$W1" --encargo "$T/e.txt" --delegacion-id hijo-1 --parent padre-1 2>&1 | head -1 )
case "$r" in *"argumento desconocido"*) mal "el wrapper acepta el flag --parent" "$r" ;;
                                     *) ok  "el wrapper acepta el flag --parent" "aceptado" ;; esac

# --- 2 · y REGISTRA el vinculo en el manifest --------------------------------------------------
v=$(campo "$W1/.delegacion/hijo-1/manifest.json" parent_delegation_id)
[ "$v" = "padre-1" ] && ok "el manifest registra parent_delegation_id" "$v" \
                     || mal "el manifest registra parent_delegation_id" "$v"

# --- 3 · CONTROL INTERNO: sin --parent el vinculo es null (debe pasar TAMBIEN con el mutante) ---
W2=$(nuevo_fixture r2)
( cd /var/tmp && "$S" --worktree "$W2" --encargo "$T/e.txt" --delegacion-id suelto-1 ) >/dev/null 2>&1
v=$(campo "$W2/.delegacion/suelto-1/manifest.json" parent_delegation_id)
[ "$v" = "None" ] && ok "sin --parent el vinculo queda a null (control interno)" "null" \
                  || mal "sin --parent el vinculo queda a null (control interno)" "$v"

# --- 4 · el valor registrado es EL QUE SE PASO, no uno fijo ------------------------------------
W3=$(nuevo_fixture r3)
( cd /var/tmp && "$S" --worktree "$W3" --encargo "$T/e.txt" --delegacion-id hijo-2 --parent otro-padre ) >/dev/null 2>&1
v=$(campo "$W3/.delegacion/hijo-2/manifest.json" parent_delegation_id)
[ "$v" = "otro-padre" ] && ok "el vinculo registrado es el valor recibido" "$v" \
                        || mal "el vinculo registrado es el valor recibido" "$v"

# --- 5 · el vinculo NO se confunde con previous_thread_id --------------------------------------
v=$(campo "$W3/.delegacion/hijo-2/manifest.json" previous_thread_id)
[ "$v" = "None" ] && ok "parent_delegation_id no contamina previous_thread_id" "null" \
                  || mal "parent_delegation_id no contamina previous_thread_id" "$v"

# --- 6 · seguridad ------------------------------------------------------------------------------
grep -q 'aura-project-bible' "$MARCA" 2>/dev/null \
  && mal "ninguna invocacion apunta a AURA" "$(grep -c 'aura-project-bible' "$MARCA")" \
  || ok "ninguna invocacion apunta a AURA" "0"

[ $f -eq 0 ] && { echo "PASS"; exit 0; } || { echo "FAIL · $f"; exit 1; }
