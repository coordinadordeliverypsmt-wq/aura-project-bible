---
id: IE-036
titulo: ANative-Lab/EvoAgentX — framework de flujos multiagente con optimizadores de prompts y workflows (TextGrad, AFlow, MIPRO, EvoPrompt, SEW, MAP-Elites) y HITL
fuente: https://github.com/ANative-Lab/EvoAgentX
rama-revision: main (por defecto) @ f3d1ea5e46f3adf40ce252716440a154d81c91c6 (2026-10-22, último push)
fecha-revision: 2026-10-26
licencia: MIT (fichero `LICENSE`, «Copyright (c) 2025 EvoAgentX»); la API devuelve `NOASSERTION` porque el fichero añade una sección «Third-party Licenses» (AFlow de MetaGPT, MIT; LiveCodeBench, MIT)
area: asistentes (auto-mejora de agentes)
estado: descartado
cobertura: Inspección estática remota con `gh api` (metadatos, id del repositorio, commits, releases, license, issues abiertas, árbol de 567 ficheros) de LICENSE, pyproject.toml, evoagentx/hitl/approval_manager.py, evoagentx/tools/cmd_toolkit.py y evoagentx/optimizers/aflow_optimizer.py (cabecera y bucle). NO se leyeron los demás optimizadores, memory/, rag/, agents/, la interfaz web/GUI de HITL ni las pruebas (solo se contaron). Sin clonar, instalar ni ejecutar. No se leyeron los papers
relacionadas: [IE-034, IE-035, IE-037]
---

Base de las citas: `B = https://github.com/ANative-Lab/EvoAgentX/blob/f3d1ea5e46f3adf40ce252716440a154d81c91c6`.

Clasificación: **[CÓDIGO]** · **[README]/[PAPER]** · **[TESTS-DECLARADOS]** · **[TERCERO]** · **[INFER]** · **[HIPO]**.

## Qué se examinó (rutas y símbolos)

- **Propietario y procedencia:** `ANative-Lab/EvoAgentX`, organización, no bifurcado, creado el 2025-04-15.
  `repos/EvoAgentX/EvoAgentX` resuelve al **mismo id de repositorio (967062640)**: es un renombrado o transferencia
  de organización, no un duplicado. Propietario inequívoco **[CÓDIGO]** (API).
- **Mantenimiento:** 1.178 commits, 29 contribuidores, releases v0.1.2 a v0.1.4 (junio de 2026). Último commit el
  2026-10-22 («fix pytest error»); 32 issues abiertas, dos de seguridad recientes: #292 (el `allowed_imports` del
  `PythonInterpreterToolkit` se salta con `__import__()`/`open()`) y #287 (inyección SQL en
  `get_collection_info`) **[TERCERO]** (títulos, no reproducidas).
- **Dependencias** (`B/pyproject.toml`) **[CÓDIGO]**: base con `openai`, `litellm>=1.83.10`, `dashscope`, `networkx`,
  `pandas` y `tree_sitter`; extras con `llama-index`, `faiss-cpu`, `neo4j`, `sentence-transformers`, `transformers`,
  `ollama`, `selenium`, `docker`, `fastmcp`, `exa-py`, `pymongo` y `psycopg2-binary`. Módulos para Gmail, Google Maps,
  finanzas y criptomonedas en `evoagentx/tools/`.
- **Pruebas** **[TESTS-DECLARADOS]**: 54 rutas bajo `tests/`. Los commits recientes arreglan pruebas rotas.

## Patrones relevantes

- **HITL** `B/evoagentx/hitl/approval_manager.py#L42-L106` **[CÓDIGO]**: si el gestor está inactivo, `request_approval`
  devuelve `APPROVE` con `request_id="auto_approved"` (`#L57-L63`); si está activo y vence el plazo (1.800 s por
  defecto), devuelve `REJECT` (`#L95-L103`).
- **Ejecución de órdenes** `B/evoagentx/tools/cmd_toolkit.py` **[CÓDIGO]**: lista negra por expresiones regulares
  (`_is_dangerous_command`, `#L37-L114`), confirmación por `input()` (`#L116-L160`) y ejecución
  `[self.default_shell, "-c", command]` (`#L200-L211`; `default_shell` devuelve «bash» por defecto, L33/L35). Tiene un `permission_cache` declarado (`#L25`) cuyo uso no se verificó.
- **AFlow** `B/evoagentx/optimizers/aflow_optimizer.py#L56-L137` **[CÓDIGO]**: rondas persistidas en
  `round_N/graph.py`, reanudación desde `initial_round`, `validation_rounds` en validación, prueba de la mejor ronda
  con `test()`, y convergencia (`ConvergenceUtils`).
- **Benchmarks y «auto-evolución»** **[README]/[PAPER]**: no revisados ni reproducidos.

## Hallazgos

### HAL-036-1 · Aprobación humana que se auto-concede si el canal no está activo

- **Problema:** autorización determinista antes de los efectos.
- **Mecanismo:** con el HITL inactivo, la respuesta es `APPROVE` (`approval_manager.py#L57-L63`); con el HITL activo,
  el vencimiento del plazo es `REJECT` (`#L95-L103`). La misma operación falla abierta o cerrada según una bandera de
  configuración.
- **Evidencia primaria:** **[CÓDIGO]**.
- **Grado de verificación:** leído.
- **Componente de AURA:** lista roja con confirmación humana **siempre** (ADR-0003); `autoconstruccion.autoriza()`
  devuelve siempre `False` y «el silencio no habilita» (`review.py:400-404`).
- **Alternativa existente en AURA:** cubierto; en AURA la ausencia del canal humano no aprueba nada **[INFER]** de las
  líneas citadas.
- **Beneficio y costes:** sirve de contraejemplo.
- **Riesgos y condiciones de rechazo:** no se adopta nada.
- **Criterio de aceptación de una prueba futura:** una acción de lista roja con el canal de confirmación ausente o
  desactivado queda rechazada o pendiente, nunca ejecutada. Si esa prueba no existe hoy, añadirla; un mutante que
  cambie «ausente» por «aprobado» debe morir.
- **Autorización requerida:** ninguna para comprobar si existe la prueba; un Decision Package si hay que tocar código.
- **Clasificación:** **REFERENCIA**.

### HAL-036-2 · Shell arbitrario protegido por lista negra y `input()`

- **Problema:** ejecutar acciones con permisos.
- **Mecanismo:** `bash -c <orden libre>` tras unas expresiones regulares y una confirmación interactiva
  (`cmd_toolkit.py#L37-L211`). Se suman la issue #292 (salida del intérprete Python) **[TERCERO]** y la ausencia de
  motor único o registro de capacidades.
- **Evidencia primaria:** **[CÓDIGO]** + títulos de issues **[TERCERO]**.
- **Grado de verificación:** leído.
- **Componente de AURA:** regla «AURORA nunca ejecuta instrucciones arbitrarias del SO: solo CAPACIDADES registradas»
  (CEO, 2026-08-03); motor único (ALERTA-005).
- **Alternativa existente en AURA:** capacidades registradas y gobernadas por el motor único.
- **Beneficio y costes:** ninguno.
- **Riesgos y condiciones de rechazo:** contradice reglas no negociables.
- **Criterio de aceptación:** no aplica.
- **Autorización requerida:** no procede.
- **Clasificación:** **NO ADOPTAR**.

### HAL-036-3 · Optimización por rondas persistidas y reanudables

- **Problema:** recuperar tareas tras una interrupción y correlacionar intento y estado.
- **Mecanismo:** cada ronda materializa `round_N/` en disco y el optimizador acepta `initial_round` para continuar
  (`aflow_optimizer.py#L56-L89`); la selección final prueba la mejor ronda sobre el conjunto de prueba
  (`#L119-L137`).
- **Evidencia primaria:** **[CÓDIGO]**.
- **Grado de verificación:** leído; no se comprobó la atomicidad de la escritura de rondas ni qué pasa si la
  interrupción cae a mitad de una ronda **[HIPO]**.
- **Componente de AURA:** recuperación tras caídas (commit 9f13935, DP-RECUPERACION-TRAS-CAIDAS); diario de
  `autoconstruccion.py`.
- **Alternativa existente en AURA:** ya cubierto, y con escritura atómica y `fsync` (`autoconstruccion.py:667-697`).
- **Beneficio y costes:** ninguno añadido.
- **Riesgos y condiciones de rechazo:** no aplica.
- **Criterio de aceptación:** no aplica.
- **Autorización requerida:** ninguna.
- **Clasificación:** **REFERENCIA** (ya cubierto).

## Límites, riesgos y dependencias

- Árbol de dependencias muy amplio, con proveedores en la nube (OpenAI, DashScope, Exa, OpenRouter) y bases de datos
  externas: choca con D24/ADR-0001.
- Dos issues de seguridad abiertas en octubre de 2026 (#292, #287) **[TERCERO]**.
- Alcance funcional enorme (correo, mapas, finanzas, navegador): «prohibido crear componentes si existe equivalente»
  y D23 impiden incorporarlo.

## Comparación con AURA

| AURA | Relación |
|---|---|
| ADR-0003 / `review.py:400-404` | EvoAgentX auto-aprueba con el HITL inactivo (HAL-036-1) |
| Motor único + capacidades registradas | EvoAgentX ejecuta shell libre (HAL-036-2) |
| Recuperación tras caídas | Equivalente de rondas reanudables; AURA ya lo cubre (HAL-036-3) |
| Optimizadores de prompts (TextGrad, MIPRO, EvoPrompt) | Sin problema real de AURA que los pida hoy; no se fuerza la correspondencia |

## Decisión

**DESCARTAR** como dependencia o código. Solo **REFERENCIA**: el contraejemplo de HITL que falla abierta (HAL-036-1).

## Validación mínima

Localizar o escribir la prueba de HAL-036-1 (lista roja sin canal humano → nunca ejecuta) y su mutante.

## Licencia y precauciones

MIT con avisos de terceros (AFlow y LiveCodeBench, MIT). **No se copia nada.** No se clonó, instaló ni ejecutó nada.
