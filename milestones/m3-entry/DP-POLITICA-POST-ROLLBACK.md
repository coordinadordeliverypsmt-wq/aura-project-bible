# DP · POLÍTICA DEL MOTOR TRAS UNA VERIFICACIÓN FALLIDA

> **Estado: PROPUESTA AL CEO.** Preparado por el CTO el 2026-09-21. No modifica la política vigente,
> no elige alternativa y no recomienda ninguna. Es evidencia para que el CEO decida.
>
> **Plano: DESARROLLO (proceso), no producto.** Esto gobierna `entorno/control-plane/`, el motor que
> construye AURORA. No concede ninguna capacidad a AURA ni mueve la métrica de gobierno 0/7. El
> README de ese plano lo dice sin rodeos: *«confundir "autonomía para desarrollar AURORA" con
> "autonomía de AURORA" sería el error más caro posible aquí»*. **Por tanto D23 —alcance del MVP
> cerrado— no aplica**, pese a que este fichero viva entre Decision Packages de producto.
>
> **Identificador: PENDIENTE DE ASIGNAR.** No existe familia de IDs para la línea del motor de
> autonomía (sí las hay para `D-CP-n`, `D-ORCH-n`, `D-M8-n`, `D-G1-n`…). Abrir familia nueva o
> continuar otra serie es convención de gobernanza y **corresponde al CEO**; sin ID, el acta que
> cierre esta decisión no tendrá a qué apuntar. Se deja el hueco declarado en vez de inventarlo.
>
> **Formato de 4 niveles (acta D3): no aplica.** Se declara en vez de omitirse en silencio, como
> hizo ALERTA-001. Aquí no hay compra ni alternativa de mercado que comparar: hay una política
> interna ya escrita en código.
>
> **La política vigente NO se ha tocado.** `motor_autonomia.py:137` sigue deteniendo el ciclo
> completo, y `test_una_VERIFICACION_fallida_detiene_y_revierte` —que está en HEAD y la fija— sigue
> intacta y en verde.

---

## 1 · Contexto

Cuando una tarea autónoma se aplica y su verificación falla, el ejecutor revierte el cambio y **el
motor detiene el ciclo entero**, aunque queden en cola otras oportunidades autorizadas que no
tienen ninguna relación con la que falló.

La justificación está escrita en el propio código, y es anterior a esta investigación
(`test_red_motor_autonomia.py`, en HEAD):

> *«El árbol roto es peor que no haber hecho nada, y seguir tras un fallo de verificación es apostar
> a que el siguiente cambio arregle el anterior.»*

Esa prueba monta dos ficheros disjuntos y afirma `ejecutadas == 0`.

**Precisión sobre qué demuestra esa prueba, y qué no.** Usa `verificacion=lambda: False`, es decir,
la verificación falla **siempre**: la segunda tarea habría fallado igual. Por tanto la prueba
acredita que **el ciclo se detiene**, pero **no** acredita que se detenga habiendo trabajo viable
pendiente, ni permite inferir qué contempló su autor. Eso último lo acredita la medición de §2 —una
tarea falla y la otra, que sí habría tenido éxito, no se intenta—, no este test. La distinción
importa: presentar la prueba como evidencia de intención sería análisis disfrazado de hecho.

**Precedente aprobado en el OTRO plano, que conviene tener delante.**
`milestones/m3-entry/DP-017-LIMITE-DE-REINTENTOS.md`, **aprobado por el CEO el 2026-08-10**,
resolvió el mismo dilema —agotar una tarea frente a detener el resto— **en el plano de producto**, y
lo resolvió en sentido *continuar*: su criterio de aceptación 4 dice *«el ciclo continúa con las
demás tareas: una escalada no detiene a AURORA»*. **No vincula a este plano** —son constantes,
ficheros y capas distintas (`_LIMITE_DE_REINTENTOS = 3` en `walking-skeleton/aura_skeleton/core/
decisiones.py:213`, frente a `TOPE_DE_REINTENTOS = 2` en `entorno/control-plane/planificador.py:136`)
y la asimetría puede ser deliberada: el producto no escribe en el árbol de código. Pero es el
precedente más directo que existe, y omitirlo empobrecía la decisión.

Ese mismo DP-017 §4 fija además la **doctrina aprobada sobre umbrales numéricos**, que gobierna la
alternativa D de §5: *«lo que hace al número defendible no es su valor, sino que sea VISIBLE y
AJUSTABLE […] una prueba lo fija de modo que cambiarlo obligue a declararlo»*. Concuerda con la
regla del CEO del 2026-08-04.

**No existe ADR, Decision Package ni acta que decida esto.** Se buscó en `adr/`, `decisiones/`,
`docs/` y `milestones/`: cero resultados. Hay una decisión de diseño vigente y documentada en
código, sin acto de gobierno que la respalde ni la revoque. Ese vacío es el motivo de este DP.

---

## 2 · Evidencia

Toda medida en sandbox aislado, sin tocar el árbol real, sin ejecutar `OP-100cc3d4e29a` y con
`PARADA` armada durante todo el proceso.

| Hecho | Medición |
|---|---|
| El rollback es **local a la tarea** | `autoconstruccion.ejecutar` lee `original` en el momento de **esa** llamada, no al inicio del ciclo. Una reversión nunca deshace el efecto de una tarea anterior ya aplicada |
| Las tareas llevan su contrato | `tarea["contrato"]` viaja desde el TOML: `cap["id"]` → `Oportunidad.detalle["numero"]` → `planificador.a_tarea` |
| El motor **no compara tareas entre sí** | No existe ningún punto del código donde dos tareas se contrasten. La información (`fichero`, `contrato`, `operacion`, `buscar`, `sustituir`) está en la tarea; nada la evalúa |
| Una tarea fallida cuesta **dos ciclos completos** | `TOPE_DE_REINTENTOS = 2`. Medido con dos contratos distintos: ciclo 1 y 2 gastados en la tarea que falla, ciclo 3 ejecuta la otra |
| El trabajo pendiente **se recupera** | En el ciclo 3, agotado el presupuesto de la fallida, la otra oportunidad se ejecutó correctamente (`ejecutadas=1`, `motivo='cola agotada'`) |
| El agotamiento **deja constancia** | Evento `presupuesto_de_tarea_agotado` con id, origen e intentos |
| El redescubrimiento por iteración protege dependencias reales | Medido con `eliminar_codigo_muerto`: al borrar un envoltorio, la siguiente vuelta descubre que su auxiliar quedó huérfano. **La seguridad frente a dependencias no la da la parada total: la da redescubrir** |

**Reproducibilidad de esta tabla (auditoría independiente, 2026-09-21).** Un auditor distinto del
autor reprodujo de extremo a extremo la fila del coste en ciclos —con una verificación dependiente
del contenido real, no un `lambda` fijo— y obtuvo exactamente lo declarado: ciclos 1 y 2 con
`revertidas=1, motivo='verificacion fallida'`, ciclo 3 con `ejecutadas=1, motivo='cola agotada'`.
**Dos filas quedaron sin reproducir por él**: la del redescubrimiento y el hallazgo de §4 sobre dos
contratos apuntando al mismo fichero. Ambas exigían escribir contratos TOML reales, fuera de su
mandato de solo lectura. Constan como medidas por el autor en sandbox aislado y como **consistentes
por inspección** —no existe ninguna función de comparación entre tareas—, pero **no** con doble
medición. Se deja dicho para que nadie las lea con más fuerza probatoria de la que tienen.

---

## 3 · Comportamiento actual

```
tarea A falla verificación
   → el cambio de A se revierte (local a A)
   → se registra `cambio_aplicado` con revertido=true
   → el ciclo se detiene: motivo_de_parada = "verificacion fallida"
   → las tareas B, C… NO se intentan, aunque sean independientes
   → hace falta una invocación externa nueva del motor para volver a intentar
```

`BLOQUEADA` y `DECISION_REQUIRED` **sí** dejan continuar el ciclo: detienen su frente y no el resto.
La parada total aplica solo a los estados que **llegaron a escribir y revertir** —verificación
fallida y objeciones del revisor—. La asimetría es deliberada.

---

## 4 · Hallazgo sobre contratos distintos

Clasificación: **B — INDEPENDENCIA NO DEMOSTRADA.**

El sistema distingue los contratos, pero **la distinción no establece aislamiento**:

- Dos contratos distintos **pueden apuntar al mismo fichero**. Medido: ambos salieron
  `OPORTUNIDAD_REAL`, el mecanismo **no lo señaló de ningún modo** —no hay campo ni evento de
  colisión— y con la verificación en verde **ambos se ejecutaron en el mismo ciclo**.
- Salieron bien **porque sus patrones caían en líneas distintas**, no porque nada lo garantizara.
- `simbolo` viaja vacío con `sustituir_texto`, así que no sirve como discriminador.
- La única frontera con evidencia es **`fichero`** — y no la aporta el contrato.

Medido únicamente con `sustituir_texto`, el único ejecutor constructivo activo. **No extrapolable**
a operaciones futuras.

---

## 5 · Alternativas descriptivas

Se describen; **no se elige ni se recomienda ninguna**.

**A · Mantener la parada total.** El ciclo se detiene ante cualquier reversión. Es lo vigente.

**B · Continuar solo con tareas de fichero disjunto.** Tras una reversión, seguir con las tareas de
la cola cuyo `fichero` no coincida con el de la fallida. Exigiría definir la comparación y un punto
donde hacerla —hoy no existe ninguno—.

**C · Continuar solo con tareas de contrato distinto.** Se enuncia porque fue la hipótesis que
originó la investigación.

**El hecho medido `[EJEC]`, que es lo único que este párrafo afirma:** dos contratos distintos
pueden apuntar al mismo fichero; se midió que ambos salieron `OPORTUNIDAD_REAL`, que el mecanismo
no lo señaló de ningún modo y que con la verificación en verde ambos se ejecutaron en el mismo
ciclo (§4). Es decir: **el criterio «contrato distinto» no establece aislamiento**. Ese hecho no
depende de ninguna interpretación.

**Lectura del CTO `[INFER]`, que el CEO no tiene por qué compartir.** A mi juicio ese hecho pone a
C en tensión con tres reglas ya aprobadas —ADR-0003 trasladado a este plano (*«ante la duda, no»*,
`planificador.py:178`, `review.py:421`, `contrato.py:312`), INV-9, y la regla del CEO del
2026-08-04 sobre valores que no se derivan del modelo—. **Lo marco como inferencia y no como
veredicto a propósito**: la medición es un hecho, la incompatibilidad con esas tres reglas es una
lectura mía, y confundir ambas cosas sería exactamente el defecto que este documento corrigió en su
§1. Queda dicho para que la elección se haga con ello delante, no para cerrarla.

**D · Reducir el coste sin cambiar la política.** Dejar la parada total y actuar sobre
`TOPE_DE_REINTENTOS`, que hoy hace que cada tarea fallida cueste dos ciclos completos. No cambia
qué se detiene; cambia cuánto dura.

**E · Hacer explícita la colisión de contratos.** Detectar y declarar que dos contratos apuntan al
mismo fichero, sin cambiar la política de parada. Cierra el hallazgo de §4 sin tocar §3.

---

## 6 · Consecuencias técnicas conocidas

**Lo que se rompería si se relajara la parada total:**

- `test_red_motor_autonomia.py::test_una_VERIFICACION_fallida_detiene_y_revierte` — está en HEAD,
  monta ficheros disjuntos y afirma `ejecutadas == 0` (con la verificación fallando siempre: ver la
  precisión de §1 sobre qué acredita y qué no).
- `test_red_ciclo_autonomo.py` — mismo patrón sobre el módulo hermano.
- `aura.py::codigo_de_salida()` — distingue la salida según `motivo_de_parada`; un consumidor
  externo (cron, operador) confía en ese código por ciclo.

**Lo que se rompería con la alternativa D, que el coste aparente no deja ver.** D se enuncia como
*«no cambia qué se detiene; cambia cuánto dura»*. Es cierto del comportamiento y **engañoso del
coste**: `TOPE_DE_REINTENTOS` no es una constante suelta. Verificado ejecutando `[EJEC]`:

- `test_red_presupuesto_de_tarea.py:160` — `assert plan.TOPE_DE_REINTENTOS == 2, "el tope no se toca
  en este incremento"`.
- `test_red_reintento_gobernado.py:89` — `assert pl.TOPE_DE_REINTENTOS ==
  inspect.signature(ag.ejecutar_tarea).parameters["max_intentos"].default`. **El tope está acoplado
  al valor por defecto de la firma de `agentes.ejecutar_tarea`** (`agentes.py:262`,
  `max_intentos: int = 2`), y hay una prueba que exige que sigan coincidiendo.

Cambiar el tope toca **cuatro ficheros** —`planificador.py`, `agentes.py` y las dos pruebas— y
rompe un contrato de firma. Las 13 pruebas implicadas están hoy en verde `[EJEC]`. Se deja dicho
porque el enunciado de D —*«cambia cuánto dura»*— sugiere un coste que la medición no respalda.

**Lo que NO haría falta construir:** el rollback local ya está garantizado y medido. Es el
prerrequisito de cualquier noción de disjunción, y ya existe.

**Lo que sí haría falta:** un punto donde comparar tareas. Hoy no hay ninguno, y crearlo es diseño
nuevo, no una línea.

---

## 7 · Preguntas técnicas abiertas

1. ¿Qué significa «disjunto» con precisión suficiente para un candado? `fichero` es la única
   frontera medida; `contrato` está refutado; `simbolo` no aplica.
2. ¿Qué pasa con dependencias que el AST no ve —imports dinámicos, reflexión, configuración
   externa—? El redescubrimiento protege lo que el AST alcanza, no más.
3. ¿Se extiende el criterio a operaciones futuras? Todo lo medido es con `sustituir_texto`.
4. ¿Debe la colisión de contratos sobre un mismo fichero bloquearse, declararse o permitirse?
5. ¿Cuál es el coste aceptable de una tarea fallida? Hoy son dos ciclos de todo el trabajo
   autorizado.

---

## 8 · DECISION_REQUIRED

> **¿Debe el motor continuar con las tareas restantes tras una verificación fallida, o seguir
> deteniendo el ciclo completo?**

**Por qué es del CEO y no trabajo técnico:** no falta capacidad ni autoridad —el rollback local ya
lo haría viable— sino la decisión sobre **cuánto riesgo de árbol inconsistente se acepta a cambio
de aprovechar el trabajo autorizado restante**. Es la frontera entre «el árbol roto es peor que no
haber hecho nada» y «detener todo desperdicia trabajo válido», y ninguna medición la resuelve.

**Qué instrumento portará la decisión, se elija lo que se elija.** Según
`docs/libro-01-gobernanza-y-metodo/1.2-sistema-adrs-gestion-cambio.md` §3, un ADR es **obligatorio**
para *«decisiones de seguridad, privacidad o autonomía (fronteras de datos, permisos, guardrails)»* y
para *«decisiones difíciles o costosas de revertir»*. Esta es exactamente una decisión de autonomía y
de guardrail. El siguiente número libre es **ADR-0025** `[EJEC]`; no se asigna aquí.

Y una consecuencia que conviene no pasar por alto: **también la alternativa A —mantener lo vigente—
requiere acto formal.** Hoy la política no tiene ninguno: vive en código y en una prueba de HEAD,
sin ADR, sin DP y sin acta. Ratificarla no es «no hacer nada»: es producir el ADR que documenta el
statu quo y cierra el vacío de gobierno que abrió este documento. La regla de oro de 1.2 §7 fija el
orden —`propuesta → ADR en proposed → gate del CEO → accepted → capítulos y CHANGELOG → solo
entonces código`— y prohíbe escribir código que dependa de un ADR aún en `proposed`.

---

## 9 · Retorno sobre Tokens

Exigido por el principio 8 del `estándar de trabajo — producto demostrable` (2026-07-28): *«debe
figurar en TODOS los Decision Package futuros»*.

**Lo que ya devolvió esta línea, con independencia de lo que se decida.** El trabajo que produjo este
DP cerró el verificador —sin él el motor no podía completar **ninguna** tarea—, ató cada tarea a su
contrato, blindó los eventos de autoridad, y dejó constancia del agotamiento de presupuesto, que
antes desaparecía en silencio. Eso es autonomía real: cada tarea que el motor completa sin
intervención ahorra un ciclo humano completo de contexto. El evento
`presupuesto_de_tarea_agotado` evita además la clase de investigación que costó esta misma sesión:
descubrir *por qué* una oportunidad autorizada dejó de intentarse.

**El coste medido del estado actual, como dato y no como argumento.** Con la política vigente, una
tarea que falla consume **dos ciclos completos** de todo el trabajo autorizado
(`TOPE_DE_REINTENTOS = 2`) y obliga a una invocación externa nueva por cada reversión. **Esta cifra
describe el statu quo; no es un cargo contra la alternativa A**, que puede ser exactamente el
precio correcto de un árbol que nunca queda inconsistente. No se ofrece la cifra equivalente de
ninguna otra alternativa, porque no se ha medido y estimarla sería ordenar las opciones por coste.

**Lo que NO se calcula aquí, a propósito.** No se estima el retorno en tokens de cada alternativa.
Hacerlo sería construir un argumento cuantitativo a favor de una de ellas, y este documento no
recomienda ninguna: la frontera que el CEO debe resolver es de **riesgo aceptado**, no de coste. Un
apartado de retorno que ordenase las opciones por ahorro estaría decidiendo por él con aspecto de
dato. Se deja dicho para que la ausencia no se lea como olvido.

**Reutilización:** cero componentes nuevos. Todo lo medido se apoya en el motor, el planificador y
el arnés ya existentes.

---

## 10 · Lo que esta propuesta no hace

No modifica `motor_autonomia.py`, no toca las pruebas que fijan la política, no amplía `DR-E`, no
retira `PARADA` y no ejecuta `OP-100cc3d4e29a`. No elige alternativa y no recomienda ninguna.

**Y no basta con responder la pregunta de §8 para que algo se construya.** Son dos actos distintos:
*elegir alternativa* y *autorizar el incremento que la materialice*. `CHECKLIST-CONTINUIDAD.md` §5.2
mantiene NO AUTORIZADO *«iniciar cualquier incremento nuevo sin decisión posterior a la revisión
estratégica»*, y el levantamiento del 2026-08-25 (`D-ORCH-5`) cubre solo la Línea B / Communication
Plane, no el motor de autonomía.
