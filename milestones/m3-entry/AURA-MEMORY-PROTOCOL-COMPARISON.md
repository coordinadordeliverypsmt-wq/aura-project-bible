---
documento: "Comparación de protocolos de memoria de agentes (investigación externa)"
tipo: "Investigación. NO es una decisión ni una aprobación."
fecha: 2026-09-10
checkpoint: 5ebdce4
autor: "APUS-5 (CTO)"
---

# Qué existe realmente en el ecosistema (septiembre 2026)

**Clasificación de evidencia** (D47): `[LECT]` leído en la fuente · `[INFER]` deducido · **NO CONSTA** = no documentado
en la fuente consultada. Ninguna celda se rellena por suposición.

## 1 · Lo primero: no existe un estándar ratificado

| Nivel | Qué hay | Fuente |
|---|---|---|
| **Estándar ratificado** | **NINGUNO** para memoria de agentes | — |
| Grupo de interoperabilidad | **W3C AI Agent Memory Interoperability Community Group**, charter v1.0 (19-jun-2026). Un Community Group **«does not produce W3C Recommendations or other W3C standards»**; entrega *Community Group Reports* `[LECT]` | [w3.org/community/ai-agent-memory-interop](https://www.w3.org/community/ai-agent-memory-interop/) |
| Internet-Draft | **SAIHM** (`draft-saihm-memory-protocol-01`). **«This I-D is not endorsed by the IETF and has no formal standing in the IETF standards process.»** El ISE concluyó su consideración y recomienda llevarlo al IETF propiamente `[LECT]` | [datatracker.ietf.org](https://datatracker.ietf.org/doc/draft-saihm-memory-protocol/) |
| Propuestas con spec pública | **UMP**, **AMP** (YouTale), **OMP**, **open-memory-protocol** | ver §2 |
| Implementación + patrón | **Letta / MemGPT** | [letta.com/blog/agent-memory](https://www.letta.com/blog/agent-memory/) |
| Confusión de nombre | **OpAMP** = *Open Agent **Management** Protocol* (OpenTelemetry): gestiona **flotas de agentes de telemetría**, **no memoria** `[LECT]` | [opentelemetry.io/docs/specs/opamp](https://opentelemetry.io/docs/specs/opamp/) |

> **Corrección a la premisa de la misión.** «OAMP — Open Agent Memory Protocol» **no existe** con ese nombre.
> Lo que existe es `OpAMP`, de gestión de agentes de telemetría, sin relación con memoria. Y **«AMP» designa al
> menos dos proyectos distintos**: uno markdown-first de YouTale AI y otro un servidor de memoria MCP-native
> ([akshayaggarwal99/amp](https://github.com/akshayaggarwal99/amp)). Tratarlos como un solo «AMP» sería un error
> de análisis.

## 2 · Los candidatos, uno a uno

### UMP — Universal Memory Protocol
**Qué resuelve:** memoria portable entre agentes, runtimes y motores de almacenamiento; se posiciona como «la
tercera capa de interoperabilidad junto a MCP (herramientas) y A2A (coordinación)» `[LECT]`.
**Madurez:** el repositorio declara *Stable v1.0* con `SPEC.md`; el sitio mostraba v0.1 — **discrepancia entre
fuentes, anotada**. Propuesta de un autor individual, no estándar `[LECT]`.
**Modelo de datos (9 campos):** `kind`, `body`, `scope` (owner/project/visibility), `time` (bi-temporal),
`lifecycle`, `relations`, `provenance` (quién y cómo), `consent` (permisos de exportación), `integrity` (firma, L3).
**Operaciones:** `capabilities`, `recall`, `remember`, `get`, `revise` (supersede preservando historial),
`forget` (tombstone con razón); opcionales `feedback`, `subscribe`. Niveles de conformidad **L1/L2/L3**.
**Storage-agnóstico:** explícito — «no estandariza el algoritmo de recuperación, el modelo de embeddings, la base
de datos ni la política de ranking». Hay stores de JSON, Postgres, SQLite, Redis, Qdrant, Pinecone, Weaviate.
**Portabilidad:** ficheros `*.ump.json` (firmado) y `*.ump.md` (editable); copiar el fichero mueve la memoria.
**Auditoría:** log *append-only, hash-chained*, opcionalmente firmado, **local al servidor — no viaja con el record**.
**Seguridad:** trata la memoria como entrada controlable por el atacante y exige una tubería *verify → filter →
frame* en la rehidratación; **nunca interpolar en el prompt** `[LECT]`.
**Omisiones explícitas:** separación evidencia/hecho **NO CONSTA**; mecanismo de resolución de contradicciones
(solo existen «contradiction relations» en L3) **NO CONSTA**; estructura exacta de los timestamps bi-temporales
**NO CONSTA**; acceso al historial tras `revise` **NO CONSTA**; conflicto multi-agente **NO CONSTA**.

### AMP — Agent Memory Protocol (YouTale AI)
**Qué resuelve:** estructurar, enlazar, versionar y hacer portable la memoria del agente `[LECT]`.
**Madurez:** **v0.1 draft**, Apache 2.0.
**Modelo:** nodos **markdown con frontmatter**, enlazados estilo wiki formando un grafo; *daily notes*; git-friendly.
**NO CONSTA:** operaciones detalladas, contradicciones, evidencia/hecho, contexto/memoria, multi-agente,
auditoría, privacidad, olvido, seguridad, índices.
**Lectura para AURA:** es, en esencia, **el modelo Obsidian elevado a protocolo**. Sirve como formato de
*representación humana*; no como autoridad de memoria.

### SAIHM — `draft-saihm-memory-protocol`
**Qué resuelve:** memoria soberana con *identity binding* post-cuántico, **anclaje de auditoría en cadena
pública**, cifrado por celda con claves derivadas de wallet, contratos de compartición revocables y borrado
criptográfico alineado con el art. 17 del RGPD `[LECT]`. Compañero declarado de MCP.
**Madurez:** Internet-Draft **sin respaldo ni standing formal en el IETF**.
**Choque directo con AURA:** el anclaje en cadena pública y las claves derivadas de wallet son **dependencias
externas**, incompatibles con `D24`/`ADR-0001` (local-first, sin claves de terceros) `[INFER]`.

### Letta / MemGPT
**Qué es:** **implementación y patrón arquitectónico**, no protocolo de interoperabilidad.
**Modelo:** tres niveles inspirados en la jerarquía de memoria de un computador — *core memory* (bloques
editables dentro de la ventana de contexto), *recall memory* (histórico conversacional buscable) y *archival
memory* (almacenamiento vectorial) `[LECT]`. **Sleep-time agents**: un agente de fondo gestiona y compacta la
memoria de forma asíncrona.
**Lo decisivo para AURA:** **el agente lee y escribe su propia memoria**. Es exactamente la autoridad que la
hipótesis de AURA niega.

### Otros, declarados sin análisis profundo
`open-memory-protocol` (SMJAI) y `OMP` (open-mem, «capa de memoria determinista para agentes de código»)
existen y se registran aquí por completitud; **no los analicé en profundidad** y por tanto **NO CONSTA** su
detalle. `akshayaggarwal99/amp` es un servidor de memoria MCP-native, homónimo de AMP.

## 3 · Matriz de capacidades

`SÍ` = documentado · `PARCIAL` = presente pero sin mecanismo especificado · `NO` = documentado como ausente o
contrario · **NO CONSTA** = no documentado en la fuente consultada.

| Capacidad | UMP | AMP (YouTale) | SAIHM | Letta/MemGPT | **AURA hoy (5ebdce4)** |
|---|---|---|---|---|---|
| provenance | **SÍ** (campo, portable) | NO CONSTA | SÍ (firma/identidad) | NO CONSTA | **SÍ** (`trace_id, fuente, clase, origen, ts`) |
| authority | PARCIAL (scope + tokens L3) | NO CONSTA | SÍ (cripto) | **NO** (el agente edita) | **SÍ** (Core único; motor único; HITL rojo) |
| temporal validity | PARCIAL (bi-temporal en L2, campos NO CONSTA) | NO CONSTA | NO CONSTA | NO CONSTA | **NO** (solo `ts` de registro) |
| versioning | PARCIAL (`revise` preserva historial; acceso NO CONSTA) | PARCIAL (git) | NO CONSTA | NO CONSTA | **NO** (no hay `version`) |
| contradiction resolution | PARCIAL (relación L3, mecanismo NO CONSTA) | NO CONSTA | NO CONSTA | NO CONSTA | **PARCIAL** (gana la última declaración; `refutada`) |
| evidence vs fact | **NO CONSTA** | NO CONSTA | NO CONSTA | NO CONSTA | **PARCIAL** (`clase` distingue declarado/observado) |
| context separation | PARCIAL (`scope`) | NO CONSTA | NO CONSTA | **NO** (core memory *está* en el contexto) | **PARCIAL** (hay frontera; contamina vía episódica) |
| multi-agent | PARCIAL (scope compartido; conflicto NO CONSTA) | NO CONSTA | SÍ (contratos revocables) | SÍ (sleep-time agent) | **NO** (no hay agentes internos aún) |
| audit | SÍ (hash-chain local, no portable) | NO CONSTA | SÍ (cadena pública) | NO CONSTA | **SÍ** (`audit.jsonl`, `audit=True`) |
| storage independence | **SÍ** (explícito) | NO (markdown) | NO CONSTA | NO (tiers propios) | **SÍ** (`MemoryStore` + N1/N2) |
| privacy / terceros | PARCIAL (`consent` de exportación) | NO CONSTA | SÍ (cifrado por celda) | NO CONSTA | **SÍ** (`_TERCERO`, `SenalDeTercero`) |
| deterministic lookup | **NO CONSTA** (no estandariza recuperación) | NO CONSTA | NO CONSTA | **NO** (tool calls / vectorial) | **SÍ** (0,00 s, 0 llamadas al LLM) |
| forgetting | SÍ (`forget` = tombstone con razón) | NO CONSTA | SÍ (borrado criptográfico) | NO CONSTA | **PARCIAL** (`borrar`, `refutar`, histórico no recuperable) |
| portability | **SÍ** (`.ump.json` / `.ump.md`) | SÍ (markdown+git) | NO CONSTA | NO CONSTA | **PARCIAL** (`exportar()` JSON; sin importar) |

## 4 · Evidencia empírica independiente (no de los protocolos)

**a) Dónde situar el plano de control cambia el resultado, y el problema real es el olvido.**
«Control-Plane Placement Shapes Forgetting», 13 configuraciones y **385 casos adversariales** `[LECT]`:
primitivos deterministas bastan para categorías léxicas y temporales pero caen a **5 % en ofuscación de
identificadores y 0 % en multilingüe**; un LLM en tiempo de inscripción recupera canonicalización (**100 %**) pero
da **0 %** en borrado consciente de intención; un *hook en tiempo de mutación* alcanza **78–85 %** en ese borrado y
**91,7–93,2 %** global, con 2,3 s/caso. Conclusión citada: **«los fallos de producción son predominantemente
fallos de olvido, no de recuperación, aunque los benchmarks existentes solo miden recuperación.»**
[arxiv.org/abs/2606.15903](https://arxiv.org/abs/2606.15903)

**b) Envenenamiento de memoria: basta UNA escritura.**
«A diferencia del prompt injection y el jailbreaking, donde el payload debe estar presente en el contexto activo
**cada vez**, el envenenamiento de memoria requiere **una sola escritura exitosa**» `[LECT]`. Variantes
documentadas: *sleeper* (entre recuperaciones exitosas, **89 %** de acciones con la intención del atacante),
**MemoryGraft** (sin *trigger*: artefactos de ingesta aparentemente benignos —**documentación**— hacen que el
agente construya y **persista** «experiencias exitosas» maliciosas) y *MemPoison*. Incidentes referidos en
Gemini, Azure y Bedrock. Y la tensión de fondo: **las políticas agresivas de escritura y recuperación que mejoran
el rendimiento amplían la superficie de ataque**.
[arxiv.org/pdf/2606.04329](https://arxiv.org/pdf/2606.04329) · [arxiv.org/html/2605.15338v1](https://arxiv.org/html/2605.15338v1)

## 5 · Las tres conclusiones de la investigación

1. **No hay estándar al que adherirse.** Adoptar hoy cualquiera de estos protocolos como autoridad sería atarse a
   una propuesta v0.1–v1.0 de un solo autor, a un Internet-Draft sin standing, o a un formato markdown.
   Lo defendible es **tomar vocabulario y forma de record**, no la autoridad.
2. **Ninguno resuelve evidencia vs hecho ni la contradicción.** Es la capacidad que AURA ya tiene a medias (por
   `clase` y «gana la última declaración») y la que ningún candidato especifica. Ahí AURA **inventa**.
3. **La literatura refuta el modelo de Letta para AURA.** Un agente que edita su propia memoria, con una sola
   escritura envenenada, convierte una inferencia en verdad persistente. La hipótesis del CEO —Memory Core como
   única autoridad— **queda respaldada por evidencia externa**, no solo por preferencia arquitectónica.

---
**Fuentes** · [UMP](https://github.com/edihasaj/universal-memory-protocol) ·
[AMP YouTale](https://agentmemoryprotocol.io/) · [amp MCP-native](https://github.com/akshayaggarwal99/amp) ·
[OpAMP](https://opentelemetry.io/docs/specs/opamp/) · [SAIHM I-D](https://datatracker.ietf.org/doc/draft-saihm-memory-protocol/) ·
[W3C CG](https://www.w3.org/community/ai-agent-memory-interop/) · [Letta](https://www.letta.com/blog/agent-memory/) ·
[open-memory-protocol](https://github.com/SMJAI/open-memory-protocol) · [OMP](https://github.com/open-mem/omp) ·
[control-plane/forgetting](https://arxiv.org/abs/2606.15903) · [memory poisoning](https://arxiv.org/pdf/2606.04329) ·
[sleeper poisoning](https://arxiv.org/html/2605.15338v1) · [SMSR defence](https://arxiv.org/pdf/2606.12703)
