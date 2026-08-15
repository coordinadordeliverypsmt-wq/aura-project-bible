# CHECKPOINT DE CONTINUIDAD — AURA

**Protocolo PCC (CEO, 2026-08-03).** Este fichero se lee **antes que nada** al reanudar. No rehacer
análisis ya cerrado. No recorrer el repositorio salvo que aquí se indique. No reabrir decisiones
aprobadas.

**Fecha:** 2026-08-03 · **Motivo de la parada:** límite de contexto de la sesión.

**El Protocolo de Continuidad es PERMANENTE** (CEO, 2026-08-03) y vive en `CLAUDE.md` §0: parada automática por debajo del ~2 % de contexto, sin esperar a que el CEO lo pida.

---


## CIERRE — 017 + BUZON VISIBLE (2026-08-10)

**Rama:** `2ae2416` · limpio · **`main` = `origin/main` = `02f1404`** (Pieza 2 integrada).
`main` es ancestro de HEAD: **merge sin conflictos**. La rama trae DOS commits:
`b48fbbd` (017) y `2ae2416` (buzon visible).

### Evidencia
- Quality Gate PASS: **845 pruebas, 3 skipped**. **28 mutantes, 0 supervivientes, 0 no aplicados.**
- 017: el bucle medido tras Pieza 2 queda cerrado -reabiertas 1,1,0,0,0,0- con el historial intacto
  y escalada al CEO. Umbral `_LIMITE_DE_REINTENTOS = 3`, con su motivo escrito y fijado por prueba.
- Buzon visible: `--gobierno` real muestra
  `Decisiones pendientes [AURORA] 1 esperando tu decision: 659bb014b5d1 · proponer_cambio · efecto: ...`
  y `Escaladas al CEO`. E2E: solicitud -> panel -> el CEO aprueba por su huella -> se ejecuta -> deja
  de reclamar atencion.

### Deudas declaradas, NO corregir
- `DEUDA-PANEL-BLOQUEO-SIN-MOTIVO.md`: el panel revienta ante una tarea bloqueada sin motivo. No
  alcanzable hoy -el director siempre pasa el motivo-. Fuera de alcance por decision del CEO.
- `DEUDA-ADR0014-MEMORIA-VACIA.md` y `CLAUDE.md` §2 (nada en paralelo con `herramientas.mutar`).

### SIGUIENTE ACCION EXACTA: integrar (lo ejecuta el CEO; el sandbox aisla al agente)

    MAIN=/home/majo1230/Documentos/AURA/aura-project-bible
    git -C "$MAIN" merge --no-ff worktree-m3-entry -m "merge: 017 + buzon visible en el Centro de Gobierno"
    cd "$MAIN/walking-skeleton" && AURA_DATOS=/tmp/aura-gate ./quality-gate.sh
    git -C "$MAIN" push
    # y desde el worktree:  git merge --ff-only main

`AURA_DATOS` NO es opcional: sin el, el gate puede escribir en el `~/.aura` real.

### DESPUES: solo ANALISIS, sin implementar (orden del CEO)
**Decision Package sobre la frontera real de autonomia**, con evidencia, distinguiendo: que resuelve
software · que exige un modelo/LLM · que exige hardware · coste y riesgo de cada alternativa · y
cuanto aumenta la autonomia cada una. **NO abrir 015/016 ni ningun cambio hasta aprobar ese DP.**

Contexto medido que el analisis debe partir: `admitir()` acepta `ceo`, `asistencia_externa` y
`derivado`, y **AURORA solo puede crear trabajo `derivado`**, con cadena de longitud 1 por corte
deliberado. Puede reaccionar a lo que encuentra; no puede iniciar nada nuevo. Ese es el cuello.

---


## PIEZA 2 — APROBACION DIFERIDA · LISTA PARA INTEGRAR (2026-08-10)

**Commit:** `975e465` · worktree limpio · **`main` = `origin/main` = `62387a6`**
`main` es ancestro de HEAD: **el merge no puede tener conflictos**. Trae 1 commit, 9 ficheros.

### METRICA DE AUTONOMIA — antes / despues

| | ANTES | DESPUES |
|---|---|---|
| Ejecutores utilizables sin el CEO delante | **3 de 4** (solo los verdes: verificar, auditar, diagnosticar) | **4 de 4** |
| `proponer_cambio` (el UNICO que produce trabajo nuevo) | `input()` -> EOFError -> autodenegada, **peticion perdida** | solicitud persistida; el trabajo se reanuda al aprobar |
| Trabajo de lista roja completable en ausencia del CEO | **ninguno** | el aprobado, en el latido siguiente |

**Lo que NO cambio:** la autorizacion no se presume ni se sustituye. Sin aprobacion la accion no se
ejecuta, igual que antes. Lo que sobrevive a la ausencia del CEO es la SOLICITUD, no el permiso.

### EVIDENCIA E2E — DOS PROCESOS DISTINTOS, ejecutor real del programador

```
PROCESO 1 (AURORA sin el CEO)   t-cambio (roja)  : bloqueada
                                t-audit  (verde) : terminada   <- siguio trabajando
                                BUZON: proponer_cambio | efecto=sustituir 1 aparicion en
                                       demo_obra.txt y verificar | huella=ef5ae4b7... | pendiente
EL CEO APRUEBA editando el JSON a mano, sin herramientas de AURA
PROCESO 2 (nuevo)               t-cambio         : terminada
                                fichero: 'contenido viejo aqui' -> 'contenido nuevo aqui'
```

### VERIFICACION
- **16 mutantes / 0 supervivientes / 0 no aplicados** (`mutaciones/decisiones-diferidas.toml`).
  Cuatro sobrevivian en la primera pasada. `motor-ciclo.toml` 5/5.
- **Quality Gate PASS: 828 pruebas, 3 skipped**, ejecutado sobre `975e465`.
- Controles negativos verdes: sin aprobacion no ejecuta · rechazo persiste · **aprobacion obsoleta
  caduca** · fichero manipulado no autoriza · fichero corrupto no autoriza · verdes intactas · kill
  switch por delante. Sin timeout, sin «fail open», sin aprobacion automatica.

### DEFECTO REAL QUE DESTAPO LA DEMOSTRACION (no las pruebas de unidad)
El motor identifica la unidad de trabajo con el `event_id` `"<trace>:<tarea_id>"`, y
`reabrir_aprobadas` comparaba contra el `tarea_id` pelado. **No coincidian nunca.** Las pruebas
pasaban el identificador ya limpio, asi que la reapertura parecia funcionar mientras en el sistema
real **la aprobacion del CEO no producia ningun efecto**. Corregido con `_solo_tarea()` y cubierto
por `test_reabrir_entiende_el_identificador_que_emite_el_motor`. Sin correr la cadena completa en dos
procesos, esto se habria integrado roto.

Segundo defecto, de la mutacion: una prueba mia inspeccionaba el CODIGO FUENTE buscando la cadena
`_tarea`, asi que el mutante que la vaciaba pasaba. Era decorativa; ahora comprueba el valor real.

### SIGUIENTE INCREMENTO RECOMENDADO (metrica de gobierno)
**Capacidad 017 — usar su historial para decidir.** `Tarea.intentos` se incrementa y **nadie lo lee
para cambiar una decision** (`NO_MEDIBLE` en el IMA). Hoy AURORA reintenta una tarea que ya fallo
igual que la primera vez: con la Pieza 2 puede pedir permiso y seguir, pero **no aprende de lo que ya
le paso**. Es software puro, sin dependencia de hardware.

Por detras: **010-012** (los tres pasos deterministas del Traductor Operativo, que reducen lo que el
CEO tiene que traducir a mano) y **B** (modo usuario/diagnostico: NO aumenta autonomia, cerrarlo en
cualquier hueco). **014-016 congeladas por hardware** -- no gastar ciclos ahi.

---


## METRICA QUE GOBIERNA LOS SIGUIENTES INCREMENTOS (CEO, 2026-08-09)

> **¿Que trabajo nuevo puede completar AURORA POR SI MISMA despues de este incremento que antes no
> podia completar?**
>
> Si la respuesta no aumenta autonomia real, el incremento queda POR DETRAS de uno que si la
> aumente. El objetivo dejo de ser un repositorio cada vez mas perfecto.

**A queda APROBADO funcionalmente** por el CEO con los cuatro defectos criticos corregidos. **No se
abren mas auditorias sobre A ni microvalidaciones.** El merge y el push los ejecuta el CEO desde el
checkout principal, con el procedimiento indicado abajo y **sin bypass del Quality Gate**.

Centro de gravedad de la proxima sesion: **A integrado y cerrado → B minimo y cerrado → Pieza 2**.
Despues de B se deja de invertir en endurecer garantias ya suficientemente protegidas.

---

## ESTADO (2026-08-09, fin de sesion) — A LISTO PARA INTEGRAR

**Worktree:** `b8d914b` limpio · **`main` = `origin/main` = `131896c`** (Conversacion General v1 YA
integrado y publicado).

### Hecho y cerrado
- **Conversacion General v1**: integrado en `131896c`, publicado, hook pre-push PASS.
- **Incremento A (HECHO_DECLARADO)**: implementado, auditado, RECHAZADO, corregido y verificado.
  Bible 4.4 §1 ampliada. Quality Gate PASS 804 pruebas · 10 mutantes 0 supervivientes.
  Verificacion corta sobre el producto: los 4 defectos criticos/altos de la auditoria, cerrados.

### SIGUIENTE ACCION EXACTA: integrar A
El sandbox impide al agente operar sobre el checkout compartido. Lo ejecuta el CEO:

    MAIN=/home/majo1230/Documentos/AURA/aura-project-bible
    git -C "$MAIN" merge --no-ff worktree-m3-entry -m "merge: incremento A - hechos declarados"
    cd "$MAIN/walking-skeleton" && AURA_DATOS=/tmp/aura-gate ./quality-gate.sh
    git -C "$MAIN" push
    # y desde el worktree:  git merge --ff-only main

`AURA_DATOS` NO es opcional: sin el, el gate puede escribir en el `~/.aura` real (ya se contamino
una vez).

### Despues, por orden fijado por el CEO (2026-08-09)
1. **B — Experiencia Conversacional v1**: PEQUENO. Solo separar modo usuario de modo diagnostico.
   DP ya escrito: `milestones/m3-entry/DP-B-EXPERIENCIA-CONVERSACIONAL-V1.md`. Medido: NO hay
   logging que migrar, `observability.py` NO se toca. Falta un flag `--debug` y ocultar el bloque de
   arranque. Dos mutantes obligatorios: ADR-0003 y el registro forense integros en modo usuario.
2. **Pieza 2 — buzon de decisiones / canal HITL permanente.** ES EL BLOQUEO DE AUTONOMIA:
   verificado en `hitl_consola.py:33-38`, desatendida AURORA recibe EOFError y SE AUTODENIEGA toda
   accion de lista roja. No puede pedir permiso. DP existente:
   `milestones/m3-entry/DP-CANAL-PERMANENTE-CEO-AURORA.md` (Pieza 2, la unica sin entregar).
3. Capacidad **017** (usar su historial para decidir) y **010-012** (Traductor Operativo).

### Criterio operativo VIGENTE del CEO (2026-08-09)
- Ejecuta directamente lo que este dentro del alcance aprobado y no cambie arquitectura, autonomia,
  permisos, datos ni politicas. **Detente solo** si cambia arquitectura o amplia soberania.
- **No abrir mas rondas de auditoria** salvo riesgo real de seguridad, perdida de datos, soberania
  del usuario o veracidad del comportamiento.
- Quality Gate y regresion son GUARDRAILS, no el objetivo. "Las pruebas protegen el producto, no son
  el producto."
- **014-016 congeladas por hardware**: no gastar ciclos en resolver por software un limite medido de
  capacidad del LLM (25,8 s por "Hola").
- **D-ADP-1** se atiende cuando se toque el adaptador, salvo que afecte una ejecucion real.

### Deudas registradas
`DEUDA-ADR0014-MEMORIA-VACIA.md` (24/24 es CON MEMORIA VACIA; con corpus sembrado 19/24, y este
incremento no lo introduce) · `CLAUDE.md` §2 (nada en paralelo con `herramientas.mutar`).

---


## ESTADO ACTUAL — CONVERSACION GENERAL v1 CERRADA Y AUDITADA (2026-08-09)

**Ultimo commit del worktree:** `4ab4c8a` · **`main`:** `befb303` (NO contiene el incremento).
**Rama:** `worktree-m3-entry`. Worktree limpio. **NO INTEGRADO: falta el acta del CEO.**

### Que hay hecho
Cinco commits, del defecto al cierre:
- `e552746` implementacion (RED -> GREEN -> mutacion -> Quality Gate)
- `8a52dd1` correcciones del rechazo de las 2 primeras auditorias
- `fee4e52` cierre de los 8 mutantes que la 2a auditoria demostro vivos
- `51b19d8` el inventario congelaba menos de lo que su nombre decia
- `4ab4c8a` conteos no derivables fuera + la CLASE del defecto

**Evidencia final `[EJEC]`:** Quality Gate PASS (761 pruebas, 3 skipped) ·
35 mutantes en `conversacion-general-v1.toml`, 0 supervivientes · `conversacion-so.toml` 11/11 ·
`contencion-alerta006.toml` 5/5 · 24/24 negativas de ADR-0014 por el nucleo, 0 llamadas al LLM ·
equivalencia 5/172 y NINGUNA frase pasa del nucleo al LLM.

**Cuatro auditorias independientes.** Rechazaron dos veces; ambos rechazos eran correctos y estan
corregidos. Veredicto final: APRUEBAN. El bloqueante mas grave lo encontro la auditoria, no la
implementacion: el saludo con nombre FABRICABA ("No me llamo Pedro, me llamo Mauricio" -> "Buenos
dias, Pedro") y ademas era INALCANZABLE por via de usuario, porque decir "me llamo X" no alimenta el
Modelo de Usuario (medido: 0 entradas). Se retiro entero.

### DECISION PENDIENTE DEL CEO — no continuar sin ella
1. **Integrar a `main`** o no. Todo lo tecnico esta cerrado y auditado.
2. **El volcado de 17 identificadores en snake_case** ante "¿que puedes hacer?" incumple el Ajuste 2
   del contrato. La plantilla es PREEXISTENTE (verificado contra 06f53f3) y redactarla exige decidir
   como se nombra cada capacidad: es contenido de producto. Propuesto como primer punto de
   *Experiencia Conversacional v1*.
3. **Punto de insercion**: el detector se evalua antes de 4 de las 12 superficies, no de todas como
   decia el DP §1. Es NECESARIO para componer saludo+capacidades, que el ajuste posterior del CEO
   exige. Requiere acta.
4. **DP nuevo propuesto**: "AURORA aprende como te llamas". Sin esa capacidad, el saludo por el
   nombre no puede existir sin fabricar.

### Limites declarados (NO son deuda, son limites del metodo)
- **Crecimiento DECLARADO**: anadir una variante y declararla en el inventario pasa el gate, y esa
  frase deja de llegar a ADR-0014. No es cerrable por prueba: ninguna puede decidir que "que me
  gusta" no es semanticamente una consulta de pendientes. Lo que SI esta protegido: coincidir con
  una de las 24 negativas rompe dos pruebas distintas.
- **El saludo se pierde** cuando la principal NO esta en la lista ("hola, lista el directorio").
  Anteponerlo exigiria propagar el prefijo por toda la cascada: el refactor que el CEO prohibio.
- **`_es_consulta_de_capacidades` casa por SUBCADENA**: "que puedes hacer y cual es la capital de
  Francia" pierde la pregunta. PREEXISTENTE y ajeno, medido identico en `06f53f3`.
- **`_CLASES_DECLARADAS`** no tiene mordida propia demostrada: en la prueba del auditor, 9 de 10
  fallos eran pruebas preexistentes. Se mantiene por explicito y barato.

### Siguiente paso exacto
Esperar el acta del CEO sobre los 4 puntos de arriba. Si aprueba la integracion, seguir `CLAUDE.md`
§3 (merge --no-ff a `main`, Quality Gate en `main`, push, realinear el worktree).

---










## PRIORITARIO · DEFECTO REPRODUCIDO POR EL CEO EN USO REAL (2026-08-05)

**Primera evidencia de producto generada por uso real, no por diseno.** El CEO escribio
*"buenos dias Aurora, que tienes pendiente para hoy?"* y recibio
*"No tengo ningun recuerdo registrado sobre eso."* Declarado **prioritario sobre cualquier capacidad
nueva**.

### CAUSA EXACTA — UNA LINEA
`orchestrator.py`, `_es_consulta_de_memoria`:

```python
return any(p in t for p in _PATRONES_CONSULTA_MEMORIA) or _es_pregunta(texto)
```

**`or _es_pregunta(texto)`: CUALQUIER frase interrogativa se clasifica como consulta de memoria.**
Sin mas criterio. Log del CEO: `recall 'buenos dias...' -> 0 hit(s)` -> `grounding: memoria vacia ->
respuesta determinista` -> respuesta de ausencia.

### POR QUE NO SE PUEDE ARREGLAR SIN DECISION PACKAGE
Ese `or` **es DELIBERADO** — el docstring lo dice: *"sin ella la garantia de no-fabricacion cubria una
fraccion minima del espacio real de preguntas"*. Se amplio para reforzar **ADR-0014**: impedir que el
LLM invente recuerdos ante preguntas sin marcador explicito.

**La garantia y el defecto viven en la MISMA linea.** Quitar el `or` sin sustituirlo reabre el hueco
que ADR-0014 cerro. Toca una garantia dura => **Decision Package antes de implementar**.

**Direccion propuesta (a discutir, NO implementada):** que la ausencia de memoria deje de ser el cajon
por defecto y exija que la pregunta trate del **pasado compartido**, no del presente de AURORA.
*"que me dijiste ayer"* SI; *"que puedes hacer"* NO. Obligatorio: al terminar, el mutante **"el LLM
responde cuando no hay recuerdos" debe SEGUIR MURIENDO**. Si sobrevive, se rompio ADR-0014 arreglando
la experiencia.

### DATO QUE CAMBIA LA PRIORIDAD DEL WORKTREE
**El incremento conversacional pendiente NO arregla esto.** Anade superficies DELANTE en la cascada, y
*"buenos dias Aurora, que tienes pendiente para hoy?"* no coincide con sus patrones: nunca llega a
ellas y cae igual en la ausencia de memoria. Integrarlo es necesario pero **NO suficiente** para lo que
el CEO acaba de reportar.

**Es el MISMO defecto que la auditoria rechazo el 2026-08-04** -detectores demasiado anchos, sin guarda
de dominio- pero en la superficie mas antigua y protegida del sistema.

---

## >>> PUNTO DE REANUDACION EXACTO (CEO, 2026-08-05) <<<

**NO INICIAR NADA NUEVO MIENTRAS LA CUOTA SIGA AGOTADA.** Orden literal del CEO al volver:

1. **Verificar las correcciones escritas** (commit `WIP` del worktree, ver abajo). `./quality-gate.sh`
   + `python3 -m herramientas.mutar mutaciones/conversacion-so.toml` + **rehacer los 5 mutantes
   A7-A11 del auditor** (vivian en `/tmp`, ya no existen; reconstruirlos desde el informe de arriba).
2. **Rehacer la auditoria independiente** — agente que NO implemento.
3. **Integrar el incremento conversacional en `main`.**
4. **Validar en el binario oficial** que responde a: que puedes hacer · en que estas trabajando ·
   que aprendiste · por que estas bloqueada · que sabes de mi.
5. **Solo cuando esa version sea la que el CEO use a diario**, empezar la etapa siguiente.

### Etapa siguiente (definida, NO empezada)
Usar AURORA como interfaz principal para que **genere evidencia de producto y detecte por si misma
necesidades reales**. Su evolucion se basa en esa evidencia, y **siempre propone los cambios para
aprobacion antes de implementarlos**.

### ESTADO VERIFICADO DEL PRODUCTO HOY (medido 2026-08-05, no leido)
`main` = `befb303`. Ejecutado contra el binario oficial con `AURA_DATOS` aislado:

```
tu> ¿Que puedes hacer?          AURA> No tengo ningun recuerdo registrado sobre eso.
tu> ¿En que estas trabajando?   AURA> No tengo ningun recuerdo registrado sobre eso.
tu> ¿Por que estas bloqueada?   AURA> No tengo ningun recuerdo registrado sobre eso.
tu> ¿Que aprendiste?            AURA> No tengo ningun recuerdo registrado sobre eso.
tu> ¿Que sabes de mi?           AURA> Todavia no se nada sobre ti.
```

`_es_consulta_de_capacidades` **no existe en main** (0 coincidencias). Lo que el CEO ejecuta hoy es la
version anterior. **Lo unico integrado y util de este trabajo son `--gobierno` y `--servir`.**
Tambien sigue apareciendo el bloque `AURA - arranque verificado`, que el criterio 3 del sprint pide
ocultar.

### PENDIENTE NO TECNICO
El **Modelo de Usuario real contiene un dato FABRICADO** ("prefiero trabajar de noche"). Limpiarlo por
la via del producto ANTES de que el CEO empiece a usar AURORA a diario: si no, lo primero que le dira
sobre si mismo sera falso.

---

## ESTADO 2026-08-05 · CORRECCIONES ESCRITAS PERO **SIN VERIFICAR** — LEER ANTES DE TOCAR NADA

**El incremento conversacional fue RECHAZADO por auditoria independiente. Las correcciones estan
APLICADAS EN EL ARBOL DE TRABAJO pero NADIE HA VERIFICADO QUE FUNCIONEN.** El agente que las escribio
murio por **limite de gasto mensual de la cuenta** justo antes de ejecutar la demo y las pruebas.

**NO INTEGRAR. NO ASUMIR QUE ESTAN BIEN.** Este es exactamente el estado en el que nace
«declarado != real»: codigo escrito que parece terminado y que nadie ejecuto.

Modificado sin verificar: `aura_skeleton/core/orchestrator.py`,
`mutaciones/conversacion-so.toml`, `tests/integration/test_conversacion_ventana_so.py`.
Indicios de que la correccion se intento: 11 menciones de `dominio` y 2 de `UnicodeDecodeError`
en el orquestador. **Indicio no es evidencia.**

### LOS 3 DEFECTOS QUE HAY QUE COMPROBAR CERRADOS (informe completo del auditor arriba)

1. **5 mutantes sobrevivian a las 684 pruebas** (A7-A11): capacidades FABRICADAS a mano en vez de las
   17 reales, y Plan de Formacion INVENTADO, pasaban la suite entera. Aserciones decorativas que
   cualquier constante satisface (`test_conversacion_ventana_so.py:67-68`, `:189-190`, `:159`, `:177`).
   Las ramas de ausencia `orchestrator.py:439` y `:442` no tenian NINGUNA prueba. ALERTA-005 nº 10.
2. **6 regresiones de conducta**: detectores sin guarda de dominio. *"que esta pasando con mi pedido de
   Amazon"* respondia **"no hay nada bloqueado"**, y *"que has aprendido de mi"* volcaba el Plan de
   Formacion con notas internas. Antes callaba honestamente; ahora contestaba MAL. El proyecto ya
   arreglo esto dos veces: `orchestrator.py:210-222` y `:148-171` exigen marcador **Y** dominio.
3. `UnicodeDecodeError` no capturado en `:437-440` (es `ValueError`, no `OSError`): el turno reventaba.

### PRIMER PASO EXACTO AL RETOMAR (en este orden)

1. `./quality-gate.sh` — si falla, las correcciones estan a medias.
2. `python3 -m herramientas.mutar mutaciones/conversacion-so.toml` — deben morir TODOS.
3. **Reconstruir los mutantes A7-A11 del auditor y comprobar que ahora MUEREN.** Vivian en
   `/tmp/aura_audit/auditoria-conversacion-so.toml`, que **ya no existe**: hay que rehacerlos desde la
   descripcion de arriba. Sin este paso no se sabe si el defecto 1 esta cerrado.
4. Pruebas negativas con las 6 frases del defecto 2.
5. Demo real con `env AURA_DATOS=/tmp/... python3 -m aura_skeleton` (NUNCA `VAR=val cmd | cmd2`).
6. **Re-auditoria independiente.** Sigue sin poder integrarse sin ella.

### BLOQUEO OPERATIVO REAL

**Cuota mensual de la cuenta AGOTADA.** Han muerto por esta causa: la auditoria de la Pieza 1, la
re-auditoria de la Pieza 3 y ahora la correccion del incremento conversacional. **No es un problema
tecnico del proyecto y no se resuelve trabajando mas**: hasta que haya cuota, no hay auditoria
independiente, y sin auditoria independiente no se integra nada. El trabajo pendiente esta
completamente especificado; lo que falta es capacidad de ejecucion.

---

## PRINCIPIO RECTOR DE "EXPERIENCIA CONVERSACIONAL v1" (CEO, 2026-08-04)

> **El usuario nunca debe percibir la arquitectura interna de AURORA.**
> Puede consultar el Centro de Gobierno, el Estado Operativo, el Plan de Formacion, el Modelo de
> Usuario, la Memoria o cualquier componente, **pero siempre responde como UNA UNICA PERSONALIDAD**,
> sin mencionar modulos internos salvo peticion expresa del usuario.
> *"La conversacion debe parecer la de un companero inteligente, no la de un orquestador mostrando su
> implementacion."*

### Prueba de aceptacion del CEO
Conversacion de 20-30 min sin que aparezca **ninguna** referencia tecnica: `EVENT`, `VOICE`, `CORE`,
`MEM`, `LAT`, `trace`, `router`, "grounding", "memoria vacia", nombres de modulos — **salvo** con
`--debug` o si el usuario pide informacion tecnica explicitamente.

**Criterio de exito:** ya no basta con que pasen las pruebas. La arquitectura debe DESAPARECER detras
de la conversacion.

### COMO CONVERTIR ESA PRUEBA EN GARANTIA AUTOMATICA (aportacion de APUS-5)

La parte objetiva del criterio **si es verificable por prueba determinista**, y conviene que lo sea:
una revision manual de 20-30 min no se repite en cada push, y lo que no se automatiza se degrada
(CLAUDE.md §5: *"el trabajo manual repetitivo se abandona, no se hace mal"*).

Implementar como **lista negra de terminos** sobre la salida en modo usuario:
1. Prueba que recorra un guion de preguntas variadas y **falle si CUALQUIER respuesta contiene un
   termino de la lista**. Cubre tanto las superficies nuevas como las 8 previas.
2. **Caso de control obligatorio** (si no, la prueba es decorativa): con `--debug` los terminos **SI**
   deben aparecer. Sin ese caso, una prueba que nunca ve telemetria pasaria aunque el modo debug
   estuviera roto.
3. **Mutante:** que un termino tecnico se cuele en una respuesta de modo usuario. Debe morir.

Lo que NO puede automatizarse es si la redaccion suena natural. **Ese juicio es del CEO usando el
producto**, y es la evidencia que abre la siguiente iteracion. La lista negra protege el suelo; la
calidez la juzga el usuario.

---

## SPRINT EN COLA · "EXPERIENCIA CONVERSACIONAL v1" (CEO, 2026-08-04)

Renombrado por el CEO: ya no es "Conversacion como interfaz del SO". *"Se trata de que el usuario
olvide que esta hablando con un programa y empiece a sentir que esta hablando con AURORA."*
**Criterio rector:** usar AURORA ocho horas seguidas debe sentirse como conversar, no como leer un log.
**No se toca ninguna garantia ni la arquitectura: solo la experiencia de uso.**

### C1 · Redaccion natural, verdad del nucleo
El LLM solo redacta cuando exista y convenga; mientras tanto, **plantillas deterministas bien
escritas**. La VERDAD siempre la fija el Core (ADR-0014). Con 25,8 s / 8 tokens, generar por turno no
es viable hoy.

### C2 · Modo usuario por defecto, `--debug` para lo demas
Por defecto solo `tu>` y `AURORA>`. VOICE, EVENT, MEM, CORE, LAT, trace, event_id, router: al modo
desarrollador. **Ocultar != dejar de auditar**: `audit.jsonl` sigue completo (forense, ADR-0023).
Punto unico de cambio: `observability.py:41` imprime TODO por stderr.

### C3 · La consola es un PRODUCTO, no una herramienta de desarrollo
Eliminar de la vista por defecto el bloque "AURA - arranque verificado" (`__main__.py:_informe`).
Sustituir por algo minimo: `AURORA v0.3 / Estado: Operando / tu>`.

**MATIZ QUE NO DEBE PERDERSE:** `_informe` NO se borra. Lo usa el flag `--verificar`, que es la
comprobacion de arranque exigida por **D27 (preflight obligatorio, "se verifica siempre el estado real
del sistema, nunca se asume")**. Se deja de MOSTRAR por defecto; se conserva bajo `--verificar` y
`--debug`. Borrarlo romperia una decision del CEO de 2026-07-17.

### C4 · Las respuestas de ausencia son conversacion, no mensajes de error
Hoy: *"No tengo ningun recuerdo registrado sobre eso."* / *"Todavia no se nada sobre ti."*
Debe decir lo MISMO sonando a persona: *"Aun no conozco suficientes cosas sobre ti. Con el tiempo ire
recordando tus preferencias y la forma en que trabajamos juntos, pero por ahora todavia estoy
aprendiendo."*

**MATIZ CRITICO (ADR-0014):** *"No tengo ningun recuerdo registrado sobre eso"* NO es un texto
cualquiera: es **la garantia determinista** que impide que el LLM invente un recuerdo cuando la
busqueda da cero resultados (ADR-0014:42-44, *"no se le concede la oportunidad de inventar"*).
Se puede cambiar **la REDACCION**. **NO se puede cambiar la CONDICION que la dispara ni permitir que
el LLM intervenga en ese camino.** Hay pruebas que comparan contra el texto literal: al reescribirlo,
actualizarlas SIN debilitar lo que verifican, y comprobar que el mutante "el LLM responde cuando no
hay recuerdos" **sigue muriendo**. Si al terminar ese mutante sobrevive, se rompio ADR-0014.

**Orden:** va DESPUES de la auditoria independiente del encargo conversacional (que sigue bloqueando
su integracion). Protocolo completo: RED -> GREEN -> MUTACION -> Quality Gate -> auditoria independiente.

---

## ENCARGO EN COLA 2026-08-04 (4) · EXPERIENCIA DE USO (CEO)

**Cambio de etapa declarado por el CEO:** *"Antes discutian mutantes, garantias, auditorias,
ejecutores. Ahora empieza la pregunta: como se siente usar AURORA todos los dias? Y esa pregunta ya
no la responde una prueba unitaria. La responde el usuario."*

**NO EMPEZADO.** Va DESPUES de la auditoria independiente del encargo conversacional, que sigue
pendiente y bloquea su integracion.

### Criterio 1 — la conversacion debe SENTIRSE natural

AURORA no debe responder como un conjunto de modulos. Al consultar Estado Operativo, Centro de
Gobierno, Plan de Formacion o Modelo de Usuario, debe **transformar el dato en lenguaje natural y
explicar el contexto**, no enumerar campos. Hoy responde con volcados (`## Aprendidas` con la tabla
markdown cruda, listas de capacidades con vinetas).

**Tension a resolver con cuidado (ADR-0014):** redactar en lenguaje natural NO puede significar
delegar en el LLM la VERDAD del dato. El nucleo decide QUE se responde y con que datos; la redaccion
no puede alterar hechos, inventar cifras ni suavizar una ausencia. Si se usa el modelo para redactar,
los hechos van fijados por el Core y el resultado debe seguir siendo verificable por prueba
determinista. **Recordar: con el hardware actual el LLM tarda 25,8 s en 8 tokens** — una redaccion
por LLM en cada turno haria la consola inusable. La via realista es plantilla determinista bien
escrita, no generacion.

### Criterio 2 — modo usuario (por defecto) y modo desarrollador

Por defecto la consola muestra SOLO `tu>` y `AURORA>`. Toda la telemetria (VOICE, EVENT, MEM, CORE,
LAT, traces, event_id, auditoria) **se oculta**, y sigue disponible con `--debug`/`--verbose`.
Hoy TODO log sale por stderr desde `observability.py:41`, mezclado con la conversacion.
**La auditoria NO se apaga: se deja de IMPRIMIR.** Sigue escribiendose en `audit.jsonl` (es forense,
ADR-0023). Ocultar != dejar de registrar; confundirlos romperia una garantia.

Direccion futura que el CEO dibujo (NO implementar aun, es vision): cabecera con estado y objetivo
activo, y solicitudes de decision en linea (`Tengo una decision pendiente... (S/N)`) — eso ultimo
converge con la **Pieza 2** del canal permanente, que sigue sin abrirse.

**Protocolo habitual exigido:** RED -> GREEN -> MUTACION -> Quality Gate -> **auditoria independiente**.

---

## AVISO 2026-08-04 (3) · DATO FALSO EN EL MODELO DE USUARIO REAL — LIMPIAR

Durante la demo del encargo conversacional, un error de scoping de bash
(`VAR=val cmd1 | cmd2` solo aplica VAR a cmd1) hizo que `AURA_DATOS` NO llegara al proceso: **la
primera demo corrio contra el `~/.aura` REAL**, no contra el directorio aislado.

**Consecuencia:** hay una entrada FABRICADA en `~/.aura/memoria.json` — *"usuario dijo: mi preferencia
es trabajar de noche"*, user_id `usuario`. **El CEO nunca dijo eso.** Es un dato de prueba en la fuente
que acabamos de conectar a la conversacion: si no se borra, AURORA le respondera al CEO que sabe que
prefiere trabajar de noche, y sera FALSO. Contamina justo la fuente cuya credibilidad importa.

**Como limpiarlo (NO editar el fichero a mano):** usar la propia capacidad del producto,
`ModeloUsuario.borrar` / la secuencia conversacional de refutar-olvidar. Editar el JSON a mano seria
manipular evidencia y ademas saltarse el Motor Unico.

El `audit.jsonl` tambien recibio lineas de boot de esa corrida. **NO se tocan**: es append-only por
diseno y reescribirlo seria peor que dejarlo. Queda declarado aqui, que es la forma correcta de
corregir un log inmutable.

### ESTADO DEL ENCARGO CONVERSACIONAL (agente terminado, **SIN AUDITORIA**)

Quality Gate PASS (684 pruebas), mutacion `conversacion-so.toml` 5/5 detectados. 4 superficies nuevas
insertadas DESPUES de las 8 previas y ANTES de la ausencia de memoria, con prueba de no interferencia
que reejecuta las secuencias de modelo de usuario y notificaciones. Efecto colateral detectado y
corregido: el cableado rompio el mutante M9 de `cap5-automatizacion.toml` (patron obsoleto), lo
destapo `test_garantias_vigentes.py` — el Auditor funcionando como se diseno.

**NO INTEGRADO A MAIN Y NO CERRADO: falta la auditoria independiente.** Protocolo B1 completo =
RED, GREEN, mutacion, Quality Gate **y auditoria**. Primer paso al retomar: auditar este incremento
con un agente que no lo implemento, prestando atencion a si algun patron nuevo roba frases a las 8
superficies previas en casos que la prueba de no interferencia no cubra.

---

## ESTADO 2026-08-04 (2) · ETAPA DE OPERACION Y APRENDIZAJE — TRABAJO EN PARALELO

**Mandato vigente del CEO:** AURORA aprende del uso · APUS-5 fortalece la PLATAFORMA · el CEO decide
direccion. **Ninguna capacidad de PRODUCTO sin evidencia del uso real** — si la evidencia la justifica,
se genera Decision Package, no se implementa. Mejoras de plataforma: implementables con protocolo normal.

### CERRADO — arnes de mutacion con timeout (commit `6eaa383`, EN EL WORKTREE, **sin integrar a main**)

`herramientas/mutar.py` imponia cero limite de tiempo: un mutante que degrada una condicion de parada
colgaba el arnes entero y dejaba huerfanos (dano medido: 15+ h de CPU). Ahora:
- `subprocess.Popen(start_new_session=True)` + `communicate(timeout)`; al vencer, **SIGKILL al GRUPO
  completo** (`os.killpg`, PID negativo), no solo al hijo.
- Estado nuevo **`TIMEOUT`**, distinto de `SOBREVIVE` a proposito: senala falta de garantia de
  TERMINACION, no de cobertura. **Ninguno cuenta jamas como exito**: `concluyente` exige `timeouts == 0`.
- `timeout_s` declarable en el TOML (global al fichero, 60 s por defecto).
- **M2 y M3 de `motor-ciclo.toml` REINCORPORADOS** con valvula independiente (`DirectorInestable.tras_agotar`)
  y override `pruebas` por-mutante. Ya no cuelgan: **5/5 detectados en 6-8 s**. La deuda queda CERRADA.
- `mutaciones/arnes-timeout.toml` (nuevo): el arnes se protege a si mismo, 4/4 detectados.

**HALLAZGO COLATERAL GRAVE, no buscado:** carrera del cache de bytecode. `__pycache__` invalida por
mtime en SEGUNDOS + tamano, asi que si la mutacion y la reejecucion caian en el mismo segundo y el
mutante no cambiaba el tamano del fichero, **pytest reutilizaba el .pyc SIN MUTAR**. Medido:
**2/15 iteraciones daban estado ERRONEO**; 0/30 tras el fix (`PYTHONDONTWRITEBYTECODE=1`).
Es decir: el arnes podia declarar "detectado" un mutante que nunca llego a ejecutarse. Corregido.

Evidencia: 673 pruebas (antes 670), Quality Gate PASS, sin huerfanos.

### EN CURSO — la conversacion como ventana del SO (encargo del CEO, agente trabajando)

Objetivo: que preguntas naturales consulten las FUENTES OFICIALES antes que al LLM. Hoy el chat
responde *"No tengo ningun recuerdo registrado sobre eso"* aunque el dato exista en el SO.
Mapa pedido: capacidades->composicion · tareas->Estado Operativo · bloqueos y "que esta pasando"->
Centro de Gobierno · aprendizajes->Plan de Formacion · "que sabes de mi"->Modelo de Usuario.
**Si la respuesta existe en el SO, NO se llama al LLM.** Sin componentes nuevos.

**TRAMPA ADVERTIDA AL IMPLEMENTADOR (leer antes de continuar):** ya existen **8 grupos de superficies
deterministas con 47 patrones literales**, en cascada con precedencia por orden de escritura, y **4
defectos de interferencia YA verificados** (`CHECKLIST-CONTINUIDAD.md:192-204`). Un patron nuevo como
"que esta pasando" puede ROBAR la frase a la superficie de notificaciones y romper lo que hoy funciona,
sin que ninguna prueba actual lo detecte. Se exigio: enumerar los 8 grupos, justificar el punto de
entrada en la cascada, y una **prueba de NO INTERFERENCIA**.
Limite de honestidad recordado: el Modelo de Usuario tiene **0 entradas y 0 senales**; a "que sabes de
mi" la respuesta correcta es DECLARAR la ausencia (INV-9), nunca fabricar contenido.
Criterio de aceptacion del CEO: **transcripcion literal de una conversacion real** con las 8 preguntas.

Ficheros que estaba tocando: `aura_skeleton/core/orchestrator.py`, `aura_skeleton/composicion.py`,
`tests/integration/test_conversacion_ventana_so.py`, `mutaciones/conversacion-so.toml`.

### POR QUE `6eaa383` NO SE INTEGRO A MAIN

El worktree tiene trabajo concurrente **a medias** del encargo conversacional. Integrar ahora
arrastraria codigo sin terminar. **Primer paso de la proxima sesion:** comprobar si el agente cerro su
trabajo (`git log`, `git status`, Quality Gate); si esta completo y en verde, integrar TODO junto; si
quedo a medias, integrar `6eaa383` de forma aislada o rehacer el encargo conversacional desde este
checkpoint.

### SIGUE PENDIENTE (bloqueado por cuota, no por decision tecnica)

1. Auditorias independientes de las Piezas 1 y 3 del canal permanente.
2. Confirmacion definitiva de la capacidad **018** (hoy: parcial, NO confirmada).
3. **Pieza 2** — buzon de decisiones. Diseno completo en el DP §4. Sin ella, AURORA desatendida
   **sigue autodenegandose toda accion de lista roja**.

---

## ESTADO 2026-08-04 · CANAL PERMANENTE CEO<->AURORA (piezas 3 y 1 entregadas)

**DP aprobado por el CEO con 7 condiciones** — `milestones/m3-entry/DP-CANAL-PERMANENTE-CEO-AURORA.md`.
Orden acordado 3 -> 1 -> 2. **Criterio de exito del CEO (literal):** *"que pueda abrir una terminal,
ejecutar AURORA, cerrar Claude Code por completo y seguir viendo que esta haciendo, que necesita de mi
y que decisiones esperan mi aprobacion"*.

### HECHO Y VERIFICADO [EJEC]

- **Mitigacion N2 (condicion 7, prioritaria).** `model.onnx` (449 MB) y `tokenizer.json` (17 MB) eran
  enlaces simbolicos a `/home/majo1230/.claude/jobs/d69740cc/tmp/mlmodel/`. **Materializados** en
  `~/.aura/models/`. SHA-256 del modelo identico al del manifiesto (`185ae63f...`). Cero symlinks
  bajo `~/.aura`. Quedan 6,8 GB libres. **La memoria ya no depende de ningun job externo.**
- **PIEZA 3 — Centro de Gobierno visible.** `publicar()` en `centro_gobierno.py` (escritura atomica
  via `os.replace`) + flag `--gobierno` en `__main__.py`. Escribe `~/.aura/CENTRO-DE-GOBIERNO.md`.
  **RECHAZADA por auditoria independiente y corregida**: 5 defectos, entre ellos que el panel elegia
  `activos[0]` y ocultaba el resto de objetivos, firmando como [AURORA] un "sin riesgos activos"
  FALSO. Ahora **cubre TODOS los objetivos activos** y prefija cada bloque con `[objetivo_id]`
  cuando hay mas de uno (decision de diseno de APUS-5, no del implementador).
- **PIEZA 1 — AURORA tiene proceso propio.** Flag `--servir` arranca `motor_ciclo.servir()`.
  Corregido el defecto declarado en el DP: `servir()` ya **captura excepciones del latido**, las
  registra en el audit, continua, y se detiene tras `_MAX_FALLOS_CONSECUTIVOS=5` fallos SEGUIDOS;
  un latido con exito reinicia el contador. `correr()` NO se toco (decision justificada: corrida
  acotada vigilada por quien la invoca).
- **Defecto de plataforma corregido por APUS-5:** `herramientas/mutar.py` reventaba con
  `KeyError: 'AMBIGUO'` en `_formatear_informe`, ocultando el informe ENTERO -incluidos
  supervivientes-. Ahora usa `.get` con marca por defecto.

**Evidencia de cierre:** Quality Gate **PASS** (666 pruebas, 3 skipped, 8 contratos).
Mutacion: `centro-gobierno` 12/12 · `gobierno-cli` 5/5 · `servicio-permanente` 4/4 =
**21 mutantes, 0 supervivientes, 0 no aplicados, 0 ambiguos.**
Servicio verificado vivo 75 s (dos ciclos de espera); **kill switch lo detiene fuera de banda**;
sin procesos huerfanos. Panel consultado desde otra terminal con el servicio corriendo.

### INCUMPLIMIENTO DEL ESTANDAR QUE DEBE SABERSE

**Las dos auditorias independientes cayeron por limite de gasto mensual de la cuenta** (la de la
Pieza 3 ya habia emitido su rechazo y sus 5 defectos fueron corregidos; su RE-auditoria y la
auditoria completa de la Pieza 1 **no llegaron a terminar**). La verificacion final la hizo APUS-5,
que **no implemento** ninguna pieza pero **si tomo la decision de diseno D-3**. No equivale a una
auditoria independiente. **Deuda abierta: auditar Pieza 1 y re-auditar Pieza 3 cuando haya cuota.**

### SIGUIENTE PASO EXACTO

**PIEZA 2 — buzon de decisiones (aprobacion diferida).** NO empezada. Condicion 4 del CEO: toda
solicitud persiste en disco, sobrevive a reinicios y **se revalida con un NUEVO dry-run antes de
ejecutarse; la aprobacion nunca autoriza un estado obsoleto**. Diseno acordado en el DP §4:
- confirmador `adapters/hitl_diferido.py` con la MISMA firma que `hitl_consola.py` (previsto en su
  propio docstring, `:7-9`)
- reutiliza **`Tarea.decisiones_pendientes`** (`estado_operativo.py:76`), campo que YA EXISTE y que
  nadie escribe ni lee
- el CEO responde con un fichero en `~/.aura/decisiones/`; AURORA re-ejecuta el dry-run y compara
  antes de reabrir la tarea (`bloqueada -> abierta`, transicion ya permitida)
- la omision SIGUE siendo denegacion (ADR-0003, tolerancia cero a falsos negativos)

**Recordatorio del propio sistema:** el panel ya dice, derivandolo de su historial, que *"desbloquear
'programador' liberaria 1 de 2 tareas detenidas (50%)"*. Eso ES la Pieza 2, y la pidio AURORA.

---

## Identificación

| | |
|---|---|
| Milestone | `m3-entry` |
| Worktree | `.claude/worktrees/m3-entry` |
| Rama | `worktree-m3-entry` |
| Último commit de la rama | `315a7f9` (espec G-1) |
| `main` publicado | `ba73208` + merge de G-1 (ver §Último resultado válido) |

---

## ESTADO AL 2026-08-03 (fin de sesion)

Entregadas DOS capacidades del SO Interno: **EstadoOperativo** (bcc0922) y **DirectorGeneral**
(Incremento 1). Ambas con mutacion 5/5 y 6/6 y Quality Gate PASS.

**Siguiente incremento:** bucle continuo del Director (repetir mientras haya tareas y detenerse solo)
y cableado en `composicion.py` -- hoy ambos componentes existen y funcionan pero NADIE los usa en
produccion. Ese es el cuello de botella real.

**Pendiente:** auditoria independiente de ambos incrementos.

## Objetivo que se estaba ejecutando

Cerrar la cadena **ALERTA-006 → D-M-8 → G-1**, entregando diseño revisable **sin implementar código**,
según el orden fijado por el CEO.

## Completado (no repetir)

- **Contención de ALERTA-006 IMPLEMENTADA y publicada.** 3 medidas: guarda de dominio en el disparador
  de olvido · `_foco` no actúa ante ambigüedad (pide desambiguación) · `refutar` solo confirma con
  mutación efectiva. RED→GREEN→**mutación 5/5**→Quality Gate PASS. Publicada en `ba73208`.
- **DP D-M-1** (recuperador N1, `A′` prefijo+cota) — **aprobado como documento**. Implementación NO
  autorizada; supeditada a D-M-2.
- **DP D-M-2** (auto-eco) — **diagnóstico aprobado**. `Op-5` NO autorizada; supeditada a D-M-7.
- **DP D-M-7** (clasificación de intención) — **diagnóstico y modelo de 2 ejes aprobados**.
  Implementación NO autorizada. Batería de 172 casos en `milestones/m3-entry/bateria-intencion.json`.
- **DP D-M-8** (Motor Único de Mutaciones) — **diagnóstico y modelo aprobados**. Implementación
  condicionada a G-1.
- **ESPEC G-1** (Ruta Única de Mutación) — **APROBADA como documento de diseño** (CEO, 2026-08-03).

## Pendiente exacto

1. **Implementar D-M-8** siguiendo el plan de 7 fases del DP. **Requiere autorización explícita del
   CEO**, que aún no se ha dado.
2. **Corregir ALERTA-006 en lo estructural** mediante el nuevo Motor.
3. **D-M-7** sobre la nueva arquitectura → **D-M-2** con el clasificador definitivo → **D-M-1**.
4. **Revisión independiente de la contención de ALERTA-006** — no se pudo completar (el agente auditor
   terminó por límite de gasto de la cuenta). **La contención NO está cerrada definitivamente.**
5. **Decisión pendiente del CEO:** renombrar las operaciones mutantes a nombres inequívocos. Medido que
   es **condición de viabilidad de G-1** (resolución de receptor 40 % → 100 %). Toca superficie pública
   de los almacenes.

## Próximo primer paso al reanudar

> **1) Construir el ROADMAP, cuya FASE 1 es el ciclo cerrado de 7 pasos (ver seccion de cierre metodologico). Cada fase debe entregar CAPACIDAD REAL, no documentacion.**
> **1b) Inventario total previo antes de proponer nada nuevo.**
> **(referencia) ROADMAP del Sistema Operativo Interno** (ver seccion "ENCARGO EN COLA").
> **2) Dentro de el, pedir las dos autorizaciones pendientes: implementar D-M-8 y renombrar las operaciones mutantes.** Sin esas
> dos autorizaciones no puede avanzarse: el orden aprobado sitúa D-M-8 antes que todo lo demás, y G-1
> no es viable sin nombres inequívocos.

Antes de tocar nada: `bash entorno/scripts/preflight-check.sh` y `./quality-gate.sh` (§1 del Checklist).

## Último resultado válido

| Elemento | Estado |
|---|---|
| Quality Gate | **PASS** (última ejecución en la rama, tras la espec G-1) |
| Mutación | `mutaciones/contencion-alerta006.toml` → **5/5 detectados, 0 supervivientes** |
| Pruebas nuevas | `tests/unit/test_contencion_alerta006.py` (7 casos, 2 son controles) |
| Alerta abierta | **ALERTA-006** — contención hecha; **estructural ABIERTO** |
| DP aprobados como documento | D-M-1 · D-M-8 · ESPEC G-1 |
| DP con diagnóstico aprobado | D-M-2 · D-M-7 |

## Riesgos abiertos / qué falta verificar

- **ALERTA-006 sigue abierta en lo estructural:** la mutación **no pasa por el Motor Único** y **el kill
  switch armado NO la detiene**. La contención solo evitó la destrucción silenciosa.
- **La contención no tiene auditoría independiente.** La revisó quien la implementó, lo que incumple el
  estándar del proyecto.
- **G-1 no demuestra ausencia de rutas alternativas** (limitación del análisis estático, declarada en
  la especificación). Necesita la prueba dinámica complementaria G-2b.
- Deuda previa viva: `D-N2-5`, `D-A-11`, `D-M-1`…`D-M-7`, `ModeloUsuario.corregir` construido y **no
  cableado**, `CentroNotificaciones.cerrar_sesion` sin llamador.

---

## ENCARGO EN COLA — Roadmap del Sistema Operativo Interno de AURORA (CEO, 2026-08-03)

**No iniciado.** Recibido por debajo del umbral de parada del Protocolo de Continuidad; empezarlo
habria sido hacerlo "a la carrera". **Es el primer trabajo de la proxima sesion.**

### Cambio de objetivo principal
El objetivo deja de ser cerrar deuda tecnica: pasa a ser que **AURORA evolucione hacia una arquitectura
capaz de administrarse, verificarse y mejorarse a si misma en local**, sin depender de Claude para el
trabajo operativo. La pregunta rectora ya no es *"como implementamos esto"* sino
**"como hacemos que AURORA pueda implementarlo ella misma"**.

### Los 7 principios de trabajo (obligatorios)
1. Ningun cambio deja vacios arquitectonicos. Si aparece uno: documentarlo y proponer su cierre
   **antes** de continuar.
2. Toda implementacion responde a: *¿esto acerca a AURORA a ser mas autonoma y autosuficiente?*
3. **No hay modulos nuevos** sin integracion clara en el modelo general. Se prefiere una arquitectura
   pequeña, coherente y extensible.
4. El siguiente nivel es el **Sistema Operativo Interno**, con 10 roles bajo un **unico orquestador**:
   Director General · Arquitecto · Programador · QA y Mutacion · Seguridad · Documentacion ·
   Investigacion · Planificador · Memoria · Observabilidad.
5. **Ningun agente decide estrategia por su cuenta.** Arquitectura, Bible, ADR, protocolos y diseño
   pasan por Decision Package aprobado.
6. Transicion **incremental**, reutilizando lo existente. **No se rehace AURORA**: se convierten
   gradualmente los componentes actuales en un sistema capaz de mejorarse a si mismo.
7. **Reutilizar tiene prioridad sobre crear.** Antes de codigo nuevo: identificar que componentes
   actuales pueden convertirse en capacidades permanentes.

### Entregable pedido — roadmap tecnico, no funciones aisladas
Debe mostrar: **estado actual · estado objetivo · fases de transicion · dependencias · riesgos ·
que puede ejecutar AURORA por si misma en cada fase**.

### Punto de partida ya disponible (NO re-investigar)
- **Rol Orquestador:** existe `MotorAutomatizacion` como camino unico de ejecucion + `D-M-8` (Motor
  Unico de Mutaciones, modelo aprobado) + `ESPEC G-1` (verificador AST, aprobada).
- **Rol QA y Mutacion:** existe el arnes `herramientas/mutar.py` y el `quality-gate.sh` de 5 pasos.
- **Rol Seguridad:** existen `PermissionManager` (catalogo de 28 acciones, listas roja/verde),
  `KillSwitch` y HITL.
- **Rol Observabilidad:** existe `observability.py` con audit log append-only y sellado.
- **Rol Memoria:** existen `PersistentMemory`, `ModeloUsuario`, `AlmacenSenales`.
- **Rol Arquitecto:** existe `architecture_manifest.toml` (fuente unica de verdad, D41) + prueba AST.
- **Rol Documentacion:** existen `CLAUDE.md`, `CHECKLIST-CONTINUIDAD.md` y este checkpoint.
- **Definiciones de agentes:** `.claude/agents/` (4 roles ya versionados).
- **Vacios conocidos que el roadmap debe cubrir:** Director General, Programador, Investigacion y
  Planificador **no tienen contraparte** en el codigo actual.

### Directrices adicionales del CEO (2026-08-03, segundo mensaje)

**El roadmap es el PLAN MAESTRO DE EVOLUCION de AURORA, no una organizacion de tareas.**

**Paso previo obligatorio — INVENTARIO TOTAL antes de proponer nada nuevo.** Inventariar todo lo que
AURORA ya posee y decidir que se reutiliza, para no duplicar: motores · modulos · agentes · pruebas ·
herramientas · protocolos · ADR · Bible · infraestructura · automatizaciones · capacidades.
**El roadmap no puede crear un sistema paralelo:** debe transformar gradualmente el sistema actual en
una organizacion capaz de desarrollar AURORA desde dentro.

**Cada fase debe responder las 7 preguntas, explicitamente:**
1. ¿Que existe hoy?
2. ¿Que falta realmente?
3. ¿Que puede reutilizarse?
4. ¿Que debe evolucionar?
5. ¿Que debe desaparecer?
6. ¿Que nuevas capacidades obtiene AURORA al terminar la fase?
7. ¿Que PORCENTAJE del trabajo puede hacer sin intervencion de Claude?

**Reduccion de dependencia externa — es un objetivo explicito del roadmap.**
Definir como se reduce la dependencia de modelos externos **sin comprometer la calidad**. No se trata
de sustituir a Claude, sino de que **Claude pase de desarrollador principal a consultor especializado**,
invocado solo cuando AURORA detecte que alcanzo un limite tecnico o cuando el CEO pida revision
estrategica. **Ese descenso de dependencia es UNO DE LOS INDICADORES PRINCIPALES del proyecto y debe
medirse objetivamente en cada etapa.**

**Vacios arquitectonicos: priorizados por IMPACTO, no por facilidad de implementacion.**
**Regla de parada:** si durante el analisis aparece un vacio mas critico que los ya conocidos,
**detenerse, justificarlo con evidencia y presentarlo antes de continuar**.

**Criterio rector:** no se busca avanzar mas rapido, sino una arquitectura que sostenga el crecimiento
de AURORA **durante años**.

### Directriz final del CEO (2026-08-03, tercer mensaje) — el PROPOSITO y el IMA

**Correccion del proposito.** Reducir la dependencia de Claude es un **RESULTADO, no el proposito**.
El proposito es un ecosistema donde AURORA **comprenda** el estado del proyecto, **planifique** su
evolucion, **ejecute** trabajo, **valide** resultados, **aprenda** de ellos y **proponga mejoras** de
forma continua — siempre dentro de los limites de la arquitectura y **bajo supervision humana para las
decisiones estrategicas**.

**Indice de Madurez de Autoevolucion (IMA)** — a proponer en el roadmap como **indicador principal del
proyecto**. Nueve dimensiones minimas:

1. Comprension del proyecto
2. Capacidad de planificacion
3. Capacidad de implementacion
4. Capacidad de validacion
5. Capacidad de auditoria
6. Capacidad de recuperacion ante fallos
7. Capacidad de aprendizaje
8. Capacidad de coordinacion entre agentes
9. Dependencia de asistencia externa

**Cada indicador exige tres cosas:** (a) definicion objetiva · (b) forma de medicion · (c) criterio
claro de fase completada.

**Requisito duro:** el IMA debe **actualizarse automaticamente con evidencia obtenida del propio
sistema**, NO por valoracion subjetiva. Un indice que se rellena a mano es una opinion, no una metrica.

**Filtro obligatorio para TODA capacidad propuesta** — responder explicitamente:
1. ¿Esta capacidad hace mas inteligente a AURORA **como producto**?
2. ¿Esta capacidad hace mas capaz a AURORA de **desarrollar la siguiente version de si misma**?

Si ambas respuestas no son positivas, **probablemente no es prioridad de esta etapa**.

**Estatus:** con esto la vision estrategica queda definida. El roadmap pasa a ser **la guia de evolucion
del proyecto durante los proximos hitos**, y todas las decisiones futuras deben poder alinearse con el.

### Observacion tecnica ya detectada (no re-analizar, verificar al construir el roadmap)
El IMA —y en particular la dimension 9— **exige instrumentar el proceso de desarrollo, no el producto**.
Hoy **no existe ninguna instrumentacion para eso**: el audit log mide lo que AURORA hace como producto,
no lo que el equipo hace al construirla. Sin resolver esa brecha, los porcentajes de cada fase serian
estimaciones y no datos — el patron "declarado != real" otra vez. **Es lo primero que hay que examinar.**

### CIERRE DE LA DEFINICION METODOLOGICA + FASE 1 (CEO, 2026-08-03, cuarto mensaje)

**La fase de definicion metodologica queda CERRADA.** Se deja de diseñar como se trabaja y se empieza a
construir la capacidad de autoevolucion. El roadmap es el documento rector, **pero no puede ser un
ejercicio teorico**.

**REGLA PERMANENTE:** *cada fase debe terminar con una **capacidad REAL de AURORA**, utilizable de
inmediato — no solo documentacion ni decisiones de arquitectura.*

**Estructura obligatoria de cada fase del roadmap:**
Objetivo · **Capacidad nueva que AURORA obtiene** · **Evidencia objetiva de que funciona** ·
Impacto sobre el IMA · Dependencias · Riesgos · Criterios de finalizacion.

**FASE 1 — el primer ciclo cerrado.** Debe ser **lo minimo necesario para que AURORA coordine su
propio trabajo**. NO se busca autonomia completa: se busca **cerrar el ciclo**. Siete pasos:

1. Recibir un objetivo.
2. Descomponerlo en tareas.
3. Asignar esas tareas a sus agentes internos.
4. Consolidar los resultados.
5. Detectar conflictos.
6. Preparar un **Decision Package** cuando la decision sea estrategica.
7. Presentar un **informe ejecutivo al CEO**.

**Criterio del CEO:** si ese ciclo funciona, aunque sea de forma limitada, **se cruza un punto de no
retorno**. A partir de ahi se amplian capacidades, **no se rediseña el proceso**.

**Encargo concreto del roadmap:** identificar cual es esa Fase 1 y que **todo el trabajo posterior se
construya sobre ella**. Ese es el inicio real del Sistema Operativo Interno de AURORA.

### AUTORIZACION DE INICIO + NUCLEO VIVO (CEO, 2026-08-03, quinto mensaje)

**Etapa de planificacion CERRADA. Comienza la construccion del Sistema Operativo Interno.**
**El roadmap queda AUTORIZADO a iniciarse.**

**Disciplina permanente (aplica a todo el proyecto):**
- **No crear documentacion** si antes no existe una implementacion o validacion que la justifique.
- **Cada Decision Package termina convertido en capacidad funcional o queda explicitamente descartado.**
- **La documentacion es un artefacto del desarrollo, no el objetivo del desarrollo.**

**PRIORIDAD ADICIONAL — identificar el primer "NUCLEO VIVO":** el conjunto **minimo** de componentes
que permita a AURORA empezar a trabajar sobre si misma **de manera persistente**. No se busca todavia
una organizacion completa de agentes: se busca **el primer ciclo autonomo persistente**.

**El nucleo debe responder, como minimo:**
1. ¿Donde vive el estado del trabajo?
2. ¿Quien decide cual es la siguiente tarea?
3. ¿Quien verifica que la tarea termino correctamente?
4. ¿Quien actualiza el estado del proyecto?
5. ¿Como se reanuda automaticamente tras cualquier interrupcion?
6. ¿Como evita repetir trabajo ya realizado?

**Debe identificarse reutilizando todo lo existente antes de proponer componentes nuevos.**

**CRITERIO PRINCIPAL DE PROGRESO DEL PROYECTO:**
> *AURORA debe construir capacidades que **permanezcan despues de cada sesion**. Cada sesion debe dejar
> a AURORA **objetivamente mas capaz** que al comenzar.*

**Sigue vigente:** todo cambio de arquitectura, Bible, ADR o modelo de gobierno se presenta como
Decision Package **antes** de implementarse.

### Hipotesis de partida a VERIFICAR con el inventario (no dar por cierta)
De los 7 pasos del ciclo de Fase 1: los pasos **6 y 7** (Decision Package e informe ejecutivo) ya
existen como practica establecida; los pasos **3 y 4** (asignar a agentes, consolidar) tienen
precedente operativo en el despacho de exploradores y auditores. **Lo que no existe es la PERSISTENCIA
del ciclo:** hoy el objetivo, su descomposicion y el estado de cada tarea viven en el contexto del
modelo y se pierden al terminar la sesion. Las 6 preguntas del nucleo vivo apuntan todas a esa misma
carencia. **Probable nucleo real de la Fase 1 = estado del trabajo persistente + reanudacion
automatica.** Verificar con el inventario antes de proponerlo.

### PUNTO DE INFLEXION — PERSISTENCIA OPERATIVA (CEO, 2026-08-03, sexto mensaje)

El CEO eleva a **mayor vacio arquitectonico de AURORA** el hecho de que **hoy el ciclo de trabajo solo
sobrevive porque un humano y un modelo escriben un checkpoint a mano**.

**El roadmap NO empieza preguntandose como organizar agentes.** Empieza por:
> **¿Que necesita existir para que AURORA nunca vuelva a depender de la memoria de una sesion?**

**El inventario tiene como objetivo descubrir ese nucleo.** Si confirma la hipotesis, **la Fase 1 no es
"crear agentes": es construir la PERSISTENCIA OPERATIVA de AURORA.**

**Persistencia Operativa = que AURORA pueda, por si misma:**
1. Saber exactamente donde quedo su trabajo.
2. Saber cual era el objetivo activo.
3. Saber que tareas estaban abiertas.
4. Saber quien era responsable de cada una.
5. Saber que decisiones estaban pendientes.
6. Saber que evidencias ya existen.
7. Saber que falta por validar.
8. **Reanudar automaticamente sin depender del contexto de un modelo.**

**Instruccion:** investigar si esa capacidad puede construirse **reutilizando los componentes
actuales**. Si puede reutilizarse, **esa es la prioridad**. Si NO puede, entregar un **Decision Package**
que explique exactamente **que componente falta y por que**.

**PRINCIPIO PERMANENTE (registrado tambien en `CLAUDE.md` §4, reglas no negociables):**
> *Toda capacidad importante de AURORA debera sobrevivir al reinicio de una sesion. Si una capacidad
> desaparece cuando termina la conversacion, todavia no pertenece realmente a AURORA. Solo pertenece
> aquello que el propio sistema puede recuperar, comprender y continuar por si mismo.*

Es, en palabras del CEO, **la verdadera diferencia entre un asistente conversacional y un sistema
operativo de inteligencia**.

## Modo de trabajo vigente (CEO, 2026-08-03)

1. **No abrir nuevos Decision Packages ni alertas**, salvo bloqueo crítico para la implementación.
2. **Prioridad: cerrar deuda, no crear documentación.**
3. Detenerse al ~98 % de contexto y escribir este checkpoint.
4. Al reanudar: leer este fichero y continuar desde el paso pendiente.
