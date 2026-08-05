# Decision Package — Conversación General v1 (implementación mínima)

**Estado:** propuesto · **Fecha:** 2026-08-05 · **Decide:** CEO · **Propone:** APUS-5
**Sustituye** al rediseño completo del Intent Router, que el CEO detiene tras el rechazo de la tabla.

---

## 1 · Qué se decide

**No se refactoriza nada.** Se añade **un solo detector** —`_es_conversacion_general`— con una lista
corta y explícita de frases cotidianas, evaluado **inmediatamente antes** de la puerta de Memoria.

Todo lo demás del orquestador queda **intacto**: los 12 detectores actuales, su orden, sus patrones y
la puerta de ADR-0014. Ni una línea.

---

## 2 · Por qué así y no refactorizando la regla de Memoria

La auditoría midió el riesgo con precisión: **tocar la regla de admisión de Memoria lleva ADR-0014 de
24/24 a 0/24** sobre las negativas de la batería oficial, y `test_grounding_core.py` seguiría en verde
porque sus 4 frases llevan marcador. Ese es el camino que este DP **evita por completo**.

**La diferencia es toda la propuesta:**

| Enfoque | Qué toca | Riesgo sobre ADR-0014 |
|---|---|---|
| Refactor del router (rechazado) | reglas de admisión de 13 dominios | **24/24 → 0/24** |
| **Este DP** | añade una lista **positiva** delante | **ninguno**: lo no listado sigue el camino de hoy, bit a bit |

Una lista de exclusión **positiva y cerrada** solo puede desviar lo que nombra. Las 24 negativas
(«¿cuál es la combinación de mi caja fuerte?») **no estarán en la lista**, luego siguen llegando a la
puerta de ADR-0014 exactamente como hoy. La garantía no se toca ni se delimita: se deja quieta.

---

## 3 · Los ~20 casos

Semilla propuesta, a fijar con el CEO. Incluye las 5 frases que pidió y las que el uso real ya produjo:

**Saludos y cortesía** — buenos días · buenas tardes · buenas noches · hola · qué tal · cómo estás ·
cómo te va · gracias · adiós · hasta luego

**Estado de AURORA en lenguaje llano** — qué tienes pendiente · qué tienes pendiente para hoy ·
qué tal vas · cómo va todo · qué hay de nuevo

**Sobre ella misma** — quién eres · qué eres · para qué sirves

**Sobre sus capacidades** — qué puedes hacer · qué sabes hacer · en qué me puedes ayudar

**Regla de admisión:** coincidencia por **frase completa normalizada** o por prefijo declarado. **Nada
de `any(patrón in texto)`**: esa es la construcción que produjo el defecto original. Una lista laxa
recrearía el problema en el otro sentido.

**Qué responde cada grupo** — se decide en implementación, sin capacidades nuevas: los saludos y
«quién eres» con plantilla determinista; «qué tienes pendiente» y «cómo va todo» leyendo el Estado
Operativo si está cableado, y si no, declarando que no hay nada activo; las capacidades desde el
registro. **Todo determinista, sin LLM** (ADR-0014 §2).

---

## 4 · Garantías y verificación

| Regla | Cómo se cumple |
|---|---|
| **ADR-0014 §1** | La puerta de Memoria **no se modifica**. Prueba obligatoria: las **24 negativas** de `bateria_memoria.json` siguen dando `provider == "core"` y **cero** llamadas al LLM |
| **ADR-0014 §2** | El detector es determinista. Sin clasificador |
| **No interferencia** | Se inserta **justo antes** de la puerta de Memoria: las 12 superficies previas se evalúan primero y **nada puede robarles una frase** |
| **Prueba de equivalencia** | Grabar el corpus **antes**. `bateria-intencion.json` (172 casos) existe y **ninguna prueba lo lee** — se estrena aquí. Cambios esperados declarados: **solo** las frases de la lista. Todo lo demás, idéntico |
| **Mutantes** | (a) el detector no detecta; (b) la lista se evalúa **después** de Memoria (no cambiaría nada: debe morir); (c) coincidencia por subcadena en vez de frase completa; (d) **el mutante que no existía**: la puerta de ADR-0014 se salta — debe morir contra las 24 negativas |

**El mutante (d) es el irrenunciable que la auditoría descubrió que nunca se había escrito.** Se
escribe aquí, en el incremento más pequeño posible, que es el mejor momento para estrenarlo.

---

## 5 · Lo que este DP NO hace

- **No arregla los 200 casos.** Deliberado: los siguientes salen del uso real, no de la imaginación.
- **No hace explícita la precedencia** de las 12 superficies. Sigue siendo implícita y sigue siendo
  deuda declarada; el rediseño queda **aparcado**, no cancelado.
- **No mejora la conversación general abierta.** Fuera de la lista, todo sigue igual que hoy.
- **No oculta la telemetría** — eso es *Experiencia Conversacional v1*.

**Riesgo declarado:** una lista cerrada resuelve exactamente lo que enumera. «Qué tienes pendiente
para mañana» fallará si no está. **Es aceptable a propósito**: cada fallo del CEO en uso real es una
entrada nueva y una evidencia registrada, que es justamente el mecanismo que se quería arrancar.

---

## 6 · Retorno sobre Tokens

Un detector y una lista frente a un refactor de 13 superficies. **Auditable en una sesión corta** —
importante con la cuota agotada— y **reversible en un commit** si el uso real lo desmiente.

---

## 7 · Qué se pide aprobar

1. **Un detector nuevo** con lista cerrada de ~20 frases, insertado antes de la puerta de Memoria.
2. **La lista concreta** del §3 (o la que el CEO ajuste).
3. **Prueba irrenunciable**: las 24 negativas de la batería siguen atendidas por el núcleo, sin LLM.
4. **Prueba de equivalencia** sobre los 172 casos de `bateria-intencion.json`, con los únicos cambios
   esperados declarados por adelantado.
5. Protocolo completo: RED → GREEN → MUTACIÓN → **auditoría independiente** → integración.

**Bloqueado por cuota** para la auditoría. La implementación sí cabe en una sesión corta.
