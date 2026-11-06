---
id: IE-021
titulo: kayba-ai/recursive-improve — trazas, detectores deterministas y ratchet keep/revert
fuente: https://github.com/kayba-ai/recursive-improve
rama-revision: main @ 9cf4b85 (último push 2026-03-31)
fecha-revision: 2026-10-22
licencia: Apache-2.0 (SPDX vía API de GitHub; fichero LICENSE presente). No archivado, 297 estrellas.
area: asistentes
estado: investigado
cobertura: LEÍDO (remoto, vía WebFetch): ratchet/engine.py, ratchet/git_ops.py, ratchet/config.py, eval/detectors.py, evolve/engine.py, README.md; árbol completo. NO leído: cli.py (20 KB, el bucle real), ratchet/scorer.py, ratchet/log.py, capture/*, store/*, data/*SKILL.md (las instrucciones al agente), dashboard, tests/. No se clonó ni se ejecutó nada.
relacionadas: [IE-009, IE-022, IE-024]
---
## Qué se examinó (rutas y símbolos)
`recursive_improve/ratchet/engine.py` (`ratchet_eval`, `ratchet_commit`, `ratchet_revert`, `ratchet_log_iteration`, `ratchet_status`), `ratchet/git_ops.py` (`create_ratchet_branch`, `commit_iteration`, `revert_to_last_commit`), `ratchet/config.py` (`RatchetConfig`, `parse_program_md`), `eval/detectors.py` (`detect_loops`, `detect_give_up`, `detect_errors`, `detect_recovery`, `detect_clean_success`, `detect_duration_outlier`), `evolve/engine.py` (`evolve_init`, `evolve_update`, `evolve_status`), README.

## Patrones relevantes
- [CÓDIGO] Captura de trazas: **parcial** (README + estructura `capture/`: `ri.patch()` parchea clientes OpenAI/Anthropic/LiteLLM y guarda JSON por llamada; el código de `capture/` no se leyó) .
- [CÓDIGO] Detección de errores: **sí, determinista, sin LLM** (`eval/detectors.py`): bucles (≥3 llamadas consecutivas a la misma herramienta), frases de rendición (regex), errores en respuestas de herramienta (regex), recuperación, duración atípica (>60 s). **Errores recurrentes: no** hay detector dedicado (`detect_errors` cuenta, no agrupa por contenido; `detect_recovery` construye `error_tool_ids` y no lo usa).
- [CÓDIGO] Objetivos y métricas: **sí**. `parse_program_md` lee un `program.md` con métricas (`direction` minimize/maximize, `weight`), `max_iterations`=20, `plateau_patience`=3, `time_budget_minutes`=15, `max_duration_hours`=8. `ratchet_status` solo **informa** de plateau; quién lo hace cumplir está en `cli.py`/skill ([NO VERIFICADO]).
- [CÓDIGO] Tests antes/después: **parcial**. `ratchet_eval` ejecuta `run_eval` + un `compute_baselines.py` opcional (timeout 600 s) y compone un score; **la comparación y la decisión keep/revert la hace el llamador** (no está en estos ficheros). Fallos de la evaluación se tragan (`except` → métricas vacías, `trace_count`=0).
- [CÓDIGO] Qué modifica: código y prompts del agente (README); `improve_command` invoca `claude -p` con herramientas `Edit,Write,Bash,Read,Glob,Grep` y **sin lista de rutas protegidas** (`config.py` no define editables/protegidos).
- [CÓDIGO] Worktree/sandbox: **worktrees git por isla** en `/evolve` (`evolve_init` → `n_islands`=4 worktrees desde HEAD); ratchet usa una **rama** `ri/ratchet-<UTC>`. No hay sandbox de proceso/red.
- [CÓDIGO] Snapshots/rollback: commit por iteración en la rama; revert = `git checkout -- .` + `git clean -fd` (sin `check=True` en el clean). **Destructivo** sobre cambios no relacionados; `git add -A` mete todo.
- [CÓDIGO] Git: commit automático en rama propia; **sin push** en `git_ops.py`.
- [CÓDIGO] Revisión independiente/desacuerdo: **no** (el mismo agente propone y el score decide). README: «espera tu aprobación» en `/recursive-improve` (no verificado en código).
- [CÓDIGO] Memoria: log JSONL de iteraciones (`ratchet_log.jsonl`) + resumen; sin memoria semántica/procedimental. `store/` (SQLite/JSON) no leído.
- [CÓDIGO] Presupuestos/watchdog: parámetros en config; **ejecución real no verificada**. Sin watchdog propio.
- [README] Benchmarks repetibles: el README **no da ningún resultado cuantitativo** («Only improvements survive» es declaración). `benchmark.py` no leído. Sin evidencia de mejora real.
- [INFER] Red/secretos: las trazas se quedan en `eval/traces/` pero el análisis lo hace Claude Code/Codex → el contenido de las trazas sale al proveedor del modelo. No hay redacción de secretos en lo leído.

## Límites, riesgos y dependencias (hardware, nube, seguridad, mantenimiento)
Depende de Claude Code/Codex (nube). Autoedición con `Bash` sin confinamiento. Revert destructivo. Un solo contribuyente aparente, último push hace 7 meses [INFER por fecha]. Contenido remoto tratado como dato.

## Comparación con AURA          (ruta:símbolo de AURA, estado actual, brecha real o «ya cubierto»)
- Revert tras fallo: `entorno/control-plane/autoconstruccion.py:ejecutar` (L545–L675) revierte si `not (efecto and sano)` y «no se midió» = revertir. **AURA ya cubre** el keep/revert, con más rigor (autorización previa `SinAutorizacion`, `ParadaActiva`, `ZonaProhibida`, `FicheroIntocable`).
- Materia reservada / controles intocables: `review.py:es_materia_reservada` (L191) + `autoconstruccion.zona_permitida`. recursive-improve **no tiene** equivalente (editables sin lista).
- Parada y tope: `motor_autonomia.trabajar` (L74) comprueba `orq.parada_solicitada` en cada vuelta y `MAX_TAREAS`. Cubierto.
- Aislamiento: `aislamiento.py` (Landlock, `_confinar_ficheros`, `_limitar_recursos`) supera a ratchet (nada).
- Brecha real [INFER]: **score compuesto antes/después con línea base persistida** y `plateau_patience` medido sobre métricas, no solo «efecto booleano + verificación sana». `estancamiento.py:hay_estancamiento` (L130) cuenta ciclos sin avance con `K_ESTANCAMIENTO=None` (inerte) pero no compara una métrica con su baseline.
- Brecha real [INFER]: detector de **fallos recurrentes por huella** (aquí tampoco existe): `ciclo_autonomo.py:_clase_de_fallo` (L64) clasifica, pero `descubrimiento.py:FUENTES` (L415) no tiene fuente «fallo repetido».

## Decisión
**Adoptar patrón** (no código): (a) detectores deterministas sobre trazas con salida de tasas; (b) iteración con baseline persistido y decisión keep/revert sobre un score declarado antes. Descartar tal cual: edición con `Bash` libre, `git clean -fd`, `git add -A`.

## Validación mínima
Prueba RED en `walking-skeleton/` o `entorno/control-plane/`: dado un historial de ciclos con una métrica que no mejora k veces, `estancamiento()` eleva `DECISION_REQUIRED`; con la métrica mejorando, no. Caso de control: el mutante «ignora la métrica» debe sobrevivir a la prueba antigua y morir con la nueva (`herramientas.mutar`).

## Licencia y precauciones
Apache-2.0: código copiable con atribución y NOTICE; aun así no se adapta código (el patrón es trivial). No instalar (`pip install` desde GitHub, parchea clientes LLM). Prioridad P2.
