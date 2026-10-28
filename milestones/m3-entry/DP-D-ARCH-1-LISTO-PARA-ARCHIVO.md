# Decision Package — `D-ARCH-1`: qué significa **LISTO PARA ARCHIVO**

**Estado:** **`DECISION_REQUIRED`.** No implementa nada, no crea la fuente, no conecta el archivador,
no toca `politica-orquestador.toml` ni ninguna autoridad. **Todavía no se ha escrito código.**
**Encargo (CEO, 2026-09-06):** definir cuándo un artefacto producido por AURA es suficientemente
maduro para ser candidato a archivado Cloud, y decidir si se autoriza una octava fuente de
descubrimiento, exclusivamente lectora, que identifique esos candidatos.
**ID propuesto:** `D-ARCH-1`, siguiendo el esquema vigente (`D-G1-n`, `D-CP-n`, `D-ORCH-n`,
`D-M8-n`). **El identificador definitivo lo fija el CEO.**
Evidencia D47: `[EJEC]` medido · `[LECT]` leído · `[INFER]` deducido.

---

## 1 · Contexto — por qué aparece ahora

`archivador_cloud.py` está cerrado técnicamente `[EJEC]`: 29 pruebas propias, 17/17 mutantes
detectados, 843 pruebas del control-plane, ruff limpio, y una prueba real contra Google Drive por
GVFS con verificación posterior por relectura y hash. Copia y solo copia: sin `os`, sin `shutil`, sin
`subprocess`, sin red. Fail-closed. Conflictos versionados sin destruir lo anterior.

La auditoría arquitectónica posterior encontró que **no falta capacidad: falta criterio**. El
componente sabe archivar; nadie ha decidido **qué merece archivarse ni cuándo**. Sin esa decisión, el
archivador solo puede invocarse a mano, y conectarlo al ciclo sería automatizar un juicio que no
existe.

Esta decisión es la que desbloquea esa pregunta, y **solo esa**.

## 2 · Problema — por qué la madurez no debe inferirse

Un archivador automático sin criterio no preserva historia: **multiplica borradores**. Y las
heurísticas disponibles fallan las tres:

- **«Está commiteado»** — un borrador se commitea igual. Commitear no aprueba nada. Además, consultar
  git desde el plano de desarrollo exigiría **ejecutar** un proceso donde hoy no hay ejecución.
- **«No ha cambiado en N días»** — mide inactividad, no madurez. Un capítulo abandonado a medias
  puntúa igual que uno aprobado.
- **«Está en un directorio de gobernanza»** — `adr/` contiene también `adr/plantilla-adr.md` `[LECT]`.

Las tres tienen el mismo defecto de fondo: **serían el sistema decidiendo qué es historia**. Eso es
justo lo que este proyecto no hace — `INV-9` prohíbe fingir capacidad, y `D47` exige clasificar la
evidencia en vez de deducirla.

## 3 · Propuesta — la definición

> **Un artefacto está `LISTO_PARA_ARCHIVO` cuando declara en su propio frontmatter un estado terminal
> otorgado por autoridad humana, esa declaración es legible por máquina, lleva identidad de versión,
> y pertenece a una categoría permitida de `AURA_CLOUD`.**
>
> **La madurez la declara el documento. El sistema la lee y la verifica. Nunca la infiere.**

Las cuatro precondiciones son **necesarias y, juntas, suficientes**:

| # | Precondición | Cómo se comprueba |
|---|---|---|
| 1 | Estado terminal declarado | `estado: "Aprobado"` · `estado: accepted` · `estado: "Vinculante"` en el frontmatter |
| 2 | Identidad de versión | campo `version`, o `fecha-resolucion` en los ADR |
| 3 | Categoría permitida | una de las siete de `archivador_cloud.CATEGORIAS` |
| 4 | Supera la lista negra | la que `archivador_cloud` ya aplica y protege con 17 mutantes |

Ninguna basta sola: un capítulo aprobado dentro de `.git` no se archiva, y un fichero en categoría
permitida sin estado declarado tampoco.

## 4 · Evidencia del repositorio

El patrón **no se propone: ya existe**, y se cita con fichero y línea `[LECT]`:

| Afirmación | Evidencia |
|---|---|
| `Aprobado` + `version` ya existe | `docs/libro-01-gobernanza-y-metodo/1.1-constitucion-roles-autoridad.md:7` (`estado: "Aprobado"`) y `:4` (`version: 1.4.0`) — **37 de 37 capítulos** lo declaran `[EJEC]` |
| `accepted` + `decisor` ya existe | `adr/0003-listas-autonomia-hitl.md:4` (`estado: accepted`) y `:7` (`decisor: "Mauricio (CEO)"`) — **23 ADR reales** `[EJEC]` |
| `Vinculante` ya existe | `decisiones/2026-07-17-acta-decisiones-fundacionales.md:6` (`estado: "Vinculante"`) y `:3` (`version: 1.20.0`) |
| `proposed` no debe tratarse como maduro | `adr/plantilla-adr.md:4` — **el único `proposed` del repositorio es una plantilla**: el criterio ya discrimina solo, sin ayuda |
| La autoridad está detrás del estado | `1.1 §3` — jerarquía normativa; solo el CEO aprueba documentos normativos |
| Categorías ya operativas | `archivador_cloud.CATEGORIAS` = las siete carpetas de `AURA_CLOUD` ya creadas `[EJEC]` |

**Ambigüedad detectada, y no la resuelvo:** existen **tres vocabularios** para el mismo concepto —
`"Aprobado"` (capítulos), `accepted` (ADR), `"Vinculante"` (actas)—. Son tres formas de decir «esto ya
está decidido», pero **ningún documento del repositorio los declara equivalentes**. Tratarlos como
sinónimos es una interpretación, y corresponde al CEO hacerla o rechazarla.

**Segunda ambigüedad:** **12 de 65** ficheros de `milestones/` tienen frontmatter; los otros **53**
declaran su estado en prosa —`**Estado:** PROPUESTO`— `[EJEC]`. No es maquinable de forma fiable, y
un parser laxo archivaría propuestas como si fueran decisiones.

## 5 · Alternativas

**A · Inferir madurez por heurísticas** (commit, antigüedad, `mtime`).
*Ventaja:* cobertura inmediata, sin tocar documentos. *Riesgo:* el sistema decide qué es historia;
la señal de commit exige ejecutar git, introduciendo ejecución en el plano de desarrollo.
*Consecuencia:* contradice `INV-9` y `D47`. **Desaconsejada.**

**B · Frontmatter declarativo** (la propuesta).
*Ventaja:* cero inferencia; verificable a simple vista; ya cubre **60 documentos** —37 capítulos, 23
ADR y las actas—; no necesita git, ni red, ni ejecución. *Riesgo:* deja fuera los 53 milestones sin
frontmatter y los cierres, que son históricos de hecho pero no lo declaran.
*Consecuencia:* archivo más pequeño y enteramente justificado.

**C · Declarativo + enriquecimiento posterior del frontmatter.**
Igual que B, y después se añade frontmatter a los milestones que lo merezcan.
*Ventaja:* cobertura completa con el mismo criterio. *Riesgo:* tocar 53 documentos de gobernanza es
**trabajo de autoría, no de archivo**, y cada uno exige decidir cuál es su estado real.
*Consecuencia:* válida como fase posterior; **no debe fusionarse con esta decisión**.

## 6 · Recomendación

**Alternativa B.** La evidencia del repositorio la respalda sin necesidad de interpretación: el
proyecto ya declara madurez con autoridad y versión en 60 documentos, y eso es exactamente lo que
merece preservarse.

Lo que no la declara **no es que esté maduro sin que se note: es que nadie ha dicho que lo esté**, y
el archivador no debe ser quien lo decida. La alternativa C queda disponible como encargo posterior
si el CEO quiere cobertura completa.

## 7 · Alcance de la octava fuente

Sería la octava de `descubrimiento.FUENTES`, que hoy tiene siete `[EJEC]`: `codigo_muerto`,
`invocables_sin_clasificar`, `eventos_sin_puerta`, `decisiones_pendientes`, `bloqueos_registrados`,
`estancamiento`, `capacidades_del_entorno`. El precedente exacto es la séptima (`DR-A`), que también
nació lectora y con techo `DECISION_REQUIRED`.

**Lo que podría hacer:** abrir ficheros de las categorías permitidas, leer su frontmatter, comprobar
las cuatro precondiciones y **proponer** candidatos.

**Lo que NO podría hacer, y debe quedar escrito en el acta:**

- **sin escritura** — ni un fichero, ni un evento, ni `estado.json`
- **sin red** — `A8 · §16` intacta
- **sin git** — nada de `subprocess` ni de consultar HEAD
- **sin Drive** — la fuente **no archiva**; solo identifica candidatos
- **sin archivado** — invocar `archivador_cloud` no le corresponde
- **sin cambio de autoridad** — no toca `AUTO`, `REVIEW`, `act_scope` ni ejecutores
- **salida máxima `DECISION_REQUIRED`** — nunca `OPORTUNIDAD_REAL`; eleva conocimiento, jamás permiso

## 8 · Gobernanza — dos decisiones, deliberadamente separadas

**DECISIÓN 1 — la de este documento.** Adoptar la definición de `LISTO_PARA_ARCHIVO` y autorizar la
fuente **lectora**. No amplía autoridad: leer frontmatter y proponer no ejecuta nada.

**FUTURA DECISIÓN 2 — no incluida aquí.** Autorizar que *archivar* sea una acción de nivel `REVIEW`.
Es una decisión distinta y mayor, porque **archivar escribe**, y `politica-orquestador.toml` deriva
`AUTO` **solo de acciones de efecto `lectura`** `[LECT]`. Exigiría además ampliar el alcance del acta
`DEC-ORCH-2` y declarar la acción en la política — fichero que, según su propia cabecera, *«ningún
componente del orquestador puede escribir»*.

**No se fusionan.** Aprobar la primera no concede la segunda, y ese es el punto: se puede saber qué
está listo para archivo mucho antes de decidir si AURA lo archiva sola.

## 9 · `ALERTA-006` — cómo la respeta esta propuesta

`ALERTA-006` sigue **abierta y con prioridad máxima** `[LECT]`, por rutas que mutan estado **fuera del
Motor Único**, en violación de `ALERTA-005` (*«toda ejecución pasa por el motor único; ninguna ruta
alternativa»*).

**La fuente propuesta no la roza**: no muta nada. Es lectura pura, igual que las siete actuales.

**El archivado futuro sí la rozaría**, y conviene decirlo ahora: archivar **escribe** en Drive. Un
archivado automático que no pasara por el Motor Único sería exactamente el patrón que `ALERTA-006`
denuncia. Existe un atenuante real —el archivador nunca borra ni sobrescribe, y verifica por
relectura— pero **un atenuante no es una excepción**. Por eso la Decisión 2 debe resolverse por la vía
del motor, no por una ruta propia.

## 10 · Impacto — qué podría requerir cambios **después** de aprobar

Un módulo nuevo de fuente en `entorno/control-plane/` con sus pruebas y su fichero de mutación · una
entrada en `descubrimiento.FUENTES` · el acta que registre la decisión.

**Y nada más.** En particular, la Decisión 1 **no** requiere tocar `politica-orquestador.toml`, ni
`AUTO`, ni `REVIEW`, ni el archivador, ni crear ningún evento. Eso pertenece a la Decisión 2.

## 11 · Lo que NO cambia ahora

`politica-orquestador.toml` · `AUTO` (las cuatro de observación) · `REVIEW` (vacío en política) ·
`TODO_LO_DELEGABLE` · `_MATERIA_RESERVADA` (10 entradas) · `REVIEW_HABILITADO` (`False`) ·
`_EJECUTORES` (exit 127) · el ciclo autónomo · Ollama · `archivador_cloud.py` · `estado.json` ·
`eventos.jsonl` · la Bible · los ADR · el roadmap.

## 12 · Criterio de aceptación de la decisión

Si se aprueba, la fuente estaría correctamente implementada cuando se demuestre que: identifica los
capítulos, ADR y actas que cumplen las cuatro precondiciones; **rechaza `adr/plantilla-adr.md`** por
`proposed`; **rechaza el `CHECKPOINT`** por no declarar estado terminal; nunca produce
`OPORTUNIDAD_REAL`; no escribe absolutamente nada —comprobado sobre el árbol sintáctico—; no importa
red, git ni el archivador; y su mutación no deja supervivientes. Más la suite del control-plane sin
regresiones y ruff limpio.

## 13 · Retorno sobre Tokens

Ahorra el trabajo recurrente de decidir a mano qué archivar en cada sesión, y —más importante— evita
el coste mucho mayor de un archivo lleno de borradores indistinguibles de decisiones. Reutiliza tres
piezas ya construidas y probadas: el archivador, el patrón de fuente lectora de `DR-A` y el
frontmatter que la Bible ya mantiene. **No añade infraestructura nueva.**

## 14 · Qué tendría que demostrarse para cambiar esta decisión

Que existe una señal objetiva de madurez **que no dependa de una declaración humana** y que no exija
ejecución. Hoy no se ha encontrado ninguna: las tres candidatas evaluadas —commit, antigüedad,
ubicación— fallan por inferencia o por requerir git.

---

## 15 · Texto final de decisión para el CEO

> **¿Adopta AURA el frontmatter ya existente en el repositorio —`estado: "Aprobado"` en los capítulos,
> `estado: accepted` en los ADR, `estado: "Vinculante"` en las actas, en todos los casos junto a su
> `version`— como definición única y suficiente de `LISTO_PARA_ARCHIVO`, y autoriza una octava fuente
> de descubrimiento, exclusivamente lectora, sin escritura, sin red, sin git, sin Drive y con salida
> máxima `DECISION_REQUIRED`, que identifique los candidatos que cumplen esas condiciones?**
>
> **APROBAR** · **NO APROBAR**

Aprobar **no** autoriza archivar automáticamente: eso es la Decisión 2, separada a propósito.
