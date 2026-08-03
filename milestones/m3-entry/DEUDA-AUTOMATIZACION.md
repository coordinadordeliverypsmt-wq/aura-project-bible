# Deuda registrada — Automatización definida por el usuario (MVP capacidad 5)

**Estado:** registrada, **no bloqueante**. Capacidad **APROBADA POR EL CEO el 2026-08-02** tras verificar la
evidencia de persistencia.
**Alcance del cierre:** el usuario crea una automatización en lenguaje natural, esta **persiste**, se
**ejecuta sola** cuando ocurre el evento, **sobrevive al reinicio** de AURA y puede **inspeccionarse**.

**Evidencia que sustentó la aprobación** (verificación exigida por el CEO antes de aprobar):

1. **Artefacto físico:** `~/.aura/reglas.jsonl` (JSONL append-only, junto al estado permanente del
   usuario). Una única ruta de escritura en todo el código: `AlmacenReglas.crear`, modo append.
2. **Modelo persistido = modelo aprobado:** `rule_id`, `evento`, `condicion` declarativa, `accion`, `args`
   por referencia (`$evento.ruta`), `estado`, `metadatos` — más `user_id` (aislamiento, P-ARQ-5).
3. **Carga desde el artefacto, sin recreación:** tras reiniciar con `AlmacenReglas.crear` **saboteado para
   abortar el proceso**, la regla se ejecutó igual y el fichero quedó **idéntico byte a byte** (mismo
   inode, `mtime_ns` y SHA-256; 1 línea). Las reglas se leen en el **constructor**, antes del primer turno.
4. **Descarte de recreación implícita:** una regla **escrita a mano fuera de AURA**, con un `rule_id`
   inexistente en el repositorio, fue descrita y ejecutada correctamente. El sistema no puede haberla
   generado: solo leído.
5. **Control negativo permanente:** `test_sin_regla_no_hay_copia` — sin artefacto no hay copia, lo que
   descarta un comportamiento incondicional.

`metadatos.frase` es **trazabilidad, no mecanismo**: la regla escrita a mano carece de ese campo y se
ejecuta igual. La persistencia no es el par `{frase, acción}` que el CEO rechazó explícitamente.

Este documento existe para que lo que quedó fuera **no se olvide ni se confunda con un descuido**. Todo lo
listado fue excluido **deliberadamente** por decisión del CEO al aprobar el Decision Package, o detectado
durante la construcción y acotado aquí.

## 1 · Excluido por decisión explícita del CEO (alcance del MVP)

| # | Deuda | Por qué no bloquea hoy | Qué haría falta |
|---|---|---|---|
| D-A-1 | **Editar / desactivar reglas** desde la conversación | El almacén es append-only y el modelo ya tiene `estado`; hoy solo se crea e inspecciona. | **Más caro de lo estimado** — ver `D-A-9`. |
| D-A-2 | **Prioridades y resolución de conflictos** entre reglas | Con una sola regla reconocible no hay conflicto posible. | Campo de prioridad + orden determinista + prueba de dos reglas sobre el mismo evento. |
| D-A-3 | **Cadenas de reglas y prevención de bucles** | Las acciones disparadas por una regla **no republican eventos**, así que hoy es estructuralmente imposible encadenar. Al levantar esa restricción, el riesgo de bucle aparece de golpe. | Profundidad máxima / detección de ciclos **antes** de permitir que una regla dispare a otra. |
| D-A-4 | **Disparadores externos** (hora, sensores, correo, hogar) | Hoy el bus solo produce `action.command` y `perception.turn_end`; no hay más eventos que ofrecer. | Productores de eventos + su gate de habilitación (ADR-0019). |
| D-A-5 | **Sugerencia automática de reglas por aprendizaje** | Requiere datos de uso real (misma dependencia que M3.2b). | Capacidad 8 · inferencia. |

## 2 · Deuda accionable

| # | Deuda | Riesgo real hoy | Qué haría falta |
|---|---|---|---|
| **D-A-11** | **Una línea corrupta en `reglas.jsonl` tumba TODO el arranque de AURA** | Auditoría independiente 2026-08-02. `_cargar` no captura `JSONDecodeError` ni `TypeError`, y `AlmacenReglas` se construye en `composicion.componer()`: un carácter dañado impide arrancar el sistema entero, no solo las automatizaciones. **Preexistente**, pero este incremento duplica las escrituras (crear + desactivar). | Descartar la línea ilegible y registrar el hecho en vez de propagar la excepción. Es **disponibilidad**, no integridad: el append-only garantiza que nada se pierde. |
| D-A-7 | **Sin semántica transaccional**: si la acción de una regla previa falla, la acción del usuario se ejecuta igualmente. | Acotado: el fallo **no se silencia** (se narra al usuario y va al Centro de Notificaciones), y la acción del usuario que hoy dispara reglas —borrar— es de lista roja, o sea que el usuario está presente y la confirma. Aun así, "guarda **antes** una copia" es una promesa que un fallo silencioso de la copia debilitaría. | Decidir política explícita: ¿un disparo previo fallido **aborta** la acción? No es trivial —la copia falla legítimamente si el respaldo ya existe—, así que requiere su propio Decision Package. |


## 3 · Observaciones técnicas (NO son backlog)

**Criterio del CEO (2026-08-02): solo se registra como DEUDA lo que bloquea un incremento, compromete la
arquitectura, compromete la seguridad o puede producir pérdida de información.** Todo lo demás vive aquí
como observación hasta que merezca convertirse en trabajo. El backlog debe permanecer **pequeño y
accionable**; una lista larga de deuda menor no informa, entierra lo importante.

| Observación | Por qué NO es deuda hoy | Se promueve a deuda si… |
|---|---|---|
| **El reconocedor confunde órdenes puntuales con automatizaciones.** *«Cuando llegue a casa, borra el temporal y guarda una copia»* crea una regla permanente **y no ejecuta el borrado**. Acierta por subcadena (*«describir»* contiene `escrib`; *«promuevas»* contiene `muev`). Falso negativo: *«Antes de borrar cualquier archivo, guarda una copia»* no se reconoce. | Molesto, no peligroso: no destruye datos ni compromete la arquitectura. La regla creada de más solo produce copias, que son reversibles. | Un falso positivo llegue a disparar una acción **destructiva**, o el usuario se queje del comportamiento en uso real. |
| **La respuesta arrastra un sufijo técnico** (`[accion borrar_archivo ejecutada]`). | Cosmético. Es la marca de evidencia de ejecución de ALERTA-005, presente en todo el sistema desde M2.5. | Se aborde la limpieza del canal conversacional como incremento propio. |
| **Al mover un archivo, el mensaje expone la ruta absoluta del sistema.** | UX confusa, sin implicación de seguridad (es la ruta del propio usuario). | Aparezcan rutas de terceros o de sistema en mensajes al usuario. |

## 4 · Cerrado

- **`D-A-6` — el reconocedor cubría un solo patrón** → **RESUELTO** (2026-08-02, `98e3352`): reconoce
  cuatro disparadores (borrar, escribir, mover, renombrar), cada uno con su regla independiente.

## 5 · Lo que este incremento **sí** dejó cerrado (para no reabrirlo por error)

- El **modelo de regla persistido es el definitivo** (`rule_id`, `evento`, `condicion` declarativa, `accion`,
  `args` por referencia al evento, `estado`, `metadatos`). Ampliar el reconocedor o añadir disparadores no
  obliga a migrar los datos ya escritos.
- Las reglas **no son un atajo**: cada disparo recorre el motor único, con permisos y dry-run (RN-5).
- `copiar_archivo` es **lista verde por reversibilidad** (solo crea `<ruta>.copia`, con `O_EXCL`: nunca
  sobrescribe). Es la única operación "creadora" verde y su clasificación depende de esa garantía: **si
  alguna vez se le permitiera sobrescribir, debe pasar a lista roja en el mismo cambio.**
