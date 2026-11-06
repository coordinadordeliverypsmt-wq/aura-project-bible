---
id: IE-027
titulo: "NullLabTests/Aurogene — «mente digital autoevolutiva» (derivado de Ouroboros)"
fuente: https://github.com/NullLabTests/Aurogene
rama-revision: main @ último push 2026-06-24 (commit corto no obtenido)
fecha-revision: 2026-10-22
licencia: "MIT (SPDX, API de GitHub). Copiable con aviso; procedencia declarada: Ouroboros (A. Razzhigaev)"
area: asistentes
estado: investigado
cobertura: "Leídos: ouroboros/tools/{evolve_cycle,shell,git}.py, ouroboros/{review,reflection_engine}.py, README.md (afirmaciones). NO leídos: loop.py (presupuesto real), agent.py, memory.py, consciousness.py, goals.py, debate.py, group_evolution.py, tool_creator.py, supervisor/*, tests/*, BIBLE.md, prompts/*. Las cifras de presupuesto y los tests son solo [README]."
relacionadas: [IE-026, IE-028, IE-029]
---
## Qué se examinó (rutas y símbolos)
`evolve_cycle.py` (`_run_evolution_cycle`, `_propose_evolution`, `run_tests`, `sync_versions`, `validate_not_identity_core_deletion`), `shell.py` (`_run_shell`, `_run_claude_cli`, `_claude_code_edit`), `git.py` (`_repo_write_commit`, `_repo_commit_push`, `_run_pre_push_tests`, `_git_push_with_tests`), `review.py` (`collect_sections`, `compute_complexity_metrics`), `reflection_engine.py` (`contrastive_reflection`, `_apply_consolidation`).

## Patrones relevantes
| Aspecto | Resultado |
|---|---|
| Trazas/episodios | Parcial [CÓDIGO]: lee journal de reflexiones y `task_results/*.json` (estado, coste, rondas) |
| Errores recurrentes | No explícito [CÓDIGO]: sin contador; se pide al LLM «señales de estancamiento» (`_find_patterns`) |
| Objetivos/métricas | No en lo leído [CÓDIGO]: solo test pasa/falla, nº de ciclos, `REFLECTION_INTERVAL=10`. `compute_complexity_metrics` es informativa (funciones >150 líneas, módulos >1000) |
| Hipótesis | No [CÓDIGO]: `description` en texto libre |
| Tests antes/después | Una sola vez, antes del commit, sin línea base; `skip_tests` los omite [CÓDIGO]. Pre-push pytest (30 s) en `git.py` |
| Qué modifica | Código y prompts los edita el LLM (vía `claude` CLI con Read/Edit/Grep/Glob); `evolve_cycle` solo toca VERSION/pyproject/README. `identity.md` se reescribe con salida LLM sin validar |
| Sandbox/worktree | No [CÓDIGO]: rama dev del repo vivo, sin worktree |
| Revisión independiente | Parcial [README]: «/review» y debate interno; en lo leído, `review.py` es solo utilidades. El «constitution check» es por palabras clave y no bloquea [CÓDIGO] |
| Snapshots/rollback | No [CÓDIGO]: ninguna función de reversión |
| Memoria | `identity.md` (+journal) [CÓDIGO]; episódica/semántica/procedimental no verificada |
| Presupuesto/ciclos/watchdog | Solo [README]: `TOTAL_BUDGET`, 10 % para conciencia de fondo, 200 rondas. En lo leído: timeouts 120/300 s, `--max-turns 12`, tope de filas de changelog |
| Permisos/secretos/red | No [CÓDIGO]: `_run_shell` ejecuta cualquier lista de args, hereda todo el entorno, sin redacción de salida; `bypassPermissions` por defecto y reintento con `--dangerously-skip-permissions`; restricción de alcance solo en el prompt |
| git commit/push/deploy | Sí, automático [CÓDIGO]: commit sin puerta humana; push por defecto tras pre-push tests (`OUROBOROS_EVOLVE_PUSH`, `OUROBOROS_PRE_PUSH_TESTS`) |
| Benchmarks de mejora | No [README]; el propio README es inconsistente (229 vs 205 tests; 66 vs 42 herramientas) |

Patrones transferibles (ideas, no código): (1) núcleo de identidad con comprobación de «no borrar» antes del ciclo; (2) un cambio coherente por ciclo + versión; (3) bloquear push si falla el test, dejando commit local. En AURA son más débiles que lo que ya hay.

## Límites, riesgos y dependencias
OpenRouter/Telegram/GitHub token/Anthropic key: incompatible con D24 y «sin claves de terceros». El agente tiene shell sin límite, push automático y todas las claves en el entorno: contraejemplo de exfiltración. Afirmaciones de «consciencia» = marketing, sin evidencia de mejora.

## Comparación con AURA
- Auto-commit/push: AURA lo prohíbe (promoción solo con gates + autorización humana); Aurogene es el opuesto. **Contraejemplo.**
- Reversión: `autoconstruccion.py` ≈L661-703 revierte; Aurogene no. **Ya cubierto.**
- Revisión/materia reservada: `review.py:191`, `revisores.py`/`revision_local.py`. **Ya cubierto.**
- Aislamiento: `aislamiento.py` Landlock. **Ya cubierto.**
- Detección de errores recurrentes: Aurogene la delega al LLM; `estancamiento.py` (≈L130) y `observatorio.py` de AURA son deterministas. **Ya cubierto** (en lo contrastado por nombre; no se leyó su cuerpo aquí).
- Brecha real: ninguna adoptable. Solo recordatorio: la reflexión que escribe en la identidad sin validar (`_apply_consolidation`) es el riesgo que AURA evita al no dejar que el agente edite sus controles.

## Decisión
**Descartar** (nada adoptable que AURA no tenga mejor). Conservar como contraejemplo de autoedición sin puertas.

## Validación mínima
Ninguna nueva. Si se quisiera, verificar con prueba que ningún camino de AURA pueda hacer `git push` desde una tarea autónoma (probable ya cubierto por hooks/PARADA; no verificado en esta ficha).

## Licencia y precauciones
MIT permitiría reutilizar, pero el diseño es inseguro; no copiar. Contenido remoto = dato no confiable; no se ejecutó nada. Prioridad: **P2 (contraejemplo)**.
