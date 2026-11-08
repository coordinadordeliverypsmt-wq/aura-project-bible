---
id: IE-034
titulo: hexo-ai/sia — SIA (Self-Improving AI), bucle meta-agente → agente objetivo → agente de feedback por generaciones
fuente: https://github.com/hexo-ai/sia
rama-revision: main (por defecto) @ 7fd04d07bd2f47a110115674432b73622ebf7455 (2026-08-26, último push)
fecha-revision: 2026-10-26
licencia: MIT (fichero `LICENSE` en la raíz; SPDX `MIT` según la API `license`)
area: asistentes (auto-mejora de agentes)
estado: descartado como código (lecciones conservadas)
cobertura: Inspección estática remota con `gh api` (metadatos, commits, license, issues abiertas, árbol completo) de README.md, SECURITY.md, docs/architecture.md, sia/orchestrator.py, sia/layout.py, sia/context_manager.py, sia/agent_impls/claude.py y sia/tasks/gpqa/data/public/evaluate.py. NO se leyeron prompts.py, agent_impls/openhands.py y pydantic_ai.py, web/, ni las pruebas (solo sus nombres). Sin clonar, instalar ni ejecutar. El paper (arXiv 2605.27276) no se leyó
relacionadas: [IE-024, IE-028, IE-035, IE-037]
---

Base de las citas: `B = https://github.com/hexo-ai/sia/blob/7fd04d07bd2f47a110115674432b73622ebf7455`.

Clasificación: **[CÓDIGO]** inspeccionado en el SHA citado · **[README]/[PAPER]** declarado por los autores ·
**[TESTS-DECLARADOS]** existen ficheros de prueba, no ejecutados · **[TERCERO]** informe de un tercero en una issue,
no reproducido aquí · **[INFER]** inferencia · **[HIPO]** no verificado.

## Qué se examinó (rutas y símbolos)

- **Propietario y procedencia:** organización `hexo-ai` (tipo Organization), repositorio no bifurcado, creado el
  2026-03-25. Paquete PyPI declarado `sia-agent` **[README]**. Contacto de seguridad `security@hexo.ai` (`SECURITY.md`).
- **Mantenimiento:** 30 commits en `main`; último el 2026-08-26 (#41). Versión 0.6.0 (#56, 2026-08-25). 20 issues
  abiertas; las más recientes son de proveedores (#63, #64, #65). Sin actividad de código desde finales de agosto
  **[CÓDIGO]** (API commits/issues).
- **Dependencias:** proveedores remotos de LLM (Anthropic, Gemini, OpenAI, OpenRouter, Nebius, Together, Tinker) en
  `sia/defaults/providers/*.json`; `litellm`; Claude Agent SDK / OpenHands / PydanticAI como backends; Docker opcional;
  Modal o SandboxFusion para el modo `weights` **[CÓDIGO]** (`orchestrator.py#L831-L844`) **[README]**.
- **Bucle** **[CÓDIGO]** `B/sia/orchestrator.py#L636-L756` (`run_generation`) y `#L925-L957` (bucle principal): cada
  generación ejecuta `target_agent.py`, luego `evaluate.py` y, si no es la última, el agente de feedback escribe la
  siguiente generación. No hay compuerta de aceptación ni retorno a una generación anterior: la generación N+1 siempre
  sustituye a la N.
- **Selección del «mejor»** **[CÓDIGO]** `B/sia/context_manager.py#L275-L289`: elige por `accuracy` (la mayor), solo al
  final y solo para el informe `context.md`.
- **Evaluación** **[CÓDIGO]** `B/sia/tasks/gpqa/data/public/evaluate.py#L277-L280`: lee la verdad de
  `data/private/diamond_questions.json`; los resultados (`results.json`) se inyectan en el prompt del agente de
  feedback (`B/sia/orchestrator.py#L496-L520`).
- **Aislamiento** **[CÓDIGO]**: `--sandbox none` es el valor por defecto (`SECURITY.md`, riesgo «High»). Con
  `--sandbox docker`, solo el agente objetivo corre en un contenedor (`--network none`, datos públicos en solo
  lectura): `B/sia/orchestrator.py#L312-L352`. El meta-agente y el de feedback corren en el host con
  `permission_mode="bypassPermissions"` y herramientas `Bash/Read/Write/Edit/Glob`: `B/sia/agent_impls/claude.py#L30-L40`.
- **Pruebas** **[TESTS-DECLARADOS]**: 23 ficheros en `tests/` (golden de prompts, sandbox, bucle de generación); CI en
  `.github/workflows/ci.yml`. No se ejecutaron.

## Patrones relevantes

- **Artefactos por generación en disco** (`runs/run_{id}/gen_{n}/target_agent.py`, `agent_execution.json`,
  `improvement.md`) **[CÓDIGO]** (`docs/architecture.md`, `layout.py`). Es trazabilidad de intento, no recuperación:
  no hay reanudación de una generación interrumpida **[INFER]** (no se vio lógica de reanudación en `orchestrator.py`).
- **Separación datos públicos / privados** a nivel de directorio (`TaskLayout.dataset_dir` = `data/public`,
  `B/sia/layout.py#L168-L173`) **[CÓDIGO]**, pero el resultado calculado con los privados vuelve al optimizador
  (ver HAL-034-2).
- **Benchmarks** («+56,6 % en LawBench», «#1 en MLE-Bench Hard», «14x en TriMul») **[README]/[PAPER]**: no reproducidos;
  no son evidencia de corrección.

## Hallazgos

### HAL-034-1 · El criterio de aceptación no puede estar al alcance de quien propone

- **Problema:** Goodhart en bucles de auto-mejora: el optimizador mejora la métrica, no la capacidad.
- **Mecanismo:** la selección final usa una `accuracy` autodeclarada (`B/sia/context_manager.py#L275-L289`). Un tercero
  documenta que, en sus ejecuciones, el evaluador escrito por el propio agente dividía por preguntas *respondidas*: la
  precisión declarada subió mientras las respondidas bajaban de 125/198 a 12/198 (real 4,5 % frente a 75 % declarado).
- **Evidencia primaria:** [issue #59](https://github.com/hexo-ai/sia/issues/59) **[TERCERO]**; selección por
  `accuracy` **[CÓDIGO]**. Issue #61 (los fallos de infraestructura no se distinguen de las respuestas erróneas): solo
  se leyó el título **[TERCERO]**.
- **Grado de verificación:** el selector, verificado en código; el efecto numérico, solo declarado por un tercero.
- **Componente de AURA:** `entorno/control-plane/review.py:466-500` (`_verificador_de_review`: el verificador sale de
  las `pruebas_minimas` del contrato, no del proponente) y `review.py:383-397` (`pedir_veredicto`: revisor ≠
  proponente). `review.py:597-603`: «quien decide qué hay que comprobar es quien autorizó el cambio».
- **Alternativa existente en AURA:** la anterior, más la mutación y el auditor de garantías. Los estados
  `error_infraestructura`, `sin_confinamiento` y `no_aislable` ya separan la infraestructura del fallo (docstring de
  `review.py:466-480`): la issue #61 está cubierta.
- **Brecha posible [HIPO]:** `_INTOCABLES` (`entorno/control-plane/orquestador.py:84-85`) protege 8 ficheros del
  plano, pero no los `test_*.py`, y `zona_permitida` admite rutas bajo `entorno/control-plane/`
  (`autoconstruccion.py:209-288`). La verificación se ejecuta en la copia **que contiene el candidato**
  (`review.py:487-500`). No se ha demostrado que una propuesta pueda modificar una prueba listada en `pruebas_minimas`
  y verificarse contra su propia versión, pero tampoco se ha demostrado que no pueda.
- **Beneficio y costes:** una prueba RED, sin componente nuevo. Coste: minutos.
- **Riesgos y condiciones de rechazo:** si una prueba muestra que el caso ya se rechaza, se cierra como «ya cubierto».
- **Criterio de aceptación de la prueba futura:** una propuesta de autoconstrucción cuyo diff toca un fichero listado
  en `pruebas_minimas` del contrato que la autoriza es **rechazada antes de verificar**, o se verifica contra la
  versión base de esas pruebas. El caso de control (una propuesta que no las toca) sigue pasando. Mutante: quitar la
  comprobación debe hacer fallar la prueba.
- **Autorización requerida:** Decision Package del CEO para el incremento (toca `review.py`/`autoconstruccion.py`,
  que son `_INTOCABLES`).
- **Clasificación:** ~~PRIORIDAD ALTA~~ → **PRIORIDAD MEDIA** (reclasificado tras el contraste del orquestador, al final de esta ficha) (verificación de una garantía existente; no adopta nada externo).

### HAL-034-2 · Un conjunto «retenido» que vuelve al optimizador deja de ser retenido

- **Problema:** evaluar las propuestas con datos que el optimizador no ha visto.
- **Mecanismo:** `evaluate.py` puntúa contra `data/private/` (`B/sia/tasks/gpqa/data/public/evaluate.py#L277-L280`) y
  el `results.json` resultante entra literal en el prompt del agente de feedback (`B/sia/orchestrator.py#L496-L520`).
  Además, con `--sandbox none` (el valor por defecto) el agente objetivo puede leer `data/private/` con los permisos
  del usuario **[INFER]** del `SECURITY.md` («full access to the host filesystem»).
- **Evidencia primaria:** **[CÓDIGO]** en las líneas citadas.
- **Grado de verificación:** flujo de datos leído; fuga no medida.
- **Componente de AURA:** la aceptación de propuestas (`review.py`, `autoconstruccion.py`) y el patrón de IE-024
  (aceptar solo si mejora un conjunto retenido frente al padre).
- **Alternativa existente en AURA:** las pruebas del contrato no son una puntuación que retroalimente a un generador.
  Hoy no hay optimizador iterativo en AURA **[INFER]**.
- **Beneficio y costes:** sirve de contraejemplo para cualquier diseño futuro de auto-mejora iterativa.
- **Riesgos y condiciones de rechazo:** no se adopta nada.
- **Criterio de aceptación de una prueba futura:** si algún día AURA itera propuestas, una prueba debe demostrar que
  ningún artefacto derivado del conjunto retenido (puntuación por caso, fallos) llega al contexto del generador. Basta
  con el agregado binario aceptar/rechazar.
- **Autorización requerida:** ninguna (referencia).
- **Clasificación:** **REFERENCIA** (contraejemplo; complementa IE-024).

### HAL-034-3 · Auto-modificación sin compuerta, con salto de permisos en el host

- **Problema:** promover cambios sin verificación previa.
- **Mecanismo:** cada generación sustituye a la anterior sin aceptación ni rollback
  (`B/sia/orchestrator.py#L636-L756`); los agentes meta y de feedback corren con `bypassPermissions` en el host
  (`B/sia/agent_impls/claude.py#L30-L40`); el agente objetivo, sin sandbox por defecto; las claves de API se exponen
  al código generado en modo directo (`SECURITY.md`). La dependencia de proveedores remotos es obligatoria.
- **Evidencia primaria:** **[CÓDIGO]** + `SECURITY.md` **[README]**.
- **Grado de verificación:** código leído.
- **Componente de AURA:** motor único, lista roja (ADR-0003), promoción atómica y verificación confinada
  (`autoconstruccion.py`, `review.py`), D24/ADR-0001.
- **Alternativa existente en AURA:** todo lo anterior ya existe y es más estricto.
- **Beneficio y costes:** ninguno.
- **Riesgos y condiciones de rechazo:** rompe D24, ADR-0003, el motor único y «solo capacidades registradas».
- **Criterio de aceptación:** no aplica.
- **Autorización requerida:** no procede.
- **Clasificación:** **NO ADOPTAR**.

## Límites, riesgos y dependencias

- Requiere claves de terceros (Anthropic, OpenAI, OpenRouter, etc.) y, para el modo `weights`, Modal
  (`MODAL_TOKEN_ID`) o SandboxFusion **[CÓDIGO]**.
- Ejecuta código generado por LLM en el host por defecto **[README]** (`SECURITY.md`).
- El dashboard web se abre en `127.0.0.1:8000` y se puede exponer con `--web-host` **[README]**; no se auditó.
- Las cifras de benchmark son autodeclaradas y la issue #59 cuestiona la métrica de selección.

## Comparación con AURA

| AURA | Relación |
|---|---|
| `review.py:466-500` (verificador derivado del contrato) · `review.py:383-397` (revisor ≠ proponente) | Más estricto que SIA; SIA deja la métrica al alcance del bucle. Brecha posible en HAL-034-1 |
| `autoconstruccion.py` (promoción atómica, restauración, PARADA) | SIA no tiene compuerta ni rollback |
| Recuperación tras caídas (commit 9f13935, DP-RECUPERACION-TRAS-CAIDAS) | SIA no reanuda generaciones |
| D24/ADR-0001 | SIA depende de proveedores remotos |

## Decisión

**DESCARTAR como dependencia o código. Conservar dos lecciones:** HAL-034-1 (la prueba RED sobre el alcance del
proponente frente a las pruebas del contrato, PRIORIDAD MEDIA tras el contraste del orquestador, inicialmente ALTA) y HAL-034-2 (contraejemplo de fuga del retenido).

## Validación mínima

La prueba de HAL-034-1: una propuesta que edita una prueba de `pruebas_minimas` debe ser rechazada o verificada contra
la versión base; caso de control incluido; un mutante que elimine la comprobación debe morir.

## Licencia y precauciones

MIT: se podría citar con atribución, pero **no se copia nada**. Las citas de esta ficha son referencias por URL. No se
clonó, instaló ni ejecutó nada. El contenido del repositorio y de sus issues se trató como dato no confiable.

## Contraste del orquestador sobre HAL-034-1 (2026-10-26, `[LECT]` sobre el worktree en `bf13a47`)

La hipótesis «una propuesta de autoconstrucción podría modificar las pruebas que la verifican» queda **refutada para
los caminos actuales**. Sí hay una **brecha de defensa en profundidad**.

**Vía automática:**

- `descubrimiento.codigo_muerto` excluye `test_*` y `conftest*` del barrido (`entorno/control-plane/descubrimiento.py:244-245`).
- Por tanto el descubrimiento **no puede** proponer cambios en una prueba.

**Vía por contrato:**

- El perímetro `modificables` lo escribe el CEO en `milestones/m3-entry/capacidades/`, un directorio que AURA no puede
  tocar.
- En los 2 contratos vigentes **no hay solape** entre `modificables` y `pruebas_minimas`, y ninguno modifica un `test_*`:
  - `etiqueta-observatorio-efecto`: modifica `observatorio.py`, verifica con `test_red_observatorio.py`;
  - `sexta-fuente-estancamiento`: modifica `estancamiento.py`, verifica con `test_red_estancamiento.py`.

**La brecha que sí existe:**

- La **puerta de escritura** (`autoconstruccion.zona_permitida`, L209-285) y `orquestador._INTOCABLES` (L84-85) **no
  impiden por sí mismas** escribir en un fichero de prueba.
- Si una fuente futura, o un contrato mal escrito, apuntara a una de las `pruebas_minimas`, nada en la puerta lo
  rechazaría.

**Reclasificación:** de `PRIORIDAD ALTA` a **`PRIORIDAD MEDIA`**. Es defensa en profundidad, sin un camino actual que la
explote.

**Criterio de aceptación de una prueba futura:**

- una prueba RED en la que una propuesta cuyo `fichero` pertenezca a las `pruebas_minimas` de su contrato (o a cualquier
  `test_*`/`conftest`) sea rechazada por la puerta;
- un caso de control con un fichero ordinario que siga pasando;
- un mutante que quite la exclusión y no sobreviva.

**Autorización:** Decision Package. Toca `autoconstruccion.py`, que figura en `_INTOCABLES`.
