# DECISION-PACKAGE-LINEA-A

> **2026-08-25.** No implementa nada, no promueve nada, no toca `aura_skeleton/`.
> Evidencia D47: `[EJEC]` medido · `[LECT]` leido · `[INFER]` deducido.
> **IDs segun el esquema vigente** (`D-G1-n`, `D-CP-n`, `D-ORCH-n`): las nuevas son `D-M8-n`.

**Los 11 bloqueos de Linea A se agrupan en 3 decisiones nuevas + 2 ya registradas.** Ninguna
necesita analisis adicional: lo que falta es que el CEO elija.

---

## D-M8-1 · Como llega el kill switch a la rama de soberania

**HALLAZGOS AFECTADOS:** G-2 x3 — `modelo_usuario.py` (borrar, refutar) y `reglas.py` (crear).
**Arrastra G-3 #4**, que es el mismo agujero visto por su efecto.

**GARANTIA:** con la parada de emergencia ARMADA, ninguna mutacion persistente ocurre.

**CONTRATO QUE LA RESPALDA:** `ALERTA-005` (CLAUDE.md, regla no negociable): *«Toda ejecucion pasa
por el motor unico, con permisos y dry-run. **Ninguna ruta alternativa**»*. `DP-D-M-8 §6` fija la
forma de G-2: *«prueba parametrizada sobre TODAS las operaciones del catalogo, no solo las que pasan
por `authorize`»*.

**LO DETERMINADO:** la direccion. `DP-D-M-8 §4.3` desactiva ademas la unica objecion de producto:
*«pasar por el motor no es lo mismo que pedir confirmacion»*, asi que enrutar **no** obliga a que
«olvida esto» pida permiso.

**LO NO DETERMINADO:** **cuando**. Enrutar depende de `F2`/`F3`, bloqueadas por `C-ESPEC-F2-F3`.

**ALTERNATIVAS:**

- **A · consultar el kill switch dentro de cada rama.** Toca `modelo_usuario.py` y `reglas.py`.
  Barata e inmediata. **DESCARTADA POR CONTRATO:** deja la mutacion fuera del motor y crea
  exactamente la ruta alternativa que `ALERTA-005` prohibe. No es una decision nueva: es aplicar la
  que ya existe. *(Lo registro como descarte, no como veredicto propio.)*
- **B · enrutar la operacion por el motor unico.** Toca `modelo_usuario.py`, `reglas.py`, el motor y
  el catalogo. Cierra las tres de una vez y G-3 #4 como consecuencia. Coste: depende de F2/F3.
  Riesgo: cambia la ruta de borrado de datos del usuario — la mas sensible del sistema.
- **C · enrutar, pero por fases**, empezando por una sola operacion. Reduce el radio de impacto a
  cambio de convivir un tiempo con dos rutas. **Respaldada por el propio DP**, que ya organiza el
  trabajo en F1..F3.

**DECISION MINIMA DEL CEO:** ¿B ahora, o C por fases? *(A no esta sobre la mesa.)* Y si B: levantar
`C-ESPEC-F2-F3`.

**RECOMENDACION TECNICA:** la evidencia permite B o C; **no la convierto en decision**. C encaja con
la estructura F1..F3 que el DP ya aprobo y con la regla del proyecto de incrementos pequenos.

**RIESGO SI NO SE DECIDE:** el titular de `ALERTA-006` sigue vivo — *con la parada de emergencia
armada, AURA sigue destruyendo datos del usuario*. **Es el bloqueo mas grave de los cinco.**

**DEPENDENCIAS:** `C-ESPEC-F2-F3`. **BLOQUEADOS SI NO SE DECIDE:** G-2 x3 y G-3 #4.

---

## D-M8-2 · Las tres entradas del catalogo

**HALLAZGOS AFECTADOS:** G-3 x3 — `permissions.py`. **Ubicacion unica.**

**GARANTIA:** `RN-2` — ninguna operacion no catalogada se ejecuta.

**CONTRATO:** `DP-D-M-8 §4.2` las **nombra literalmente**: *«Se añaden como minimo
`registrar_informacion_usuario`, `olvidar_informacion_usuario`, `refutar_informacion_usuario`»*.

**LO DETERMINADO:** las tres entradas, por nombre. **Esto es implementacion de contrato existente,
no ampliacion contractual** — el DP ya esta aprobado y el alcance de `D23` no se toca.

**LO NO DETERMINADO:** la **dimension `sujeto`**. El mismo §4.2 dice que *«la politica se resuelve
con el par (operacion, sujeto)»*, y `§7` asigna el catalogo con sujeto a **F3**. Añadir las tres
entradas sin el sujeto cierra los tres rojos pero **deja a medias la garantia**: seguiria sin
distinguirse borrar un temporal de borrar un hecho clinico.

**ALTERNATIVAS:**

- **A · añadir solo las tres entradas.** Toca `permissions.py`. Cierra G-3 x3 ya. Riesgo: rojos en
  verde con la garantia a medias — la forma exacta del patron «declarado != real».
- **B · añadir las tres junto con la dimension `sujeto`.** Toca `permissions.py` y quien consulte el
  catalogo. Cierra la garantia entera. Coste: es F3, y arrastra su dependencia.

**DECISION MINIMA DEL CEO:** ¿A ahora y `sujeto` en F3, o B de una vez?

**RECOMENDACION TECNICA:** la evidencia permite A o B. **Si se elige A, conviene que quede escrito
que G-3 en verde no significa RN-2 cumplida**, o dentro de tres sesiones nadie lo recordara.

**RIESGO SI NO SE DECIDE:** mutaciones del estado del usuario siguen ejecutandose sin catalogar.

**DEPENDENCIAS:** B depende de F3. **BLOQUEADOS:** G-3 x3.

---

## D-M8-3 · Semantica del borrado: auditoria y append-only

**HALLAZGOS AFECTADOS:** G-6 y G-7 — ambos en `modules/memory.py`.

**Comparten fichero y operacion (`olvidar`), pero NO son el mismo problema, y resolver uno no
resuelve el otro:**

| | G-6 · auditoria | G-7 · append-only |
|---|---|---|
| Pregunta | ¿queda constancia de QUE se perdio? | ¿se pierde? |
| Contrato | `§5.1` | `§5.2` |
| Determinado | **si**: `§5.1` enumera los campos — operacion, sujeto, `trace_id`, origen, resultado real e identificacion del objeto | **la direccion si**: `§5.2` declara `AlmacenReglas.desactivar` *«el modelo a imitar»* |
| Abierto | nada relevante | **si**: que significa «olvidar» |

**LO NO DETERMINADO — y el DP lo dice de su puño:** `§5.2` deja al CEO el matiz y se abstiene
expresamente: *«append-only en memoria implica que "olvida esto" no borra fisicamente del disco de
inmediato. Propuesta: baja logica inmediata + purga fisica diferida ("olvidar del todo"), que si
seria lista roja. **No lo decido aqui**»*.

**ALTERNATIVAS (solo para G-7; G-6 no las necesita):**

- **A · lapida sin purga.** Reversible y auditable. Riesgo: el usuario pide «olvida» y el dato sigue
  en disco — tension con `ADR-0017`.
- **B · lapida + purga fisica diferida** como capacidad de **lista roja** (`ADR-0003`: confirmacion
  humana siempre). Es la propuesta del DP. Coste: una capacidad nueva.

**DECISION MINIMA DEL CEO:** dos respuestas, y **pueden ir por separado**: (1) G-6 — ¿se implementa
el registro completo de `§5.1` tal como esta enumerado? (2) G-7 — ¿A o B?

**RECOMENDACION TECNICA:** **G-6 esta lo bastante determinado para ejecutarse en cuanto se levante
la zona**; no requiere eleccion, solo autorizacion. G-7 si requiere elegir.

**RIESGO SI NO SE DECIDE:** lo borrado no es reconstruible y `INV`/`ADR-0023` (append-only) se
incumple en memoria.

**BLOQUEADOS:** G-6, G-7.

---

## G-3 #4 · `test_g3_el_olvido_se_ejecuta_sin_estar_catalogado`

**NO necesita decision propia.** Es `D-M8-1` visto por su efecto: la operacion no esta catalogada
**y aun asi muta el disco**. Catalogarla (`D-M8-2`) sin enrutarla la dejaria denegada en un catalogo
que nadie consulta. **Se cierra sola cuando se resuelva `D-M8-1`**; hasta entonces permanece
`PROPOSAL_ONLY`, que es lo correcto. *(Opcion A de las tres que planteo el encargo.)*

---

## G-1 x2 · YA TIENE DECISIONES REGISTRADAS — no se crean nuevas

`D-G1-1`, **`D-G1-2`** (*«aprobar la lista blanca inicial»*) y **`D-G1-3`** estan **abiertas en
`decisiones_pendientes`** y bloquean `G1-GREEN`. Aplico la regla de no repeticion: **no creo una
decision E.**

### ⚠ CONTRADICCION — no la reconcilio, la elevo

| Fuente | Dice | Evidencia |
|---|---|---|
| `D-G1-2` (registrada) | *«R-A: **0 entradas detectables**»* | `[LECT]` |
| `D-G1-3` (registrada) | *«G-1 detecta **0 de las 4 rutas** de ALERTA-006»* | `[LECT]` |
| Medicion de hoy | **R-A detecta 4 violaciones**, con fichero y linea, en `core/modelo_usuario.py` (95, 113) y `core/orchestrator.py` (1287, 1314) | `[EJEC]` |

Las cuatro que R-A senala hoy **son** las rutas que `D-G1-3` daba por invisibles. O el codigo cambio
—`D-G1-3` culpaba a que los `__init__` no anotan tipos—, o las notas quedaron desfasadas.
**No lo resuelvo por mi cuenta:** afecta a que decidio el CEO cuando escribio esas notas.

**DECISION MINIMA DEL CEO:** confirmar si `D-G1-2`/`D-G1-3` siguen describiendo el estado real antes
de decidir sobre ellas.

---

## Tabla de decisiones

| Decision | Hallazgos | Estado | Requiere CEO |
|---|---|---|---|
| **D-M8-1** · kill switch / motor unico | G-2 x3 (+G-3 #4) | A **descartada por contrato**; elegir B o C | **SI** |
| **D-M8-2** · catalogo de operaciones | G-3 x3 | 3 entradas determinadas; `sujeto` abierto | **SI** |
| **D-M8-3** · borrado, audit y append-only | G-6, G-7 | G-6 determinado; G-7 abierto (A/B) | **SI** |
| — · olvido sin catalogar | G-3 x1 | se cierra con D-M8-1; sigue `PROPOSAL_ONLY` | no |
| **D-G1-2 · D-G1-3** (ya registradas) | G-1 x2 | **CONTRADICCION que verificar antes** | **SI** |

**Ninguna de estas decisiones se puede tomar sin usted, y ninguna la he tomado.**
