## 2026-07-19 — Limpieza de regenerables (política de mantenimiento del CEO)
- Qué se borró: cachés de calidad (`__pycache__`, `.mypy_cache`, `.ruff_cache`, `.pytest_cache`), salidas de validación (`resultados-m1.json`, `m1-validacion-datos/`), scripts scratch antiguos del job tmp. **Nada de código, docs ni git.**
- Por qué: higiene del entorno; todos son 100% regenerables (se recrean con el Quality Gate / la validación).
- Cuánto se recuperó: mínimo (los regenerables propios eran ~15 MB). El disco está al 93% a nivel de **sistema** (≈50 GB usados no atribuibles a AURA; 4.2 GB libres, suficientes). Si el disco se llena de nuevo, es mantenimiento del **sistema/host**, fuera del alcance de AURA.
- Estado: entorno operativo (Quality Gate corre sin problema).
