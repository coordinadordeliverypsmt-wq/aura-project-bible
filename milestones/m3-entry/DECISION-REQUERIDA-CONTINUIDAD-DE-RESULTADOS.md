---
documento: "Decisión requerida — continuidad de resultados de ejecución entre turnos"
tipo: "PROPUESTA — no ratificada. Este documento NO decide nada."
fecha: 2026-09-21
mantenido-por: "APUS-5 (CTO)"
decide: "CEO (Mauricio)"
checkpoint: "6dad6af (árbol con cambios sin commitear)"
---

# Decisión requerida · qué puede recordar AURA de lo que ejecuta

**Lo que este documento aporta y que antes no existía:** la pregunta ya no es «¿debería AURA
recordar resultados?». Medido `[EJEC]` el 2026-09-21, **ya los recuerda**, bajo una política que el
CEO aprobó el 2026-09-15 para otra cosa. La decisión que falta es más estrecha, más concreta y más
urgente de lo que parecía.

---

## 1 · El hecho que cambia el encuadre

La misión anterior concluyó que AURA «no conserva resultados entre turnos». **Esa conclusión era un
artefacto de la medición:** se arrancaba un proceso por turno, y la ventana de trabajo vive en RAM.

Medido de nuevo dentro de **un solo proceso**, la ventana `Orchestrator._dialogue` contiene:

```
[hecho] 'Ejecuté «listar_directorio». 7 entrada(s): CENTRO-DE-GOBIERNO.md, audit.jsonl,
         cursores, estado_operativo.jsonl, memoria.json, memoria.json.backups, models'
```

Esa ventana está gobernada por **`DR-4`, aprobada por el CEO el 2026-09-15**
(`milestones/m3-entry/DECISIONES-REQUERIDAS-2026-09-15.md`). Sus parámetros, leídos del código:

| parámetro | valor | qué hace |
|---|---|---|
| `_DIALOG_N` | 6 | turnos que se conservan siempre tras un descarte |
| `_DIALOG_MAX` | 9 | turnos a partir de los cuales se descarta por bloques |
| `_RECORTE_AURA` | 160 | caracteres de cada respuesta previa de AURA que reentran en el prompt |

**Conclusión:** existe una política de retención aprobada para la memoria de trabajo, y los
resultados de ejecución ya viajan dentro de ella. Lo que **nadie ha decidido** es lo de abajo.

---

## 2 · Por qué esto no puede decidirlo el código

`DR-4` se decidió **por latencia y caché de prefijo**. Su expediente no menciona privacidad ni una
sola vez, y por una razón legítima: cuando se aprobó, **`leer_archivo` todavía no era una orden
conversacional**. La capacidad de leer ficheros del usuario desde la conversación llegó después.

El resultado es una consecuencia que nadie eligió. Medido `[EJEC]`:

```
USUARIO> lee el archivo /…/privado.txt
AURA   > Ejecuté «leer_archivo». Esto es lo que dice:
         IBAN ES91-2100-0418 clave del router colibri-verde-1978

USUARIO> cuéntame algo interesante sobre los pájaros      ← otro tema por completo

  prompt enviado al modelo:
  [conversacion reciente:
  (previo) tu: lee el archivo /…/privado.txt | AURA [HECHO]: Ejecuté «leer_archivo».
  Esto es lo que dice:
  IBAN ES91-2100-0418 clave del router colibri-verde-1978]
  Usuario: cuéntame algo interesante sobre los pájaros
```

**El contenido de un fichero del usuario reentra en el prompt de un turno que no tiene nada que ver.**
No es un fallo del código: es `DR-4` funcionando exactamente como se aprobó, sobre un dato que no
existía cuando se aprobó.

### Qué lo acota hoy, y hasta cuándo

Que no salga de la máquina. **No existe ningún proveedor de modelo remoto** —solo `OllamaProvider`,
local; sin endpoint, sin clave de terceros (`D24`, `ADR-0001`)—. Verificado y **fijado como prueba**
en `tests/integration/test_frontera_continuidad.py`.

El día que se añada un proveedor externo, `Bible 5.5 §2` («al LLM externo se envía el contexto
mínimo necesario, **nunca la memoria completa**; los datos identificables se redactan») se aplicaría
a esta ventana **sin que nada en el código la haga cumplir**. Esa prueba es el centinela de ese día.

---

## 3 · Las doce preguntas

Están redactadas para poder contestarse sin rehacer la investigación técnica. Cada una indica dónde
se implementaría y qué se rompe si se contesta mal.

### A · ¿Qué resultados pueden sobrevivir entre turnos?
Hoy: **todos**, en forma del texto que AURA dijo. Opciones técnicas: (1) todos, como ahora;
(2) solo los metadatos —qué capacidad, con qué desenlace— sin el payload; (3) por capacidad, con una
marca en el catálogo (`catalogo_capacidades.py`) que diga cuáles retienen payload.
**Consecuencia observable:** con (2), AURA podría decir «ejecuté una lectura» pero no repetir lo leído.

### B · ¿Cuánto duran?
Hoy: entre 6 y 9 turnos (`DR-4`), y mueren con el proceso. Opciones: mantenerlo; un tope distinto
para los resultados que para la conversación; o expirar por tiempo además de por turnos.
**Nota:** hoy no hay ninguna expiración por tiempo en ningún punto del sistema.

### C · ¿Cuál es el alcance?
Hoy: **proceso**. La ventana es un `dict` de instancia sin respaldo en disco (fijado como prueba).
Opciones: proceso (como ahora) · sesión · usuario · sistema.
**Consecuencia:** cualquier opción distinta de «proceso» exige crear persistencia que hoy no existe,
y entonces las preguntas D, F, G y H dejan de ser teóricas.

### D · ¿Qué contenido está prohibido retener?
La pregunta con más consecuencia. Hoy **no hay ninguna exclusión**. El caso concreto y medido es
`leer_archivo`. Opciones: (1) ninguna exclusión; (2) excluir el payload de las capacidades que
devuelven contenido del usuario, conservando el metadato; (3) redactar por patrón —IBAN, claves—, que
es la opción que `Bible 5.5 §2` ya nombra para el LLM externo; (4) preguntar al usuario.
**Advertencia:** (3) es una garantía que depende de acertar el patrón, y `ADR-0014 §4` dice que una
garantía no puede depender de un comportamiento probabilístico. Un patrón no es un modelo, pero
tampoco es una frontera demostrable.

### E · ¿Cómo se tratan los desenlaces que no son «ejecutada»?
Hoy: **igual que los buenos** — el texto entra en la ventana pase lo que pase. Medido: un
`leer_archivo` rechazado retiene «ruta fuera del ámbito permitido: '/etc/shadow'».
Casos a decidir por separado: **error** · **detenida** (gobierno: kill switch, permisos) ·
**`duplicate`** (idempotencia: no se volvió a ejecutar, así que no hay resultado nuevo) ·
**timeout** · **parcial** (la revisión compuesta puede ejecutar 2 de 3).
**Consecuencia:** retener un bloqueo como si fuera un dato permite que el modelo lo lea después y
razone sobre un contenido que el gobierno impidió obtener.

### F · ¿Cómo se purgan?
Hoy: por desplazamiento de la ventana y por muerte del proceso. No hay purga explícita, ni orden de
usuario, ni purga por sensibilidad.

### G · ¿Cómo se audita la lectura y la escritura?
Hoy: **no se auditan**. El audit log registra que una capacidad se ejecutó y con qué desenlace —eso
se corrigió en esta misión—, pero **nada registra que un resultado entró en la ventana ni que
reentró en un prompt**. Si se decide retener, esto pasa a ser obligatorio: sin ello no hay forma de
demostrar qué se le enseñó al modelo.

### H · ¿Puede el usuario pedir el borrado?
Hoy: **no existe la orden**. La soberanía (`ADR-0017 §3`) cubre la memoria personal —ver, exportar,
olvidar— pero no la ventana de trabajo, porque hasta ahora no se consideraba un almacén.

### I · ¿Qué ocurre al cambiar de tema?
Hoy: **nada, el resultado sigue ahí** — y se demostró que reentra en el prompt de un turno sobre
pájaros. Opciones: mantenerlo; detectar el cambio de tema y descartar; separar la ventana por tema.
**Advertencia:** detectar cambio de tema con el modelo choca con `ADR-0014 §4`.

### J · ¿Cómo se evita contaminar la memoria personal?
Hoy está **bien separado y ahora protegido**: la escritura a `memoria.json` usa solo el texto del
usuario, nunca el `say` de AURA (`D-FC-8 = B`). Fijado como prueba y como mutante `FC-M7`.
**La decisión solo debe confirmar que esta frontera se mantiene.** `Bible 4.1 §1` separa la memoria
de trabajo de las tres persistentes; mezclarlas convertiría el ruido de una ejecución en «lo que AURA
sabe de ti».

### K · ¿Cómo se evita que el audit log se convierta en memoria conversacional?
Hoy está **estructuralmente impedido y ahora protegido**. Medido sobre el audit log real (1209
entradas): esquema fijo de 7 claves `{level, module, msg, trace_id, audit, ts, seq}`, sin ningún
campo donde quepa un payload; `msg` más largo = 288 caracteres, y es una línea de configuración.
Ninguna superficie de conversación lo lee. Fijado por ausencia de acoplamiento en
`test_ninguna_superficie_de_conversacion_LEE_el_audit_log_para_responder`.

### L · ¿Qué debe decir AURA cuando no puede recuperar un resultado?

> **RESUELTO por la misión M8 del CEO (2026-09-22), no por inferencia.** El mensaje de misión fijó
> los doce escenarios, los ocho estados y la orden explícita: *«No permitas que todos estos estados
> colapsen en: "No tengo ningún recuerdo registrado sobre eso"»*. Construido: una superficie
> determinista que recupera de la ventana el último turno de ejecución y **repite lo que AURA ya
> dijo**, diciendo que lo repite y que no ha vuelto a ejecutar. Sin ejecución previa da una ausencia
> **propia** —«en esta conversación todavía no he ejecutado nada»— distinta de la de `ADR-0014`, que
> permanece intacta y sigue sosteniendo su `24/24`. Lo que sigue abierto es **D**, y pesa más ahora:
> ver la nota al final de este documento.

**Texto original de la pregunta, conservado:**

**Aquí hay un problema hoy, y conviene verlo.** Medido en los seis escenarios: AURA responde
siempre lo mismo —*«No tengo ningún recuerdo registrado sobre eso»*— sea cual sea el caso: listado,
auditoría, revisión, cambio de tema, lectura bloqueada.

Esa frase es la puerta de ausencia de `ADR-0014` y es **cierta sobre la memoria personal**, que es lo
único que consulta. Pero se pronuncia mientras **la ventana de trabajo contiene literalmente la
respuesta**. AURA no miente sobre lo que consultó; sí da a entender que no sabe algo que sí tiene.

Casos que hoy son indistinguibles y quizá no deberían serlo: *no se conservó* · *se conservó pero la
política no autoriza recuperarlo* · *nunca existió* · *existió y falló* · *lo impidió el gobierno*.

**No se ha tocado esa frase en esta misión, deliberadamente.** Ampliar la puerta de ausencia ya rompió
tres pruebas de `DR-1 = A` en un intento anterior, y decidir qué distingue AURA al responder es
precisamente esta decisión.

---

## 4 · Qué queda preparado y qué NO se ha hecho

**Preparado dentro de la autoridad vigente** (no crea política; fija lo que ya rige):

- 8 pruebas en `tests/integration/test_frontera_continuidad.py` que clavan las cuatro fronteras:
  la ventana **sí** retiene · **no** tiene respaldo en disco · el resultado **no** llega a la memoria
  personal · el audit log **no** lleva el payload y nadie lo lee para conversar · el contenido **sí**
  reentra en el prompt · el proveedor **es** local.
- 7 mutantes en `mutaciones/frontera-continuidad.toml`, **7 detectados, 0 supervivientes**.
- El registro forense corregido: ya no afirma «ejecutada» sobre órdenes detenidas o con error.

**NO se ha hecho, y por qué:**

- Ninguna persistencia nueva. Ningún TTL, alcance, exclusión por sensibilidad ni purga: todo eso es
  la decisión de arriba.
- No se ha tocado la puerta de ausencia de `ADR-0014` (punto L).
- No se ha extendido el versionado a «me llamo X» — ver la decisión hermana, abajo.

---

## 5 · Decisión hermana · ¿la identidad versiona?

Medido `[EJEC]` en esta misión:

```
tu> me llamo Mauricio      tu> me llamo Pedro      tu> ¿qué sabes de mí?
AURA> • me llamo Mauricio (me lo dijiste)
      • me llamo Pedro (me lo dijiste)
```

La familia posesiva «mi X es Y» **sí versiona** (verde → azul supersede correctamente). La familia
identidad «me llamo X» escribe sin `atributo`, `version`, `supersedes` ni `valid_until`, así que dos
valores contradictorios quedan vigentes a la vez y AURA afirma ambos.

**Lo que sí se corrigió en esta misión:** que redeclarar el **mismo** valor lo listara varias veces.
Es un defecto de proyección, no de política —`ADR-0023` dice que todo salvo el historial existe
«únicamente como proyección reconstruible»— y el historial conserva las tres declaraciones.

**Lo que NO se corrigió y se eleva:** que un valor **distinto** supersediera al anterior cambia la
vigencia y define por accidente parte de `D-AMP-3` (FORGET vs DELETE), que sigue sin firmar.

**Pregunta:** ¿debe «me llamo X» versionarse como «mi X es Y», cerrando la versión anterior con
`valid_until` y conservándola como historial?


---

## 6 · Lo que M8 cambió en la pregunta D (2026-09-22)

**D sigue sin decidir, y ahora tiene más consecuencia.** Antes de M8, el contenido de un fichero
leído quedaba en la ventana y reentraba en el prompt del modelo: exposición **incidental**. Desde
M8 el usuario puede además **pedirlo** y AURA se lo repite:

```
tu>   lee el archivo /…/privado.txt
AURA> Ejecuté «leer_archivo». Esto es lo que dice: IBAN ES91-2100 clave colibri-verde-1978
tu>   ¿y qué ponía?
AURA> Lo recupero de esta misma conversación; no lo he vuelto a ejecutar:
      Ejecuté «leer_archivo». Esto es lo que dice: IBAN ES91-2100 clave colibri-verde-1978
```

**El argumento por el que se construyó igualmente, para que el CEO pueda rebatirlo:** recuperar
repite al **mismo usuario**, en la **misma conversación** y en el **mismo proceso**, algo que AURA ya
le había dicho minutos antes. No es una divulgación nueva y no vuelve a leer el fichero —el Motor
Único recibe **cero** llamadas, fijado como prueba—. Lo que sí cambia es que pasa a ser
**recuperable a petición**.

**Lo que NO se hizo, a propósito:** ninguna exclusión por sensibilidad. Hoy no existe ninguna
clasificación de sensibilidad de resultados en el código —la única noción de «sensible» que hay
(`D-FC-2`) clasifica el **tema de la pregunta** (salud, derecho, finanzas, religión), no el contenido
de un resultado—. Inventarla sería exactamente la política que esta línea tiene reservada.

**Pregunta, sin recomendación:** ¿debe la recuperación excluir el contenido de las capacidades que
devuelven ficheros del usuario, entregando solo el metadato («leí ese archivo, tenía N líneas»)?
Opciones: (1) repetir todo, como ahora; (2) metadato sin payload para esa familia de capacidades;
(3) repetir solo si el usuario lo pide una segunda vez, confirmando; (4) redacción por patrón.
**Infraestructura ya preparada:** `test_el_CONTENIDO_de_un_fichero_se_repite_al_recuperar` fija hoy
el comportamiento, así que el día que se decida el cambio será deliberado y visible.

---

## 7 · Propuesta técnica integral del punto D (Director, 2026-11-06, v2 tras dos evaluaciones independientes) — **APROBADA por el CEO Operativo (2026-11-06), las ocho decisiones de §7.7** (acta `decisiones/2026-11-06-acta-continuidad-de-resultados-punto-d.md`); decisión 6: ver/exportar SÍ incluyen `resultado_accion`

**Encargo del CEO Operativo (2026-11-06):** el punto D del Umbral es el siguiente incremento; resolver las doce
preguntas y presentar el diseño. **No se ha modificado código.** Código verificado sobre `integracion/m3-entry`
`e1c86e1` (exploración de solo lectura; pruebas de las fronteras actuales en verde `[EJEC]`). La v1 de esta sección se
sometió a `arquitecto-evaluador` (CABE CON CONDICIONES: 4 afirmaciones falsas y una contradicción, corregidas aquí) y a
`security-reviewer` (APROBADO CON CONDICIONES: 2 ALTOS y 4 MEDIOS, incorporados). AgentShield no está instalado.

### 7.0 Qué «punto D» se cierra — hay dos, y esta propuesta resuelve los dos

- **D-privacidad** (el registrado: mapa maestro §18-19, `pendientes.md:24`, §2 y §6 de este documento): el contenido
  de un fichero leído reentra en el prompt de turnos ajenos y M8 lo repite.
- **D-reinicio** (el del encargo y del mapa §14: «el resultado no sobrevive al reinicio»).
- Precisión: el DoD del Umbral (§14) es «en UNA conversación … recuerda el resultado»; persistir tras reinicio **no**
  lo exige ni lo cierra (el Umbral sigue sin E2E físico de la cadena entera). D-reinicio es continuidad de producto.

### 7.1 Hecho de partida `[EJEC/LECT]`

- La «memoria del resultado» de S2 es solo la ventana `Orchestrator._dialogue` (RAM, `orchestrator.py:1723`; DR-4
  L1765-1767). Nada la escribe ni la lee de disco; tras reiniciar, M8 responde «todavía no he ejecutado nada».
- Sobrevive: `memoria.json` `kind="historico"` («usuario dijo: …», no recuperable, `contracts.py:52`) y el audit
  (metadato; HA real ya escribe `entidad: antes -> después (verificado=…)`, `home_assistant_real.py:407`).
- `ver`/`exportar`/`olvidar` del modelo del usuario solo operan sobre `_TIPOS` (`modelo_usuario.py:22,107-113`;
  `ejecutor_modelo_usuario.py:45,71,92,110`). La población de CM2 filtra por `_TIPOS` (`reloj_cm2.py:200`).
- La única guarda de PARADA de escritura está en `_finalizar_turno` (`orchestrator.py:3520`).
- No hay idempotencia persistente en el camino conversacional (`event_id` por turno).

### 7.2 Diseño recomendado

**D-privacidad — ventana en proceso.** Marca de catálogo `devuelve_contenido_usuario` (hoy: `leer_archivo`; ampliable
por declaración, no por heurística). Para esa familia: (a) la **reentrada en el prompt** de turnos posteriores lleva solo
el metadato («leí un archivo, N líneas»), nunca el contenido —elimina la exposición incidental (caso «pájaros», I)—;
(b) la **recuperación a petición** del usuario en la misma conversación sigue repitiendo el contenido (argumento de §6:
mismo usuario, misma conversación, sin nueva divulgación). Frontera demostrable por catálogo, compatible con
ADR-0014 §4. Cambia `test_el_CONTENIDO_de_un_fichero_se_repite_al_recuperar` solo en la rama del prompt.

**D-reinicio — registro de resultado de acción.** Kind nuevo `resultado_accion` en `memoria.json` (reutiliza el
historial append-only soberano con P1/P2-B; descartados el audit —frontera K, no borrable por el usuario— y
`estado_operativo` —modela tareas de AURORA—). Esquema **cerrado en campos Y en valores**, validado al escribir **y al
leer**:

| campo | regla |
|---|---|
| `capacidad` | identificador del catálogo (`^[a-z_]{1,64}$`) |
| `desenlace` | enum `{ejecutada, no_limpia, detenida, error, duplicada, desconocido}` |
| `entidad` | solo dominio hogar, `^[a-z_]+\.[a-z0-9_]{1,64}$`; **nula** en capacidades de ficheros y en las marcadas `devuelve_contenido_usuario` |
| `antes`/`despues` | enum de estados del dominio (`on, off, unavailable, unknown, playing, paused, idle, standby`) o entero acotado (volumen); cualquier otro valor → `desconocido` |
| `verificado` | bool estricto · `elementos`: int acotado · `trace_id`, `ts` (al minuto): formato fijo |

Rechazo de caracteres de control y Unicode de formato/bidireccional; ningún texto libre del motor ni de HA; plantillas de
respuesta fijas. Registro inválido al leer → se trata como ausente y se audita `resultado.rechazado`.

**Una sola redacción.** La descripción del desenlace se extrae de `_redactar_resultado_de_orden` a una función única
`describir_desenlace(meta)` que usan el turno en vivo y la recuperación tras reinicio (sin segunda implementación,
lección de ALERTA-005).

### 7.3 Las doce preguntas (v2)

| | Situación comprobada | Recomendación | Riesgo → mitigación | Impacto | Prueba de aceptación |
|---|---|---|---|---|---|
| **A** Qué sobrevive | Entre turnos: texto completo; entre reinicios: nada | En proceso: DR-4 (con 7.2 D-privacidad). Tras reinicio: **solo metadatos** validados | Pérdida de detalle de ficheros → se dice explícitamente | `_despachar_orden`, `recuperacion` | Reinicio real: «¿qué hiciste antes de reiniciarte?» → «encendí media_player.tv_sala: off → on (verificado)» |
| **B** Duración | 6-9 turnos; ningún TTL en el sistema | **Sin TTL** (decisión consciente, revisable con evidencia de uso; ningún número sin derivación, regla CEO 2026-08-04). La recuperación lee los registros por orden de `ts`/posición | Crecimiento/flood → límite de línea en lectura; medir crecimiento del historial real antes de fijar tope | Ninguno | Persiste tras dos reinicios |
| **C** Alcance | Proceso | **Usuario**, en `memoria.json` | — | `memory.py` sin cambio de formato | Dos usuarios: cada uno solo lo suyo |
| **D** Contenido prohibido | Ninguna exclusión | Persistido: **lista blanca de campos y valores** (7.2). En proceso: prompt sin contenido para `devuelve_contenido_usuario`; recuperación a petición lo repite | Inyección vía HA → enum/patrón, valores no válidos → `desconocido` | Validador, catálogo | Estado HA con `\n` e instrucción → `desconocido`; IBAN de `leer_archivo` ni en disco ni en el prompt de otro turno |
| **E** Desenlaces | Todos como texto en la ventana | Se persiste el **enum** sin el texto del motivo. **Con PARADA armada no se persiste nada** (coherente con 7.4): tras reinicio, una acción detenida por PARADA no consta | Motivo libre puede llevar rutas → solo enum | `describir_desenlace` | `error`/`duplicada` tras reinicio con su texto; `duplicada` no cuenta como ejecutada |
| **F** Purga | Ventana y muerte del proceso | Olvido lógico por lápida, mediante **operación de catálogo nueva o ampliada** (los predicados actuales no alcanzan el kind) | Olvido asimétrico: el audit conserva el metadato de la ejecución, como hoy para toda acción → declarado | `ejecutor_modelo_usuario` (catálogo; D23/acta) | Tras «olvida lo que hiciste», nada recuperable ni tras reinicio |
| **G** Auditoría | Rastro de entrada en ventana y de recuperación | `resultado.persistido` / `.no_persistido` / `.rechazado` (capacidad, desenlace, `trace_id`; **sin entidad**); recuperación con `origen=persistido` | — | `obs.log` | Escribir/recuperar/rechazar dejan rastro sin contenido |
| **H** Borrado por el usuario | No existe | **Sí**: «olvida lo que hiciste» / «borra el historial de acciones» por la vía de soberanía (T11: no se captura). **Ver/exportar NO lo incluyen hoy** (solo `_TIPOS`); incluirlo es decisión aparte (7.7-6) | ADR-0017 **§4** (ver/exportar/borrar) se cumple solo parcialmente sin 7.7-6 → declarado | Reconocedor de soberanía | Tras la orden, ningún registro recuperable |
| **I** Cambio de tema | El resultado reentra en el prompt | Sin detección de tema (ADR-0014 §4). Lo persistido **nunca** entra en el prompt; el contenido de ficheros deja de reentrar (7.2) | — | Construcción del prompt | Prompt tras reinicio y tras cambio de tema sin registros ni contenido de ficheros |
| **J** Memoria personal | Separada (D-FC-8=B, FC-M7) | `resultado_accion` en `KINDS_NO_RECUPERABLES`; **fuera de `_TIPOS`** (modelo del usuario, CM2); nunca el `say` | `KINDS_NO_RECUPERABLES` falla en abierto → prueba de que la exclusión es **permanente** (incluso si se revierte el código) | `contracts.py` | «¿qué sabes de mí?» sin registros; recall no los devuelve |
| **K** Audit no es memoria | Impedido y probado | Sin cambios; la recuperación no lee el audit | — | Ninguno | Prueba K en verde |
| **L** Qué dice AURA | M8 en proceso; tras reinicio «no he ejecutado nada» | Cascada: ventana (M8) → **registro persistido**, también cuando la ventana tiene ejecuciones nuevas si la pregunta es «antes de reiniciarte» → ausencia **sin «nunca»**: «no conservo registro de acciones anteriores; podría haber alguna». Lo persistido se presenta como «consta en mi registro local», no con el estatus de hecho del Core | Caída entre efecto y escritura → efecto sin registro (ver 7.4) | `recuperacion.py`, `estatus` | Tres ramas + «antes de reiniciarte» con ventana no vacía; motor: 0 llamadas |

### 7.4 Comportamiento ante fallos y seguridad

- **Orden:** el registro se escribe **después** del desenlace del motor; leer nunca re-ejecuta.
- **Fallo de escritura:** la acción no pasa a fallida; `resultado.no_persistido` y aviso honesto (INV-9).
- **Caída entre efecto y escritura (límite declarado):** el efecto queda sin registro; por eso la ausencia no dice
  «nunca». Opción no incluida, para decisión aparte: registro de intención antes del efecto.
- **Línea cortada:** P2-B. Un registro cortado se descarta entero; nunca se completan campos por inferencia.
- **PARADA:** guarda en el punto de escritura con `es_escritura_pasiva` (no un segundo `if`: ALERTA-005) y prueba
  estructural propia; el estado de PARADA se toma una vez, antes del motor. `KINDS_PASIVOS` no cambia.
- **Duplicación:** un reintento del usuario es otra ejecución (registro propio, legítimo); deduplicación por
  `trace_id` al leer; mutante de doble escritura.
- **Manipulación local (límite declarado):** `memoria.json` es texto plano; un proceso del mismo usuario podría anexar un
  registro falso. Mitigaciones incluidas: validación al leer, presentación como «registro local» (no hecho del Core),
  permisos 0600/0700. **No incluido:** HMAC por registro (requiere custodia de clave: decisión aparte, no se toca la
  custodia por un hallazgo).
- **Privacidad:** `entidad`+`ts` es un patrón de vida → `ts` al minuto; **dominios de seguridad (cerraduras, alarma,
  cámaras) excluidos de la persistencia**; el audit no lleva la entidad. Sin cifrado en reposo (deuda previa de
  `memoria.json`, Bible 4.1 §5).
- **Idempotencia de la acción tras reinicio:** fuera de alcance, declarada.

### 7.5 Pruebas RED/GREEN y mutación

RED: reinicio real (instancia nueva de `componer`, con dobles de HA: **no** es cierre físico, D34) → recuperación del
efecto; «antes de reiniciarte» con ventana no vacía; `leer_archivo` con IBAN (ni en disco, ni en el prompt de otro turno;
sí en la recuperación a petición en proceso); valor malicioso de HA → `desconocido`; registro falsificado/ inválido →
ausente + `resultado.rechazado`; registro cortado; detenida/error/duplicada; dos usuarios; olvido de acciones; PARADA no
persiste; fallo de escritura → acción exitosa + constancia + aviso; dominios de seguridad no persisten; prompt sin
registros; CM2 y modelo del usuario no los ven; exclusión permanente de recall.

Fronteras a reescribir (aprobación requerida): `test_frontera_continuidad.py:74` (la ventana no tiene respaldo en
disco) y `:95` (el resultado no entra en la memoria persistente) → «solo registros `resultado_accion` de esquema
cerrado»; `test_el_CONTENIDO_de_un_fichero_se_repite_al_recuperar` (rama del prompt).

Mutantes (`mutaciones/continuidad-resultados.toml`): escribir `say`/payload; sin validación de valores; sin validación
al leer; registro falso presentado como hecho; `entidad` no nula en ficheros; sin deduplicación; ausencia con «nunca»;
recuperable por recall; persistir con PARADA; guarda de PARADA con `if` propio; leer del audit; re-ejecutar al
recuperar; cascada invertida; contenido de fichero en el prompt; doble redacción; **cableado en `composicion.py`**.
FC-M1..M9, M8, G7, P2 deben seguir muriendo.

### 7.6 Dependencias, deuda y reversibilidad

- **Tensión ADR-0023:** el metadato de la ejecución queda en dos historiales (audit forense del sistema; registro
  soberano del usuario), con olvido asimétrico. Declarado; no se resuelve sin borrado físico / D-AMP-3.
- **ADR-0024 / D-A006:** añade una escritura de memoria fuera del Motor Único que **no es conversacional**: amplía el
  residual que el acta dejó «delimitado, no resuelto». Requiere reconocimiento expreso del CEO.
- **Bible 4.1 §1:** el kind se declara **episódico de acción** (evento fechado), no un cuarto tipo; ser no recuperable
  no basta, se documenta en la taxonomía.
- **D-AMP-3** (FORGET vs DELETE) sin firmar: el olvido de acciones es lógico; no decide el borrado físico.
- **Reversibilidad:** el código se revierte; los datos append-only no. La exclusión de `KINDS_NO_RECUPERABLES` debe
  mantenerse siempre (prueba).
- **Autorización de integración:** hace colaborar ejecución y memoria; el checklist dice que la fase de integración no
  está abierta. Requiere **acta** del CEO en `decisiones/` (el encargo del CEO Operativo no está aún como acta).
- Contrato de olvido: nueva fila **T19** (acciones persistidas) con prueba adversarial.

### 7.7 Decisiones que el CEO debe aprobar

1. **D-privacidad:** el prompt no lleva contenido de capacidades `devuelve_contenido_usuario`; la recuperación a petición
   en proceso sí lo repite.
2. **D-reinicio:** persistir solo metadatos con lista blanca de campos y valores, kind `resultado_accion` (episódico de
   acción), alcance usuario, no recuperable y fuera del modelo del usuario.
3. **Sin TTL** (revisable con evidencia); olvido por operación de catálogo y fila T19.
4. **PARADA:** no persistir con PARADA armada, guarda con `es_escritura_pasiva`.
5. **Privacidad:** `ts` al minuto, dominios de seguridad excluidos; HMAC no incluido (límite declarado).
6. **Ver/exportar:** ¿incluir los registros de acciones en `ver`/`exportar` (ADR-0017 §4 completo) o dejarlos fuera?
7. **Fronteras:** sustituir `:74`, `:95` y la rama del prompt de la prueba de contenido.
8. **Acta de integración** y reconocimiento de la ampliación del residual de ADR-0024.

### 7.8 Límites declarados de la implementación (2026-11-06, tras las auditorías independientes)

- **Revisión compuesta (`_despachar_revision`) no persiste:** el enganche aprobado está en `_despachar_orden`. Tras un
  reinicio no constan esas ejecuciones; la recuperación lo cubre con «puede estar incompleto» y la ausencia sin «nunca».
  Persistirla exigiría un identificador por capacidad (hoy comparten `trace_id`). Observación; pasa a deuda si el uso
  real muestra revisiones compuestas que el usuario pregunta tras reiniciar.
- **Sin firma criptográfica:** la barrera frente a un registro anexado a mano es de formato (lista blanca al leer,
  catálogo, ts no futuro, duplicados conflictivos descartados), no de autenticidad. Lo persistido se presenta como
  «registro local sin verificar ahora» con estatus de abstención, nunca como verificación física.
- **Permisos:** `memoria.json`, su `.tmp` y los backups a 0600; los directorios no se modifican (límite declarado).
- **Olvido lógico, no borrado físico** (contrato §5, D-AMP-3): el usuario deja de verlo y AURA de usarlo; la línea y la
  lápida siguen en `memoria.json` y en los backups; el audit conserva el metadato de la ejecución.
- **Crecimiento sin TTL:** ~170 B por acción; medido `[EJEC]` (auditoría de seguridad): con 10⁵ registros la carga de
  `PersistentMemory` tarda ~5,8 s y cada lectura ~1,1 s. Observación; pasa a deuda cuando el historial real supere
  10⁴ registros o la carga medida supere 1 s.
- **Ruta del fichero (preexistente):** la orden dictada («lee el archivo /…») se guarda como turno `historico` y reentra
  en el prompt como texto del usuario; el punto D no la introduce ni la elimina.
- **Cohesión:** `orchestrator.py` crece a ~3800 líneas (techo blando 800); la lógica del registro vive en
  `resultado_accion.py`, pero `_persistir_resultado`/`_texto_de_registro` siguen en el orquestador. Deuda de cohesión.
- **PARADA armada durante la ejecución:** el estado se lee una vez antes del motor; si se arma mientras el motor trabaja,
  el registro de esa orden ya evaluada se escribe (coherente con la orden).
