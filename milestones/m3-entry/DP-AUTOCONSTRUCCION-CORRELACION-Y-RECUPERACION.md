---
documento: "Decision Package — autoconstrucción: correlación estable tarea→cambio y recuperación verificada"
fecha: 2026-10-26
estado: "DISEÑO COMPLETO (§11, decisión del CEO 2026-10-26: completar sin implementar), revisado por arquitecto-evaluador (§10 y §12). NADA implementado: autoconstruccion.py, review.py y los contratos normativos SIN cambios. Sin prototipo (se propone como siguiente paso aprobable). Requiere decisión del CEO"
complementa: "DP-RECUPERACION-TRAS-CAIDAS.md §10.3-§10.4 (límite resultado_ambiguo y atribución por orden) · DP-CANDIDATO-AISLADO-AUTOCONSTRUCCION.md (copia, diario y promoción atómica)"
evidencia: "[LECT] autoconstruccion.py, review.py, planificador.py del worktree (estado del 2026-10-26, tras aplicar la recuperación); [EJEC] log real leído en copia"
---

# DP — Correlación estable y recuperación verificada en la autoconstrucción

## 1. Problema, con evidencia

Hay dos defectos de **contrato de persistencia**, no de lógica, y un tercero que se encontró durante el análisis.

**D1 · Atribución por orden** `[LECT]`. Ningún evento enlaza una tarea con su resultado. La cadena real del log
(`seq` 1573-1577) es esta:

1. `tarea_planificada{id: TA-…}`
2. `veredicto_emitido{id: TA-…}`
3. `propuesta_registrada{id: P-018}`, sin la tarea
4. `propuesta_autorizada{id: P-018}`
5. `cambio_aplicado{id: P-018}`, sin la tarea

`planificador.resultado_de` atribuye el `cambio_aplicado` a la **última `tarea_planificada` anterior**. Es correcto solo
si hay un único escritor. El supervisor único por log (ya aplicado) lo garantiza **para el motor**, pero no para
`review.ejecutar_bajo_review` lanzado a mano (`review.py:606` → `ac.ejecutar`).

**D2 · Una recuperación no publica la verificación** `[LECT]`.

- `_promover` solo marca el diario `promovido` después de verificar en la copia (`efecto and sano`, L1300-1306) **y**
  de releer el vivo con `efecto_en` (L1066-1068).
- Sin embargo, `_resolver` (L952-957) publica un `cambio_aplicado` **sin** `efecto_verificado` ni
  `verificacion_sana`.
- Como «la duda nunca completa», la tarea recuperada queda `resultado_ambiguo`. Lo fija una prueba con xfail estricto
  en `test_red_reanudacion_tras_caida.py`.

**D3 · Carrera en el id de propuesta** (hallazgo de este análisis) `[LECT]`.

- `proponer` (L339-341) calcula `P-{n+1}` contando `propuesta_registrada` **fuera de cualquier cerrojo** y después lo
  registra.
- Dos escritores a la vez pueden emitir el **mismo** `P-NNN` para propuestas distintas.
- Consecuencia: `esta_autorizada` y `constaba` (L953) compararían propuestas ajenas.
- Para el motor lo neutraliza el supervisor único; para escritores manuales concurrentes, no.

## 2. Contrato propuesto

| # | Pieza | Propuesta | Dónde se toca |
|---|---|---|---|
| 1 | **Id de tarea estable** | La propuesta lleva `tarea` (el `id_tarea`, ya derivado y no correlativo) e `intento`, que es el `seq` de su `tarea_planificada`: único, monótono y protegido por la cadena de hash. **Todo intento tiene `tarea_planificada`**, también el manual (§10, C3) | **`motor_autonomia.py:142`** pasa el `seq` que ya devuelve `registrar_planificada` (un dato, no una ejecución); `review.ejecutar_bajo_review` lo recibe y lo pasa a `ac.proponer` |
| 2 | **Correlación de punta a punta** | `tarea` e `intento` viajan en `propuesta_registrada`, en el **diario** (claves opcionales nuevas) y en **cada** `cambio_aplicado`, ya sea normal, rechazado o recuperado (`_registro` y `_resolver`) | `autoconstruccion._registro`, `_promover`, `_resolver` |
| 3 | **Caída entre promover y registrar** | El diario `promovido` guarda además `efecto_verificado: true` y `verificacion_sana: true`, que **sí** son ciertos por construcción (L1300 y L1066-1068). También guarda los **valores reales** de `verificacion_aislada` y `ejecucion_confinada` (L1297-1298), que **no** son ciertos por construcción: fijarlos a `true` violaría INV-9. `_resolver` los **copia** al `cambio_aplicado` recuperado, junto con `recuperado: true`, `tarea` e `intento` | `_promover`, `_resolver` |
| 4 | **Sin atribución por orden** | `planificador.resultado_de` usa `(tarea, intento)` cuando el evento lo trae. **Solo** cae al orden en eventos anteriores al contrato | `planificador.resultado_de` y `_resultados_de` |
| 5 | **Promovido y verificado frente a promovido sin verificación** | Si los campos de verificación vienen copiados del diario, la tarea queda `completada` (y `recuperado: true` dice cómo se supo). Si el diario es anterior y no los tiene, se publica `verificacion_no_registrada: true` y la tarea **sigue** `resultado_ambiguo`, ahora con motivo explícito | `_resolver`, `planificador.estado_de` |
| 6 | **Id de propuesta sin carrera (D3)** | El `P-NNN` se calcula **y** se registra bajo un único `lock_estado`, **extendiendo** `registrar_evento_si` con un parámetro opcional que derive los `datos` dentro del cerrojo. **Sin primitiva nueva** (regla del CEO 2026-08-03, `CLAUDE.md:240`) | `control_plane.registrar_evento_si`, `autoconstruccion.proponer` |

**Lo que no se cambia:**

- el orden de promoción;
- el cerrojo de `autoconstruccion`;
- las 8 claves obligatorias del diario. Las nuevas son **opcionales**, pero el lector nuevo **sí** las valida con tipo estricto: booleanos `is True` o `is False`, `intento` entero y `tarea` con la forma `TA-…`. Si un valor está presente pero mal formado, se trata como ausente y el resultado queda `resultado_ambiguo`;
- PARADA, `review`, la autoridad y la norma «el motor no ejecuta».

## 3. Orden de operaciones y garantía ante caídas (con el contrato)

| Muerte tras… | Estado en disco | Qué hace la recuperación (idempotente) | Estado de la tarea |
|---|---|---|---|
| `tarea_planificada{intento: s}` | — | Nada | `interrumpida_reintentable` (contrato vigente) |
| `propuesta_registrada{tarea, intento}` | — | Nada | Ídem. La propuesta queda huérfana y sin autorizar, lo que es inocuo |
| Diario `preparado` | Original o candidato | Restaura el original | `interrumpida_reintentable` |
| Diario `promovido` (con verificación) | Candidato | Publica `cambio_aplicado{tarea, intento, efecto_verificado, verificacion_sana, recuperado}` | **`completada`** (antes, `resultado_ambiguo`) |
| `cambio_aplicado` publicado | Candidato | `constaba` se busca por `(tarea, intento)` o, en eventos anteriores, por la propuesta: no duplica | `completada` |
| Durante la propia recuperación | Diario intacto hasta registrar `recuperacion_al_arranque` (L961-962) | Se repite sin efecto doble | Igual |

## 4. Compatibilidad con los eventos históricos

- **Todos los campos son aditivos.** Los eventos anteriores no se reescriben (ADR-0023, log append-only).
- **Los lectores viejos ignoran las claves nuevas.** `_validar_diario` solo **exige** `_CLAVES_DIARIO` (L821-822), así
  que el código actual acepta un diario escrito por el nuevo. Por eso se puede **revertir aunque haya diarios
  pendientes**.
- **Los lectores nuevos tratan como opcionales las claves ausentes.**
  - Un evento sin `tarea` se atribuye por orden, igual que hoy.
  - En el log real eso es correcto: hay 6 tareas, todas con un único escritor. Medido en copia: el planificador vivo y
    el prototipo coinciden en las 6 (`DP-RECUPERACION-TRAS-CAIDAS` §10.3, B6).
- **Los ids `P-NNN` existentes no cambian.** La numeración continúa.

## 5. Pruebas que demostrarían el contrato (TDD; todas en sandbox)

1. **Cada `cambio_aplicado` lleva `tarea` e `intento`, y coinciden con su `tarea_planificada`.** Control: sin el
   cambio, faltan.
2. **Dos tareas intercaladas por dos escritores manuales** (sin el motor): cada resultado se atribuye a su tarea.
   Control: con el orden como único criterio, una se lleva el resultado de la otra.
3. **SIGKILL entre promover y registrar con un diario nuevo:** la tarea queda `completada`, con `recuperado: true`, un
   solo `cambio_aplicado`, intentos = 1. Quita el xfail estricto actual, que es precisamente su alarma.
4. **Lo mismo con un diario anterior** (sin campos de verificación): queda `resultado_ambiguo` con
   `verificacion_no_registrada: true`.
5. **Recuperación repetida tres veces:** un único `cambio_aplicado` y una única `recuperacion_al_arranque` por diario.
6. **Muerte durante la propia recuperación,** inyectada antes de `recuperacion_al_arranque`: la siguiente termina sin
   duplicar.
7. **D3:** dos `proponer` concurrentes, en procesos reales, obtienen ids **distintos**. Control: sin cerrojo, colisionan.
8. **Compatibilidad:** un log histórico real, en copia, da el mismo `estado_de` en todas sus tareas.
9. **Reversión:** un diario escrito por el código nuevo y recuperado por el código actual se resuelve sin
   `_DiarioInvalido`.
10. **Mutación:**
    - quitar `tarea` o `intento` del registro;
    - no copiar la verificación del diario;
    - volver a atribuir por orden;
    - calcular `P-NNN` fuera del cerrojo.

    Cada mutante debe morir. Y el **auditor de garantías** antes de aplicar: es la lección de `DP-RECUPERACION` §10.7.

## 6. Reversión

- **Revertir:** `patch -R` del diff. Los eventos ya escritos con campos nuevos se quedan, porque el log es append-only,
  y el código actual los ignora.
- **Diarios pendientes:** compatibles (§4). Aun así, se recomienda revertir con el directorio de estado de
  `autoconstruccion` vacío, comprobándolo con `recuperar()` en solo lectura bajo PARADA.
- **Sin migración de datos.**

## 7. Riesgos

- **El cambio toca `review.py` y `autoconstruccion.py`**, componentes con baterías de mutación previas. Riesgo de dejar
  garantías sin red, como en §10.7. Mitigación: ejecutar `test_garantias_vigentes` en la copia antes de aplicar.
- **La extensión de `registrar_evento_si`** (pieza 6, parámetro `derivar`; ya no es una primitiva nueva, §10 C5) amplía la API. Debe negar los eventos gobernados igual que
  `registrar_evento_si` y clasificarse en `NO_CONCEDEN_ESTADO`.
- **Los escritores manuales concurrentes** siguen siendo posibles. El contrato hace **correcta** la atribución, pero no
  los serializa. Opcionalmente, `review` manual podría tomar también `supervisor_unico`. Es una decisión aparte.

## 8. Retorno sobre tokens

Cierra el último caso en que una tarea **hecha** se ve como ambigua y exige revisión humana. Elimina la dependencia del
orden, que obligaba a razonar sobre la concurrencia en cada cambio futuro. Es menos intervención humana y menos
contexto para diagnosticar el log.

## 9. Decisión que se pide

1. Aprobar el contrato del §2, piezas 1-5. Alcance: `review.py`, `autoconstruccion.py` y `planificador.py`.
2. Aprobar la pieza 6 (D3) como extensión de `registrar_evento_si` (sin primitiva nueva), o aceptar D3 como residual mientras solo escriba el motor.
3. Autorizar después: un prototipo en copia aislada con TDD, mutación, auditor de garantías, revisión independiente y
   QG. Su aplicación al worktree será una decisión separada.

## 10. Revisión del `arquitecto-evaluador` (2026-10-26): ENCAJA CON CONDICIONES, incorporadas

| Condición | Cómo queda |
|---|---|
| **C1 · INV-9:** `verificacion_aislada` y `ejecucion_confinada` no son ciertos por construcción (L1297-1298, L1255) | Corregido en la pieza 3: se guardan y se copian los **valores reales**. Prueba adicional: un verificador heredado `bool` promovido y recuperado publica `verificacion_aislada: false` |
| **C2 · Alcance:** el motor descarta el `seq` (`motor_autonomia.py:142`) | Añadido al alcance. Pasar un dato no viola «el motor no ejecuta» (`CIERRE-MOTOR-DE-AUTONOMIA.md:22`); la guardia AST lo seguirá comprobando |
| **C3 · El escritor manual (D1) no tiene `intento`** | `review.ejecutar_bajo_review` **sin** `intento` registra antes su propia `tarea_planificada` mediante `planificador.registrar_planificada`, el mecanismo que ya existe, con identidad del ejecutor y comprobación bajo cerrojo. Así **todo** intento, automático o manual, tiene `seq`, recuperación e intentos contados, sin componente nuevo |
| **C4 · Validación de las claves opcionales** | Tipo estricto (pieza «lo que no se cambia», §2). Mutante adicional: aceptar un valor que solo se evalúe como verdadero |
| **C5 · Pieza 6 como primitiva hermana** | Sustituida por una extensión de `registrar_evento_si` |
| **C6 · El diario pasa a conceder `completada`** | **Analizado.** El diario vive **fuera del repositorio**, en `~/.local/state/aura/autoconstruccion/<sha16-del-directorio>` (L700-711), con directorios `0700`, propios (`_es_dir_propio`, L714-720) y sin enlaces. `_validar_diario` ya exige que el vivo coincida con `sha_candidato`. Forjar una `completada` exigiría escribir en ese directorio **y** que el fichero vivo fuera exactamente el candidato. Quien puede hacer eso ya puede escribir el log. Con el modelo de amenaza vigente (el worker sub-invocado no escribe fuera de su sandbox), el riesgo es **aceptable y declarado**. Mitigación adicional: `recuperado: true` hace auditable toda `completada` que salga de un diario |
| **C7 · Tensión con «evidencia del uso real»** (`CLAUDE.md:243`) | **Declarada.** En el log real no ha ocurrido nada de esto: 0 `recuperacion_al_arranque`, 0 colisiones de `P-NNN` y un solo escritor. **D2** se trata como deuda según `CLAUDE.md` §7 (pérdida de información: un trabajo hecho que se ve como dudoso). **D1** y **D3** son **preventivos**: solo serían reales con escritores concurrentes, que hoy solo hay a mano. El CEO puede aprobar solo D2 (piezas 2, 3 y 5) y dejar D1 y D3 como residuales declarados |

**Dato medido sobre el log real** (`[EJEC]`, en lectura): hay 12 `cambio_aplicado` y 7 `tarea_planificada`.

- 5 cambios (P-001 y P-008 a P-011) son **anteriores al planificador** (`seq` < 228) y `resultado_de` no los atribuye a
  ninguna tarea. Es correcto: nacieron a mano, sin tarea.
- Los otros 7 corresponden 1 a 1 a las 7 planificaciones.

**Deuda declarada que introduce:**

- una **lectura dual** permanente, por `(tarea, intento)` o por orden en eventos anteriores, para todos los lectores;
- el diario como fuente de una concesión, vigilada por `recuperado: true`.

**Reversibilidad:** sí, sin migración. Coste visible: una tarea que el código nuevo dejó `completada` por recuperación
volvería a verse `resultado_ambiguo` con el código anterior.

**Alcance actualizado:** `motor_autonomia.py` (un dato), `review.py`, `autoconstruccion.py`, `planificador.py` y la
extensión de `control_plane.registrar_evento_si`.

## 11. Diseño completo (decisión del CEO, 2026-10-26): D1, D2 y D3, sin implementar

### 11.1 Hechos observados frente a riesgos teóricos

| | Hecho observado `[EJEC]` / `[LECT]` | Riesgo teórico `[INFER]` |
|---|---|---|
| **D1** | Ningún evento enlaza la tarea con su `cambio_aplicado` (log real, `seq` 1573-1577). El motor ya está serializado por `supervisor_unico` | Un `review` manual concurrente con un ciclo atribuiría resultados por orden. **No ha ocurrido**: un solo escritor, 7 de 7 tareas bien atribuidas |
| **D2** | `_resolver` publica la promoción recuperada sin verificación (L952-957), y la prueba xfail estricta lo fija | En el log real hay 0 `recuperacion_al_arranque`. Sería pérdida de información (trabajo hecho que se ve como dudoso) en cuanto ocurra una caída en esa ventana |
| **D3** | `proponer` cuenta sin cerrojo (L339-341) | Dos `proponer` concurrentes generan el mismo `P-NNN`. En el log real, 0 colisiones entre 18 propuestas |

### 11.2 Invariantes

- **I1 · Correlación explícita.** Todo `cambio_aplicado` posterior al contrato lleva `tarea` e `intento`, y existe
  exactamente una `tarea_planificada` con ese `id` y `seq == intento`. **Prohibido** atribuir por orden un evento que
  traiga esos campos.
- **I2 · Un intento, un desenlace.** Para cada `(tarea, intento)` hay como máximo un `cambio_aplicado`. La
  recuperación lo busca por esa clave antes de escribir.
- **I3 · La verificación no se fabrica.** Los campos de verificación de un `cambio_aplicado` recuperado son **copia
  literal** de lo que `_promover` midió. Nunca son un valor por defecto `true`. Si falta un campo, la tarea queda
  `resultado_ambiguo` con `verificacion_no_registrada`.
- **I4 · Ids de propuesta únicos.** `P-NNN` se calcula y se añade bajo el mismo `lock_estado`.
- **I5 · Compatibilidad.** Un evento sin `tarea` ni `intento` se lee como hoy (por orden). Ningún evento existente
  cambia de estado al aplicar el contrato (comprobable sobre una copia del log real).
- **I6 · El motor sigue sin ejecutar.** El motor solo **transporta** el `seq` (`motor_autonomia.py:142` → L148). La
  guardia AST se mantiene.

### 11.3 Estados y transiciones del intento

`planificado` → `propuesto` → `autorizado` → `verificado_en_copia` → `diario_preparado` → `promovido` → **`registrado`**.

Desde cualquier estado anterior a `registrado`, una caída lleva a uno de estos dos caminos:

- **sin diario:** `interrumpida_reintentable`, por el contrato de `DP-RECUPERACION-TRAS-CAIDAS`;
- **con diario:** `recuperar` lo lleva a `registrado`, restaurando o confirmando.

| Desde | Evento | Hacia | Efecto en el log |
|---|---|---|---|
| — | `registrar_planificada` (devuelve `seq`) | planificado | `tarea_planificada{id, ejecutor}` |
| planificado | `proponer(tarea, intento)` bajo cerrojo (I4) | propuesto | `propuesta_registrada{P-NNN, tarea, intento}` |
| propuesto | `registrar_propuesta_autorizada` | autorizado | — |
| autorizado | verificación en copia, `efecto and sano` | verificado_en_copia | — (o `cambio_aplicado{revertido}` si falla) |
| verificado_en_copia | `_promover` guarda el diario | diario_preparado | — |
| diario_preparado | escritura atómica y relectura | promovido | diario: `promovido` más la verificación real |
| promovido | `_registro` | **registrado** | `cambio_aplicado{tarea, intento, verificación}` |
| promovido (con caída) | `recuperar` | **registrado** | `cambio_aplicado{…, recuperado: true}` y `recuperacion_al_arranque` |

### 11.4 Idempotencia y recuperación ante caídas

- `recuperar` busca un `cambio_aplicado` previo con la clave `(tarea, intento)`, o la propuesta en eventos anteriores
  al contrato (I2). Si existe, no lo duplica.
- El diario solo se borra **después** de `recuperacion_al_arranque` (L961-962). Una caída a mitad de la recuperación
  la repite sin efecto doble.
- **D3 se recupera solo:** si un proceso muere tras calcular `P-NNN` y antes de añadirlo, no queda nada, porque ambas
  cosas ocurren bajo un único cerrojo.

### 11.5 Pruebas de carrera (además de las del §5)

- **R1 · Propuestas concurrentes:** dos procesos reales llaman a `proponer` sincronizados con una barrera
  (`multiprocessing.Barrier`). Los ids tienen que ser distintos y la cadena del log, íntegra. **Control:** con el
  cálculo fuera del cerrojo, mutante obligatorio, colisionan en un número reproducible de ejecuciones.
- **R2 · Intercalado manual frente al motor:** un `review` manual y un ciclo del motor sobre tareas distintas e
  intercaladas. Cada `cambio_aplicado` se atribuye a su `(tarea, intento)`. **Control:** con la atribución por orden,
  falla.
- **R3 · Doble recuperación:** dos procesos llaman a `recuperar` sobre el mismo diario. El cerrojo no bloqueante de
  `autoconstruccion` deja actuar a uno solo, y queda un único `cambio_aplicado`.

### 11.6 Migración de registros antiguos

**No hay migración.** El log es append-only (ADR-0023): los eventos antiguos se leen con la regla de compatibilidad
(I5) y los nuevos traen los campos. Antes de aplicar, se ejecuta un recorrido de solo lectura sobre una **copia** del
log real que compare `estado_de` en todas las tareas, con el planificador actual y con el nuevo. Tiene que dar 0
diferencias.

### 11.7 Rollback

`patch -R`. Los eventos con campos nuevos se quedan y el código anterior los ignora. Los diarios nuevos son legibles
por el código anterior: `_validar_diario` solo exige las 8 claves (§4). **Coste visible:** las tareas que el código
nuevo dejó `completada` por recuperación vuelven a verse `resultado_ambiguo`.

### 11.8 Criterios de aceptación (todos `[EJEC]`, antes de proponer su aplicación)

1. Pruebas 1-10 del §5 y R1-R3, cada una con su caso de control. Primero RED y después GREEN.
2. Un mutante para cada invariante I1-I6, todos detectados, más los de las piezas del §2.
3. Auditor de garantías (`test_garantias_vigentes`): 0 garantías anteriores sin red (lección de
   `DP-RECUPERACION-TRAS-CAIDAS` §10.7).
4. Suite del control-plane en copia y QG en una exportación limpia.
5. Recorrido del log real en copia: 0 cambios de estado (§11.6).
6. Revisión independiente de código y de seguridad (el diario concede estado: C6).
7. Producción intacta (PARADA, `estado.json` y `eventos.jsonl`) antes y después.
8. La xfail estricta de `test_red_reanudacion_tras_caida.py` **pasa a xpass y se convierte en prueba normal**: es su
   alarma.

**Alcance de la implementación futura:** `motor_autonomia.py:142-148` (transporte), `review.py:526-610`,
`autoconstruccion.py` (`proponer`, `_promover`, `_registro`, `_resolver`), `planificador.py` (`resultado_de`,
`_resultados_de`, `estado_de`) y `control_plane.registrar_evento_si` (parámetro opcional `derivar`, sin primitiva nueva).

## 12. Segunda revisión del `arquitecto-evaluador` (2026-10-26): ENCAJA CON CONDICIONES. Correcciones al §11

| Hallazgo (`[LECT]`) | Corrección del diseño |
|---|---|
| **I1 era falso:** `autoconstruccion.ciclo()` (L1365, L1375) llama a `proponer` y `ejecutar` sin tarea | **I1 corregido:** todo `cambio_aplicado` de la vía **`review` o motor** lleva `tarea` e `intento`. `ciclo()`, una API pública sin llamante de producción (`review.py:434-437`), entra en el alcance: sus eventos llevan `tarea: null`, `intento: null` y `via: "ciclo"`, y el planificador **nunca** los atribuye a una tarea, ni siquiera por orden. Mutante: atribuir un evento `via: "ciclo"` |
| **I2 depende del cerrojo de `autoconstruccion`**, y el texto no lo decía | Se hace explícito: el `constaba` de `_resolver` (L953-957) y el registro normal (L1307-1318) ocurren bajo el mismo `_cerrojo`. **Mutante:** registrar fuera de ese cerrojo |
| **C3 cambia el `review` manual:** `registrar_planificada` exige `origen`, `accion`, `fichero` y `riesgo` (`planificador.py:241-242`) y puede lanzar `TareaNoElegible` | Se declara como **cambio de contrato** del `review` manual: puede rechazar una tarea no elegible (por ejemplo, porque otra ejecución está viva) y exige esos campos. Pruebas: rechazo de una tarea no elegible y de una tarea incompleta, ambos explícitos y sin efecto parcial |
| **Tabla del §11.3 incorrecta** | **Corregida en el §12.1** |
| **La prueba de C1 era irrealizable:** un verificador `bool` da `aislada = True` (`_verificar`, L1250-1262) | Se sustituye por una inyección de `ResultadoVerificacion(estado="sano", aislada=False, confinada=False)`: promovido, muerto y recuperado, publica `verificacion_aislada: false` y `ejecucion_confinada: false`. El mutante de C4 (aceptar un valor que solo se evalúa como verdadero) figura ahora **explícitamente** en el §12.2 |
| **«D3 se recupera solo» tenía un motivo equivocado** | Corregido: una muerte entre calcular y añadir no deja nada **porque el cálculo solo existe en memoria**. El cerrojo **no** recupera nada: garantiza la **unicidad** (I4). `derivar` no escribe, porque el cerrojo no es reentrante |
| **R1 y R2 no eran deterministas; R3 no tenía control** | Corregido en el §12.2 |
| **El criterio 5 no ejercita la lectura dual** (el log real tiene 0 recuperaciones y un solo escritor) | Se añaden **logs sintéticos** con caso recuperado, intercalado manual y `via: "ciclo"`, además del recorrido del log real |

### 12.1 Transiciones (sustituye a la tabla del §11.3)

| Desde | Paso (código) | Hacia | Efecto en el log |
|---|---|---|---|
| — | `registrar_planificada`, que devuelve `seq` (motor L142; `review` manual por C3) | planificado | `tarea_planificada{id, origen, accion, fichero, riesgo, ejecutor}` |
| planificado | `pedir_veredicto` (`review.py:579`) | revisado | `veredicto_emitido{id, cumple}`. Si no cumple → **objetada** (fin) |
| revisado | `proponer(tarea, intento)` bajo cerrojo | propuesto | `propuesta_registrada{P-NNN, tarea, intento}` |
| propuesto | `registrar_propuesta_autorizada` (`review.py:600`) | autorizado | `propuesta_autorizada{P-NNN}` |
| autorizado | `ejecutar` → `recuperar()` de diarios ajenos (L1150) | autorizado | posibles `recuperacion_al_arranque`. Si queda bloqueado → `PromocionesBloqueadas` (fin, requiere a una persona) |
| autorizado | verificación en copia | verificado_en_copia, o rechazo | si falla: `cambio_aplicado{revertido, motivo}`; si la verificación revienta: `cambio_revertido_por_error` (L1268-1272) |
| verificado_en_copia | `_promover_si_procede` (L1326-1350) | diario_preparado, o rechazo | rechazos con `cambio_aplicado{revertido}`: `diario_pendiente_ajeno`, `base_cambiada`, `promocion_revertida`; con excepción: `ParadaActiva` |
| diario_preparado | escritura atómica y relectura | promovido | diario `promovido` más la verificación **real** |
| promovido | `_registro` bajo `_cerrojo` | **registrado** | `cambio_aplicado{tarea, intento, verificación}` |

**Caídas y recuperación** (corrige la frase «con diario: `recuperar` lo lleva a `registrado`»):

- **diario `preparado`:** se restaura el original y se registra solo `recuperacion_al_arranque` (L947-951). La tarea
  queda `interrumpida_reintentable`, como dice el §3;
- **diario `promovido`:** se confirma y se pasa a **registrado**, con `recuperado: true`;
- **diario inválido o con contenido ambiguo:** **BLOQUEO** que exige a una persona (L936-937 y L958-960). Nunca
  `registrado`.

### 12.2 Pruebas y controles deterministas (sustituyen a R1-R3 del §11.5)

- **R1:** un gancho de prueba inyecta una **pausa entre leer y añadir** en `proponer`. Hay dos procesos, y el segundo
  arranca durante la pausa del primero. **Control** (mutante, con el cálculo fuera del cerrojo): el mismo guion produce
  la colisión **siempre**, no a veces.
- **R2:** el intercalado se **fuerza** con eventos de sincronización entre procesos. El segundo escribe su
  `tarea_planificada` justo después del `propuesta_registrada` del primero. **Control:** con atribución por orden,
  falla siempre.
- **R3:** dos `recuperar` sobre el mismo diario. Se comprueba que el segundo devuelve **`ocupado`** y que hay un único
  `cambio_aplicado` por `(tarea, intento)`.
- **C1:** `ResultadoVerificacion` inyectado con `aislada=False, confinada=False` → el evento recuperado publica `false`
  en ambos campos.
- **C4:** el mutante «aceptar un valor que se evalúa como verdadero en lugar de exigir `is True`» debe morir.
- **C3:** un `review` manual de una tarea no elegible → `TareaNoElegible`, sin propuesta ni efecto. Con campos
  incompletos → error explícito.
- **I1 `ciclo`:** un evento `via: "ciclo"` no se atribuye a ninguna tarea.

Todas se suman a los criterios del §11.8, cuyo criterio 5 se amplía con los logs sintéticos.


## 13. Matriz de cobertura frente a los requisitos del CEO (2026-10-26) y estados de D2

**Estado del documento:** diseño completo y revisado dos veces (§10 y §12). **No implementado ni autorizado.** Haber
documentado D1, D2 y D3 **no** autoriza a implementarlos.

### 13.1 D2: los cuatro estados que pide el CEO

La verificación **precede** a la promoción por construcción: la promoción solo se alcanza si pasa la guarda `if not (efecto and sano)` (L1301-1308; la llamada a
`_promover_si_procede`, que invoca a `_promover` (L1042), está en L1313), y el diario solo pasa a `promovido` (L1078)
después de releer el vivo (L1066-1068). Por eso «verificación
pendiente» **no es un estado del vivo**, sino de una promoción interrumpida **antes** de quedar registrada. Ninguna caída
convierte una verificación desconocida en una satisfactoria.

| Estado pedido | Qué es en el diseño | Cómo se observa | Desenlace |
|---|---|---|---|
| **Promoción realizada** | Diario `promovido` **con** la verificación real copiada (I3) | Diario en disco y, cuando se registra, `cambio_aplicado{tarea, intento, recuperado?}` | Recuperar → **verificación confirmada** |
| **Verificación pendiente** | Diario `preparado` (vivo a medio promover), o `promovido` **sin** los campos de verificación (diario anterior al contrato) | `recuperar()` en el motor antes de planificar; el motor para con «recuperacion pendiente» si hay bloqueo u ocupación | `preparado` → se **restaura** el original → `interrumpida_reintentable`. Sin campos → **resultado ambiguo** |
| **Verificación confirmada** | `cambio_aplicado` con `efecto_verificado is True`, `verificacion_sana is True` y `revertido is False`, ya sea normal o recuperado | `estado_de` → `completada` (monótona) | Fin |
| **Resultado ambiguo** | `cambio_aplicado` sin la verificación completa (`verificacion_no_registrada: true`), o un diario inválido (BLOQUEO) | `estado_de` → `resultado_ambiguo`; o `promociones_bloqueadas` | No elegible. **Requiere a una persona.** Nunca se reintenta automáticamente |

**Idempotencia** (I2): por cada `(tarea, intento)`, como mucho un `cambio_aplicado`. El diario se borra **después** de
`recuperacion_al_arranque`. Recuperar dos veces no duplica (R3).

### 13.2 Cobertura de cada requisito

| Requisito del CEO | Sección |
|---|---|
| D1 · `cambio_aplicado` identifica tarea e intento | §2 pieza 1-2; I1 (§11.2), acotado a la vía `review`/motor y con `ciclo()` marcado `via:"ciclo"` (§12) |
| D1 · prohibido atribuir por orden | I1, I5 y §2 pieza 4; mutante «volver a atribuir por orden» (§5.10) |
| D1 · contrato de eventos antiguos y nuevos | §4, I5, §11.6 (sin migración, recorrido de solo lectura del log real más logs sintéticos, §12) |
| D2 · el diario registra la verificación real | §2 pieza 3 (valores **reales**, C1), I3 |
| D2 · una caída no convierte lo desconocido en satisfactorio | I3 y §13.1 (sin campos → `resultado_ambiguo`) |
| D2 · los cuatro estados | §13.1 |
| D2 · sin duplicación al recuperar | I2, §11.4 y R3 (§12.2) |
| D3 · un único mecanismo de sincronización compatible | §2 pieza 6: `registrar_evento_si` + `derivar`, sin primitiva nueva (C5); I4 |
| D3 · carreras y pruebas deterministas | R1 con pausa inyectada entre leer y añadir, y control mutante que colisiona **siempre** (§12.2) |
| D3 · caída entre asignar y persistir | §12: el cálculo solo existe en memoria y el cerrojo muere con el proceso, así que no queda número huérfano. El cerrojo garantiza la **unicidad**, no la recuperación |
| Invariantes, transiciones, idempotencia y rollback | §11.2, §12.1, §11.4 y §11.7 |
| Criterios de aceptación y pruebas de carrera | §11.8 y §12.2 (incluidos C1, C3, C4 e I1 `ciclo`) |

**Defectos documentales corregidos en esta revisión:** ninguno en las secciones existentes. Se añade esta matriz, que
hace explícitos los cuatro estados de D2, que antes solo estaban implícitos en el §3 y el §12.1.
