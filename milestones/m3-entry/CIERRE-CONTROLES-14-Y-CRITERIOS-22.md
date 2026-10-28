# Cierre · controles del `§14` + criterios de aceptación del `§22` + deuda del `§21`

**Fecha:** 2026-08-30 · **DP:** `DP-DEVELOPMENT-ORCHESTRATOR` (aprobado) · **Commits:** 0 · **Push:** 0

---

## 0 · Por qué existe este incremento, y por qué no hizo falta una decisión nueva

La sesión anterior cerró declarando la cola vacía. **Era falso, y el CEO tenía razón al no aceptarlo.**

Lo que estaba vacío era la cola de `DEC-ORCH-2` —cuyo alcance es `eliminar_codigo_muerto` y en el plano
de desarrollo no queda código muerto—. Pero un Decision Package aprobado **es un contrato**, y sus
criterios de aceptación son trabajo derivado de él. El cierre de F1 dejó esta línea:

> | A6–A12 | worker, revisor, GitHub, seguridad, cuota, 0/7 | **FUERA DE F1** — dependen de F2–F5, bloqueadas |

F2, F3 y F4 se cerraron después. **De los siete criterios que esa fila aparcaba, solo uno seguía
dependiendo de F5.** Los otros seis llevaban semanas autorizados y sin demostrar. Nadie afirmó nada
falso: la condición que los bloqueaba dejó de existir y nadie volvió a mirar. Es `declarado ≠ real` en
su forma más silenciosa —la novena vez que este proyecto lo encuentra—.

Lo mismo con el `§14`, que se titula *«los controles son estructurales, no confianza»*: cuatro de sus
filas describen un control que **no existía en el código** `[EJEC]`. Y con el `§21`, que declaró una
deuda con su condición de vencimiento escrita —*«cuando C5 se implemente, esta prueba debe apuntar a la
clase real o se convierte en decoración»*—: C5 se implementó en F4 y la deuda venció sin que nadie la
cobrara.

**Descubrimiento dirigido sobre el perímetro ya autorizado, que es exactamente lo que el CEO pidió.**
Ninguna tarea inventada: cada una cita el apartado del DP que la ordena.

---

## 1 · Qué cambió técnicamente

### Los cuatro controles del `§14` que estaban declarados y no existían

| Fila del `§14` | Estado medido antes | Qué se construyó |
|---|---|---|
| **Kill switch** — *«fichero centinela consultado en cada iteración»* | `ruta_centinela()` existía, pero es el centinela del **`flock`**. El bucle no consultaba ninguno | `ruta_parada()` · `parada_solicitada()` · consulta al principio de **cada** iteración · evento `parada_de_emergencia` · reversible |
| **Tarea repetitiva** — *«misma huella»* | ninguna huella de tarea | `huella_de_tarea()`: `sha256` de *(acción, objetivo, ficheros ordenados)*. **Sin el `id`**: la amenaza es trabajo repetido, no id repetido |
| **Medir con el árbol mutado** — *«un lock que impide toda otra tarea»* | sin rastro | `mutacion_en_curso()` sobre `/proc`. El ciclo se niega y registra `medicion_rechazada_por_mutacion` |
| **A12** — *«`COMPLETED` solo tras el criterio mecánico»* | `cerrar_tarea` exigía evidencia verificada, **pero la enmarcaba el propio Worker** | criterio fijado antes de invocar y exigido **por el motor único** (ver §2.ter: la primera versión lo puso en el llamante y una auditoría lo refutó) |

### A12 · el hueco real, y por qué era grave

`§14.bis` dice que este vector quedó cerrado **por diseño**. En el código no lo estaba:

```
tarea → sobre (lleva criterio_de_finalizacion) → worker → evidencia → verificar_efecto → cerrar_tarea
                                                            ↑
                                              la evidencia la elige el WORKER
```

`verificar_efecto` mira el mundo y no el texto —eso es cierto—, **pero mira el trozo de mundo que la
evidencia le señala**. Una evidencia que se cumple sola —`{"tipo":"salida_contiene","patron":"OK",
"salida":"OK"}`— la pasa siendo falsa la tarea. Nada ataba la comprobación al `criterio_de_finalizacion`
registrado antes de invocar.

Lo construido sigue las cuatro reglas del `§14.bis` al pie de la letra:

1. `fijar_criterio()` lo escribe en el event log **antes**. Un segundo criterio distinto lanza
   `CriterioAlterado`; repetir **el mismo** es idempotencia y no invalida nada.
2. `criterio_valido()` exige una **capacidad del catálogo de la política**, no una lista escrita en el
   módulo: si viviera en el código, ampliarla no exigiría acta del CEO.
3. `verificar_criterio(directorio, id, ejecutor)` **no tiene parámetro por donde entre la afirmación
   del Worker**. La garantía es la misma forma que el `Veredicto` sin campo `autoriza`: lo que no
   existe en el tipo no se pondera mal más adelante.
4. `admite_nivel_auto()`: sin criterio mecánico, la tarea no es `AUTO`.

La atadura es **doble**: huella `sha256` del criterio **y** origen. Solo con la huella no basta —el
criterio vive en un log que el worker puede leer, así que copiarla está a su alcance—; el `origen` dice
**quién la calculó**.

### La deuda del `§21`, cobrada

`CAMPOS_VEREDICTO` en `test_modelo_orquestador.py` pasa de ser una tupla escrita a mano a derivarse de
`revisores.Veredicto.__dataclass_fields__`. El DP lo pedía con estas palabras: *«su poder de detección
frente a una implementación futura que se desvíe es nulo»*.

---

## 2 · Dos hallazgos, y ninguno era el que se buscaba

### HALLAZGO 1 · la zona segura tenía una puerta abierta para que las pruebas pasaran

`autoconstruccion.zona_permitida` terminaba así:

```python
return _ZONA_PERMITIDA in texto or texto.startswith("/tmp/") or "/pytest-" in texto
```

Las dos últimas cláusulas existían porque las pruebas trabajan en directorios temporales. El precio:
**el guardarrail de producción protegía la zona declarada *más todo `/tmp`*.**

Lo material no es la teoría, es la cuenta: **17 pruebas de la batería pasaban por ese hueco.** Creían
ejercitar la regla real y ejercitaban la excepción, así que la barrera nunca se probó donde importa.
Cerrarlo las rompió a las 17 —esa es la demostración de que el hueco era real—.

Es el caso de control que este proyecto exige antes de escribir una aserción —*«¿qué tendría que
romperse para que fallara?»*— contestado por el lado que no se mira: **la prueba pasaba porque el
código la dejaba pasar, no porque la garantía existiera.**

Arreglo: sin `raiz`, la zona es exactamente la declarada. Una prueba que necesite un sandbox lo declara
**visiblemente en la llamada**, y otra prueba comprueba que ningún módulo de producción escribe ahí una
ruta a mano. La excepción sigue existiendo, pero **declarada, acotada y vigilada** en vez de escondida
dentro del guardarrail.

### HALLAZGO 2 · `acceptEdits` anula la allowlist — medido contra el binario real

`§14.ter` declaraba dos capas de seguridad como deuda de verificación. `A11` dice: *«ningún control se
declara operativo sin un intento real de violación que falle»*. Se midió con `medicion-a11.py` contra
`claude` 2.1.251, cada capa con su caso de control:

```
OK    · CONTROL · con Write y sin hook, DEBE escribir        modo=default      fichero_creado=True
OK    · CAPA 1 · allowlist sin Write, NO debe escribir       modo=default      fichero_creado=False
OK    · CAPA 2 · hook PreToolUse exit 2 pese a Write         modo=default      fichero_creado=False
OK    · HALLAZGO · acceptEdits ANULA la allowlist            modo=acceptEdits  fichero_creado=True
```

**A11 CUMPLIDO `[EJEC]`.** Las dos capas bloquean un intento real, y el caso de control demuestra que
sin ellas la escritura sí ocurre —sin él, «no se creó el fichero» no distinguiría una barrera de un
agente que no lo intentó—.

Y con el hallazgo: **el modo de permisos puede anular la allowlist.** Bloquea en `default` y en `plan`;
**no bloquea en `acceptEdits`**. El `§14` llama a `--allowedTools` *«control primario `[EJEC]`»* sin
mencionar que un segundo parámetro lo desactiva.

Hoy `permisos_de()` devuelve siempre `plan`, así que el orquestador **nunca estuvo expuesto**. Pero
nada lo impedía: `bypassPermissions` estaba prohibido por su nombre y `acceptEdits` hace lo mismo por
otra vía. Una garantía que se sostiene porque nadie escribió la otra palabra no es una garantía. Ahora
`permisos_de()` **se niega** ante cualquier modo fuera de `MODOS_QUE_NO_ANULAN_LA_ALLOWLIST`.

### Un tercer defecto, en mis propias pruebas

`test_A9_un_porcentaje_SIN_fuente_ni_instante_se_rechaza` verdeaba porque pasaba `ventana="SHORT_4H30"`,
que **no existe**: el `ValueError` venía de la validación de ventana, no de la garantía. Una prueba
decorativa, del tipo que ya produjo ≥4 falsos PASS aquí. **Lo encontró la mutación, no yo** — `C22-M11`
sobrevivió y esa fue la señal.

---

## 2.ter · La auditoría independiente refutó este cierre — y tenía razón

**Lo que este documento afirmaba unos párrafos más arriba era falso.** Un auditor distinto del
implementador, con el encargo explícito de atacar A12 «con especial dureza», encontró **dos GRAVE**.
Se dejan escritos aquí, en el mismo sitio donde estaba la afirmación equivocada, porque un cierre que
oculta lo que casi se le cuela no sirve de aviso a nadie.

### GRAVE 1 · `transicion()` era una ruta alternativa

La puerta del criterio mecánico la puse en `agentes.cerrar_tarea`. Pero `control_plane.transicion()`
es la primitiva que usa **toda** la base —incluida `agentes.py`— y no la consultaba:

```python
ag.cerrar_tarea(d, "T-1", falsa, autoridad="orquestador")   # -> SinEvidencia   (mi puerta, cerrada)
cp.transicion(d, "T-1", "COMPLETED", autoridad="ceo", causa="afirmo que está hecho")
cp.estado_de(d, "T-1")                                      # -> "COMPLETED"    (se cerró igual)
```

Es **ALERTA-005** literal: *«toda ejecución pasa por el motor único… ninguna ruta alternativa»*. Y la
razón por la que mis 34 pruebas nuevas no lo veían es la que más conviene recordar: **todas entraban
por `cerrar_tarea`. Probé la puerta que yo había puesto, no el edificio.**

### GRAVE 2 · el aparato existía y no estaba enchufado

Ningún módulo de producción llamaba a `fijar_criterio()` antes de invocar a un worker. Para **toda
tarea real**, `criterio_registrado()` devolvía `None`, la rama de protección quedaba **inerte**, y el
cierre seguía dependiendo de la evidencia que enmarca el worker — la vulnerabilidad exacta que este
documento declaraba cerrada.

Es, palabra por palabra, el defecto que `CLAUDE.md` pone como ejemplo: *«el mutante "la composición no
enciende las automatizaciones" sobrevivió con 426 pruebas en verde, y era ALERTA-005 otra vez»*.
Aparición número **10** de `declarado ≠ real`, y otra vez con la asistencia externa como autora.

### Cómo se corrigió

La regla vive ahora **solo en el motor único**. `cp.transicion()` exige, para llegar a `COMPLETED`:

- con autoridad **no humana**: criterio mecánico fijado, ejecutado y superado;
- con autoridad **humana**: puede cerrar sin criterio —`§14.bis` regla 4, lo no automatizable lo juzga
  una persona—, pero **no puede saltarse uno ya fijado**: un criterio que se puede esquivar declarando
  otra autoridad no es un criterio.

`cerrar_tarea` dejó de escribir la regla por su cuenta. Tenerla en dos sitios era además el defecto
que el `§0` del CHECKPOINT ya documenta, **en su versión cara: la copia que faltaba era una ruta
abierta**. El bucle del orquestador y el circuito de `D-ORCH-3` fijan ahora el criterio **antes** de
invocar y registran `criterio_verificado`.

### Los dos MEDIO

- **`zona_permitida(ruta, raiz=…)` concedía el producto.** Con `raiz` dado, la función dejaba de mirar
  la zona y solo comprobaba pertenencia: `raiz=<raíz del repo>` abría `walking-skeleton/`. Mi arreglo
  del Hallazgo 1 había cerrado un agujero y abierto otro con la misma forma. Ahora producto y
  gobernanza se rechazan **siempre**, por segmento de ruta: *«el producto queda fuera»* lo sostiene la
  función, no una convención de nombres vigilada por `grep`.
- **Mensajes falsos.** El docstring y las excepciones de `orquestador.py` decían *«el catálogo `AUTO`
  está vacío»*, falso desde `D-ORCH-3` (2026-08-26). `INV-9` va en las dos direcciones: no fingir
  capacidad que no existe, y no negar la que sí. Un mensaje falso en una excepción es lo que alguien
  lee justo cuando está depurando y menos margen tiene para dudar.

### La lección, que vale más que las cuatro correcciones

**Una garantía probada sobre su propia función no es una garantía del sistema.** Hay que probarla
desde la primitiva que cualquiera usaría, recorriendo **todas** las vías públicas. La prueba que
faltaba —`test_TODAS_las_vias_publicas_a_COMPLETED_respetan_el_criterio`— es hoy la que sostiene A12,
y no existía porque yo estaba mirando mi propio código en vez del sistema.

**Y el proceso funcionó exactamente como está diseñado:** lo encontró un auditor independiente, no el
implementador. La regla *«el que implementa nunca audita su propio trabajo»* no es burocracia; aquí
fue la diferencia entre un control real y uno declarado.

---

## 2.bis · Dos divergencias más, encontradas siguiendo la cola

Cerrado el `§14` y el `§22`, la cola no estaba vacía: el mismo método —leer el contrato y medir el
código— dio dos filas más.

### `§13 · Idempotencia`, mecanismo 2 — el `--session-id` no derivaba del sobre

El `§13` lo escribe así, y las cuatro últimas palabras son el mecanismo entero:

> `uuid5(namespace, tarea_id + sha256(sobre))`. La misma tarea **con el mismo sobre** produce el
> mismo identificador.

El modelo conceptual —escrito **antes** de que existiera el orquestador, justamente para fijar el
contrato— lo modela igual: `id_de_sesion(tarea_id, huella_sobre)`. La implementación derivaba **solo
del `tarea_id`**, y ni siquiera con `uuid5`.

**Consecuencia medible:** dos ejecuciones de la misma tarea con permisos, presupuesto, criterio de
finalización o versión de política **distintos** recibían el **mismo** identificador de sesión. El
orquestador las habría tomado por la misma ejecución — lo contrario de lo que el mecanismo existe para
conseguir.

Es la deuda del `§21` otra vez, en otro sitio: **las pruebas que había fijaban lo implementado en vez
de lo acordado.** `test_c4_el_session_id_se_DERIVA_de_la_tarea_y_es_estable` pasaba el `id` como
cadena y por eso el defecto podía vivir en verde.

### `§12 · Recuperación`, la fila de la escritura interrumpida

`§12` declara: *«Escritura de evidencia interrumpida → línea truncada → **línea descartada del log**,
tarea `FAILED`»*. Medido `[EJEC]` sobre un log con la última línea a medias:

```
leer_eventos               -> JSONDecodeError
proyectar                  -> JSONDecodeError
registrar_evento           -> JSONDecodeError
verificar_integridad_log   -> JSONDecodeError
```

**Ninguna línea se descartaba: el Control Plane entero dejaba de ser legible.** Y lo más grave de esa
lista es `registrar_evento`: el sistema no podía ni anotar que estaba roto, así que no había
recuperación posible sin editar el fichero a mano. Para un componente cuya razón de ser es sobrevivir
a un `SIGKILL` —el criterio `A4`, medido aquí con un `kill -9` real— era el fallo exacto que tenía que
soportar.

**Lo que distingue el arreglo de un agujero:** truncada **no** es lo mismo que alterada. Solo la
*última* línea puede quedar a medias por una caída; las anteriores ya estaban completas y con `fsync`.
Una línea rota **en medio** viene de que alguien tocó el fichero, y descartarla en silencio convertiría
el log encadenado en un registro que se repara solo borrando lo que le estorba. Esa se rechaza con
`LogCorrupto`.

Y una corrección sobre la marcha, antes de que la encontrara nadie: la primera versión **regeneraba el
fichero entero**. `§5` dice de C1 *«nunca: borrarse ni reescribirse»*, y regenerarlo bastaría con que
la serialización produjera un byte distinto para alterar la historia en silencio. Ahora se **trunca**:
los bytes de los eventos ya cerrados quedan físicamente fuera de alcance, y una prueba lo comprueba
**por bytes** —única forma de distinguir «no cambió» de «volvió a escribirse igual»—.

---

## 2.quater · Cuatro auditorías independientes, y cada una encontró algo un nivel más abajo

La `§2.ter` cuenta la primera. Hubo **cuatro**, y la secuencia es la parte que vale la pena leer:
cada vez cerré la ruta que me señalaron, y cada vez la siguiente auditoría encontró la misma clase de
agujero **un piso por debajo**.

| # | Lo que encontró | Dónde estaba |
|---|---|---|
| **1.ª** | La puerta del criterio vivía en `agentes.cerrar_tarea`, no en el motor; y el aparato del `§14.bis` no estaba **cableado** a ninguna ruta de producción | en el llamante |
| **2.ª** | Mi prueba «TODAS las vías públicas» enumeraba **tres a mano** y omitía `completar_tarea` y `fijar_estado_tarea`; y los eventos del criterio se podían **forjar** en crudo | en la lista escrita a mano |
| **3.ª** | `_registrar_evento_gobernado` aceptaba **cualquier tipo**: bypass total. Y `registrar_sesion` se llamaba **antes** de invocar, quemando toda tarea `AUTO` en su primer intento | en la puerta interna |
| **4.ª** | `esperar_por_cuota` **no era «la única vía»**: `transicion()` aceptaba `WAITING_FOR_QUOTA` a pelo. Y `guardar()`/`actualizar_estado()` persistían un `COMPLETED` fabricado | en el borde de persistencia |

**Dos afirmaciones mías resultaron falsas y están corregidas donde se escribieron:**

- *«`esperar_por_cuota` es la única vía que este módulo ofrece»* — no lo era. La regla del `§11` vive
  ahora **en el motor**, donde pasa todo el mundo.
- *«Ninguna ruta pública concede estado sin gobierno — probado»* — tampoco. `validar_tareas()` exige
  hoy para un `COMPLETED` lo mismo que exigen `completar_tarea` y `fijar_estado_tarea`.

### Lo que cambió de fondo, y no es ninguna de las correcciones

Las cuatro veces el defecto tenía la misma forma: **una lista escrita a mano haciéndose pasar por un
barrido**. Ampliarla una quinta vez solo aplaza la quinta auditoría. Lo que se hizo:

- La clasificación de invocables vive en **una sola fuente** (`FUNCIONES_GOBERNADAS`,
  `NO_CONCEDEN_ESTADO`, `ESCRITORES_CRUDOS`), y las dos primeras son **disjuntas** —una función en las
  dos se restaba del barrido sin que nada fallara—.
- El barrido recorre **los módulos leídos del directorio**, no una tupla; **privadas** y **métodos**;
  **clases anidadas** y **`functools.partial`**; y busca el estado **también por su constante**.
- Cada exclusión que quité se había pagado con una auditoría: `_` escondió la puerta interna, «solo
  funciones sueltas» escondía los métodos, «solo este módulo» escondía los otros seis.

### El residual que **sí** se declara, y por qué es distinto

`_registrar_sin_lock` escribe el fichero. **No se puede gobernar desde dentro del proceso**: quien
pueda importarla puede abrir `eventos.jsonl` con un editor. Lo que sí se garantiza:

1. **Ninguna ruta pública** concede estado sin gobierno.
2. La cadena `sha256` es **verificable**: una escritura cruda no pasa desapercibida.
3. El worker **no tiene** permiso de escritura sobre `entorno/control-plane/` — A6, medido `[EJEC]`.

La 4.ª auditoría comprobó expresamente si esa declaración era honesta o una excusa, y señaló que
`guardar`/`actualizar_estado` **sí** eran cerrables y estaban declaradas como si no. Tenía razón, y
por eso están cerradas.

### La lección, en una frase

**Una garantía probada sobre su propia función no es una garantía del sistema**, y una lista de
sitios donde mirar que excluye sitios no es un barrido: es una muestra. Cuatro auditorías
independientes lo demostraron cuatro veces sobre el mismo código, y ninguna la encontró el
implementador.

---

## 3 · Verificación

| Qué | Resultado |
|---|---|
| Batería del Control Plane | **527 passed** (antes 382) |
| Communication Plane | 180 passed · 5 skipped |
| Agente externo | 20 passed |
| `ruff` | **PASS** |
| Quality Gate | **FAIL 5/1139/3 — idéntico al baseline**, sin regresiones nuevas |
| `estado.json` | **INTACTO** (`sha256` 1195a9f6… antes y después) |
| Árbol tras mutar | limpio: ningún fichero quedó mutado |

### Mutación — 215 mutantes en **once** arneses, 0 supervivientes, 0 `NO_APLICADO`

| Arnés | Mutantes |
|---|---|
| `f1-orquestador` | 35 |
| `f2-f3-orquestador` | 18 |
| `d-orch-3-failover` | 19 |
| `d-orch-2-autoconstruccion` | 15 |
| `d-orch-2-review` | 13 |
| `ciclo-autonomo` | 11 |
| `f4-revisores` | 14 |
| **`controles-14-y-criterios-22`** | **57** |
| **`recuperacion-12b`** | **11** |
| **`auditoria-3-y-cuota-11`** | **12** |
| **`auditoria-4`** | **10** |

**La primera pasada dio 7 supervivientes.** No se cerró con ellos. Diagnóstico uno a uno:

- **4 huecos reales de cobertura míos** — `C14-M11` (ninguna prueba ejercitaba el barrido real de
  `/proc`), `C14-M20` (nadie probaba una huella correcta con origen falso), `C22-M7` (nadie probaba que
  una raíz declarada **acota**), `C22-M11` (la prueba decorativa de arriba).
- **2 listas de pruebas mal declaradas por mí** — `C14-M18` y `C22-M8`. La prueba que los mataba
  existía y no la declaré. Es la trampa que el propio `CLAUDE.md` advierte: *«elegir mal las pruebas
  produce supervivientes falsos»*.
- **1 equivalente** — `C14-M16` (`fijados[-1]` en vez de `fijados[0]`). **Retirado como EQUIVALENTE
  DEMOSTRADO POR EJECUCIÓN, no aceptado como superviviente**: `criterio_registrado` lanza
  `CriterioAlterado` en cuanto hay más de una huella, luego al llegar al `return` todos los registros
  tienen la misma; y un registro es `{id, criterio, huella}`, así que dos con la misma huella son
  iguales campo a campo. Demostrado ejecutando en
  `test_refijar_el_mismo_criterio_deja_entradas_IDENTICAS`.

**Y 4 `NO_APLICADO` en la regresión de arneses anteriores**, todos consecuencia directa de mis cambios
(`F23-M14`, `AC-M6`, `AC-M7`, `CA-M2`): sus patrones dejaron de casar. `NO_APLICADO` **nunca** cuenta
como detectado, así que se reapuntaron y se reejecutaron hasta volver a morir.

### El control que se disparó contra sí mismo

La exclusión mutua funcionó demasiado bien: el arnés se lanza como `python -m herramientas.mutar`, así
que al mutar **se detecta a sí mismo** y el bucle se negaba en toda la batería. No es un falso
positivo: es el control haciendo su trabajo. Las pruebas que trabajan sobre un `tmp_path` sintético
**declaran** que no miden el árbol real, con un fixture que lo dice por escrito; las de la garantía lo
vuelven a poner en `True` y ganan por ser más específicas.

Y una consecuencia más fina: la prueba del detector no puede preguntar *«¿no hay ningún arnés
corriendo?»* **desde dentro de un arnés** —es indecidible ahí— y dejaba la base en rojo justo al
mutarla. Se separó `_hay_proceso_con(marca)` para poder ejercitar el barrido con una marca inventada,
independiente del ambiente. La marca se **construye en ejecución**: escrita como literal aparecía en la
línea de órdenes del shell que lanzaba la batería, y el barrido la encontraba ahí.

---

## 4 · Qué gana AURA como producto

**Nada.** Y decirlo es obligatorio (`INV-9`).

Esto es infraestructura de desarrollo. `A10` se demostró justamente así: ningún módulo del plano de
desarrollo importa el producto, y la zona de escritura lo excluye. **La autonomía de AURORA sigue en
0/7.** Reejecutar la medición del razonador no habría demostrado nada sobre este trabajo, porque ese
número depende del razonador y no del orquestador.

Lo que gana es **el proyecto**: el orquestador ya no puede certificarse a sí mismo, se le puede parar
desde fuera de banda, no repite trabajo equivalente, y no mide mientras el árbol está mutado.

---

## 5 · Cómo lo demostraría el CEO

```bash
cd entorno/control-plane

# A12 — falsear la evidencia del Worker no completa la tarea
python3 -m pytest test_red_controles_14.py -q -k "A12 or huella_BUENA"

# El kill switch para el bucle, y es reversible
python3 -m pytest test_red_controles_14.py -q -k "kill_switch"

# A11 — las dos capas, contra el binario real (cuesta cuota, tarda ~2 min)
python3 medicion-a11.py

# La zona ya no tiene puerta trasera
python3 -m pytest test_red_criterios_22.py -q -k "TMP or gobernanza"
```

---

## 6 · Deuda abierta y observaciones

**Deuda** (bloquea, o compromete arquitectura/seguridad):

- **`mutacion_en_curso()` solo detecta, no bloquea.** La mitad cooperativa —un lock que
  `herramientas.mutar` tomara al arrancar— vive en `walking-skeleton/herramientas/mutar.py`, **fuera
  del perímetro** de `DEC-ORCH-2`. Hoy la detección es por barrido de `/proc`: real y medida, pero
  best-effort. Registrada como oportunidad bloqueada.

**Observaciones** (no son deuda; se anota la condición que las promovería):

- **`max_derivadas` del `§14` no se implementó.** El orquestador **no crea tareas derivadas**, así que
  el control no tiene nada que guardar. Se promovería a deuda el día que se cree la primera tarea
  derivada. Construirlo hoy sería fabricar trabajo.
- **El `§14` describe `--allowedTools` como control primario sin mencionar que el modo de permisos
  puede anularlo.** Corregirlo es editar el DP, que es gobernanza. Se reporta, no se toca.
- **`§10.3` del DP afirma que `D22` delegó en un «CTO humano»**. Es falso: `1.1:94` dice que el CTO es
  **Fable (IA)**. Ya se reportó en el cierre de F4 y sigue sin corregir. Misma razón: es el DP.

---

## 7 · Retorno sobre Tokens

Este incremento **no añade capacidad de gastar**: añade controles que **paran**. Y quita trabajo futuro
de tres maneras concretas:

- El criterio mecánico hace que una tarea `AUTO` se cierre **sin lectura humana de prosa**. Ese era el
  cuello de botella que obligaba a que alguien leyera la evidencia del worker.
- La huella impide pagar dos veces por trabajo equivalente en el mismo ciclo.
- La exclusión mutua evita el coste que este proyecto ya pagó una vez: una auditoría entera basada en
  una medición hecha sobre un árbol mutado.

Y deja una lección que vale más que el código: **una cola vacía no se declara, se demuestra por
descubrimiento dirigido sobre el contrato.** Esta sesión encontró 11 tareas reales donde la anterior
había reportado cero, sin inventar ninguna y sin una decisión humana nueva.
