# DP · D-CP-8 — dónde está la frontera de enforcement de la barrera B4

> **Decision Package. No implementa nada.** Redactado el 2026-08-24 tras detener la implementación:
> el bloqueo **no es técnico, es contractual**. `communication_plane.py` no se ha tocado.
> **Ninguna decisión previa se reinterpreta**; los huecos se declaran **NO DEFINIDO**, no se rellenan.

## 1 · Contrato actual reconstruido

| Concepto | Fuente | Definición literal | ¿Permite enforcement? | Vacío |
|---|---|---|---|---|
| **capacidad** | `CLAUDE.md` (CEO 2026-08-03) · `permissions.py` | *«AURORA nunca ejecuta instrucciones arbitrarias del SO: solo CAPACIDADES registradas»*, nombradas **por el resultado** | **Sí** — hay catálogo real y clasificación verde/roja | — |
| **criterio** | `DP-ORCH §14.bis` r.1-4 · `D-CP-4`=C | Lo fija **quien crea la tarea**, se escribe en el event log **antes** de invocar al Worker; **referencia una capacidad registrada**; **procede del Control Plane**; **NO viaja en `cuerpo`** | Sí, pero **fuera del canal** | — |
| **objetivo** | `D-CP-5` (esquema cerrado) | `"objetivo": str` | **No** | ⚠ **NO DEFINIDO**: ninguna fuente dice que sea un identificador de capacidad |
| **mensaje** | `CONTRATO-CP` · `CAMPOS_MENSAJE` | Sobre con `tipo/de/para/cuerpo/…`; **ningún campo concede autoridad**, y *«esa ausencia ES la garantía»* | Sí, por ausencia | — |
| **Control Plane** | Sección E · `fuentes_de_autoridad()` | *«El canal pregunta al Control Plane; el Control Plane nunca pregunta al canal»*. Única fuente de autoridad | **Sí** | — |
| **Communication Plane** | `DP-CP §10` · `permisos_sobre_el_control_plane()` | **TRANSPORTE**. Permiso sobre el Control Plane: `SOLO_LECTURA` | Limitado: **no puede escribir autoridad** | — |
| **B4** | Sección E (7 símbolos) | Vocabulario e invariantes de la barrera | **Hoy no**: 4 de sus símbolos tienen **0 usos** | — |
| **AUTO** | `DP-ORCH` C6 · §14.bis r.4 | Estado de una **tarea del Orchestrator**, del mapa `Policy: acción → AUTO/REVIEW/HUMAN` |  Sí, **en el Orchestrator** | — |
| **REVIEW / HUMAN** | `DP-ORCH` C6 · §14.bis r.4 | Escalones a los que **sube** una tarea no automatizable |  Sí, **en el Orchestrator** | — |
| **publicación** | `Canal.publicar()` | Invoca `validar()`; id determinista sobre el contenido | **Sí, y ya se usa** (D-CP-4 y D-CP-5) | — |
| **entrega** | `entregar_a_receptor()` | `confianza=NO_CONFIABLE`, `ejecutable=False` | **Sí — pero nadie la invoca** | ⚠ no hay ruta de entrega cableada |
| **lectura** | `leer()` · `leer_desde()` | Devuelven el mensaje **crudo** | **No** | — |
| **autorización** | Sección E · `clase_de()` | *«ningún tipo de mensaje es una AUTORIZACIÓN»*; la autorización **no viaja** | Sí, por ausencia | — |

## 2 · La ambigüedad exacta

El criterio de enforcement pedido es: *«una capacidad no-AUTO no puede atravesar la frontera como si
fuera AUTO»*. Reconstruido el contrato, **esa frase no es implementable en el Communication Plane**,
y no por una limitación técnica sino por dos hechos del propio contrato:

1. **`AUTO` no es un concepto del canal.** Es un estado de **tarea del Orchestrator**, definido en su
   `Policy` (C6). Un mensaje no es AUTO ni deja de serlo: un mensaje se transporta.
2. **Ninguna capacidad viaja por el canal.** `D-CP-4`=C ya cerró esa puerta: el criterio procede del
   Control Plane y **no viaja en `cuerpo`**. No hay «capacidad atravesando la frontera» que detener.

Para que sí fuera implementable haría falta afirmar que `cuerpo["objetivo"]` nombra una capacidad
—y **ninguna fuente lo establece**—. Eso sería **crear una segunda vía de clasificación**, que la
propia orden prohíbe.

## 3 · Hipótesis evaluada explícitamente

> `cuerpo["objetivo"] == nombre de capacidad` → **NO DEFINIDO**

Verificado el 2026-08-24 sobre `CONTRATO-COMMUNICATION-PLANE.md`, `DP-COMMUNICATION-PLANE-AURORA.md`,
`estado.json` y el esquema de `D-CP-5`: **cero apariciones** que liguen `objetivo` a `capacidad` o al
catálogo. **No se convierte en requisito implícito.**

## 4 · Alternativas contractuales

### A · Enforcement en el Control Plane, antes de publicar

| | |
|---|---|
| **Conserva** | Todo. Es donde §14.bis r.1 ya sitúa el criterio: en el event log, antes de invocar |
| **Rompe** | Nada del canal |
| **Necesita** | Un Control Plane que decida — hoy `estado.json` es un registro, no un decisor |
| **¿Campo nuevo?** | No |
| **¿Segunda clasificación?** | No: usa la que ya existe |
| **RED afectadas** | Ninguna del canal |
| **Decisión humana** | Construir esa capacidad de decisión ⇒ **es el Orchestrator**, hoy prohibido |

### B · Enforcement dentro del Communication Plane (`leer()` devuelve envuelto)

| | |
|---|---|
| **Conserva** | La dirección de dependencia (el canal sigue solo leyendo autoridad) |
| **Rompe** | **El contrato de B1**: `leer`/`leer_desde` cambian de tipo de retorno |
| **Necesita** | Nada externo |
| **¿Campo nuevo?** | Sí, en lo entregado (`confianza`, `ejecutable`) |
| **¿Segunda clasificación?** | No para E-1; **sí** si añade clasificación de capacidad |
| **RED afectadas** | Las de `leer`, `leer_desde`, `pendientes`, `hilo` — **~7 pruebas B1 en verde hoy** |
| **Decisión humana** | Autorizar modificar el contrato de B1, que `D-CP-2` aprobó acotado |

### C · Método explícito de entrega (`Canal.entregar(id)`)

| | |
|---|---|
| **Conserva** | **Todo B1 intacto** |
| **Rompe** | Nada |
| **Necesita** | Nada |
| **¿Campo nuevo?** | No en el sobre; sí en el objeto entregado |
| **¿Segunda clasificación?** | No |
| **RED afectadas** | Ninguna existente; las 2 de E-1 pasarían a verde |
| **Decisión humana** | Aceptar que el enforcement es **opt-in y por tanto rodeable**: quien llame a `leer()` sigue recibiendo el crudo |

### D · Declarar el límite como permanente

Aceptar el veredicto **(B)** de la Sección E como **constraint arquitectónico**, no como deuda:
*«el canal no puede impedir que un modelo sea persuadido; solo que la persuasión produzca efecto»*
—que es literalmente lo que `limites_frente_a_inyeccion()` ya declara— y situar el enforcement donde
el contrato lo pone: en el **Motor Único** y en el **Orchestrator**. Es el precedente ya sentado en
`D-CP-7`, donde el CEO aprobó redefinir el criterio de cierre al probarse un límite estructural.

## 5 · Recomendación

**No hay una alternativa concluible del contrato para E-2**, así que no recomiendo ninguna sobre ella.

**Sobre E-1 sí puede concluirse algo respaldado literalmente:** `entregar_a_receptor()` es un símbolo
**ya aprobado** que declara `confianza=NO_CONFIABLE` y `ejecutable=False`. Que exista sin que ninguna
ruta lo invoque es «declarado ≠ real» dentro del propio canal. **Cablearlo no amplía el contrato: lo
aplica.** Entre B y C, la diferencia es si el enforcement debe ser **inevitable** (B, rompiendo B1) o
**disponible** (C, rodeable) — y eso es decisión del CEO, no mía.

## 6 · Impacto por alternativa

| | B1 | B2 | B3 | B4 | D-CP-4 | D-CP-5 | Sección E | Orquestador | Claude/Codex |
|---|---|---|---|---|---|---|---|---|---|
| **A** | — | — | — | — | — | — | (B) sigue | **lo requiere** | — |
| **B** | **rompe** | revisar | — | **cablea** | — | — | **cierra E-1** | compatible | receptor recibe dato marcado |
| **C** | — | — | — | **cablea parcial** | — | — | **E-1 opt-in** | compatible | igual, si lo llama |
| **D** | — | — | — | queda declarativo | — | — | **(B) permanente** | lo asume | — |

**Bypasses previsibles:** en **C**, llamar a `leer()` en vez de `entregar()` — trivial. En **B**,
leer `canal.jsonl` directamente del disco: ninguna alternativa lo impide, y **ya está declarado** en
`limites_de_identidad()` (*«quien tenga acceso de escritura al disco puede falsificar un mensaje»*).

## 7 · Qué puede continuar sin decidir esto

El **resto del contrato del Communication Plane**: 23 símbolos ausentes y 43 RED en rojo, ninguno
dependiente de D-CP-8.

## 8 · Artefacto para la futura auditoría de Codex

Este DP más `test_red_dcp8_cableado.py` (en rojo) son el paquete mínimo. La pregunta para Codex, sin
darle la conclusión: *«¿existe en estos artefactos alguna fuente que ligue `cuerpo["objetivo"]` al
catálogo de capacidades? ¿Y algún punto donde el canal pueda distinguir AUTO de no-AUTO sin
inventarlo?»*. Se añadirá al paquete descrito en `PAQUETE-AUDITORIA-CODEX.md`.
