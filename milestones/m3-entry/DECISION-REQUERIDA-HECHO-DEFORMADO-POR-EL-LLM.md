---
documento: "DECISION_REQUIRED — ampliar la tabla de hechos respondibles por el Core"
tipo: "Expediente de decisión (NO implementado: requiere tocar orchestrator.py)"
fecha: 2026-09-10
estado: "RESUELTO. Autorizado e implementado por el CEO el 2026-09-10. Se conserva como expediente."
mantenido-por: "APUS-5 (CTO)"
---

# Un hecho que el Core tenía bien, y el modelo devolvió mal

**Clasificación de evidencia** (D47): `[EJEC]` medido · `[LECT]` leído · `[INFER]` deducido.

## 1 · Lo medido `[EJEC]`

Conversación real, un solo proceso, `AURA_STACK_REAL=1`, `qwen2.5:0.5b`:

| Turno | Resultado |
|---|---|
| usuario: «Mi color favorito es el azul» | se registra; el turno pasa por el LLM (65,8 s) |
| usuario: **«¿Cuál es mi color favorito?»** | **129,02 s · `provider=ollama` · 1 llamada** |
| respuesta de AURA | **«Mis preferencias personales incluyen la agradable amarilla, la apacible llena y la hermosa amarillo.»** |

**El usuario dijo azul. AURA contestó amarillo.** El hecho correcto estaba en el `recall` y viajó en el
prompt: el modelo lo deformó al redactarlo.

Compárese con los dos atributos que **sí** tienen superficie determinista, en la misma conversación:

| «¿Cómo me llamo?» | **0,00 s · `core` · 0 llamadas** | «Te llamas Mauricio.» |
| «¿A qué me dedico?» | **0,00 s · `core` · 0 llamadas** | «Trabajas en logística.» |

## 2 · Por qué pasa `[LECT]`

`_responder_hecho` (`orchestrator.py:1279`) responde desde el Modelo de Usuario, sin LLM, pero solo para
lo que figura en **`_CONSULTAS_DE_HECHO`** (`orchestrator.py:210`), que hoy tiene **tres** entradas:
nombre, trabajo y proyecto. Más `_PAT_CONSULTA_PREFERENCIA` (`que prefiero`,
`cuales son mis preferencias`, `que me gusta`), con el que «cual es mi color favorito» **no** casa.

Todo lo demás —cualquier otro hecho personal declarado— sigue hasta el paso 19 y lo redacta el modelo.

## 3 · Qué está realmente en juego

No es latencia. Es que **el LLM puede deformar un hecho personal que el Core posee correctamente**, y eso
roza el núcleo de `ADR-0014`: el Core es la única autoridad sobre los hechos del usuario. Hoy la
autoridad la tiene el Core, pero **la redacción final la tiene el modelo**, y en un modelo de 0,5 B la
redacción no conserva el dato. El ahorro de 129 s es el beneficio secundario.

## 4 · El cambio exacto que haría falta

**Archivo:** `walking-skeleton/aura_skeleton/core/orchestrator.py` — **zona protegida, no lo he tocado.**

**Símbolo:** `_CONSULTAS_DE_HECHO` (constante de módulo, línea 210).

**Cambio:** añadir entradas a la tabla cerrada, con la misma forma que las tres existentes
`(preguntas, patrón, plantilla, ausencia)`. Por ejemplo:

```python
(
    ("cual es mi color favorito", "que color me gusta mas", "cual es mi color preferido"),
    r"(?:mi color favorito es|mi color preferido es)\s+(.+)",
    "Tu color favorito es {}.",
    "Todavía no me has dicho cuál es tu color favorito.",
),
```

**Nada más.** No se toca `_responder_hecho`, ni la frontera, ni `_es_consulta_de_memoria`, ni la guarda de
`ADR-0014`, ni el router, ni el motor, ni los permisos. La mecánica de seguridad ya está construida y
probada: solo entradas **vivas** de clase `HECHO_DECLARADO`, el valor sale de la **frase del usuario** vía
`_valor_declarado`, gana la **última** declaración, y si no hay declaración se **dice** en lugar de
inferir (`INV-9`).

**Por qué es necesario:** sin ello, cada hecho personal fuera de esos tres atributos se responde con el
modelo, pagando ~130 s y **arriesgando que el dato salga cambiado** — demostrado arriba.

## 5 · Alternativa sin tocar `orchestrator.py`

**No existe una equivalente.** Lo he comprobado:

- `_CONSULTAS_DE_HECHO` y `_responder_hecho` **viven en `orchestrator.py`**; ampliar la cobertura es
  editar ese fichero.
- Las 14 superficies no son un registro extensible: cada una es un `if` con su método dentro de
  `on_turn`. No hay puerto por el que inyectar una superficie nueva desde `composicion.py`.
- Parchear la constante en tiempo de composición sería *monkeypatching* sobre el Core: peor que el
  problema, y contrario a la ruta única.
- Mover la tabla a `core/modelo_usuario.py` **también** exige editar `orchestrator.py` para importarla.

La única alternativa real es **no hacerlo**, y entonces la mitigación disponible no es técnica sino de
expectativa: aceptar que, fuera de los tres atributos, AURA puede devolver un hecho personal deformado.

## 6 · Riesgos del cambio

| Riesgo | Valoración |
|---|---|
| Romper el `24/24` | **Nulo por construcción** `[INFER]`: la tabla actúa en el paso 1, **antes** del recall, y solo responde si el usuario **declaró** el atributo. Si no lo declaró, devuelve el texto de ausencia — que es justo lo que el `24/24` protege. Verificable con la batería. |
| Robar turnos a otra superficie | Bajo pero real: `_cae_en` casa por subcadena. Cada frase añadida debe comprobarse contra las superficies que van antes (la lección de «que sabes de mi proyecto», ya documentada en el propio código). |
| Responder un hecho obsoleto | Cubierto: solo entradas vivas, y gana la última declaración. |
| Convertir el Core en generador | No: plantilla fija sobre el valor literal del usuario. |
| Crecimiento sin control de la tabla | Real a medio plazo: una tabla de atributos no escala a «cualquier hecho». La solución general —emparejar consulta y hecho sin plantillas— es otro incremento, con otro diseño. |

## 7 · Recomendación `[INFER]`

**Autorizar el cambio, acotado y con prueba previa.** Concretamente: ampliar `_CONSULTAS_DE_HECHO` con
los atributos que el uso real demuestre (empezando por el color, que ya produjo una respuesta falsa),
con un RED que fije la conducta, mutación sobre la tabla, y la batería `24/24` re-medida antes y después.

Y registrar la deuda de fondo: **la tabla no escala.** Lo que esta medición enseña no es que falte una
fila, sino que **redactar con el modelo un dato que el Core posee es una fuente de error**. El diseño
general —cómo emparejar una pregunta con un hecho almacenado sin plantillas y sin LLM— merece su propio
Decision Package.

## 8 · Resuelto `[EJEC]` — 2026-09-10

**El CEO autorizó el cambio acotado y está implementado.** Hizo falta **una mitad más** de la que este
expediente preveía, y se descubrió al implementar:

| Mitad | Fichero | Por qué era imprescindible |
|---|---|---|
| 1 | `conectores/conversacion.py` → `_HECHO` | `_clasificar("mi color favorito es el azul")` devolvía **`None`**: ni hecho ni preferencia. La declaración se guardaba **sin clase**, y `_responder_hecho` solo admite `HECHO_DECLARADO`. Sin esto, ampliar la tabla no habría servido de nada. |
| 2 | `core/orchestrator.py` → `_CONSULTAS_DE_HECHO` | la fila con la que responder (dos formas inequívocas, plantilla y texto de ausencia). |

**Medido a través del producto, contra Ollama real:**

| Turno | Antes | Después |
|---|---|---|
| «¿Cuál es mi color favorito?» (sin declarar) | — | **0,00 s · core · 0 llamadas** · «Todavía no me has dicho cuál es tu color favorito.» |
| «Mi color favorito es el azul» | 65,8 s | 152,4 s · LLM (la declaración sigue pasando por el modelo) |
| **«¿Cuál es mi color favorito?»** | **129,02 s · 1 llamada · «amarillo»** | **0,00 s · core · 0 llamadas · «Tu color favorito es azul.»** |
| «Mi color favorito es el verde» | — | 131,4 s · LLM |
| **«¿Cuál es mi color favorito?»** | — | **0,00 s · core · 0 llamadas · «Tu color favorito es verde.»** |

**La distinción hecho/preferencia del acta de 2026-08-09 se conserva:** solo entra la construcción
declarativa completa. «Me gusta el azul» y «Prefiero el azul» siguen siendo `PREFERENCIA_DECLARADA`, con
prueba propia.

**7 mutantes, 0 supervivientes.** Uno de ellos —`HD-M6`, sustituir el filtro de clase por «todas las
entradas vivas»— **sobrevivió en la primera pasada**: la regla que el CEO mandó preservar no la cubría
ninguna prueba. Se cerró con un caso en el que una señal **observada** (`PATRON_DE_USO`) contiene el
texto del atributo y **no** debe devolverse como declaración del usuario.

**La deuda de fondo sigue en pie:** la tabla no escala a «cualquier hecho». Lo sigue mereciendo un
Decision Package propio.
