---
id: IE-026
titulo: "viko-nexus/viko-assistant — asistente de voz (Gemini Live) con módulo «self_engineer»"
fuente: https://github.com/viko-nexus/viko-assistant
rama-revision: main @ 02f3718 (último push 2026-09-19)
fecha-revision: 2026-10-22
licencia: "PolyForm Noncommercial 1.0.0 (LICENSE propio; SPDX de GitHub: NOASSERTION). No es código abierto y no admite uso comercial: no copiable"
area: asistentes
estado: investigado
cobertura: "Leídos por lectura remota: viko/self_engineer/{engine,generator,tester,analyzer,backup}.py y LICENSE. NO leídos: planner.py, restarter.py, llm.py, viko/agent/*, viko/tools/executor.py, viko/skills/* (cmd_control, dev_agent, self_update), tests/self_engineer/*, docs/overview/SECURITY.md, CLAUDE.md, planes/specs. No se ejecutó nada."
relacionadas: [IE-009, IE-010, IE-011]
---
## Qué se examinó (rutas y símbolos)
- `viko/self_engineer/engine.py`: `SelfEngineerEngine.run/_run_inner/_execute_plan`, `_save_pending_plan`, `_save_pending_restart`.
- `generator.py`: `generate`, `_generate_patch`, `_generate_new_file`, `apply_changes`.
- `tester.py`: `run`, `_syntax_check`, `_import_check`, `_core_load_check`.
- `analyzer.py`: `build_context`, `_categorize_intent`. `backup.py`: `save`, `restore`, `restore_latest`.
- Metadatos API: Python, 1 estrella, no archivado.

## Patrones relevantes
Matriz pedida (sí/no/parcial):
| Aspecto | Resultado |
|---|---|
| Trazas/episodios | Parcial [CÓDIGO]: solo `read_recent(100)` del log, y solo para la categoría `fix_bug` (analyzer.py). No hay episodios estructurados |
| Errores recurrentes | No [CÓDIGO]: no hay contador ni agrupación; se deja al LLM |
| Objetivos/métricas | No [CÓDIGO]: la entrada es la petición del usuario; solo `TOKEN_BUDGET` de contexto (20 000) |
| Hipótesis | No [CÓDIGO]: hay «plan» (planner.generate), no hipótesis falsable |
| Tests antes/después | Solo después [CÓDIGO]: `tester.run` tras aplicar; sin línea base. Comprueba `ast.parse`, `import` en subproceso y carga de UI; no comportamiento |
| Qué modifica | Código (parches texto `before/after`), skills nuevas y `prompt.txt` completo [CÓDIGO] |
| Sandbox/worktree | No [CÓDIGO]: subprocesos locales con `sys.executable`, timeout 30 s, sobre el árbol vivo |
| Revisión independiente | No [CÓDIGO]: el mismo LLM planifica y genera; el humano confirma |
| Snapshots/rollback | Sí [CÓDIGO]: copia previa en `backups/` + `manifest.json`; `restore` revierte y borra creados. Sin poda; manifiesto ilegible reinicia ids (pérdida de historial) |
| Memoria ep./sem./proc. | Fuera del módulo evaluado; `viko/core/memory.py` y `vector_store.py` NO leídos [NO VERIFICADO] |
| Presupuestos/ciclos/watchdog | Parcial [CÓDIGO]: un pipeline a la vez (`Lock` no bloqueante), un plan pendiente; sin tope de ciclos/coste |
| Permisos/secretos/red | No [CÓDIGO]: sin lista de rutas; `BASE_DIR / ruta` admite `..` y rutas absolutas (generator.py); validación solo por prompt |
| git commit/push/deploy | No hay git en `engine.py` [CÓDIGO]; reinicio de la app solo tras 2.ª confirmación humana |
| Benchmarks de mejora | No (en lo leído) |

Patrón útil, único: **dos puertas humanas** (confirmar plan → aplicar+probar → confirmar reinicio) y copia previa con manifiesto antes de escribir [CÓDIGO]. Débil: «PATCH MISS» deja el fichero escrito y reportado como parcheado [CÓDIGO] — contraejemplo.

## Límites, riesgos y dependencias
- Gemini Live (nube de tercero, clave API): choca con D24. Voz/UI Qt/navegador: no aplicable.
- Escritura sin lista de rutas ni validación de salida; probar después de escribir sobre el árbol real.
- Licencia no comercial. Proyecto de 1 estrella; el README declara «self-modification» pero el código es un pipeline asistido, no un bucle autónomo [INFER].

## Comparación con AURA
- Motor/reversión: `entorno/control-plane/autoconstruccion.py` (≈L661-703 `cambio_revertido_por_error`, «revertidos»): AURA revierte si no puede comprobar la sanidad; Viko no. **Ya cubierto con más rigor.**
- Presupuesto/ciclos: `motor_autonomia.py` `MAX_TAREAS=25`, `EVENTO_PRESUPUESTO_AGOTADO`: **ya cubierto**.
- Materia reservada/revisión: `review.py:191 es_materia_reservada`, `revisores.py`: AURA tiene revisor distinto del autor; Viko ninguno. **Ya cubierto.**
- Aislamiento: `aislamiento.py` (Landlock) vs. subprocesos sin confinamiento. **Ya cubierto.**
- Brecha real: ninguna nueva. Solo contraste: el «PATCH MISS escrito igualmente» es un generador de casos para una prueba AURA de «parche parcial = fallo total» (comprobar si `autoconstruccion.py` ya lo exige; no verificado).

## Decisión
**Descartar** código y dependencia (licencia, nube, sin sandbox). Conservar como contraejemplo y la idea de doble confirmación, que AURA ya tiene vía PARADA/autorización humana.

## Validación mínima
Opcional y pequeña: prueba RED en AURA que un parche con `before` no encontrado aborte y revierta todo (si no existe). Sin esa prueba no se adopta nada.

## Licencia y precauciones
PolyForm Noncommercial: no copiar ni adaptar texto/código. Contenido remoto tratado como dato no confiable; nada ejecutado ni instalado. Prioridad: **P2 (informativo)**.
