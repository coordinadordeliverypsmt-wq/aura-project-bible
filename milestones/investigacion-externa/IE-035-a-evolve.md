---
id: IE-035
titulo: A-EVO-Lab/a-evolve — infraestructura de «evolución agéntica» (workspace en ficheros + motores de evolución intercambiables + git como versionado)
fuente: https://github.com/A-EVO-Lab/a-evolve
rama-revision: main (por defecto) @ 18ba996dac9843f2759b2cdf8a94022f58fbfeb9 (2026-08-21; último push 2026-08-22)
fecha-revision: 2026-10-26
licencia: SIN fichero LICENSE en el árbol (API `license` → 404). `pyproject.toml` declara `license = "MIT"` y el README muestra una insignia MIT. Concesión no formalizada en un fichero de licencia
area: asistentes (auto-mejora de agentes)
estado: descartado
cobertura: Inspección estática remota con `gh api` (metadatos, commits, license, issues, árbol completo de 418 ficheros de texto) de README.md (afirmaciones), DESIGN.md, pyproject.toml, agent_evolve/engine/{loop,versioning,trial,history,human_interface}.py, agent_evolve/contract/workspace.py y agent_evolve/algorithms/adaptive_skill/{gating,engine}.py, más la issue #28. NO se leyeron los motores meta_harness, navigation, guided_synth y propose_curate, los agentes por benchmark, protocol/base_agent.py (citado solo a través de la issue #28) ni el paper (arXiv 2602.00359). Sin clonar, instalar ni ejecutar
relacionadas: [IE-024, IE-028, IE-034, IE-036, IE-037]
---

Base de las citas: `B = https://github.com/A-EVO-Lab/a-evolve/blob/18ba996dac9843f2759b2cdf8a94022f58fbfeb9`.

Clasificación: **[CÓDIGO]** inspeccionado en el SHA citado · **[README]/[PAPER]** declarado · **[TERCERO]** informe de
un tercero, no reproducido aquí · **[INFER]** · **[HIPO]**.

## Qué se examinó (rutas y símbolos)

- **Propietario y procedencia:** organización `A-EVO-Lab`, repositorio original (no bifurcado), creado el 2026-02-20.
  Es el repositorio «oficial» del paper *Position: Agentic Evolution is the Path to Evolving LLMs* (descripción del
  repositorio) **[README]**. 7 contribuidores; los últimos commits son casi todos de un único autor.
- **Mantenimiento:** 80 commits; el último toca el README (2026-08-21) y el anterior con código es
  «Publish A-Evolve-Training» (2026-06-29). 6 issues abiertas, entre ellas la #28 (seguridad, abierta desde el
  2026-08-03 y sin respuesta en la API) **[CÓDIGO]** (API). Sin releases.
- **Dependencias:** la base solo pide `matplotlib` y `pyyaml`; los extras traen `anthropic`, `openai`, `boto3`
  (Bedrock), `litellm`, `strands-agents`, `swebench`, `mcp` y `gepa` (`B/pyproject.toml`) **[CÓDIGO]**. La interfaz
  humana opcional usa Telegram y Slack (`B/agent_evolve/engine/human_interface.py#L52-L183`) **[CÓDIGO]**.
- **Bucle** `B/agent_evolve/engine/loop.py#L68-L183` **[CÓDIGO]**: Solve → Observe → snapshot `pre-evo-N` →
  `engine.step()` → snapshot `evo-N` → recarga desde el sistema de ficheros → convergencia por ventana de puntuación
  (`#L33-L41`).
- **Contrato de workspace** `B/agent_evolve/contract/workspace.py#L15-L196` **[CÓDIGO]**: `prompts/system.md`,
  `skills/*/SKILL.md`, borradores (`drafts`), `tools/registry.yaml`, `memory/*.jsonl` (episódica) y `evolution/`
  (historial y métricas).
- **Versionado** `B/agent_evolve/engine/versioning.py#L62-L125` **[CÓDIGO]**: commit con `tag -f` por ciclo; `rollback`
  restaura como **commit nuevo** y conserva el rechazado en el historial. `DESIGN.md#L279` dice en cambio
  «Bad mutation? `git reset --hard`»: el documento no coincide con el código.
- **Afirmaciones de benchmark** («#1», «SOTA Agent», «3 lines of code», «zero human intervention») **[README]**: no
  reproducidas.

## Patrones relevantes

- **Correlación tarea↔intento por etiquetas**: cada ciclo deja `pre-evo-N` y `evo-N` (con `score=` en el mensaje) y una
  línea en `evolution/history.jsonl` (`loop.py#L110-L134` y `#L187-L198`) **[CÓDIGO]**.
- **Rollback no destructivo**: `checkout <ref> -- .`, borrado de los ficheros añadidos después y commit
  «rollback to <ref>» (`versioning.py#L89-L121`) **[CÓDIGO]**.
- **Separación algoritmo / agente / evaluación** a través del workspace (`DESIGN.md`, «Separation of Concerns»)
  **[README]**.

## Hallazgos

### HAL-035-1 · Rollback como commit nuevo que conserva el candidato rechazado

- **Problema:** prevenir regresiones sin perder la evidencia del intento fallido.
- **Mecanismo:** `VersionControl.rollback` restaura el contenido de la referencia, borra los ficheros que no existían
  en ella y confirma un commit nuevo; el rechazado sigue accesible por su etiqueta (`versioning.py#L89-L121`).
- **Evidencia primaria:** **[CÓDIGO]**.
- **Grado de verificación:** leído; no ejecutado.
- **Componente de AURA:** `entorno/control-plane/autoconstruccion.py` (diario, `_escribir_atomico` en L675, restauración
  con `RestauracionFallida` en L142, `_BaseCambiada` en L648) y la recuperación tras caídas (commit 9f13935).
- **Alternativa existente en AURA:** la promoción atómica con diario y la verificación en copia ya cubren el retorno al
  estado anterior. AURA no versiona su propio plano con git automático (y no debe: «no commit / no push» en
  `RESTRICCIONES_PERMANENTES`, `orquestador.py:89-92`).
- **Beneficio y costes:** como idea, conservar el candidato rechazado (diff y veredicto) como evidencia en el diario
  del intento; AURA podría hacerlo ya con `eventos.jsonl` **[INFER]**. Adoptar git automático costaría romper una
  restricción permanente.
- **Riesgos y condiciones de rechazo:** se rechaza todo lo que implique commits automáticos.
- **Criterio de aceptación de una prueba futura:** si se decide, tras un rechazo, el diario o el evento conserva el
  diff del candidato y el motivo, y el árbol vivo queda byte a byte igual que antes.
- **Autorización requerida:** ninguna para registrarlo como referencia; un Decision Package si se cambiara el formato
  del diario.
- **Clasificación:** **REFERENCIA**.

### HAL-035-2 · Compuerta que falla abierta: sin retenido, acepta; umbral por defecto 0,0

- **Problema:** evaluar las propuestas antes de promoverlas.
- **Mecanismo:** `GatingStrategy.validate` devuelve `True` si no hay tareas retenidas («No holdout tasks available,
  accepting mutation») y su `min_score_threshold` vale 0.0 por defecto, así que una media ≥ 0 siempre acepta
  (`B/agent_evolve/algorithms/adaptive_skill/gating.py#L19-L49`). En el bucle genérico,
  `engine.on_cycle_end(accepted=step_result.mutated, …)` equipara «mutado» con «aceptado» (`loop.py#L150`).
  `adaptive_skill/engine.py` no llama a `GatingStrategy` (búsqueda de «gat», «validate» y «rollback» sin resultados).
  No se verificó si la llaman otros motores.
- **Evidencia primaria:** **[CÓDIGO]**.
- **Grado de verificación:** leído.
- **Componente de AURA:** `review.py:466-500`: si falta cualquier control de confinamiento, no se ejecuta nada y el
  estado es `sin_confinamiento` (rechazo); `review.py:400-404`: «el silencio tampoco habilita».
- **Alternativa existente en AURA:** AURA ya falla cerrada en este punto.
- **Beneficio y costes:** sirve de contraejemplo para documentar la regla y como caso para una mutación existente.
- **Riesgos y condiciones de rechazo:** no se adopta nada.
- **Criterio de aceptación de una prueba futura:** ya debería existir. Comprobar que un mutante que convierta
  «sin evidencia» en «aceptar» en `review.py` o `autoconstruccion.py` muere con la batería actual. Si sobrevive, el
  hallazgo sube a PRIORIDAD ALTA.
- **Autorización requerida:** ninguna para lanzar la comprobación de mutación (sin ejecutar nada en paralelo, según
  `CLAUDE.md` §2).
- **Clasificación:** **REFERENCIA** (contraejemplo; el auditor de garantías puede usarlo).

### HAL-035-3 · Candidato escrito por el proponente, cargado con `exec_module` en el mismo proceso tras una compuerta que solo compila

- **Problema:** verificar el candidato sin que su código se ejecute con la autoridad del orquestador.
- **Mecanismo:** según la issue, `BaseAgent` carga `harness.py` del workspace con `spec.loader.exec_module` (lo que
  ejecuta el código de nivel de módulo en el proceso de a-evolve); la compuerta `_validate_candidate` solo llama a
  `compile()`; y el proponente es el CLI de Claude Code lanzado con `--dangerously-skip-permissions` y
  `cwd=workspace.root`.
- **Evidencia primaria:** [issue #28](https://github.com/A-EVO-Lab/a-evolve/issues/28) **[TERCERO]**, con prueba de
  concepto fijada a `c9d4789`. No se reprodujo, ni se leyeron `protocol/base_agent.py` ni `meta_harness/engine.py`.
- **Grado de verificación:** declarado por un tercero con líneas concretas; no contrastado con el código.
- **Componente de AURA:** `review.py:466-500` (verificación confinada con Landlock y seccomp en una copia, también para
  los procesos hijos) y `autoconstruccion.py` (`CandidatoNoAislable`, L147).
- **Alternativa existente en AURA:** cubierto: AURA nunca importa el candidato en el proceso del plano **[INFER]** de
  `review.py:466-500`.
- **Beneficio y costes:** ninguno que adoptar; confirma una decisión de diseño de AURA.
- **Riesgos y condiciones de rechazo:** es un patrón explícitamente prohibido en AURA.
- **Criterio de aceptación:** no aplica.
- **Autorización requerida:** no procede.
- **Clasificación:** **NO ADOPTAR**.

### HAL-035-4 · Workspace del agente como contrato de ficheros (prompts, skills, borradores, memoria episódica JSONL)

- **Problema:** memoria de experiencias y artefactos evolucionables con un formato estable.
- **Mecanismo:** `AgentWorkspace` con lectura y escritura por tipo y `add_memory(entry, category="episodic")` en JSONL
  (`workspace.py#L132-L162`); los borradores (`write_draft`, `clear_drafts`, `#L90-L106`) separan lo propuesto de lo
  instalado.
- **Evidencia primaria:** **[CÓDIGO]**.
- **Grado de verificación:** leído; no se midió su utilidad.
- **Componente de AURA:** `PLAN-DE-FORMACION-AURORA.md` (capacidades en observación), `eventos.jsonl` del plano.
- **Alternativa existente en AURA:** registro de eventos y plan de formación. No hay evidencia de uso real que pida un
  almacén de «skills» evolucionables **[INFER]**.
- **Beneficio y costes:** bajo hoy. Crear un componente así exigiría demostrar que no existe un equivalente (regla
  del CEO del 2026-08-03).
- **Riesgos y condiciones de rechazo:** se rechaza si no hay bloqueos repetidos observados.
- **Criterio de aceptación de una prueba futura:** solo con evidencia de uso real; tendría que demostrar que separar
  borrador e instalado reduce las promociones fallidas medidas.
- **Autorización requerida:** Decision Package del CEO.
- **Clasificación:** **REFERENCIA**.

## Límites, riesgos y dependencias

- Proveedores remotos (Bedrock, Anthropic, OpenAI y LiteLLM) y canales Telegram y Slack: chocan con D24/ADR-0001.
- Lema «zero human intervention» **[README]**, opuesto a ADR-0003 (lista roja con confirmación humana).
- Sin fichero de licencia: la declaración MIT de `pyproject.toml` no es un texto de licencia en el repositorio.
- Issue de seguridad #28 abierta y sin respuesta.
- Discrepancia documento/código sobre el rollback (`DESIGN.md#L279` frente a `versioning.py#L89-L121`).

## Comparación con AURA

| AURA | Relación |
|---|---|
| `autoconstruccion.py` (promoción atómica, diario, restauración) | Equivalente más estricto; a-evolve versiona con git automático (prohibido en AURA) |
| `review.py:466-500` (verificación confinada, falla cerrada) | a-evolve falla abierta (HAL-035-2) y ejecuta el candidato en su proceso según la issue #28 (HAL-035-3) |
| `eventos.jsonl` / recuperación tras caídas | Las etiquetas por ciclo correlacionan intento y estado; AURA ya registra eventos por tarea |

## Decisión

**DESCARTAR como dependencia o código** (sin fichero de licencia, nube, «zero human intervention», compuerta
abierta). Se conservan como **REFERENCIA** el rollback que preserva el rechazado (HAL-035-1) y el contraejemplo de la
compuerta que falla abierta (HAL-035-2), útil para comprobar mutantes de AURA.

## Validación mínima

HAL-035-2: lanzar `herramientas.mutar` con un mutante que convierta «sin evidencia de verificación» en aceptación en
el camino de `review.py`/`autoconstruccion.py`; debe morir. Ninguna otra validación hasta que haya evidencia de uso.

## Licencia y precauciones

**No hay fichero de licencia; no se copia nada.** Solo ideas y referencias por URL. No se clonó, instaló ni ejecutó
nada. La prueba de concepto de la issue #28 **no** se ejecutó.
