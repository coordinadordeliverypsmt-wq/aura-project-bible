---
documento: "Mapa del flujo de una consulta de memoria, y qué parte ya evita el LLM"
tipo: "Inspección + medición (Fase 0 de la misión de optimización de primer orden)"
fecha: 2026-09-10
estado: "Medido. NINGÚN cambio de código: la optimización buscada ya existía."
mantenido-por: "APUS-5 (CTO)"
---

# La llamada que ya no se hace

**Clasificación de evidencia** (D47): `[EJEC]` medido · `[LECT]` leído en el código · `[INFER]` deducido.

## 1 · Corrección de una medición mía `[EJEC]`

La misión parte de un dato que yo reporté: «una consulta de memoria con recuerdo existente costó
**126,4 s** porque el Core recuperó el hecho y después llamó al modelo para redactarlo».

**Ese dato era un artefacto de mi instrumentación, no el comportamiento del producto.** Sembré el hecho así:

```python
await sistema.memoria.write("usuario", "semantica", "Mi color favorito es el azul",
                            {"fuente": "siembra de laboratorio", "bench": True})
```

Sin la clave **`clase`**. Y `ModeloUsuario.ver()` expone `clase` desde `provenance["clase"]`
(`modelo_usuario.py:61`), mientras `_responder_hecho` solo acepta entradas de clase
**`HECHO_DECLARADO`** (`orchestrator.py:1285`). El hecho sembrado era **invisible** para la superficie
que debía responderlo, así que el turno siguió hasta el LLM. Midiendo el flujo real —el usuario declara
hablando— el resultado es el opuesto.

## 2 · Mapa del flujo `[LECT]`

```
entrada (texto o STT)
  → handle_utterance → on_turn
      ├─ 1. MODELO DE USUARIO ............ _atender_modelo_usuario
      │        ├─ _PAT_MODELO_VER ........ describir_conocimiento(entradas)
      │        ├─ _responder_hecho ....... _CONSULTAS_DE_HECHO  ← AQUÍ muere la llamada al LLM
      │        └─ olvidar / refutar / porqué
      ├─ 2-13. otras 12 superficies deterministas (notificaciones, reglas, conversación general,
      │        capacidades, tareas, evolución, última tarea, autorización, decisiones,
      │        oportunidades, gobierno, formación, aritmética) ......... todas `provider=core`
      ├─ 14. frontera cognitiva .......... intencion.es_cognicion_general(text)
      ├─ 15. recall ...................... hits = await self.memory.recall(uid, text)
      ├─ 16. GUARDA ADR-0014 ............. if not hits and _es_consulta_de_memoria and not cognición
      │                                     → "No tengo ningún recuerdo registrado sobre eso."  (core)
      ├─ 17. prompt ...................... [contexto memoria: hits] + buffer + "Usuario: …"
      ├─ 18. modo ........................ "accion" si _pide_accion y no cognición, si no "cognitivo"
      ├─ 19. router.route(prompt, tid, modo) → OllamaProvider  ← la única llamada al modelo
      └─ 20. _finalizar_turno ............ destino_de_memoria + guarda de PARADA
```

Respuestas a las ocho preguntas de la Fase 0:

| # | Pregunta | Respuesta |
|---|---|---|
| 1 | ¿Dónde se detecta una consulta de memoria? | `_es_consulta_de_memoria` (= `MARCADORES_DE_EVOCACION` ∪ `es_interrogativa`), paso 16 |
| 2 | ¿Dónde consulta Core el MemoryStore? | paso 15, `self.memory.recall`; y antes, `modelo_usuario.ver()` dentro del paso 1 |
| 3 | ¿Dónde se obtiene el hecho? | `ModeloUsuario.ver()` → `_entradas()` filtra por `kind in _TIPOS` y expone `clase` |
| 4 | ¿Dónde se decide llamar al ModelProvider? | paso 19; se llega ahí **solo** si ninguna superficie respondió y la guarda no disparó |
| 5 | ¿Dónde se construye el `say`? | en cada superficie (paso 1–13) o desde el JSON del modelo (paso 19) |
| 6 | ¿Dónde interviene el Orchestrator? | en **todo** el recorrido: las 14 superficies son métodos suyos |
| 7 | ¿Qué pertenece a `orchestrator.py`? | los pasos 1–20 completos, incluida `_CONSULTAS_DE_HECHO` y `_responder_hecho` |
| 8 | ¿Existe ruta segura para devolver un hecho ya verificado? | **Sí, y ya está construida**: `_responder_hecho`, dentro de la soberanía del Modelo de Usuario |

## 3 · Lo que la ruta existente ya garantiza `[LECT]`

`_responder_hecho` cumple, una por una, las nueve condiciones de la Fase 1 de la misión:

- **A/B · hecho recuperado y bajo autoridad del Core** — la fuente es `modelo_usuario.ver()`, que lee el
  MemoryStore; el LLM no participa.
- **C · corresponde exactamente a la consulta** — `_CONSULTAS_DE_HECHO` es una tabla **cerrada** de
  (preguntas, regex, plantilla, ausencia). No hay emparejamiento por parecido.
- **D · sin ambigüedad** — solo entradas **vivas** (no refutadas) y de clase `HECHO_DECLARADO`; la
  **última** declaración gana, porque redeclarar es cómo uno se corrige.
- **E/F/G/I · sin razonamiento, conocimiento externo, hipótesis ni inferencia creativa** — el valor sale
  de la **propia frase del usuario** vía `_valor_declarado`, y se inserta en una plantilla fija.
- **H · sin acción** — devuelve texto; no toca el motor.
- **INV-9 explícito**: si el atributo no se declaró, lo dice («Todavía no me has dicho cómo te llamas»)
  en lugar de dejar que la pregunta caiga al recall y se responda por parecido de texto.

**No es un «LLM falso» dentro del Core:** es una plantilla sobre un valor declarado por el usuario.

## 4 · Medición del flujo real `[EJEC]`

Secuencia conversacional en un solo proceso, sin sembrar nada: el usuario **declara hablando** y después
pregunta.

| Paso | Tiempo | Proveedor | Dominio | Llamadas al LLM | Respuesta |
|---|---|---|---|---|---|
| «Me llamo Mauricio» | 65,05 s | ollama | llm | 1 | «Hola, ¿Cómo estás?» |
| **«¿Cómo me llamo?»** | **0,00 s** | **core** | modelo_usuario | **0** | **«Te llamas Mauricio.»** |
| «Trabajo en logística» | 32,34 s | ollama | llm | 1 | «Hola, trabajas en logística?» |
| **«¿A qué me dedico?»** | **0,00 s** | **core** | modelo_usuario | **0** | **«Trabajas en logística.»** |
| **«¿Cómo se llama mi hija?»** | **0,00 s** | **core** | memoria | **0** | «No tengo ningún recuerdo registrado sobre eso.» |

**Los dos ejemplos que la misión da como casos válidos responden ya en 0,00 s con cero llamadas al
modelo.** El ahorro frente a un turno cognitivo medido en este equipo (42–154 s) es de **dos órdenes de
magnitud**, y no hay que construirlo: está construido.

## 5 · El hueco que sí existe

Lo que **no** cubre la ruta: un hecho declarado que no es uno de los **tres** atributos de la tabla
(nombre, trabajo, proyecto) ni casa con `_PAT_CONSULTA_PREFERENCIA` (`que prefiero`,
`cuales son mis preferencias`, `que me gusta`). «¿Cuál es mi color favorito?» es exactamente ese caso.

**Medido, y es peor que un problema de latencia** `[EJEC]`:

| Turno | Resultado |
|---|---|
| usuario: «Mi color favorito es el azul» | 65,84 s · LLM |
| usuario: **«¿Cuál es mi color favorito?»** | **129,02 s · `ollama` · 1 llamada** |
| respuesta | **«Mis preferencias personales incluyen la agradable amarilla, la apacible llena y la hermosa amarillo.»** |

El usuario dijo **azul**; AURA contestó **amarillo**. El hecho correcto estaba en el `recall` y viajó en
el prompt: **el modelo lo deformó al redactarlo**. La autoridad del Core se respeta, pero la redacción
final la tiene un modelo de 0,5 B que no conserva el dato.

Ampliar la tabla es tocar `orchestrator.py`, y esta misión **no** autoriza hacerlo unilateralmente:
expediente en `DECISION-REQUERIDA-HECHO-DEFORMADO-POR-EL-LLM.md`.

## 6 · Los ocho casos de seguridad `[EJEC]`

| # | Caso | Tiempo | Proveedor | Dominio | Llamadas al LLM | ¿Correcto? |
|---|---|---|---|---|---|---|
| 1 | «¿Cómo me llamo?» | **0,00 s** | core | modelo_usuario | **0** | sí |
| 2 | «¿A qué me dedico?» | **0,00 s** | core | modelo_usuario | **0** | sí |
| 3 | «¿Cómo se llama mi hija?» | **0,01 s** | core | memoria | **0** | sí |
| 4 | «¿Quién fue Jesús Cristo?» | 129,38 s | ollama | llm | 1 | enrutado sí |
| 5 | «Si todos los A son B y X es A…» | 137,68 s | ollama | llm | 1 | enrutado sí |
| 6 | «¿Qué me recomiendas para concentrarme mejor?» | 153,80 s | ollama | llm | 1 | enrutado sí |
| 7 | «¿Qué pasaría si no durmiera nada?» | 166,59 s | ollama | llm | 1 | enrutado sí |
| 8 | «Hoy tuve un día difícil.» | 195,06 s | ollama | llm | 1 | enrutado sí |

**Ninguno de los casos 3–8 se convirtió en una respuesta directa de memoria.** La frontera se comporta
como debe: lo que es del Core lo responde el Core; lo que es cognición va al modelo.

Dos observaciones sobre la **calidad** del modelo, que no son de enrutado y no se corrigen aquí:

- El caso 4 situó a Jesús Cristo «en el siglo III a.C.».
- El caso 5 respondió **«Trabajo en logística.»** — copió un hecho del contexto de memoria en lugar de
  razonar. El `recall` inyecta el contexto personal en **todos** los prompts cognitivos, y un modelo de
  0,5 B lo reutiliza de forma espuria. Es una observación técnica, no deuda de esta misión.
