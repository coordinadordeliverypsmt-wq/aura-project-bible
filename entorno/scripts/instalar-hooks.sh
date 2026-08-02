#!/usr/bin/env bash
# Activa los hooks versionados del proyecto (una vez por clon).
#
# Los hooks de git NO viajan con el repositorio: viven en `.git/hooks`, que no se versiona. Por eso el
# proyecto los guarda en `.githooks/` (versionado) y aqui se apunta `core.hooksPath` a ese directorio.
# Sin este paso, el Quality Gate volveria a depender de que alguien se acuerde de ejecutarlo — que es
# exactamente el problema que el hook resuelve.
#
# `core.hooksPath` es configuracion LOCAL y se comparte entre el repositorio principal y sus worktrees.

set -euo pipefail

RAIZ="$(git rev-parse --show-toplevel)"
cd "$RAIZ"

# Solo los hooks: `omisiones.log` es un fichero de DATOS y no debe ser ejecutable.
chmod +x .githooks/pre-push 2>/dev/null || true
git config core.hooksPath .githooks

echo "hooks activados: core.hooksPath -> $(git config --get core.hooksPath)"
echo "  pre-push: ejecuta el Quality Gate y BLOQUEA la publicacion si falla."
echo "  omision excepcional y trazable:  AURA_OMITIR_GATE=\"motivo\" git push"
