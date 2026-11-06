---
documento: "Decision Package — M3.2a · Exportar el modelo del usuario (cablear la soberanía)"
tipo: "Decision Package (PROPUESTA). NADA implementado. Requiere aprobación del CEO."
estado: "EJECUTADO Y VERIFICADO (2026-10-11). Aprobado por el CEO opción A (actas 2026-10-11-M3.2a-exportar-aprobacion.md y -confirmacion-opcion-A.md). Construido con CONFIRMACIÓN explícita: QG PASS (3254), mutación 6/6, ECC clase cerrada. La exportación NUNCA se vuelca por detección de texto — exige confirmación inequívoca por igualdad del turno (no subcadena). Sin commit."
fecha: 2026-10-11
mantenido-por: "Dirección Técnica (sesión de asistencia)"
decide: "CEO (Mauricio)"
sobre: "ROADMAP-M3-REORDENADO.md §3 paso 2 (M3.2a) · Bible 4.4 §2 / 4.1 §5 · ADR-0001 · ADR-0017"
---

# M3.2a · Exportar el modelo del usuario

**Esto NO es la obra: es su perímetro para aprobar o rechazar.** No se ha construido nada. El método
`exportar` YA existe; lo que falta es su ruta al usuario y resolver una tensión de la Bible.

`[EJEC]` medido/ejecutado · `[LECT]` leído en el código · `[INFER]` deducido.

---

## 1 · Problema, justificación y evidencia

El `ROADMAP-M3-REORDENADO.md` §3 ordena, como paso 2 (determinista, disponible sin datos reales),
**M3.2a · Soberanía del modelo del usuario**: *ver, corregir, exportar y borrar* lo que AURA cree
saber. Bible 4.4 §2 lo exige: *«El modelo del usuario es dato del usuario: local, cifrado, exportable
(4.1 §5)»*. Es la «capacidad 8» del DoD de M3.0.

**Verificación dirigida `[EJEC]` 2026-10-11 (no se duplica trabajo existente):**

| Capacidad | Implementada | **Cableada al usuario** | Evidencia |
|---|---|---|---|
| Ver | sí | **sí** | `orchestrator.py:2248` `await self.modelo_usuario.ver(uid)` → `describir_conocimiento` |
| Corregir | sí | **sí** | `orchestrator.py:2327` `refutar_entrada(uid, foco)` |
| Borrar | sí | **sí** | vía Motor Único `olvidar_informacion_usuario` (`ejecutor_modelo_usuario.py:28,349`) |
| **Exportar** | **sí** (`modelo_usuario.py:107-113`) | **NO** | `grep` de llamadores vacío: sin orden conversacional, sin capacidad de catálogo, sin CLI |

**La brecha real, por tanto, NO es construir la exportación** (su núcleo existe y es correcto: JSON con
`usuario`, `exportado_ts` y las entradas, `modelo_usuario.py:109-113`). **La brecha es que no tiene
ruta al usuario** — es el patrón «declarado ≠ real» (el mismo de la capacidad 009 del Centro de
Gobierno): la función existe, el camino que la entrega no. Tres de las cuatro capacidades de soberanía
son alcanzables; la cuarta no, así que la soberanía está incompleta.

## 2 · Objetivo funcional

Que el usuario pueda **pedir y obtener una copia de su propio modelo** (lo que AURA cree saber de él)
por una ruta real, con el mismo patrón de acceso que ya tienen ver/corregir/borrar. Criterio de
aceptación = comportamiento demostrado: el usuario emite la petición y recibe su modelo; no «el método
existe».

## 3 · Requisitos (explícitos) y la decisión que falta

**Explícitos, no negociables (de Bible/ADR vigentes):**
- **Local-first, sin terceros** (ADR-0001 / D24): la exportación ocurre en local; no sale a ninguna red.
- **Legible sin AURA** (4.1 §5, ya en el docstring de `exportar`): un formato que solo AURA sepa leer
  no es soberanía. El JSON actual cumple esto.
- **Procedencia** (4.4 §2): la exportación debe conservar la procedencia que `ver` ya expone.
- **Aislamiento por `user_id`** (4.1): se exporta solo el modelo del `user_id` que lo pide.
- **Por el patrón de soberanía existente**: si la petición es una acción gobernada, pasa por el Motor
  Único con permisos/dry-run (como `borrar`); si es una consulta de lectura, por la ruta de `ver`.
  — a confirmar en diseño (ver §5).

**CIFRADO — resuelto por el texto exacto de la Bible (no es una contradicción; revisión 2026-10-11).**
La supuesta tensión «4.4 §2 cifrado vs. 4.1 §5 legible» se disuelve al leer 4.1 §5, que **distingue
explícitamente tres propiedades**:
- **4.1 §5 L62 — «Local y cifrada»:** la memoria **almacenada** es cifrada; *«nunca sale del perímetro
  salvo respaldo cifrado»*. El cifrado aplica al **almacén en reposo** y a los **respaldos** que salen
  del perímetro (sync/backup). ADR-0001.
- **4.1 §5 L64 — «Exportación total»:** *«el usuario exporta toda su memoria en **formato neutral** — "el
  usuario es el dueño" (D1)»*. La **exportación de soberanía** se especifica como **formato neutral
  legible, NO cifrado** — coherente con el docstring actual de `exportar` («legible sin AURA», 4.1 §5).

Por tanto «cifrado» (4.4 §2) y «exportable/formato neutral» (4.1 §5 L64) son requisitos **de objetos
distintos**: el almacén y el artefacto exportado. No hay contradicción que el CEO deba dirimir. Las
alternativas, con su lectura:
  - **A — Exportación en formato neutral legible, sin cifrar el artefacto.** Es lo que 4.1 §5 L64
    especifica literalmente. El método actual ya lo cumple. **RECOMENDADA.**
  - **B — Exportación cifrada.** Exigiría clave/bóveda (Libro V 5.4) y **contradiría** «legible sin AURA»
    y «el usuario es el dueño»: un export que el usuario no puede abrir sin AURA no es soberanía. No lo
    pide la Bible para la exportación (el «respaldo cifrado» de L62 es otro caso: datos que salen como
    backup, no la copia que el usuario se lleva).
  - **C — Ambas, el usuario elige.** Válida pero añade complejidad (clave) sin requisito que la exija;
    el respaldo cifrado ya existe aparte (`memory.backup()` con checksum).

**Recomendación fundamentada: A.** No requiere decisión de cifrado del CEO; el cifrado del **almacén en
reposo** (4.1 §5 L62 / ADR-0001) es un requisito **separado** y NO es objeto de este DP (verificar su
estado es trabajo aparte). Esto no es aprobación: la recomendación es técnica.

## 4 · Alcance y exclusiones

**Dentro:** (a) una ruta de usuario para invocar `exportar` (orden conversacional reconocida y/o
comando), siguiendo el patrón de ver/corregir/borrar; (b) el cifrado según la opción que el CEO elija
en §3; (c) pruebas y evidencia de comportamiento demostrado.

**Fuera (exclusiones explícitas):**
- El algoritmo de exportación en sí (ya existe; no se duplica).
- **M3.2b** (inferencia de preferencias): CONGELADO, no se toca.
- El **riesgo del buffer `recent`**: cuestión independiente de continuidad/privacidad, pendiente de
  decisión de alcance del CEO. NO entra aquí.
- D-AMP-3/4/5, D-M-1 A′ y cualquier otro incremento no autorizado.
- Tocar CM2, S3 o CM1/R1.

## 5 · Contratos e interfaces afectados (con evidencia)

- `aura_skeleton/core/modelo_usuario.py:107` `exportar(user_id) -> str` — se reutiliza; posible cambio
  solo si el CEO elige cifrado (opción B/C).
- Ruta de acceso: el punto de cableado es el orquestador, donde ya viven las ramas de ver
  (`orchestrator.py:2248`) y corregir (`:2327`). Diseño mínimo a validar por `arquitecto-evaluador`:
  ¿orden conversacional («expórtame lo que sabes de mí») reconocida en `core/intencion.py`, o capacidad
  de catálogo gobernada por el Motor Único? Si la exportación se considera una **acción** sobre dato del
  usuario, el precedente es `borrar` (por el Motor, con permisos); si es **lectura**, el precedente es
  `ver`. La decisión de cuál encaja mejor es de diseño, no de gobierno.
- Catálogo de capacidades / `operaciones.py`: solo si se decide exponerla como capacidad del Motor.

## 6 · Pruebas exigidas

- **RED→GREEN**: una prueba que hoy falle porque el usuario NO puede exportar (no hay ruta) y pase
  cuando la ruta exista; con **control** (una petición que NO es de exportación no dispara la ruta).
- **Integración**: el usuario pide su modelo y recibe un artefacto con sus entradas y procedencia,
  aislado por `user_id` (no filtra otro usuario).
- **Seguridad/privacidad**: el export no incluye datos de terceros que el modelo no deba contener
  (coherente con la frontera ya existente); si opción B/C, que el cifrado sea real (no reversible sin
  clave).
- **Mutación**: mutantes sobre el cableado (la ruta deja de llamar a `exportar`) y sobre el aislamiento
  por `user_id`; cada uno debe morir.
- **Regresión**: ver/corregir/borrar siguen cableados; `test_garantias_vigentes` verde.

## 7 · Quality Gate y ECC para el cierre

- **Quality Gate PASS** (formato, ruff, mypy, pruebas, contratos).
- **Mutación**: 0 supervivientes en lo tocado.
- **ECC**: revisión independiente de privacidad (fuga por el export, aislamiento por `user_id`) y de
  calidad/contratos. No sustituye pruebas ni QG.

## 8 · Riesgos, criterios de aceptación y recuperación

| Riesgo | Mitigación |
|---|---|
| Que el export filtre datos de otro `user_id` | Prueba de aislamiento; `exportar` ya toma `user_id` |
| Que «cifrado» se implemente sin decisión y contradiga 4.1 §5 | §3 lo eleva al CEO; no se fija mecanismo sin su opción |
| Declarar «exportación» sin ruta real (repetir capacidad 009) | El criterio de aceptación es comportamiento demostrado, no «el método existe» |
| Sobre-ingeniería (bóveda de claves prematura) | Opción A evita clave; B/C solo si el CEO lo exige |

**Criterio de aceptación:** el usuario emite la petición por la ruta real y obtiene su modelo completo,
con procedencia, aislado, en local, en el formato que el CEO apruebe. Demostrado ejecutando.

**Recuperación:** la ruta de acceso es reversible (quitar el cableado); el método `exportar` es lectura
pura, no muta el store, así que un fallo no daña la memoria.

## 9 · Dependencias, secuencia y evidencia para PASS

**Dependencia dura:** la aprobación del CEO del cableado (DECISION_REQUIRED). El cifrado del artefacto YA
no es dependencia: 4.1 §5 fija formato neutral (opción A). Antes del diseño, confirmar el patrón de ruta.

**Secuencia (tras aprobación):** diseño mínimo (arquitecto-evaluador: ruta lectura vs. Motor) → RED →
GREEN (cablear la ruta a `exportar`, sin reconstruirlo) → mutación → Quality Gate → ECC → cierre en cinco bloques.

**Evidencia para PASS:** RED→GREEN demostrado, integración con artefacto real exportado, 0
supervivientes de mutación, QG PASS, ECC sin CRÍTICOS/ALTOS, ver/corregir/borrar sin regresión.

---

## DECISION_REQUIRED — M3.2a Exportar

**Pregunta única:** ¿Se aprueba **cablear** la exportación del modelo del usuario (la capacidad existe
—`modelo_usuario.py:107`— pero no es alcanzable), completando M3.2a, con el formato **neutral legible**
que la Bible ya especifica (4.1 §5 L64)?

*(El cifrado del artefacto exportado NO es una decisión pendiente: 4.1 §5 lo resuelve —exportación en
formato neutral; el cifrado es del almacén en reposo, requisito separado de ADR-0001. Si el CEO
prefiriera export cifrado opcional —opción B/C— sería una ampliación con clave/bóveda que la Bible no
exige.)*

Esta propuesta **no concede** nada: no autoriza obra hasta que el CEO responda, no toca M3.2b, el buffer
`recent`, CM2, S3 ni CM1/R1, y no fabrica aprobación alguna.
