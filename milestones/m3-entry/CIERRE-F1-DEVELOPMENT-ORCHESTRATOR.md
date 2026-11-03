# Cierre · `DP-DEVELOPMENT-ORCHESTRATOR` — Fase **F1** = C1 + C2

**Fecha:** 2026-08-26 · **Rama:** `worktree-m3-entry` · **Commits:** 0 · **Push:** 0
**Autorización:** CEO — *«AUTORIZO DP-DEVELOPMENT-ORCHESTRATOR … EJECUTA COMO UN ÚNICO BLOQUE
VERTICAL Y ENTREGA UN ÚNICO RESULTADO FINAL»*.
**Alcance ejecutado:** solo **F1**. `§20` la declara *«Depende de: nada»*, y `§5` confirma que C1 y
C2 *«se pueden construir, probar y usar sin resolver ninguna de las decisiones pendientes de §25»*.
**F2–F5 permanecen bloqueadas** por D-ORCH-1…4, que son del CEO y no de este bloque.

---

## 1 · Qué cambió técnicamente

Todo en `entorno/control-plane/control_plane.py`, **aditivo**, como exige `§9`. Cierra los tres
defectos que el propio DP midió `[EJEC]`:

| Defecto del DP | Cómo estaba | Qué lo cierra |
|---|---|---|
| **P3** — *«`estado.json` se sobrescribe entero en cada guardado»* | no había historia | `eventos.jsonl` append-only: `seq` monotónico, `fsync` por línea, `sha256` **encadenado** |
| **P2** — *«si dos procesos cargan y guardan, el último gana y el otro pierde sus cambios en silencio»* | no había lock | `flock` exclusivo envolviendo **leer-modificar-escribir** (`lock_estado`, `actualizar_estado`) |
| **P4** — *«nada impide pasar de `COMPLETED` a `WORKING`»* | no había gobierno | `TRANSICIONES` de `§6` + autoridad y causa obligatorias, en **las dos** rutas |

**Superficie nueva:** `registrar_evento` · `leer_eventos` · `verificar_integridad_log` ·
`ruta_eventos` · `ruta_centinela` · `lock_estado` · `proyectar` · `estado_de` · `transicion` ·
`validar_transicion` · `actualizar_estado` · `reconciliar_tras_caida` · `TRANSICIONES` ·
`AUTORIDADES_HUMANAS` · `ESTADOS_SOLO_HUMANO` · `ESTADOS_EN_VUELO` · `TransicionInvalida`.
**Superficie modificada:** `fijar_estado_tarea` (gobernada, `§9.3`) y `ESTADOS`, que gana el único
estado que `§6` autoriza añadir: `WAITING_FOR_REVIEW`.

### Cuatro decisiones de diseño que el DP no resolvía

1. **La cadena encadena, no solo firma.** Un `sha256` por línea detecta una línea *alterada* pero
   **no** una *eliminada*. `hash_anterior` convierte un borrado en una ruptura visible.
2. **La proyección es función pura del log.** No lleva `actualizado` ni `cuota`: ninguno deriva de
   la historia —son observación del entorno— y meterlos haría que dos reconstrucciones del mismo
   log difirieran. Una proyección que no es función de su historia no es una proyección.
3. **Re-afirmar el mismo estado es idempotencia, no transición.** La tabla de `§6` no lista `X → X`
   porque describe el *flujo*, no la repetición. Exigirlo allí rompería registrar dos veces el mismo
   bloqueo de cuota **sin proteger nada**: el estado resultante es idéntico.
4. **Una tarea nueva se crea, no transiciona.** Sin esa distinción el gobierno prohibiría registrar
   un bloqueo de entorno sobre una tarea que aún no consta `WORKING` —que es lo que `interrumpir` y
   `registrar_bloqueo_de_cuota` hacen hoy— y P4 se habría «cerrado» rompiendo el uso legítimo.

### Las **cuatro** rutas al estado están gobernadas — corregido tras auditoría

> **Corrección de una afirmación falsa de este documento.** Su primera versión decía *«ambas rutas
> al estado están gobernadas»*. **Eran cuatro, y dos estaban abiertas.** La auditoría independiente
> encontró la más grave; la cuarta salió tirando del mismo hilo. La afirmación era exactamente el
> patrón `declarado ≠ real` **dentro de la herramienta que vigila el trabajo**, que es donde más
> daño hace.

| Ruta | Estado |
|---|---|
| `transicion()` — sobre el log | gobernada desde el principio |
| `fijar_estado_tarea()` — en memoria | gobernada desde el principio (`§9.3`) |
| **`completar_tarea()`** | **abierta hasta la auditoría** — escribía en `trabajo_completado`, de donde `estado_de_tarea` lee `COMPLETED` |
| **`registrar_evento(tipo="estado_de_tarea")`** | **abierta hasta la auditoría** — evento crudo que la proyección aplicaba como bueno |

Todas comparten hoy `validar_transicion`. `interrumpir` y `registrar_bloqueo_de_cuota` entran por
`fijar_estado_tarea`, así que quedan cubiertas. El estado previo se lee con `estado_de_tarea`, **no**
del diccionario, porque `completar_tarea` también produce `COMPLETED` (mutante **F1-M13**).

---

## 2 · Qué gana AURA como producto

**Nada. Y decirlo es parte del entregable.** `§0` del DP: *«No es AURORA y no le concede ninguna
capacidad. La autonomía de AURORA sigue en 0/7 y este DP no la mueve.»* Verificado `[EJEC]`:
`control_plane.py` tiene **0** referencias a `aura_skeleton` o `walking-skeleton`, y la garantía
`test_el_control_plane_no_importa_nada_del_producto` sigue viva.

Lo que gana es **el trabajo sobre AURORA**: la historia de qué se hizo, quién lo ordenó y por qué
deja de ser prosa reconstruible a mano y pasa a ser un log verificable. Es la precondición de la
regla del CEO *«toda capacidad importante sobrevive al reinicio de sesión»* aplicada al propio
proceso de desarrollo.

---

## 3 · Cómo lo demuestra un usuario — **ejecutado**

```
A2 · dos procesos reales escribieron a la vez -> 21 eventos, 0 perdidos
     cadena integra: True
A5 · la tarea espera una decision. Estado: DECISION_REQUIRED
     orquestador  -> RECHAZADO      worker    -> RECHAZADO
     revisor      -> RECHAZADO      adaptador -> RECHAZADO
     bot          -> RECHAZADO
     ceo          -> ACEPTADO. Estado: WORKING
P4 · ni el CEO reabre una tarea cerrada:
     transicion prohibida COMPLETED -> WORKING; desde COMPLETED solo: ('<ninguno: es final>',)
A1 · estado.json BORRADO. Reconstruido del log: True
     seq 22  WAITING_FOR_NEXT_TASK -> WORKING           por orquestador (arranca)
     seq 23            WORKING -> DECISION_REQUIRED     por orquestador (falta decidir F2)
     seq 24  DECISION_REQUIRED -> WORKING               por ceo         (decidido: F1 primero)
     seq 25            WORKING -> COMPLETED             por ceo         (F1 entregada)
```

**A4 con `SIGKILL` real**, no simulado — proceso lanzado, matado a mitad con `kill -9`:

```
proceso 864444 muerto con SIGKILL
integridad tras SIGKILL: True | eventos: 2      <- el fsync cumplio
estado antes de reconciliar: WORKING
reconciliadas: ['T-MUERE'] -> estado: FAILED
```

El `flock` se liberó solo al morir el proceso: la reconciliación lo tomó sin bloquearse.

### Bajo presión, y la reconciliación es idempotente

```
PRESION · 8 procesos x 60 eventos = 480 esperados
  escritos      : 480   (perdidos: 0)
  seq sin huecos: True        cadena integra: True
  procesos vistos: 8 de 8

RECONCILIACION · 1a llamada: ['T-X']  ·  2a llamada: []   -> estado final: FAILED
```

**Sobre el coste:** la medición dio ~200 eventos/s con `fsync` por línea. **No es un techo
arquitectónico y no se publica como tal**, conforme a la regla del CEO del 2026-08-04: el número
depende del disco y de la carga de esta máquina, no del modelo. Se registra como observación
`[EJEC]` del 2026-08-26 y solo sería relevante si algún día el orquestador escribiera a un ritmo
comparable — hoy escribe unidades de eventos por tarea.

### Criterios de aceptación de `§22`

| # | Criterio | Veredicto |
|---|---|---|
| **A1** | estado reconstruible tras borrar `estado.json` | **CUMPLIDO** `[EJEC]` |
| **A2** | dos procesos concurrentes no pierden escrituras | **CUMPLIDO** `[EJEC]` — dos procesos reales |
| **A3** | tarea completada no se reejecuta tras reinicio | **CUMPLIDO** `[EJEC]` |
| **A4** | tarea interrumpida queda `FAILED`, nunca `COMPLETED` | **CUMPLIDO** `[EJEC]` — `SIGKILL` real |
| **A5** | `DECISION_REQUIRED` no se resuelve sin acto humano | **CUMPLIDO** `[EJEC]` — **16 vías del código**, 0 abiertas |
| A6–A12 | worker, revisor, GitHub, seguridad, cuota, 0/7 | **FUERA DE F1** — dependen de F2–F5, bloqueadas |

### Verificación

| Medición | Resultado |
|---|---|
| Pruebas nuevas de F1 | **44**, todas en verde |
| Control Plane completo | **242 passed** `[EJEC]` |
| Communication Plane | **180 passed · 5 skipped** — sin cambios |
| agente-externo | **20 passed** — sin cambios |
| `ruff` (los tres planos) | **All checks passed** |
| **Mutación** `mutaciones/f1-orquestador.toml` | **30 detectados · 0 supervivientes · 0 NO_APLICADO** |
| Quality Gate del producto | **FAIL 5 / 1139 passed / 3 skipped** — **idéntico al baseline previo** |

Los 5 fallos del gate son los ya clasificados y **ninguno lo causa F1**: G-1 ×3 (deuda aceptada por
`DEC-G1-MANIFIESTO-TRAS-F4 = C`), `test_garantias_vigentes` (defecto preexistente del auditor de
rutas) y `test_limite_reintentos` (su consecuencia).

**Un número interno sí se movió, y conviene decirlo antes de que alguien lo lea mal.** Dentro de
`test_garantias_vigentes`, el contador pasó de **175 de 477** a **180 de 482**. No es una regresión:
son los 5 mutantes que F1 añadió al re-auditar. Medido `[EJEC]`:

```
mutantes de f1-orquestador.toml reportados como AUSENTE : 26
total «AUSENTE — no existe control_plane.py»            : 71   (de 27 TOML distintos)
```

El auditor de garantías **resuelve rutas solo bajo `walking-skeleton/`**, y `control_plane.py` vive
en `entorno/control-plane/` **a propósito** —es infraestructura de desarrollo, no producto—. Así que
declara «AUSENTE» los 26 mutantes de F1, igual que ya hacía con los 45 de los otros 26 TOML del
Control Plane. **Los 26 se acaban de ejecutar y los 26 murieron.** Es un falso negativo del auditor,
no una garantía perdida: exactamente el patrón `declarado ≠ real`, pero **del lado del medidor** —el
mismo del que CLAUDE.md ya advierte con el caso de la medición en paralelo al arnés.

F1 no crea este defecto; lo hace 26 unidades más visible. Su corrección es acotada —enseñar al
auditor a resolver rutas bajo `entorno/`— y **no pertenece a este DP**.

### Dos mutantes que sobrevivieron y por qué importa

La primera pasada dio **19/21**. Los dos supervivientes eran huecos de cobertura **míos**, no del
código, y ambos del mismo tipo: *la prueba pasaba por el motivo equivocado*.

- **F1-M5** (comprobación del enlace): el caso de «línea eliminada» se detectaba por el **salto de
  `seq`**, así que la comprobación de la cadena nunca llegaba a ejercitarse. Hizo falta el caso
  realista —línea sustituida, `seq` correcto, firmada consigo misma— donde lo único que delata la
  manipulación es `hash_anterior`.
- **F1-M7** (proyección determinista): comparar dos proyecciones seguidas no prueba pureza, porque
  `_ahora()` tiene precisión de **segundos** y ambas caen en el mismo. Hizo falta mover el reloj
  entre las dos reconstrucciones.

Es exactamente lo que CLAUDE.md advierte: *«una prueba sin caso de control no vale»*. Ambas se
detectan ahora.

---

## 3.bis · Auditoría independiente — **encontró lo que yo había dado por bueno**

El protocolo exige que *«el que implementa nunca audita su propio trabajo»*, y aquí se ve por qué:
la primera versión de F1 pasó 228 pruebas, 21 mutantes sin supervivientes y una demostración de A5
que parecía exhaustiva — **con dos puertas abiertas**.

| # | Hallazgo | Gravedad | Estado |
|---|---|---|---|
| **H1** | `completar_tarea()` cerraba una tarea en `DECISION_REQUIRED` **sin acto humano** | **GRAVE — A5 incumplido** | **CERRADO** · mutante `F1-M22` |
| **H2** | La prueba que garantizaba la tabla era **decorativa**, y ocultaba una divergencia real con `§6` | **GRAVE** | **CERRADO** · `F1-M25` |
| **H3** | El atajo de idempotencia se evaluaba antes del control de autoridad humana | MENOR | **CERRADO** · `F1-M24` |
| **H4** | `registrar_evento` crudo fabricaba estado saltándose el gobierno | GRAVE (propio) | **CERRADO** · `F1-M23` |

**Por qué la mutación no los detectó, que es la lección de verdad.** Los 21 mutantes degradaban
código **que existía**. Ninguno podía degradar un control **que no estaba escrito**. La mutación
verifica que lo construido tiene red; **no dice qué falta por construir**. Para eso hace falta un
lector independiente que pregunte *«¿por dónde más se entra?»* — que es precisamente lo que CLAUDE.md
llama tratar la mutación como *«un revisor más, no una prueba más»*.

**H2 merece una nota aparte.** La prueba decorativa la escribí yo, en este mismo bloque, al reciclar
una prueba de premisa superada: dejé `A or B` donde `B` comparaba solo las **claves** del diccionario.
El operando alcanzable no comprobaba nada, y por debajo viajó una divergencia real con el DP. Es el
`≥4.º` falso PASS documentado del proyecto y confirma el corolario de CLAUDE.md: *«antes de escribir
una aserción, pregúntate qué tendría que romperse para que fallara»*.

### A5, ahora sí, «por todas las vías del código»

```
vias candidatas detectadas por inspeccion: 13
  fijar_estado_tarea -> WORKING    -> RECHAZADO      completar_tarea            -> RECHAZADO
  fijar_estado_tarea -> COMPLETED  -> RECHAZADO      interrumpir                -> RECHAZADO
  fijar_estado_tarea -> FAILED     -> RECHAZADO      registrar_bloqueo_de_cuota -> RECHAZADO
  re-afirmar DECISION_REQUIRED     -> RECHAZADO      transicion -> WORKING      -> RECHAZADO
  evento crudo estado_de_tarea     -> RECHAZADO      reconciliar_tras_caida     -> sin efecto

y el humano si puede:
  fijar_estado_tarea como ceo      -> WORKING        transicion como ceo        -> WORKING

A5 CUMPLIDO [EJEC] · 10 vias intentadas, 0 abiertas, y el humano sigue pudiendo
```

### Un defecto que introduje al corregir, y que corregí

Al gobernar `completar_tarea` dupliqué la regla «crear no es transicionar» en dos funciones. Es
literalmente el defecto estructural que el `§0` del CHECKPOINT identifica tras cinco auditorías:
**una regla escrita dos veces**. Vive ahora solo en `validar_transicion`, con el mutante `F1-M26`
protegiendo que no vuelva a dividirse.

### Segunda auditoría: el arreglo de H1 introdujo otro GRAVE

Los cuatro hallazgos quedaron cerrados, **y mi corrección abrió uno nuevo**. Al gobernar
`completar_tarea` añadí la regla «crear no es transicionar» con un `return` que saltaba también la
tabla y el control humano: **cualquier id nunca visto podía aparecer en `COMPLETED`** con cualquier
cadena por autoridad.

Lo delató la **asimetría**, no una prueba: `transicion()` sí lo rechazaba —*«no se transiciona lo que
no existe»*— y la ruta en memoria no. Dos rutas al mismo estado con distinto rigor es ALERTA-005. Y
mi barrido de A5 no lo vio porque **las 10 vías partían de una tarea que ya estaba** en
`DECISION_REQUIRED`; ninguna probó una tarea inexistente.

Cerrado con `ESTADOS_CREABLES` —solo `WAITING_FOR_NEXT_TASK`, `WORKING`, `WAITING_FOR_ENVIRONMENT`,
`WAITING_FOR_QUOTA`, `FAILED`—, que es exactamente lo que el uso legítimo necesita: `interrumpir` y
`registrar_bloqueo_de_cuota` crean tareas en tres de ellos. Mutantes `F1-M27/M28/M29`.

**La corrección obligó a migrar ~20 pruebas** que completaban tareas sin haberlas empezado. Al
revisarlas encontré que mi migración mecánica había metido una línea de *setup* **dentro** de un
`with pytest.raises`: la prueba pasaba, pero si el setup lanzara pasaría igual sin comprobar nada.
Un escaneo AST del árbol completo confirma que ya no queda ninguno.

### La garantía que cierra la clase entera de defecto

H1 y H4 fueron **el mismo error dos veces**: apareció una ruta al estado y nadie la contó. Enumerar
rutas a mano no escala —quedó demostrado, el cierre dijo «ambas» cuando eran cuatro—. Así que la
garantía ya no enumera: `test_ninguna_funcion_FUERA_de_las_gobernadas_cambia_el_estado_de_una_tarea`
**recorre el módulo entero** y comprueba que ninguna función pública fuera de las gobernadas puede
mover una tarea. El mutante `F1-M30` planta una quinta ruta clandestina en `iniciar_tarea` y el
detector la encuentra.

---

## 3.quater · Rompí el `estado.json` real del Control Plane

**Y hubo pérdida de datos que no he podido reparar entera.** Debe leerse antes que cualquier otra
parte de este informe.

La primera versión de ese detector llamaba a **toda** función pública con el estado — incluida
`guardar()`, cuyo `destino` por defecto es `entorno/control-plane/estado.json`, el estado **real** del
proyecto. Lo sobrescribió con el estado de prueba. No hay copia: el directorio es *untracked*, no
existe en `main` ni en ningún otro punto del disco `[EJEC]`.

| | |
|---|---|
| **Reconstruido** | `defectos`: `DEF-CUERPO-LIBRE` y `DEF-FLAKY-P2`, derivados de `CHECKPOINT-CONTINUIDAD.md` (líneas 1842 y 1899) |
| **PERDIDO** | `trabajo_completado` (**49 entradas históricas**), `tareas` (6), `aprobaciones`, `decisiones_pendientes`, `git`, `verificacion`, `sesion_claude` |

**No he fabricado lo perdido.** Ninguna fuente del proyecto contiene esas 49 entradas, e inventarlas
es precisamente lo que D34 e INV-9 prohíben. El propio `estado.json` lleva ahora un bloque
`perdida_de_datos` con la causa, el inventario de lo perdido y la procedencia de lo reconstruido, y
cada defecto reconstruido declara su fuente en `procedencia_del_registro`.

**Prevención, no promesa:** la prueba culpable excluye las funciones que escriben en disco, y
`test_el_detector_de_rutas_NUNCA_escribe_en_el_estado_real` fija ese contrato inspeccionando las
firmas — si alguien añade otra función con ese destino por defecto, la prueba lo dice. Verificado
`[EJEC]`: el `md5` de `estado.json` ya no cambia al correr la batería completa **ni el arnés de
mutación**.

**La lección es la del propio CLAUDE.md, del lado del medidor:** una herramienta que vigila el
trabajo no puede escribir sobre lo que vigila. Es hermana del caso ya documentado de medir en
paralelo al arnés de mutación.

---

## 3.ter · Una pregunta para el CEO — **no la he decidido yo**

Al cerrar H2, la tabla volvió a ser literalmente la de `§6`. Eso deja visible algo que la divergencia
tapaba: **`WAITING_FOR_HUMAN` tiene salidas declaradas pero ningún estado lo declara como destino**,
así que es **inalcanzable desde el flujo**. Mi versión lo había añadido como destino de `WORKING`
—sin decirlo, que es el problema—.

**No lo enmiendo por cuenta propia:** añadir un destino a la tabla del DP es decidir sobre el flujo
de estados, y eso es del CEO. Las opciones son (a) añadir `WAITING_FOR_HUMAN` como destino de
`WORKING`, (b) retirarlo del vocabulario si `DECISION_REQUIRED` ya lo cubre, o (c) dejarlo
inalcanzable a propósito, reservado para fases posteriores. **Hoy no bloquea nada**, porque nada
transiciona a él.

---

## 4 · Deuda abierta

| Estado | Qué |
|---|---|
| **Bloqueado por el CEO** | F2–F5 del DP: D-ORCH-1 (F5/revisor externo), D-ORCH-2 (F4), D-ORCH-3 (F3), D-ORCH-4 (F2) |
| **Deuda aceptada** | G-1 ×3 en el Quality Gate — `DEC-G1-MANIFIESTO-TRAS-F4 = C` |
| **Defecto preexistente** | `test_garantias_vigentes`: el auditor resuelve rutas solo bajo `walking-skeleton` |
| **Observación técnica** | `guardar()` sigue sin lock **a propósito** — es una escritura, no una actualización. Quien necesite la garantía usa `actualizar_estado`. Se promovería a deuda si aparece un tercer escritor que use `guardar()` directamente sobre un estado compartido |
| **Observación técnica** | `proyectar()` relee el log entero en cada llamada. Irrelevante hoy; se promovería a deuda si el log supera el orden de 10⁴ eventos o si la proyección entra en un bucle caliente |

**Ninguna es BLOQUEANTE** según el criterio del `§0` del CHECKPOINT: ninguna permite una acción
destructiva, viola ADR-0003 ni rompe INV-9.

---

## 5 · Qué capacidades existentes mejoran

- **`fijar_estado_tarea`** pasa de registrar a **gobernar**, sin romper a ninguno de sus 17 puntos
  de uso. `TransicionInvalida` hereda de `ValueError` para que quien ya capturaba `ValueError` siga
  capturándolo: endurecer una garantía no debería obligar a reescribir el manejo de errores de quien
  la usaba bien.
- **`interrumpir`** gana respaldo estructural: antes *pedía* no fabricar un `COMPLETED` falso; ahora
  la tabla lo **impide**, y `reconciliar_tras_caida` extiende esa honestidad a las muertes por
  `SIGKILL`, donde no hay nadie para llamar a `interrumpir`.
- **`DEF-FLAKY-P2` cerrado.** La prueba de concurrencia aseveraba *«se pierde exactamente una
  escritura»* —el accidente, que depende del planificador— y por eso era intermitente. Ahora asevera
  la **garantía**: con lock sobreviven las dos, siempre. Una prueba de concurrencia deja de ser
  flaky cuando mide la garantía en vez del accidente.
- **Tres pruebas de premisa superada**, reescritas en vez de borradas. Dos avisaban de su propio
  final por escrito —*«si esto falla, las transiciones ya están gobernadas y P4 está cerrado»*,
  *«si algún día el Control Plane gana un lock, esta prueba fallará»*—. Fallaron. Mantenerlas
  midiendo el defecto habría sido pedirle al código que **no** hiciera lo que se le encargó.

---

## 6 · Retorno sobre Tokens

**¿Deja al proyecto más capaz de evolucionar con menos intervención humana y menos contexto?**

Sí, y de forma medible: el estado del trabajo deja de necesitar que alguien **lea prosa** para
reconstruir qué pasó. `proyectar()` responde «quién ordenó qué y por qué» desde el log, sin cargar
el CHECKPOINT de 2 865 líneas en contexto. La reconciliación tras caída elimina la pregunta más cara
al retomar —*«¿esa tarea llegó a terminar?»*— que hoy se responde investigando a mano.

**Lo que NO hace:** no reduce la intervención humana en las **decisiones**. Al contrario, `A5` la
hace obligatoria y la deja registrada. Esa es la dirección correcta: menos intervención en la
mecánica, más trazabilidad en el criterio.

---

## 7 · Restricciones del CEO — verificadas

| Restricción | Estado |
|---|---|
| NO sudo · NO root | **cumplido** — ninguna orden privilegiada |
| NO commit · NO push | **cumplido** — 0 commits, 0 push |
| D24 no se modifica · local-first intacto | **cumplido** — sin red, sin claves, sin terceros |
| `AURA_APPROVED` vacío · no almacenar credenciales | **cumplido** — no tocado |
| OpenCode y Codex ausentes al finalizar | **cumplido** — no se invocaron |
| No tocar `aura_skeleton/`, `orchestrator.py`, Communication Plane, contratos, canal, permisos | **cumplido** — F1 toca **un solo fichero de producción**: `entorno/control-plane/control_plane.py` |
| No crear autoridad nueva | **cumplido** — `AUTORIDADES_HUMANAS` es cerrada; `control_plane` y `entorno` son las autoridades **ya existentes** de `interrumpir` y `registrar_bloqueo_de_cuota`, ahora declaradas en vez de implícitas |
| El implementador nunca audita su propio trabajo | **cumplido en 2 de 3 rondas** — ver abajo |

**Aviso sobre la tercera ronda.** Lancé una tercera auditoría independiente acotada a
`ESTADOS_CREABLES` —la regla que nadie externo había revisado— y **murió por límite de gasto
mensual**: *«You've hit your monthly spend limit»*, el mismo modo de fallo que el `§11` del
CHECKPOINT ya documenta. El límite se restablece a las 11:00 (Bogotá).

Ejecuté yo sus siete puntos y encontré dos cosas reales —el `setup` dentro del `pytest.raises` y el
`estado.json` sobrescrito—, pero **eso es autoauditoría y no cumple el estándar del proyecto**. Las
dos auditorías anteriores demostraron que reviso peor mi propio trabajo que un tercero: entre las
dos encontraron cuatro defectos que yo había dado por buenos. **`ESTADOS_CREABLES` sigue sin
revisión independiente.**
