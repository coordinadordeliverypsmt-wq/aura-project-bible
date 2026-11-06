#!/usr/bin/env bash
# Quality Gate de AURA (Bible 7.1/7.2). Se ejecuta antes de cada integracion/ejecucion.
# Verifica: formato, analisis estatico, tipado, pruebas y contratos.
set -uo pipefail
cd "$(dirname "$0")"
FAIL=0
PASOS=()
step(){ echo ""; echo "==> $1"; }
chk(){ if [ "$1" -eq 0 ]; then echo "  [ OK ] $2"; PASOS+=("--paso" "$2=OK"); else echo "  [FAIL] $2"; PASOS+=("--paso" "$2=FAIL"); FAIL=1; fi; }
# Copia de la salida de pytest para el registro estructurado (herramientas/registro_gate.py); se borra al salir.
SALIDA_PYTEST="$(mktemp)"; trap 'rm -f "$SALIDA_PYTEST"' EXIT

step "1/5 Formato (ruff format --check)"
python3 -m ruff format --check aura_skeleton tests; chk $? "formato"
step "2/5 Analisis estatico (ruff check)"
python3 -m ruff check aura_skeleton tests; chk $? "lint"
step "3/5 Tipado (mypy)"
python3 -m mypy aura_skeleton; chk $? "tipado"
step "4/5 Pruebas (pytest: unit/integration/e2e/performance)"
python3 -m pytest 2>&1 | tee "$SALIDA_PYTEST"; chk "${PIPESTATUS[0]}" "pruebas"
step "5/5 Contratos (pytest tests/test_contracts.py)"
python3 -m pytest tests/test_contracts.py; chk $? "contratos"

echo ""
echo "======================================================"
[ $FAIL -eq 0 ] && echo "QUALITY GATE: PASS — listo para integrar/ejecutar" || echo "QUALITY GATE: FAIL — corrige lo anterior"
echo "======================================================"
# Registro del ÚLTIMO resultado para el AURA Progress Dashboard. Es una proyección: nunca cambia el resultado del gate
# (el módulo devuelve siempre 0 y, si no puede escribir, lo dice por stderr).
python3 -m herramientas.registro_gate --pytest-salida "$SALIDA_PYTEST" "${PASOS[@]}" || true
exit $FAIL
