# DECISION-PACKAGE-AUTONOMIA-RESTANTE

> **Preparado el 2026-08-25.** No implementa nada, no promueve nada, no escribe en `tareas_AUTO`.
> Evidencia clasificada segun D47: `[EJEC]` medido · `[LECT]` leido · `[INFER]` deducido.

## 1 · Estado actual

Discovery observa, clasifica y propone; el CEO promueve; `tareas_AUTO` autoriza. La cadena esta
cerrada y probada. `siguiente_auto()` = `None`: **no hay trabajo autorizado pendiente**, y quedan
dos decisiones humanas — mas una tercera que este analisis destapa.

`tareas_AUTO` 6 (completadas) · `propuestas` 3 (0 promovidas) · `trabajo_completado` 50.

## 2 · DEC-WAITING-HUECO-DE-CONTRATO

**Hecho `[EJEC]`:** el procedimiento nombra cuatro categorias; `clasificar()` implementa tres.
**No existe hoy ningun hallazgo que ejerza `WAITING`.** Los dos hallazgos reales caen en
`PROPOSAL_ONLY` y `DECISION_REQUIRED`. **No fabrico un caso para justificarlo.**

Hay un candidato *aparente* y conviene descartarlo explicitamente: `AUDITORIA-DMOCHO-F0` esta en
`WAITING_FOR_QUOTA`, que **si** es una espera por condicion externa. Pero no es un hallazgo de
Discovery: es un estado de tarea, y vive en otro vocabulario. Confundirlos seria justificar una
categoria de clasificacion con evidencia de otra cosa.

| | A — incorporar ahora | B — mantener fuera | C — eliminar del procedimiento |
|---|---|---|---|
| **Que cambia** | `clasificar()` gana una cuarta salida y una regla para decidir cuando algo «espera» | Nada en codigo; se documenta que son tres | Se borra `WAITING` de la documentacion |
| **Garantia** | Anade distinguir «no se puede aun» de «no se debe» | No anade ni quita | Elimina una promesa que nada respalda |
| **Riesgo** | **Alto y concreto:** sin caso real, la regla se inventa. Una categoria sin ejercer es una garantia sin red — y si `WAITING` acabara siendo mas permisivo que `DECISION_REQUIRED`, seria una via nueva | Persiste el desajuste documento/codigo, que es como empieza «declarado != real» | Perder vocabulario util si mañana aparece el caso; recuperarlo cuesta poco |
| **Autonomia** | Ninguna ganancia hoy: nada lo ejerceria | Sin cambio | Sin cambio |
| **Autoridad** | **Riesgo de cuarta via** si se define mal | Sin cambio | Sin cambio |
| **Pruebas** | RED que produzca un hallazgo en espera real, que no degrade a permiso, y control de que no absorbe `DECISION_REQUIRED` | Ninguna | Ninguna en codigo |

**Recomendacion tecnica (no es decision): B, y C como variante honesta.** B deja el desajuste
escrito; C lo elimina. Ambas evitan legislar sobre un caso que no existe. **A es la unica que
inventa contrato.**

## 3 · DEC-QUALITY-GATE-GLOBAL

### 3.1 · La cifra registrada era incorrecta — **son 11, no 13** `[EJEC]`

La propuesta dice *«13 tests de Linea A en rojo»*. **Medido: 11 tests rojos.** El 13 son las
**violaciones** que G-1 detecta (4 rutas de almacen + 9 escrituras a disco), no tests. Dos cosas
distintas contadas como una — el patron de siempre, esta vez en el propio backlog.

### 3.2 · Desglose por grupo `[EJEC]`

| Grupo | Rojos | Que falla | Trabajo cerrado |
|---|---|---|---|
| **G-1** | 2 | R-A: 4 operaciones de almacen fuera de modulos autorizados · R-B: 9 escrituras directas a disco | — |
| **G-2** | 3 | el kill switch armado **no detiene** olvido, refutacion ni creacion de reglas | — |
| **G-3** | 4 | mutaciones del estado propio **sin catalogar** (3 capacidades) + olvido ejecutado sin catalogo | — |
| **G-6** | 1 | el audit no registra QUE se borro: lo perdido no es reconstruible | — |
| **G-7** | 1 | el olvido destruye lineas del almacen: **no es append-only** | — |
| **G-4 · G-5** | **0** | — | **verdes: la contencion F1 ya las cerro** `[LECT]` |

**F0 esta `TECHNICALLY_COMPLETE / WAITING_FOR_INDEPENDENT_AUDIT`** `[LECT]`: no falta construccion,
falta la auditoria independiente (`AUDITORIA-DMOCHO-F0`, `WAITING_FOR_QUOTA`). Y **Linea A tiene
bloqueos propios ya registrados**: `D-G1-2`, `D-G1-3`, `C-ESPEC-F2-F3`, `D-ORCH-5`, con
`siguiente_accion_segura: "ninguna sin D-G1-2 y D-G1-3"`.

### 3.3 · Como los clasificaria el mecanismo HOY — **y por que eso es el problema** `[EJEC]`

Construi los 11 hallazgos tal y como `descubrir()` los produce y llame a `clasificar()`:

**Los 11 salen `AUTO_EXECUTABLE`.** Los cinco grupos, sin excepcion.

No es que el mecanismo falle: es que **mira el fichero equivocado**. Un hallazgo de red roja declara
`fichero` = **el fichero de la prueba** (`tests/unit/…`), y las zonas se calculan sobre el. Pero el
trabajo real esta en **`aura_skeleton/`** — zona bloqueada, corazon del producto, y ninguno de los
11 la nombra. La contencion de zonas **no ve donde esta el trabajo, solo donde esta la prueba**.

Es el mismo patron que ya corrigio la contencion de `DEF-CUERPO-LIBRE`, en otro punto: la falta de
informacion funcionando como permiso. **Promover el gate global tal cual entregaria a AURA 11 tareas
AUTO que exigen tocar `aura_skeleton/`.**

**Clasificacion honesta, corregido el sesgo:** los 11 son **`DECISION_REQUIRED`** — tocan zona
vetada, dependen de `D-G1-2`/`D-G1-3` sin resolver, y F0 espera auditoria independiente.
**`AUTO_EXECUTABLE`: 0.**

## 4 · Que podria ejecutar AURA sola tras una promocion

**Hoy, nada de Linea A.** Y no por falta de mecanismo, sino porque cada rojo exige modificar el
producto en zona bloqueada, con decisiones abiertas encima.

## 5 · Que seguira requiriendo decision humana

`D-G1-2` · `D-G1-3` · `C-ESPEC-F2-F3` · `D-ORCH-5` · `AUDITORIA-DMOCHO-F0` (la desbloquea la cuota,
no el CEO) · `D-CP-1` · `D-CP-3` · `M9` (SIN_CONTROL, sin auditor externo).

## 6 · Riesgos

- **Promover el gate global sin corregir el sesgo de zona** → 11 tareas AUTO sobre `aura_skeleton/`.
  Es el riesgo mayor de este paquete, y es **evitable**.
- **Incorporar `WAITING` sin caso real** → contrato inventado, posible cuarta via de autoridad.
- **Dejar la cifra 13 en el backlog** → se sigue decidiendo sobre un numero que no corresponde a
  ninguna medicion.

## 7 · Recomendacion final — **separada de la decision del CEO**

1. **Corregir primero el sesgo de zona** (`DEC-ZONA-POR-FICHERO-DE-TRABAJO`, abierta aqui). Es
   precondicion de cualquier promocion de Linea A, no un extra.
2. **`WAITING`: B o C.** Ninguna evidencia sostiene A.
3. **Quality-gate global: no promover, y reclasificar a `DECISION_REQUIRED`** con la cifra corregida
   a 11. Trocearlo por grupo solo tiene sentido despues del punto 1.

**Decido nada de esto.** Las tres son suyas.
