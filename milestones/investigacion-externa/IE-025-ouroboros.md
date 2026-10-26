---
id: IE-025
titulo: Lycorecoil/ouroboros — fork de Ouroboros (agente que se reescribe vía git, constitución BIBLE.md)
fuente: https://github.com/Lycorecoil/ouroboros
rama-revision: main @ 31325fb (único commit visible, 2026-02-24)
fecha-revision: 2026-10-22
licencia: MIT (SPDX del fork vía API de GitHub). El upstream del que deriva (README: `joi-lab/ouroboros`; el fork de genesis cita a razzant) NO se comprobó. 1 estrella; no archivado.
area: asistentes
estado: descartado
cobertura: LEÍDO (remoto): ouroboros/tools/git.py, tools/review.py, tools/shell.py, loop.py (resumen dirigido), README.md; árbol. NO leído: agent.py, context.py, consciousness.py, memory.py, supervisor/*, tools/core.py, tools/control.py, tests/ (test_constitution.py, test_smoke.py), colab_*.py. NO se diferenció contra el upstream: no se sabe qué cambia el fork (probablemente una copia).
relacionadas: [IE-023, IE-022]
---
## Qué se examinó (rutas y símbolos)
`tools/git.py:_repo_write_commit/_repo_commit_push/_git_push_with_tests/_run_pre_push_tests`, `tools/review.py:_multi_model_review_async`, `tools/shell.py:_run_shell/_claude_code_edit/_run_claude_cli`, `loop.py:run_llm_loop/_check_budget_limits/_maybe_inject_self_check`.

## Patrones relevantes          (marcar cada afirmación: [CÓDIGO] observado · [README] declarado · [INFER] · [PROPUESTA])
- [CÓDIGO] Trazas: eventos y registro de herramientas (`events.jsonl`) — no leídos en este fork (el fork de IE-023 añade `failure_memory`/`task_stats`; **este no los tiene**: ausentes del árbol).
- [CÓDIGO] Errores recurrentes: **no**. Objetivos/métricas: **no** como mejora; sí coste y rondas.
- [CÓDIGO] Hipótesis/evaluación: **no** estructuradas; el LLM decide qué cambiar. Tests antes/después: pre-push `pytest tests/` que bloquea el push si falla; su valor por defecto es **ambiguo** (la lectura remota dio resultados distintos: ON con timeout 30 s en este fork; en genesis OFF con 60 s) → [NO VERIFICADO] sin leer el literal. Si falta `tests/` o `ctx` es `None`, no corre.
- [CÓDIGO] Qué modifica: su propio código fuente, vía `claude_code_edit` (CLI de Claude Code) y commit/push a su rama (`ouroboros`). Prompt `STRICT: solo modifica ficheros dentro de {work_dir}` — **petición al modelo, no barrera**; herramientas del CLI limitadas a `Read,Edit,Grep,Glob`, modo de permisos por defecto **`bypassPermissions`** con reintento `--dangerously-skip-permissions`.
- [CÓDIGO] Sandbox/worktree: **no**. `_run_shell` acepta cualquier ejecutable (sin `shell=True`), sin lista negra ni rutas protegidas, `cwd` puede salir del repo con `..`, hereda todo el entorno (claves incluidas), sin límites de red; timeout 120 s.
- [CÓDIGO] Revisión: `multi_model_review` (≤10 modelos OpenRouter, mismas condiciones que IE-023); no reconcilia, no bloquea, no exige independencia de modelo; PASS gana a FAIL si ambas palabras aparecen en la línea.
- [CÓDIGO] Git: `git add -A` sin `paths`, `pull --rebase` con fallo ignorado, `push origin <rama_dev>` automático; bloqueo `git.lock` con caducidad 600 s; sin push forzado; sin escaneo de secretos; sin ficheros protegidos.
- [CÓDIGO] Presupuesto/watchdog: `_check_budget_limits` es **parada dura** solo si se conoce `budget_remaining_usd` (>50 % del restante → una última respuesta sin herramientas); `MAX_ROUNDS` 200; aviso suave 30–50 %; autochequeo cada 50 rondas **consultivo** («tú decides»). **No hay watchdog** pese a que un comentario lo menciona.
- [README] Seguridad: núcleo de identidad «intocable» (BIBLE.md, identity.md), revisión por otros LLM antes de commit, `/panic`, circuito de 3 respuestas vacías, rama `ouroboros-stable` como respaldo. «Hardening» sin mecanismo técnico explicado. 131 pruebas smoke (histórico) y 12 constitucionales — en IE-023 se vio que `test_constitution.py` es una especificación por palabras clave, no un test de comportamiento (**no leído aquí**).
- [README] Auto-push al fork del usuario, y artefactos (`evolution.json`, retrato diario) a una web, sin paso de aprobación.
- Benchmarks de mejora: **ninguno**; el único «benchmark» compara dos modelos.
- [README] Memoria: `memory/`, `identity.md`, `knowledge.py` (no leídos).

## Límites, riesgos y dependencias (hardware, nube, seguridad, mantenimiento)
Nube total (OpenRouter, Telegram, GitHub, Drive/Colab, Anthropic, OpenAI opcional) y token de GitHub `repo`. Autonomía con `bypassPermissions` + shell abierta + push automático = el modelo de riesgo opuesto al de AURA. «Conciencia»/identidad es marketing narrativo: sin evidencia de capacidad.

## Comparación con AURA          (ruta:símbolo de AURA, estado actual, brecha real o «ya cubierto»)
- Materia que el agente no puede tocar: `review.py:es_materia_reservada` (L191, `_MATERIA_RESERVADA` L66) y `autoconstruccion.zona_permitida`; en Ouroboros la protección de BIBLE.md es prosa + una prueba de palabras. **Cubierto, con enforcement.**
- Auto-commit/push/deploy: prohibido en AURA (`CLAUDE.md §3`, `quality-gate.sh` en el push humano). **Cubierto.**
- Capacidades vs ejecución arbitraria: AURA solo ejecuta capacidades registradas por el Motor Único (`CLAUDE.md §4`); `_run_shell` abierto contradice la regla. 
- Presupuesto duro: `motor_autonomia.MAX_TAREAS` y `test_red_presupuesto_de_tarea.py`; Ouroboros solo corta si conoce el presupuesto.
- Sin brecha nueva que este repo ayude a ver. Único eco: PARADA/`/panic` (ya cubierto: `orquestador.parada_solicitada`).

## Decisión
**Descartar.** Contraejemplo de seguridad (shell abierta, permisos omitidos, push automático, secretos en el entorno, protección declarada sin mecanismo). Cualquier idea útil (snapshot de rescate, memoria de fallos) está mejor en IE-023.

## Validación mínima
Ninguna: no hay nada que adoptar. Como control negativo, AURA ya debe tener pruebas de que el motor rechaza ejecución arbitraria y un push sin humano (ver `test_red_blindaje_del_mecanismo.py`).

## Licencia y precauciones
MIT; no se copia nada. No instalar ni ejecutar (token de GitHub con `repo`, `bypassPermissions`). Verificar licencia/atribución del upstream si algún día se citase código.
