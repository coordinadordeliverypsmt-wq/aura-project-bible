# DP · DELEGACIÓN A SUBAGENTES ESPECIALIZADOS

> **Estado: CONSTRUIDA (CEO, 2026-09-21).** El CEO autorizó la construcción por misión expresa, y
> la pieza 19 existe y ejecuta: `entorno/control-plane/delegacion.py`, con 60 pruebas y 24 mutantes
> (0 supervivientes). Lo que sigue describe el análisis previo que llevó a ella; **se conserva sin
> reescribir** porque su valor es haber medido que 18 piezas ya existían y que solo faltaba una.
>
> **Lo que NO cambió al construirla, y es lo importante:** `crear_autoridad` sigue en
> `_MATERIA_RESERVADA`, `TODO_LO_DELEGABLE` sigue con sus dos verbos, `_INTOCABLES` sigue en 8 y el
> alcance de REVIEW no se amplió. La capacidad **presta** autoridad ya concedida —las capacidades
> `[auto]` de efecto lectura— y no crea ninguna.
>
> **Queda una `DECISION_REQUIRED` nueva, medida por una auditoría adversarial:** ver §13.

> **Estado del análisis previo: PROPUESTA AL CEO — presentaba un BLOQUEO, no un plan de construcción.** Preparado por el
> CTO el 2026-09-21. No implementa nada, no elige alternativa y no recomienda ninguna.
>
> **Conclusión adelantada, para que nadie tenga que leer doce secciones para encontrarla: no existe
> hoy autoridad para construir esta capacidad, ni en el plano de producto ni en el de desarrollo, y
> no hay ninguna parte de ella construible dentro de la autoridad vigente.** Este documento existe
> para que el CEO tenga delante lo que haría falta, no para pedir permiso de empezar.
>
> **Plano: afecta a los DOS, y ahí está la trampa.** Enunciada como «AURA crea subagentes», la
> capacidad vive en el PRODUCTO. Construible, solo lo sería en el plano de DESARROLLO
> (`entorno/control-plane/`). Confundirlos contaminaría el roadmap del MVP, así que el documento
> mantiene la distinción en cada sección.
>
> **Identificador: PENDIENTE DE ASIGNAR.** No hay familia de IDs para esta línea. Corresponde al CEO.
>
> **Este DP NO reclama `ADR-0025`.** Ese número está declarado como el siguiente libre para la
> política post-rollback (`decisiones/pendientes.md`). Tomarlo contaminaría una decisión abierta.

---

## 1 · Qué se propone, y por qué no es lo que parece

La dirección de largo plazo es que AURA pueda detectar una misión, decidir si la delega, crear un
subagente especializado y efímero con autoridad acotada, darle herramientas limitadas, permitirle
investigar —quizá con acceso a Internet—, trabajar en sandbox, producir artefactos, ejecutar
pruebas, devolver evidencia, auditarlo, aceptarlo o rechazarlo, retirarlo, y registrar todo con
trazabilidad completa, sin que pueda ampliar su autoridad ni encadenar subagentes sin fin.

Enunciado así parece una arquitectura nueva. **No lo es.** La medición dice lo contrario.

---

## 2 · Lo que YA existe — 18 de las 19 piezas

Este proyecto prohíbe crear un componente sin demostrar antes que no existe equivalente (regla del
CEO, 2026-08-03). La demostración es esta tabla, levantada leyendo el código `[EJEC]`:

| Pieza que la capacidad necesitaría | Estado | Dónde está hoy |
|---|---|---|
| Detectar la necesidad | PARCIAL | `autoconstruccion.observar()` / `diagnosticar()`; `descubrimiento.py` clasifica oportunidades. Solo detecta un tipo, no genérico |
| Decidir delegar | PARCIAL | `agentes.justifica_fallback()` / `clasificar()` decide relevo entre dos binarios fijos |
| **Crear subagente con misión propia** | **NO EXISTE** | `CADENA_DE_AGENTES = ("claude", "opencode")` es una lista **fija**. No hay fábrica ni parametrización de misión |
| Misión acotada por tarea | PARCIAL | `agentes.sobre_para_externo()` arma un «sobre» con restricciones por tarea |
| Herramientas acotadas | EXISTE | `allowedTools` + `permission_mode` en el sobre; `orquestador.py` mide que `acceptEdits` anularía la allowlist |
| Investigar | EXISTE | Agentes de Claude Code — herramienta **externa** del CTO, no capacidad de AURA |
| Internet gobernado | DISEÑADO, SIN IMPLEMENTAR | `ADR-0019` define opt-in y `DeclaracionTransparencia`. **Cero conectores lo usan** |
| Sandbox | PARCIAL | `tmp_path` + `zona_permitida()` + `_la_raiz_es_de_este_repositorio()`. Aislamiento **lógico**, no de proceso ni de SO |
| Producir artefactos | EXISTE | `propuesta.py`, `autoconstruccion.proponer()` → evento `propuesta_registrada` |
| Ejecutar pruebas | EXISTE | `verificador.py`: conteo por JUnit XML, `LIMITE_S = 600`, `os.killpg` del grupo de procesos |
| Devolver evidencia, no afirmación | EXISTE | `agentes.verificar_efecto()`; `Veredicto.evidencia_citada` contrastada contra disco |
| Auditar el resultado | EXISTE | `revisores.py` (4 revisores) y las cinco puertas de `review.ejecutar_bajo_review` |
| Aceptar / rechazar | EXISTE | `Veredicto` de cuatro valores; `permite_seguir()` |
| Retirar el subagente | PARCIAL | Contrato documentado `INSTALAR → VERIFICAR → EJECUTAR → MEDIR → RETIRAR → LIMPIAR → VERIFICAR AUSENCIA` |
| Registrar actividad | EXISTE | Log append-only con hash encadenado y `seq` monotónico |
| Impedir escalada de autoridad | EXISTE | `_INTOCABLES` (8); `review.habilitar` **no puede ampliar** el alcance vigente, solo mantenerlo o estrecharlo |
| Impedir cadena infinita | EXISTE | `siguiente_agente()` recorre la cadena una vez y devuelve `None`; `TOPE_DE_REINTENTOS = 2`; `MAX_TAREAS = 25` |
| Trazabilidad | EXISTE | `Intento` con 9 campos + log encadenado |
| Presupuesto | EXISTE | Los topes anteriores más `presupuesto_de_tarea_agotado`. Nota del propio plano: *«un presupuesto es un límite que el operador fija, jamás una medición de lo que queda»* |

**La delegación de autoridad acotada ya está resuelta, y bien.** `registrar_propuesta_autorizada`
acepta exactamente dos autoridades: un humano, o `REVIEW:<revisor>` **si y solo si** REVIEW está
realmente habilitado en el historial. En palabras del propio módulo: *«la autoridad delegada vale
porque hay un acta detrás, no porque se nombre»*.

**Lo único que falta es instanciar un subagente con misión propia.** Y falta **a propósito**:
`_EJECUTORES = {"claude": _no_implementado(...), "opencode": _no_implementado(...)}` devuelve
siempre `exit_code=127`, con esta razón escrita en el código: *«lanzar un agente gasta dinero y hace
trabajo, y eso exige una puerta explícita (INV-9)»*.

**Aviso contra un falso amigo.** Existe una clase llamada `RevisorSubagente` (`revisores.py:135-192`)
y el nombre engaña: **no invoca a ningún agente**. Aplica mecánicamente el catálogo de criterios de
D22. Su propio docstring lo advierte: *«invocarlo sería ejecutar, y un revisor que ejecuta deja de
ser un revisor»*.

---

## 3 · El contrato de capacidad, evaluado — resultado: **BLOQUEADA**

Aplicando `CONTRATO-DE-CAPACIDAD.md` regla C, que es fail-closed y se evalúa **antes** que la
implementabilidad porque *«la gobernanza habla primero»*:

| Condición de bloqueo | ¿Se cumple? | Evidencia |
|---|---|---|
| Toca **materia reservada** → D22 | **SÍ** | `review.py:66-70` lista literalmente **`"crear_autoridad"`** entre `_MATERIA_RESERVADA`, *«Reservado al CEO por D22. No delegable ni con REVIEW habilitado»*. Crear un subagente con autoridad acotada **es** crear autoridad `[EJEC]` |
| `regla_de_transformacion == REQUIERE_INFERENCIA` | **SÍ** | Detectar una misión, decidir si se delega y juzgar el resultado no son deterministas |
| `ejecutor.verbo` sin ejecutor construido → INV-9 | **SÍ** | `review.py:106` — `_EJECUTORES_CONSTRUIDOS = ("eliminar_codigo_muerto", "implementar_incremento_especificado")`. Nada más `[EJEC]` |
| `autoridad.acta` no consta en el log | **SÍ** | No existe acta alguna sobre esta capacidad |

Cuatro causas simultáneas, cada una suficiente por sí sola.

**Y el propio sistema ya lo declara sobre sí mismo**, en `entorno/control-plane/estado.json` `[EJEC]`:

```
capacidades_de_autoconstruccion.nunca: [... "crear autoridad nueva", "ampliar AUTO"]
autonomia_de_desarrollo.para_ampliar: "otra acta del CEO. AURA no puede ampliar su alcance (probado)"
```

No hace falta deducirlo: AURA ya lo dice.

---

## 4 · Por qué no hay autoridad — los bloqueos, por plano

**Plano de PRODUCTO (`walking-skeleton/`).** Tres bloqueos independientes:

- **D23** (acta fundacional): *«el CEO declara CERRADO el alcance funcional de la versión inicial de
  AURA: no se incorporarán nuevas funcionalidades ni cambios de visión salvo Alerta de Arquitectura
  o decisión estratégica excepcional aprobada por el CEO»*. Esta capacidad no está entre las diez
  oficiales.
- **D22**: toda decisión de rango 1 y toda Alerta de Arquitectura quedan reservadas al CEO.
- **D21**, pregunta 2 (*«¿reduce la dependencia de un proveedor?»*): un subagente atado a un
  proveedor responde **NO** → exige Alerta de Arquitectura.

**Plano de DESARROLLO (`entorno/control-plane/`).** D23 no aplica —es proceso, no producto, y su
README lo declara—, pero el bloqueo es igual de firme y está **escrito en el código del propio
plano**: `crear_autoridad` es materia reservada; el alcance vigente es
`('implementar_incremento_especificado',)` sin ampliar; `TODO_LO_DELEGABLE` y
`_EJECUTORES_CONSTRUIDOS` son listas blancas de dos verbos.

**Y el `CHECKLIST-CONTINUIDAD.md` §5.2 sigue vigente.** El único levantamiento —`D-ORCH-5`,
2026-08-25— cubre la Línea B / Communication Plane, y su cláusula de exclusión menciona
expresamente `D24` e **«instalar agentes de forma permanente»**: justo este terreno.

---

## 5 · La regla que decide el caso, y no es ninguna de las anteriores

**CEO, 2026-08-04:** *«El desarrollo lo guía la evidencia del uso real, no las ideas. Las capacidades
nacen de bloqueos observados y repetidos durante la operación diaria, se registran en
`PLAN-DE-FORMACION-AURORA.md` y ninguna se incorpora sin evidencia suficiente.»* Y la regla de
admisión del propio plan: *«ninguna capacidad entra aquí por parecer buena idea. Entra cuando el uso
real produce evidencia repetida, y esa evidencia se cita.»*

Revisado el plan entero `[LECT]` —8 capacidades aprendidas, 4 en observación, 5 bloqueadas—:

> **No existe ni un solo bloqueo observado, ni una vez, que una capacidad de subagentes resolviera.**

Ninguna entrada dice «no puedo delegar», «necesito dividir una misión», «me falta un auditor» ni «no
puedo retirar un agente». El único registro de uso real son dos necesidades traducidas, y sus
bloqueos son de **formulación**, no de coordinación.

**Consecuencia formal: la capacidad no cumple hoy el criterio de incorporación**, por deseable que
sea la dirección. Es el hallazgo más incómodo de este documento y el que menos conviene esquivar.

**Agravante medido.** Las capacidades 014 (formular cambios de código), 015 (interpretar una
necesidad) y 016 (proponer backlog) están **bloqueadas por hardware y formulación** —el plan las
llama *«la misma limitación vista desde tres ángulos»*—. Un subagente que investigue y produzca
artefactos necesita exactamente esas tres. Sin razonador local viable, la capacidad no acercaría a
AURORA a valerse por sí misma: **trasladaría la dependencia a una asistencia externa episódica**,
que es lo contrario de la regla del 2026-08-03 (*«solo pertenece lo que el sistema puede recuperar,
comprender y continuar por sí mismo»*).

---

## 6 · Arquitectura propuesta — diseño, no construcción

Se documenta porque *«diseñar no lo activa; construir sí»*. Nada de esto se implementa aquí.

**Forma correcta según la arquitectura real: no un catálogo de agentes, sino un VERBO delegable.**
Un subagente **no es** una capacidad registrable: `ADR-0021` + INV-6 establecen que las dependencias
relacionan capacidades **entre sí, nunca capacidades con implementaciones o servicios**, y un agente
es una implementación. Lo registrable sería el verbo —nombrado por el resultado que ofrece, según la
regla del CEO de 2026-08-03: `delegar_investigacion`, nunca `lanzar_claude`—.

Los cinco roles del enunciado (Research, Architect, Engineer, QA, Security) **no deben convertirse en
componentes**. Ya tienen representación: `revisores.py` tiene cuatro revisores; el catálogo de
criterios de D22 cubre la auditoría. Duplicarlos crearía la segunda arquitectura paralela que la
misión prohíbe.

**Las cinco condiciones acumulativas para que un subagente NO sea una ruta alternativa de
ejecución** —ALERTA-005, que este proyecto ya pagó dos veces—:

1. El subagente **propone y observa; nunca ejecuta**. Todo efecto lo despacha el Motor Único.
2. Todo lo que se ejecute está en el catálogo de capacidades registradas, nombradas por resultado.
3. El efecto lo verifica AURA, no el agente (patrón ya construido: `NO_VERIFICADO`).
4. `PARADA` lo detiene **fuera de banda**, sin cooperación del subagente (ADR-0024 §1).
5. Profundidad y ciclos acotados **por construcción**, no por configuración.

**Cumplir las cinco convierte la capacidad en algo mucho más pequeño: un proponente auditado. Que es,
exactamente, lo que ya existe.** Esa frase es el resultado técnico central de esta investigación, y
merece que el CEO la tenga delante antes de autorizar nada.

---

## 7 · Internet — por qué es el bloqueo más duro

Los cinco niveles del enunciado (sin red · lectura web · investigación · APIs autorizadas · acciones
externas) son un diseño razonable, y `ADR-0019` ya define el mecanismo genérico: opt-in explícito y
`DeclaracionTransparencia` obligatoria con `datos_locales`, `datos_que_salen`, `destino` y
`proposito`; *«un conector externo sin esa declaración no puede habilitarse»*. Pero su §6 dice
**«sin proveedor real: no se añaden credenciales, llamadas de red ni integración»**, y cero
conectores lo usan hoy.

Por encima está **D24**: *«no se utilizarán APIs comerciales ni claves de terceros… no se solicitan
claves de API ni soluciones propietarias salvo justificación arquitectónica documentada y
aprobada»*.

**Y esta contradicción ya tiene expediente abierto y sin resolver.** Es `D-ORCH-1`, registrada en
`DP-DEVELOPMENT-ORCHESTRATOR.md` §25.1: *«¿Alcanza D24 a la infraestructura de desarrollo?»*. El
mismo DP sitúa la fase **F5 (`RevisorExterno`) como BLOQUEADA**, requiriendo *«§25.1 + enmienda de
D24»*. La oportunidad `OB-1` de `estado.json` lo confirma: quien desbloquea, **CEO**; ejecutable hoy,
**false**.

Es decir: **el «quizá use Internet» del enunciado no es un detalle de diseño; es, por sí solo, un
bloqueo formal ya identificado hace semanas y todavía abierto.**

---

## 8 · Barreras de seguridad y cómo se demostrarían

La misión pide que el subagente nunca pueda ampliar su autoridad, tocar las reglas que lo gobiernan,
retirar `PARADA`, modificar `_INTOCABLES`, escapar del sandbox, escribir fuera del perímetro,
convertir investigación en ejecución, encadenar subagentes, ocultar actividad, borrar evidencia ni
tocar la Bible.

**Casi todas esas barreras ya existen y están probadas** (§2). Lo que faltaría es **ejercerlas contra
un subagente real**, y el criterio de aceptación del proyecto es exigente: *«ningún control de
seguridad se declara operativo sin un intento real de violación que falle»*.

Especificación de la red de mutación que haría falta —**especificación, no pruebas escritas**, porque
escribir una prueba RED ya sería iniciar el incremento—:

- Un subagente que intente ampliar su propio alcance debe ser rechazado, y el mutante que quite esa
  barrera debe morir.
- Un subagente que escriba fuera del perímetro debe ser rechazado **con `raiz` arbitraria**: es el
  incidente real que borró 49 líneas de un fichero del repositorio.
- `PARADA` debe detenerlo **sin su cooperación**.
- La profundidad debe estar acotada por construcción: el mutante que eleve el límite debe morir.
- Un subagente que afirme haber hecho algo sin haberlo hecho debe producir `NO_VERIFICADO`.

**Riesgo específico contra INV-9, con precedente en este mismo proyecto.** La capacidad 009 se
declaró aprendida siendo falsa — *«el patrón "declarado ≠ real" número 9 del proyecto, y el primero
cuyo autor fue la asistencia externa»*. Una capacidad de subagentes ejecutada **por** la asistencia
externa reproduce ese patrón a mayor escala: el sistema *parece* delegar cuando en realidad delega
quien lo asiste.

---

## 9 · Ruta de maduración

Las seis fases del enunciado son coherentes, y el proyecto ya tiene una serie equivalente: F1…F5 del
`DP-DEVELOPMENT-ORCHESTRATOR`, donde **F4 (`RevisorSubagente`) está autorizado por `D-ORCH-2`** y
**F5 (`RevisorExterno`) está bloqueada**. Proponer una numeración nueva y paralela sería exactamente
la segunda arquitectura que la misión prohíbe: **la ruta debe continuar F5, no abrir una serie
propia.**

Hoy el sistema está en FASE 1 y **no puede pasar a FASE 2** sin acta: pasar de «el CTO crea y
controla los subagentes» a «AURA puede solicitarlos bajo reglas predefinidas» es, literalmente,
`crear_autoridad`.

---

## 10 · Retorno sobre Tokens

**Lo que devolvería, si se construyera.** Sería la primera capacidad que reduce la dependencia de la
asistencia externa en la dimensión que el IMA ya mide y hoy da en falso: `ima.py:141-148`,
*«Coordinación entre agentes»*, con la comprobación *«los agentes se piden trabajo entre sí»*
anotada *«COLABORACIÓN: el corte estructural limita la profundidad a 1»*. **El IMA sí registraría un
aumento** — pero solo si la capacidad queda cableada en el sistema compuesto del producto: el plano
de desarrollo no mueve el IMA por construcción.

**Lo que cuesta hoy no tenerla:** cada misión de este tipo consume una sesión externa completa que
no sobrevive a su propia conversación. Es la asimetría que `CLAUDE.md` §0.bis describe: *«AURORA
trabaja en continuo; la asistencia externa es episódica»*.

**Lo que NO se calcula aquí, a propósito.** No se estima el ahorro de ninguna de las vías de
desbloqueo. Hacerlo sería construir un argumento cuantitativo a favor de una, y este documento
presenta un bloqueo, no una propuesta de compra.

**Reutilización: 18 de 19 piezas.** Si algún día se autoriza, el trabajo no es construir una
arquitectura: es **añadir una pieza a la que existe**. Ese es, probablemente, el dato más útil de
todo el documento.

---

## 11 · DECISION_REQUIRED

Se enumeran **sin resolver y sin ordenar por preferencia**. Ninguna es técnica: las seis son actos de
gobierno.

1. **¿Pertenece esta capacidad a la hoja de ruta, sin evidencia de uso real que la respalde?** Es la
   pregunta previa a todas las demás: la regla del 2026-08-04 exige evidencia repetida, y no la hay
   (§5). Responder que sí sería una excepción consciente a esa regla, y debería constar como tal.
2. **¿Alcanza D24 a la infraestructura de desarrollo?** Ya abierta como `D-ORCH-1`; sin ella no hay
   Internet ni agente externo real. Requiere además **enmienda documentada de D24**.
3. **¿Puede `crear_autoridad` dejar de ser materia reservada para este caso concreto** —o se acota la
   capacidad a proponer y auditar, sin crear autoridad, en cuyo caso deja de necesitar esa
   excepción?
4. **¿Se amplían `TODO_LO_DELEGABLE` y el alcance de `REVIEW`** con un verbo nuevo, y cuál, nombrado
   por su resultado?
5. **¿Se levanta `CHECKLIST` §5.2 para esta línea**, como se hizo con `D-ORCH-5` para la Línea B?
6. **¿Qué identificador de familia recibe esta línea?** Sin él, ninguna acta podrá citarla.

**Y una advertencia de orden, que no es una recomendación sobre el fondo:** la línea del motor está
hoy *cerrada a la espera de la decisión post-rollback*, y el `CHECKPOINT` la declara «siguiente paso
exacto». Abrir este frente antes de cerrar aquel dejaría dos decisiones de autonomía abiertas a la
vez sobre el mismo motor.

---

## 12 · Lo que este documento no hace

No implementa nada. No añade una línea de código ni una prueba. No toca
`politica-orquestador.toml`, `TODO_LO_DELEGABLE`, `_EJECUTORES_CONSTRUIDOS` ni `permissions.py`. No
habilita `REVIEW` ni amplía alcance. No emite eventos de autoridad. No retira `PARADA` ni ejecuta
`OP-100cc3d4e29a`. No reclasifica ninguna capacidad en `PLAN-DE-FORMACION-AURORA.md` —esa
reclasificación no corresponde a la asistencia externa—. No reclama `ADR-0025`. Y no pre-decide la
política post-rollback.


---

## 13 · DECISION_REQUIRED nueva, nacida de atacar lo construido

Una auditoría adversarial independiente atacó la capacidad el 2026-09-21. **Tres ataques
funcionaron y se corrigieron en la misma misión** (credencial fabricable, recursión por profundidad
autodeclarada, carrera en el uso único). Un cuarto hallazgo **no es corregible aquí**, y es este:

> **`ejecutar_pruebas` implica ejecución de código arbitrario.** No es un defecto del módulo: es lo
> que hace pytest. Cualquier fichero `test_*.py` del sandbox se ejecuta como Python real y desde
> ahí puede leer y escribir **fuera** del sandbox. El aislamiento que existe es de variables de
> entorno y de rutas en la línea de órdenes; **no hay aislamiento de sistema operativo** —ni
> contenedor, ni namespaces, ni usuario distinto—. Demostrado ejecutándolo: se leyó y se escribió
> fuera del sandbox con la misión marcada `ok=True`.

**Por qué la capacidad es utilizable hoy pese a ello.** El perímetro acota *qué ficheros se le
nombran a la herramienta*, no *qué hace el código que contienen*. Hoy el sandbox lo prepara quien
delega, dentro del repositorio, así que la condición se cumple. Pero es **una condición de uso, no
una garantía del código**, y la diferencia entre ambas cosas es la que este proyecto lleva ocho
incidentes aprendiendo. Está escrita en el docstring del módulo para que nadie la descubra tarde.

**La decisión:** ¿se acepta esa condición de uso —delegar solo sobre sandboxes cuyo contenido
provenga de una fuente tan fiable como el propio plano—, o se exige **aislamiento de sistema
operativo** antes de ampliar la capacidad a contenido menos controlado?

**Por qué es del CEO:** construir aislamiento de SO es diseño nuevo, toca decisiones de plataforma
y podría rozar D24 según la vía elegida. No falta capacidad técnica para decidirlo: falta decidir
cuánto vale la contención frente a su coste. **No se recomienda ninguna opción.**

**Lo que NO está en cuestión:** la capacidad con las tres correcciones aplicadas resiste los demás
vectores probados —ruta absoluta, inyección de opciones, symlink re-apuntado entre delegar y
ejecutar, sandbox que es symlink, materia reservada, bytes nulos—, todos bloqueados y con mutante
que lo demuestra.
