# Deuda registrada — Automatización definida por el usuario (MVP capacidad 5)

**Estado:** registrada, **no bloqueante**. El MVP está cerrado y demostrado (2026-08-02).
**Alcance del cierre:** el usuario crea una automatización en lenguaje natural, esta **persiste**, se
**ejecuta sola** cuando ocurre el evento, **sobrevive al reinicio** de AURA y puede **inspeccionarse**.

Este documento existe para que lo que quedó fuera **no se olvide ni se confunda con un descuido**. Todo lo
listado fue excluido **deliberadamente** por decisión del CEO al aprobar el Decision Package, o detectado
durante la construcción y acotado aquí.

## 1 · Excluido por decisión explícita del CEO (alcance del MVP)

| # | Deuda | Por qué no bloquea hoy | Qué haría falta |
|---|---|---|---|
| D-A-1 | **Editar / desactivar reglas** desde la conversación | El almacén es append-only y el modelo ya tiene `estado`; hoy solo se crea e inspecciona. | Superficie conversacional + escritura del cambio de `estado`. |
| D-A-2 | **Prioridades y resolución de conflictos** entre reglas | Con una sola regla reconocible no hay conflicto posible. | Campo de prioridad + orden determinista + prueba de dos reglas sobre el mismo evento. |
| D-A-3 | **Cadenas de reglas y prevención de bucles** | Las acciones disparadas por una regla **no republican eventos**, así que hoy es estructuralmente imposible encadenar. Al levantar esa restricción, el riesgo de bucle aparece de golpe. | Profundidad máxima / detección de ciclos **antes** de permitir que una regla dispare a otra. |
| D-A-4 | **Disparadores externos** (hora, sensores, correo, hogar) | Hoy el bus solo produce `action.command` y `perception.turn_end`; no hay más eventos que ofrecer. | Productores de eventos + su gate de habilitación (ADR-0019). |
| D-A-5 | **Sugerencia automática de reglas por aprendizaje** | Requiere datos de uso real (misma dependencia que M3.2b). | Capacidad 8 · inferencia. |

## 2 · Detectado durante la construcción (acotado, no excluido por el CEO)

| # | Deuda | Riesgo real hoy | Qué haría falta |
|---|---|---|---|
| D-A-6 | **El reconocedor de lenguaje natural cubre UN solo patrón** ("guarda una copia antes de borrar"). Si el usuario define otra automatización, AURA no la reconoce. | Producto: la capacidad se demuestra pero no generaliza. **No es deuda arquitectónica**: la generalidad ya vive en el modelo de regla (`evento → condición → acción`, args por referencia) y en el motor; ampliar el reconocedor **no obliga a migrar** ninguna regla ya escrita en disco. | Ampliar el reconocedor (o delegar el *parseo* en el LLM manteniendo la **decisión** en el núcleo, ADR-0014). |
| D-A-7 | **Sin semántica transaccional**: si la acción de una regla previa falla, la acción del usuario se ejecuta igualmente. | Acotado: el fallo **no se silencia** (se narra al usuario y va al Centro de Notificaciones), y la acción del usuario que hoy dispara reglas —borrar— es de lista roja, o sea que el usuario está presente y la confirma. Aun así, "guarda **antes** una copia" es una promesa que un fallo silencioso de la copia debilitaría. | Decidir política explícita: ¿un disparo previo fallido **aborta** la acción? No es trivial —la copia falla legítimamente si el respaldo ya existe—, así que requiere su propio Decision Package. |
| D-A-8 | **La respuesta al usuario arrastra un sufijo técnico** (`[accion borrar_archivo ejecutada]`). | Es la marca de evidencia de ejecución real de ALERTA-005, presente en **todo** el sistema desde M2.5, no algo introducido aquí. Choca con el principio que el CEO fijó para el Centro de Notificaciones: *"eventos comunicables, no eventos técnicos"*. | Incremento propio: mover la evidencia de ejecución a la auditoría y dejar el canal conversacional limpio, sin perder la garantía de ALERTA-005. Afecta a pruebas e2e existentes. |

## 3 · Lo que este incremento **sí** dejó cerrado (para no reabrirlo por error)

- El **modelo de regla persistido es el definitivo** (`rule_id`, `evento`, `condicion` declarativa, `accion`,
  `args` por referencia al evento, `estado`, `metadatos`). Ampliar el reconocedor o añadir disparadores no
  obliga a migrar los datos ya escritos.
- Las reglas **no son un atajo**: cada disparo recorre el motor único, con permisos y dry-run (RN-5).
- `copiar_archivo` es **lista verde por reversibilidad** (solo crea `<ruta>.copia`, con `O_EXCL`: nunca
  sobrescribe). Es la única operación "creadora" verde y su clasificación depende de esa garantía: **si
  alguna vez se le permitiera sobrescribir, debe pasar a lista roja en el mismo cambio.**
