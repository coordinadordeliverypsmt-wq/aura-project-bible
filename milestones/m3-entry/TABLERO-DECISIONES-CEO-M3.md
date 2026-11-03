> **ACTUALIZACIÓN 2026-08-23:** `D-CP-4` (alternativa C) y `D-CP-6` (opción a) están **DECIDIDAS
> por el CEO, implementadas, mutadas y auditadas**, junto con la resolución del conflicto
> `ADR-0003` (solo lo VERDE es criterio AUTO). **Siguen abiertas `D-CP-5`, `D-CP-7` y `D-CP-3`.**
> Las filas de abajo reflejan el estado del día en que se escribió el tablero.

# Tablero de decisiones del CEO — M3

> **ACTUALIZACIÓN 2026-08-25 — `D-CP-7` CERRADA:** `F-DCP7 = GREEN respecto al WORKER ADMINISTRADO`. `bwrap` + user namespace es enforcement real para el Worker dentro de la jaula. **Constraint arquitectónico permanente, no deuda:** no protege frente a otro proceso del **mismo UID**; sin privilegios esa frontera no se considera cerrable. **Siguen ABIERTOS** —y no se presentan como cerrados— el lanzador omitible, el TOCTOU, credencial+red, el audit log `rw` y la cobertura incompleta del hook. **Sigue abierta `D-CP-3`.**


> **ACTUALIZACIÓN 2026-08-23 — `D-CP-5` YA ESTÁ DECIDIDA E IMPLEMENTADA:** esquema CERRADO por tipo, con RED, GREEN, mutación 6/6 sin supervivientes y auditoría independiente. **Decisión del CEO del 2026-08-23** (mensaje de encargo: *«La decisión vigente es ESQUEMA CERRADO POR TIPO»*), registrada tardíamente el mismo día tras una auditoría independiente que señaló su ausencia como artefacto. Lo detectó esa misma auditoría: cinco documentos seguían declarándola abierta mientras el código ya la implementaba — «declarado ≠ real», esta vez del lado de la gobernanza. **Siguen abiertas `D-CP-7` y `D-CP-3`.**


**Fecha:** 2026-08-18 · **Prepara:** APUS-5 · **Decide:** CEO
**Este documento no elige, no autoriza y no cambia ningún estado.** Consolida **solo** lo que hay
que decidir para desbloquear construcción. Toda la evidencia citada está medida en documentos
previos; aquí no se investiga nada nuevo.
**Clasificación D47:** `[EJEC]` medido · `[LECT]` leído · `[INFER]` deducido · `[UNKNOWN]` no verificado.

---

# BLOQUE 1 · `P1`

> ## ¿Esta máquina es el objetivo de despliegue de AURORA?

`D36` ya oficializó **E1** (*«uso personal, un solo proceso»*) como escenario inicial. **`P1` no
elige escenario: elige la máquina.**

### A) SÍ — esta Lenovo es el objetivo

| Consecuencia | Evidencia |
|---|---|
| **N2 nunca se materializa** | Umbral **8 GB**; la máquina tiene **3,6 GB** `[EJEC]`. El arranque real registra `degradadas=['memoria']; memoria -> N1` |
| **El turno con LLM local no es viable** | «Hola» de 8 tokens → **25,8 s**, *21×* sobre HC-1; prompt real de 543 tokens → **no completa** `[EJEC]` |
| **~430 LOC de 6 ADRs aceptados nunca se ejecutan** | `[EJEC]` revisión §3.4 |
| **Margen de disco escaso** | 8,2 GB libres, 85 % usado; USB `AURORA_EXT` **391 MB, 95 %** `[EJEC]` |
| **La inversión A queda cerrada de hecho** | Si esta máquina es el objetivo y el presupuesto sigue en cero (**D34**), el techo de Product Readiness se acepta como permanente |
| **Identidad fuerte (N-3) queda descartada** | Máquina monousuario: cualquier proceso lee el secreto. Firmar daría **apariencia** de autenticación `[INFER]` |

### B) NO — es entorno de desarrollo / prototipo

| Consecuencia | Evidencia |
|---|---|
| **Las mediciones de hardware dejan de ser criterio de producto** | Miden el entorno de desarrollo, no el objetivo |
| **N2 y el LLM local pasan a estar pendientes del objetivo real** | No se declaran inviables: se declaran **no medidos aquí** |
| **`D-CP-3/N-3` vuelve a ser posible** | Un objetivo multiusuario o con llavero permite aislar secretos `[INFER]` |
| **`D-CP-7/B` deja de chocar con E1** | Si el objetivo admite multi-proceso, que AURORA lance agentes no contradice el escenario |
| **Se abre la pregunta de qué máquina es** | **No la responde este documento** |

**Se decide, además, si la alternativa A de inversión sigue viva.** No se elige.

---

# BLOQUE 2 · LÍNEA A — Motor Único

### `D-G1-2` · Lista blanca inicial de G-1

- **Decisión:** ratificar la clasificación de los 10 módulos que escriben a disco.
- **Evidencia** `[EJEC]`: **25 escrituras reales en 10 módulos**. **A** (fuente existe): `memory.py`,
  `reglas.py`, `observability.py` y **`estado_operativo.py`** —ADR-0023 lo reconoce explícitamente—.
  **B** (decisión humana): `decisiones.py`, `conectores/auditoria.py`, `adapters/programador.py`,
  `adapters/computador.py`. **C** (propuesta de exclusión): `kill_switch.py` (Bible 5.3 §5),
  `centro_gobierno.py` (proyección regenerable, ADR-0023).
- **Si se aprueba:** el manifiesto puede escribirse y **R-B** deja de estar en rojo.
- **Si sigue pendiente:** **G-1 no puede entrar en verde**; F0 no cierra.

### `D-G1-3` · Las cuatro rutas invisibles

- **Decisión:** ¿se autorizan **dos anotaciones de tipo** en producción (`modelo_usuario.py:30` y el
  `__init__` del orquestador), sin cambio de comportamiento?
- **Evidencia** `[EJEC]`: los **4 receptores no resolubles son exactamente las 4 rutas de
  ALERTA-006**. Medido **sobre copia temporal**: con la anotación, R-A pasa de **0 a 2** detecciones.
- **Si se aprueba:** G-1 detecta lo que existe para detectar.
- **Si sigue pendiente:** **G-1 en verde sería ciega a ALERTA-006** — «declarado ≠ real» dentro de la
  garantía madre. Es la razón por la que **no escribí el manifiesto**.

### `C-ESPEC-F2-F3` · Adaptadores en dos familias

- **Decisión:** cuando un adaptador escribe a disco, ¿manda **F3** (efecto externo, ruta autorizada
  del Motor) o **R-B** (escritura directa prohibida)?
- **Evidencia** `[LECT]`: `ESPEC §2.2` lista *«adaptadores»* en **F3**; R-B los detecta igual.
  **La ESPEC no dice cuál manda.**
- **Si se aprueba:** `programador.py` y `computador.py` salen de `D-G1-2/B`.
- **Si sigue pendiente:** o se acusa al mecanismo legítimo, o se abre un hueco por omisión.

### `D-ORCH-5` · Levantar `CHECKLIST §5.2` para `ORCH-FASE-1`

- **Decisión:** autorizar el incremento del orquestador.
- **Evidencia** `[LECT]`: la aprobación de `DP-D-M-8` y la resolución de la inversión **ya
  satisficieron §5.2 para D-M-8**; `ORCH-FASE-1` sigue sin su propia autorización.
- **Si se aprueba:** puede construirse event log + lock + transiciones gobernadas.
- **Si sigue pendiente:** los defectos **P2** (escritura perdida) y **P4** (transición sin validar)
  siguen vivos, ambos demostrados por ejecución.

**No se proponen decisiones nuevas en este bloque.**

---

# BLOQUE 3 · LÍNEA B — Communication Plane

| Id | Decisión exacta | Dependencia | Evidencia | Si se aprueba | Si sigue pendiente |
|---|---|---|---|---|---|
| **`D-CP-3`** | Identidad: mantener **N-2** o ir a **N-3** | **`P1`** | N-2 da trazabilidad e integridad del log; **no** autenticación ni no repudio | Se fija el nivel y su límite queda escrito | La identidad sigue siendo suplantable (**B-3**) |
| **`D-CP-4`** | Criterio: **A** catálogo cerrado · **B** fuera de `cuerpo` · **C** ambas | **`D-CP-6`** para que A baste; efecto real solo con **`D-CP-7` B/C** | `§14.bis` regla 3 ordena **ejecutar** el criterio; **solo A ataca V3** | V1 cerrado; V3 acotado | Un mensaje puede convertirse en **ejecución de código** |
| **`D-CP-5`** | Lista negra → **esquema cerrado por tipo** | Ninguna *(la única independiente)* | La lista negra está demostrada **solo a profundidad 1**; una lista de palabras es infinita | V4 cerrado por construcción | Contrabando por anidamiento y sinónimos |
| **`D-CP-6`** | Esquema de argumentos para las **23** capacidades sin él | Es trabajo de **Línea A** | **10 de 33** tienen esquema; **las 4 que A usaría, no** `[EJEC]` | El catálogo cerrado pasa a acotar también los **argumentos** | Acotar *qué* se ejecuta no acota *con qué* |
| **`D-CP-7`** | Quién lanza al agente: **A** usuario · **B** AURORA · **C** híbrido | **`P1`** | `permissions.allow = ["Bash(*)"]`, **sin hooks en ningún nivel** `[EJEC]` | Las decisiones del canal dejan de ser documentales | **La frontera entera es documental** |

---

# BLOQUE 4 · Dependencias

| Decisión | Desbloquea | Bloquea mientras siga pendiente |
|---|---|---|
| `P1` | `D-CP-7`, `D-CP-3/N-3`, inversión A | El escenario de todo lo demás |
| `D-CP-7` | Que `D-CP-4/5/6` sean frontera real | `ORCH-FASE-1` |
| `D-CP-6` | Que `D-CP-4/A` sea suficiente | Validación de argumentos |
| `D-CP-4` | Canal B1 | V1 y V3 |
| `D-CP-5` | Canal B1 | V4 |
| `D-G1-2` | Escribir el manifiesto | G-1 |
| `D-G1-3` | Que G-1 vea ALERTA-006 | La veracidad de G-1 |
| `C-ESPEC-F2-F3` | Cerrar `D-G1-2/B` | 2 de los 4 módulos dudosos |
| `D-ORCH-5` | `ORCH-FASE-1` | P2 y P4 |

### Las dos cadenas

```
P1 ──▶ D-CP-7 ──▶ D-CP-4 / D-CP-5 / D-CP-6 ──▶ frontera real del canal
                     (bajo D-CP-7/A siguen siendo documentación)

D-G1-2 + D-G1-3 ──▶ G-1 ──▶ Motor Único como ruta única ──▶ frontera real del Communication Plane
```

> **Las dos cadenas convergen.** El canal solo puede apoyarse en el Motor si el Motor es **ruta
> única**, y eso es **G-1**. La cadena de Línea A **sostiene** a la de Línea B.

---

# BLOQUE 5 · Los dos primeros GREEN

### `GREEN-A` · G-1 en verde

| | |
|---|---|
| **Precondiciones** | `D-G1-2` + `D-G1-3` |
| **RED existente** | **15 pruebas** — 5 rojas, 10 verdes `[EJEC]` |
| **Producción que modificaría** | **2 anotaciones de tipo**, sin cambio de comportamiento — y solo si `D-G1-3` se aprueba. El verificador vive en `tests/` |
| **Riesgos** | Falsos positivos de R-B en adaptadores (`C-ESPEC-F2-F3`) · fricción de R-C al clasificar métodos nuevos · coste del AST en el gate **no medido** `[HIPO]` |
| **Habilita después** | `F4` y `F6` de `D-M-8`; y da al canal el Motor como ruta única |

### `GREEN-B` · Communication Plane B1

| | |
|---|---|
| **Precondiciones** | `D-CP-2` + `D-CP-5` + `D-CP-4` |
| **RED existente** | **79 pruebas** — 35 + 14 + 30, todas rojas `[EJEC]` |
| **Producción que modificaría** | **Ninguna.** Vive en `entorno/`, fuera de `walking-skeleton/` |
| **Riesgos** | Bajo `D-CP-7/A` la frontera es documental (**B-1**) · identidad suplantable (**B-3**) · persuasión semántica, que **nada cierra** (**B-4**) |
| **Habilita después** | B2 (dos extremos `claude -p`) y, si se resuelven `D-CP-1.bis`/`.ter`, B3 con Codex |

**Ninguno espera a Codex, a cuota ni a hardware nuevo.**

---

# BLOQUE 6 · Análisis del orden — **no es autorización**

### Qué debe resolverse primero

**`P1`.** Es la única con dependientes en las dos líneas: condiciona `D-CP-7`, `D-CP-3/N-3` y la
vigencia de la inversión A. **Mientras `P1` siga abierta, `D-CP-7` no se puede decidir sin suponer.**

### Qué puede resolverse en paralelo

**Sin dependencias entre sí ni con `P1`:** `D-G1-2` · `D-G1-3` · `C-ESPEC-F2-F3` · `D-ORCH-5` ·
`D-CP-5`. **Las cinco son decidibles hoy.**

### El orden de construcción más pequeño y seguro, técnicamente

`[INFER]` Comparando **longitud de cadena** y **superficie tocada**:

| | `GREEN-A` | `GREEN-B` |
|---|---|---|
| Decisiones previas | **2**, ambas independientes de `P1` | **3**, y `D-CP-4` arrastra `D-CP-6` |
| Producción tocada | 2 anotaciones | ninguna |
| ¿Su valor depende de otra decisión? | **No** | **Sí** — bajo `D-CP-7/A` es documental |

**`GREEN-A` tiene la cadena más corta y su valor no depende de ninguna decisión abierta.**
`GREEN-B` toca menos producción, pero **su valor sí depende de `D-CP-7`**. Es una observación sobre
las cadenas, no una elección.

### Dónde aparece el primer GREEN real

Tras `D-G1-2` + `D-G1-3`: **G-1 en verde con cobertura real**, que es el primer incremento que cierra
un defecto medido en vez de documentarlo. A partir de ahí, `F2`→`F3`→`F5` en el orden que el propio
`D-M-8 §7` fija.

**Esta sección no autoriza nada.**

---

DECISION_REQUIRED

1. **`P1`** — ¿Esta máquina es el objetivo de despliegue de AURORA? *(A: sí · B: solo desarrollo)*
2. **`D-G1-2`** — Ratificar la lista blanca de G-1: los 4 de **A**, los 4 de **B**, los 2 de **C**.
3. **`D-G1-3`** — ¿Se autorizan las **dos anotaciones de tipo** en producción, sin cambio de comportamiento?
4. **`C-ESPEC-F2-F3`** — Cuando un adaptador escribe a disco, ¿manda **F3** o **R-B**?
5. **`D-ORCH-5`** — ¿Se levanta `CHECKLIST §5.2` para `ORCH-FASE-1`?
6. **`D-CP-7`** — ¿Quién lanza al agente ejecutor: **A** usuario · **B** AURORA · **C** híbrido?
7. **`D-CP-4`** — Criterio de finalización: **A** catálogo · **B** fuera de `cuerpo` · **C** ambas.
8. **`D-CP-5`** — ¿Se sustituye la lista negra por un **esquema cerrado por tipo**?
9. **`D-CP-6`** — ¿Se declara esquema de argumentos para las **23** capacidades que no lo tienen?
10. **`D-CP-3`** — Identidad: ¿se mantiene **N-2** o se va a **N-3**? *(depende de `P1`)*
11. **`D-CP-2`** — ¿Se autoriza GREEN del canal, y en qué fase: **B1** · **B2** · **B3**?
12. **Primer incremento** — ¿**GREEN-A** (G-1) o **GREEN-B** (Canal B1)?
