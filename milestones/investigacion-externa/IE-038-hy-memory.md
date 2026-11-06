---
id: IE-038
titulo: Tencent-Hunyuan/Hy-Memory — memoria cognitiva para agentes LLM (chat, trabajo y código) con reconciliación por LLM
fuente: https://github.com/Tencent-Hunyuan/Hy-Memory
rama-revision: main (por defecto) @ 0abf87d4b613cf7c8a4177e2dab3f82808e59cb4 (2026-10-26T14:34:53Z, merge PR #180)
fecha-revision: 2026-10-26
licencia: Apache-2.0. El fichero `LICENSE` es Apache-2.0 íntegro con un preámbulo de Tencent («does not impose any additional restrictions»); la API de GitHub lo clasifica como `NOASSERTION`/«Other» por ese preámbulo. `pyproject.toml` declara `license = "Apache-2.0"`
area: asistentes (memoria)
estado: no adoptar el motor (referencia de esquema)
cobertura: Lectura remota con `gh api` (repo, commits, license, contents?ref=<SHA>, git/trees recursivo, releases, contributors, search/issues). Leídos: README.md (262 líneas), LICENSE, pyproject.toml, .env.example, hy_memory/models/memory.py, hy_memory/agent/reconciler.py (por grep y tramos), hy_memory/coding/types.py, hy_memory/coding/fact_reconciler.py (cabecera), hy_memory/coding/store.py (grep y tramos), hy_memory/data/history_store.py (grep). NO leídos: los 3 artículos (arXiv 2606.09483, 2610.22196 y el PDF CMB), pipelines/writer.py, reader*, system2_*, memhub/ completo, los 122 ficheros de tests (solo nombres), ni el modelo de Hugging Face. Sin clonar, instalar ni ejecutar. Lo leído por un solo agente, sin auditor independiente
relacionadas: [IE-021, IE-022, IE-039]
---

Base de las citas: `B = https://github.com/Tencent-Hunyuan/Hy-Memory/blob/0abf87d4b613cf7c8a4177e2dab3f82808e59cb4`.

Clasificación: **[CÓDIGO]** observado en el SHA citado · **[README]/[PAPER]** declarado por los autores ·
**[TESTS-DECLARADOS]** existen pruebas con ese nombre, no ejecutadas · **[REPRODUCIDO-POR-TERCEROS]** con fuente ·
**[INFER]** inferencia. Ningún benchmark de esta ficha ha sido reproducido.

## Qué se examinó (rutas y símbolos)

- **Procedencia y mantenimiento** **[CÓDIGO]**: organización `Tencent-Hunyuan` (cuenta de tipo Organization; coincide con
  el equipo Hunyuan de Tencent, propietario no ambiguo). Repo creado el 2026-10-15, último push el 2026-10-26, 1.303
  estrellas, 181 issues/PR. Releases `v1.0.2` (10-16), `v1.0.4` (10-18), `hy-memory-v2.0.5` (10-22). 5 contribuidores
  visibles; uno con 58 commits. **Proyecto de 11 días**: muy activo, pero sin historial de estabilidad.
- **Dependencias** (`pyproject.toml`) **[CÓDIGO]**: `openai>=1.40` (cliente compatible), `chromadb`, `kuzu`,
  `scikit-learn`, `tiktoken`, `rank-bm25`, `jieba`, `langdetect`; opcionales `torch`+`transformers` (rerank),
  `qdrant`, `faiss`, `neo4j`, `aiomysql`.
- **Configuración por defecto** **[CÓDIGO]** (`.env.example#L22-L38`): LLM `deepseek-chat` en `https://api.deepseek.com` y
  embeddings `text-embedding-v4` en `dashscope.aliyuncs.com`, **ambos con clave de terceros**. El cliente es
  «OpenAI-compatible», así que podría apuntarse a un servidor local **[INFER]**; no se verificó que funcione con un
  modelo pequeño.
- **Modelo propio** **[README]** (`README.md#L35-L38`, `#L57-L59`): `Hy-Memory-30B-A3B` (MoE, 30B parámetros totales,
  3B activos), con versiones FP8 y GGUF, entrenado con «attributed reinforcement learning» para extraer y reconciliar.
- **Modos** **[README]** (`README.md#L198-L204`): `lite` (solo embeddings del texto crudo, sin LLM), `pro` (+ extracción y
  reconciliación por LLM), `ultra` (+ «System 2», inducción de esquemas y grafo).

## Patrones relevantes

**1. Hechos versionados que no se reescriben** **[CÓDIGO]**
- `MemoryNode` lleva `valid_from/valid_until`, `supersedes`, `superseded_by` e `is_latest`
  (`B/hy_memory/models/memory.py#L262-L275`), y `VersionedFact` declara «no modificar el contenido; cambiar por status +
  arista SUPERSEDED_BY» (`#L572-L577`).
- Estados (`#L121-L129`): `ACTIVE`, `SUPERSEDED`, `NEGATED`, `CONFLICTED`, `SHADOW` (borrado lógico o inferencia de
  baja confianza), `ARCHIVED`.

**2. Distingue declarado de inferido, al menos en el esquema** **[CÓDIGO]**
- `SourceType` = `EXPLICIT` («用户明确陈述», lo declaró el usuario) / `INFERRED` / `COMPOSITE` (`#L132-L136`).
- Etiquetas metacognitivas `INFERRED_NOT_STATED`, `STALE`, `CONFLICTED` y `NEEDS_CLARIFICATION` (`#L170-L185`).
- Tipos de laguna `UNRESOLVED_CONFLICT` e `INFERRED_UNVERIFIED` (`#L210-L215`).
- Procedencia: `source_session_id`, `source_turn_index` y `evidence_chain` (`#L319-L322`).
- **No se verificó** qué ruta de escritura rellena realmente `INFERRED`, ni si el lector filtra por esos campos
  (no se leyó `writer.py` ni `reader*.py`).

**3. Los conflictos los resuelve un LLM, no una regla** **[CÓDIGO]**
- `agent/reconciler.py`: por cada lote recupera candidatos (vector + BM25) y hace **una llamada al LLM** que devuelve
  operaciones.
- `SUPERSEDE`: el viejo pasa a `SHADOW`, `is_latest=False`, y el nuevo lleva `supersedes=[old]`.
- `UPDATE` (fusionar): el viejo pasa a `SHADOW`, sin cadena (`#L83-L98`).
- Un `DELETE` heredado se convierte en `SHADOW` (`#L1876-L1894`).
- **La decisión de qué contradice a qué la toma el modelo.**

**4. Ante un fallo, prefiere duplicar a perder** **[CÓDIGO]**
- Si el LLM de reconciliación cae o su JSON no se puede analizar, se ejecuta `_fallback_add_ops` y **todo se inserta
  como ADD** (`#L693-L702`, `#L1453-L1472`).
- El comentario justifica que «perder contenido es irrecuperable; los duplicados los limpia una reconciliación
  posterior».
- Consecuencia **[INFER]**: tras un fallo pueden quedar **dos hechos contradictorios ACTIVOS a la vez**, sin marcarse
  como `CONFLICTED`.

**5. Incoherencia interna entre lo declarado y lo real** **[CÓDIGO]**
- El docstring del módulo dice que las operaciones son «ADD / DELETE» (`#L13-L25`).
- La clase y el analizador usan `ADD / SUPERSEDE / UPDATE` (`#L83-L98`, `#L1910`).
- Es menor, pero es el mismo patrón que `CLAUDE.md` §5.

**6. Memoria de ingeniería («Working/Coding»)** **[CÓDIGO]** — la parte más cercana al problema real de AURA
- Dos capas enlazadas:
  - `WorkingFact`: qué se hizo en la sesión, con `statement`, `files` y `details` literales (`B/hy_memory/coding/types.py#L210-L252`).
  - `CodingMemory` (la experiencia): `task`, `solution`, `boundary_envs`, `confidence=0.7` por defecto y
    `source_fact_ids` (`#L84-L115`).
- Enlace en los dos sentidos: `fact.derived_experience_ids` ↔ `experience.source_fact_ids`.
- Un hecho sustituido pasa a `superseded`, con `fact_link` hacia el nuevo (`#L237-L239`; `store.py#L1295-L1296`).
- **Sin TTL**: la vigencia la decide un `FactReconciler` (LLM) que juzga si la nueva traza «continúa la misma tarea»
  (`types.py#L145-L155`).
- **Pero las experiencias se borran físicamente**: `DELETE FROM coding_memory_meta` (`store.py#L1083-L1089`), y se
  actualizan por upsert (`#L1051-L1078`).
- Una experiencia no tiene estado `retractada`, ni `refutada por` [CÓDIGO, por grep: los únicos estados son
  `active`/`superseded`, y solo en los hechos].

**7. Cadena de versiones del código** **[README]** (`README.md#L218-L236`): guarda el diff real de cada revisión (de
git o de las acciones `path/old/new` de la traza) **sin LLM**, porque el resumen omite justo las versiones revertidas.

**8. Auditoría** **[CÓDIGO]**
- `history_store.py` crea la tabla `memory_history` (event, old/new memory, old/new status).
- La tabla `memory_operations` (auditoría de ADD/UPDATE) está **desactivada por defecto**
  (`.env.example#L18`, `MEMORY_MEMORY_OPERATIONS_ENABLED=false`).

**Pruebas** **[TESTS-DECLARADOS]**: 122 ficheros en `tests/`, entre ellos `test_reconcile_fallback.py`,
`test_supersede_chain_recall.py`, `test_evolution_chain_shadow_filter.py`, `test_delete_complete.py` y
`coding/test_fact_reconciler.py`. No ejecutados.

**Benchmarks**:
- Se anuncian el artículo EMNLP 2026 (arXiv 2606.09483), el benchmark CMB (enviado a ICLR 2027, PDF en el repo) y el
  informe técnico arXiv 2610.22196 **[PAPER, no leídos]**.
- Ninguna cifra se ha **[REPRODUCIDO-POR-TERCEROS]**: en el issue tracker no aparece ninguna reproducción; la búsqueda
  de «reproduce» solo devuelve 19 resultados, todos bugs o PR propios.

## Límites, riesgos y dependencias

- **Nube y claves de terceros por defecto** (DeepSeek y DashScope): choca con D24/ADR-0001 tal como viene.
- **Modelo grande.** El extractor propio tiene 30B parámetros totales. Ni en GGUF cabe en HC-1 (3,6 GiB de RAM) **[INFER]**.
  Con `qwen2.5:0.5b` como reconciliador, la calidad de las decisiones SUPERSEDE/UPDATE no está demostrada en ningún
  sitio.
- **El LLM decide la verdad de la memoria.** Contradice ADR-0014: en AURA el Core es la fuente de verdad y las
  superficies deterministas no consultan al LLM.
- **Juventud.** 11 días de vida, versiones 1.0 → 2.0 en una semana e issues abiertos de interbloqueo y crecimiento sin
  límite (#118, #119).
- **Volumen de dependencias.** Chroma, Kuzu y scikit-learn: pesado para un Celeron N4020 **[INFER]**.

## Comparación con AURA

| AURA | Hy-Memory | Relación |
|---|---|---|
| `core/modelo_usuario.py` (`origen` declarada/observada, `fuente`, `valid_from` en `ver()` L53-L70; `corregir` L77 → `declarada`; `refutar` L132, marca persistente sin borrar; `olvidar_entrada` L143 por `ts`) | `SourceType` EXPLICIT/INFERRED/COMPOSITE, estados SHADOW/NEGATED/SUPERSEDED | **Ya cubierto en lo esencial**, y con más rigor: en AURA la corrección es del usuario y pasa por el Motor Único, mientras que en Hy-Memory la decide un LLM. AURA no tiene `CONFLICTED` como estado explícito **[INFER, grep]** |
| `core/ejecutor_modelo_usuario.py:268-278` (`cm2.hecho_retirado`, sin texto) | `memory_history` y `memory_operations` (apagada por defecto) | AURA audita la retirada por defecto; Hy-Memory no |
| Memoria de experiencias de ingeniería | `WorkingFact` ↔ `CodingMemory` con `source_fact_ids`, `boundary_envs` y `confidence` | **Brecha real en AURA.** Hoy esa memoria vive en documentos (`CHECKPOINT-CONTINUIDAD.md`, fichas IE, `CLAUDE.md` §5, `PROCEDIMIENTO-DEFECTO-DIFICIL.md`), no en una estructura que el sistema recupere. No se encontró código equivalente en `aura_skeleton` **[INFER, grep de «experiencia/lección»]** |
| `CLAUDE.md` §5 («declarado ≠ real») | Retroceso a ADD-all; docstring que contradice al código | Hy-Memory es un **contraejemplo** útil para las pruebas |

## Hallazgos

**HAL-038-1 · Esquema de dos capas para la memoria de experiencias de ingeniería**

- **Problema:** AURA no tiene memoria estructurada de defectos previos ni de cómo se resolvieron.
- **Mecanismo:** un hecho por sesión (qué se hizo, qué ficheros) más experiencias reutilizables (tarea, solución, entorno
  límite, confianza), enlazados en los dos sentidos.
- **Evidencia:** `B/hy_memory/coding/types.py#L84-L115`, `#L210-L252` [CÓDIGO].
- **Grado de verificación:** esquema leído; comportamiento no ejecutado.
- **Componente AURA:** nuevo, junto a `modules/memory.py`. La alternativa existente son los documentos de continuidad.
- **Beneficio:** recuperar «este defecto ya ocurrió, se resolvió así, en este entorno».
- **Costes:** un componente nuevo. La regla de `CLAUDE.md` §4 exige demostrar antes que no puede extenderse uno
  existente.
- **Riesgos y condiciones de rechazo:**
  - la extracción por LLM fabricaría experiencias;
  - se rechaza si la experiencia no se puede derivar de un artefacto verificable (commit, prueba, informe de mutación).
- **Criterio de aceptación futuro:** dada una regresión conocida (p. ej. ALERTA-005), la consulta devuelve la
  experiencia con su `source` (commit/ADR). Una experiencia sin fuente se rechaza al escribirse.
- **Autorización:** Decision Package del CEO más acta D23, porque es una capacidad nueva.
- **Clasificación:** **PRIORIDAD MEDIA**. Solo se adopta el esquema; la extracción por LLM no.

**HAL-038-2 · Retractar experiencias sin borrarlas**

- **Problema:** una experiencia de ingeniería que resulta falsa debe dejar de recomendarse sin perder el rastro.
- **Mecanismo:** Hy-Memory **no lo hace**. Borra físicamente las experiencias (`store.py#L1083-L1089`); solo los hechos
  tienen `superseded`.
- **Evidencia:** [CÓDIGO].
- **Grado de verificación:** lectura.
- **Componente AURA:** el patrón `refutar` de `modelo_usuario.py:132` ya existe y es el correcto.
- **Uso para AURA:** si se construye HAL-038-1, debe heredar `refutar` (estado más motivo y referencia de la evidencia
  refutadora), no copiar el `DELETE`.
- **Riesgos:** ninguno, porque no se adopta nada.
- **Criterio de aceptación futuro:** refutar una experiencia la excluye de la recuperación y conserva la entrada con la
  referencia al refutador.
- **Autorización:** la misma de HAL-038-1.
- **Clasificación:** **REFERENCIA** (contraejemplo).

**HAL-038-3 · Que el LLM decida qué hecho contradice a otro**

- **Mecanismo:** `SUPERSEDE`/`UPDATE` emitidos por el LLM, y retroceso ADD-all que deja contradicciones activas sin
  marcar.
- **Evidencia:** `B/hy_memory/agent/reconciler.py#L83-L98`, `#L693-L702` [CÓDIGO].
- **Componente AURA:** `modelo_usuario.py` (`corregir` lo decide el usuario).
- **Por qué no se adopta:**
  - viola ADR-0014 y D24 (modelo en la nube por defecto);
  - con `qwen2.5:0.5b` sería una fuente de verdad poco fiable;
  - el retroceso viola INV-9, porque muestra como vigentes dos versiones contradictorias.
- **Condición para revisarlo:** ninguna mientras ADR-0014 esté en vigor.
- **Clasificación:** **NO ADOPTAR**.

**HAL-038-4 · Estado explícito `CONFLICTED` y laguna `UNRESOLVED_CONFLICT`**

- **Problema:** ante dos declaraciones incompatibles sin corrección explícita, AURA solo distingue `vigente`/`refutada`
  **[INFER]**.
- **Mecanismo:** marcar el par como en conflicto y pedir aclaración (`NEEDS_CLARIFICATION`) en lugar de elegir.
- **Evidencia:** `B/hy_memory/models/memory.py#L121-L129`, `#L170-L185`, `#L210-L215` [CÓDIGO; no se verificó qué lo
  rellena].
- **Componente AURA:** `describir_conocimiento` y el filtro de vigencia de `modelo_usuario.py:182-215`.
- **Beneficio:** no fingir certeza (INV-9).
- **Riesgo:** sobremarcar conflictos.
- **Criterio de aceptación futuro:** dos declaraciones incompatibles con el mismo `valid_from` producen una pregunta
  determinista al usuario y ninguna de ellas se afirma.
- **Autorización:** DP del CEO.
- **Clasificación:** **REFERENCIA**. Se promovería a MEDIA solo si el uso real muestra conflictos no resueltos
  (`PLAN-DE-FORMACION-AURORA.md`).

**HAL-038-5 · Cadena de diffs sin LLM como memoria de versiones revertidas**

- **Mecanismo:** guardar el diff real de cada revisión, porque los resúmenes pierden las versiones revertidas.
- **Evidencia:** `README.md#L218-L236` [README]; `coding/chain_store.py` no se leyó.
- **Componente AURA:** git y las evidencias de `milestones/`. El problema ya está cubierto por git **[INFER]**.
- **Clasificación:** **REFERENCIA**.

## Decisión

**ADAPTAR SOLO EL ESQUEMA (HAL-038-1) como referencia de diseño; NO ADOPTAR el motor.**

- El paquete no se usa: nube y claves por defecto, un LLM como árbitro de la verdad y un proyecto de 11 días.
- El esquema hecho↔experiencia con procedencia es la mejor referencia vista hasta ahora para memorizar experiencias de
  ingeniería.
- Deben corregirse sus dos defectos: el borrado físico y el retroceso que deja contradicciones activas.

## Validación mínima

Antes de cualquier DP: escribir a mano (sin LLM) 5 experiencias de ingeniería reales de AURA, sacadas de `CLAUDE.md` §5 y
de `CHECKPOINT`, con el esquema de HAL-038-1 más `refutada`, y medir si una consulta por síntoma recupera la experiencia
correcta mejor que grep sobre los documentos. Si no mejora a grep, se descarta.

## Licencia y precauciones

**Apache-2.0** con un preámbulo de Tencent que no añade restricciones. Si se reutilizara código habría que conservar el
`NOTICE` y la atribución, pero **solo se toma la idea del esquema; no se copia código**. Los pesos de `Hy-Memory-30B-A3B`
no se examinaron, y el README no indica que tengan una licencia distinta. No se clonó, instaló, descargó ni ejecutó nada.
Para usar `gh api` hubo que salir del sandbox de red, solo para lecturas.
