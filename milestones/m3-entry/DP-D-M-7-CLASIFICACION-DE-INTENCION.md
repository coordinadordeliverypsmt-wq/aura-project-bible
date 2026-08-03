# Decision Package — D-M-7: modelo de clasificación de intención

**Estado:** propuesta, **pendiente de aprobación del CEO**. **No se ha modificado código.**
**Encargo (CEO, 2026-08-03):** definir el modelo general de clasificación de intención y **justificar
el modelo conceptual** sobre qué información constituye memoria recuperable, no solo el mecanismo.

**Clasificación de evidencia** (D47): `[EJEC]` salvo marca explícita.

> ### ⚠ Antes de nada: `ALERTA-006`
> El inventario destapó que **existe una ruta que elimina información del usuario sin pasar por el
> motor único ni por confirmación humana**, y que puede borrar **el dato equivocado**. Está registrada
> aparte en `ALERTA-006-BORRADO-SIN-MOTOR.md` y **no se resuelve en este DP**. Requiere decisión
> independiente y probablemente más urgente que todo lo que sigue.

---

## 1 · El inventario: la dispersión medida

**13 clasificadores léxicos independientes · 91 patrones · 4 ficheros · 3 copias distintas del
normalizador.** Ninguno comparte tabla con otro. **Ninguno distingue una pregunta de una afirmación.**

| Fichero | Clasificadores | Patrones | Decide |
|---|---|---|---|
| `core/orchestrator.py` | 9 | 59 | ADR-0014, notificaciones, ver/olvidar/refutar/explicar el modelo, ver/crear/cancelar reglas |
| `conectores/conversacion.py` | 2 | 22 | **qué se escribe como memoria semántica**; descarte de terceros |
| `modules/router.py` | 1 | ~10 | la **acción** del turno, y con ella la lista roja |
| `modules/memory.py` | 1 | 112 vacías | si hay `hits`, y por tanto si ADR-0014 se activa |

**Todos deciden por `subcadena in texto`**, salvo uno (`_habla_de_tercero`, único con regex real).
`router.py:24` —la capa que decide acciones de **lista roja**— es la única que **no normaliza
acentos**: solo hace `.lower()` `[EJEC]`.

### Contradicciones verificadas por ejecución

| Frase | Qué ocurre |
|---|---|
| «No quiero que borres la copia de seguridad» | **Desactiva la automatización** de copias. Es una orden de *protección*, leída como cancelación: `"no quiero"` + `"copia"` |
| «Olvida que a mi hermana le gusta el café» | **Borra una preferencia propia** del usuario → `ALERTA-006` |
| «Apaga la luz del salón» | El proveedor devuelve `encender_dispositivo`: responde «Listo, encendí la luz» **a una orden de apagar** |
| «¿Qué reglas hay para entrar al gimnasio?» | Responde con la lista de automatizaciones. No consulta ni memoria ni LLM |
| «Mis reglas de vida son simples» | Una **afirmación** convertida en consulta de automatizaciones |
| «Deja de llover, por favor» | Se escribe en el **modelo del usuario** como `semantica / feedback_directo` |
| «Te conté que prefiero el té sin azúcar» | **Afirmación** clasificada como consulta de memoria (`"te conté"`) |
| «¿Qué sabes de mí?» | Activa **dos** clasificadores; el literal está duplicado en `orchestrator.py:61` y `:101`. Gana el orden posicional |
| «Por qué dices que prefiero el té?» | Explica la procedencia **y guarda la propia pregunta como preferencia declarada** |

**Cero clasificadores miran el signo de interrogación, la posición del verbo o cualquier marca de
modalidad** `[EJEC]`: verificado que `«Prefiero el té.»` y `«Prefiero el té?»` se clasifican idéntico.

### Cobertura de pruebas de todo esto

**Una sola mención en toda la suite**, y es a código defensivo. No existen pruebas unitarias de
`_es_consulta_de_memoria`, `_es_cancelacion_de_regla`, `_es_consulta_de_reglas` ni de
`conversacion._clasificar` `[EJEC]`. Los fallos de arriba **no los cubre ninguna prueba**.

### El orden posicional es la única regla de desempate

Las 7 ramas de `on_turn` se evalúan en secuencia con `return` inmediato. Consecuencias medidas: las
ramas 1-3 **ni siquiera consultan la memoria** (`recall` está en la línea 363, después); «¿Qué sabes de
mí?» da **dos respuestas distintas** según esté o no cableado `modelo_usuario`, con el mismo texto.

---

## 2 · Mi hipótesis inicial, refutada

Propuse: *«solo se convierte en memoria recuperable aquello que el usuario afirma sobre su mundo»*. El
CEO pidió no aceptarla como principio hasta probarla contra seis tipos de información. **Falla en 5 de
12 casos `[EJEC]`:**

| Caso | Acto detectado | ¿La hipótesis lo almacena? | ¿Debería? |
|---|---|---|---|
| Preferencia permanente | AFIRMACIÓN | sí | sí ✓ |
| Objetivo («quiero aprender Rust») | AFIRMACIÓN | sí | sí ✓ |
| Corrección («ya no trabajo en…») | CORRECCIÓN | sí | sí ✓ |
| **Recordatorio** («recuérdame llamar al médico») | ORDEN | **no** | **sí** ✗ |
| **Procedimental** («para el café uso la italiana») | ORDEN | **no** | **sí** ✗ |
| **Automatización** («cuando llegue a casa enciende…») | PREGUNTA | **no** | **sí** ✗ |
| **Pregunta con info implícita** («¿dónde dejé las llaves de mi coche nuevo?») | PREGUNTA | **no** | **sí** ✗ |
| **Pregunta con info implícita** («¿sabías que soy alérgico?») | PREGUNTA | **no** | **sí** ✗ |

**Dos causas distintas, y la distinción es la clave del DP:**

- **Fallos del mecanismo** (procedimental, automatización): colisiones léxicas. `«Para el café…»` se
  lee como orden porque `para` es también el imperativo de *parar*; `«Cuando llegue…»` como pregunta
  porque `cuando` es también interrogativo `[EJEC]`. **No refutan el modelo**, refutan la tabla.
- **Fallos del modelo** (recordatorio, y las dos preguntas con información implícita): el acto de habla
  **es** el correcto y aun así el turno contiene un hecho que debe persistir. **Estos sí refutan la
  hipótesis.**

> **Conclusión: el acto de habla no determina por sí solo qué se almacena.** La hipótesis colapsaba dos
> preguntas independientes en una sola.

---

## 3 · Taxonomía propuesta: dos ejes ortogonales

### Eje 1 — Acto de habla: **qué quiere el usuario de este turno**

Determina el **enrutado**. Clases mutuamente excluyentes, con prioridad explícita y documentada:

| Acto | Enrutado |
|---|---|
| `CORRECCION` | modifica lo ya sabido (gana a todo: cambia el estado) |
| `ORDEN` | motor único → permisos → HITL |
| `PREGUNTA` | consulta; **habilita la garantía de ADR-0014** si no hay `hits` |
| `SOCIAL` | respuesta conversacional; sin efectos |
| `AFIRMACION` | por defecto |

### Eje 2 — Contenido proposicional: **qué hechos aporta el turno**

Determina **qué se almacena**, con independencia del acto. Un turno puede ser `PREGUNTA` en el eje 1 y
aportar una proposición almacenable en el eje 2 — que es exactamente lo que refutó la hipótesis.

| Tipo de contenido | Memoria recuperable | `kind` |
|---|---|---|
| Hecho estable sobre el usuario (preferencia, dato, objetivo) | **sí** | `semantica` |
| Conocimiento de cómo hace las cosas | **sí** | `procedimental` |
| Compromiso futuro (recordatorio, cita) | **sí** | `semantica` + vencimiento |
| Regla condicional | **no** en memoria: al almacén de reglas | — |
| Nada proposicional (social, orden pura) | **no** | histórico no recuperable |

### El principio, ya corregido

> **Se convierte en memoria recuperable el contenido proposicional que el turno aporta sobre el mundo
> del usuario — sea cual sea el acto de habla que lo vehicula.** El acto decide **a dónde va el turno**;
> el contenido decide **qué se recuerda**.

### Por qué esto explica todos los defectos abiertos

| Defecto | Explicación bajo la taxonomía |
|---|---|
| **D-M-2** (auto-eco) | El eco guarda **el turno entero** como si fuera contenido proposicional. Una pregunta pura no aporta ninguno: no debería ser recuperable |
| **D-M-7** (ADR-0014 no se activa) | La garantía se dispara con 15 literales en vez de con el **acto** `PREGUNTA`. Con el eje 1, se activaría en las 70/77 consultas reales en vez de en 0/77 |
| **D-M-4** (recuerdo largo atractor) | Consecuencia de almacenar turnos crudos en vez de proposiciones |
| **ALERTA-006** | El acto `ORDEN` sobre datos propios debería ir al motor; hoy va por una rama que ni lo consulta |

**El eco no es un descuido: es el parche que suple un eje 2 demasiado estrecho.** Hoy `AlmacenSenales`
solo captura si el enunciado dispara uno de 22 marcadores; todo lo demás se perdería sin el eco. Por
eso `«Mi cumpleaños es el 14 de marzo»` —una afirmación que aporta un hecho— **no activa ningún
clasificador** y solo sobrevive como `usuario dijo: …` `[EJEC]`.

---

## 4 · Alternativas de mecanismo

**Restricción dura, no negociable.** ADR-0014 §2: *«La detección también es determinista. Identificar
"el usuario pregunta por un recuerdo" se hace por patrones en el núcleo, no por clasificación del
modelo: delegar esa decisión en el LLM reintroduciría la dependencia que la decisión elimina.»* Y §4:
si no se puede escribir una prueba determinista, **no es una garantía, es una expectativa**.

| # | Mecanismo | Veredicto |
|---|---|---|
| **M-1** | **Clasificador único determinista** con tabla compartida, normalizador único y prioridad explícita | **Recomendado** — ver abajo |
| M-2 | Mantener los 13 dispersos, unificar solo el *contrato* de salida | Reduce el síntoma, conserva 91 patrones y 3 normalizadores. No elimina las contradicciones |
| M-3 | Clasificación por LLM | **Prohibido por ADR-0014 §2** para todo lo que active garantías |
| M-4 | Clasificador estadístico local entrenado | Local-first lo permite, pero no es determinista ni auditable con prueba fija; y el hardware ya bloquea N2 |
| M-5 | Híbrido: núcleo determinista + LLM solo para lo que **no** active garantías | Viable a futuro. Hoy añade una segunda vía que mantener sin resolver nada nuevo |

### Fiabilidad medida de M-1 `[EJEC]`

Prototipo del eje 1 sobre banco etiquetado de 31 frases y sobre la batería oficial:

| Medida | Resultado |
|---|---|
| Banco etiquetado (5 actos) | **29/31 = 93,5 %** |
| Consultas de la batería clasificadas `PREGUNTA` | **70/77** (las 7 restantes son de una sola palabra, no son preguntas) |
| Recuerdos del corpus clasificados `AFIRMACION` | **65/65** |
| Detector vigente `_es_consulta_de_memoria`, misma batería | **0/77** |
| Falsos positivos sobre afirmaciones | **0/8** (el vigente: 4/8) |

Los 2 fallos del banco son colisiones léxicas de la tabla (`encender` en infinitivo ausente donde sí
está `enciende`), **no del modelo**. Se declaran como límite conocido del enfoque léxico: cualquier
tabla tiene cobertura finita, y por eso el eje 1 debe tener pruebas propias — hoy no tiene ninguna.

---

## 5 · Qué tendría que demostrarse para cambiar esta decisión

1. **Que el eje 2 no puede implementarse de forma determinista.** Es el riesgo real: extraer
   proposiciones es más difícil que clasificar actos. Si se demuestra, la alternativa sería mantener el
   eco como histórico **no recuperable** y aceptar menos memoria a cambio de veracidad. `[HIPO]`
2. **Que la unificación rompe comportamiento aprobado.** Los 13 clasificadores no tienen pruebas: la
   red de seguridad hay que construirla **antes** de tocarlos, no después.
3. **Que el CEO considere que la soberanía debe seguir exenta del motor** (ver `ALERTA-006`). Es
   decisión de producto y cambiaría el enrutado del acto `ORDEN` sobre datos propios.
4. **Que aparezca un acto de habla que no encaje en los cinco.** La taxonomía se propone pequeña a
   propósito; si hicieran falta diez clases, dejaría de ser un núcleo y volvería a ser una colección.

---

## 6 · Lo que este DP NO incluye

- **No resuelve `ALERTA-006`**, que es más urgente y necesita decisión propia.
- **No implementa nada.** Ni el clasificador, ni la unificación, ni cambios en `recall`.
- **No decide D-M-2**: queda supeditado a que se apruebe esta taxonomía, como fijó el CEO.
- **No aborda** el proveedor (`router.py`), cuya clasificación de acciones de lista roja **sin
  normalizar acentos** merece revisión aparte.
- **No propone** ampliar el alcance funcional del MVP (D23).
