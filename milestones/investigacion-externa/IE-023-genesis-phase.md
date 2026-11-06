---
id: IE-023
titulo: EXOAI-1/genesis-phase — fork de Ouroboros con memoria de fallos y estadísticas de tareas
fuente: https://github.com/EXOAI-1/genesis-phase
rama-revision: main @ 3df3163 (último push 2026-03-22)
fecha-revision: 2026-10-22
licencia: MIT (SPDX vía API de GitHub). No archivado, 2 estrellas. Declara basarse en Ouroboros de razzant (README) — la licencia del upstream no se comprobó.
area: asistentes
estado: investigado
cobertura: LEÍDO (remoto): ouroboros/failure_memory.py, task_stats.py, tools/git.py, tools/review.py, supervisor/git_ops.py, tests/test_constitution.py, README.md; árbol. NO leído: loop.py, agent.py, consciousness.py, context.py, tools/shell.py (solo leído en el fork IE-025), supervisor/workers.py, test_smoke.py, colab_*.py, setup.py. Lo que no se leyó se marca [NO VERIFICADO].
relacionadas: [IE-025, IE-022]
---
## Qué se examinó (rutas y símbolos)
`failure_memory.get_recent_failures`; `task_stats.compute_task_stats/compute_tool_stats/write_stats_summary`; `tools/git.py:_git_push_with_tests/_run_pre_push_tests/_repo_commit_push`; `tools/review.py:_multi_model_review_async/_parse_model_response`; `supervisor/git_ops.py:checkout_and_reset/_create_rescue_snapshot/safe_restart/import_test`; `tests/test_constitution.py`.

## Patrones relevantes          (marcar cada afirmación: [CÓDIGO] observado · [README] declarado · [INFER] · [PROPUESTA])
- [CÓDIGO] Trazas/episodios: **sí, como log** `logs/events.jsonl` y `logs/tools.jsonl`; `task_stats` solo aritmética sobre las últimas 200/500 líneas.
- [CÓDIGO] Errores recurrentes: **parcial** — `failure_memory` marca como recurrentes solo errores de herramienta vistos ≥2 veces (últimos 20, clave «herramienta: error» truncada a 60 caracteres); los fallos de tarea no se deduplican. Nada se persiste (se rederiva en cada llamada); cualquier excepción devuelve cadena vacía (fallo silencioso).
- [CÓDIGO] Objetivos/métricas: **parcial** — tasa de éxito por tipo de tarea, rondas medias/máx, fiabilidad por herramienta (`compute_tool_stats`). No se ve que alimenten decisiones de mejora (¿quién llama a `get_rounds_stats_for_type`? [NO VERIFICADO]).
- [CÓDIGO] Hipótesis: **no** estructurada; el LLM «ve» los fallos y decide («evita repetir estos errores»); el código no inyecta el texto (lo hace el llamador).
- [CÓDIGO] Tests antes/después: pre-push `pytest tests/ -q` **bloquea el push si falla**, pero **desactivado por defecto** (`OUROBOROS_PRE_PUSH_TESTS`≠"1" → no corre), se omite si no hay `tests/` o `ctx is None`, timeout 60 s; un `pull --rebase` fallido se ignora. No hay medición antes/después de comportamiento.
- [CÓDIGO] Qué modifica: su propio código/prompt/memoria vía git (`repo_write_commit`, `repo_commit_push`).
- [CÓDIGO] Sandbox/worktree: **no** en lo leído.
- [CÓDIGO] Revisión independiente: `multi_model_review` consulta ≤10 modelos de OpenRouter en paralelo (concurrencia 5, 120 s), cada uno aislado de los otros; **no reconcilia desacuerdos** (lista de veredictos), **no bloquea commits**, no verifica que el revisor sea distinto del autor; `_parse_model_response` marca PASS si la línea contiene PASS y FAIL.
- [CÓDIGO] Snapshots/rollback: **sí, lo más aprovechable** — `supervisor/git_ops.py` con `unsynced_policy` (`ignore|block|rescue_and_block|rescue_and_reset`): `_create_rescue_snapshot` guarda estado, diff, commits no empujados y hasta 200 ficheros/≈12 MB sin commitear **antes** de `git reset --hard origin/<rama>`; `safe_restart` prueba la rama de desarrollo con `import_test` y cae a la estable. `import_test` solo hace `import ouroboros, ouroboros.agent` (no ejecuta tests); usa `python3` y no `sys.executable`.
- [CÓDIGO] Git automático: `repo_commit_push` hace `git add -A` si no hay `paths` y `git push origin <rama_dev>`; **push automático**; sin push forzado; sin escaneo de secretos; sin ficheros protegidos.
- [CÓDIGO] Constitución: `test_constitution.py` es una «SPEC_TEST» de palabras clave y booleanos fijados por la propia prueba; **no carga BIBLE.md ni ejercita ninguna protección** (lo dice el propio fichero).
- [CÓDIGO] Presupuestos: se emiten eventos `llm_usage` por revisión; **sin tope aplicado** en lo leído. [README] `TOTAL_BUDGET`, límite de rondas, circuito de pausa: no verificados (loop.py no leído).
- [CÓDIGO] Red/secretos: Telegram, OpenRouter, GitHub token, Drive (README); el entorno del agente contiene todos los secretos.
- [README] Mejoras: «8 mejoras», sin benchmark ni resultados; las «6 correcciones» no aparecen en el README.

## Límites, riesgos y dependencias (hardware, nube, seguridad, mantenimiento)
Nube obligatoria (OpenRouter, Telegram, Colab, Drive, GitHub): choca con D24 (local-first, sin claves de terceros). Push automático con secretos en el entorno. Proyecto minúsculo (2 estrellas, un único commit visible); sin evidencia de mejora.

## Comparación con AURA          (ruta:símbolo de AURA, estado actual, brecha real o «ya cubierto»)
- Revisión independiente: `revisores.py:pedir_revision` (L353) con buzón y `respuesta_ya_registrada`/`intentos_de_revision`, y `revision_local.py` (expediente con citas verificables `localizar`/`vigente`). **Cubierto, con más rigor** (genesis no reconcilia ni bloquea).
- Auto-push: AURA lo prohíbe; `CLAUDE.md §3` exige merge/push humano con quality gate (`quality-gate.sh`). **Cubierto.**
- Parada: `motor_autonomia.trabajar` + `PARADA`. **Cubierto.**
- Brecha real [INFER]: **instantánea durable previa a revertir/reiniciar**. `autoconstruccion.py:ejecutar` (L660–L675) restaura con `ruta.write_text(original)` desde memoria: si el proceso muere entre la escritura y el revert queda el fichero modificado (la regla de `mutar.py` ya reconoce que un SIGKILL deja ficheros mutados y pide `git checkout`). Genesis guarda el estado en disco antes del reset. [CÓDIGO] `grep` en `autoconstruccion.py` no encuentra respaldo en disco (`original` solo en variable local, L601/L663/L670); mitigación parcial si el fichero está versionado en git (recuperable con `git checkout`), no si el cambio previo estaba sin commitear. Evento `cambio_aplicado` (L676) se registra después del revert, no antes de escribir.
- Recurrencia: misma brecha que IE-021 (`descubrimiento.py:FUENTES` L415).

## Decisión
**Solo referencia.** Patrón útil: snapshot de rescate en disco previo a cualquier operación destructiva (adaptable a `autoconstruccion`); estadísticas por tipo de tarea derivadas del log (ya análogo a `observatorio.ciclos`). Descartar: push automático, `add -A`, gate desactivado por defecto, constitución como prueba de palabras clave.

## Validación mínima
Prueba RED: simular muerte del proceso (excepción `BaseException` tras `write_text` pero antes de revertir) y comprobar que existe una copia en disco y que un arranque posterior la detecta y restaura o eleva `DECISION_REQUIRED`. Control: la prueba falla con el código actual si el original solo vive en memoria.

## Licencia y precauciones
MIT; no se copia código. Verificar licencia del upstream antes de cualquier uso derivado. No instalar. P1 solo para la brecha de snapshot durable (decisión del CEO para abrir DP); el resto P2.
