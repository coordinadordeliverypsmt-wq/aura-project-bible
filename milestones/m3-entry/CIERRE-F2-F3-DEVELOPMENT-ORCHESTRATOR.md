# Cierre · `DP-DEVELOPMENT-ORCHESTRATOR` — **F2 + F3**, recuperación de estado y blindaje

**Fecha:** 2026-08-26 · **Rama:** `worktree-m3-entry` · **Commits:** 0 · **Push:** 0
**Alcance ejecutado:** recuperación del `estado.json`, blindaje de pruebas, **F2** (C3+C4) y **F3**
(C6+C7). **F4 y F5 aisladas por bloqueo contractual demostrado** (§5 de este documento).

---

## 1 · Recuperación del `estado.json` — parcial, y por eso declarada

La búsqueda fue exhaustiva `[EJEC]`: `git fsck --unreachable`, `git log --all` sobre la ruta,
ficheros `.tmp`, `find` en todo `$HOME`, y los **transcripts de todas las sesiones y subagentes**.

| | |
|---|---|
| **Conteos originales, verificados** | `trabajo_completado` **51** · `tareas_AUTO` **6** · `propuestas` **14** · `promociones` **0** — de salidas de verificación en transcripts `[EJEC]` |
| **RESTAURADO literalmente** | **9 de 51** entradas de `trabajo_completado`: `CP-1…CP-5`, `EXP-1`, `EXP-REPRO`, `DP-ORCH-DISENO`, `DP-CP-DISENO`. Contenido literal recuperado de un volcado en transcript, no reconstruido |
| **Reconstruido desde el CHECKPOINT** | `defectos`: `DEF-CUERPO-LIBRE`, `DEF-FLAKY-P2` |
| **Ids conocidos, sin contenido** | Las 6 `tareas_AUTO`: `CP-G4-BLOQUEADO-POR`, `CP-DCP8-ENTREGAR`, `AUTO-01-IDEMPOTENCIA-ENTREGA`, `SECCION-E-ALINEAR-DCP5`, `CP-G4B-APROBAR`, `DCP8-E2-NO-PROCEDENTE` |
| **PERDIDO** | 42 entradas de `trabajo_completado`, el **contenido** de las 6 `tareas_AUTO`, las 14 `propuestas` |

**`tareas_AUTO` NO se ha recreado.** Tengo los ids pero no su contenido, y fabricar entradas
ejecutables con contenido inventado sería exactamente lo que D34 e INV-9 prohíben —además de alterar
`tareas_AUTO`, que la orden prohíbe sin decisión aprobada—. Los ids quedan registrados como hecho
verificable dentro de `perdida_de_datos`, para que una restauración futura sepa qué buscar.

---

## 2 · Blindaje del estado — **dos capas, y la segunda repara**

El incidente lo causó una prueba que llamó a `guardar()` sin destino. Ahora:

1. **Intercepción** — `guardar()` consulta un centinela antes de escribir y falla **en el acto**, en
   la prueba culpable y su línea. Un fallo tardío ya demostró ser inútil: el incidente no salió a la
   luz hasta la regresión general.
2. **Huella + restauración** — se compara el `sha256` antes y después de **cada** prueba, y si
   cambió **se repone el fichero** desde el respaldo. Cubre lo que la intercepción no ve: un `open()`
   directo, un `shutil.copy`, un subproceso.

`autouse` en `conftest.py`, aplicado a la batería entera: una protección que hay que acordarse de
pedir no protege de un descuido, y esto **fue** un descuido.

**Ambas capas verificadas ejecutando** `[EJEC]`: una prueba desechable que escribía por `open()`
directo fue detectada, nombrada y el fichero repuesto.

---

## 3 · F2 (C3+C4) y F3 (C6+C7)

Se construyen como **un solo bloque vertical** porque F3 gobierna lo que F2 ejecuta: separarlas
dejaría a F2 decidiendo su propia política, que es justo lo que `§5` le prohíbe.

| Componente | Qué hace | Nunca (`§5`) | Cómo se garantiza |
|---|---|---|---|
| **C6 · Policy** | `politica-orquestador.toml`, mapa acción → nivel | ser escrita por C3/C4/C5 | `escribir_politica()` existe **para negarse** · `F23-M2` |
| **C7 · Presupuesto** | topes por tarea y por ciclo | inventar cuota | no expone «cuánto queda» de nada externo · `F23-M4/M5` |
| **C3 · Orchestrator** | bucle **finito**: leer → elegir → invocar → registrar | decidir política · editarse a sí mismo | `puede_tocar()` niega su código, su política y el Control Plane · `F23-M9/M10` |
| **C4 · WorkerAdapter** | sobre de `§7.1` + orden de `§7.2` + evidencia | ejecutar sin permisos declarados | fail-closed · `F23-M13/M14` |

### El orquestador arranca sin nada que ejecutar, y eso es lo correcto

El catálogo `AUTO` está **vacío**. No es un fichero a medio rellenar: `§25.3` (`D-ORCH-3`) dispone
que *«sin lista aprobada, **todo es `HUMAN`**»*, y esa decisión no consta tomada. `REVIEW` está vacío
por una razón más fuerte: **el nivel no existe** —ADR-0003 define dos listas, no tres— y crearlo es
`D-ORCH-2`, del CEO.

Rellenar esas listas para que «funcionase» habría sido concederle autonomía por la puerta de atrás.
El E2E demuestra **las dos mitades**: el flujo real, que se detiene en la decisión; y el flujo
completo bajo una política hipotética en `tmp`, que llega hasta el borde de la ejecución y **se para
en la puerta** — sin tocar la política real. La capacidad se demuestra sin concederla.

### Verificación

| Medición | Resultado |
|---|---|
| Control Plane | **279 passed** `[EJEC]` (F1 44 · F2/F3 23 · blindaje 11 · E2E 4) |
| Communication Plane · agente-externo | **180/5 skipped** · **20 passed** — sin cambios |
| `ruff` | **All checks passed** |
| **Mutación F1** | **35 detectados · 0 supervivientes · 0 NO_APLICADO** |
| **Mutación F2+F3** | **18 detectados · 0 supervivientes · 0 NO_APLICADO** |
| Quality Gate | **FAIL 5 / 1139 / 3** — idéntico al baseline, sin relación con este bloque |

---

## 4 · Tres GRAVES más, encontrados por auditoría independiente

La tercera auditoría —que en el bloque anterior no pudo ejecutarse por límite de gasto— encontró
**tres defectos graves**, todos ciertos:

| # | Hallazgo | Estado |
|---|---|---|
| **G1** | `guardar()`/`cargar()` no validaban `estado["tareas"]`: escribir el diccionario a mano y persistir fabricaba cualquier estado, **por debajo** de `validar_transicion` | **CERRADO** · `F1-M31/M32` |
| **G2** | Crear en `FAILED` → `WORKING` → `COMPLETED`, en 3 llamadas y sin autoridad humana, produce una tarea que nunca existió y consta terminada | **ACOTADO Y MARCADO** — ver abajo |
| **G3** | El destino por defecto de `guardar()` quedaba **horneado en la firma al importar**: quien se aislaba reasignando `ESTADO_POR_DEFECTO` seguía escribiendo el fichero real | **CERRADO** · `F1-M35` |

**G3 merece subrayarse:** fallaba exactamente el patrón que la gente usa **para protegerse**. Y el
propio centinela leía la global, así que una prueba que la reasignaba movía con ella el objetivo del
vigilante. Ahora el `conftest` fija la ruta real al cargar.

**G2 no se cierra, y decirlo es parte del entregable.** Exigir autoridad humana para completar
rompería el propósito entero del orquestador. El control que lo cierra de verdad es el criterio
**A12** —*«`COMPLETED` solo tras ejecutar el criterio mecánico, no tras la afirmación del Worker»*—,
que pertenece a **F4/F5**, hoy bloqueadas. Lo que sí se ha hecho hoy: que el rodeo **deje huella**.
Una tarea que aparece directamente en un estado de trabajo o terminal queda marcada
`creada_sin_origen`, y la marca **sobrevive** a `completar_tarea` (`F1-M33/M34`). La honesta no se
marca — sin ese contraste la marca no distinguiría nada.

**El límite estructural, dicho sin adornos:** dentro de un proceso, el código puede tocar su propia
memoria. La garantía fuerte no es el diccionario en RAM sino el **log append-only de F1**, que sí es
verificable. Lo que G1 añade es el **borde de persistencia**: lo que llega a disco lleva los campos
que solo pone el gobierno. Eleva la falsificación de trivial a deliberada, y la deja escrita.

---

## 5 · F4 y F5 — bloqueo contractual demostrado, no supuesto

| Fase | Qué la bloquea | Evidencia |
|---|---|---|
| **F4** | `§20` la hace depender de **`§25.2`** (`D-ORCH-2`): crear el nivel `REVIEW`, que *«no existe hoy»* en ADR-0003 —dos listas, no tres— y cuya habilitación *«solo el CEO puede conceder… nunca automáticamente»* | `D-ORCH-2` **no consta aprobada** en ninguna fuente `[EJEC]` |
| **F5** | El propio `§20` la marca **«Bloqueada»**: exige `§25.1` **+ enmienda de D24** | `D-ORCH-1` no consta aprobada, y la orden vigente es **«NO tocar D24»** |

Construirlas exigiría **crear autoridad nueva** —expresamente prohibido— o **enmendar D24**. Se
aíslan; todo lo demás se ha ejecutado.

`D-ORCH-3` sigue abierta pero **no bloquea F2/F3**: su efecto es que el catálogo `AUTO` nazca vacío,
que es el comportamiento que el contrato prescribe mientras no haya lista.

---

## 6 · Decisión nueva registrada — `D-ORCH-6`

**Contradicción documental verificada** en el propio DP: `§139` dice que el vocabulario de estados
*«se conserva íntegro»* y `§351` da a `WAITING_FOR_HUMAN` las salidas `("WORKING","FAILED")` — pero
**ningún estado lo declara como destino**, así que es inalcanzable desde el flujo. Sin menciones en
`adr/`, `docs/` ni `decisiones/` `[EJEC]`.

**No la resuelvo:** añadir un destino a la tabla es decidir sobre el flujo de gobierno. Opciones:
(a) destino de `WORKING` · (b) retirarlo del vocabulario · (c) dejarlo reservado. **Impacto hoy:
ninguno** — F2 y F3 no usan ese estado `[EJEC]`, así que la decisión se aísla y no detiene nada.

---

## 7 · Seguridad y gobernanza

| | |
|---|---|
| D24 · Bible · ADR · roadmap | **sin tocar** |
| `AURA_APPROVED` | vacío |
| OpenCode · Codex | **ausentes** |
| Procesos huérfanos · credenciales | **0** — las dos señales del barrido fueron falsos positivos verificados: el `pgrep` se autodetectó, y la «credencial» era la palabra *tokens* en un docstring sobre troceo de identificadores |
| El orquestador lanza procesos | **0** — `subprocess`/`Popen`/`os.system`: cero ocurrencias `[EJEC]` |
| Autoridad nueva | **ninguna creada**; `D-ORCH-6` registrada, no resuelta |
| `tareas_AUTO` | **no alterada** — ni siquiera recreada tras la pérdida |
| Commits · push | **0 · 0** — `HEAD` sigue en `790fafc` |

---

## 8 · Retorno sobre Tokens

El orquestador aún no ahorra trabajo humano —no puede, sin lista `AUTO`—, pero **el sobre de `§7.1`
sí ataca el consumo de contexto**: lleva punteros, no historia, y una prueba fija que no supere los
4 KB. Ese es el mecanismo por el que este DP reduce coste: no ejecutando más rápido, sino evitando
que cada tarea arrastre el proyecto entero.

Lo que sí ahorra ya: la recuperación tras caída y el log auditable eliminan la pregunta más cara al
retomar —*«¿esto llegó a terminar?»*—, que hoy se responde investigando a mano.
