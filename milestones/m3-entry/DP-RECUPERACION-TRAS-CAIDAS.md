---
documento: "Decision Package — Recuperación tras caídas: reanudar una tarea interrumpida sin duplicarla"
fecha: 2026-10-26
estado: "OPCIÓN C APROBADA COMO CANDIDATA (CEO, 2026-10-26). Condiciones cerradas en copia y APLICADA AL WORKTREE DE DESARROLLO el 2026-10-26 a las 11:52 (diff e2922963). SIN commit. Producción detenida por PARADA: el ciclo real no la ha ejecutado"
evidencia: "milestones/m3-entry/evidencia-cm2-s3-2026-10-25/reanudacion-tras-caida/"
diff: "PROPUESTA-reanudacion-final.diff (sha e292296372e13dc3, 7 ficheros, 1249 líneas). Historial: 2a2f616c → f06393f1 → 11bbbfaa → 4ecaa278 → a784091c → e2922963"
---

# DP — Recuperación tras caídas

## 1. Problema y evidencia reproducible `[EJEC]`

Se mató el proceso del motor con `SIGKILL` a mitad de la verificación
(`evidencia-…/ciclo-autonomo-aislado/ciclo_interrumpido.py`, sandbox fuera del repositorio).

- **Bien:** el fichero del proyecto queda intacto, porque el candidato estaba en la copia `aura-candidato-*`. El log
  está íntegro y `autoconstruccion.recuperar()` no encuentra nada ambiguo.
- **Mal:** todos los ciclos siguientes dicen «**cola agotada**» con 0 ejecuciones, y el trabajo **sigue sin hacer**.
  La tarea no se reintenta nunca y no se informa: es declarado ≠ real (INV-9).

**Causa raíz, confirmada por el código y las pruebas.** `planificador.elegible` (árbol vivo, L177-195) trata «planificada y sin
resultado» como **no elegible para siempre** («puede estar corriendo»), y `tarea_planificada` no contiene nada que
permita saber si el proceso que la planificó sigue vivo. El cerrojo de `autoconstruccion` (L1311) solo cubre la
promoción, no la verificación. La hipótesis de partida queda **confirmada**.

## 2. Contrato de estados de la tarea

| Estado | Condición | ¿Elegible? |
|---|---|---|
| `nunca` | Sin `tarea_planificada` | sí |
| `en_curso` | Planificada, sin resultado, **ejecutor vivo** | **no** (no se duplica) |
| `completada` | `efecto_verificado`, `verificacion_sana` y `not revertido` | no |
| `revertida_reintentable` | Resultado revertido, intentos < tope | sí |
| `interrumpida_reintentable` | Planificada, sin resultado, **ejecutor muerto** (o en otro arranque o con el PID reutilizado), intentos < tope | sí, y **consume intento** |
| `agotada` | Revertida o interrumpida con los intentos agotados (tope 2) | no; **observable por `estado_de`**. Ver la nota de abajo |
| `elevada` | Planificada, sin resultado, y después `decision_requerida` de la misma tarea (M1) | no; espera una decisión humana |
| `esperando_revisor` | Planificada, sin resultado, y después `revision_sin_revisor_capaz` (M1) | no; esperar no es fracasar |
| `objetada` | Planificada, sin resultado, y después `veredicto_emitido` con `cumple` falso (M1) | no |
| `sin_resultado_historico` | Planificada **sin campo `ejecutor`** (constancia anterior al contrato) | no; conservador, como hoy |
| `resultado_ambiguo` | Hay resultado, pero ni completado ni revertido | no; ante la duda, no |

`planificador.estado_de(directorio, id)` devuelve uno de estos 11 estados. `elegible` es `estado_de(…) in {nunca,
revertida_reintentable, interrumpida_reintentable}`.

**Nota sobre `agotada` (corrección tras la revisión del arquitecto).** La primera versión de este DP decía «estado
explícito y observable». Solo es **observable consultando `estado_de`**: **no se registra como evento**. El evento que ya
existe, `presupuesto_de_tarea_agotado` (`motor_autonomia.py:149-181`), solo se emite en `motor_autonomia.py:136`, tras un
resultado **revertido**. Una tarea agotada por **interrupciones** nunca llega a esa línea: los dos intentos mueren antes y
el tercero ya no es elegible. Registrarlo exige tocar `motor_autonomia`, que está protegido. Queda pendiente de autorización
(§8).

**Más reglas del contrato, añadidas tras la revisión independiente:**

- **Por intento (M4).** `resultado_de` solo atribuye el resultado posterior a la **última** `tarea_planificada` de la
  tarea. Un intento vivo tras uno revertido está `en_curso`; no hereda el resultado del anterior.
- **/proc ilegible no es muerte (M2).** Si no se puede leer `/proc/<pid>/stat` por un error distinto de «no existe», el
  ejecutor se da por **vivo**. Ante la duda, no se duplica.
- **`hidepid=2` (segunda revisión).** Un pid ajeno vivo **no aparece** en `/proc` (ENOENT). Por eso un ENOENT se contrasta
  con `os.kill(pid, 0)`: solo `ESRCH` prueba la muerte, y `EPERM` significa que el proceso existe. **Límite conocido:** con
  `hidepid=2` y un pid ya reutilizado por otro proceso, la tarea se ve `en_curso` hasta el siguiente arranque. Es el lado
  conservador: no hay duplicado, solo espera.
- **Stat malformado = duda (B2).** Si falta el campo 22, se trata como desconocido, es decir, vivo.
- **Zombi = muerto (B3).** Un proceso en estado `Z` ya no ejecuta nada.
- **Identidad incompleta = sin identidad (B1).** Si falta el starttime o el `boot_id`, no se registra `ejecutor`: la tarea
  cae en `sin_resultado_historico` (conservador) en lugar de quedar `en_curso` para siempre.

## 3. Alternativas consideradas

| Alternativa | Por qué no, o por qué sí |
|---|---|
| A. Solo el PID | **Insuficiente.** El PID se reutiliza, y un proceso ajeno con ese PID haría creer que la tarea sigue en curso |
| B. PID + starttime | Insuficiente tras un **reinicio**: el starttime cuenta desde el arranque y puede repetirse |
| **C. PID + starttime + `boot_id`** (recomendada) | Identifica un proceso concreto de un arranque concreto. Sin dependencias, en `/proc`, y coherente con `herramientas/mutar.py`, que ya usa pid + starttime |
| D. Latido o arrendamiento con caducidad | Necesita un proceso que renueve el arrendamiento y un umbral temporal, que es un número no derivable del modelo (regla del CEO 2026-08-04). Es más complejo sin ganar fiabilidad local |
| E. Cerrojo `flock` mantenido durante toda la ejecución | Exige cambiar `autoconstruccion`, para ampliar el cerrojo a la verificación, y `motor_autonomia`. El cerrojo muere con el proceso, lo que es elegante, pero toca componentes protegidos |
| F. Marcar a mano «interrumpida» desde un supervisor externo | Reintroduce el factor humano para algo deducible del estado |

## 4. Opción recomendada: C, más comprobar y añadir bajo el cerrojo del log

1. `registrar_planificada` añade `datos.ejecutor = {pid, inicio, arranque}`, que es un **campo nuevo y aditivo**.
2. `registrar_planificada` **comprueba la elegibilidad y añade el evento dentro de `cp.lock_estado`**. Si dos
   supervisores ven la misma tarea interrumpida, el segundo recibe `TareaNoElegible`, de modo que **nunca hay dos
   ejecutores**.
3. `elegible` y `estado_de` deciden según el contrato del §2.
4. `registrar_planificada` se declara en `control_plane.NO_CONCEDEN_ESTADO`, porque registra la intención y no concede
   COMPLETED. Lo exigen los guardianes `test_red_auditoria_2/3`.

**Lo que no se cambia:** `motor_autonomia`, `ciclo_autonomo`, `autoconstruccion`, el formato de los eventos
existentes y la proyección de estado.

## 5. Compatibilidad con los eventos históricos

- **No hace falta migrar.** Las `tarea_planificada` antiguas, sin `ejecutor`, siguen siendo `sin_resultado_historico`
  y **no elegibles**, el mismo comportamiento que hoy. El historial real no se reescribe.
- **Medido `[EJEC]`, en solo lectura, sobre el log real** (2026-10-26): hay 6 tareas planificadas, **0 sin resultado**
  y 0 con campo `ejecutor`. Ninguna tarea real queda atascada ni cambia de estado al aplicar el contrato.
- **Riesgo residual, aceptado:** una tarea histórica interrumpida antes del contrato sigue atascada. Si existiera,
  requeriría un `review` humano explícito, que no se automatiza.

## 6. Caídas en los bordes

| Instante de la caída | Qué pasa |
|---|---|
| Antes de `tarea_planificada` | No hay rastro: la tarea sigue `nunca` |
| Durante la verificación (el caso medido) | `interrumpida_reintentable`; el proyecto, intacto, porque el candidato estaba en la copia |
| Entre verificar y promover | El diario de `autoconstruccion` en estado `preparado`; `recuperar()`, que se llama al inicio de cada `ejecutar`, restaura o descarta |
| Entre promover y registrar `cambio_aplicado` | El diario en estado `promovido`; `recuperar()` registra el `cambio_aplicado` que falta. Queda un riesgo de orden, en §8 |
| Durante la propia recuperación | El segundo intento interrumpido consume presupuesto y la tarea queda **`agotada`**, sin bucle y observable por `estado_de`; todavía no deja evento (§2). La prueba `test_dos_interrupciones_AGOTAN_y_queda_explicito` y el mutante RC5 lo cubren |
| Reinicio de la máquina | El `boot_id` es distinto, así que todo ejecutor anterior está muerto. Prueba de reinicio y mutante RC2 |

## 7. Pruebas de aceptación (en copia), con resultados `[EJEC]`

**Estado final (2026-10-26, tras la revisión independiente):**

- **21 pruebas** en `test_red_reanudacion_tras_caida.py`: las 12 originales más M1 (3 parámetros), M2, M4, B1 y B3
  (starttime, zombi, espera del cerrojo ≥1 s). **RED:** 6 fallaban antes de las correcciones. **GREEN:** 33 passed, junto
  con `test_red_reintento_gobernado.py`.
- **Suite del control-plane en la copia: 1401 passed, 3 skipped, 2 failed.** Los 2 fallos son
  `test_red_capacidad_completada.py` (`KeyError 'sexta-fuente-estancamiento'`). Fallan **igual en la línea base sin
  prototipo** (`f3-suites-en-copia.log`: 1380 passed, los mismos 2 FAILED): están atados a la ruta real.
- **Mutación RC1-RC14** (antes de la segunda revisión): **14 detectados, 0 sobreviven, 0 no aplicados** (`mutacion-reanudacion-rc14.log`, EXIT=0). Una
  primera corrida dio 11 + **3 NO_APLICADO** (RC1, RC3, RC7): sus patrones seguían el código anterior a las correcciones.
  Se reescribieron para las **mismas garantías**, sin rebajar ninguna, y se conserva el log
  (`mutacion-reanudacion-rc14-primer-intento-3-no-aplicados.log`).
- **Higiene de la E2E.** El SIGKILL impide a `autoconstruccion` borrar su copia `aura-candidato-*`. Antes caía en el
  `/tmp` del sistema: se midieron 46, de 28 KB y con contenido de sandbox, procedentes de las corridas de hoy. No es una
  fuga del producto: `autoconstruccion` ya barre las copias propias huérfanas de más de 1 h (L870-895). La prueba fija
  ahora `TMPDIR` a su `tmp_path` y comprueba que la copia huérfana queda ahí (RED → GREEN). Durante las 14 corridas de
  mutación no apareció ningún residuo nuevo.
- **Secuencia de 10 pasos repetida con el prototipo final** (`secuencia-recuperacion-prototipo-final.log`): rc −9 →
  `interrumpida_reintentable` con el fichero intacto → el supervisor nuevo la completa → 1 promoción → la segunda
  ejecución hace 0. `estado.json` real sigue en `9a7b5841…`, `eventos.jsonl` real en 3715 líneas, PARADA presente.
- **El diff reproduce la copia byte a byte** sobre un export del vivo, y `patch -R` lo deja idéntico.

**Segunda revisión independiente (`code-reviewer`): APTO CON CONDICIONES.** M1, M4, B1 y B3 están verificados con
control, sin regresiones ALTAS ni CRÍTICAS. Tratamiento de sus hallazgos:

| Hallazgo | Tratamiento `[EJEC]` |
|---|---|
| MEDIO: `hidepid=2` confundido con la muerte | **Corregido** con `_existe` (`kill(pid, 0)`). RED → GREEN, con prueba de control (un pid muerto con ENOENT sigue interrumpido). Mutante **RC15** |
| MEDIO: «agotada» sin evento, y la cabecera de la prueba decía «se dice» | **Afirmación corregida** en la prueba y en el DP (§2). El evento exige `motor_autonomia` (§8) |
| BAJO: el IndexError de B2 no tenía prueba | Prueba `test_B2_un_stat_MALFORMADO…`, mutante **RC16** |
| BAJO: la rama de inicio desconocido de B1 no tenía prueba | Prueba `test_B1_con_el_inicio_PROPIO_ilegible…` |
| BAJO: posible regresión de `completada` por M4 en logs heredados | **Medido sobre una copia del log real:** las 6 tareas dan idéntico `completada` y `elegible` con el planificador vivo y con el prototipo. El log real no cambió (sha `ab09f46f…` antes y después) |
| BAJO: `revisores.py:345-366` emite `veredicto_emitido` sin `cumple` | **Observación**, no deuda: esa tarea no se reconoce como `objetada` y cae en `en_curso` o `interrumpida`. Pasa a deuda si el motor autónomo usa esa vía |
| BAJO: coste (unas 5 lecturas del log por `estado_de`) | **Observación**: lineal, sin ningún disparador medido |

**Cifras finales:**

- **25 pruebas** en el fichero nuevo.
- **84 passed** en reanudación, reintento gobernado, motor_autonomia y auditoría 2.
- **Suite de la copia: 1405 passed, 3 skipped, 2 failed.** Los 2 fallos son los de la línea base
  (`suite-control-plane-copia-final.log`).
- **Mutación RC1-RC16: 16/16, EXIT=0** (`mutacion-reanudacion-rc16.log`). Ningún residuo nuevo en `/tmp`.

**Historial: primera versión, anterior a la revisión.**

- **`test_red_reanudacion_tras_caida.py`, 12 pruebas:**
  - identidad registrada;
  - terminación normal;
  - fallo recuperable;
  - ejecutor vivo (no se duplica);
  - ejecutor muerto;
  - PID reutilizado;
  - reinicio;
  - evento histórico;
  - agotada explícita;
  - dos supervisores;
  - replanificación;
  - **E2E con SIGKILL real** sobre el `motor_autonomia` de producción sin modificar.
  - **Resultado:** RED (12 fallan sin el prototipo), luego **12 passed**.
- **Regresión:** `test_red_reintento_gobernado.py` sigue verde. Suite del control-plane en la copia: **1392 passed,
  3 skipped**. Solo fallan los 2 tests de `test_red_capacidad_completada.py`, atados a la ruta real, que fallan en
  cualquier copia desde (w).
- **Mutación:** `mutaciones/reanudacion-tras-caida.toml`, RC1-RC7, **7/7**, en copia aislada.
- **Secuencia de 10 pasos** (`secuencia-recuperacion.log`): SIGKILL (rc −9), `interrumpida_reintentable` con el
  fichero intacto, nuevo supervisor que la completa, 1 promoción y la segunda ejecución sin repetir.
- **Producción intacta** en todas las ejecuciones: `estado.json` y `eventos.jsonl` con el mismo sha y las mismas
  líneas; PARADA real armada.

## 8. Riesgos y límites

- **Promovida pero sin `cambio_aplicado` registrado:**
  - el planificador la vería `interrumpida_reintentable` y la volvería a planificar;
  - `recuperar()`, al inicio del `ejecutar` siguiente, registra el `cambio_aplicado` pendiente, pero **después** de la
    nueva `tarea_planificada`;
  - `resultado_de` asocia ese resultado al intento nuevo, y la tarea queda `completada` sin volver a aplicar el
    cambio, porque el patrón ya no existe en el fichero;
  - el efecto es correcto, pero el intento queda contado de más;
  - **mitigación propuesta, no implementada** porque toca `motor_autonomia`: llamar a `recuperar()` antes de
    `descubrir`.
- **Deuda: `cp._registrar_sin_lock` usado desde el planificador.** Es una función privada de `control_plane`, y
  hace falta para comprobar y añadir dentro de un único `lock_estado`. Alternativa limpia: una primitiva pública
  `cp.registrar_si(directorio, tipo, datos, condicion)`, que tocaría `control_plane` más allá de `NO_CONCEDEN_ESTADO`. Se
  propone **aceptar la deuda** y registrarla, salvo que el CEO prefiera la primitiva.
- **«Agotada por interrupción» no deja evento** (nota del §2): requiere `motor_autonomia`.
- **`TareaNoElegible` en una carrera (M3)** se propaga desde `motor.trabajar`, que hoy no la captura: el segundo supervisor
  termina con una excepción. Es seguro, porque no duplica, pero es ruidoso. Capturarla también toca `motor_autonomia`.
- **Solo Linux** (`/proc`), igual que el confinamiento estricto.

## 9. Aplicación y reversión (cuando se autorice)

- **Aplicar**, desde la raíz del worktree:
  `patch -p1 < milestones/m3-entry/evidencia-cm2-s3-2026-10-25/reanudacion-tras-caida/PROPUESTA-reanudacion-tras-caida.diff`.
  Después: suite del control-plane, `herramientas.mutar …/reanudacion-tras-caida.toml --raiz ../entorno/control-plane`
  y el QG.
- **Revertir:** `patch -R -p1 < …`. No hay ningún dato que migrar.
- **Después de aplicar** (condición 5 del arquitecto): repetir la suite del control-plane **en el árbol vivo**,
  incluido `test_red_capacidad_completada.py`, que solo pasa en la ruta real.
- **Decisión que se pide.** El `arquitecto-evaluador` dictaminó **ENCAJA CON CONDICIONES**.
  1. Aprobar la opción C con el contrato del §2 y aplicar el diff. **Clasificación** frente a la regla «el desarrollo lo
     guía la evidencia del uso real»: el defecto está **reproducido y medido**, pero **no ha ocurrido** en el log real (0
     tareas sin resultado). Es una corrección **preventiva**, no un bloqueo observado, y el CEO decide si basta.
  2. Hecho: corregido el texto sobre «agotada» (nota del §2).
  3. Aceptar la deuda de `_registrar_sin_lock` o pedir la primitiva pública.
  4. Opcional, en `motor_autonomia`, que está protegido: capturar `TareaNoElegible` (M3), registrar «agotada por
     interrupción» y llamar a `recuperar()` antes de `descubrir` (riesgo de orden del §8).
  5. Repetir la suite viva al aplicar (arriba).

## 10. Cierre de las condiciones (decisión del CEO, 2026-10-26)

**Decisión del CEO:**

- Opción C aprobada como candidata.
- API privada no aceptada como contrato.
- Autorizado prototipar en copia los defectos de `motor_autonomia`.

**Norma comprobada antes de tocar el motor.** `CIERRE-MOTOR-DE-AUTONOMIA.md:22`: el motor «encadena y para, no ejecuta».
Lo vigila la guardia AST `test_red_motor_autonomia.py:390`: el motor no puede usar `write_text`, `unlink` ni `mkdir`, ni
importar `os`, `shutil` o `subprocess`, y tiene que pasar por `ejecutar_bajo_review`. Todos los cambios del motor la
respetan, y se añade una guardia más: de `autoconstruccion`, el motor **solo** usa `recuperar` y `ZonaProhibida`.
`recuperar()` es el **deshacer de una promoción ya gobernada** (ADR-0003), no una ejecución nueva.

### 10.1 Contrato final, con los estados pedidos por el CEO

| Estado pedido | Estado del contrato | Cómo se observa |
|---|---|---|
| No iniciada | `nunca` | `estado_de` |
| En ejecución verificable | `en_curso` (ejecutor `{pid, inicio, arranque}` vivo, o sin poder descartarlo) | `estado_de` |
| Completada con resultado persistido | `completada`, **monótona**: algún intento dejó efecto verificado y sano | `estado_de` y `completada` |
| Fallida y reintentable | `revertida_reintentable` | `estado_de` |
| Interrumpida y reintentable | `interrumpida_reintentable` (ejecutor muerto, otro arranque o pid reutilizado) | `estado_de` |
| Agotada y observable | `agotada` **más el evento** `presupuesto_de_tarea_agotado`, uno solo, **también por interrupciones** | log |
| En recuperación | El motor **no planifica** mientras `recuperar()` diga `bloqueado` (diario ambiguo) u `ocupado` (otro proceso recuperando): para con «recuperacion pendiente». Una promoción recuperada queda `resultado_ambiguo` (§10.4) | motivo de parada y `recuperacion_al_arranque` |
| Revertida | `revertida_reintentable` o `agotada`, con `cambio_aplicado.revertido = true` | log |
| Bloqueada por una condición de seguridad | `elevada` (`decision_requerida`: zona prohibida, materia reservada, review no habilitado) · `esperando_revisor` · `objetada` · PARADA (el motor no arranca) | `estado_de` y motivo de parada |
| Además | `sin_resultado_historico` (constancias anteriores al contrato) · `resultado_ambiguo` | `estado_de` |

Se conservan los 11 nombres del §2, porque cubren la lista del CEO sin crear un estado por inercia. «En recuperación» no
es un estado de la tarea, sino del ciclo: la recuperación es una propiedad del diario de `autoconstruccion`, y
duplicarla en el planificador sería la «segunda copia» que este proyecto ya ha pagado.

### 10.2 Orden de las operaciones y garantía ante una caída en cada punto

| # | Operación (quién) | Si el proceso muere justo después | Garantía |
|---|---|---|---|
| 0 | Tomar `supervisor_unico` (motor), **antes** de `motor_iniciado` | El `flock` muere con el proceso | Nunca hay dos ciclos sobre el mismo log. El rechazado deja `supervisor_rechazado`, fuera de los ciclos del observatorio |
| 1 | `recuperar()` antes de planificar (motor) | Es idempotente: confirma, restaura o bloquea; `constaba` evita duplicar `cambio_aplicado` | La siguiente vuelta lo repite sin efecto doble |
| 2 | `tarea_planificada` con su ejecutor, comprobando y añadiendo bajo `lock_estado` (`registrar_evento_si`) | `interrumpida_reintentable`, que consume intento | No hay duplicado: el mismo id no se replanifica si sigue vivo |
| 3 | Verificación en copia confinada (`autoconstruccion`) | El vivo queda intacto, porque el candidato estaba en la copia | Se reintenta dentro del tope y después queda `agotada` con evento |
| 4 | Diario `preparado` y promoción atómica, bajo el cerrojo de `autoconstruccion` | `recuperar()` restaura el original | El árbol nunca queda a medias |
| 5 | Diario `promovido` | `recuperar()`, **llamado por el motor antes de planificar**, registra el `cambio_aplicado` que faltaba | **Medido:** sin intento extra y una sola promoción. La tarea queda `resultado_ambiguo` (§10.4) |
| 6 | `cambio_aplicado` | El diario aún existe y `recuperar()` lo cierra; `constaba` impide duplicar | El log ya dice la verdad |
| 7 | `recuperacion_al_arranque` y cierre del diario | — | — |

### 10.3 Estado de cada condición

| Condición | Clasificación | Evidencia `[EJEC]` |
|---|---|---|
| A. `hidepid=2` (pid vivo oculto) | **Corregido** | `kill(pid, 0)` ante ENOENT; RC15 |
| A. PID inexistente, reutilizado, reinicio | **Corregido** (ya lo estaba) | RC1, RC2, RC3 |
| A. Identidad incompleta o malformada; **pid fuera de rango** (`2**40`, `0`, `-1`) | **Corregido** | Validación de rango antes de `/proc` y de `kill` (security A1); RC11, RC16, RC27 |
| A. `kill(pid, 0)` frente a un pid reutilizado | **Límite documentado y probado** | Con `hidepid=2` y un pid reutilizado, la tarea se ve `en_curso` hasta el siguiente arranque. Lado seguro: espera, no duplica (`test_LIMITE_hidepid_2…`). La carrera entre comprobar y ejecutar no existe: comprobar y añadir es atómico bajo `lock_estado` |
| A. Inicio sin resultado · resultado persistido con evento pendiente · evento con proyección pendiente | **Corregido o cubierto** | Interrumpida (E2E SIGKILL); §8 (E2E de promover y registrar); `estado.json` desfasado no cambia `estado_de` (prueba) |
| B1. Carrera de dos supervisores, terminaba en excepción (M3) | **Corregido** | Captura de `TareaNoElegible` → «tarea tomada por otro supervisor» (RC17) **y** supervisor único (RC25, RC26). Demo: dos procesos reales → uno trabaja y el otro para |
| B2. Intento de más si se promovió sin registro (§8) | **Corregido, y era peor de lo descrito** | Sin el arreglo, el cambio quedaba en disco **sin constancia en el log para siempre**, porque el patrón ya no existe y nada vuelve a llamar a `ejecutar`. Ahora: `recuperar()` en el motor (RC18, RC19) |
| B3. Agotada por interrupciones sin evento | **Corregido** | `_registrar_agotadas` (RC20, RC21) |
| B4. Cabecera de la prueba («se dice») | **Corregido** | Texto actual: «observable … y con evento» |
| B5. Función privada `_registrar_sin_lock` | **Corregido** | API pública `cp.registrar_evento_si`: comprueba y añade bajo cerrojo y **niega los eventos gobernados**, cosa que el escritor privado no hacía (RC14, RC22, RC23). El planificador ya no la usa (guardia AST) |
| B6. Logs heredados con `completada` | **Corregido** | `completada` monótona (RC24). Sobre una copia del log real, 6/6 tareas iguales con el planificador vivo y con el prototipo |
| B7. `revisores.py` sin `cumple` | **No reproducible en la vía del motor** | `review.py` no importa `revisores.py`; el motor usa `review.ejecutar_bajo_review` |
| B8. Coste de lectura | **Observación con disparador** | Medido: `estado_de` ≈ 97 ms, unas 2,2 lecturas del log, con 3719 eventos. Lineal en eventos × oportunidades × vueltas. Pasa a deuda si un despertar deja de caber en su ventana de cron; remedio: una sola pasada indexada por id |
| H1: el supervisor rechazado cortaba en el observatorio el ciclo legítimo (3.ª ronda) | **Corregido** | Cerrojo antes de `motor_iniciado`; el rechazado deja `supervisor_rechazado` en lugar de abrir o cerrar un ciclo. Prueba con el ciclo A abierto; RC29 |
| H2: «otro supervisor en curso» salía con código 2 en el cron | **Corregido** | Se añade a `aura.PARADAS_NORMALES`. Es el **7.º fichero** del diff (`aura.py`); RC30 |
| H3: `_PID_MAX` se lee al importar | **Límite documentado** | Si `pid_max` se sube en caliente, el resultado es conservador (espera) y se corrige al reiniciar el proceso |
| Atribución cruzada entre tareas distintas (code-reviewer, 2.ª ronda) | **Corregido para el motor**; residual documentado | Supervisor único por log. Otros escritores manuales del log (no el motor) siguen atribuyendo por orden: la corrección de raíz es estampar el id de la tarea en `cambio_aplicado` (toca `review` y `autoconstruccion`, con DP propio) |

### 10.4 Límite conocido: una promoción recuperada no consta como `completada`

`autoconstruccion.recuperar` (`autoconstruccion.py:956`) registra el `cambio_aplicado` recuperado **sin**
`efecto_verificado` ni `verificacion_sana`, aunque solo se promueve con `efecto and sano` (L1300-1306). La duda nunca
completa, así que la tarea queda `resultado_ambiguo`:

- no es elegible;
- no se repite;
- el log contiene `recuperacion_al_arranque` con `promocion_confirmada`.

Una prueba con **xfail estricto** espera `completada` y avisará en cuanto se corrija `autoconstruccion`. La corrección
(que el diario guarde `efecto` y `sano` y que `_resolver` los publique) queda **fuera del alcance autorizado** y necesita
su propia decisión.

### 10.5 Resultados del prototipo final, en la copia

| Comprobación | Resultado | Log |
|---|---|---|
| Pruebas de reanudación | 51 passed, 1 xfailed (estricto) | — |
| Suite del control-plane | **1429 passed, 3 skipped, 1 xfailed, 2 failed** | `suite-control-plane-copia-final3.log` |
| Mutación | **29 mutantes, 29/29, EXIT=0** (RC1-RC27 más RC29-RC30) | `mutacion-reanudacion-rc30.log` |
| Lint | `ruff` 0 en los 5 ficheros Python | — |
| Demo | Dos supervisores reales a la vez → uno trabaja y el otro para; §8 recuperada sin intento extra; agotada con un evento; la segunda ejecución hace 0 | `secuencia-cierre-final.log` |

- **Los 2 fallos de la suite** son de `test_red_capacidad_completada` y **dependen de la ruta, no del prototipo**.
  Comparados en dos copias, con y sin el diff, son idénticos (`comparacion-fallos-base/`). Su causa son las rutas
  absolutas del vivo en `capacidades/sexta-fuente-estancamiento.toml` (5), el filtro de ámbito de `formacion.py:145` y
  un id derivado de la ruta (`TA-4c50255a4c70`, que figura 5 veces en el log real).
- **Mutante RC28 no declarado:** es **equivalente**. `os.close` ya libera el `flock`.
- **Producción, antes y después de cada demo:** `estado.json` en `9a7b5841…`, PARADA presente.

### 10.6 Tercera revisión, verificación y aplicación al worktree `[EJEC]`

- **Verificación independiente de H1 y H2 (`code-reviewer`): APTO, sin condiciones.** 135 passed en reanudación,
  observatorio, despertador y estancamiento. `supervisor_rechazado` no necesita clasificarse: el descubrimiento de
  «eventos sin puerta» solo recorre `EVENTOS_GOBERNADOS`.
- **Observación técnica (§7 de `CLAUDE.md`), no deuda: un supervisor colgado queda oculto.** Si un proceso vivo pero
  bloqueado retiene el `flock` con su ciclo abierto, el observatorio dice TRABAJANDO indefinidamente y los rechazos
  salen con código 0. No es una regresión: un supervisor colgado ya era invisible antes.
  - **Pasa a deuda** si se observa un ciclo abierto durante más de un despertar con `supervisor_rechazado` repetidos.
  - **Remedio previsto:** una señal en el observatorio para «rechazos consecutivos con el ciclo abierto».
- **Aplicación, 2026-10-26 a las 11:52, lejos de los despertares de :00 y :30.** Se comprobó antes:
  - diff `e2922963…`, que aplica limpio y no estaba aplicado (el `patch -R --dry-run` falla);
  - ningún arnés ni ninguna prueba en curso.

  Resultado:
  - **copia previa** de los 5 ficheros en `evidencia-…/reanudacion-tras-caida/previos-a-la-aplicacion/`, con
    `SHA256SUMS`;
  - `patch` con exit 0, sin `.orig` ni `.rej`;
  - los 7 ficheros, **idénticos byte a byte** a la copia validada;
  - los cambios previos sin commit de `control_plane.py`, `motor_autonomia.py` y `planificador.py` se conservan, porque
    el diff se generó contra su contenido actual.
- **Después de aplicar, en el árbol vivo:**
  - el despertador del cron **importa** sin error, y `aura.PARADAS_NORMALES` incluye la parada nueva;
  - pruebas focalizadas: **217 passed, 1 xfailed, EXIT=0**;
  - **los 2 tests de `test_red_capacidad_completada`, que fallan en toda copia, PASAN en la ruta real.** Queda
    demostrado que su fallo en copia era de entorno;
  - `estado.json` sigue en `9a7b5841…`, `eventos.jsonl` en 3720 líneas, PARADA armada, y no se ha creado ningún
    `.supervisor.lock`.
- **Revertir:** `patch -R -p1 < evidencia-…/reanudacion-tras-caida/PROPUESTA-reanudacion-final.diff`, o restaurar
  desde `previos-a-la-aplicacion/` y verificar con `SHA256SUMS`. Ningún dato que migrar.


### 10.7 Quality Gate en el árbol vivo: un FAIL corregido y después PASS `[EJEC]`

- **QG 1 (11:52-12:12): FAIL.** 3841 passed, 1 failed: `test_garantias_vigentes`. El cambio había dejado sin red
  **3 garantías de incrementos anteriores**:
  - `motor-autonomia.toml:MOT-M16` («cada vuelta redescubre») y `MOT-M21` («la cola agotada sale con 0»): patrón
    ausente;
  - `f1-orquestador.toml:F1-M23` («un `estado_de_tarea` crudo no fabrica estado»): patrón duplicado por
    `registrar_evento_si`.
- **Corrección.** Se amplió cada patrón hasta que coincidiera una sola vez, con **la misma garantía y el mismo efecto**.
  MOT-M16 conserva la línea nueva en `sustituir`.
  - Diff: `evidencia-…/reanudacion-tras-caida/AJUSTE-garantias-previas.diff` (sha `5a432f64…`).
  - Copia previa de los dos toml en `previos-a-la-aplicacion/`.
  - Validación con el arnés, solo para esos 3 mutantes: **3/3 detectados**, EXIT=0
    (`mut-tres-garantias.log`).
  - Auditor de garantías: 4 passed.
- **QG 2 (12:15-12:25): PASS.** 3842 passed, 3 skipped, 17 xfailed, EXIT=0. Formato, lint, tipado, pruebas y contratos
  en OK. `estado.json` sin cambios; en el log real, solo `despertar_rechazado`.
- **Lección para el procedimiento:** validar en copia solo la suite del control-plane **no basta**. El auditor de
  garantías (`walking-skeleton/tests/unit/test_garantias_vigentes.py`) recorre las 1820 garantías declaradas de todo el
  repositorio y tiene que ejecutarse **antes** de aplicar cualquier cambio que toque código protegido por baterías
  anteriores.
- **Ficheros que cambian en el worktree:**
  - los 7 del diff final;
  - los 2 toml del ajuste (`walking-skeleton/mutaciones/motor-autonomia.toml` y `f1-orquestador.toml`).

  Todo **sin commit**.
