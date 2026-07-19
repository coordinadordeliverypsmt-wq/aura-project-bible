# Cierre de M1 (M1-Exit) — flujo y plantillas

Juego de entregables para cerrar el Milestone M1, conforme a la directriz del CEO (validacion funcional) y a D25 (Architecture Review por milestone) + D17 (Executive Summary).

## Flujo de cierre (en el hardware objetivo, 100% local — D24)

```bash
# 1. Verificar entorno y ejecutar los 3 arneses (ver entorno/VALIDACION-COMPLETA.md)
bash entorno/scripts/verify-stack.sh
cd walking-skeleton
python3 demo_capacidad_m1.py --real                 # demo oficial (producto, 6/6 capacidades)
python3 validar_m1.py --real --iterations 50        # -> resultados-m1.json (latencia/CPU/RAM/estabilidad)
python3 evals_m1.py --real --models qwen2.5:3b,llama3.2:3b   # -> evals-m1.json (guardrails/consistencia)

# 2. Auto-generar los resultados medidos + comparacion vs Bible (rellena solo)
python3 generar_m1_exit.py --resultados resultados-m1.json --evals evals-m1.json \
        --out ../milestones/m1-exit/RESULTADOS-MEDIDOS.md
```

Comparte `resultados-m1.json` y `evals-m1.json` (o el `RESULTADOS-MEDIDOS.md` generado) y el CTO completa las plantillas 2 y 3.

## Entregables del cierre (los 4 que pidio el CEO)

1. **Resultados medidos** -> `RESULTADOS-MEDIDOS.md` (auto-generado por `generar_m1_exit.py`).
2. **Comparacion contra los objetivos de la Bible** -> incluida en el mismo `RESULTADOS-MEDIDOS.md` (con veredicto y aviso de Alerta D15 si algo falla).
3. **Architecture Review M1-Exit** -> `ARCHITECTURE-REVIEW-M1-EXIT.md` (plantilla, 12 secciones; se puebla con los datos medidos).
4. **Executive Summary de M1** -> `EXECUTIVE-SUMMARY-M1.md` (plantilla, cara al CEO).

## Regla de cierre

Si un objetivo de rendimiento/estabilidad o un guardrail critico NO se cumple: **Alerta de Arquitectura (D15)** con la plantilla de 10 secciones (D16), nunca ajuste silencioso. M1 se cierra solo con la Architecture Review M1-Exit y el Executive Summary **aprobados por el CEO**.
