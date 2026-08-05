# Decision Package — Intent Router delante de Memoria

**Estado:** propuesto · **Fecha:** 2026-08-05 · **Decide:** CEO · **Propone:** APUS-5
**Origen:** defecto reproducido por el CEO en uso real (`88132f6`), no por diseño anticipado.

---

## 1 · El problema es arquitectónico, no de patrones

El CEO escribió *«buenos días Aurora, ¿qué tienes pendiente para hoy?»* y recibió *«No tengo ningún
recuerdo registrado sobre eso»*. La causa está en una línea de `_es_consulta_de_memoria`:

```python
return any(p in t for p in _PATRONES_CONSULTA_MEMORIA) or _es_pregunta(texto)
```

**`or _es_pregunta(texto)`: toda frase interrogativa es una consulta de memoria.** Y ese `or` es
deliberado — su docstring lo justifica: amplía la cobertura de ADR-0014 para que el LLM no invente
recuerdos ante preguntas sin marcador explícito.

**La garantía y el defecto viven en la misma línea.** Por eso ampliar o recortar la lista de patrones
no resuelve nada: mueve el límite sin cambiar la estructura. El diagnóstico del CEO es correcto —
**el defecto es que Memoria es el destino por defecto de todo lo que nadie más reclamó.**

---

## 2 · Qué se decide

Introducir un **Intent Router determinista** que clasifique cada turno en un dominio antes de
consultar nada, con seis destinos: **Estado Operativo · Capacidades · Centro de Gobierno · Modelo de
Usuario · Memoria Episódica · Conversación General**.

**Solo el dominio «Memoria Episódica» —el pasado compartido— llega a Memoria y activa ADR-0014.**

**El dominio por defecto deja de ser Memoria y pasa a ser Conversación General.** Ese es el cambio que
resuelve el defecto reportado; todo lo demás es su consecuencia estructural.

---

## 3 · Por qué NO es un componente nuevo

La regla del proyecto es dura: *«prohibido crear un componente sin demostrar antes que no existe
equivalente, que no puede extenderse uno existente y que aumenta el IMA»*.

**Hoy el router YA EXISTE: está implícito.** `on_turn` evalúa 12 detectores en cascada —modelo de
usuario ×4, notificaciones, reglas ×3, ausencia de memoria, más las 4 del incremento pendiente— y
**la precedencia la fija el orden en que se escribieron las líneas**. No hay tabla, no hay contrato,
no hay lugar donde consultar quién gana. Ya ha producido **4 defectos de interferencia verificados**,
y el propio Checklist advierte que antes de añadir una superficie hay que comprobar que no colisiona
con las existentes.

El Intent Router **no añade lógica: la hace explícita**. Un punto único de decisión, con precedencia
declarada y auditable, en vez de precedencia accidental. Eso es exactamente **INV-7** (*el plan se
interpreta en un solo punto y nunca se reinterpreta*) aplicado a la intención.

**Reduce complejidad en vez de añadirla**, que es lo que D26 exige para admitir un cambio.

---

## 4 · Conformidad con las garantías

| Regla | Cómo se cumple |
|---|---|
| **ADR-0014 §2** — *«identificar la intención se hace por patrones en el núcleo, no por clasificación del modelo: delegar esa decisión en el LLM reintroduciría la dependencia que la decisión elimina»* | **El router es 100 % determinista.** Ni una llamada al LLM para clasificar. Esta es la regla que más fácilmente se rompería «mejorando» el router con un clasificador |
| **ADR-0014 §1** — el LLM no puede inventar recuerdos | Se **conserva íntegra**, y mejor delimitada: la ruta de ausencia sigue siendo determinista, pero solo se activa en su dominio real. Hoy protege de más y estropea la conversación |
| **ADR-0014 §4** — toda garantía debe ser código verificable con prueba determinista | El enrutado es una función pura `texto → dominio`: comprobable frase a frase |
| **El Core es la única fuente de verdad** | El router decide el DOMINIO; los hechos los sigue dando cada fuente |
| **D40** | Sin ejecutable nuevo; vive dentro del orquestador ya compuesto |
| **D23** | No amplía el alcance funcional: reorganiza el enrutado existente |

---

## 5 · Ataque a la propuesta

| Ataque | Respuesta |
|---|---|
| **«Un router determinista sigue siendo listas de patrones. ¿En qué mejora?»** | El defecto **nunca fue la lista**: era que Memoria fuese el destino por defecto. El router cambia el default y hace la precedencia explícita. Con las mismas listas, «buenos días, ¿qué tienes pendiente?» deja de ir a Memoria — no por tener más patrones, sino porque ya no cae en el cajón |
| **Reorganizar 12 superficies con 4 defectos de interferencia conocidos es la operación más arriesgada posible** | **Cierto, y es el riesgo principal.** Mitigación obligatoria: **prueba de equivalencia** — grabar la respuesta actual a un corpus amplio de frases ANTES de tocar nada, y exigir que tras el cambio **nada varíe salvo donde se quiere que varíe**, con la lista de cambios esperados declarada por adelantado. Sin esa red, no debe implementarse |
| **«Conversación General» va al LLM, y el LLM tarda 25,8 s en 8 tokens** | Hoy el camino por defecto es `MockProvider`, un clasificador de 5 reglas: el saludo ya se responde sin modelo. El router **no empeora la latencia**; solo deja de desviar al usuario a una respuesta falsa. Pero **conviene decirlo: «conversación general» hoy es pobre**, y este DP no lo arregla |
| **¿Y si el router se equivoca de dominio?** | Un fallo de enrutado es **visible** (respuesta fuera de tema) y **acotado** (una función pura, un punto que corregir). Hoy el fallo es invisible: la respuesta parece legítima y el usuario concluye que AURORA no sabe nada |
| **¿Aumenta el IMA?** | Sí: convierte una decisión implícita y no medible en una función pura auditable, prerrequisito para que AURORA razone algún día sobre su propio enrutado |

---

## 6 · Lo que este cambio NO resuelve

- **No mejora la conversación general.** Un saludo seguirá respondiéndose pobremente; solo dejará de
  ser respondido con una falsedad.
- **No sustituye al incremento conversacional pendiente** en el worktree: aquel aporta las respuestas
  desde las fuentes; este decide cuándo se usan. Son complementarios y **este debe ir primero**.
- **No arregla la telemetría en pantalla** — eso es *Experiencia Conversacional v1*.

---

## 7 · Retorno sobre Tokens

Convierte 12 decisiones dispersas en una tabla revisable de un vistazo: cada superficie futura se
añade declarando su dominio, sin releer el orquestador entero ni arriesgar interferencias. **Reduce
el contexto necesario para tocar la conversación**, que es hoy el fichero más caro de modificar.

---

## 8 · Qué se pide aprobar

1. **Intent Router determinista** con los 6 dominios, precedencia declarada y **dominio por defecto =
   Conversación General**.
2. **Prueba de equivalencia obligatoria** antes de tocar nada: corpus grabado, cambios esperados
   declarados por adelantado, todo lo demás invariante.
3. **Mutante irrenunciable:** *«el LLM responde cuando no hay recuerdos»* debe seguir muriendo. Si al
   terminar sobrevive, se rompió ADR-0014 arreglando la experiencia — y el incremento se revierte.
4. **Orden:** este DP va **antes** de integrar el incremento conversacional pendiente, porque cambia
   la estructura sobre la que aquel se apoya.

**Bloqueado por cuota:** requiere auditoría independiente, hoy no disponible. **No se implementa hasta
que el CEO apruebe y exista capacidad de auditar.**
