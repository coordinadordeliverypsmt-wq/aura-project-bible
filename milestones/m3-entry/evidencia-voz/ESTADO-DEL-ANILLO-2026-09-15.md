---
documento: "Estado del anillo autónomo — reconstruido por ejecución"
tipo: "Evidencia técnica operacional"
fecha: 2026-09-15
mantenido-por: "APUS-5 (CTO)"
estado: "OPORTUNIDAD_REAL = 0, verificado hoy. La causa es estructural y está documentada."
---

# El anillo no tiene trabajo, y se sabe exactamente por qué

**Clasificación de evidencia** (D47): `[EJEC]` medido ejecutando · `[LECT]` leído · `[INFER]` deducido.

No se aceptó el valor anterior: el estado se reconstruyó ejecutando el descubrimiento real
(`entorno/control-plane/aura.py diagnosticar`, que solo lee y no toca la PARADA).

---

## 1 · Resultado del descubrimiento `[EJEC]`

```
cola:  ejecutables 0 · bloqueadas 5 · elevadas 12 · falsos huecos 2
hay_trabajo_autorizado: false
alcance_del_acta: ["eliminar_codigo_muerto", "implementar_incremento_especificado"]
```

**`OPORTUNIDAD_REAL = 0` sigue siendo cierto.** De 19 oportunidades descubiertas, ninguna es ejecutable.

| Clase | N.º | Qué son |
|---|---|---|
| `OPORTUNIDAD_REAL` | **0** | — |
| `DECISION_REQUIRED` | 12 | 10 son las **capacidades 010–018** del Plan de Formación (`autoridad = CEO`): construirlas exige acta. Las otras 2, decisiones de gobierno pendientes |
| `BLOQUEADA` | 5 | `OB-1`…`OB-6`: bloqueadas por **zona** (`walking-skeleton/` está fuera del perímetro) o por tocar el flujo de gobierno |
| `FALSO_HUECO` | 2 | Ya construidas. Una es la sexta fuente de descubrimiento: *«construida y cableada pero inerte porque su umbral…»* — parece un hueco y no lo es |

## 2 · Por qué el anillo no puede generar trabajo

La autoridad autónoma tiene **dos dimensiones**, y hoy **ambas están agotadas**:

- **ALCANCE** (acta DEC-ORCH-2): `eliminar_codigo_muerto` e `implementar_incremento_especificado`.
  El plano de control no tiene código muerto pendiente, y no existe ningún contrato de incremento escrito.
- **ZONA**: `entorno/control-plane/`. Todo lo demás —incluido `walking-skeleton/`, donde vive AURA— queda
  fuera.

Esto **no es un defecto del anillo**: es el diseño funcionando. El anillo descubre 19 oportunidades
reales, las clasifica correctamente y se detiene donde su autoridad termina, en vez de inventarse permiso.
Que `OPORTUNIDAD_REAL = 0` no significa que no haya trabajo en el proyecto; significa que **el trabajo que
queda exige un acta humana**.

## 3 · Los cinco candidatos, contrastados con la autoridad real `[EJEC]`

Ninguno se descartó por preferencia: los descarta el propio motor de AURA.

| Candidato | Veredicto | Motivo (del propio sistema) |
|---|---|---|
| 1 · Alinear etiquetas del observatorio | **No ejecutable** | La propuesta **P-019** existe pero **no tiene acta de aprobación**: sigue siendo propuesta |
| 2 · Reanclar garantías obsoletas | **No ejecutable** | Viven en `walking-skeleton/mutaciones/`, fuera de la zona |
| 3 · Auditor de garantías (`OB-2`) | **No ejecutable** | Registrado literalmente: *«vive en walking-skeleton/ — FUERA del perímetro que DEC-ORCH-2 autoriza»* |
| 4 · Lock cooperativo del arnés (`OB-5`) | **No ejecutable** | Registrado literalmente: *«walking-skeleton/ está FUERA del perímetro»* |
| 5 · Translator determinista (cap-010…012) | **No ejecutable** | Clasificadas `DECISION_REQUIRED` con `autoridad = CEO` |

## 4 · Hallazgo: el registro humano quedó desfasado del código `[EJEC]`

`entorno/control-plane/estado.json` (actualizado el 2026-08-31) declara:

```json
"autonomia_de_desarrollo": { "alcance": ["eliminar_codigo_muerto"] }
```

pero el motor, ejecutado hoy, reporta **dos** acciones:

```json
"alcance_del_acta": ["eliminar_codigo_muerto", "implementar_incremento_especificado"]
```

Es una discrepancia entre lo **registrado** y lo **vigente**, de la misma familia que «declarado ≠ real»
—aunque aquí el desfase está del lado del registro, no del código—. Encontrarla es precisamente el motivo
por el que no se aceptó el valor anterior sin verificarlo.

**No se ha modificado `estado.json`.**

> **CORRECCIÓN (2026-09-15, auditoría arquitectónica independiente).** Dos afirmaciones de la redacción
> original de este apartado eran **falsas**, y se rectifican aquí en vez de borrarlas:
>
> 1. Se dijo que `estado.json` es *«el historial autoritativo del plano de control»*. **No lo es.**
>    **ADR-0023** («El historial es la única fuente de verdad», *accepted*) establece que el historial
>    autoritativo es **`eventos.jsonl`**, y el propio código lo declara en `control_plane.py:1786`:
>    *«Borra `estado.json` y vuelve; edítalo a mano y manda el log.»*
> 2. Se dijo que podría corregirlo *«el propio ciclo cuando vuelva a ejecutarse»*. **Nunca lo hará.**
>    `grep` de `autonomia_de_desarrollo` sobre todo el código Python devuelve **cero** resultados: ningún
>    módulo escribe, lee ni valida ese campo. No hay un sincronizador roto — **no existe sincronizador**.
>
> La razón para no tocarlo sigue siendo válida, pero es otra: **qué hacer con ese campo es una decisión
> del CEO**, no una corrección técnica (ver §6).

### El alcance vigente y de dónde sale realmente `[EJEC]`

El motor **no** lee el alcance de `estado.json`: lo reconstruye del event log
(`review.py:164-169`), tomando el **último** evento `review_habilitado`. Solo existen dos:

| `seq` | Fecha | Autoridad | Alcance |
|---|---|---|---|
| 1 | 2026-08-26 | `ceo` | `["eliminar_codigo_muerto"]` — acta **DEC-ORCH-2** |
| **1542** | **2026-09-07** | `ceo` | `["eliminar_codigo_muerto", "implementar_incremento_especificado"]` — acta **DR-D** |

El verbo entró por la puerta correcta: `review.habilitar()` exige autoridad humana (ADR-0003:33) y acta no
vacía. **AURA no se amplió el alcance a sí misma.** El registro que estaba desfasado era el documento, no
la autoridad.

### Clasificación del hallazgo: **C · inconsistencia real**

No es A (ningún documento declara que este campo pueda quedar obsoleto), ni B (no es una proyección: el
criterio literal de **ADR-0023 §4** es *«debe poder eliminarse por completo y regenerarse desde el
historial»*, y borrar `estado.json` **no** regeneraría este bloque — `_aplicar()` ignora los eventos
`review_habilitado`), ni D (un bug exige un sincronizador roto, y aquí nunca existió).

**Ningún permiso se concedió ni se negó por este desfase**: ningún camino de autorización lee
`estado.json`. El riesgo es de **veracidad del registro**, no de autoridad — exactamente el fallo que
ADR-0023 §1 predijo: *«un dato almacenado dos veces termina divergiendo»*. Y llegó a engañar a un lector
humano: este mismo documento estuvo a punto de reportar un alcance de una acción cuando el vigente son dos.

## 5 · Qué desbloquearía trabajo

El propio estado lo declara, y coincide con lo medido:

> *«un acta que amplíe el ALCANCE del acta de DEC-ORCH-2 más allá de `eliminar_codigo_muerto`, o que
> amplíe la ZONA más allá de `entorno/control-plane/`. Ambas dimensiones están agotadas hoy»*

Ampliar cualquiera de las dos es **autoridad nueva** y corresponde a una decisión de la familia, no al
anillo ni al CTO. Se deja identificado, no propuesto como ejecutable.

---

## 6 · Decisiones que la auditoría deja abiertas (no resueltas aquí)

### 6.1 · Qué hacer con `autonomia_de_desarrollo` en `estado.json`

El campo es un **anexo narrativo escrito a mano** que ADR-0023 no ampara: no se proyecta desde el log, no
lo lee ningún código y lleva 20 días congelado mientras la autoridad vigente cambiaba. Tres salidas
posibles —**ninguna elegida aquí**—: proyectarlo desde el log, retirarlo por duplicado, o mantenerlo a
mano asumiendo explícitamente que es una nota fechada y no una fuente. Editarlo sin más solo aplazaría el
problema hasta la próxima acta.

### 6.2 · La letra del acta DR-D es más estrecha que lo que el mecanismo sabe representar

El acta `seq 1542` se autolimita: *«Alcance: ÚNICAMENTE esta capacidad; sin ampliación general de
autoridad»*. Pero `_alcance()` devuelve **verbos**, sin granularidad de capacidad: una vez
`implementar_incremento_especificado` está en la tupla, `en_alcance()` lo concede para **cualquier** tarea
de ese verbo, no solo para la sexta fuente.

Hoy eso **no ha concedido nada indebido** —siguen mandando la zona, la materia reservada, el ejecutor
construido (`review.py:106`) y el contrato de cada capacidad—, y el propio `review.py:78-85` deja escrito
que entrar en la lista blanca «no lo hace ejecutable por sí solo». Pero es una **divergencia entre la
intención escrita del acta y lo que el mecanismo puede expresar**, y conviene que la familia sepa que
existe antes de firmar la próxima.

### 6.3 · Una afirmación documental que el código no sostiene

`DP-DEVELOPMENT-ORCHESTRATOR.md:118` y `:294` afirman que `estado.json` *«pasa a ser proyección
reconstruible → cumple ADR-0023 por su propio criterio»*. La evidencia que lo respalda
(`CIERRE-F1…md:91`, «estado.json BORRADO. Reconstruido del log: True») acredita **solo el subconjunto de
tareas**, no el fichero entero. No se ha modificado ese documento: es un Decision Package y su corrección
no corresponde al CTO.
