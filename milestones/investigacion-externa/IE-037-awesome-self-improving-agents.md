---
id: IE-037
titulo: selfimproving-agent/Awesome-Self-Improving-Agents — lista curada y fuentes LaTeX de la revisión «Self-Improvements in Modern Agentic Systems: A Survey»
fuente: https://github.com/selfimproving-agent/Awesome-Self-Improving-Agents
rama-revision: main (por defecto) @ d89d1adec7ef20553ca137a9eecee8d624ecd8c4 (2026-10-26, último push)
fecha-revision: 2026-10-26
licencia: MIT (fichero `LICENSE`; SPDX `MIT` según la API). La licencia cubre la lista; cada trabajo enlazado tiene la suya
area: asistentes (auto-mejora de agentes) — fuente bibliográfica
estado: referencia
cobertura: Lectura remota con `gh api` de metadatos, commits, license, issues abiertas, árbol, README.md (secciones 2.2 Memoria, 2.4 Full Scaffolding, Evaluación y benchmarks de Ingeniería de Software) y las primeras líneas de README_AGENT.md. NO se leyeron las secciones 1.x (modelo fundacional), 2.1 (prompts) y 2.3 (herramientas) más allá de su índice, ni `Paper/`. **Ninguna entrada enlazada se verificó**: se extraen solo como pistas, con su enlace tal como figura en la lista
relacionadas: [IE-024, IE-025, IE-034, IE-035, IE-036]
---

Base de las citas: `B = https://github.com/selfimproving-agent/Awesome-Self-Improving-Agents/blob/d89d1adec7ef20553ca137a9eecee8d624ecd8c4`.

Clasificación: **[CÓDIGO]** observado en la lista (contenido del fichero) · **[README]** declarado por los
mantenedores · **[INFER]** · **[HIPO]**. Para cada entrada de la lista, título y año son **[README]**; nada de lo que
afirman los trabajos enlazados se ha verificado aquí.

## Qué se examinó (rutas y símbolos)

- **Propietario y procedencia:** organización `selfimproving-agent`. El nombre canónico es
  `Awesome-Self-Improving-Agents` (la URL en minúsculas redirige). No bifurcado, creado el 2025-12-28. Acompaña a la
  revisión arXiv 2607.13104 (`B/README.md#L99-L101`) **[README]**.
- **Mantenimiento:** 200 commits y 23 contribuidores; último merge el 2026-10-26 (#33, EvoRepair). Muy activo. Las
  aportaciones entran por PR y algunas las ha redactado un agente («Cursor Agent», commit 2d422a2) **[CÓDIGO]** (API).
  5 issues abiertas, todas peticiones de alta.
- **Estructura:** taxonomía (modelo fundacional frente a scaffolding: prompts, memoria, herramientas, scaffolding
  completo) y evaluación (métricas, jueces, benchmarks por mecanismo y por dominio) (`B/README.md#L111-L770`).
- **`README_AGENT.md`** está escrito como guía para asistentes de IA. Se trató como dato: no se siguió ninguna de sus
  indicaciones.
- **Calidad de los enlaces** **[CÓDIGO]**: hay errores verificables en el propio fichero.
  - L403 (Dynamic Cheatsheet) enlaza `arXiv 2305.00833`, el mismo identificador que la L395 (Self-Notes).
  - L581 (Gödel Agent) enlaza `arXiv 2410.04444`, el mismo que la L576 (STOP).
  - L456 (SEDM) enlaza `arXiv 2309.08532` y el código `beeevita/EvoPrompt`, que corresponden a otro trabajo **[INFER]**.
  - L405 tiene `[paper]()` y `[code]()` vacíos.

  **La lista no sirve como fuente primaria: hay que verificar cada enlace antes de citarlo.**

## Entradas pertinentes para AURA (extraídas, sin verificar)

| Problema de AURA | Entrada (línea del README) | Enlaces |
|---|---|---|
| Memoria de experiencias de ingeniería | ExpeL, AAAI 2024 (L396) | https://arxiv.org/abs/2308.10144 · https://github.com/LeapLabTHU/ExpeL |
| Ídem | Agent Workflow Memory, ICML 2025 (L400) | https://arxiv.org/abs/2409.07429 · https://github.com/zorazrw/agent-workflow-memory |
| Ídem — **resultado negativo** | From Knowledge to Noise: CTIM-Rover and the Pitfalls of Episodic Memory in SE Agents, 2025 (L436) | https://arxiv.org/abs/2505.23422v1 · https://github.com/Liqs-v2/ctim-rover |
| Ídem (reparación) | Learning from Repair Experience, ICSE 2026 (L480) | https://arxiv.org/abs/2605.30105 · https://github.com/iSEngLab/Learn-from-Repair-Experience |
| Evaluación antes de promover | Recursive Self-Evolving Agents via Held-Out Selection, 2026 (L593) | https://arxiv.org/abs/2606.28374 |
| Ídem (el evaluador como objetivo) | The Red Queen Gödel Machine: Co-Evolving Agents and Their Evaluators, 2026 (L596) | https://arxiv.org/abs/2606.26294 |
| Promoción gobernada | AgentDevel: Reframing Self-Evolving LLM Agents as Release Engineering, 2026 (L585) | https://arxiv.org/abs/2601.04620 |
| Ídem | Ouroboros: A Self-Developing Frontier Coding Agent with **Reviewed Core Evolution**, 2026 (L599) | https://arxiv.org/abs/2608.08311 · https://github.com/razzant/ouroboros (**no** es el `Lycorecoil/ouroboros` de IE-025) |
| Auto-mejora de agentes de código | Darwin Gödel Machine, 2025 (L579) · Live-SWE-agent, 2025 (L584) | https://arxiv.org/abs/2505.22954 · https://arxiv.org/abs/2511.13646 |
| Riesgo de memoria persistente | DrunkAgent: Stealthy Memory Corruption in LLM-Powered Recommender Agents, WWW 2026 (L658) | https://arxiv.org/abs/2503.23804 |
| Autorización antes de efectos / riesgo | Identifying the Risks of LM Agents with an LM-Emulated Sandbox (ToolEmu), ICLR 2024 (L687) | https://openreview.net/forum?id=GEcwtMk1uA · https://github.com/ryoungj/ToolEmu |
| Ídem | EvoSafeHarness, 2026 (L604) | https://arxiv.org/abs/2609.05903 · https://github.com/SaFo-Lab/EvoSafeHarness |
| Prevención de regresiones (pruebas) | SWT-Bench, NeurIPS 2024 (L713) · TDD-Bench Verified, 2024 (L714) | https://openreview.net/forum?id=9Y8zUO11EQ · https://arxiv.org/abs/2412.02883 |
| Juez independiente | Agent-as-a-Judge, ICML 2025 (L669) | https://arxiv.org/abs/2410.10934 · https://github.com/metauto-ai/agent-as-a-judge |
| Agente personal | PAST-Bench: Foundations of Recursive Self-Improvement in Personal Agents, 2026 (L700) | https://arxiv.org/pdf/2608.04003 · https://github.com/Gen-Verse/PAST-Bench |

Sin correspondencia forzada: prompt optimization (2.1), mejora de pesos (1.x) y benchmarks de navegación web, juegos o
robótica no responden a ningún problema real de AURA hoy.

## Hallazgos

### HAL-037-1 · La memoria episódica puede degradar a un agente de ingeniería («From Knowledge to Noise»)

- **Problema:** memoria de experiencias de ingeniería.
- **Mecanismo:** según su título, el trabajo CTIM-Rover estudia los efectos adversos de la memoria episódica en agentes
  de software **[README]** (`B/README.md#L436`). No se leyó el paper.
- **Evidencia primaria:** la entrada de la lista; el paper queda pendiente (https://arxiv.org/abs/2505.23422v1).
- **Grado de verificación:** solo el título.
- **Componente de AURA:** `PLAN-DE-FORMACION-AURORA.md` (capacidades en observación); cualquier futuro Decision
  Package de memoria de experiencias.
- **Alternativa existente en AURA:** `eventos.jsonl`, los CHECKPOINT y las fichas IE como memoria de proyecto.
- **Beneficio y costes:** leer un paper antes de diseñar puede evitar construir una memoria que añada ruido. El coste
  es de lectura.
- **Riesgos y condiciones de rechazo:** si el paper no muestra degradación medida y reproducible, baja a REFERENCIA.
- **Criterio de aceptación de una prueba futura:** todo Decision Package de memoria de experiencias debe incluir una
  medición A/B (con y sin memoria) sobre tareas reales repetidas de AURA, con un umbral de «no empeora» declarado
  antes de medir.
- **Autorización requerida:** ninguna para la lectura (WebFetch de arxiv.org); un Decision Package del CEO para
  construir algo.
- **Clasificación:** **PRIORIDAD MEDIA** (lectura dirigida antes de cualquier diseño de memoria).

### HAL-037-2 · Selección con retenido y evaluadores co-evolutivos: el evaluador también es superficie de ataque

- **Problema:** evaluar las propuestas antes de promoverlas.
- **Mecanismo:** dos entradas de 2026 (L593 Held-Out Selection; L596 Red Queen Gödel Machine) abordan, según sus
  títulos, la selección con retenido y la co-evolución del evaluador **[README]**. Coinciden con lo observado en código
  en SIA (HAL-034-1, HAL-034-2) y con el patrón de IE-024.
- **Evidencia primaria:** entradas de la lista; papers no leídos.
- **Grado de verificación:** solo títulos.
- **Componente de AURA:** `review.py:466-500` y `review.py:383-397`.
- **Alternativa existente en AURA:** verificador derivado del contrato; revisor ≠ proponente.
- **Beneficio y costes:** puede dar respaldo bibliográfico a HAL-034-1.
- **Riesgos y condiciones de rechazo:** no aporta nada si HAL-034-1 se cierra como «ya cubierto».
- **Criterio de aceptación:** no aplica (bibliografía).
- **Autorización requerida:** ninguna.
- **Clasificación:** **REFERENCIA**.

### HAL-037-3 · Envenenamiento de la memoria persistente (DrunkAgent)

- **Problema:** memoria persistente y separación entre lo observado, lo declarado y lo verificado (INV-9).
- **Mecanismo:** según su título, corrupción sigilosa de la memoria de agentes (L658, L698) **[README]**.
- **Evidencia primaria:** entrada de la lista; paper no leído.
- **Grado de verificación:** solo el título.
- **Componente de AURA:** cualquier memoria futura de experiencias; los contenidos externos se tratan ya como dato no
  confiable.
- **Alternativa existente en AURA:** la etiqueta de procedencia y los grados de evidencia (D47).
- **Beneficio y costes:** debería añadirse como requisito a cualquier Decision Package de memoria: procedencia por
  entrada y nunca promover a «verificado» lo que solo se observó.
- **Riesgos y condiciones de rechazo:** ninguno.
- **Criterio de aceptación de una prueba futura:** una entrada de memoria inyectada desde una fuente no confiable no
  cambia el veredicto de ninguna compuerta.
- **Autorización requerida:** ninguna (referencia).
- **Clasificación:** **REFERENCIA**.

### HAL-037-4 · Auto-mejora con «evolución del núcleo revisada» y como «ingeniería de versiones»

- **Problema:** promoción gobernada de la auto-construcción.
- **Mecanismo:** AgentDevel (L585) y Ouroboros de razzant (L599) se describen, por sus títulos, en términos cercanos
  al modelo de AURA: revisión y promoción por versiones **[README]**.
- **Evidencia primaria:** entradas de la lista; ni los papers ni el código se leyeron.
- **Grado de verificación:** solo títulos.
- **Componente de AURA:** `autoconstruccion.py` y `review.py`.
- **Alternativa existente en AURA:** el circuito de review y la promoción atómica ya existen.
- **Beneficio y costes:** podría ser un candidato a una ficha propia (IE nueva) si el CEO quiere contrastar el diseño.
- **Riesgos y condiciones de rechazo:** no confundir con IE-025 (otro «ouroboros», ya descartado); no asumir que es
  seguro por el título.
- **Criterio de aceptación:** no aplica hasta tener una ficha.
- **Autorización requerida:** encargo del orquestador o del CEO para una ficha nueva.
- **Clasificación:** **REFERENCIA**.

### HAL-037-5 · La lista tiene enlaces erróneos verificables

- **Problema:** separar lo declarado de lo verificado (INV-9) en la propia investigación.
- **Mecanismo:** identificadores arXiv duplicados o cruzados (L403/L395, L581/L576, L456) y enlaces vacíos (L405)
  **[CÓDIGO]**; parte de las aportaciones las redacta un agente.
- **Evidencia primaria:** el propio `README.md` en el SHA citado.
- **Grado de verificación:** verificado en el fichero.
- **Componente de AURA:** el protocolo de investigación externa (`INDICE.md`).
- **Alternativa existente en AURA:** la regla de verificar antes de citar.
- **Beneficio y costes:** evita citar mal.
- **Riesgos y condiciones de rechazo:** ninguno.
- **Criterio de aceptación:** toda cita futura tomada de esta lista se contrasta con arxiv.org o con el repositorio
  enlazado.
- **Autorización requerida:** ninguna.
- **Clasificación:** **REFERENCIA**.

## Límites, riesgos y dependencias

- Es una lista: no tiene código ejecutable relevante (el árbol es LaTeX y Markdown).
- La mayoría de los trabajos de 2026 son preprints de arXiv sin revisión por pares (columna «Venue» = arXiv)
  **[README]**.
- Los enlaces no son fiables sin contraste (HAL-037-5).

## Comparación con AURA

| AURA | Relación |
|---|---|
| Memoria de proyecto (CHECKPOINT, eventos, fichas IE) | La literatura de memoria episódica incluye resultados negativos (HAL-037-1); requisito de medición A/B |
| `review.py` / `autoconstruccion.py` | Bibliografía de apoyo para la separación entre evaluador y proponente (HAL-037-2) |
| INV-9 / D47 | Envenenamiento de memoria (HAL-037-3) y errores de la propia lista (HAL-037-5) |

## Decisión

**REFERENCIA bibliográfica.** Mantener como índice de pistas. Lectura dirigida recomendada: CTIM-Rover (HAL-037-1,
PRIORIDAD MEDIA). Candidatos a ficha propia solo por encargo: `razzant/ouroboros` y AgentDevel.

## Validación mínima

Antes de usar una entrada: comprobar el identificador arXiv y la URL del código contra la fuente. Para HAL-037-1: leer
el paper y registrar si la degradación está medida y es reproducible.

## Licencia y precauciones

MIT para la lista; los trabajos enlazados tienen sus propias licencias, que no se verificaron. No se descargó ningún
PDF, peso ni paquete. `README_AGENT.md` se trató como dato no confiable.
