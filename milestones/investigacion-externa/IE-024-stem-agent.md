---
id: IE-024
titulo: RobertoN0/stem_agent — agente que reescribe prompt/herramientas/memoria con núcleo inmutable y gate de validación
fuente: https://github.com/RobertoN0/stem_agent
rama-revision: master @ c4fff00 (último push 2026-09-08)
fecha-revision: 2026-10-22
licencia: MIT (SPDX vía API de GitHub). No archivado, 1 estrella.
area: asistentes
estado: investigado
cobertura: LEÍDO (remoto): README.md, orchestrator.py (resumen dirigido de 77 KB, por partes que el lector devolvió), growth/apply.py, growth/manifest.py, growth/reflect.py, sandbox/runner.py, eval/benchmark.py; árbol. NO leído: eval/dataset.py, tools/base.py, agent/agent.py, sandbox/Dockerfile, tests/ (test_growth.py 33 KB, test_orchestrator.py 32 KB), mutation_manifest.yaml, artifacts/. Líneas exactas de orchestrator.py no verificadas.
relacionadas: [IE-021, IE-022]
---
## Qué se examinó (rutas y símbolos)
`orchestrator.py` (`main`, `validation_gate`, `smoke_test`, `_docker_run_cmd`, `copy_snapshot`, `bootstrap_gen0`, `make_llm_handler`, `LLMUsageTracker`), `growth/apply.py` (`apply_proposal`, `_PLANNERS`, `_apply_planned`, `_safe_rel_path`, `_check_import_allowlist`), `growth/manifest.py` (`load_mutation_manifest`, `is_mutable_path`, `is_protected_file`), `growth/reflect.py` (`reflect`, `_dispatch_reflection_tool`), `sandbox/runner.py`, `eval/benchmark.py`.

## Patrones relevantes          (marcar cada afirmación: [CÓDIGO] observado · [README] declarado · [INFER] · [PROPUESTA])
- [CÓDIGO] Trazas/episodios: **sí** — el sandbox devuelve trayectorias por tarea; el host registra `llm_calls.jsonl` (peticiones/respuestas completas), transcripciones y config en `artifacts/runs/<id>/`.
- [CÓDIGO] Errores recurrentes: **parcial** — `_select_trajectories` escoge fallos/aciertos de **train**; `reflect` los resume (matriz de confusión, telemetría). Sin agrupación por huella entre generaciones.
- [CÓDIGO] Objetivos y métricas: **sí** — macro-F1 y accuracy en `per_task`, `n_errors`, tokens y `cost_usd` por candidato.
- [CÓDIGO] Hipótesis: **sí** — `reflect` (hasta 6 pasos con herramientas de solo lectura) debe leer antes de proponer y emite `propose_changes` (rationale, intent iterate|halt, changes de 10 clases). El rationale es la hipótesis; que cite task_ids **no se verifica**.
- [CÓDIGO] Tests antes/después: **sí, el patrón más fuerte** — `validation_gate`: rechaza si `n_errors>0`, exige macro-F1 **estrictamente mayor** que el padre (los empates fallan); `smoke_test` de una tarea sin etiqueta; evaluación en train solo si se acepta.
- [CÓDIGO] Qué modifica: `agent/` (prompt, solve loop), `tools/`, `knowledge/`, `self_model/` (README + manifiesto). El orquestador y `growth/` son el «núcleo inmutable» [README]; **la inmutabilidad no se impone con hash** (manifest.py no hace hashing; el orquestador no se leyó entero).
- [CÓDIGO] Sandbox: contenedor Docker por tarea, `--network none` salvo `sandbox.network`, `--memory`, `--cpus`, código del agente montado `:ro`, `/work` escribible, timeout en el host + `docker kill`. **Sin** `--read-only`, `--user`, `--cap-drop` ni scrub de entorno en lo leído. `sandbox/runner.py` por sí solo no aísla (mismo proceso, `signal.alarm` con huecos).
- [CÓDIGO] Revisión independiente: **no** (el mismo modelo investiga, formula y escribe); solo gates estructurales y evaluación posterior.
- [CÓDIGO] Snapshots/rollback: **por generación** — `copy_snapshot` crea `gen_N` (error si existe); candidatos rechazados se borran con `rmtree`; el puntero al padre solo avanza si se acepta (rollback implícito). `_apply_planned` conserva los bytes originales **solo en memoria** y traga errores de rollback.
- [CÓDIGO] Memoria: episódica/semántica en ficheros mutables `self_model/failure_modes.md`, `experiments.md` y `knowledge/` que el reflector actualiza (`replace_file`); `recent_proposals` (últimos 6 resultados) en la autoobservación. Procedimental: herramientas añadidas (`add_tool`).
- [CÓDIGO] Presupuestos/watchdog: `max_generations`, `plateau_generations` (`_bump_plateau_or_stop`), parada por `agent_halt` y por `reflect_error`; **coste registrado, no limitado**. Sin watchdog separado más allá del timeout de contenedor.
- [CÓDIGO] Permisos/secretos: LLM por **proxy en el host** (`make_llm_handler`); la clave de OpenAI (`.env`) no entra al contenedor en los flags vistos. Registro de payloads completos en disco.
- [CÓDIGO] Git: ninguna operación git en lo leído (versionado por directorios `gen_N`).
- [CÓDIGO] Debilidades de `apply_proposal`: `_PROTECTED_FILES` solo se aplica en `delete_file`; `edit_prompt/edit_solve_loop/add_tool/edit_tool` usan rutas fijas sin pasar por `is_mutable_path`; la lista blanca de imports permite `os`/`subprocess`; `halt` no impide aplicar; dos cambios al mismo fichero se pisan; si el manifiesto falta, usa uno heredado y, si está en la zona mutable, el candidato podría ampliarse [NO VERIFICADO].
- [README] Benchmark repetible: **parcial y honesto**. Tabla de 6 generaciones (val macro-F1 0.670→0.733→0.792, 3 rechazadas) y **test retenido**: semilla 0.753 vs evolucionado 0.733 → la mejora de validación **no generalizó**. Sin semillas, repeticiones ni varianza (`benchmark.py`). Resultado cuantitativo reproducible: [NO VERIFICADO].

## Límites, riesgos y dependencias (hardware, nube, seguridad, mantenimiento)
Requiere Docker y OpenAI (nube, clave de tercero: D24). Tarea de dominio único (clasificación de vulnerabilidades PrimeVul). Código joven, un contribuyente. Las protecciones están en el manifiesto/orquestador y en la práctica son más débiles que lo que declaran.

## Comparación con AURA          (ruta:símbolo de AURA, estado actual, brecha real o «ya cubierto»)
- Núcleo intocable: AURA lo impone **en código y con pruebas**: `review.py:es_materia_reservada` (L191), `autoconstruccion.zona_permitida` (L174) / `FicheroIntocable` / `ZonaProhibida`, `test_red_blindaje_del_mecanismo.py`, `test_red_blindaje_del_anillo.py`. **Cubierto, más fuerte** (stem_agent protege por convención y manifiesto).
- Aislamiento: `aislamiento.py` Landlock + `_limitar_recursos` (L222) frente a Docker `--network none`: equivalentes en intención; AURA sin daemon.
- Revisión independiente y desacuerdos: `revisores.py:pedir_revision`/`responder_buzon`, `revision_local.py`: stem_agent no tiene. **Cubierto.**
- Gate de aceptación: `autoconstruccion.ejecutar` (L640–L675) = efecto+sano, no comparación de métricas. **Brecha real [INFER]**: no hay conjunto retenido ni «estrictamente mayor que el padre» para ninguna capacidad de mejora; `formacion.py:formacion` (L100) y `PLAN-DE-FORMACION-AURORA.md` registran aprendizaje pero no miden delta frente a una línea base retenida. Hallazgo útil de stem_agent: **la mejora en validación puede no generalizar**; sin test retenido AURA no lo detectaría.
- Presupuesto: `motor_autonomia.MAX_TAREAS` / `max_tareas` y `test_red_presupuesto_de_tarea.py` superan a stem_agent (coste solo registrado).
- Parada: `PARADA` + chequeo por vuelta. Cubierto.

## Decisión
**Adoptar patrón** (de diseño, no de código): (1) regla de aceptación «estrictamente mayor que el padre y cero errores», (2) **conjunto retenido** que el reflector/agente nunca ve, (3) candidato rechazado = directorio desechable, el padre solo avanza al aceptar, (4) registrar el resultado negativo (generalización). **Probar en aislamiento** solo si el CEO abre un DP de «mejora medida». No adaptar código.

## Validación mínima
Experimento de papel + prueba: con una métrica sintética de dos conjuntos (visible y retenido), un candidato que sube el visible y baja el retenido debe ser rechazado por el gate; control: un gate que solo mira el visible lo acepta (mutante que debe morir con `herramientas.mutar`). Sin LLM, determinista, local.

## Licencia y precauciones
MIT; sin necesidad de copiar. No instalar (Docker + OpenAI). Contenido remoto = dato no confiable. Prioridad P1 (patrón de conjunto retenido), condicionada a un DP aprobado.
