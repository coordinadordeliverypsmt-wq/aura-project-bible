# Deuda — la cifra «24/24 sin LLM» de ADR-0014 es CONDICIONAL

**Registrada:** 2026-08-09 · **Origen:** re-auditoría independiente de Conversación General v1
**Estado:** deuda preexistente, **fuera del alcance** del incremento que la destapó (decisión del CEO)

---

## Qué se midió

La garantía de no-fabricación de ADR-0014 se documenta como *«24/24 negativas atendidas por el núcleo,
cero llamadas al LLM»*. **Esa cifra es cierta bajo una condición que no se estaba escribiendo: con la
memoria VACÍA**, que es como corre la prueba oficial.

Con el corpus de 65 recuerdos de la propia batería sembrado, el auditor midió `[EJEC]`:

| Condición | Atendidas por el núcleo | Llamadas al LLM |
|---|---|---|
| Memoria vacía | **24/24** | 0 |
| Corpus sembrado | **19/24** | 5 |

Las cinco que se escapan: *«¿Cuánto gana mi jefa Marta?»*, *«…apellido de mi mejor amiga Sofía?»*,
*«…instrumento toca mi grupo de música favorito?»*, *«…coche de mi vecino?»*,
*«…camisa de mi hermano?»*.

## Por qué ocurre

La puerta es `if not hits and _es_consulta_de_memoria(text)` (`orchestrator.py`). Con recuerdos
temáticamente próximos, `hits` deja de estar vacío, la puerta no se activa y el turno llega al LLM
**con esos recuerdos como contexto**. Son exactamente los *falsos positivos críticos* que
`tests/integration/test_bateria_memoria.py` ya documenta: el recuerdo pertenece a OTRA entidad que
comparte un atributo genérico, y el modelo puede responder un dato concreto pero equivocado.

## Por qué NO pertenece al incremento que la destapó

Medido neutralizando `_atender_conversacion_general` —la única rama que Conversación General v1 añade
antes de la puerta—:

```
CON detector: 19/24, 5 llamadas al LLM
SIN detector: 19/24, 5 llamadas al LLM
consultas con resultado distinto: 0
```

El incremento **no introduce ni agrava** esta diferencia.

## Qué obliga esta deuda

**Toda cifra de ADR-0014 se documenta con su condición**: «24/24 **con memoria vacía**». Publicarla
sin la coletilla la convierte en una propiedad incondicional que no se sostiene, y eso es
exactamente lo que la regla del CEO (2026-08-04) prohíbe: *nunca se documenta como propiedad
arquitectónica un valor numérico que no pueda derivarse formalmente del modelo*.

## Condición que la promovería a trabajo

Si el uso real produce **una sola** respuesta fabricada sobre una entidad equivocada, deja de ser
deuda documental y pasa a ser un defecto de producto con Decision Package. Hoy no hay evidencia de
que haya ocurrido: el CEO no lo ha reportado y el recuperador N1 está medido contra la batería.

**No se abre trabajo por anticipado** (regla del CEO, 2026-08-04: el desarrollo lo guía la evidencia
del uso real, no las ideas).
