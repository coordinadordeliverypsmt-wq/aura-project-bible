---
id: IE-029
titulo: "Cole-Will-I-Am/Heka — agente que reescribe su código con «consejo» de tres LLM locales"
fuente: https://github.com/Cole-Will-I-Am/Heka
rama-revision: main @ último push 2026-03-24 (commit corto no obtenido)
fecha-revision: 2026-10-22
licencia: "Sin licencia (license=null; sin LICENSE en el árbol). NO copiable"
area: asistentes
estado: descartado
cobertura: "Leídos: heka/{evolution,council,watchdog,memory,soul}.py y README.md. NO leídos: main.py (donde se decide si se respeta `review()`), consciousness.py, mind.py, journal.py, perception.py, GENESIS.md, systemd/heka.service. No hay carpeta de tests en el árbol [CÓDIGO]."
relacionadas: [IE-027, IE-028]
---
## Qué se examinó (rutas y símbolos)
`evolution.Evolution.{plan,implement,review,execute,git_record,update_readme,_rollback}`, `council.Council.{code_review,deliberate,_needs_debate}`, `watchdog.Watchdog.{heartbeat,runtime_hazards,opinion_health_check,check_previous_instance}`, `memory.{MemoryPersistence,SnapshotManager}`, `soul.py`.

## Patrones relevantes
| Aspecto | Resultado |
|---|---|
| Trazas/episodios | Parcial [CÓDIGO]: `store_procedural` registra éxito/fallo de cada evolución; `heartbeat.json` |
| Errores recurrentes | No [CÓDIGO] |
| Objetivos/métricas | «Deseos» y «estado de ánimo» numéricos (soul.py, watchdog) — son estado interno, no métrica de mejora; el «gap de opiniones» probablemente nunca se activa por un bug (`last_opinion_cycle` se reescribe en cada llamada) [CÓDIGO] |
| Hipótesis | No; el plan tiene `confidence` ≥ 0.3 autodeclarada [CÓDIGO] |
| Tests antes/después | **No hay ejecución de tests** [CÓDIGO]; solo `ast.parse` (con 1 reintento) y mínimo 3 líneas no vacías. Sin carpeta `tests/` |
| Qué modifica | Su propio código fuente (≤3 ficheros por plan) y `README.md` [CÓDIGO] |
| Sandbox/worktree | No [CÓDIGO]: escribe en el árbol vivo |
| Revisión independiente | Parcial [CÓDIGO]: `code_review` con analista+codificador en paralelo y arquitecto decide (empate/vacío = rechazo). Pero `Evolution.execute()` pone `review_passed=True` sin consultar el veredicto; quien llame debe aplicarlo (no leído: main.py). Los revisores ven código truncado a 3000 caracteres/fichero y **no ven pruebas**; no se garantiza independencia del autor. «Debate» solo si hay división o confianza media <0.62 |
| Snapshots/rollback | Parcial [CÓDIGO]: copia `.bak` por ciclo y `_rollback`; los ficheros nuevos no se revierten; README sin copia; `SnapshotManager` de SQLite conserva 10 [CÓDIGO]; rollback por ciclo y «journal checkpoint» solo [README] |
| Memoria | Enum con EPISODIC/SEMANTIC/PROCEDURAL pero **sin tratamiento diferenciado**, sin ranking, sin consolidación ni olvido; sin historial de valores (sobrescribe) [CÓDIGO]. SQLite WAL + checksum SHA-256 por fila |
| Presupuestos/ciclos/watchdog | Parcial [CÓDIGO]: ≤3 ficheros, presupuestos de tokens, umbrales de disco/RAM/CPU; sin enfriamiento ni tope de ciclos en lo leído; el reinicio depende de systemd (no hay rollback en el watchdog) |
| Permisos/secretos/red | No evaluado en lo leído; sin lista de ficheros protegidos [CÓDIGO]; Ollama local |
| git commit/push/deploy | Sí, **automático**: commit por ciclo y `push` a `origin` por defecto salvo `HEKA_GIT_PUSH=0` [CÓDIGO] |
| Benchmarks de mejora | No. El README no menciona tests |

Patrones útiles (mínimos): consejo con *arquitecto desempata y empate = rechazo conservador*; debate adaptativo solo ante desacuerdo; checksum por registro de memoria. Todo ello ya existe o es trivial.

## Límites, riesgos y dependencias
El «consejo» de tres LLM del mismo operador no es revisión independiente real [INFER]; la compuerta puede ignorarse en `execute`; push automático por defecto; lenguaje de «conciencia/angustia cognitiva» es marketing sin medición (mezcla de caracteres chinos en un texto interno sugiere salida LLM sin revisar). Sin licencia. Último push hace 7 meses.

## Comparación con AURA
- Revisión: `revisores.py`/`revision_local.py` + `review.py:191 es_materia_reservada`; la puerta de AURA es independiente del autor y bloquea. **Ya cubierto con mucho más rigor.**
- Memoria: la de producto (`walking-skeleton/aura_skeleton/modules/memory.py`, `core/historial*`/`recuperacion.py`) no se contrasta aquí con detalle; Heka no aporta (tipos sin comportamiento, sin consolidación). **Sin brecha.**
- Rollback/aislamiento/mutación/gate: `autoconstruccion.py` (revierte), `aislamiento.py`, `mutar.py`, `quality-gate.sh`. **Ya cubierto.**
- Auto-push: prohibido en AURA. **Contraejemplo.**
- Brecha real: ninguna. Útil como lista de verificación negativa: «un veredicto que no se aplica» (review_passed=True fijo) es otra instancia de «declarado ≠ real» (CLAUDE.md §5): conviene una prueba AURA de que un rechazo del revisor impide de verdad el paso (mutar el cableado, como exige §2).

## Decisión
**Descartar.** Sin licencia, sin tests, sin sandbox y con push automático; nada que AURA no tenga ya.

## Validación mínima
Opcional: mutante en `mutaciones/*.toml` «el rechazo del revisor no bloquea la promoción» debe morir. Si ya existe, nada que hacer (no verificado aquí).

## Licencia y precauciones
Sin licencia: no copiar. Contenido remoto = dato no confiable; no se ejecutó nada. Prioridad: **P2 (contraejemplo)**.
