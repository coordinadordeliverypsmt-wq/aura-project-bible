# Informe de decisión — `DECISION-CEO-INVERSION`

**Fecha:** 2026-08-17 · **Para:** CEO · **Prepara:** APUS-5 (asistencia externa)
**Naturaleza:** informe de decisión. **No es un Decision Package.** No propone, no recomienda y no
crea alternativas.

> **Qué es y qué no es este documento.**
>
> - **No hay recomendación.** El encargo del CEO fue explícito: *«NO recomendar una alternativa por
>   cuenta propia»*. No la hay en ninguna sección.
> - **No hay alternativas nuevas.** Las seis son literalmente las de
>   `revisiones/2026-08-02-revision-estrategica-roadmap.md §6`, incluida la descartada.
> - **No se ha modificado ningún DP**, no se ha escrito código y no se ha lanzado ningún agente.
> - **Se han verificado hechos que cambiaron desde el 2026-08-02.** La revisión tiene quince días;
>   decidir sobre datos caducados sería el mismo error que este proyecto lleva diez veces pagando.
>   Van marcados y separados en §4.

**Clasificación D47:** `[EJEC]` medido ejecutando · `[LECT]` leído · `[INFER]` deducido · `[HIPO]` no verificado.

---

## 1 · Por qué esta decisión bloquea el producto

`[LECT]` `CHECKLIST-CONTINUIDAD.md §5.2` declara **no autorizado** *«Iniciar cualquier incremento
nuevo sin decisión posterior a la revisión estratégica»*. `§3` registra que **«Siguiente inversión del
proyecto tras la revisión estratégica»**, pendiente **desde el 2026-08-02**, bloquea *«Todo trabajo de
construcción nuevo»*.

`[EJEC]` Busqué un acta posterior que lo levantara: `decisiones/` no contiene nada posterior al
2026-07-28, y la revisión estratégica termina en **§6 Alternativas** y **§7 Preguntas que solo el CEO
puede responder**. **La decisión nunca se tomó.**

Consecuencia medida: la Línea A (producto) solo puede verificar y corregir lo ya existente. **Quince
días de bloqueo de construcción, y la causa no es técnica ni de cuota.**

---

## 2 · Las seis alternativas

Las filas de la tabla son **literales** de `§6`. El desarrollo de cada una añade únicamente lo que
otras fuentes de verdad ya dicen; donde no hay fuente, se declara.

### A · Hardware / entorno de inferencia

| | |
|---|---|
| **Desbloquea** (literal §6) | **55% del peso** de la métrica |
| **Contrapartida** (literal §6) | Dinero; presupuesto hoy cero |
| **Evidencia** (literal §6) | §1.2, §2, §5 |

**Qué problema resuelve.** `[EJEC §1.2]` El motor de inferencia existe y **no es viable en esta
máquina**: prompt «Hola» de 8 tokens → **25,8 s**, *21× por encima* del límite HC-1 de 1200 ms; prompt
real de AURA (543 tokens) → **no completa**, error 500 tras 3 min. La revisión lo formula sin
ambigüedad: *«La restricción no es el modelo, es la máquina»*. Por eso AURA arranca por defecto con
`MockProvider`, **un clasificador de 5 reglas de palabras clave**.

**Dependencias.** `[LECT]` **D34 — presupuesto de hardware cero**, que es la pregunta §7.1 (*«¿Sigue
vigente?»*). Y `[LECT]` **P1 — escenario de despliegue**, pendiente desde el 2026-07-21, del que
dependen **3 de las 5 fases de M3** (§7.2).

**Riesgo que introduce.** Coste monetario. Y D34 prohíbe **fabricar entornos para aprobar hitos**: la
frontera entre «invertir en hardware» y «fabricar un entorno» es una línea que solo el CEO puede
trazar.

**Trabajo que ya existe.** `[EJEC]` Ollama instalado con **2 modelos íntegros** verificados contra el
manifiesto (`qwen2.5:3b`, `qwen2.5:0.5b`). `[EJEC]` El **instrumento A/B está construido y congelado
por SHA** (152 pruebas, Quality Gate PASS). `[EJEC]` `EXP-REPRO` ejecutado: 2 inferencias reales,
respuestas idénticas byte a byte. **Existe con qué medir el efecto de A antes y después.**

**Trabajo nuevo que requeriría.** **No es determinable sin conocer el hardware objetivo**, que es P1.
No lo estimo: sería inventarlo.

**Impacto sobre AURORA como producto.** Es la única alternativa que ataca la causa por la que el turno
conversacional real no funciona.

**Impacto sobre la autonomía.** `[LECT]` `PLAN-DE-FORMACION-AURORA.md` clasifica **014 (formular
cambios de código), 015 (interpretar una necesidad) y 016 (proponer backlog)** como bloqueadas, y
declara que *«014, 015 y 016 son la misma limitación vista desde tres ángulos»*, con **014 bloqueada
por hardware**. **A es la única de las seis que toca esa limitación.**

---

### B · Fase de integración

| | |
|---|---|
| **Desbloquea** (literal §6) | Repara interferencia **ya contraída** |
| **Contrapartida** (literal §6) | No mueve las dimensiones pesadas |
| **Evidencia** (literal §6) | §3.2 |

**Qué problema resuelve.** `[EJEC §3.2]` El front-end conversacional son **47 patrones literales en 8
grupos**, en cascada, *«el árbitro es el orden en que se escribió el código»*. Interferencia medida de
extremo a extremo:

| El usuario dice | AURA responde | Diagnóstico |
|---|---|---|
| «Mis reglas de casa son otras» | lista las automatizaciones | falso positivo |
| «Olvida lo que ha pasado» | «No he encontrado eso para olvidarlo» | superficie equivocada |
| «Olvida esa automatización» | «No he encontrado eso para olvidarlo» | la regla sigue activa |
| «Elimina la automatización de copias» | pasa al LLM, sin efecto | hueco sin cubrir |

`[INFER §3.2]` *«El coste es cuadrático: cada superficie nueva puede colisionar con todas las
anteriores.»*

**Dependencias.** `[LECT]` **La fase de integración NO está abierta.** `CHECKLIST §3` lo registra como
decidido y vigente: *«Agotar las capacidades construibles es condición necesaria, no suficiente; el
cambio de fase es decisión **explícita** del CEO»*. `§5.1` la declara **no autorizada**. **B exige
levantar esa decisión, no solo elegirla.**

**Riesgo que introduce.** El de §6: no mueve las dimensiones pesadas de la métrica.

**Trabajo que ya existe.** `[LECT]` `CHECKPOINT §8` registra **«Incremento B (Experiencia
Conversacional v1, DP escrito)»** como **diferido por el CEO — no abrir sin acta**. `[EJEC]` Y existen
commits de esa línea: `e552746 feat(conversacion): Conversacion General v1 -secuencia de intenciones-`
más cuatro correcciones posteriores de dos auditorías independientes (`8a52dd1`, `fee4e52`, `51b19d8`,
`4ab4c8a`). **Hay DP escrito y hay código construido.**

**Trabajo nuevo que requeriría.** No determinable desde las fuentes sin abrir el DP diferido, cosa que
este informe no hace.

**Impacto sobre AURORA como producto.** Corrige fallos que el usuario **ya sufre** en las cuatro
frases medidas arriba.

**Impacto sobre la autonomía.** `[INFER]` Indirecto: reduce el coste cuadrático de añadir superficies,
pero no toca ninguna capacidad de la tabla 🔴.

---

### C · Ampliar el núcleo determinista

| | |
|---|---|
| **Desbloquea** (literal §6) | Único camino que **hoy** cumple HC-1 (1,9–6,0 ms) |
| **Contrapartida** (literal §6) | Construye un sistema de reglas, no una IA; agrava §3.2 |
| **Evidencia** (literal §6) | §1.1, §3.2 |

**Qué problema resuelve.** Entrega un turno que responde **dentro del límite de latencia** sin depender
del LLM inviable de §1.2.

**Dependencias.** `[LECT]` La pregunta **§7.3**, que la revisión dirige al CEO en estos términos:
*«¿Es aceptable que AURA sea útil sin LLM (camino C), o contradice la visión PIOS de forma
inadmisible?»* **Es una pregunta de visión, no técnica.**

**Riesgo que introduce.** El literal de §6 —*«construye un sistema de reglas, no una IA»*— y, medido:
**agrava §3.2**, el crecimiento cuadrático de colisiones que la alternativa B pretende reparar. `[INFER]`
**C y B tiran en direcciones opuestas** sobre la misma superficie.

**Trabajo que ya existe.** `[EJEC]` Los 47 patrones, el `MockProvider` de 5 reglas y las heurísticas
deterministas del benchmark A/B.

**Trabajo nuevo que requeriría.** No determinable sin fijar qué capacidades entrarían en el núcleo —
y eso roza D23 (**alcance del MVP cerrado**, ampliarlo exige acta).

**Impacto sobre AURORA como producto.** Es la única que hoy produce un producto usable **en este
hardware**.

**Impacto sobre la autonomía.** `[LECT]` Ninguno sobre 014/015/016: el `PLAN-DE-FORMACION` las clasifica
como bloqueadas por **hardware y formulación**, no por falta de reglas.

---

### D · ~~Modelo dimensionado al hardware~~ — **DESCARTADA POR EVIDENCIA**

| | |
|---|---|
| **Desbloquea** (literal §6) | — |
| **Contrapartida** (literal §6) | **DESCARTADA POR EVIDENCIA**: el 0.5b ya está descargado y tampoco completa un turno |
| **Evidencia** (literal §6) | §1.2 |

Se reproduce **porque aparece en la fuente de verdad**. `[EJEC]` La evidencia que la descartó sigue en
pie y se ha reforzado: `EXP-REPRO` (2026-08-17) ejecutó dos inferencias reales con `qwen2.5:0.5b` y el
veredicto de clasificación fue **`NO_VIABLE` en ambas** — la acción propuesta quedó fuera de catálogo.
**No es elegible.**

---

### E · Consolidación (cerrar deuda)

| | |
|---|---|
| **Desbloquea** (literal §6) | Elimina el riesgo del artefacto temporal, las colisiones y el hogar que miente |
| **Contrapartida** (literal §6) | Cero valor nuevo visible |
| **Evidencia** (literal §6) | §3.2, §3.3, §4.2 |

**⚠ Uno de sus tres motivos ya no existe.** `[EJEC 2026-08-17]` El **artefacto temporal** (§4.2: los
470 MB de N2 eran enlaces simbólicos al directorio temporal de un job de Claude Code) **fue mitigado**
en el commit `3e716d4`, cuyo mensaje lo declara y cuya verificación confirma: `~/.aura/models/` es hoy
un **directorio real**, no un enlace. **El CEO debe saberlo antes de decidir: E vale hoy menos que el
2026-08-02.**

**Qué problema resuelve, de lo que queda.** `[EJEC §3.3]` **El hogar que miente**: con Home Assistant
ausente, AURA responde *«Enciendo la lámpara. [accion encender_dispositivo ejecutada]»* **sin que se
encienda nada** — la garantía de ALERTA-005 verifica que *el adaptador respondió*, no que *el mundo
cambió*. Es el **cuarto caso** del patrón `declarado ≠ real`. Más `[EJEC §3.4]`: **~430 LOC** de
producción correspondientes a **6 ADRs aceptados** que **nunca se ejecutan** en una sesión real.

**Dependencias.** `[LECT]` Parte de la deuda **no puede cerrarse sin D-M-8**: `DEUDA-N1-RECUPERADOR`
registra **`D-M-7` y `D-M-2` como CRÍTICAS**, y `DP-D-M-8 §10` declara que *«no decide D-M-7 ni D-M-2,
que se retomarán sobre esta arquitectura»*. **E depende parcialmente de la decisión sobre D-M-8** (§3).

**Riesgo que introduce.** El literal: cero valor nuevo visible.

**Trabajo que ya existe.** `[LECT]` Cinco documentos de deuda inventariada: `DEUDA-N2-MEMORIA-SEMANTICA`,
`DEUDA-AUTOMATIZACION` (8 partidas), `DEUDA-CAPTURA-DE-SENALES`, `DEUDA-ADAPTADORES-SIMULADOS`
(`D-ADP-1`) y `DEUDA-N1-RECUPERADOR` (7 partidas). **El diagnóstico está hecho; falta ejecutarlo.**

**Trabajo nuevo que requeriría.** Acotable partida por partida desde esos documentos; no lo cuantifico
porque ninguna fuente lo cuantifica.

**Impacto sobre AURORA como producto.** `[INFER]` Retira afirmaciones falsas de la interfaz. No añade
capacidad.

**Impacto sobre la autonomía.** `[INFER]` Reduce la superficie de `declarado ≠ real`, que es el patrón
que ha invalidado diez veces el juicio del proyecto — incluido el de la propia AURORA cuando se audita
a sí misma (capacidad 004).

---

### F · Uso real sostenido

| | |
|---|---|
| **Desbloquea** (literal §6) | Única vía de generar materia prima para la capacidad 8 |
| **Contrapartida** (literal §6) | Usar AURA hoy es penoso: consola, sin voz, sin LLM viable |
| **Evidencia** (literal §6) | §1.3 |

**Qué problema resuelve.** `[EJEC §1.3]` **Nadie ha usado AURA**: el audit log de producción contiene
**8 entradas, todas de arranque**. Sin memoria persistida, sin reglas, sin backups. `[INFER]` *«Ninguna
decisión de producto puede apoyarse hoy en telemetría de uso real, y la capacidad 8 (aprendizaje)
carece de materia prima.»*

**⚠ Su contrapartida ha cambiado en parte.** `[EJEC 2026-08-17]` Desde la revisión, AURORA obtuvo
**proceso propio** (`--servir`), **superficie de gobierno** (`--gobierno`, `~/.aura/CENTRO-DE-GOBIERNO.md`)
y **buzón de decisiones diferidas** (`975e465`, acta del CEO 2026-08-10, cableado en `__main__.py:28`,
34 pruebas). **«Consola» ya no describe del todo la experiencia.** Lo que **no** ha cambiado: sigue
**sin voz** y **sin LLM viable**.

**Dependencias.** `[INFER §6, literal]` *«**A y F están acopladas:** no habrá uso real sostenido
mientras el turno no sea usable, y no lo será sin resolver A. Ninguna de las otras rompe ese lazo.»*
**Es la fuente quien lo afirma, no este informe.**

**Riesgo que introduce.** `[INFER]` Uso real sobre un sistema con ALERTA-006 abierta significa **datos
reales del usuario** expuestos a las rutas de borrado descritas en §3. La contención está puesta; la
ruta estructural no.

**Trabajo que ya existe.** El proceso propio, el panel y el buzón citados arriba.

**Trabajo nuevo que requeriría.** No determinable: depende de qué se considere «uso sostenido», que no
está definido en ninguna fuente.

**Impacto sobre AURORA como producto.** Es la única alternativa que produce **evidencia de uso real**,
que es la materia prima que el propio protocolo exige (*«El desarrollo lo guía la evidencia del uso
real, no las ideas»*, CEO 2026-08-04).

**Impacto sobre la autonomía.** `[LECT]` Directo y explícito: la **capacidad 8 (aprendizaje)** carece
de materia prima, y `PLAN-DE-FORMACION` condiciona toda incorporación a *«evidencia repetida del uso
real»*. **Sin F, el Plan de Formación no puede avanzar por su propia regla de admisión.**

---

## 3 · `DP-D-M-8 — Motor Único de Mutaciones`, tratado por separado

**No es una alternativa de §6.** Es una decisión independiente que el CEO puede tomar **además de**
cualquiera de las seis, o **en lugar de** ninguna.

### 3.1 · Por qué existe

`[LECT]` Encargo del CEO del **2026-08-03**: definir el contrato del Motor Único, el flujo obligatorio
de toda mutación persistente, su integración con Kill Switch / PermissionManager / HITL, auditoría,
reversibilidad, garantías del Quality Gate y plan de migración. **Peso declarado por el CEO:** *«de él
dependerán todas las garantías futuras de AURORA»*.

`[LECT]` El diagnóstico del DP es preciso y **no acusa de ausencia**: *«El motor ya existe y su
contrato es correcto (…). El defecto no es la ausencia del motor: es su alcance»* — está acoplado a
`RegistroAdaptadores`, y las mutaciones del **estado propio de AURA** (memoria, modelo del usuario,
reglas) no tienen adaptador, *«así que quedaron fuera por construcción, no por decisión»*.

### 3.2 · Qué implica ALERTA-006

`[LECT]` **Abierta, prioridad máxima.** Viola ALERTA-005, ADR-0003, Bible 5.3 §5 / RN-3 (kill switch)
e INV-9. Su resumen en una línea:

> **Con la parada de emergencia armada, AURA sigue destruyendo datos del usuario** `[EJEC]`.

`[LECT]` De las **7 ramas del turno, solo 1 pasa por el motor**. Las ramas 1 (soberanía: borra/refuta
el modelo persistido), 4 y 5 (escriben `reglas.jsonl`) mutan **sin motor, sin permisos y sin kill
switch**.

`[EJEC]` El caso reproducido, textual del documento:

```
frase   : «Se me olvida siempre tomar la pastilla.»   ← no pide olvidar nada
antes   : ['tiene alergia a la penicilina', 'suele pagar las facturas por la app']
después : ['suele pagar las facturas por la app']
fichero : 0 líneas → la entrada DESAPARECIÓ del disco
```

**Una frase mundana sobre medicación destruyó un dato clínico declarado.** Y `olvidar` **reescribe el
JSONL completo**: no es append-only, no hay lápida, `backup()` existe pero **nadie lo llama** en
producción, y el registro forense **no permite reconstruir lo borrado**.

### 3.3 · Qué está ya implementado — verificado, no leído

`[EJEC 2026-08-17]` **La Fase F1 (contención) está en el código.**

| Verificación | Resultado |
|---|---|
| Guarda de dominio en el disparador de olvido | `orchestrator.py:153` — el comentario cita literalmente el caso *«Se me olvida siempre tomar la pastilla»* |
| `_foco` que no destruye ante duda | `orchestrator.py:221` — *«un referente ambiguo ya no destruye nada»* |
| Mutación | `[LECT]` `CHECKLIST`: **5/5 mutantes detectados** |

### 3.4 · Qué falta — verificado

`[EJEC 2026-08-17]` **El bypass estructural sigue en pie.** `orchestrator.py:1011` llama
`self.modelo_usuario.borrar(...)` y `:1022` llama `self.modelo_usuario.refutar(...)` **directamente**;
`self.motor.ejecutar(...)` solo aparece en `:958` y `:1338`, que son otras rutas.

`[LECT]` Pendientes las fases **F0** (escribir G-1…G-7 en rojo), **F2** (kill switch universal como
paso 0 del motor), **F3** (ejecutor interno `simular`/`aplicar`), **F4** (migrar rutas: soberanía →
reglas → señales), **F5** (reversibilidad: lápidas, retirar la reescritura) y **F6** (limpieza:
corregir `test_modelo_usuario_flujo.py`, *que hoy fija el bypass*).

`[LECT]` **Deuda que la migración debe absorber:** `ModeloUsuario.corregir` está **construido y no
cableado** `[EJEC]`, y `CentroNotificaciones.cerrar_sesion` —de la que depende ALERTA-002— **tampoco
tiene llamador**. El DP advierte: *«Migrar sin cablearlas repetiría el patrón que originó todo esto»*.

### 3.5 · Qué riesgo existe si se posterga

1. **El kill switch declarado no protege lo que dice proteger.** Es una garantía publicada que no se
   cumple: INV-9 exactamente.
2. **La destrucción sigue siendo irreversible.** La contención reduce la probabilidad del disparo; **no
   añade lápidas, ni backup, ni reconstrucción forense**. Si se dispara, el dato no vuelve.
3. **`D-M-7` y `D-M-2`, ambas CRÍTICAS, quedan congeladas**: `DP-D-M-8 §10` las remite a esta
   arquitectura.
4. `[INFER]` **Interacción con la alternativa F.** Uso real sostenido significa datos reales del
   usuario circulando por rutas que aún no pasan por el motor.
5. `[LECT]` **El propio DP señala una salida parcial**, y se cita sin recomendarla: *«**F1 podría
   adelantarse** si el CEO quiere detener la destrucción de datos antes de aprobar el resto»*. **F1 ya
   está hecha** (§3.3), de modo que esa puerta ya se usó.

---

## 4 · HECHOS VERIFICADOS · vs · DECISIONES PENDIENTES

### 4.1 · HECHOS VERIFICADOS en esta pasada `[EJEC 2026-08-17]`

| # | Hecho | Cómo se verificó |
|---|---|---|
| H1 | No existe acta posterior que levante el bloqueo de construcción | `decisiones/` sin nada tras 2026-07-28; la revisión acaba en §6/§7 |
| H2 | La contención F1 de ALERTA-006 **está implementada** | `orchestrator.py:153`, `:221` |
| H3 | El bypass estructural de ALERTA-006 **sigue abierto** | `orchestrator.py:1011`, `:1022` llaman directo, no vía motor |
| H4 | El artefacto temporal de N2 (§4.2) **ya fue mitigado** | `3e716d4`; `~/.aura/models/` es directorio real |
| H5 | AURORA tiene proceso propio, panel y buzón de decisiones | `975e465`, `2ae2416`; 34 pruebas |
| H6 | La alternativa D sigue descartada, con evidencia nueva | `EXP-REPRO`: `NO_VIABLE` en las 2 inferencias |
| H7 | Disco: **8,2 GB libres, 85% usado** | una lectura de `df`; coincide con los 8,5 GB de §5 |

**Nota de honestidad sobre §5.** El resto de las restricciones de hardware (CPU, RAM, USB, swap) son
`[LECT]` **del 2026-08-02** y **no se han vuelto a medir** en esta pasada: el CEO prohibió la
vigilancia de RAM. Si la decisión se apoya en esas cifras, **deben re-medirse con
`entorno/scripts/preflight-check.sh` antes de decidir.**

### 4.2 · DECISIONES PENDIENTES — ninguna la resuelve este informe

| Id | Decisión | Desde | Qué bloquea |
|---|---|---|---|
| **DECISION-CEO-INVERSION** | Elegir entre A/B/C/E/F | 2026-08-02 | **Todo trabajo de construcción nuevo** |
| **P1** | Escenario de despliegue | 2026-07-21 | 3 de 5 fases de M3; condiciona A |
| **§7.1** | ¿Sigue vigente D34, presupuesto hardware cero? | 2026-08-02 | Determina si A es considerable |
| **§7.3** | ¿Es aceptable que AURA sea útil sin LLM? | 2026-08-02 | Determina si C es admisible |
| **Fase de integración** | Abrirla es decisión explícita | vigente | Condición previa de B |
| **DP-D-M-8** | Aprobar el Motor Único | 2026-08-03 | F2–F6; `D-M-7` y `D-M-2` |
| **D-N3** | Reducción de `n=3` | 2026-08-17 | `EXP-CAMPANA` |
| **D-CP-1/2/3** | Transporte · GREEN · identidad | 2026-08-17 | `CP-GREEN` |
| **D-ORCH-1…5** | Alcance D24 · REVIEW · AUTO · fases · CHECKLIST:235 | 2026-08-17 | `ORCH-FASE-1…5` |
| **D-FORM-1** | Reclasificar 017 y 018 | 2026-08-17 | Plan de Formación |

---

## 5 · DECISIÓN REQUERIDA DEL CEO

**Las alternativas, exactamente como aparecen en la fuente de verdad**
(`revisiones/2026-08-02-revision-estrategica-roadmap.md §6`), sin reinterpretar:

> ## 6 · Alternativas de inversión
>
> Derivadas de la evidencia. **Sin recomendación.**
>
> | | Alternativa | Desbloquea | Contrapartida | Evidencia |
> |---|---|---|---|---|
> | **A** | **Hardware / entorno de inferencia** | **55% del peso** de la métrica | Dinero; presupuesto hoy cero | §1.2, §2, §5 |
> | **B** | **Fase de integración** | Repara interferencia **ya contraída** | No mueve las dimensiones pesadas | §3.2 |
> | **C** | **Ampliar el núcleo determinista** | Único camino que **hoy** cumple HC-1 (1,9–6,0 ms) | Construye un sistema de reglas, no una IA; agrava §3.2 | §1.1, §3.2 |
> | **D** | ~~Modelo dimensionado al hardware~~ | — | **DESCARTADA POR EVIDENCIA**: el 0.5b ya está descargado y tampoco completa un turno | §1.2 |
> | **E** | **Consolidación** (cerrar deuda) | Elimina el riesgo del artefacto temporal, las colisiones y el hogar que miente | Cero valor nuevo visible | §3.2, §3.3, §4.2 |
> | **F** | **Uso real sostenido** | Única vía de generar materia prima para la capacidad 8 | Usar AURA hoy es penoso: consola, sin voz, sin LLM viable | §1.3 |
>
> `[INFER]` **A y F están acopladas:** no habrá uso real sostenido mientras el turno no sea usable, y no
> lo será sin resolver A. Ninguna de las otras rompe ese lazo.

**Y las preguntas que la fuente dirige al CEO** (`§7`), literales:

> 1. **¿Sigue vigente el presupuesto de hardware cero (D34)?** Determina si A es considerable, y con ella
>    el techo de ~50% en Product Readiness.
> 2. **¿Cuál es el escenario de despliegue (P1)?** Pendiente desde el 2026-07-21; bloquea 3 de 5 fases de M3.
> 3. **¿Es aceptable que AURA sea útil sin LLM** (camino C), o contradice la visión PIOS de forma inadmisible?
> 4. **¿Se corrige ya el artefacto de N2 alojado en directorio temporal?** (§4.2)

**Sobre la pregunta 4:** `[EJEC]` **ya está corregido** (H4). Queda contestada por los hechos.

### Lo que basta decir para desbloquear

Una sola frase del tipo **«la siguiente inversión es X»**, con X ∈ {A, B, C, E, F}, levanta
`CHECKLIST §5.2` para esa línea de trabajo. **Dos decisiones más son independientes** y pueden tomarse
en el mismo acto o por separado:

- **`DP-D-M-8`** — aprobar o no el Motor Único (§3). No consume la elección de inversión.
- **Abrir la fase de integración** — condición previa **añadida** si X = B.

**Este informe no elige.** No hay recomendación en ninguna de sus secciones, y esa ausencia es
deliberada: la elección entre A/B/C/E/F es de rango 1 y la fuente de verdad la dejó explícitamente
*«sin recomendación»*.
