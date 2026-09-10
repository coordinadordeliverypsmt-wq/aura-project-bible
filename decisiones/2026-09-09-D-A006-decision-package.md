---
documento: "Paquete de decisión — ALERTA-006: cierre técnico, exposición residual y reconciliación de G-1"
tipo: "Decision Package (1.1 §3.2.3)"
fecha: 2026-09-09
actualizado: 2026-09-09 (tras la ejecución de D-A006-1, D-A006-3, D-A006-4, D-A006-5 y la corrección del auditor)
mantenido-por: "APUS-5 (CTO)"
decide: "CEO (Mauricio)"
estado: "CERRADO. Las cuatro decisiones resueltas por el CEO el 2026-09-09; ver decisiones/2026-09-09-acta-cuatro-decisiones-ceo.md"
sobre: "milestones/m3-entry/ALERTA-006-BORRADO-SIN-MOTOR.md"
checkpoint: "3708e11d38ab9a4bbcbfb814fbc1c1ccbb293b8b"
---

# ALERTA-006 — Paquete de decisión

**Clasificación de evidencia** (D47): `[EJEC]` medido ejecutando · `[LECT]` leído · `[INFER]` deducido.

> **Historial de este documento.** Nació el 2026-09-09 como paquete **previo** a la ejecución, con las
> tres decisiones sin resolver. Ese mismo día el CEO aprobó D-A006-1, D-A006-2 (Opción B), D-A006-4 y
> D-A006-5, se ejecutaron, y apareció evidencia nueva al corregir el auditor de garantías. Esta versión
> lo reestructura para que quede **un único paquete coherente**. No está en git —el fichero nunca se
> commiteó—, así que su redacción anterior no es recuperable: se dice aquí en vez de dejarlo implícito.
> Lo que no se ha tocado es el documento de `ALERTA-006`, cuyo diagnóstico del 2026-08-03 sigue íntegro.

---

# Estado ejecutivo

| | Asunto | Estado |
|---|---|---|
| **A** | Defecto original de `ALERTA-006` — cuatro rutas destructivas fuera del motor | **RESUELTO TÉCNICAMENTE** `[EJEC]` |
| **B** | `orchestrator → memory.write` fuera del motor, con `PARADA` armada | **EXPOSICIÓN RESIDUAL ACOTADA.** Opción B adoptada y publicada en `ADR-0024`; **no autorizada**, delimitada |
| **C** | G-1 · Ruta Única de Mutación | **RECONCILIADO: R-A 0 · R-B 0** `[EJEC]` |
| **D** | Garantías declaradas sin red | **13 deudas ajenas reales**, no 588 falsos positivos `[EJEC]` |
| **E** | H6 · `programador.py` declaraba lo contrario de lo que hacía | **CORREGIDO**; la deuda documental que lo rodea, independiente |
| **F** | Construcción nueva | **DESBLOQUEADA el 2026-09-09**: *Cognición Local + Rendimiento*, perímetro en `DP-COGNICION-LOCAL-Y-RENDIMIENTO.md` |

**Las cuatro decisiones están resueltas** (acta del 2026-09-09). Sigue abierta **una sola cuestión menor**: qué
hacer con las 13 deudas ajenas de garantías — y no bloquea nada.

---

# ALERTA-006 original — estado técnico

**Las cuatro rutas denunciadas pasan por el Motor Único.** Verificado sobre el código `[LECT]`:

| Ruta del documento original | Símbolo | Evidencia |
|---|---|---|
| G-1 · M-01 borrado del modelo | `modelo_usuario.borrar` | `modelo_usuario.py:112` → `_por_el_motor` |
| G-1 · M-02 refutación | `modelo_usuario.refutar` | `modelo_usuario.py:128` → `_por_el_motor` |
| §1 rama 4 · crear automatización | `AlmacenReglas.crear` | `reglas.py:126-135` → `self._motor.ejecutar` |
| §1 rama 5 · cancelar automatización | `AlmacenReglas.desactivar` | `reglas.py:154-162` → `self._motor.ejecutar` |

Camino único declarado en `_por_el_motor`: `catálogo → sujeto → authorize → kill switch → motor →
ejecutor`. **Fail-closed en las cuatro**: sin motor inyectado no hay mutación (`return 0` / `return` /
`return False`). El propio código nombra lo que cerró — `modelo_usuario.py:119`: *«MIGRADA en F4. Antes
llamaba a `memoria.olvidar` directamente: sin motor, sin permisos y sin kill switch. **Ese era el
agujero de ALERTA-006**.»*

**Y G-1 ya no las reporta como violaciones** `[EJEC]`: `R-A = 0`, `R-B = 0`. Antes acusaba dos de ellas
por análisis nominal; eso quedó reconciliado (ver más abajo).

**Fijado por prueba:** `test_g1_ruta_unica.py::test_las_cuatro_rutas_de_alerta_006_ALCANZAN_el_motor`.

> **Conclusión técnica: el defecto tal como fue descrito no se reproduce y no puede reproducirse sin
> deshacer F4.** Eso es un hecho medido, no una opinión.

---

# Exposición residual — `memory.write`

**No es ALERTA-006.** Es un problema distinto, encontrado al auditarla, y se trata aparte.

```
orchestrator.py:1777   await self.memory.write(uid, kind, f"usuario dijo: {text}", {...})
```

**H2** `[EJEC]` — **no hay guarda de kill switch al inicio del turno.** `_sistema_detenido()` se
comprueba en **un solo punto** del orquestador (`:1218`) y solo para peticiones de olvido y refutación.
Un turno cualquiera con `PARADA` armada recorre la cascada entera y llega a `_finalizar_turno`.

**H3** `[EJEC]` — **`memory.write` no pasa por el motor, ni por permisos, ni por el kill switch.**
`write` está declarado **mutante** de `memory.py` en `architecture_manifest.toml`.

| | ALERTA-006 (original) | Exposición residual |
|---|---|---|
| naturaleza | **destruye** datos declarados del usuario | **crea** memoria conversacional |
| reversible | no: reescribía el JSONL sin lápida | sí: el dato puede olvidarse por el motor |
| dispara sin pedirlo | sí — *«se me olvida tomar la pastilla»* borraba un dato clínico | no |
| estado | **cerrado en código** | **acotado por `ADR-0024`**, no cerrado |

**Mitigación parcial ya en vigor** (Opción B aprobada, ejecutada): con `PARADA` armada solo se escribe
lo que `contracts.es_escritura_pasiva` declara pasivo — whitelist `{episodica, historico}`, fail-closed.
**Eso acota el residual; no lo cierra**, porque la pregunta de fondo —si `PARADA` debe impedir también
esa escritura— sigue siendo de semántica constitucional.

---

# D-A006-1 — Estado de ALERTA-006

**Hecho demostrado** `[EJEC]`: las cuatro rutas están migradas al motor desde F4 · G-1 no las reporta ·
`R-A = 0` · `R-B = 0` · el defecto original está **resuelto técnicamente**.

**Lo ejecutado:** se actualizó la cabecera de `ALERTA-006-BORRADO-SIN-MOTOR.md` con un bloque de cierre
fechado y la evidencia línea a línea. **El §1 en adelante quedó intacto**: es el diagnóstico del
2026-08-03 y reescribirlo falsificaría lo que se sabía entonces.

**Cierre de gobernanza — EJECUTADO el 2026-09-09**, autorizado por el CEO:

1. `CHECKLIST-CONTINUIDAD.md` §2 — el contador de alertas abiertas pasa de **1 a 0**, con la evidencia y
   la salvedad del residual en la misma celda.
2. `CHECKLIST-CONTINUIDAD.md` §7 — la ficha de `ALERTA-006` deja de decir «ALERTA ABIERTA — PRIORIDAD
   MÁXIMA» y dice qué se resolvió, con qué evidencia y **qué no se cierra con ella**.
3. `ALERTA-006-BORRADO-SIN-MOTOR.md` §1 — aviso fechado antes de la tabla de rutas: las columnas
   «¿Motor?» decían *No* cuando se escribieron y hoy dicen *Sí*. **La tabla no se corrige: se fecha.**

**Nada se borró ni se reescribió.** El diagnóstico del 2026-08-03 sigue íntegro, y el fichero está
versionado desde `58ba28f`. La frase que impide leer el cierre como «toda mutación está gobernada» está
en las tres anotaciones, no en una.

---

# D-A006-2 — Alcance de `PARADA` · **RESUELTA: OPCIÓN B**

> **Decidida por el CEO el 2026-09-09.** Registrada en **`ADR-0024`** y en el acta
> `decisiones/2026-09-09-acta-cuatro-decisiones-ceo.md` §D-2. `PARADA` bloquea las acciones del Motor
> Único y **no** es un apagado de la conversación. La decisión **no autoriza `memory.write` fuera del
> motor**: lo acota mediante la whitelist fail-closed de escritura pasiva y deja su tratamiento
> definitivo expresamente delimitado, no resuelto.
>
> El análisis que sigue se conserva **tal como se elevó**, porque es la base sobre la que se decidió.

> **¿`PARADA` debe impedir toda mutación del turno, o solo determinadas acciones y mutaciones?**

## La letra, y por qué no la resuelve

`kill_switch.py:1-2`, citando `Bible 5.3 §5`: *«Cuando está activado, **NINGUNA acción** se ejecuta.»*
Y `_sistema_detenido`: *«Bible 5.3 §5 y RN-3 dicen que cuando está activado NINGUNA acción se ejecuta,
**sin excepciones**.»*

**La palabra que decide es «acción», y en este proyecto no es neutra:** es vocabulario del `CATALOGO` de
`permissions.py` — lo que pasa por el motor con permisos y HITL. Escribir memoria conversacional **no
es una acción catalogada**. Por tanto:

- lectura **literal** → no obliga hoy a bloquear `memory.write`;
- lectura por **intención** (*«cómo se detiene todo»*, `5.3`) → sugiere que sí.

**Las dos son defendibles con el texto en la mano. Por eso es decisión y no corrección.**

## Evidencia

`H2` y `H3`, arriba, medidas. Y el estado vigente tras la Opción B: con `PARADA` armada se escribe lo
pasivo y **nada más** —verificado por `test_parada_escritura_pasiva.py`, que fija los dos lados: que lo
pasivo sigue funcionando y que lo no pasivo no ocurre—.

## OPCIÓN A — `PARADA` detiene el turno completo

| | |
|---|---|
| Compatibilidad con la Bible | Alta bajo la lectura por intención; exige aceptar que «acción» incluye escrituras pasivas |
| Componentes afectados | `orchestrator.on_turn` — una guarda al inicio, antes de la cascada |
| Impacto sobre memoria | Ninguna escritura con `PARADA` armada |
| Impacto sobre conversación | **AURA enmudece.** No diría ni que está detenida, si esa respuesta cierra turno |
| Tests que cambiarían | Los que hoy esperan respuesta con `PARADA` armada, incluido `test_parada_escritura_pasiva.py::test_con_PARADA_armada_la_escritura_pasiva_SIGUE_funcionando` y `::test_con_PARADA_armada_una_ACCION_del_motor_queda_bloqueada` |
| Riesgos | **`PARADA` deja de ser una parada de la ejecución y pasa a ser un apagado del producto.** El usuario pierde la superficie por la que preguntaría qué ocurre |
| ¿ADR? | **Sí.** Cambia la semántica publicada del kill switch |

## OPCIÓN B — `PARADA` bloquea ejecución, permite cierre conversacional — **vigente**

| | |
|---|---|
| Compatibilidad con la Bible | Alta bajo la lectura literal: ninguna *acción* se ejecuta |
| Componentes afectados | Ninguno nuevo: es lo implementado |
| Impacto sobre memoria | Se escribe solo lo declarado pasivo; `INCIERTO` y cualquier `kind` futuro, bloqueados |
| Impacto sobre conversación | AURA puede seguir diciendo que está detenida |
| Tests que cambiarían | Ninguno |
| Riesgos | **El residual de `memory.write` permanece.** La whitelist lo acota pero no lo elimina: un turno sigue escribiendo memoria con la parada echada |
| ¿ADR? | No para mantenerla. **Sí** si se quiere elevar la distinción «pasivo / ejecutable» a norma publicada |

**No elijo entre las dos.** Lo único que señalo, y ya está ejecutado, es que la Opción B **con la
distinción definida mecánicamente** es estrictamente mejor que la Opción B tácita: sin definición, cada
escritura futura la resolvería quien la escribiera, y así nacen las rutas alternativas que `ALERTA-005`
prohíbe.

---

# D-A006-3 — Reconciliación de G-1 · ejecutada

**La pregunta de fondo era:** ¿G-1 debe detectar *llamadas directas a símbolos mutantes* o *rutas de
mutación que no alcanzan la autoridad*? **La arquitectura responde lo segundo**, y la evidencia lo
demostró por sus dos extremos simultáneos:

- **falso positivo:** `orchestrator` llamaba a `crear` y `desactivar`, que **sí** pasan por el motor;
- **falso negativo:** `orchestrator` llama a `memory.write`, que **no** pasa por el motor.

**Un detector nominal se equivoca en las dos direcciones a la vez.** `ALERTA-005` no dice «no llames a
ciertos símbolos»: dice *«toda ejecución pasa por el motor único; ninguna ruta alternativa»*.

**Ejecutado:**

- `verificador_g1.operaciones_que_alcanzan_el_motor()` — una llamada deja de ser violación si el
  destinatario enruta por el motor. **Derivado del manifiesto y del código, no de una lista de
  excepciones**: si mañana `crear` deja de enrutar, R-A vuelve a acusarla sola.
- **Meta-prueba obsoleta corregida.** `test_las_cuatro_rutas_..._aparecen_como_violacion` exigía que el
  detector **encontrara** las cuatro rutas; reescrita como `..._ALCANZAN_el_motor`, que asevera la
  propiedad. *Una prueba que asevera la PRESENCIA de un defecto se vuelve falsa el día que el defecto
  se arregla.*
- **Exclusiones POR OPERACIÓN** (D-A006-4, aprobada): cuatro entradas `[[mutaciones.excluido]]` con
  `opera`, motivo y fecha — `computador` (`unlink`, `rename`), `programador` (`write_bytes`),
  `auditoria` (`open`, `replace`), `decisiones` (`open`, `replace`). **GRUPO A sin ampliar y `D-G1-2`
  sin tocar.** El verificador se extendió para que `opera` exima **solo lo nombrado**: una escritura
  nueva se sigue acusando, fijado por `test_la_exencion_por_operacion_NO_exime_las_demas_operaciones`.
- **`write` sigue fuera de R-A por nombre**, respetando la decisión medida del CEO del 2026-08-17
  (§4.5): incluirlo hundía la resolución de receptor del 100 % al 40 %, y los 12 casos irresolubles
  eran todos `f.write()` sobre ficheros. **Corrección de mi propio informe anterior**, donde escribí que
  G-1 «debería» señalarlo.

---

# G-1 después de la reconciliación

```
R-A : 0 violaciones
R-B : 0 violaciones
mutación g1-alcance-de-autoridad    : 3 detectados · 0 supervivientes
mutación parada-escritura-pasiva    : 5 detectados · 0 supervivientes
```

Los tres fallos permanentes del Quality Gate que venían de G-1 **están cerrados**. Eran: dos falsos
positivos del criterio nominal y una meta-prueba que medía el pasado.

---

# Auditor de garantías y deuda real

**Defecto encontrado y corregido** `[EJEC]`: `auditar_garantias` resolvía **todas** las rutas contra la
raíz del producto, de modo que daba `AUSENTE` a cuanto viviera en el plano de control, de comunicación o
del agente externo. El arnés ya sabía resolverlo —acepta `--raiz`—; el auditor no. **Era el patrón
«declarado ≠ real» cometido por quien existe para cazarlo.**

```
garantías rotas : 588  →  13
vigentes        : 970 de 983      (968/981 fue un estado intermedio, no el final)
```

**`588` NO es un baseline vigente. Era un artefacto del defecto:** 583 de las 588 eran el auditor
mirando en el plano equivocado.

**Atribución por fecha de las 21 roturas reales que aparecieron al destaparlo:**

- **8 las rompió el trabajo de esta sesión** → **corregidas**, re-ancladas con su motivo escrito.
- **13 son deuda ajena documentada** → fuera de alcance: 7 anclajes obsoletos de otros incrementos,
  5 huérfanos de `validador.py` (el fichero no existe en ningún plano) y 1 sin referencia previa.

**Dos garantías que no tenían red, ahora la tienen.** Al re-anclar, el arnés encontró `RV-M8` y `RV-M9`
**vivos**. La causa no era que faltara una prueba cualquiera: `test_basta_UN_criterio_incumplido` usa
`accion="x"` con `directorio=None`, y en ese caso **`alcance` falla siempre** — así que habría pasado
igual con los cuatro criterios de `D22` borrados. Aseveraba el agregado en vez del criterio. Se añadieron
dos pruebas con **base en verde** que aseveran *qué* criterio falló.

**`AUD-M2`** —invertir el defecto haciendo que la raíz por defecto fuera otra— **sobrevivía**: las dos
comprobaciones existentes seguían pasando mientras los 394 mutantes del producto dejaban de resolverse.
Cerrado con el **caso positivo** que faltaba. Mutación del auditor: **2 detectados · 0 supervivientes**.

> **Corrección de mis informes anteriores.** Repetí que «588 = baseline, sin regresión». El número no
> cambiaba, pero estaba **ciego justo al plano donde estaba trabajando**, así que comparaba dos cifras
> ciegas. Los 8 anclajes que rompí eran invisibles por eso.

---

# H6 — deuda independiente

`adapters/programador.py` abría con *«propone cambios VERIFICABLES, **no escribe ficheros**»* y tiene
tres `write_bytes`. El comportamiento siempre fue correcto —escribe, verifica y revierte si falla—; la
descripción no. **La primera línea quedó corregida.** No es una exposición de seguridad y **no pertenece
a ALERTA-006**: es el patrón «declarado ≠ real» del §5 de `CLAUDE.md`, y se deja registrado como deuda
documental propia. **No se toca más en esta misión.**

---

# Decisiones que requieren CEO

1. ~~**D-A006-2**~~ — **RESUELTA el 2026-09-09: Opción B**, publicada en `ADR-0024`.
2. ~~**Cierre de `ALERTA-006` como acto de gobernanza**~~ — **RESUELTO el 2026-09-09**: alerta formalizada
   como resuelta técnicamente; `CHECKLIST` §2/§3/§7 actualizados; el diagnóstico del 2026-08-03 conservado
   y fechado. Detalle de lo que NO se cierra con ella, en el acta §D-1.
3. **Cierre de `ALERTA-006` — texto original de esta entrada, conservado:** — retirarla de prioridad máxima y del registro de
   alertas activas, con las tres anotaciones de D-A006-1 y la frase que impide leerla como «toda
   mutación está gobernada».
4. **Las 13 deudas ajenas** — **ÚNICA que sigue abierta**: ¿se abren como trabajo, se declaran aceptadas,
   o los 5 mutantes de `validador.py` se retiran por apuntar a un fichero que ya no existe? No bloquea la
   siguiente inversión: el criterio de salida del DP solo exige no añadir deuda nueva.

**Ninguna recomendación de este documento es autorización de ejecución.**

---

# Trabajo explícitamente bloqueado

- ~~**Toda construcción nueva**~~ — **DESBLOQUEADA el 2026-09-09**: la inversión es *Cognición Local +
  Rendimiento del Razonador*. Perímetro en `milestones/m3-entry/DP-COGNICION-LOCAL-Y-RENDIMIENTO.md`.
- ~~**3 de las 5 fases de M3**~~ — **DESBLOQUEADAS**: `P1` resuelto como despliegue local con `HC-1` de
  referencia (acta §D-4).
- **`D-INT-1`** — integración de la rama a `main`.
- **El residual de `memory.write`** — por D-A006-2.
- **`test_limite_reintentos`** — fallo preexistente del plano de control, ajeno a este paquete.

---

# Invariantes

`_INTOCABLES` (4 entradas) · `_MATERIA_RESERVADA` (10) · `TODO_LO_DELEGABLE` (2 verbos) ·
`REVIEW_HABILITADO = False` · Motor Único como camino de ejecución (`ALERTA-005`) · Core como única
autoridad sobre los hechos (`ADR-0014`) · HITL en lista roja (`ADR-0003`) · kill switch fuera de banda
(`Bible 5.3 §5`) · `PARADA` **ARMADA** · `InProcessEventBus` sin sustituir por NATS · `main` intacta ·
fail-closed en las cuatro rutas migradas.

**Todos verificados sin diff respecto al checkpoint, salvo `architecture_manifest.toml`, que recibió
exactamente las cuatro exclusiones por operación que el CEO aprobó.**

---

# Estado Git

```
HEAD                     : 3708e11d38ab9a4bbcbfb814fbc1c1ccbb293b8b
origin/worktree-m3-entry : 3708e11d38ab9a4bbcbfb814fbc1c1ccbb293b8b
main / origin/main       : d933a08a48224a1711c89e4eb1a5210a11e9cef9
commits: 0 · push: 0 · PR: 0
PARADA: ARMADA
```

**Cero cambios de arquitectura. Cero cambios de autoridad.**
