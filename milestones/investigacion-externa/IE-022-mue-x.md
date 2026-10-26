---
id: IE-022
titulo: KorroAi/mue-x — «agente que reescribe su propio código» (pipeline AST/mutador/solidify)
fuente: https://github.com/KorroAi/mue-x
rama-revision: main @ c703844 (último push 2026-10-10)
fecha-revision: 2026-10-22
licencia: MIT (SPDX vía API de GitHub). No archivado, 280 estrellas.
area: asistentes
estado: descartado
cobertura: LEÍDO (remoto): evo/self_modification/pipeline.py, evo/dna/sandbox.py, evo/security/guard.py, evo/evolution/loop.py, evo/autonomy/auto_correction.py, evo/absorption/github_miner.py; árbol completo. NO leído: dna/mutator.py (35 KB), evo/solidify.py, memory/*, meta/*, personality/*, swarm/*, README, paper/paper.tex, tests (test_absorption.py), CI. Las afirmaciones del README («primer agente auto-evolutivo») no se verificaron.
relacionadas: [IE-021, IE-023, IE-024]
---
## Qué se examinó (rutas y símbolos)
`SelfModificationPipeline.run/apply_improvement` y `_stage_*`; `sandbox.test_gene/quick_validate`; `SecurityGuard.allow_write/allow_bash/allow_network`; `EvolutionLoop.tick`; `ErrorPatternDB.record_error`, `RegressionDetector.check`, `AutoCorrector`; `github_miner._clone_and_extract/_absorb`.

## Patrones relevantes          (marcar cada afirmación: [CÓDIGO] observado · [README] declarado · [INFER] · [PROPUESTA])
- [CÓDIGO] Errores recurrentes: **sí, simple** — `ErrorPatternDB.record_error` agrupa por huella (tipo + 100 primeros caracteres + gen) con `occurrence_count`; `get_top_errors`. Fallos: la huella de `on_fix` lleva prefijo `fix:` y nunca casa con la del error (`resolved` no se marca); `total_corrections` nunca se incrementa.
- [CÓDIGO] Objetivos/métricas: **parcial** — `SelfBenchmark` (nº de genes, líneas, fitness medio, cada 300 s) y `RegressionDetector` (fitness −20 %, LOC +50 %); la línea base **nunca se actualiza**; `mutation_success_rate` siempre 0 (se pasa `None`).
- [CÓDIGO] Hipótesis: LLM/mutador propone mutaciones por señal; `rl.select_target_gene()` se calcula pero **no se pasa** al mutador; estrategia modulada por «emociones».
- [CÓDIGO] Tests antes/después: **declarado, no aplicado**. En `pipeline.run()` el resultado de `_stage_execute_test` **no se comprueba** antes de `_stage_replace` (solo `apply_improvement` lo hace); los tests los escribe el propio LLM; funciones de test anidadas se saltan en silencio y se informa «All N passed». En `loop.tick` el éxito se fija a `True` tras `apply` (`scorer.record_task(success=True)`): **no hay comparación de fitness antes/después**.
- [CÓDIGO] Qué modifica: código de «genes» (`mue/genes/*.py`) y se añaden genes absorbidos de GitHub; también prompts/persona.
- [CÓDIGO] Sandbox: `subprocess` con `sys.executable` y timeout 15/30 s; **sin** aislamiento de ficheros/red/entorno/recursos; `import` ejecuta código de nivel de módulo; los errores de ejecución no hacen fallar (`sys.exit(0)`). Un `gene_name` sin escapar se interpola en código generado.
- [CÓDIGO] Revisión independiente: **no**. Aprobación humana: **no**.
- [CÓDIGO] Snapshots/rollback: backups `.bak` por segundo (colisionan, sin poda; hash no verificado); `_rollback` usa la copia en memoria; `loop` conserva 5 y `_maintenance` recorta a 3 (política contradictoria).
- [CÓDIGO] Memoria: lattice/episodic/skills existen (`evo/memory/*`) — **no leídos** [NO VERIFICADO].
- [CÓDIGO] Presupuestos/watchdog: `max_mutations` 1–3 por ciclo; `cycle_adapter.mutation_budget` **no se aplica**; sin límite de ciclos (`while self.running`), `stop()` no interrumpe el `sleep`; sin watchdog; `save_state()` traga excepciones.
- [CÓDIGO] Permisos/red: `SecurityGuard` es lista negra por subcadenas (`rm -rf /`, `dd if=`…), evitable; solo protege dos ficheros propios con comparación de ruta sin normalizar; bitácora `mue_audit.jsonl` guarda 200–500 caracteres de contenido/comandos **sin redactar secretos**. «El agente NO puede desactivarlo» ([CÓDIGO] docstring) no está impuesto.
- [CÓDIGO] Git: `solidifier.commit(...)` tras mutar; sin push en `loop.py`. Absorción: `git clone --depth 1` + `gh api` + `urllib` a api.github.com/raw; no ejecuta lo absorbido pero **tampoco comprueba licencia, seguridad ni sintaxis**; lo registra como gen (`genome.add_gene`).
- [README] Benchmarks repetibles: no verificados; no hay evidencia en código de mejora medida.

## Límites, riesgos y dependencias (hardware, nube, seguridad, mantenimiento)
Contraejemplo: la documentación declara controles (sandbox, git commit, aprendizaje de cada intento, «no puede desactivarse») que el código no implementa — exactamente el patrón «declarado ≠ real» de `CLAUDE.md §5`. Absorber código ajeno sin licencia viola el criterio de AURA. Sin pruebas relevantes visibles de los controles.

## Comparación con AURA          (ruta:símbolo de AURA, estado actual, brecha real o «ya cubierto»)
- Gate de verificación: `autoconstruccion.py:ejecutar` (L640–L675) trata «no se midió» como fallo y revierte; mue-x hace lo contrario. **Cubierto, mejor.**
- Aislamiento: `aislamiento.py` (Landlock) frente a un `subprocess` desnudo. **Cubierto.**
- Controles intocables: `review.py:es_materia_reservada` (L191) + `FicheroIntocable`; mue-x protege 2 ficheros con comparación ingenua.
- Parada: `entorno/control-plane/PARADA` + `motor_autonomia.trabajar` revisa cada vuelta; mue-x no puede interrumpir el `sleep`.
- Único aporte: huella de error recurrente (tipo+mensaje truncado+componente) → ver brecha en IE-021 (`descubrimiento.py:FUENTES` L415).

## Decisión
**Descartar** como código y como arquitectura. Solo referencia: huella de error recurrente, y como lista negativa de fallos de diseño a no repetir (éxito fijo, test sin comprobar, presupuesto declarado y no aplicado).

## Validación mínima
Ninguna sobre mue-x. Para la huella: prueba RED de que dos fallos con la misma clase (`ciclo_autonomo._clase_de_fallo`) y mismo componente producen un único `DECISION_REQUIRED` con contador, y que uno distinto no.

## Licencia y precauciones
MIT, pero no se copia nada. No instalar ni ejecutar (ejecuta código generado/absorbido con privilegios del usuario). Prioridad: descartar (P2 solo para la huella).
