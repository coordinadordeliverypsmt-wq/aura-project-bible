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
