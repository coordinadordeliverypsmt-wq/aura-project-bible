---
documento: "AMP-AURA — las cinco decisiones, cerradas para firma"
tipo: "Cierre de decisiones. NADA implementado. Requiere aprobación del CEO."
fecha: 2026-09-10
checkpoint: 5ebdce4
decide: "CEO (Mauricio)"
precede: "AURA-MEMORY-PROTOCOL-PROPOSAL.md · AURA-MEMORY-PROTOCOL-COMPARISON.md"
---

# Las cinco decisiones, formuladas para aprobar o rechazar

`[LECT]` leído en el código · `[EJEC]` medido · `[INFER]` deducido · `[HIPO]` no verificado.

Cada decisión se cierra con **una pregunta binaria** y su recomendación. Nada aquí está implementado.

---

## D-AMP-1 · Alcance

| | **A · AMP-AURA completo** | **B · Etapas 1–2** | **C · No adoptar** |
|---|---|---|---|
| Cambios | 6 etapas: versión, vigencia, identidad canónica, PROPOSE, Context Builder, intercambio | `version`, `supersedes`, `valid_from`, `valid_until` + supersesión sobre la identidad **ya existente** | ninguno |
| Ficheros | `almacen_senales`, `modelo_usuario`, `orchestrator`, `conversacion`, `contracts`, nuevos módulos | `almacen_senales.py`, `modelo_usuario.py` (`ver()` expone 7 claves fijas `[LECT]`), `ejecutor_modelo_usuario.py` | — |
| Riesgo | **alto**: toca la construcción del prompt y la autoridad | **bajo**: campos nuevos en un `dict` libre que el ejecutor pasa sin filtrar `[LECT]` | nulo a corto plazo |
| Complejidad | alta | baja | — |
| Beneficio | protocolo completo para agentes futuros | **historial y vigencia reales**: hoy el dato viejo desaparece sin rastro | — |
| `D24` (local-first) | compatible | compatible | compatible |
| `ADR-0014` | lo refuerza | lo refuerza | sin cambio |
| Impacto en Core | alto | **mínimo**: no toca `_responder_hecho` ni el punto de corte | nulo |
| Impacto en `MemoryStore` | **ninguno** (`provenance: dict` es libre) | **ninguno** | ninguno |
| Rendimiento | neutro si se respeta el lookup determinista | **neutro** (`[EJEC]` 0,00 s se conserva) | neutro |
| Obsidian futuro | habilita exportación estructurada | habilita exportación con historial | sigue siendo solo una nota |
| Reversibilidad | media: hay módulos nuevos | **alta**: campos ignorables | total |

**El riesgo que domina esta decisión no es técnico, es de sobre-ingeniería:** un protocolo de seis etapas para
un sistema con un usuario y una deuda de latencia sin resolver. La investigación lo señaló y sigue en pie.

> ### PREGUNTA D-AMP-1
> **¿A, B o C?**
> **Recomiendo B.** Es el único alcance que produce valor verificable (§CASO) sin tocar autoridad, prompt ni
> contratos, y es **reversible por definición**: si no aporta, los campos se dejan de leer.

---

## D-AMP-2 · Memory Context Builder

**El problema, medido, no supuesto.** El Core **sí** impide que «Mi abuela es enfermera» se convierta en hecho
personal —`_TERCERO` la descarta `[EJEC]`—, pero el turno queda como episódico y **el modelo la repitió** `[EJEC]`.
En otra medición, ante «¿Quién fue Jesús Cristo?», el modelo respondió mezclando hechos del contexto («mi nombre era
María») `[EJEC]`.

**La causa exacta está en una línea.** `orchestrator.py:1223` `[LECT]`:

```python
ctx = " | ".join(h["content"] for h in hits) if hits else "(sin recuerdos relevantes)"
prompt = f"[contexto memoria: {ctx}]\n[conversacion reciente:\n{recent}]\nUsuario: {text}"
```

Todo lo que el `recall` devuelve entra en el prompt **sin filtro de scope, de clase ni de pertinencia**. El Core
gobierna la **escritura**; nadie gobierna la **salida hacia el modelo**.

**Qué sería el Builder:** una función **pura** —entra memoria, sale texto— situada **entre el paso 15 (`recall`) y
el 17 (construcción del prompt)**, antes de `router.route`.

| Recibe | Puede transmitir | Debe excluir |
|---|---|---|
| hits del recall, buffer, atributo preguntado, scope del turno | el **valor exacto** del hecho pertinente; evidencia **marcada como no establecida** | terceros (**siempre**), propuestas, hechos no pertinentes, memoria sensible |

**Cómo no se convierte en segunda autoridad** —y es la objeción que hay que responder—: **no decide qué es verdad, solo
qué se muestra.** No escribe, no llama al motor, no altera estados. Respeta `ADR-0014` porque el valor que transmite
es el que el Core estableció, literal. Respeta `G-1` porque no es una ruta de mutación: no toca el store.
Si alguna vez escribiera algo, deja de ser un Builder y es un bug.

> ### PREGUNTA D-AMP-2
> **¿Se autoriza diseñar e implementar el Context Builder como función pura entre `recall` y el prompt, sin
> capacidad de escritura?**
> **Recomiendo aprobarlo, pero DESPUÉS de B.** Es lo único que cierra una fuga **ya medida**, y el riesgo está
> acotado por construcción (sin escritura, función pura, verificable con mutación). Pero toca el prompt, que es la
> zona que más veces ha roto algo en esta cadena de misiones: merece su propio incremento, no ir de acompañante.

---

## D-AMP-3 · FORGET vs DELETE

**Corrección a mi propia propuesta.** Presenté `FORGET` como una novedad. No lo es del todo, y el código lo aclara:

| Verbo actual | Qué hace hoy `[LECT]` | Equivale a |
|---|---|---|
| `refutar` | marca `refutada` **persistente**, **no borra**, «conserva el rastro (ADR-0017), pero AURA deja de afirmarlo» | **INVALIDATE** — ya existe |
| `borrar` | delega en `memoria.olvidar`, que **reescribe el almacén**; catalogado `efecto: destruye`, lista **soberanía** | **DELETE** — ya existe |

Así que la decisión real no es «¿añadimos FORGET?» sino **«¿qué hacemos con el `borrar` destructivo que ya existe?»**

| Dimensión | Mantener `borrar` destructivo | Convertirlo en `FORGET` (valor fuera, tombstone) |
|---|---|---|
| Privacidad | **máxima**: el dato deja de existir | alta: el valor desaparece; queda que existió |
| Soberanía del usuario | **total** | condicionada: queda una huella |
| Auditoría | se pierde el qué, queda el cuándo/quién | **completa** |
| Seguridad | un borrado malicioso es **indetectable** | **detectable**: el tombstone lo delata |
| Recuperación | imposible | imposible (el valor se fue) |
| Cumplimiento | encaja con «derecho al olvido» | exige justificar que el tombstone no es dato personal `[HIPO]` |
| Experiencia | «lo borré y ya no está» | «lo borré; AURA recuerda que había algo» — puede resultar **peor** |
| Almacenamiento | se recupera espacio | crece monótonamente |

**No doy por bueno que FORGET sea lo correcto.** Hay un argumento fuerte en contra: si el usuario pide borrar algo
íntimo, que AURA conserve «aquí había un dato que borraste el 10-sep» **puede ser exactamente lo que no quería**.

> ### PREGUNTA D-AMP-3
> **¿Política A —coexistencia— o política B —sustituir `borrar` por `FORGET`?**
> **Recomiendo A: coexistencia, y que el usuario elija.** `refutar` (invalidar) y `borrar` (destruir) ya existen y
> significan cosas distintas; añadir `FORGET` como **tercer** verbo intermedio —valor fuera, tombstone— da la opción
> sin quitar ninguna. Y una regla dura: **el borrado destructivo no puede ser nunca el modo por defecto de una
> operación automática**; solo del usuario, con HITL, como ya está catalogado. Rechazo sustituir `borrar`: sería
> reducir la soberanía del usuario en nombre de la auditoría.

---

## D-AMP-4 · Asesores no deterministas

**Mecanismo ≠ autoridad, y la distinción es la clave de toda la propuesta.** «El Core es la única autoridad sobre
los hechos» es compatible con que el Core **consulte** mecanismos falibles, igual que un juez admite un peritaje sin
delegarle la sentencia. Lo que no es compatible es que el peritaje **sea** la sentencia.

| Amenaza | Con `PROPOSE` acotado | Sin `PROPOSE` (solo determinismo) |
|---|---|---|
| Memory poisoning | **contenido**: el LLM no tiene escritura; «una sola escritura» (`[LECT]`, 2606.04329) no existe para él | nulo |
| Prompt injection → memoria | contenido: la autoridad depende de la **fuente registrada**, no del texto | nulo |
| Propuestas falsas | **real**: ruido que alguien debe revisar | nulo |
| Contaminación de contexto | **real si las propuestas llegan al prompt** → prohibido por §13 | nulo |
| Bucles de propuesta | **real**: el asesor re-propone lo rechazado → exige `REJECTED` persistente y tope por atributo | nulo |

**El coste de NO tenerlo está medido:** primitivos deterministas al **5 %** con identificadores ofuscados y **0 % en
multilingüe** (`[LECT]`, 2606.15903). Sin asesores, AURA no reconocerá «my birthday» ni «mi fecha de nacimiento» como
el mismo atributo, y cada variante costará una fila de tabla.

> ### PREGUNTA D-AMP-4
> **¿Se admite `PROPOSE` como operación de mecanismos no deterministas, sin `COMMIT`, `SUPERSEDE` ni `REVOKE`?**
> **Recomiendo aprobarlo en principio, pero NO construirlo aún.** Es compatible con la tesis y es la respuesta al
> 0 % multilingüe, pero **no hay todavía ningún asesor ni agente que lo use**: construir el buzón antes del
> remitente es sobre-ingeniería. Condiciones para cuando llegue: `REJECTED` persistente, tope de propuestas por
> atributo, y **las propuestas nunca entran en el prompt**.

---

## D-AMP-5 · Identidad canónica y alias

| Capa | Determinista | Quién decide |
|---|---|---|
| **Identidad** `subject.attribute[@scope]` | **sí** | el Core, por construcción gramatical reconocida |
| **Alias declarados** («cumpleaños» = «fecha de nacimiento») | **sí**: tabla cerrada, auditable, versionada | **el CEO/usuario**, nunca el modelo |
| **Alias sugeridos** (paráfrasis no listada) | **no** | asesor → `PROPOSAL` → confirmación |

**Ambigüedad:** si un enunciado casa con dos identidades, el Core **no elige**: no responde por esa vía y sigue la
ruta segura existente. Es la misma asimetría que ya gobierna la frontera cognitiva: **un error deja una pregunta sin
contestar; nunca expone un hecho equivocado.**

**Dos valores contradictorios bajo la misma identidad:** supersesión si hay declaración posterior; `CONFLICTED` y
pregunta si son simultáneos de fuentes distintas. El modelo no desempata.

**El riesgo real —un alias incorrecto fusiona dos hechos distintos— es grave y asimétrico:** fusionar
`usuario.cumpleanos` con `abuela.cumpleanos` produciría una respuesta **falsa con autoridad del Core**. Por eso los
alias deben ser **declarados, nunca inferidos**, y **nunca cruzar `scope`**: un alias entre sujetos distintos se
rechaza por construcción.

> ### PREGUNTA D-AMP-5
> **¿Se aprueba la identidad canónica ahora, o solo cuando el uso real demuestre que hace falta?**
> **Recomiendo posponerla.** Hoy `_atributo_declarado` funciona `[EJEC]` y el coste de su limitación es que una
> paráfrasis no se reconoce —molesto, no peligroso—. La identidad canónica es el cambio de mayor riesgo de los cinco
> (toca la resolución que ya funciona) y el de beneficio menos urgente. **Condición para traerla:** que se observen
> paráfrasis reales fallando en uso, registradas en `PLAN-DE-FORMACION-AURORA.md`, como exige la regla del CEO de
> 2026-08-04 de que las capacidades nazcan de bloqueos observados.

---

## Etapas 1–2 · ¿Demuestran valor por sí mismas?

**Sí, y se puede comprobar sin construir nada más.** Hoy, al redeclarar, el dato viejo **simplemente deja de
aparecer**: no hay versión, ni vigencia, ni historial `[LECT]`. Tras las etapas 1–2, AURA podría responder «tu
cumpleaños es el 3 de junio» **y además** «antes me dijiste el 10 de mayo, hasta el 10 de septiembre».

Lo que cuesta: cuatro campos en la procedencia —que el ejecutor ya pasa sin filtrar `[LECT]`—, exponerlos en
`ver()` —que hoy devuelve **7 claves fijas** y habría que ampliar `[LECT]`— y la lógica de supersesión sobre la
identidad **que ya existe**. Sin `PROPOSE`, sin alias, sin Builder, sin vectores, sin Obsidian.

**Criterio de fracaso, por adelantado:** si al terminar la etapa 2 nadie consulta el historial ni la vigencia,
entonces el protocolo no era necesario y la respuesta correcta a D-AMP-1 pasa a ser **C**.

## Caso del cumpleaños · qué produciría

```
t0  «Mi cumpleaños es el 10 de mayo»
    FACT usuario.cumpleanos v1 · value="10 de mayo" · status=ACTIVE
         valid_from=t0 · recorded_at=t0 · source=declaracion_usuario

t1  «Mi cumpleaños es el 3 de junio»
    v1 → status=SUPERSEDED · valid_until=t1        (no desaparece)
    FACT usuario.cumpleanos v2 · value="3 de junio" · status=ACTIVE · supersedes=v1

consulta → devuelve SIEMPRE v2, en 0,00 s, 0 llamadas al LLM
auditoría → demuestra que v1 existió, con su vigencia y su procedencia
```

Hoy el resultado visible ya es correcto (`[EJEC]`: «Tu cumpleaños es 3 de junio»); lo que falta es **todo lo que está
a la izquierda de la flecha**. **No implementado.**

## Obsidian

**OBSIDIAN ≠ MEMORIA PERSONAL.** Se mantiene como línea futura de conocimiento/documentación, sin instalación, sin
integración y sin leer ni escribir ninguna bóveda.

Lo único que la investigación añade: **AMP-AURA podría exportar hacia Obsidian** —un hecho con su historial y
procedencia se representa bien en markdown con frontmatter, que es justo el modelo de AMP/YouTale— y **consumir desde
Obsidian sería siempre `EVIDENCE`, nunca `FACT`**. Y hay una razón medida para esa asimetría: **MemoryGraft** logra
que **documentación** aparentemente benigna se persista como experiencia válida (`[LECT]`, 2606.04329). Una bóveda es
un directorio que cualquiera puede editar: como fuente de hechos sería la superficie de envenenamiento perfecta.
**No se diseña integración en esta misión.**

## Qdrant

`qdrant-client 1.18.0` está instalado **desde el 18-jul-2026** y **ningún módulo del producto lo importa** `[EJEC]`.
**No implica ninguna decisión de arquitectura.** No se instala ni se integra nada.

**¿Haría falta un backend vectorial?** Solo en la etapa de **asesores** (D-AMP-4), y únicamente para **proponer**
equivalencias de atributo que la tabla de alias no cubra. Nunca para la recuperación básica: el caso «¿cuál es mi
cumpleaños?» se resuelve estructuralmente en 0,00 s, y sustituirlo por búsqueda vectorial sería cambiar una garantía
determinista por un umbral. AURA ya tiene además `SemanticMemory` (N2, ONNX) cableada `[LECT]`: si algún día hace
falta semántica, el primer candidato es lo que ya existe, no un servicio nuevo.

## Riesgos

| Riesgo | Mitigación |
|---|---|
| Sobre-ingeniería | B es cuatro campos; con criterio de fracaso declarado |
| Romper la resolución que funciona | B no toca `_responder_hecho` ni el punto de corte |
| El Builder concentra poder | función pura, sin escritura, incremento propio, mutación obligatoria |
| Crecimiento monótono por tombstones | decisión explícita en D-AMP-3 + política de archivado |
| Alias que fusionan hechos ajenos | alias declarados, nunca inferidos, nunca entre `scope` distintos |
| Propuestas en bucle | `REJECTED` persistente + tope por atributo |
| Que todo quede en documento | si en 3 meses no hay etapa 1, la respuesta es C |

## Recomendación final

**APROBAR ahora:** **D-AMP-1 = B** (etapas 1–2) y **D-AMP-3 = A** (coexistencia de `refutar`/`borrar`/`FORGET`, con
borrado destructivo nunca automático).

**APROBAR en principio, construir después:** **D-AMP-2** (Context Builder) como incremento propio inmediatamente
posterior a B, y **D-AMP-4** (`PROPOSE`) cuando exista un asesor que lo use.

**POSPONER:** **D-AMP-5** (identidad canónica) hasta que haya paráfrasis fallando en uso real registradas.

**RECHAZAR:** sustituir `borrar` por `FORGET`; `DELETE` como operación automática; el vector como recuperación
básica; Obsidian o cualquier documento como fuente de `FACT`.

**Siguiente misión si el CEO aprueba:** etapa 1 y 2 únicamente —`version`, `supersedes`, `valid_from`,
`valid_until`, supersesión sobre la identidad existente y el historial consultable—, con el caso del cumpleaños como
prueba de aceptación y las 24/24 re-medidas. Sin `PROPOSE`, sin alias, sin Builder, sin vectores.
