---
documento: "Aprobación de D-AMP-2 — construcción del Memory Context Builder"
tipo: "Registro de decisión del CEO"
fecha: 2026-10-11
mantenido-por: "Dirección Técnica (sesión de asistencia)"
decide: "CEO (Mauricio)"
sobre: "milestones/m3-entry/AMP-AURA-DECISIONES.md §D-AMP-2"
---

# D-AMP-2 — Aprobación de la construcción del Memory Context Builder

## Origen de esta anotación

**Fuente: autorización explícita del CEO, emitida en la directiva ejecutiva «D-AMP-2 · MEMORY CONTEXT
BUILDER» de esta sesión (2026-10-11).** No existe acta anterior. Este fichero **no** documenta una
aprobación previa perdida: registra la que se acaba de dar, en el momento en que se dio, y esa es toda
su autoridad. Hasta hoy, D-AMP-2 constaba como «pregunta cerrada para firma, pendiente del CEO»
(verificado el 2026-10-11: frontmatter de `AMP-AURA-DECISIONES.md` «Requiere aprobación del CEO»,
sin acta en `decisiones/`, sin eventos en `eventos.jsonl`/`estado.json`/`audit.jsonl`).

El Decision Package `AMP-AURA-DECISIONES.md` **no se modifica**: su historia queda como estaba. Patrón
de registro replicado de `decisiones/2026-09-09-D-M-7-aprobacion-opcion-A.md`.

## Alcance aprobado

Construcción del **Memory Context Builder** descrito en `AMP-AURA-DECISIONES.md §D-AMP-2`:

1. Una **función pura** situada **entre `recall` (paso 15) y la construcción del prompt (paso 17)**,
   antes de `router.route`, en `walking-skeleton/aura_skeleton/core/orchestrator.py`.
2. **Recibe:** hits del recall, buffer de diálogo, atributo preguntado, scope del turno.
3. **Puede transmitir:** el valor exacto del hecho pertinente que el Core estableció (literal);
   evidencia marcada como no establecida.
4. **Debe excluir del contexto que llega al modelo:** hechos de **terceros (siempre)**, propuestas,
   hechos no pertinentes y memoria sensible.
5. **Sin autoridad nueva:** no escribe, no llama al motor, no altera estados. Si escribiera algo, deja
   de ser un Builder y es un bug. Respeta `ADR-0014` (el valor transmitido es el que el Core estableció)
   y `G-1` (no es ruta de mutación, no toca el store).
6. Verificable con mutación. Es un **incremento propio**, posterior a las etapas 1–2 (D-AMP-1=B) ya
   ejecutadas.

## Límites declarados de la entrega (revisión de seguridad ECC, 2026-10-11)

El Builder cierra la fuga por la vía de la **memoria recuperada** (`recall`). NO es una garantía de
privacidad cerrada, y así se declara —en el docstring de `core/contexto_memoria.py`, aquí y en el
CHECKPOINT— para no fingir capacidad (INV-9):

1. **Buffer de diálogo (`recent`):** es otra vía hacia el mismo prompt y NO pasa por el Builder. Un
   tercero mencionado en la conversación en curso reentra durante la ventana de diálogo. Es continuidad
   conversacional y su comportamiento es el previo al incremento; filtrarlo rompería esa continuidad y
   queda fuera del alcance del DP. Una política para el buffer requeriría decisión del CEO.
2. **Detección léxica y parcial:** la lista `core/sujeto.TERCERO` es cerrada (misma cobertura que la
   captura); fraseos no listados (nombres propios, «mi colega», «un amigo mío») son falsos negativos.
   Protección incremental, no exhaustiva.
3. **Filtrado por registro completo:** incluye o excluye el `content` entero, sin redacción parcial de
   la cláusula del tercero.

## Lo que esta aprobación NO concede

Aprobar la construcción del Builder **no** autoriza:

- **D-AMP-3** (FORGET/`borrar`), **D-AMP-4** (`PROPOSE`), **D-AMP-5** (identidad canónica): siguen
  pendientes de decisión del CEO.
- **D-M-1 A′** (recuperador léxico N1): fuera de este incremento.
- Modificar `ADR-0014`, `core/intencion.py`, `contracts.py`, el motor, `PARADA`, la Bible, los ADR,
  `CLAUDE.md`, el roadmap ni `decisiones/`.
- Ampliar autoridad, permisos o capacidades; crear rutas alternativas que eludan la gobernanza.
- Tocar CM2, reabrir S3 ni levantar el freeze de M3.2b.
- `commit`, `push` ni `merge`.

Si durante la construcción una regla necesaria no está definida en el DP, la Bible o los ADR
aplicables, no se inventa política: se documenta el conflicto y se detiene.
