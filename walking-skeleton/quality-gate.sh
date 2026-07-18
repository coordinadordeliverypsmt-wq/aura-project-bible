#!/usr/bin/env bash
# Quality Gate de AURA (Bible 7.1/7.2). Se ejecuta antes de cada integracion/ejecucion.
# Verifica: formato, analisis estatico, tipado, pruebas y contratos.
set -uo pipefail
cd "$(dirname "$0")"
FAIL=0
step(){ echo ""; echo "==> $1"; }
chk(){ if [ "$1" -eq 0 ]; then echo "  [ OK ] $2"; else echo "  [FAIL] $2"; FAIL=1; fi; }

step "1/5 Formato (ruff format --check)"
python3 -m ruff format --check aura_skeleton tests; chk $? "formato"
step "2/5 Analisis estatico (ruff check)"
python3 -m ruff check aura_skeleton tests; chk $? "lint"
step "3/5 Tipado (mypy)"
python3 -m mypy aura_skeleton; chk $? "tipado"
step "4/5 Pruebas (pytest: unit/integration/e2e/performance)"
python3 -m pytest; chk $? "pruebas"
step "5/5 Contratos (pytest tests/test_contracts.py)"
python3 -m pytest tests/test_contracts.py; chk $? "contratos"

echo ""
echo "======================================================"
[ $FAIL -eq 0 ] && echo "QUALITY GATE: PASS — listo para integrar/ejecutar" || echo "QUALITY GATE: FAIL — corrige lo anterior"
echo "======================================================"
exit $FAIL
