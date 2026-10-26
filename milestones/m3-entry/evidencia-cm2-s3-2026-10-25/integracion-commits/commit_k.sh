#!/usr/bin/env bash
# Uso: commit_k.sh K "<asunto conventional>" "<cuerpo>"
# Añade commit-K.paths, VERIFICA que lo staged es exactamente esa lista (más el staging previo esperado
# si K=3), que no entra nada prohibido, y hace el commit. Se detiene ante cualquier discrepancia.
set -euo pipefail
K="$1"; ASUNTO="$2"; CUERPO="$3"
W=/home/majo1230/Documentos/AURA/aura-project-bible/.claude/worktrees/m3-entry
E=$W/milestones/m3-entry/evidencia-cm2-s3-2026-10-25/particion-integracion
L=/home/majo1230/.claude/jobs/d6cb894c/tmp/integracion
PREV=$W/milestones/m3-entry/evidencia-cm2-s3-2026-10-25/reanudacion-tras-caida/previos-a-la-aplicacion
cd "$W"
LISTA="$E/commit-$K.paths"

# 1. Antes: el índice solo puede contener lo esperado (nada, o el rename preexistente antes del commit 3).
git diff --cached --name-only --no-renames | sort > "$L/staged-antes-$K.txt"
if [ "$K" = "3" ]; then
  printf '%s\n' walking-skeleton/mutaciones/arnes-validador-comandos.toml \
    walking-skeleton/mutaciones/retiradas/arnes-validador-comandos.toml | sort > "$L/esperado-antes-$K.txt"
else
  : > "$L/esperado-antes-$K.txt"
fi
diff -u "$L/esperado-antes-$K.txt" "$L/staged-antes-$K.txt" || { echo "ABORTO: índice inesperado antes del commit $K"; exit 10; }

# 2. Añadir SOLO la lista.
# Rutas presentes: git add. Rutas borradas (p.ej. el lado viejo de un rename): git rm --cached. Nunca -A.
: > "$L/presentes-$K.txt"; : > "$L/borradas-$K.txt"
while IFS= read -r r; do [ -z "$r" ] && continue
  if [ -e "$r" ] || [ -L "$r" ]; then echo "$r" >> "$L/presentes-$K.txt"; else echo "$r" >> "$L/borradas-$K.txt"; fi
done < "$LISTA"
[ -s "$L/presentes-$K.txt" ] && git add --pathspec-from-file="$L/presentes-$K.txt"
[ -s "$L/borradas-$K.txt" ] && git rm -q --cached --ignore-unmatch --pathspec-from-file="$L/borradas-$K.txt"

# 3. Commit 4: los 4 .py del control-plane se indexan en su versión PREVIA, sin tocar el árbol.
if [ "$K" = "4" ]; then
  (cd "$PREV" && sha256sum -c --quiet SHA256SUMS) || { echo "ABORTO: SHA256SUMS de previos"; exit 11; }
  for f in planificador control_plane motor_autonomia aura; do
    h=$(git hash-object -w "$PREV/$f.py")
    git update-index --add --cacheinfo "100644,$h,entorno/control-plane/$f.py"
  done
fi

# 4. Verificar: lo staged es exactamente la lista (+4 previos en K=4).
git diff --cached --name-only --no-renames | sort > "$L/staged-$K.txt"
sort -u "$LISTA" > "$L/esperado-$K.txt"
if [ "$K" = "4" ]; then
  printf 'entorno/control-plane/%s.py\n' planificador control_plane motor_autonomia aura >> "$L/esperado-$K.txt"
  sort -u -o "$L/esperado-$K.txt" "$L/esperado-$K.txt"
fi
# Las rutas de la lista sin cambios respecto a HEAD no aparecen como staged: se aceptan solo si no difieren.
comm -23 "$L/esperado-$K.txt" "$L/staged-$K.txt" > "$L/lista-sin-cambio-$K.txt"
comm -13 "$L/esperado-$K.txt" "$L/staged-$K.txt" > "$L/staged-fuera-de-lista-$K.txt"
if [ -s "$L/staged-fuera-de-lista-$K.txt" ]; then echo "ABORTO: staged fuera de la lista:"; cat "$L/staged-fuera-de-lista-$K.txt"; exit 12; fi
if [ -s "$L/lista-sin-cambio-$K.txt" ]; then echo "AVISO: rutas de la lista sin cambio frente a HEAD:"; cat "$L/lista-sin-cambio-$K.txt"; fi

# 5. Nada prohibido.
if grep -E '(^|/)(eventos\.jsonl|estado\.json|PARADA|\.control-plane\.lock|\.supervisor\.lock|kernel\.errors\.txt|ficha-evidencia\.md|scheduled_tasks\.lock|omisiones\.log)$|__pycache__|\.pyc$|graphify-out/|\.pytest_cache|\.ruff_cache' "$L/staged-$K.txt"; then
  echo "ABORTO: ruta prohibida en el índice"; exit 13
fi

# 6. Commit con los trailers de CLAUDE.md §3.
{ printf '%s\n\n%s\n\n' "$ASUNTO" "$CUERPO"
  printf 'Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>\n'
  printf 'Claude-Session: https://claude.ai/code/session_018FPxs18b7xW6kGYPWppnL1\n'; } > "$L/mensaje-$K.txt"
git commit -q -F "$L/mensaje-$K.txt"
SHA=$(git rev-parse HEAD)
git show --name-status --no-renames --format='%H %s' HEAD > "$L/commit-$K-contenido.txt"
echo "COMMIT $K = $SHA ($(wc -l < "$L/staged-$K.txt") rutas)"
git diff --cached --name-only | wc -l | xargs echo "índice tras el commit (debe ser 0):"
