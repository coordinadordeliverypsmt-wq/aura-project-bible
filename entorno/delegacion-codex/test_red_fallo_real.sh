#!/usr/bin/env bash
# RED · GRAVE-3 · un fallo REAL de Codex no se convierte en PASS y no destruye la evidencia.
#
# CODEX REAL, sin mock: la garantia depende del exit_code y del stderr que produce el binario
# autentico. La condicion de fallo es un ENCARGO VACIO -> «No prompt provided via stdin», exit 1,
# CERO eventos. Es real, reproducible y NO consume cuota: Codex falla antes de contactar la API.
#
# Ese "cero eventos" hace la prueba mas exigente de lo que parece: no hay thread_id, asi que se
# comprueba tambien que el wrapper aborta por «Codex fallo» y no lo confunde con otra causa.
#
# SEGURIDAD: objetivo sintetico bajo /tmp/codex-mvp, con root commit verificado != AURA.
S="${S:?}"; f=0
ok(){ printf "  %-54s %s\n" "$1" "$2"; }; mal(){ printf "  %-54s %s <-- FALLO\n" "$1" "$2"; f=$((f+1)); }
M=/tmp/codex-mvp/g3; rm -rf "$M"; mkdir -p "$M"
( cd "$M" && git init -q . && git config user.email t@t && git config user.name t && echo x > a.txt && git add -A && git commit -qm b )
R=$(git -C "$M" rev-list --max-parents=0 HEAD | head -1)
[ "$R" != "79018b3b49da782a57367257ca1f1bd597c076cb" ] || { echo "FAIL: el objetivo ES AURA"; exit 1; }
ok "precondicion: objetivo sintetico, root != AURA" "${R:0:12}..."
: > "$M/vacio.txt"
salida=$(cd /var/tmp && "$S" --worktree "$M" --encargo "$M/vacio.txt" 2>&1); codigo=$?
case "$salida" in FAILURE*) ok "B · fallo REAL de Codex -> FAILURE" "ok" ;; *) mal "B · fallo REAL de Codex -> FAILURE" "${salida:0:50}" ;; esac
[ "$codigo" -ne 0 ] && ok "B · el wrapper NO devuelve exito" "exit $codigo" || mal "B · el wrapper NO devuelve exito" "exit 0"
I=$(ls -1 "$M/.delegacion" 2>/dev/null | head -1)
[ -n "$I" ] && ok "B · la delegacion dejo evidencia" "$I" || { mal "B · la delegacion dejo evidencia" "ninguna"; echo "FAIL · $f"; exit 1; }
E="$M/.delegacion/$I"
[ -s "$E/stderr.txt" ] && ok "B · stderr conservado" "$(head -c 34 "$E/stderr.txt" | tr '\n' ' ')" || mal "B · stderr conservado" "vacio"
[ -e "$E/prompt.txt" ] && ok "B · prompt conservado" "ok" || mal "B · prompt conservado" "falta"
[ -e "$E/events.jsonl" ] && ok "B · events.jsonl conservado (vacio es dato)" "$(wc -l < "$E/events.jsonl") lineas" || mal "B · events.jsonl conservado" "falta"
if [ -s "$E/manifest.json" ]; then
  ok "B · manifest ESCRITO pese al fallo" "ok"
  c=$(python3 -c "import json;print(json.load(open('$E/manifest.json')).get('exit_code'))" 2>/dev/null)
  [ "$c" != "0" ] && [ -n "$c" ] && ok "B · exit_code real registrado" "$c" || mal "B · exit_code real registrado" "$c"
else
  mal "B · manifest ESCRITO pese al fallo" "NO se escribio: la evidencia del fallo se pierde"
fi
[ $f -eq 0 ] && { echo "PASS"; exit 0; } || { echo "FAIL · $f"; exit 1; }
