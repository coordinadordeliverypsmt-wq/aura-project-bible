---
documento: "Modelo de activacion — invariantes definitivos (conjunto congelado)"
fecha: 2026-07-27
autor: "CTO"
encargo: "CEO — consolidar las decisiones de dominio de la discusion y fijar el conjunto minimo, mutuamente independiente y suficiente de invariantes"
estado: "CONGELADO. INV-1..INV-11 es el UNICO conjunto vigente. Sustituye a I-A1..I-A5, I-AC1/I-AC2 e I1..I7."
base: "main @ cf050be (origin/main sincronizada) — Quality Gate PASS (362 passed / 3 skipped)"
---

# Modelo de activacion — invariantes definitivos

Cierra el modelo de activacion. A partir de aqui los invariantes **dejan de estar abiertos a
refinamiento**: solo podran modificarse si durante la implementacion de capacidades reales aparece
**evidencia objetiva** de que alguno es insuficiente o contradictorio (§5).

## 0. Sustitucion de conjuntos anteriores

Este documento es la **fuente unica** de los invariantes del modelo de activacion (D41). Sustituye a:

| Conjunto anterior | Donde vivia | Destino |
|---|---|---|
| **I-A1…I-A5** | `revisiones/2026-07-27-architecture-review-modelo-activacion-capacidades.md` §9 | Absorbidos en INV-1…INV-5 y INV-7 |
| **I-AC1 / I-AC2** | Contrato de `ActivationContext` (`capacidades.py`) | I-AC1 absorbido en INV-2; **I-AC2 eliminado** (§4) |
| **I1…I7** | `milestones/m3-entry/C1-diseno-capability-registry-manager.md` §5 | Absorbidos en INV-1 y INV-8…INV-11 |

Aquellos documentos se conservan como **registro historico**; su contenido normativo queda **derogado**
por este. Ante cualquier discrepancia, **prevalece INV-1…INV-11**.

## 1. Decisiones de dominio adoptadas (CEO, 2026-07-27)

1. **Las acciones pertenecen a la implementacion, no al contrato de la capacidad.** Una capacidad
   expresa **que** puede hacer AURA desde el dominio; un adaptador expresa **como** se materializa sobre
   una tecnologia concreta. Descarta las alternativas A, C, D y E del analisis de propiedad.
2. **B y F conviven** con responsabilidades disjuntas: **B** responde *quien materializa* una capacidad;
   **F** responde *de que depende* una capacidad. La relacion capacidad↔acciones queda **derivada, no
   declarada**, eliminando por construccion una fuente de inconsistencias.
3. **El soporte del entorno se considera estable durante una sesion de ejecucion.** No se adopta un
   modelo reactivo de reconfiguracion en caliente.
4. **La composicion es el locus del consumo del plan** —no por simplicidad, sino por ser la unica opcion
   que mantiene el flujo **unidireccional**: `Detectores → ActivationContextBuilder → ActivationContext →
   CapabilityManager → PlanActivacion → Composicion → Sistema`.

## 2. Invariantes (conjunto congelado)

### Fronteras de responsabilidad (estructura)

**INV-1 · Manager puro.** El `CapabilityManager` es una funcion pura de decision:
`planificar(contexto) → plan`, sin efectos, sin estado retenido, sin conocer tecnologia ni la maquinaria
de deteccion.

**INV-2 · El contexto es el unico contrato de entrada, inmutable y en lenguaje de dominio.** El Manager
recibe **exclusivamente** un `ActivationContext`, inmutable tras su construccion, que contiene **solo**
metricas verificadas y **nombres de capacidades declaradas en el Registry**. Prohibido cualquier
identificador ajeno al dominio: tecnologias, productos, servicios, protocolos, dispositivos por marca o
sistema operativo.

**INV-3 · Detectores por ambito, sin invasion.** El detector de hardware produce **solo** metricas
verificadas (D44); los detectores de entorno producen **solo** hechos de dominio sobre capacidades
soportadas. Toda la tecnologia concreta queda encapsulada dentro de ellos.

**INV-4 · El Builder ensambla, no decide.** El `ActivationContextBuilder` unicamente ejecuta detectores,
normaliza estructuralmente y construye el contexto. No aplica reglas, no decide estados, no conoce
Registry ni Manager. Aisla el fallo de un detector y **registra** el incidente.

**INV-5 · Registry declarativo y fuente unica de la declaracion.** Las capacidades son declaraciones
**pasivas y serializables**; **el Registry es la fuente unica de la declaracion de capacidades**,
reemplazable por cualquier Loader. Toda la inteligencia de decision vive en el Manager, nunca en la
declaracion.

**INV-6 · Separacion entre el modelo de capacidades y sus realizaciones.** La capacidad expresa **que**
puede hacer AURA en terminos de dominio y **no enumera acciones ni implementaciones**. La relacion entre
una capacidad del dominio y sus **realizaciones tecnologicas pertenece a la infraestructura** y permanece
**fuera del modelo de capacidades**. Las dependencias declaradas relacionan **capacidades entre si**,
nunca capacidades con implementaciones.

**INV-7 · Punto unico de interpretacion del plan.** El `PlanActivacion` se interpreta en **un unico punto
del sistema** y **nunca se reinterpreta posteriormente**. **Materializacion** (que existe en el sistema) y
**autorizacion** (que puede ejecutarse) son responsabilidades **separadas**: la ejecucion **nunca consulta
el plan**; se gobierna exclusivamente por permisos, HITL y kill switch.

### Semantica de la decision (comportamiento del plan)

**INV-8 · La autonomia nunca escala con la capacidad efectiva.** El nivel de autonomia efectivo jamas
supera el declarado ni aumenta por disponer de mas recursos, y queda siempre subordinado al gate HITL:
una accion de lista roja exige confirmacion humana en cualquier perfil.

**INV-9 · Una capacidad prevista no se enciende.** **Aunque existan las condiciones para activarla**, una
capacidad sin implementacion permanece latente: no se finge capacidad no construida.

**INV-10 · Una capacidad no opera si sus dependencias no operan.** En cascada, hasta punto fijo.

**INV-11 · Promocion y degradacion son reversibles y sin perdida.** Degradar conserva memoria,
configuracion, historial y compatibilidad, y el camino inverso es recorrible.

## 3. Decisiones de ciclo de vida vigentes — **no son invariantes**

Describen **esta version** del sistema, no propiedades universales del modelo. Si algun dia existiera
reconfiguracion dinamica, **INV-1…INV-11 seguirian siendo validos** y estas tres podrian cambiar.

- **CV-1** — **En esta version del sistema, el punto unico de interpretacion del `PlanActivacion` es la
  composicion.**
- **CV-2** — El contexto se evalua **una vez por sesion**, en el arranque.
- **CV-3** — Cualquier cambio del entorno se refleja en la **siguiente inicializacion**; no hay
  reconfiguracion en caliente.

## 4. Consolidacion: que se fusiono y que se elimino (trazabilidad)

| Enunciado anterior | Destino | Justificacion |
|---|---|---|
| **I3** determinismo | Fusionado en **INV-1** | Una funcion pura de su entrada **es** determinista: no aporta contenido independiente. |
| **I5** Manager agnostico | Fusionado en **INV-1 + INV-5** | Se **deduce** de la pureza sobre declaraciones pasivas. |
| **I2** degradacion sin perdida · **I7** simetria | Fusionados en **INV-11** | Dos caras de la misma propiedad: reversibilidad sin perdida. |
| **I-AC1** solo nombres de capacidades | Absorbido en **INV-2** | Mismo contenido que "el contexto no contiene tecnologia": un solo enunciado. |
| **I-AC2** no enriquecer sin concepto de dominio | **ELIMINADO** | Caso particular de una regla ya vigente (*no se introducen conceptos, tipos, capas ni abstracciones sin evidencia objetiva de insuficiencia*). Como invariante propio **ya no aporta informacion**. |

**Balance:** de 14 enunciados a **11**, sin perder ninguna restriccion. Los once son **mutuamente
independientes** (ninguno se deduce de los demas) y **suficientes**: cubren quien detecta (INV-3), quien
ensambla el contexto (INV-4), que entra al Manager (INV-2), como decide (INV-1, INV-8…INV-11), sobre que
declaraciones (INV-5, INV-6) y donde surte efecto (INV-7).

## 5. Regimen de cambio

El modelo queda **congelado**. Los invariantes **solo** podran modificarse si durante la implementacion de
capacidades reales aparece **evidencia objetiva** de que alguno es **insuficiente o contradictorio**. En
tal caso: **detenerse, presentar la evidencia y esperar decision explicita del CEO**. Ninguna decision de
diseno por iniciativa propia. Reabrir el debate **sin evidencia** no es admisible.

Las decisiones de ciclo de vida (§3) **si** pueden revisarse sin tocar los invariantes, por ser propias de
esta version.

## 6. Pendientes explicitos (no cerrados por este documento)

1. **Contrato de adaptador (Bible 6.1):** la direccion B esta adoptada, pero **modificar el contrato para
   que un adaptador declare que capacidad materializa sigue siendo una decision de implementacion no
   tomada**. INV-6 esta formulado para no anticiparla; cuando ocurra, se **especializara** sin contradecirlo.
2. **Campos 3, 4, 5 y 6 de Home Assistant:** deteccion, comportamiento degradado y criterios de promocion
   y degradacion siguen sin decidir (informe de evaluacion de HA, documento de trabajo).
3. **Coherencia documental menor:** el docstring de `ActivationContext` (`capacidades.py`) aun cita
   I-AC1/I-AC2, y los dos documentos derogados en §0 conservan sus conjuntos. Alinearlos es **tarea de
   higiene**, no trabajo funcional; se hara cuando el CEO lo autorice.
4. **`DetectorPerfil`:** duplicado conceptual sin usos, pendiente de retirada en la misma tarea de higiene.

## 7. Siguiente paso

Validar el modelo **implementando capacidades sobre el**, no perfeccionandolo mas. **Home Assistant** sera
la **primera capacidad de validacion**: ejercita el mecanismo de activacion por **soporte del entorno**
sin introducir simultaneamente nuevas incertidumbres de autonomia ni de seguridad —sus campos 9 y 10 ya
estan respaldados por ADR-0003/D4 y Bible 5.3—.
