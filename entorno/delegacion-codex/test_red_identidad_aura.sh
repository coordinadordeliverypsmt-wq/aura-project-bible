#!/usr/bin/env bash
# RED · identidad VERIFICABLE de AURA y barrera de aislamiento.
#
# REGLA ABSOLUTA (CEO 2026-08-24): ninguna prueba con objetivo prohibido invoca Codex real. Los casos
# negativos usan --solo-verificar, y ademas se antepone en PATH un `codex` CENTINELA que deja una
# marca si llegara a ejecutarse. Si la marca no aparece, Codex NO fue invocado — y eso se comprueba,
# no se supone. La leccion viene de un incidente real: una RED escrita para REPRODUCIR el bypass
# acabo EJECUTANDOLO sobre AURA.
#
# IDENTIDAD: el commit raiz del repositorio OBJETIVO (`git -C <obj> rev-list --max-parents=0 HEAD`).
# No es dirname "$0", ni la ubicacion del wrapper, ni un marcador de ficheros, ni comparacion de
# rutas: es una propiedad del repositorio, identica en el principal, en cualquier worktree y en
# cualquier subdirectorio de AURA, y ausente en repos ajenos.
S="${S:?}"; f=0; ne=0
AURA_ROOT_COMMIT=79018b3b49da782a57367257ca1f1bd597c076cb
ok(){ printf "  %-54s %s\n" "$1" "$2"; }; mal(){ printf "  %-54s %s <-- FALLO\n" "$1" "$2"; f=$((f+1)); }
AURA=/home/majo1230/Documentos/AURA/aura-project-bible
D=$(mktemp -d); trap 'rm -rf "$D"' EXIT
CENT="$D/CODEX_FUE_INVOCADO"
# El centinela solo marca una EJECUCION SOBRE EL OBJETIVO (exec/resume/review). `codex --version`
# es una consulta local que el wrapper hace al arrancar y no toca ningun repositorio: contarla seria
# un falso positivo.
mkdir -p "$D/bin"
cat > "$D/bin/codex" <<CENTINELA
#!/usr/bin/env bash
case "\$1" in
  exec|review) touch "$CENT" ;;
esac
echo '{"type":"thread.started","thread_id":"cent"}'
echo '{"type":"turn.completed"}'
exit 0
CENTINELA
chmod +x "$D/bin/codex"
( cd "$D" && mkdir sintetico && cd sintetico && git init -q . && git config user.email t@t && git config user.name t && echo x > a.txt && git add -A && git commit -qm b )
mkdir -p "$D/sin_git"

neg(){ # objetivo prohibido: FAILURE + Codex NO invocado
  rm -f "$CENT"
  local r; r=$(cd /var/tmp && PATH="$D/bin:$PATH" "$S" --worktree "$2" --review --solo-verificar 2>&1 | head -1)
  case "$r" in FAILURE*) got=FAILURE ;; *) got=OK ;; esac
  if [ "$got" != "FAILURE" ]; then mal "$1 · rechazado" "$got · $r"; else ok "$1 · rechazado" "FAILURE"; fi
  [ -e "$CENT" ] && mal "$1 · Codex NO invocado" "SE INVOCO" || ok "$1 · Codex NO invocado" "no se invoco"
}
pos(){ rm -f "$CENT"
  local r; r=$(cd /var/tmp && PATH="$D/bin:$PATH" "$S" --worktree "$2" --review --solo-verificar 2>&1 | head -1)
  case "$r" in FAILURE*) mal "$1 · aceptado" "$r" ;; *) ok "$1 · aceptado" "OK" ;; esac
}
echo "  --- objetivos PROHIBIDOS (identidad = AURA) ---"
neg "repo principal de AURA"      "$AURA"
neg "worktree m3-entry"           "$AURA/.claude/worktrees/m3-entry"
neg "walking-skeleton"            "$AURA/walking-skeleton"
neg "walking-skeleton/aura_skeleton" "$AURA/walking-skeleton/aura_skeleton"
# CASO PURO DE IDENTIDAD: un worktree de AURA en ruta ajena, que ES raiz de su repo y NO tiene
# ninguno de los marcadores. Ninguna guarda textual lo atrapa: solo el commit raiz. Se construye
# aqui mismo y se destruye al salir; jamas se invoca Codex sobre el.
# CORREGIDO 2026-08-24 (FASE 6.3), dos defectos senalados por la auditoria:
#
#  (a) SKIP se presentaba como PASS. Si la preparacion del sujeto fallaba, la RED lo anunciaba y
#      terminaba en PASS —perdiendo EN SILENCIO su caso central, el unico que ejerce el rechazo por
#      COMMIT RAIZ y con el la garantia de M11. PASS != SKIP != FAIL: que el sujeto no pueda
#      prepararse significa que la garantia NO SE EJERCIO, y eso nunca es un exito.
#  (b) el sujeto se creaba con `git worktree add` sobre el REPO PRINCIPAL de AURA, que queda
#      registrado en su `.git/worktrees/`. Se sustituye por un CLON en /tmp que comparte el COMMIT
#      RAIZ: ejerce exactamente la misma guarda de identidad sin tocar AURA (demostrado en FASE 1).
CLON=/tmp/codex-mvp/aura-clon
[ -d "$CLON" ] || git clone --quiet --shared "$AURA" "$CLON" 2>/dev/null
if git -C "$CLON" worktree add --detach "$D/aura_clon" HEAD -q 2>/dev/null    && [ "$(git -C "$D/aura_clon" rev-list --max-parents=0 HEAD 2>/dev/null | head -1)" = "$AURA_ROOT_COMMIT" ]; then
  rm -rf "$D/aura_clon/docs" "$D/aura_clon/adr" "$D/aura_clon/decisiones" "$D/aura_clon/entorno/control-plane"
  neg "sujeto con la identidad de AURA en ruta ajena (identidad pura)" "$D/aura_clon"
  git -C "$CLON" worktree remove --force "$D/aura_clon" 2>/dev/null
else
  echo "  NO_EJERCIDA · no se pudo preparar el sujeto de identidad pura"
  ne=$((ne+1))
fi
echo "  --- objetivos que deben rechazarse por otras razones ---"
neg "directorio sin git"          "$D/sin_git"
neg "ruta inexistente"            "$D/no_existe"
echo "  --- objetivo AUTORIZADO (root commit distinto) ---"
pos "repo sintetico"              "$D/sintetico"
# TRES estados distinguibles, nunca dos: PASS (todo ejercido y correcto) · FAIL (una garantia
# fallo) · NO_EJERCIDA (no se pudo preparar el sujeto: la garantia no se midio). exit 2 la separa.
if [ $f -ne 0 ]; then echo "FAIL · $f"; exit 1
elif [ $ne -ne 0 ]; then echo "NO_EJERCIDA · $ne garantia(s) sin ejercer: el resultado NO es PASS"; exit 2
else echo "PASS"; exit 0; fi
