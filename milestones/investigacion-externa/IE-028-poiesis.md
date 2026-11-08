---
id: IE-028
titulo: "china-nyx/poiesis — «SO autoevolutivo; el LLM es la CPU»"
fuente: https://github.com/china-nyx/poiesis
rama-revision: master @ último push 2026-06-27 (commit corto no obtenido)
fecha-revision: 2026-10-22
licencia: "Sin licencia (license=null; no hay fichero LICENSE en el árbol). Sin licencia explícita = NO copiable"
area: asistentes
estado: investigado
cobertura: "Leídos: poiesis/services/patcher.py, poiesis/kernel/{watchdog,image,loader,anchor}.py, services/executor.py, checks/ring.py, README.md. NO leídos: kernel/{proc,sched,config,boot,supervisor}.py, services/{cpu,syscalls,bg,cron,fs}.py, client/cli.py, tests/*, deploy/*. Por tanto: presupuestos (config.MAX_EVOLVE_ATTEMPTS, WATCHDOG_STALE_AFTER) sin valores; permisos/red/secretos de syscalls y bg NO VERIFICADOS."
relacionadas: [IE-027, IE-029]
---
## Qué se examinó (rutas y símbolos)
`patcher.evolve`, `image.{new_worktree,promote,tag_good,rollback,rollback_and_reexec,cleanup_stale,reexec}`, `loader.{selfcheck,verify_tree,_smoke}`, `anchor.check/INVARIANTS`, `watchdog.{beat,_monitor,start}`, `executor._run_task`, `checks/ring.py`.

## Patrones relevantes
| Aspecto | Resultado |
|---|---|
| Trazas/episodios | Parcial [CÓDIGO]: procesos persistentes con PCB y `SYSLOG` JSONL de generaciones («promoted»/«rejected»); detalle de procesos no leído |
| Errores recurrentes | No [CÓDIGO] en lo leído |
| Objetivos/métricas | No; el disparador es una *propuesta* que un proceso archiva al bloquearse («block») [CÓDIGO en ring.py, mock] |
| Hipótesis | No explícita; propuesta de capacidad faltante [INFER] |
| Tests antes/después | Solo puerta posterior [CÓDIGO]: `verify_tree` en proceso nuevo con `cwd` = candidato (humo, `checks/*`, ancla). Sin línea base |
| Qué modifica | Código bajo `poiesis/services/` (nunca `kernel/`) — **restricción solo por prompt** (`EVOLVER_SYSTEM`), no aplicada en código [CÓDIGO] |
| Sandbox/worktree | **Sí** [CÓDIGO]: worktree git desechable («partición B»); el árbol vivo no se toca hasta la promoción verificada |
| Revisión independiente | No [CÓDIGO]: el mismo LLM edita; la puerta es mecánica, sin humano |
| Snapshots/rollback | **Sí** [CÓDIGO]: etiqueta `good` (último bueno), `promote` ff-only, `rollback_and_reexec` a `good` si el arranque no es sano; fallos: `promote` ignora error de commit, `reset --hard` descarta cambios no confirmados |
| Memoria | Base de conocimiento, skills y toolbox globales [README]; no leídos |
| Presupuestos/ciclos/watchdog | **Sí** [CÓDIGO]: `MAX_EVOLVE_ATTEMPTS` por proceso; `max_rounds` por intento; watchdog de latido en hilo, `os._exit(70)` si no hay latido en `WATCHDOG_STALE_AFTER`, y el reinicio/rollback lo decide el arranque |
| Permisos/secretos/red | No [CÓDIGO]: `run_bg` pasa cualquier cadena a `bg.launch`; sin lista, sin red/entorno controlados; «workspace» solo por prompt |
| git commit/push/deploy | Commit y fast-forward a `main` local automáticos al promover [CÓDIGO]; no se vio push remoto; re-exec automático |
| Benchmarks de mejora | No. `ring.py` es regresión funcional con CPU simulada (sin LLM) [CÓDIGO], no medida de mejora |

Patrones útiles (ideas): (a) candidato en worktree + verificación en subproceso con `cwd` del candidato + promoción ff-only + etiqueta `good`; (b) puerta que se ejecuta *en el arranque y antes de promover*; (c) latido solo desde el bucle principal, de modo que un cuelgue real dispara el watchdog; (d) regresión de «anillo» con CPU simulada, barata y determinista.
Debilidad clave [CÓDIGO]: `anchor.py` solo comprueba tres subcadenas ("loader", "verify_tree", "beat(") y **no se protege a sí mismo**; un parche en `services/` puede mantener esas palabras (p. ej. en comentarios) y vaciar la puerta. Autoprotección de controles = justo lo que AURA exige.

## Límites, riesgos y dependencias
Sin licencia. Sin sandbox de ejecución (el worktree aísla *el código*, no los comandos). Aislamiento del kernel basado en confianza del prompt. Endpoint LLM y PCB: dependencias no evaluadas. Proyecto de 0 estrellas.

## Comparación con AURA
- Candidato aislado: AURA dispone de worktrees por convención (CLAUDE.md §3) y `aislamiento.py` (Landlock) para ejecución; `autoconstruccion.py` ≈L661-703 revierte tras escribir. **Brecha parcial real:** AURA parece escribir el cambio *en el árbol* y revertir si no es sano (`cambio_revertido_por_error`), mientras Poiesis prueba en un candidato desechable y solo promueve si pasa. Verificar leyendo `autoconstruccion.py` si el candidato se materializa en worktree antes de tocar el árbol vivo. [INFER, sin leer el cuerpo completo]
- Controles intocables: Poiesis lo hace por prompt+anchor débil; AURA con `es_materia_reservada` (`review.py:191`) y PARADA lo hace mejor. **Ya cubierto.**
- Watchdog/presupuesto: `motor_autonomia.py` `MAX_TAREAS`, `EVENTO_PRESUPUESTO_AGOTADO`; PARADA. Latido+salida 70 no tiene equivalente leído; solo relevante si AURORA corre en continuo (hay un watchdog propio no inspeccionado).
- Mutación como puerta: `herramientas/mutar.py` + `quality-gate.sh` superan el «humo + anchor».
- Brecha de objetivo/medición de mejora: ni Poiesis ni AURA la cubren aquí; AURA lo gobierna con `PLAN-DE-FORMACION-AURORA.md` y evidencia de uso real.

## Decisión
**Investigar más (solo el patrón candidato-en-worktree + etiqueta `good`)**; no copiar código. El patrón de «puerta que se verifica en proceso nuevo con el cwd del candidato» merece una lectura de AURA antes de decidir nada.

## Validación mínima
Lectura previa de `autoconstruccion.py` para responder: ¿el cambio se prueba en un worktree/copia antes de escribir en el árbol vivo? Si no, prueba RED: «un cambio que rompe el gate no deja rastro en el árbol vivo». Sin DP no se construye.

## Licencia y precauciones
Sin licencia: no copiar ni adaptar texto. Solo ideas generales (worktree, tag, ff-only), que son patrones git estándar. Contenido remoto = dato no confiable; no se ejecutó nada. Prioridad: **P1 (patrón) / P2 (resto)**.

## Seguimiento (2026-10-22): brecha confirmada en AURA y DP

La brecha que esta ficha dejaba como `[INFER]` está **confirmada ejecutando** sobre una copia:
- durante la verificación el fichero vivo contiene el candidato;
- tras un SIGKILL queda escrito, sin respaldo y sin evento.

Ver `../m3-entry/evidencia-candidato-aislado-2026-10-22/`. Decision Package (alternativa A, solo el patrón, sin
código porque este repo no tiene licencia): `../m3-entry/DP-CANDIDATO-AISLADO-AUTOCONSTRUCCION.md`. Pendiente del CEO,
porque toca `_INTOCABLES`.
