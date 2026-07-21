---
documento: "Hallazgo de M2 — Fiabilidad en la selección de acciones del modelo local"
fecha: 2026-07-21
autor: "CTO"
registro: "Ordenado por el CEO en el gate de cierre técnico de M2"
clasificacion: "Limitación de capacidad del modelo — NO es un fallo de seguridad"
estado: "Registrado, contenido por arquitectura, no resuelto"
---

# Hallazgo — El modelo local elige acciones poco fiables

## 1. Qué se observó

Durante la demo de capacidad M2 sobre stack real (Ollama, `qwen2.5:0.5b`, sin APIs de terceros), de
tres peticiones conversacionales:

| Petición del usuario | Acción elegida por el modelo | Valoración |
|---|---|---|
| *"Busca mis archivos de factura en `/tmp/.../documentos`"* | `listar_directorio` | **Aproximada.** Lo razonable era `buscar_archivo`; el resultado es útil pero no es lo pedido |
| *"Borra el archivo `.../borrador-viejo.txt`"* | `borrar_archivo` | **Correcta** |
| *"Recuérdame comprar pan mañana"* | `abrir_archivo` | **Claramente equivocada.** No guarda relación con la petición |

Una elección correcta, una aproximada y una equivocada de tres.

Con `qwen2.5:3b` no hay dato comparable: la demo **agotó 600 s por turno** y abortó, con el equipo
haciendo swap. La medición no se pudo obtener y no se sustituye por estimaciones.

## 2. Por qué NO es un fallo de seguridad

**La acción equivocada no causó ningún daño, y no fue por suerte.** Los controles del Core lo
impidieron por construcción:

| Control | Qué hizo en este caso concreto |
|---|---|
| **Catálogo finito y tipado** (M2.1) | El modelo solo puede elegir entre 27 acciones declaradas. No pudo inventar una operación ni envolver un comando arbitrario |
| **Clasificación en el Core** (ADR-0014) | `abrir_archivo` se clasificó como **lista verde, solo lectura** por el catálogo, no por lo que el modelo dijera de ella |
| **Validación de ámbito** (M2.1) | La ruta debía caer dentro de las raíces permitidas; una ruta alucinada fuera de ámbito se habría rechazado |
| **Lista roja + HITL** (ADR-0003) | Si el modelo hubiera elegido una acción destructiva, habría exigido confirmación humana con previsualización |
| **Dry-run** (M2.3 / 5.3 §3.1) | Nada que altere el estado se ejecuta sin previsualizarse primero |

El peor resultado posible de una equivocación del modelo en la configuración actual es **una acción
inútil de solo lectura**, dentro del ámbito del propio usuario. No una destructiva.

### La conclusión de arquitectura

> **La seguridad de AURA no depende de que el modelo acierte.**

Esto se diseñó así desde ADR-0003 y se reforzó en ADR-0014, pero hasta M2 era una afirmación de
diseño. Ahora es una **observación empírica**: el modelo se equivocó de verdad, en una demo real, y
el sistema absorbió el error sin consecuencias.

Es probablemente el resultado más valioso de M2 y conviene no perderlo de vista al planificar M3:
cualquier cambio que traslade decisiones de seguridad al modelo —clasificar acciones, validar rutas,
decidir si algo requiere confirmación— destruiría esta propiedad.

## 3. Qué sí compromete

**La utilidad del producto, no su seguridad.** Un compañero que interpreta mal una de cada tres
peticiones es frustrante aunque nunca rompa nada. Por eso el hallazgo se refleja en el **Product
Readiness**, bajando *"Entiende y responde con sentido"* de 12% a 10% — la única dimensión que
retrocedió en M2.

Conviene ser preciso sobre qué significa esa bajada: **el sistema no empeoró**. Lo que mejoró es la
información disponible. En M1 la cifra reflejaba "funciona con un LLM local"; ahora refleja
comportamiento observado en peticiones reales.

## 4. Causa probable y limitaciones del dato

El modelo evaluado tiene **0,5 B de parámetros** — se eligió porque el de 3 B no completa turnos en
este hardware. En M1 se verificó consistencia inter-modelo del 100% entre ambos, pero **en el
escenario de M1**: catálogo de 15 acciones y peticiones de domótica. M2 amplió el catálogo a 27
acciones con argumentos tipados, un problema de selección notablemente más difícil.

Limitaciones honestas de esta evidencia:

- **Muestra de tres peticiones.** Suficiente para registrar la observación, insuficiente para
  cuantificar una tasa de acierto.
- **Un solo modelo.** No sabemos cuánto de esto es tamaño del modelo y cuánto es diseño del prompt.
- **Sin comparación con 3 B**, que es precisamente el dato que permitiría separar ambas causas.

No se declara una tasa de error porque los datos no la sostienen.

## 5. Vías de mejora (ninguna decidida)

| Vía | Comentario |
|---|---|
| **Hardware objetivo** (HC-1) | Permitiría correr un modelo mayor. Es la palanca principal y ya es prioridad declarada para M3 |
| Modelo base distinto | Uno afinado para *tool calling* podría acertar más a igual tamaño |
| Prompt más estructurado | El catálogo se inyecta completo (27 acciones); acotarlo por contexto podría ayudar |
| Confirmación de intención | Preguntar antes de actuar cuando la confianza es baja — **añade fricción y latencia**, hoy inasumible a más de dos minutos por turno |

**Ninguna se implementa ahora.** Todas dependen de la decisión de hardware y modelo base que el CEO
ha situado como prioridad de M3, antes de incorporar capacidades nuevas.

## 6. Estado

**Registrado y contenido, no resuelto.** No se abre alerta de arquitectura: no hay riesgo para la
integridad del sistema ni decisión de arquitectura pendiente que este hallazgo bloquee. Es una
limitación de capacidad conocida, con impacto medido en el Product Readiness y con su resolución
condicionada a una decisión ya priorizada.

Evidencia completa: `milestones/m2-exit/demo-m2-stack-real.log`.
