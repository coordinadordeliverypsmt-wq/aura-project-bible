# CHECKPOINT DE CONTINUIDAD

**Actualizado:** 2026-08-26 · **Rama:** `worktree-m3-entry`
**HEAD:** compruébalo siempre con `git log --oneline -1`. **Este fichero no puede declarar su propio
commit:** cualquier SHA escrito aquí queda desfasado en el instante en que se commitea el propio
checkpoint, así que un desajuste entre esta cabecera y `git` **no es un error del repositorio**. Al
redactar esta nota `HEAD` era `790fafc` —el commit que actualizó este fichero tras cerrar la campaña
del razonador— y el commit que introduzca esta línea será, por definición, posterior.
**`main` = `origin/main` = `d933a08`** — el incremento **NO está integrado**, y así debe permanecer
hasta que el CEO lo ordene.

> **Este fichero está versionado.** Se commiteó por primera vez en `6db8302` y esta actualización
> reconcilia su contenido con el estado real tras `8698035`. Los únicos elementos no rastreados del
> árbol son `milestones/m3-entry/medicion-razonador/__pycache__/` y `esperar_umbral.sh`, excluidos
> deliberadamente del commit por decisión del CEO.

---

## 0 · CRITERIO OPERATIVO VIGENTE — orden del CEO, 2026-08-15. PERMANENTE

**Las pruebas y las auditorías protegen el producto; NO son el producto.**

El objetivo de gobierno **no** es acumular auditorías en un incremento. Es que AURORA gane
**capacidad real de autonomía de forma segura**. En consecuencia:

1. **Un defecto encontrado NO es razón automática para abrir otra ronda.** Cada pendiente se
   clasifica antes de decidir:
   - **BLOQUEANTE** — puede permitir una acción destructiva, violar el consentimiento (ADR-0003) o
     romper INV-9. **Se corrige.**
   - **IMPORTANTE** — afecta a la robustez pero no permite una operación insegura. **Se documenta.**
   - **DEUDA** — puede corregirse después sin bloquear el avance. **Se documenta.**
2. **Si no hay BLOQUEANTE, se documenta y se para.** No se sigue por inercia.
3. Antes de seguir iterando sobre un incremento hay que responder: *¿esto aumenta el trabajo nuevo
   que AURORA puede completar por sí misma?* Si no, la iteración es andamiaje.

**Este criterio nació de una medición, no de una opinión:** cinco auditorías, cuatro rechazos, y las
tres últimas encontraron **variantes del mismo defecto estructural** —una regla escrita dos veces—.
El rendimiento por ronda era decreciente y visible.

---

## 1 · A · ESTADO ACTUAL

### Commits del incremento

| Commit | Qué es |
|---|---|
| `19bb9db` | `feat` — el contexto del fallo viaja hasta la tarea derivada |
| `f252ad9` | `fix` — 1ª auditoría: defecto **D1** + el camino destructivo |
| `6ab99f9` | `docs` — retirada la condición 4 del criterio de aceptación (orden del CEO) |
| `b664b42` | `fix` — 2ª auditoría: retirada la herencia de args |
| `0f89dbf` | `docs` — checkpoint intermedio |
| `31580fe` | `fix` — 3ª auditoría: un cambio sin sustituto es un borrado |
| `a1a91a9` | `fix` — 4ª auditoría: regla única, contención por segmentos |
| `c202de5` | `fix` — 5ª auditoría: previsualización en ASCII |

Diff frente a la base: **6 ficheros de producción, +297 / −25 líneas.**

### Medición del estado, ejecutada sobre `c202de5`

| Medida | Resultado |
|---|---|
| **Quality Gate** | **PASS** — formato · lint · mypy · pruebas · contratos |
| **Pruebas** | **919 pasadas, 3 omitidas** + 8 de contratos |
| **Mutación del incremento** (`contexto-derivado.toml`) | **33 detectados · 0 supervivientes · 0 no aplicados** |
| Arneses de los ficheros modificados, revalidados | `ejecutor-programador` 7/7 · `auditor` 3/3 · `estado-operativo` 5/5 |
| Garantías declaradas que siguen aplicando | 265/265 (`test_todas_las_garantias_declaradas_siguen_vigentes`) |

**Precisión sobre la cobertura de mutación:** `c202de5` toca `auditor.py`, `programador.py`,
`estado_operativo.py` y `operaciones.py`. Los tres arneses que apuntan a esos ficheros se
reejecutaron **sobre este commit**. Los arneses de `director.py` y `planificacion.py`
(`director-general` 9/9, `planificacion` 8/8, `ciclo-completo` 4/4, `veredicto-ejecutor` 3/3,
`protocolo-transiciones` 5/5, `gobierno-estado` 2/2) se reejecutaron en `31580fe`/`b664b42` y esos
ficheros **no han cambiado desde entonces**. La cobertura de mutación de lo modificado es completa.

### Medición de los 7 casos — `[EJEC]` sobre `c202de5`, sin cambios en cuatro rondas

| Caso | Llega contexto | Ejecutable | Solo declarado | **Resoluble sin LLM** |
|---|---|---|---|---|
| 1 · auditor AUSENTE | sí | no | **sí** | **NO** |
| 2 · auditor AMBIGUO | sí | no | **sí** | **NO** |
| 3 · auditor DEGENERADO | sí | no | **sí** | **NO** |
| 4 · QA en rojo | sí | no | no | **NO** |
| 5 · diagnóstico | sí | no | no | **NO** |
| 6 · sin ejecutor para el responsable | sí | no | no | **NO** |
| 7 · programador en rojo | sí | no | no | **NO** |

**0/7 completables sin LLM.** Los 7 llegan con contexto —eso es nuevo y real—; ninguno se resuelve
sin razonar. El CEO ordenó conservar esta medición tal cual: **no** buscar otro dominio ni fabricar un
caso mecánicamente resoluble.

Lo que llega en los casos 1–3: `motivo`, `fichero_declarado`, `buscar_declarado`, `referencia`.
Lo que llega en los casos 4–7: `motivo`.

---

## 2 · B · QUÉ ESTÁ REALMENTE TERMINADO

**Terminado, medido y con red de mutación:**

1. **El transporte del contexto.** Detección → conservación → derivación → transporte → ejecutor o
   bloqueo o escalada. Los 7 casos llegan con contexto; antes llegaban con `args={}`.
2. **D1 cerrado** — el artefacto que viaja es el **TOML de declaración**, no el fichero objetivo.
   Confirmado por tres auditorías independientes y protegido por el mutante C18.
3. **INV-9** — nada se fabrica. Lo ausente sigue ausente; lo incompleto viaja como `*_declarado`, que
   ningún ejecutor consume.
4. **El todo-o-nada** en `fichero`/`buscar`/`sustituir`, aplicado en el punto de paso y con una
   **única definición** de «valor utilizable» (`texto_utilizable`, en `core/operaciones.py`).
5. **La previsualización dice la verdad** (ADR-0003): qué se sustituye, por qué, y en ASCII puro.
6. **Contención de ruta por segmentos** — ya no depende de cómo se llamen los directorios vecinos.
7. **Gobierno intacto** — una denegación del CEO no se re-presenta con presupuesto de reintentos
   nuevo; el umbral de la capacidad 017 no se puede sortear.
8. **Sin daños colaterales** — evidencias limpias (deduplicación intacta), desacoplamiento
   Director↔planificación, corte estructural en pie, `desde_verificacion` sin cablear con su contrato
   y sus pruebas intactos.

**Terminado pero con un límite que debe leerse:** el carril «contexto **ejecutable**» existe, está
probado y **no es alcanzable desde producción**. El único productor de datos accionables es el
auditor, y deliberadamente no publica `sustituir` (INV-9). En el único camino real, la derivada nace
sin argumentos de ejecución y muere en el dry-run. **El incremento entrega contexto LEGIBLE, no
contexto EJECUTABLE.**

---

## 3 · C · BLOQUEANTES

**No queda ningún BLOQUEANTE identificado.**

Los tres que existieron se cerraron y están medidos:

| Fue bloqueante | Estado |
|---|---|
| `fichero` + `buscar` sin `sustituir` → el dry-run decía «sustituir» y **borraba** el patrón; el QA daba verde y el cambio se conservaba | **CERRADO** — se exige sustituto real; el dry-run se niega y el disco no se toca |
| Un cambio se aplicaba y **conservaba fuera del árbol declarado** (contención por prefijo de texto) | **CERRADO** — `is_relative_to`, comparación por segmentos |
| Una decisión **denegada por el CEO** se re-presentaba con `intentos=0`, sorteando el umbral de 017 | **CERRADO** — herencia de args retirada entera |

**Limitación declarada, y es importante:** los defectos de la quinta auditoría los cerré **yo**, y la
verificación independiente de esos cierres **no se ejecutó** porque el CEO detuvo la sexta auditoría.
Lo que sí existe sobre `c202de5` es: mutación 33/0/0 con mutantes escritos específicamente para cada
uno de esos defectos (C27–C33), Quality Gate PASS y 919 pruebas. **Es evidencia fuerte, pero no es
una auditoría independiente.** Debe constar así en cualquier decisión de integración.

---

## 4 · D · DEUDA E IMPORTANTES

### IMPORTANTE — afecta a la robustez, no permite una operación insegura

**I-1 · `proponer_cambio` está en el catálogo de lista roja pero NO en `ESPECIFICACIONES`.**
Sus argumentos nunca pasan por `validar()`, así que el modelo puede pedirla con cualquier `args`.
Hoy está contenido porque `EjecutorProgramador._rechazo_previo` valida por su cuenta (tipos,
sustituto real, unicidad del patrón, contención de ruta) y la previsualización es honesta. Pero es
una **inconsistencia arquitectónica**: RN-2 dice que no hay ruta para ejecución libre, y ésta es una
capacidad que altera el árbol sin contrato de argumentos declarado en el catálogo.
*Alcance verificado por lectura, 2026-08-15:* es el **único** caso. Las demás capacidades de lista
roja que escriben en disco —`escribir_archivo`, `borrar_archivo`, `mover_archivo`,
`renombrar_archivo`— **sí** están en `ESPECIFICACIONES`, y las sirve `AdaptadorComputador`, cuyas
`capabilities` se derivan de ese mismo diccionario: pasan por `validar()` con validación de rutas. El
resto de entradas rojas del catálogo (`terminar_proceso`, `instalar_software`, `pago`…) **no tienen
adaptador** — son catálogo sin implementación, y por tanto inalcanzables.

*Condición que lo promueve a trabajo:* que aparezca un segundo ejecutor fuera de `ESPECIFICACIONES`,
o que se amplíe la superficie de `proponer_cambio`.

**I-2 · `texto_utilizable` es deliberadamente incompleta, y así está declarado en su docstring.**
Rechaza diez categorías Unicode que nunca se ven solas, pero **la invisibilidad no es una categoría**:
`U+3164` (relleno hangul, `Lo`) y `U+2800` (braille en blanco, `So`) son signos legítimos en
categorías ordinarias que se pintan vacíos, y ninguna regla categórica los separa de una letra.
**La garantía que sostiene esto no es la función: es que la previsualización sea ASCII pura**, de modo
que el humano vea `'ㅤ'` antes de autorizar. No ampliar la lista de categorías: esa carrera se
pierde (dos rondas de auditoría lo demostraron).

### DEUDA — corregible después, no bloquea

**D-1 · El carril ejecutable no es alcanzable desde producción** (ALERTA-005 en forma benigna).
Es consecuencia de una decisión correcta (INV-9: el auditor no inventa el patrón nuevo), pero implica
que `contexto.update(completos)` y todo el camino «contexto ejecutable» sólo se ejercitan desde las
pruebas, con una fixture marcada explícitamente como hipotética.
*Condición que lo promueve:* que aparezca un productor real de los tres campos.

**D-2 · `milestones/m3-entry/DEUDA-PANEL-BLOQUEO-SIN-MOTIVO.md`** — el panel del Centro de Gobierno
revienta ante una tarea bloqueada sin motivo. No alcanzable en producción hoy.

**D-3 · `milestones/m3-entry/DEUDA-ADR0014-MEMORIA-VACIA.md`**

**D-4 · Coste acumulado del arnés.** El arnés de este incremento tiene **33 mutantes**, frente a los
2–9 de los demás. Los mutantes se acumulan y se ejecutan por incremento; conviene revisar si algunos
son redundantes cuando se mida cómo escala el conjunto (la decisión de no meter mutación en el Quality
Gate ya se tomó por este motivo, CEO 2026-08-02).

**D-5 · Limpieza del laboratorio de medición — PARCIALMENTE RESUELTA, con perímetro explícito.**

`milestones/m3-entry/medicion-razonador/lanzar.py` creaba el laboratorio como copia completa del
repositorio y lo borraba **al final** de la función. Los experimentos abortados nunca llegaban a esa
línea: durante la campaña quedaron copias huérfanas que **llenaron el disco y bloquearon el shell**.

**Corregido (2026-08-16, sin commitear):** `try/finally` que limpia `lab` y el `.tar`. Cubierto por
`test_lanzar_limpieza.py`, 8 pruebas junto al arnés — 5 RED reales que fallaban antes, verificadas
ejecutando la suite contra el `lanzar.py` de `790fafc` en un árbol aparte (5 failed / 3 passed).

**Lo que la corrección SÍ garantiza:** camino feliz · excepciones de Python · `TimeoutExpired` ·
`KeyboardInterrupt`/SIGINT —Python ya lo convierte en excepción, así que el `finally` lo atrapa sin
una línea sobre señales— · limpieza de `lab` · limpieza del `.tar` · **preservación de la excepción
original** · **conservación de `datos`**.

**Lo que NO garantiza, y por eso la deuda NO se cierra:** **SIGTERM, SIGHUP, SIGQUIT, SIGKILL y OOM.**
Sin manejador registrado, Python termina el proceso sin desenrollar la pila y ningún `finally` corre.
Residuo en esas vías: `/tmp/aura-lab-*` y `/tmp/aura-lab-*.tar`, ~17,9 MB por aborto, que
`tmpfiles.d` elimina en el siguiente arranque.

**Decisiones que acotan el alcance, tomadas por el CEO:** no se añadieron manejadores de señal —el
precedente del proyecto es `herramientas/mutar.py`, que resuelve el mismo problema con `try/finally`
y cero señales sobre un componente más crítico—; no hay barrido de `/tmp`; no se movió `datos`; **no
se creó ningún artefacto forense nuevo**; no se añadió saneamiento de PII; no se tocó
`start_new_session`/`killpg`.

**`datos` se conserva a propósito.** Contiene `audit.jsonl`, `memoria.json` y
`estado_operativo.jsonl`, y tras esta corrección es el **único rastro post-mortem** que sobrevive a
un aborto, porque el laboratorio ya no queda para inspeccionarlo. **No se promete retención**: vive
lo que viva `/tmp`, sujeto a la política del sistema operativo.

**Recomendación operativa, no garantía técnica:** para abortar a mano, Ctrl-C. Un `kill` no limpia.

**Sin DP**, conforme a la decisión del CEO: `lanzar.py` es instrumentación, no producto. Las pruebas
viven junto al arnés y **quedan fuera del Quality Gate del producto** por decisión explícita; se
ejecutan aparte y **no deben presentarse como cobertura del gate**.

**No cambia nada del producto:** `aura_skeleton/` intacto, Quality Gate sin modificar (919 pruebas,
3 omitidas), protocolo experimental, prompts, umbrales y mediciones sin tocar. **La autonomía sigue
en 0/7**, no hay autorización para la rama de capacidad del razonador ni para construir producto
sobre él.

---

## 5 · E · IMPACTO REAL SOBRE LA AUTONOMÍA DE AURORA

**Respuesta directa a la métrica de gobierno —*¿qué trabajo nuevo puede completar AURORA por sí
misma?*—: NINGUNO. Este incremento NO aumenta la autonomía de ejecución.**

Medido, cuatro veces, sin variación: **0 de 7 casos** son completables sin un LLM. Los tres tipos que
el auditor detecta —patrón AUSENTE, AMBIGUO, DEGENERADO— exigen **decidir un texto nuevo**, y decidir
es razonar.

Lo que sí cambió, y es real:

> **Este incremento no aumenta todavía la autonomía de ejecución de AURORA; aumenta la calidad de la
> información que AURORA puede transportar hasta su siguiente capacidad de razonamiento.**

Antes, la tarea derivada nacía con `args={}` y moría con «un cambio necesita fichero y patron a
sustituir» **aunque AURORA supiera perfectamente cuál era el fichero**. Ahora llega con el artefacto a
corregir, el patrón declarado, la referencia de la garantía rota y el motivo. Eso mejora de forma
medible **la escalada al CEO** y deja el problema en condiciones de ser razonado. No lo resuelve.

### Diagnóstico arquitectónico: sí, hay andamiaje de más — y dónde

**Se construyó un tubo de alta integridad para una información que, al otro extremo, todavía no tiene
consumidor capaz de actuar sobre ella.** El consumidor es el LLM, y en este hardware —Celeron N4020,
2 núcleos, 1,0 GB de RAM libre, 25,8 s para responder «Hola»— no puede hacer ese razonamiento.

Distinguiendo con honestidad, porque no todo el trabajo de las cinco rondas fue andamiaje:

**NO era andamiaje — eran defectos de seguridad reales, en una capacidad de lista roja alcanzable
hoy.** El borrado encubierto, el escape del árbol y la regresión de gobierno existían en
`EjecutorProgramador` con independencia de este incremento, y se habrían disparado por la ruta del
LLM. Cerrarlos estaba justificado por sí mismo.

**SÍ era andamiaje — la carrera contra los caracteres invisibles.** Las rondas 4 y 5 se gastaron en
categorías Unicode para un modelo de amenaza que, en un sistema local-first, monousuario y sin claves
de terceros, exige un modelo local comprometido o un usuario tecleando invisibles a propósito. La
respuesta correcta —la previsualización en ASCII— llegó en la ronda 5. **Debí salir de esa carrera una
ronda antes.**

**La lección arquitectónica que hay que conservar:** *cuando una guarda necesita una lista negra que
crece en cada revisión, la guarda tiene la forma equivocada. Hay que mover la garantía a un punto
donde la regla pueda enunciarse entera.* Aquí ese punto era el consentimiento informado, no el
filtrado de entrada.

**El cuello de botella ya no es la calidad de la información. Es la capacidad de razonamiento** — y
ésa es una decisión de hardware o de modelo, que el CEO tiene deferida.

---

## 6 · F · SIGUIENTE INCREMENTO RECOMENDADO

**Recomendación: el siguiente incremento debe MEDIR, no construir.**

**«¿Puede el modelo local, en este hardware, resolver alguno de los 7 casos con el contexto que ahora
recibe?»**

Es la aplicación literal de la orden del CEO —*«el siguiente Decision Package deberá partir de esta
evidencia real, no de una expectativa de que el LLM ya pueda resolverla»*— y de la regla de que el
desarrollo lo guía la evidencia del uso real.

Qué produce, y por qué es lo que más rinde ahora:

- Toma el contexto que hoy llega (`fichero_declarado`, `buscar_declarado`, `referencia`, `motivo`),
  se lo da al modelo local y mide **tres cifras**: tasa de acierto al proponer un `sustituir`
  correcto, latencia real y tasa de propuestas inseguras o inventadas.
- **Cuesta casi nada de código** y no amplía la superficie de ataque: el resultado pasa por el mismo
  dry-run, la misma lista roja y la misma previsualización honesta que ya están cerrados.
- **Responde la pregunta que bloquea todo lo demás:** si el tubo tiene consumidor. Si la tasa es
  distinta de cero, el siguiente incremento es conectar el razonador y la autonomía sube de 0/7 por
  primera vez. Si es cero, queda **demostrado con datos** que el bloqueo es de hardware o de modelo, y
  la decisión de inversión deja de ser una hipótesis.
- Cualquier otro incremento en esta línea —más protección, más transporte— añade tubo sin consumidor.

**Lo que NO recomiendo ahora:** otra ronda de auditoría sobre este incremento; ampliar la protección
del ejecutor; cablear `desde_verificacion`; abrir 010–012 o 015/016; ni comprometer hardware antes de
tener la medición de arriba.

---

## 7 · QUÉ NO ESTÁ AUTORIZADO

- **No integrar. No publicar. No hacer push.** Orden expresa del CEO, vigente.
- **No lanzar la sexta auditoría.** Orden expresa del CEO, vigente.
- **No** ejecutar más mutaciones ni commits sin nueva orden.
- **No** borrar cambios, ni `reset`, ni tocar el estado actual.
- **No** inventar una capacidad nueva ni cambiar el alcance aprobado.
- **No** buscar otro dominio ni fabricar un caso mecánicamente resoluble para mejorar el 0/7.

## 8 · Diferido por el CEO — no abrir sin acta

Incremento B (Experiencia Conversacional v1, DP escrito), 010–012 (Traductor Operativo), 015/016
(bloqueados por hardware), la decisión de hardware o cambio de modelo, y el cableado de
`desde_verificacion`.

## 8.bis · Campaña diagnóstica del razonador local — **EJECUTADA Y CERRADA EN EVIDENCIA**

Registrada en el commit **`8698035`** (21 ficheros, 3.137 inserciones): seis Decision Packages, ocho
artefactos JSON de evidencia, seis scripts reproducibles y el registro del servidor, todo bajo
`milestones/m3-entry/` y `milestones/m3-entry/medicion-razonador/`.

> **NOTA DE CONTINUIDAD.** La campaña diagnóstica del razonador local queda cerrada en evidencia. La
> autonomía permanece en 0/7. El resultado no autoriza construcción de producto ni extrapolación a
> otros modelos o recursos. Cualquier nueva exploración de capacidad requiere un Decision Package
> específico y aprobación previa.

### Qué se ejecutó

| Actividad | Estado |
|---|---|
| Humos 1, 2 y 3 con `qwen2.5:0.5b` | **ejecutados** |
| Comprobación de denegación estructural, sin modelo | **verificada** — A y B en verde, 54 pruebas |
| Diagnóstico del instrumento 3B (¿confunde la forma de invocación?) | **cerrado** — era la ventana de carga, no la invocación |
| Comparación `0.5b` vs `3b`, mismos bytes de entrada | **ejecutada** |
| Experimento de aislamiento de `sustituir` | **ejecutado y cerrado** (§13 de su DP) |

### Resultado

**Ambos modelos FAIL.** Ninguno produjo una propuesta ejecutable ni, en el experimento de aislamiento,
el patrón correcto. **La rama de representación/estructura del problema no explica suficientemente el
fallo observado.**

**Lo que el resultado NO permite:** no se extrapola a otros modelos, cuantizaciones, ficheros reales
ni a la capacidad general de razonamiento local. **No autoriza construir producto sobre el razonador
local actual.** **Autonomía = 0/7, sin cambio.**

### Estado formal de los seis DP — ninguno pasa a aprobado

Todos figuran como **`PROPUESTO`** en su propio encabezado, y **este checkpoint no altera ese estado**.
Que un DP se haya ejecutado no lo convierte en aprobación arquitectónica.

| DP | Estado formal | Situación |
|---|---|---|
| `DP-MEDICION-RAZONADOR-LOCAL` | PROPUESTO | **La tanda de 30 NO se ejecutó.** Cualquier continuación exige aprobación |
| `DP-COMPARACION-RAZONADORES` | PROPUESTO | Ejecutado; **su ejecución no es aprobación arquitectónica** |
| `DP-DIAGNOSTICO-INSTRUMENTO-3B` | PROPUESTO | Cerrado; **su resultado no autoriza implementar** |
| `DP-EXPERIMENTO-AISLAMIENTO-SUSTITUIR` | PROPUESTO | Resultado ejecutado y documentado en §13; se respeta su estado formal |
| `DP-RECURSO-MINIMO-RAZONADOR` | PROPUESTO | **Permanece abierto**: la restricción de memoria bloquea la medición de capacidad |
| `DP-FRONTERA-RAZONAMIENTO-DETERMINISMO` | PROPUESTO | Conclusión conservada; **no se convierte en implementación** |

### Decisiones arquitectónicas todavía ABIERTAS

- **Capacidad del razonador** — otro modelo, cuantización o recurso. **Sin DP.** Requiere uno propio.
- **Recurso mínimo** — sin responder: la memoria impide medir la capacidad, y la capacidad determina
  el recurso.
- **Integración de este incremento a `main`** — sigue sin autorizar.

**Cualquier siguiente experimento requiere su propio Decision Package y aprobación previa.**

### Reglas de entorno del arnés, conservadas por su valor operativo

- **CUIDADO CON `AURA_DATOS`:** debe apuntar **fuera del laboratorio**. Si apunta dentro, el estado, la
  memoria y el log de auditoría se escriben en el lab y su huella SHA-256 cambia por razones legítimas,
  arruinando la prueba de no ejecución.

**Hechos de cableado ya averiguados — no volver a buscarlos:**

- `componer(config, confirmador=None)` (`composicion.py:220`) **acepta el confirmador por inyección**.
  Es la pieza que hace estructural el criterio de seguridad: se pasa un confirmador que **deniega
  siempre** y se conserva el `PermissionManager` real (`composicion.py:238`) y la lista roja real. El
  motor simula ANTES de confirmar, así que se captura `viable` + previsualización y la ejecución no
  ocurre porque el permiso se deniega. **No hace falta tocar `aura_skeleton/`.**
- `Configuracion` (`composicion.py:147`): `raices_permitidas`, `usar_stack_real` (`AURA_STACK_REAL=1`),
  `modelo` (`AURA_LLM_MODEL`, por defecto `qwen2.5:3b`).
- Ollama: binario en `/usr/local/bin/ollama`, **servicio NO levantado**; pesos en disco bajo
  `/usr/share/ollama/.ollama/models` — `qwen2.5:3b` (1,93 GB) y `qwen2.5:0.5b` (398 MB).
- Timeout del cliente: 180 s por defecto, elevable con `AURA_OLLAMA_TIMEOUT_S`.
- **Captura de la respuesta cruda del modelo, sin tocar el producto.** `OllamaProvider` expone un solo
  punto: `async def infer(self, prompt: str) -> str` (`modules/providers_real.py:68`), y el prompt de
  sistema y el catálogo se inyectan dentro de `_infer_sync`. El arnés **envuelve `infer` desde fuera**
  —en la copia del laboratorio— para registrar prompt y respuesta literales. Es instrumentación del
  arnés, no un cambio del producto. También ahí se lee `AURA_OLLAMA_TIMEOUT_S`.
- **RECONOCIMIENTO COMPLETO.** No queda nada más que averiguar antes de escribir el arnés.
- **Campos del `Sistema`** que devuelve `componer` (`composicion.py:175`), para no adivinar al escribir
  el arnés: `orquestador` (en español, **no** `orchestrator`), `motor`, `permisos`, `kill_switch`,
  `estado_operativo`, `director`, `motor_ciclo`, `memoria`, `plan`, `materializaciones`,
  `ruta_memoria`, `ruta_audit`. El ciclo real se dispara con `motor_ciclo.correr(objetivo, max_latidos=N)`
  y el oyente ya está cableado en la composición.
- Responsables con ejecutor real (`_EJECUTORES`, `composicion.py:210`): `programador`, `qa`, `auditor`,
  `diagnostico`. El caso «sin ejecutor» se provoca con cualquier otro responsable.
- **Punto de entrada real del producto para un turno**: `Orchestrator.handle_utterance(user_id,
  audio_text, trace_id)` seguido de `Orchestrator.wait(trace_id, timeout=10)`
  (`core/orchestrator.py:859` y `:867`). Es la ruta que hay que usar para medir el producto y no una
  función aislada.
- **DEFECTO DE AISLAMIENTO — CRÍTICO, detectado antes de ejecutar nada.** `EjecutorProgramador` y
  `EjecutorAuditor` **NO reciben su raíz de `Configuracion`**: la calculan como
  `Path(__file__).resolve().parents[1]` (`composicion.py:256` y `:258`), es decir, el
  `walking-skeleton/` del paquete que se haya importado. `raices_permitidas` **no los afecta** — eso
  sólo gobierna a `AdaptadorComputador`.

  Consecuencia: si el arnés se ejecuta importando `aura_skeleton` desde el worktree real, el ejecutor
  y el auditor **operarían sobre el worktree real**, no sobre el laboratorio. El aislamiento por
  `git archive` habría sido decorativo, y la comparación SHA-256 del laboratorio habría salido
  idéntica **precisamente porque nada tocaba el laboratorio**: un falso PASS de seguridad.

  **Corrección del protocolo, dentro del arnés:** el arnés se lanza con el intérprete situado en
  `<lab>/walking-skeleton`, importando `aura_skeleton` **desde la copia del laboratorio**, para que
  `__file__` resuelva dentro del lab. Verificación obligatoria antes de medir: imprimir la raíz
  efectiva de ambos ejecutores y **exigir que esté bajo el laboratorio**. Y las huellas SHA-256 se
  calculan **también sobre el worktree real**, no sólo sobre el lab, porque el riesgo era ése.

- **TRAMPA YA DETECTADA, antes de gastar el ensayo:** `wait()` trae **timeout por defecto de 10 s**, y
  en esta máquina el modelo tarda 25,8 s sólo en responder «Hola». Con el valor por defecto, TODAS las
  mediciones darían falso HARDWARE. El arnés debe pasar un `timeout` explícito y holgado, coherente
  con `AURA_OLLAMA_TIMEOUT_S`, y **registrar cuál usó** en la evidencia.

**No autorizado mientras la medición esté pendiente:** conectar el razonador al ciclo, decidir
hardware, abrir otro incremento, commitear código, y tocar `aura_skeleton/`.

## 9 · Reglas de entorno que cuestan tiempo si se olvidan

- **Nada corre en paralelo con `herramientas.mutar`**: muta los ficheros **en el sitio**, así que
  mientras corre el árbol no contiene el código real. Si el proceso muere por SIGKILL,
  `git checkout -- <fichero>` recupera.
- El sandbox rechaza `env VAR=x python3 -m …` y los heredocs complejos con redirección. Usar comandos
  simples o un script temporal dentro de `walking-skeleton/`, y borrarlo.
- Los mutantes propios **se desapuntan al editar el código** — pasó con C4, C9, C13, C24, y con M3 y
  M7 de `ejecutor-programador.toml`. Un mutante `NO_APLICADO` **no protege nada**: hay que reapuntarlo.
- El heredoc a `git commit -F` falla: usar un fichero de mensaje.

---

## 10 · Experimento A/B sobre `format` — INSTRUMENTO LISTO, CAMPAÑA NO EJECUTADA

**Estado: 2 inferencias válidas ejecutadas — las de `EXP-REPRO`, y sólo ésas.** El instrumento está
construido, auditado y congelado. La **campaña** sigue sin ejecutar: 0 de las 40 (o 20) inferencias
del protocolo A/B. Lo que la bloquea ya **no** es la memoria —el 2026-08-17 el umbral se alcanzó y se
sostuvo— sino la decisión `D-N3`, que es humana.

### Qué mide

Si restringir la **forma de la salida** (`format`: `"json"` en A, JSON Schema en B) cambia la
capacidad del razonador local para producir `sustituir` — el único campo que ningún modelo ha
generado nunca. **La única variable entre brazos es `format`**, verificado interceptando los diez
cuerpos HTTP reales.

### Benchmark de cinco casos, congelado

El criterio «cada caso inmune a toda transformación determinista» **se abandonó tras tres caídas**
—atajo léxico, docstring con dos frases, parámetro dentro del nombre— porque no convergía y producía
código irreal. Lo sustituye el criterio del CEO (2026-08-16):

> El conjunto debe impedir que una única heurística determinista simple explique de forma
> consistente los aciertos.

**142 reglas en 12 familias; ninguna explica más de 2 de 5 casos.** Los tres casos descartados se
conservan en `casos_descartados.py` como canarios y como evidencia de por qué cambió la metodología.

### Ficheros

`casos_benchmark.py` · `heuristicas_deterministas.py` · `superficie_ab.py` · `ab_format.py` ·
`test_protocolo_ab.py` · `casos_descartados.py` · `caso_v3.py`, todos en `medicion-razonador/`.
**`aislamiento.py` no se tocó** (decisión R1): su `clasificar()` lleva la respuesta del caso
histórico escrita literalmente y nunca fue genérica.

### Verificado

152 pruebas · `ruff` · `diff --check` · Quality Gate **PASS** (919+3, 8 contratos) · producto,
Bible, ADR y `decisiones` con **0 cambios** · SHA congelados de los cinco casos y de sus prompts.

Dos auditorías independientes encontraron **2 bloqueantes y 6 defectos importantes**, todos
corregidos: el evaluador reventaba con tipos inesperados y se llevaba seis mediciones; B se medía
referenciando ejecuciones A que nunca ocurrieron; `estado: completo` se declaraba sin haber medido
nada; `_residente` acertaba por subcadena y elegía el umbral equivocado.

### Bloqueo

**RAM.** El umbral de 1.400 MB rige solo antes de cargar el modelo (después basta 150), pero la
memoria disponible oscila entre **1.209 y 1.925 MB** y no lo sostiene. Medido: **el entorno de Claude
retiene ~1,1 GB de los 3,7 GB** de la máquina, más que Chrome. La primera ejecución compite contra el
modelo por la memoria que necesita para cargar.

**Medido, no supuesto — cuatro intentos, ~2,5 h de vigilancia, 0 inferencias ejecutadas:** la RAM
cruzó los 1.400 MB **una sola vez y de forma transitoria** (1.403 MB); al medir el arnés segundos
después había caído a 1.360 y abortó como `AMBIENTAL` sin enviar la petición — la guarda funcionó.
Nunca se sostuvieron 1.500 MB durante cinco muestras seguidas. Rango observado: **1.169–1.925 MB**.

**No es cuota** — no se observó ninguna señal de límite.

> ⚠ **CORRECCIÓN MEDIDA, 2026-08-17.** Este bloque concluía que *«el bloqueo es estructural para esta
> sesión, no transitorio»*. **Esa conclusión era prematura y queda refutada por ejecución:** al quinto
> intento, con la máquina en reposo, había 1.512 MB disponibles y las dos inferencias de `EXP-REPRO`
> se ejecutaron **desde dentro de una sesión de Claude Code**, sin cerrar nada y sin relajar ningún
> umbral. La recomendación de lanzar desde un terminal limpio **sigue siendo buena** —da más margen—,
> pero **no es un requisito**: cuatro fallos seguidos no demostraban imposibilidad, sólo que la
> ventana era estrecha. Es un caso de manual de conclusión por no-observación.

### `EXP-REPRO` no puede cambiar `n` por sí sola — corrección del CEO, 2026-08-17

La prueba de reproducibilidad **produce un dato, no una decisión**. Aunque las dos respuestas salgan
idénticas byte a byte, **no reduce `n=3` ni la campaña de 40 a 20 inferencias**: eso queda como
`D-N3`, en **`DECISION_REQUIRED`**, y lo decide el CEO.

Tampoco tiene autoridad sobre la estructura A/B, los criterios de validez, el criterio estadístico,
los casos ni el protocolo congelado.

### `EXP-REPRO` — **EJECUTADO el 2026-08-17. COMPLETADO y VALIDADO POR EL CEO.**

**Resultado: las dos respuestas son IDÉNTICAS byte a byte** (251 bytes cada una).

> **Acta del CEO, 2026-08-17.** Resultado recibido y validado. `EXP-REPRO` queda **COMPLETED** y las
> dos inferencias reales quedan como evidencia. **Las respuestas idénticas son un DATO, no una
> autorización para modificar `n`.** `D-N3` permanece **`DECISION_REQUIRED`**; **`n=3` permanece
> intacto**; `EXP-CAMPANA` permanece bloqueada y `ANALISIS-AB` permanece bloqueado por `D-CONF-B`.
> **Prohibido sin nueva orden:** inferencias adicionales, brazo B, `EXP-CAMPANA`, modificar `n=3`,
> commit, push y vigilancia de RAM. **El siguiente paso exige decisión humana explícita sobre `D-N3`.**

Ambas inferencias son reales, no ambientales: `clase: VALIDO`, HTTP 200, `respuesta_cruda`,
`tokens_entrada` y `tokens_generados` presentes en las dos.

| | rep. 1 | rep. 2 |
|---|---|---|
| clase | `VALIDO` | `VALIDO` |
| tokens entrada / generados | 775 / 74 | 775 / 74 |
| carga · ingesta · generación (s) | 20,94 · 234,69 · 51,74 | 0,63 · 0,61 · 43,62 |
| latencia de pared (s) | **307,57** | **44,89** |
| RAM disponible al empezar (MB) | 1.468 | 1.377 |
| umbral post-carga respetado | sí | sí |

**El entorno sí cumplió**, al quinto intento: 1.512 MB disponibles, swap libre 3.224 MB, load1 0,81 y
el modelo **no residente**. Durante la carga la RAM bajó a ~1.311 MB, muy por encima del umbral
post-carga de 150 MB. **No se relajó ningún umbral, ni se cerró ningún proceso del usuario.**

**Lo que este dato NO hace, y es lo importante:** **no reduce `n=3`** ni la campaña de 40 a 20
inferencias. `D-N3` sigue en **`DECISION_REQUIRED`** y lo decide el CEO. Tampoco toca la estructura
A/B, los criterios de validez, el criterio estadístico, los casos ni el protocolo congelado.

**Alcance de la evidencia:** un solo caso (**D**), un solo brazo (**A**), un solo modelo
(`qwen2.5:0.5b`), dos repeticiones. **No se extrapola** a los demás casos, al brazo B ni a
`qwen2.5:3b`.

**Observación registrada, no interpretada:** en ambas ejecuciones el veredicto de clasificación fue
`NO_VIABLE` — el modelo propuso la acción `verificar_patron`, que **no está en el catálogo**, y
**no produjo `sustituir`**. Es coherente con toda la campaña diagnóstica anterior, pero **dos
inferencias de un caso no son una medición de capacidad** y no se presentan como tal. **La autonomía
sigue en 0/7.**

**Artefacto:** `milestones/m3-entry/medicion-razonador/evidencia-exp-repro-qwen2.5-0.5b.json`
—los dos registros completos, con las respuestas crudas y los datos ambientales—. Es un fichero de
**evidencia**, no de instrumento: el benchmark, `ab_format.py` y el protocolo **no se tocaron**.

### El procedimiento, conservado por si hay que repetirlo

Dos inferencias: `qwen2.5:0.5b`, **caso D**, **brazo A**, repeticiones 1 y 2, comparadas byte a byte.
Con `temperature 0.0` y `top_k 1` la decodificación es greedy, así que **podrían ser idénticas** — y
entonces `n=3` no aportaría información y la campaña bajaría de 40 a 20 inferencias. **`n=3` no se
cambia hasta tener esa evidencia.**

> ⚠ **AVISO — corregido el 2026-08-17.** Una versión anterior de este bloque proponía
> `python3 ab_format.py --ejecutar --modelo qwen2.5:0.5b`. **Ese comando NO es `EXP-REPRO`: lanza la
> TANDA COMPLETA** —5 casos × 2 brazos × n=3 = **30 inferencias**—, que **no está autorizada**. Quien
> lo copiara ejecutaría una campaña entera creyendo hacer una prueba de dos.

`EXP-REPRO` son **exactamente dos** inferencias y se invocan a mano:

```bash
cd milestones/m3-entry/medicion-razonador
bash esperar_umbral.sh          # solo lee /proc; no baja umbrales
ollama ps                       # debe estar VACÍO si se quiere medir la primera carga
python3 ab_format.py            # sin --ejecutar: debe decir INERTE

PYTHONDONTWRITEBYTECODE=1 python3 -c "
import ab_format as F, casos_benchmark as B
c = B.POR_LETRA['D']
r1 = F.una_ejecucion('qwen2.5:0.5b', 'A', c, 1, 1)
r2 = F.una_ejecucion('qwen2.5:0.5b', 'A', c, 2, 2)
print('identicas:', r1['respuesta_cruda'] == r2['respuesta_cruda'])
"
```

**Cómo saber si hubo inferencia de verdad:** un registro con `omitido: true` y `clase: "AMBIENTAL"`
significa que **la guarda abortó antes de pedir** — no cuenta como inferencia ni como medición. Una
inferencia real trae `respuesta_cruda`, `tokens_entrada`, `tokens_generados` e `ingesta_s`.
**Sin `respuesta_cruda` no hubo inferencia.**

El procedimiento completo, con precondiciones y prohibiciones, está en
`entorno/control-plane/estado.json`, campo `procedimiento_lanzamiento`.

### Confusores registrados dentro del propio artefacto

Latencia **no comparable** entre brazos (caché de prompt) · `G` garantizada por construcción en B ·
omisiones ambientales **estructuralmente sesgadas hacia A** · una ventaja de B en `D` podría venir de
que el esquema impide por gramática el error de nomenclatura que A sí comete (por eso se registra
`args_claves_crudas`).

## 10.undecies · **F4 CERRADA** · ventana de trabajo autónomo (2026-08-26)

`DEC-ORCH-2` aprobada **desbloqueó F4**: `§20` la hacía depender de `F3 + §25.2`, y §25.2 era
`D-ORCH-2`. Ejecutada como bloque completo.

`entorno/control-plane/revisores.py` — contrato literal de `§8.2`: `Veredicto` con los cinco campos
y **sin campo `autoriza`, deliberadamente**; cuatro valores (`conforme` · `objeciones` · `rechazo` ·
`fuera_de_alcance`); **sin cita, no cuenta**.

**Los cuatro revisores, con su estado real** `[EJEC]`: `RevisorSubagente` **disponible** (usa los
agentes que ya existen) · `RevisorHumano` **disponible** (buzón asíncrono) · `RevisorLocal`
**sin capacidad** (previsto, no construido — INV-9) · `RevisorExterno` **bloqueado** (§25.1 + D24).

**`§8.3` · degradación, la garantía central:** sin revisor capaz la tarea pasa a
`WAITING_FOR_REVIEW` y **espera** — `veredictos emitidos: 0`. **No se autoaprueba jamás.** Las `AUTO`
siguen avanzando. El buzón humano solo lo responde una persona, y **sin cita se rechaza incluso al
CEO** `[EJEC]`.

**382 passed · 139 mutantes (35+18+19+15+13+11+14), 0 supervivientes, 0 NO_APLICADO · ruff PASS ·
Quality Gate FAIL 5/1139/3 (baseline) · `estado.json` INTACTO · 0 commits.**

### La ventana se cierra porque el trabajo autorizado se AGOTÓ, no por un fallo

F1–F4 completas · F5 **bloqueada** · cola `REVIEW` real **0 oportunidades**. Las cuatro
oportunidades restantes quedan en `estado.json → oportunidades_bloqueadas`:

| # | Qué | Por qué no se ejecuta |
|---|---|---|
| OB-1 | F5 · `RevisorExterno` | exige `D-ORCH-1` + **enmienda de D24** |
| OB-2 | auditor de garantías no resuelve rutas bajo `entorno/` | vive en `walking-skeleton/`: **fuera del perímetro** de `DEC-ORCH-2` |
| OB-3 | G-1 ×3 del gate | **deuda aceptada** por `DEC-G1-MANIFIESTO-TRAS-F4 = C` |
| OB-4 | `D-ORCH-6` | tocar la tabla de estados es decidir sobre el flujo de gobierno |

**No se inventó trabajo.** `siguiente_auto()` → `None` porque no hay trabajo real, no porque falle.

**SIGUIENTE PASO EXACTO:** desbloquear F5 (`D-ORCH-1` + enmienda D24), ampliar el alcance de `REVIEW`
por acta, o cerrar `D-ORCH-6`.

---

## 10.decies · **AUTONOMÍA DE DESARROLLO OPERATIVA** (2026-08-26)

`entorno/control-plane/ciclo_autonomo.py`. **AURA encadena tareas de código sin ningún acto humano
entre ellas**, dentro del alcance del acta.

`observar → diagnosticar → proponer → clasificar → [REVIEW] revisor + 4 criterios D22 → ejecutar →
probar → verificar efecto → registrar → siguiente → repetir`

### Demostrado `[EJEC]`

- **Cola real del repositorio:** 1 oportunidad verdadera (`_escritor`, resto del rewrite de P2 en
  `test_modelo_orquestador.py`) detectada, clasificada `REVIEW`, ejecutada y verificada. Cola agotada
  después: **0 pendientes**.
- **Encadenamiento:** 3 tareas, **`actos_humanos_durante_el_ciclo = 0`**, batería real en verde tras
  cada una, efecto comprobado **por definición** (`def _muerta_N(`), no por substring. Las funciones
  vivas quedaron intactas. Banco declarado y retirado.
- **Seis causas de parada** con prueba cada una: cola agotada · tarea `HUMAN` · verificación fallida ·
  agente no disponible · límite de seguridad · zona prohibida.

### Lo que NO puede, medido

`HUMAN` **detiene** el ciclo (probado con trabajo *posterior* a la parada, que no se ejecutó) · zona
prohibida nunca se toca · sin `REVIEW` habilitado no ejecuta nada · un ejecutor caído **no produce
éxito fingido** y no recurre a OpenCode, Codex ni Ollama (0 menciones en el módulo) · nada queda a
medias: si la verificación revienta, se revierte antes de propagar.

**361 passed · 111 mutantes (35+18+19+15+13+11), 0 supervivientes, 0 NO_APLICADO, 1 equivalente
demostrado por ejecución (`CA-M3`) · ruff PASS · Quality Gate FAIL 5/1139/3 (baseline) ·
`estado.json` INTACTO · 0 commits.**

**SIGUIENTE PASO EXACTO:** `estado.json → autonomia_de_desarrollo` lleva la acción ejecutable y el
trabajo real disponible (**hoy 0**: el plano no tiene código muerto pendiente). Ampliar el alcance
exige **otra acta**; AURA no puede, y está probado.

---

## 10.nonies · **`DEC-ORCH-2` APROBADA — `REVIEW` ENCENDIDO** (CEO, 2026-08-26)

**AURA ejecuta cambios de código sin acta individual, dentro de un alcance cerrado.** Es el primer
nivel de autonomía técnica del proyecto.

| | |
|---|---|
| **Habilitado por** | acta del CEO, registrada en el log real (`review_habilitado`, seq 1) |
| **Alcance** | `eliminar_codigo_muerto` · **solo** `entorno/control-plane/` · reversible y verificable |
| **Exige** | veredicto de revisor **distinto del proponente** que apruebe los 4 criterios de `D22` |
| **No alcanza** | D24 · Bible · ADR · roadmap · decisiones · producto · autoridad · ampliar su alcance |

### E2E real `[EJEC]` — sobre un fichero real del repositorio

```
1-2 OBSERVAR/DIAGNOSTICAR -> 1 hallazgo  _auxiliar_muerto linea 19 · fichero intacto: True
3-4 CLASIFICAR + AUTORIDAD -> habilitado=True  en alcance=True   (SIN acta individual)
      verificacion: pytest exit=0 -> SANO
5-6 EJECUTAR/VERIFICAR -> ejecutado=True revisor=auditor-consistencia efecto=True revertido=False
7 REGISTRAR · '_auxiliar_muerto' sigue: False · 'utilidad_viva' intacta: True
      eventos: review_habilitado · veredicto_emitido · propuesta_registrada ·
               propuesta_autorizada · cambio_aplicado    · log integro: True
8 CONTINUAR -> hallazgos restantes: 0
```

*(El sujeto de la validación se creó para ella y se retiró al terminar; queda declarado.)*

### Las cinco fronteras, medidas CON el nivel encendido

- **10 materias reservadas de `D22`** → rechazadas (ADR, Bible, D24, roadmap, alertas, tecnología,
  guardrails, rango 1, crear autoridad, promover propuesta).
- **4 acciones técnicas fuera del alcance** → rechazadas.
- **6 rutas de gobernanza y producto** → rechazadas **aunque la acción sí esté en alcance**.
- **AURA no amplía su propio alcance**: `aura`, `orquestador`, `auditor-consistencia` y `fable`
  rechazados por no ser autoridad humana.
- **El proponente no se revisa** (`1.1:94`).

**346 passed · 100 mutantes (35+18+19+15+13), 0 supervivientes, 0 NO_APLICADO · ruff PASS · Quality
Gate FAIL 5/1139/3 (baseline) · `estado.json` INTACTO · 0 commits.**

**Decisiones pendientes: solo `D-ORCH-6`** (`WAITING_FOR_HUMAN` inalcanzable, impacto nulo).

**SIGUIENTE PASO EXACTO:** ampliar el alcance de `REVIEW` a más acciones técnicas exige **otra acta**
—AURA no puede—. Fuera de este DP siguen `D-ORCH-1`+enmienda D24 (F5) y `D-ORCH-6`.

---

## 10.octies · `D-ORCH-2` — nivel `REVIEW` **construido** (2026-08-26)

**346 passed · 100 mutantes (35+18+19+15+13), 0 supervivientes, 0 NO_APLICADO · ruff PASS · Quality
Gate FAIL 5/1139/3 (baseline) · `estado.json` INTACTO · 0 commits.**

### La respuesta se parte en dos, y por qué

**A · Determinado por contrato.** El **CTO es Fable (IA)** (`1.1:94`) y `D22` **ya le delegó** la
aprobación de capítulos con cuatro criterios. **Delegar en un agente no es inédito aquí.**
⚠ **El `DP §10.3` afirma que «D22 delegó en un CTO humano». ES FALSO** `[EJEC]` — firmas de
delegación D22 en `5.1`, `5.2`, `5.3`, `5.5`, `5.6`. Corregido en `DEC-ORCH-2`.

**B · Derivable sin autoridad nueva:** el **mecanismo** — clasificar, pedir veredicto a un revisor
**distinto del proponente** (`1.1:94`, «no aprueba su propio trabajo»), aplicar los 4 criterios de
`D22`, registrar. **Construido.**

**C · Concesión nueva, NO tomada:** que ese veredicto **sustituya el acta** para ejecutar.
`ADR-0003:33`: *«nunca automáticamente»*. Y `D22` delega sobre **documentos**, no sobre ejecución de
código.

### Estado: mecanismo completo, `REVIEW_HABILITADO = False`

`entorno/control-plane/review.py`. Cuatro puertas antes de tocar nada: materia reservada · nivel
habilitado · alcance del acta · veredicto sin objeciones. **Encenderlo es una línea de acta, no de
código.**

**E2E `[EJEC]`:** sobre el repo real → rechazado. Con acta temporal → ejecutó, revisor independiente,
efecto verificado, log íntegro. Objeción → **no ejecuta**. Materia reservada con el nivel encendido →
**rechazada**. Auto-revisión → **rechazada**.

**SIGUIENTE PASO EXACTO: `DEC-ORCH-2`** está en `estado.json → decisiones_pendientes` con sus cinco
puntos. Es lo único que separa a AURA de ejecutar trabajo técnico sin acta caso a caso.

---

## 10.septies · **AUTOCONSTRUCCIÓN GOBERNADA** + `D-ORCH-2` parcial (2026-08-26)

**Informe:** [`milestones/m3-entry/CIERRE-AUTOCONSTRUCCION.md`](milestones/m3-entry/CIERRE-AUTOCONSTRUCCION.md)

**AURA ya modifica su propio código, bajo acta.** Ciclo de 8 pasos en
`entorno/control-plane/autoconstruccion.py`:

`OBSERVAR → DIAGNOSTICAR → PROPONER` **sola** · `AUTORIZAR` **exige acta humana** ·
`EJECUTAR → VERIFICAR → REGISTRAR → CONTINUAR` solo después.

**E2E real `[EJEC]`:** detectó la función muerta `_sin_usar` en su propio `orquestador.py`, la
propuso, **fue rechazada sin acta**, se autorizó con acta del CEO, la eliminó, verificó con la
batería real (`pytest exit=0`) y registró. Árbol sano, log íntegro.

**Reversible por construcción:** si la verificación falla, el fichero vuelve a como estaba.

**Fronteras duras, con mutante cada una:** gobernanza (D24/Bible/ADR/roadmap/decisiones) fuera
**aunque el CEO lo autorice** — cambiarla es un acto por acta, no una tarea que se encargue a un
ejecutor. Producto fuera. Zona de escritura: **solo `entorno/control-plane/`**.

**331 passed · 87 mutantes (35+18+19+15), 0 supervivientes, 0 NO_APLICADO · ruff PASS · Quality Gate
FAIL 5/1139/3 (baseline) · `estado.json` INTACTO tras mutación, baterías y gate · 0 commits.**

### `D-ORCH-2` — implementado lo decidido, registrado lo que no

**Decidido e implementado (C5):** `Veredicto` **sin campo de autorización** —tenerlo permitiría que
un modelo lo rellenase—, `autoriza()` constante a `False`, no requisito para operar, y usa los
revisores que **ya existen** en `.claude/agents/`. Base: `1.1:93` (autoridad no delegable) y `1.1:85`
(el silencio no aprueba).

**No decidido → `DECISION_REQUIRED`:** si un veredicto puede ser *condición previa* para ejecutar una
tarea `REVIEW`. `REVIEW` no existe en ADR-0003 y crearlo eleva la autonomía: solo el CEO.

### OpenCode — cerrado, no reabrir

Desinstalado y verificado: **ausente · 0 residuos · 0 procesos · 0 credenciales** `[EJEC]`.
Conclusión ya registrada: exige clave de proveedor → **choca con D24**, que no se modifica.

**SIGUIENTE PASO EXACTO:** `D-ORCH-2` (crear o no el nivel `REVIEW`) es lo único que bloquea que AURA
autorice trabajo técnico sin acta caso a caso. Después: `D-ORCH-1`+enmienda D24 (F5), `D-ORCH-6`.

---

## 10.sexies · `D-ORCH-3` RESUELTA · failover Claude → OpenCode (2026-08-26)

**Informe:** [`milestones/m3-entry/CIERRE-D-ORCH-3-FAILOVER.md`](milestones/m3-entry/CIERRE-D-ORCH-3-FAILOVER.md)

**`AUTO` ya no está vacío.** Derivado del catálogo verde de `permissions.py` + `DP §10.2`, filtrando
por **efecto lectura**: `ejecutar_pruebas` · `verificar_calidad` · `auditar_garantias` ·
`diagnosticar_estado`. **Ninguna modifica nada.** `REVIEW` sigue vacío (no existe hasta `D-ORCH-2`).

**Failover gobernado**, no ciego: solo `AGENTE_SIN_CUOTA` y `AGENTE_NO_DISPONIBLE` relevan.
`TAREA_FALLIDA`/`SIN_EFECTO`/`TIMEOUT` **no** — relevar ahí oculta el fallo rotando agentes. Cadena
finita `claude → opencode → fin`. Nueve campos de trazabilidad en **todos** los intentos.

**AURA no cree al agente:** verifica el efecto. Un proceso que dice «informe generado correctamente»
sin crearlo da `NO_VERIFICADO` y la tarea queda `FAILED`.

**308 passed · 72 mutantes (35+18+19), 0 supervivientes, 0 NO_APLICADO · ruff PASS · Quality Gate
FAIL 5/1139/3 (baseline) · `estado.json` INTACTO tras batería y gate · 0 commits.**

### ⛔ BLOQUEO REAL medido — OpenCode exige clave de proveedor

`opencode run` → *«Google Generative AI API key is missing»* `[EJEC]`. **D24 prohíbe claves de
terceros.** El mecanismo de failover funciona y está probado; lo que no puede es **razonar**.
Verificado del ciclo externo: instalar · verificar · retirar · limpiar · **ausencia**. Fijado en
`agentes.BLOQUEO_CONOCIDO`. **No redescubrirlo.**

### Continuidad lista

`agentes.continuidad()` encadena la cola `AUTO` sin intervención, **no inventa tareas**, es finita y
**se detiene dejando el motivo escrito** si ningún agente puede seguir. E2E real: 3 tareas
encadenadas, efecto verificado en las 3, tarea `HUMAN` intacta.

**SIGUIENTE PASO EXACTO:** decidir cómo dota AURORA de capacidad de razonamiento al agente
secundario sin violar D24 —es la única pieza que falta para la continuidad nocturna real—, y
`D-ORCH-2` (F4) · `D-ORCH-1`+enmienda D24 (F5) · `D-ORCH-6`.

---

## 10.quinquies · `DP-DEVELOPMENT-ORCHESTRATOR` **F2 + F3 IMPLEMENTADAS** · F4/F5 aisladas (2026-08-26)

**Informe:** [`milestones/m3-entry/CIERRE-F2-F3-DEVELOPMENT-ORCHESTRATOR.md`](milestones/m3-entry/CIERRE-F2-F3-DEVELOPMENT-ORCHESTRATOR.md)

### Estado verificado

- Control Plane **279 passed** · Communication Plane **180/5 skipped** · agente-externo **20** ·
  `ruff` **PASS** · Quality Gate **FAIL 5/1139/3** (baseline, sin relación con este bloque).
- **Mutación: F1 35/35 · F2-F3 18/18 — 53 mutantes, 0 supervivientes, 0 NO_APLICADO.**
- **0 commits · 0 push.** `HEAD` sigue en `790fafc`. OpenCode/Codex ausentes. D24 intacta.

### `estado.json` — RECUPERACIÓN PARCIAL. Leer antes de fiarse del fichero

Búsqueda agotada `[EJEC]`: `git fsck --unreachable`, `git log --all`, `.tmp`, `find` en `$HOME`,
transcripts de todas las sesiones y subagentes.

| | |
|---|---|
| Conteos originales verificados | `trabajo_completado` **51** · `tareas_AUTO` **6** · `propuestas` **14** |
| **Restaurado literal** | **9 de 51**: `CP-1…CP-5`, `EXP-1`, `EXP-REPRO`, `DP-ORCH-DISENO`, `DP-CP-DISENO` |
| Reconstruido del CHECKPOINT | `defectos`: `DEF-CUERPO-LIBRE`, `DEF-FLAKY-P2` |
| Ids sin contenido | las 6 `tareas_AUTO` (listadas en `perdida_de_datos`) |
| **PERDIDO** | 42 entradas · contenido de `tareas_AUTO` · 14 `propuestas` |

**`tareas_AUTO` NO se recreó**: hay ids pero no contenido, y fabricarlo viola D34/INV-9 y la orden de
no alterarla. **Si aparece una copia, restaurarla es preferible a lo que hay.**

### Blindaje permanente — el incidente ya no puede repetirse

`conftest.py` `autouse` con **dos capas**: intercepción en `guardar()` (falla en el acto, nombra la
prueba culpable) y huella `sha256` por prueba que **restaura el fichero** si cambió. Ambas
verificadas ejecutando.

### F2 y F3 construidas · **el orquestador arranca sin nada que ejecutar, y es lo correcto**

`entorno/control-plane/orquestador.py` + `politica-orquestador.toml`. C3 bucle finito · C4
WorkerAdapter · C6 política versionada · C7 presupuesto.

**El catálogo `AUTO` está VACÍO a propósito.** `§25.3`: *«sin lista aprobada, todo es HUMAN»*.
`REVIEW` vacío porque **el nivel no existe** hasta `D-ORCH-2`. Rellenarlos sería conceder autonomía
por la puerta de atrás. El E2E demuestra las dos mitades: el flujo real se detiene en la decisión, y
bajo una política hipotética en `tmp` llega al borde de la ejecución y para en la puerta.

### F4 y F5 — BLOQUEO CONTRACTUAL DEMOSTRADO. No reabrir sin decisión

- **F4** ← `§25.2` `D-ORCH-2`: crear el nivel `REVIEW`, que **no existe** en ADR-0003 y *«solo el CEO
  puede conceder»*. Sería **crear autoridad nueva**.
- **F5** ← el `§20` la marca **«Bloqueada»**: exige **enmienda de D24**.

`D-ORCH-3` sigue abierta pero **no bloquea F2/F3**: su único efecto es el catálogo vacío.

### Tercera auditoría independiente — 3 GRAVES, todos ciertos

| # | Hallazgo | Estado |
|---|---|---|
| **G1** | `guardar()` no validaba `tareas`: escribir el dict a mano y persistir fabricaba cualquier estado | **CERRADO** `F1-M31/M32` |
| **G2** | `FAILED`→`WORKING`→`COMPLETED` en 3 llamadas sin autoridad humana | **ACOTADO** — se cierra con **A12**, que es de F4/F5. Hoy queda **marcado** `creada_sin_origen` (`F1-M33/M34`) |
| **G3** | El destino de `guardar()` quedaba horneado en la firma al importar: fallaba **el patrón que se usa para protegerse** | **CERRADO** `F1-M35` |

**Límite estructural, dicho claro:** dentro de un proceso, el código puede tocar su memoria. La
garantía fuerte no es el dict sino el **log append-only de F1**. G1 añade el **borde de
persistencia**: lo que llega a disco lleva los campos que solo pone el gobierno.

### `D-ORCH-6` registrada — `WAITING_FOR_HUMAN` inalcanzable

Contradicción **dentro del propio DP**: `§139` dice que el vocabulario *«se conserva íntegro»* y
`§351` le da salidas, pero ningún estado lo declara destino. Sin menciones en `adr/`, `docs/` ni
`decisiones/`. **Impacto hoy: ninguno** — F2/F3 no lo usan. Registrada en
`estado.json → decisiones_pendientes`.

**SIGUIENTE PASO EXACTO:** decisión del CEO sobre `D-ORCH-2` (desbloquea F4), `D-ORCH-1` + enmienda
de D24 (desbloquea F5), `D-ORCH-3` (llena el catálogo `AUTO` y hace que el orquestador ejecute algo)
y `D-ORCH-6`. **Sin ellas no queda trabajo autorizado en este DP.**

---

## 10.quater · `DP-DEVELOPMENT-ORCHESTRATOR` **F1 IMPLEMENTADA** (2026-08-26)

**Autorizado por el CEO** como bloque vertical completo. **Solo F1 = C1 + C2.** `§20`: *«Depende de:
nada»*; `§5`: *«se pueden construir, probar y usar sin resolver ninguna de las decisiones pendientes
de §25»*. **F2–F5 siguen bloqueadas** por `D-ORCH-1…4`, que son decisiones del CEO.

**Informe completo:** [`milestones/m3-entry/CIERRE-F1-DEVELOPMENT-ORCHESTRATOR.md`](milestones/m3-entry/CIERRE-F1-DEVELOPMENT-ORCHESTRATOR.md)

### Los tres defectos del §10.ter punto 3 están CERRADOS

Aquellos *«tres defectos del Control Plane, medidos»* que *«muerden el día que haya orquestador»*:

| Defecto | Cierre | Evidencia |
|---|---|---|
| **P2** sin lock | `flock` exclusivo sobre leer-modificar-escribir | dos procesos reales, 0 escrituras perdidas `[EJEC]` |
| **P3** sin event log | `eventos.jsonl` append-only, `seq` monotónico, `fsync`, `sha256` encadenado | `estado.json` borrado y reconstruido idéntico `[EJEC]` |
| **P4** `COMPLETED → WORKING` | tabla `TRANSICIONES` de `§6` + autoridad y causa, en **las dos** rutas | `TransicionInvalida` ante 6 intentos, incluido el del CEO `[EJEC]` |

**Un solo fichero de producción tocado:** `entorno/control-plane/control_plane.py`. **Cero** ficheros
de producto. `control_plane.py` sigue con **0** referencias a `aura_skeleton`.

### Estado verificado — 2026-08-26

- Control Plane **242 passed** (44 pruebas nuevas de F1) · Communication Plane **180 passed · 5
  skipped** · agente-externo **20 passed** · `ruff` **PASS** en los tres.
- **Mutación:** `walking-skeleton/mutaciones/f1-orquestador.toml` — **30 detectados · 0 supervivientes
  · 0 NO_APLICADO**. Se ejecuta con `--raiz ../entorno/control-plane`.

### La auditoría independiente encontró DOS PUERTAS ABIERTAS. Ambas cerradas.

**No saltarse esto al retomar: es la lección más cara del bloque.** La primera versión de F1 pasó 228
pruebas, 21 mutantes sin supervivientes y una demostración de A5 que parecía exhaustiva — y tenía
**dos rutas al estado sin gobernar**. El cierre llegó a afirmar *«ambas rutas están gobernadas»*
cuando eran **cuatro**. Era `declarado ≠ real` dentro de la herramienta que vigila el trabajo.

| # | Hallazgo | Cerrado por |
|---|---|---|
| **H1 GRAVE** | `completar_tarea()` cerraba una tarea en `DECISION_REQUIRED` **sin acto humano** — A5 incumplido | `F1-M22` |
| **H2 GRAVE** | prueba **decorativa** (`A or B` con `B` comparando solo claves) que ocultaba una divergencia real con la tabla de `§6` | `F1-M25` |
| **H3** | el atajo de idempotencia se evaluaba antes del control de autoridad humana | `F1-M24` |
| **H4** | `registrar_evento` crudo fabricaba estado saltándose el gobierno | `F1-M23` |

**Por qué la mutación no los vio:** los mutantes degradan código **que existe**; ninguno puede
degradar un control **que no está escrito**. La mutación dice si lo construido tiene red, **no qué
falta por construir**. Eso solo lo da un lector independiente preguntando «¿por dónde más se entra?».

**Las cuatro rutas al estado** son `transicion()`, `fijar_estado_tarea()`, `completar_tarea()` y
`registrar_evento(tipo="estado_de_tarea")` —esta última, prohibida—. Todas comparten
`validar_transicion`. **Si se añade una quinta, tiene que entrar por ahí.**

**A5 reverificado por 16 vías del código, 0 abiertas** `[EJEC]`.

### La 2.ª auditoría encontró que MI CORRECCIÓN abrió otro GRAVE

Al gobernar `completar_tarea` añadí la regla «crear no es transicionar» con un `return` que saltaba
también la tabla: **cualquier id nunca visto podía crearse en `COMPLETED`**. Lo delató la asimetría
—`transicion()` sí lo rechazaba— y mi barrido de A5 no lo vio porque **las 10 vías partían de una
tarea que ya existía**. Cerrado con `ESTADOS_CREABLES` (`WAITING_FOR_NEXT_TASK`, `WORKING`,
`WAITING_FOR_ENVIRONMENT`, `WAITING_FOR_QUOTA`, `FAILED`) · mutantes `F1-M27/M28/M29`.

**La garantía que cierra la clase entera:**
`test_ninguna_funcion_FUERA_de_las_gobernadas_cambia_el_estado_de_una_tarea` **no enumera rutas**:
recorre el módulo entero. Enumerar a mano ya falló dos veces. Mutante `F1-M30` planta una quinta
ruta y el detector la encuentra.

### ⚠ PÉRDIDA DE DATOS — `entorno/control-plane/estado.json` (2026-08-26)

**Leer antes de fiarse de ese fichero.** La primera versión de ese detector llamaba a toda función
pública con el estado, incluida `guardar()`, cuyo destino por defecto **es el `estado.json` real**.
Lo sobrescribió. No hay copia: el directorio es *untracked* y no existe en `main` `[EJEC]`.

- **Reconstruido** desde este CHECKPOINT (líneas 1842 y 1899): `DEF-CUERPO-LIBRE`, `DEF-FLAKY-P2`.
- **PERDIDO y NO fabricado:** `trabajo_completado` (**49 entradas**), `tareas` (6), `aprobaciones`,
  `decisiones_pendientes`, `git`, `verificacion`, `sesion_claude`.

El propio `estado.json` lleva un bloque `perdida_de_datos` con causa, inventario y procedencia.
**No inventar lo perdido**: D34 e INV-9. Si aparece una copia, restaurarla es preferible a lo
reconstruido.

**Prevención verificada** `[EJEC]`: el `md5` de `estado.json` ya no cambia al correr la batería ni el
arnés de mutación, y `test_el_detector_de_rutas_NUNCA_escribe_en_el_estado_real` fija el contrato.

### La 3.ª auditoría NO se ejecutó — límite de gasto

Lancé una tercera ronda acotada a `ESTADOS_CREABLES` y **murió con «You've hit your monthly spend
limit»** (el modo de fallo del `§11`). Ejecuté yo sus 7 puntos —encontrando dos defectos reales—
pero **eso es autoauditoría**. Las dos rondas independientes encontraron 4 defectos que yo había
dado por buenos. **`ESTADOS_CREABLES` sigue sin revisión independiente: es lo primero que debe
auditarse al reanudar.**

### Pendiente de decisión del CEO — `WAITING_FOR_HUMAN` inalcanzable

Al restaurar la tabla literal de `§6` quedó visible que **`WAITING_FOR_HUMAN` tiene salidas pero
ningún estado lo declara como destino**: es inalcanzable desde el flujo. La implementación lo había
añadido a `WORKING` **sin declararlo**, y eso se ha revertido. **No se enmienda por cuenta propia**:
tocar la tabla del DP es decidir sobre el flujo de estados. Opciones: (a) añadirlo como destino de
`WORKING`, (b) retirarlo del vocabulario, (c) dejarlo reservado para fases posteriores. **Hoy no
bloquea nada.**
- **Quality Gate del producto: FAIL 5 / 1139 passed / 3 skipped — IDÉNTICO al baseline previo.** Los 5
  son los ya clasificados (G-1 ×3 deuda aceptada, `test_garantias_vigentes` defecto del auditor,
  `test_limite_reintentos` su consecuencia). **F1 no movió ni una prueba del producto.**
- **Criterios de `§22`: A1, A2, A3, A4 y A5 CUMPLIDOS `[EJEC]`.** A4 con `SIGKILL` **real** sobre un
  proceso lanzado, no simulado: el log quedó íntegro (el `fsync` cumplió), el `flock` se liberó solo
  al morir el proceso, y la tarea quedó `FAILED`. A6–A12 dependen de F2–F5: **fuera de F1**.
- **0 commits · 0 push.** OpenCode y Codex ausentes. D24 intacto, sin red, sin claves.

### Tres pruebas cambiaron de veredicto — **premisa superada, no debilitada**

Dos de ellas anunciaban por escrito su propio final. Se reescribieron como la garantía que protege
el cierre; borrarlas o dejarlas midiendo el defecto habría sido pedirle al código que **no** hiciera
lo que se le encargó:

- `test_p4_hoy_se_puede_pasar_de_completed_a_working_sin_validacion` → `test_p4_ya_NO_se_puede_...`
- `test_p2_dos_escritores_concurrentes_pierden_una_escritura` → `test_p2_la_via_GOBERNADA_conserva_...`
  **más** `test_p2_la_primitiva_CRUDA_...` como caso de control. Esto **cierra `DEF-FLAKY-P2`**: la
  aserción vieja medía el accidente («se pierde exactamente una»), que depende del planificador; la
  nueva mide la garantía, que no.
- `test_los_estados_del_modelo_respetan_el_vocabulario_ya_aprobado`: medía que `WAITING_FOR_REVIEW`
  estaba **pendiente**. F1 lo añadió — es el único estado que `§6` autoriza.

### Lo que NO debe rehacerse

- **No volver a analizar P2/P3/P4.** Cerrados y con mutantes que lo protegen.
- **No re-ejecutar la mutación de F1** salvo que se toque `control_plane.py`; y si se toca, sus 21
  mutantes siguen siendo válidos y deben seguir muriendo.
- **No empezar F2–F5.** Requieren `D-ORCH-1` (F5/revisor externo), `D-ORCH-2` (F4), `D-ORCH-3` (F3),
  `D-ORCH-4` (F2). **Son del CEO.**

**SIGUIENTE PASO EXACTO:** esperar decisión del CEO sobre `D-ORCH-1…4`. Sin ellas, `DP-DEVELOPMENT-
ORCHESTRATOR` no puede avanzar más allá de F1, y `§5` ya advierte que F1 *«es el 80 % del valor»*.

---

## 10.ter · AURORA Development Orchestrator — **FASE DE DISEÑO CERRADA. NADA IMPLEMENTADO.**

Encargo del CEO del 2026-08-17: diseñar —sin construir— la infraestructura para que el ejecutor y el
revisor continúen trabajo autorizado sin que Mauricio haga de mensajero.

**Entregado:** `milestones/m3-entry/DP-DEVELOPMENT-ORCHESTRATOR.md` (1.079 líneas, 35 secciones) y
`entorno/control-plane/test_modelo_orquestador.py` (39 pruebas del **modelo conceptual**, en verde;
105 junto a las del Control Plane; `ruff` PASS). **Cero líneas del orquestador escritas.** Ningún
demonio, ninguna API externa, ningún paquete instalado, ninguna inferencia ejecutada.

### Lo que la investigación descubrió, y no era lo esperado

1. **El obstáculo para un revisor externo NO es local-first.** `adr/0001:41` autoriza expresamente la
   nube para *«consultar modelos de IA»* y D37 dice *«local-first no es local-only»*. El choque real es
   entre la cláusula final de **D24** (sin ámbito) más `CHECKLIST:237` (enunciado plano) y esos dos
   textos. **No hay lectura que satisfaga los cuatro a la vez** → `D-ORCH-1`, del CEO.
2. **Ningún modelo puede aprobar nada, y ya estaba decidido:** `1.1:93` — *«su autoridad de aprobación
   no es delegable a ningún agente»*; `1.1:85` — *«el silencio no constituye aprobación»*.
3. **Tres defectos del Control Plane, medidos:** sin lock (dos escritores pierden una escritura, y está
   **demostrado por ejecución**), sin event log, y `fijar_estado_tarea` no valida el estado previo
   (permite `COMPLETED → WORKING`). Hoy no muerden porque solo hay un escritor; **muerden el día que
   haya orquestador**.
4. **`--max-turns` no existe** en Claude Code 2.1.233, pese a estar documentado. Detectado ejecutando.
   Sí existen `--session-id`, `--max-budget-usd`, `--json-schema` y `claude agents --json`.
5. **La cuota sigue sin ser observable.** `usage_known = false` se mantiene. Lo que sí es observable es
   el **coste por invocación** — presupuesto operacional, que no es lo mismo que conocer cuota.

### Auditoría independiente: 0 BLOQUEANTES · 3 IMPORTANTES · 1 MENOR · 2 DEUDA

Los tres IMPORTANTES **están corregidos** en el DP. El más serio lo encontró el auditor, no el autor:
**el Worker se autocertificaba** —nadie contrastaba que su evidencia cumpliera el criterio—. Cerrado en
§14.bis exigiendo que el criterio de finalización sea **un comando verificable, fijado antes de
invocar y ejecutado por el Orchestrator, no por el Worker**. Si un criterio no es expresable como
comando, la tarea **no es automatizable**.

### Recomendación

**Fase 1 y parar:** event log, lock y transiciones gobernadas. Cierra defectos reales, **no depende de
ninguna decisión pendiente** y vale aunque nunca se apruebe el resto. **El revisor por defecto NO debe
ser un proveedor externo**, sino un subagente ya existente o el propio CEO.

### Pendiente del CEO — nada se construye sin esto

`D-ORCH-1` alcance de D24 · `D-ORCH-2` nivel `REVIEW` (no existe en ADR-0003) · `D-ORCH-3` qué entra en
`AUTO` (sin lista, todo es `HUMAN`) · `D-ORCH-4` si se construye · `D-ORCH-5` levantar
`CHECKLIST:235`, que hoy prohíbe iniciar cualquier incremento nuevo.

**La autonomía de AURORA sigue en 0/7.** Esto es infraestructura de desarrollo, no capacidad del
producto.

## 10.bis · Development Control Plane — `entorno/control-plane/`

Estado del **trabajo** legible por máquina, para continuar entre sesiones sin copiar mensajes.
**No es AURORA y no le da ninguna capacidad**: no importa un solo módulo del producto y dos pruebas
lo verifican. **0/7 sin cambios.**

No duplica este checkpoint: aquí está la autoridad narrativa, allí el estado observado. Si
discrepan, **manda este documento**.

**Sobre la cuota, y esto es lo importante:** se investigó qué expone Claude Code. `policy-limits.json`
son restricciones de política; `history.jsonl` da marcas de actividad, no consumo, y **no registra
sesiones en segundo plano**. No existe señal de cuota restante. Por eso `usage_known = false` y ambas
ventanas arrancan en `UNKNOWN`. **El módulo nunca afirma cuánto queda**, y una prueba falla si aparece
cualquier insinuación de porcentaje. La única evidencia real de agotamiento es el error al fallar
—observado: varios subagentes murieron con «monthly spend limit»—, que es posterior al hecho.

Regla aplicada: **desconocer la cuota no es tenerla** — con `UNKNOWN` se permite trabajo barato y se
rechaza el caro.

---

## 11 · CUOTA — **USO ADICIONAL BLOQUEADO, CAPACIDAD INCLUIDA DISPONIBLE (2026-08-17)**

> **Esta es la sección que debe leer primero quien retome el trabajo.**
>
> **CORREGIDA el 2026-08-17 con evidencia visual del CEO.** La primera redacción de esta sección
> decía «PARADA POR CUOTA» e inducía a leer que Claude Code estaba agotado. **Es falso.** Lo que
> está agotado es el **uso adicional de pago** (USD 21,84 sobre un límite de USD 20,00). La
> **capacidad incluida del plan sigue disponible**: sesión 26 % usada, semanal 56 % usada, ambas
> DISPONIBLES.
>
> La evidencia histórica del mensaje se conserva íntegra abajo — no se borra, se reinterpreta.

### 11.1 · La evidencia, literal

| Campo | Valor |
|---|---|
| `tipo` | `QUOTA_LIMIT_OBSERVED` |
| `ventana` | `MONTHLY_SPEND_LIMIT` |
| `timestamp` | `2026-08-17T21:03:55.413Z` |
| `mensaje` | `You've hit your monthly spend limit · raise it at claude.ai/settings/usage?from=cc_cli_limit_message` |
| tarea detenida | `AUDITORIA-DP-CP` — auditoría independiente de `DP-COMMUNICATION-PLANE-AURORA` |
| último estado persistente | `DECISION_REQUIRED` |
| acción registrada | `WAITING_FOR_QUOTA` |
| `SHORT_4H30` | `UNKNOWN` — **no observada** |
| `WEEKLY` | `UNKNOWN` — **no observada** |
| renovación | `UNKNOWN` — el producto no la publica |

**Artefacto verificable:** el mensaje aparece en el transcript de la sesión
`d6cb894c-ec22-4d75-a47b-ee70a683405a.jsonl` con esa marca de tiempo. No se dedujo: se leyó.

### 11.2 · Lo que esa evidencia NO decía

Del mensaje `monthly spend limit`, por sí solo, **no se deduce nada** sobre las otras dos ventanas.
Son tres límites independientes. La lectura correcta llegó después, con la evidencia visual (§11.7):
el mensaje significaba **«uso adicional de pago agotado»**, no «Claude Code agotado».

Siguen prohibidas, y el código las impide:

1. **Calcular una fecha de renovación no observada.** Del límite mensual: `renovacion: UNKNOWN`.
2. **Afirmar un porcentaje que nadie leyó.** `observar_cuota()` no contiene ninguno, y una prueba
   falla si aparece.
3. **Extrapolar.** Los porcentajes de §11.7 son una **instantánea que caduca**: un contador que se
   mueve solo. `usage_known` sigue en `false` porque **Claude Code no los publica** — los leyó un
   humano en una página web, y el agente no puede consultarlos por su cuenta.

El error inverso también está cerrado: **una renovación del límite mensual no renueva las otras
dos**, y hay una prueba que lo fija (`test_la_renovacion_del_limite_mensual_no_renueva_las_otras_dos`).

### 11.3 · Qué se cambió en el Control Plane por esto

`entorno/control-plane/control_plane.py` modelaba **dos** ventanas. Ahora modela **tres**:

```
VENTANAS_CUOTA  = ("SHORT_4H30", "WEEKLY", "MONTHLY_SPEND_LIMIT", "UNKNOWN")
CLAVES_DE_CUOTA = ("rolling_window", "weekly", "monthly_spend")
```

- `registrar_bloqueo_de_cuota()` marca **solo** la ventana observada y añade `tipo`, `renovacion`
  y `estado_previo` (para no perder el `DECISION_REQUIRED` que la cuota interrumpió).
- `migrar_cuota()` permite cargar estados escritos antes de existir la tercera ventana: la rellena
  como `UNKNOWN`, **nunca** como `NORMAL`.
- `puede_empezar()` y el handoff miran las tres.
- Ciclo: **RED 12 fallos → GREEN → 117 pruebas en verde → ruff PASS.** Sin Quality Gate completo
  (orden del CEO: no gastar cuota).

### 11.4 · QUÉ QUEDA PENDIENTE — en este orden

| # | Pendiente | Estado | Quién decide |
|---|---|---|---|
| 1 | **Recoger/repetir la auditoría independiente** de `DP-COMMUNICATION-PLANE-AURORA` | `WAITING_FOR_QUOTA` — **NO es COMPLETED**: el auditor murió antes de entregar | agente, cuando haya cuota |
| 2 | **D-CP-1** — transporte hacia el segundo agente (Codex CLI local / API OpenAI con enmienda de D24 / humano) | `DECISION_REQUIRED` | CEO |
| 3 | **D-CP-2** — autorizar GREEN del canal | `DECISION_REQUIRED` | CEO |
| 4 | **D-CP-3** — identidad declarativa o firmada | `DECISION_REQUIRED` | CEO |
| 5 | **Solo después**, si procede, GREEN del Communication Plane | bloqueado por 1–4 | CEO |

**El punto 1 no lo desbloquea el CEO: lo desbloquea la cuota.** Los puntos 2–4 sí. Se pueden
resolver en paralelo, pero **ninguno autoriza GREEN por sí solo**.

Lo último que el auditor alcanzó a examinar antes de morir fue la **Sección E**: si el campo libre
`cuerpo` de un mensaje puede otorgar de facto la autoridad que el esquema prohíbe. **Es una pregunta
abierta y real** sobre si la garantía «el canal transporta, no autoriza» es efectiva o cosmética.
Quien retome la auditoría **debe empezar por ahí**.

### 11.5 · Estado congelado — nada de esto cambió

- `DP-COMMUNICATION-PLANE-AURORA.md` → **PROPUESTO**. `DP-DEVELOPMENT-ORCHESTRATOR.md` → **PROPUESTO**.
- **No existe `communication_plane.py`.** Las 35 pruebas RED siguen fallando, todas por
  `ModuleNotFoundError: communication_plane`, que es exactamente el motivo correcto.
- `n = 3` intacto (`ab_format.py:68 · REPETICIONES = {"qwen2.5:0.5b": 3, "qwen2.5:3b": 1}`).
- `D-N3` sigue `DECISION_REQUIRED`. `EXP-CAMPANA` y `ANALISIS-AB` siguen bloqueadas.
- Codex **NO integrado**. Sigue siendo solo un candidato a transportista dentro de `D-CP-1`.
- Autonomía de AURORA: **0/7**.
- Sin commit, sin push.

### 11.6 · Regla permanente de parada por cuota (CEO, 2026-08-17)

Si Claude Code queda bloqueado por su cuota: **no intentar consumir más**, dejar el estado
persistente completo, dejar un handoff autosuficiente y **detenerse**. En particular: **no lanzar
agentes** para «aprovechar» lo que quede — cada agente es gasto y el límite ya se observó.

### 11.7 · CORRECCIÓN — evidencia visual del CEO, página oficial de uso del plan Pro

| Ventana | Clave | Observado | Estado | Renovación |
|---|---|---|---|---|
| Sesión actual (~4 h 30) | `rolling_window` | **26 % usado** | **DISPONIBLE** | ~4 h 8 min desde la lectura (relativo) |
| Límite semanal, todos los modelos | `weekly` | **56 % usado** | **DISPONIBLE** | domingo a las 3:59 a. m. (leído) |
| Uso adicional / créditos | `monthly_spend` | **USD 21,84 / USD 20,00 = 109 %** | **BLOQUEADO** | `UNKNOWN` |

**Sobre el saldo de USD 57,65:** aparece en la página, pero **no es gasto disponible** mientras el
límite mensual siga en USD 20,00. Recarga automática **desactivada**. No se cambió el límite, no se
compraron créditos, no se tocó la configuración de facturación.

**Lo que esto refutó, y es el hallazgo importante:** el Control Plane tenía un **defecto real**.
`puede_empezar()` bloqueaba **todo el trabajo, incluido el barato**, en cuanto `monthly_spend`
pasaba a `PAUSED` — es decir, habría parado documentar, revisar y ordenar el estado, que era
exactamente lo único que sí se podía hacer. Peor: una prueba escrita ese mismo día
(`test_el_limite_mensual_pausado_detiene_el_trabajo_caro`) **fijaba la creencia equivocada** y
habría impedido corregirla. Una prueba que protege un error es peor que no tener prueba.

Corrección mínima aplicada (RED 8 fallos → GREEN → **125 pruebas PASS** → ruff PASS → diff-check):

```
CAPACIDAD_INCLUIDA = ("rolling_window", "weekly")   # agotarlo SÍ detiene el trabajo
USO_ADICIONAL      = ("monthly_spend",)             # agotarlo NO detiene lo incluido
puede_empezar(cuota, coste, requiere_uso_adicional=False)
registrar_uso_observado(...)   # exige fuente e instante; marca `caduca`
resumen_de_cuota(...)          # «capacidad incluida: DISPONIBLE · uso adicional: BLOQUEADO»
```

**`AUDITORIA-DP-CP` sigue en `WAITING_FOR_QUOTA` con `recurso_requerido: UNKNOWN`.** No puede
determinarse si la auditoría *requiere* uso adicional o si simplemente se ejecutó por una vía que lo
consume: la instantánea de porcentajes es **posterior** al fallo de las 21:03:55, no simultánea.
Orden del CEO ante la duda: registrar `UNKNOWN` y no cambiar el estado. Se resolverá al reintentarla
—si arranca, era capacidad incluida; si vuelve a morir con la sesión disponible, requiere uso
adicional—, y **no se reintenta ahora** porque lanzar agentes está prohibido por la orden vigente.

**Estado global:** vuelto a `DECISION_REQUIRED`. Mantenerlo en `WAITING_FOR_QUOTA` diría «estás
bloqueado por cuota», que es la confusión que esta corrección elimina; lo que de verdad bloquea el
avance son **D-CP-1, D-CP-2 y D-CP-3**, decisiones del CEO. El `quota_block` con la evidencia
histórica se conserva intacto. Si el CEO prefiere el global en `WAITING_FOR_QUOTA`, se revierte.

---

## 12 · DOS LÍNEAS PARALELAS — regla permanente del CEO (2026-08-17)

**AURORA avanza en dos líneas.** La infraestructura de autonomía existe para que AURORA evolucione;
**no debe desplazar indefinidamente el desarrollo del producto**. Cuando haya trabajo autorizado en
ambas, **B no tiene prioridad automática sobre A**.

### 12.1 · El mapa, verificado contra las fuentes de verdad

| | **LÍNEA A · PRODUCTO** | **LÍNEA B · AUTONOMÍA** |
|---|---|---|
| Construcción nueva | **NO AUTORIZADA** | **NO AUTORIZADA** |
| Qué lo bloquea | `CHECKLIST §5.2` — *«Iniciar cualquier incremento nuevo sin decisión posterior a la revisión estratégica»*. `§3` registra que **«Siguiente inversión del proyecto»** (pendiente desde 2026-08-02) bloquea *«Todo trabajo de construcción nuevo»* | Ambos DP en **PROPUESTO**. `CP-GREEN` ← D-CP-1/2/3 · `ORCH-FASE-1` ← D-ORCH-5 |
| Trabajo seguro que sí queda | Completar/verificar incrementos **ya aprobados** y corregir veracidad de documentos de gobierno — no es «incremento nuevo» | `AUDITORIA-DP-CP` (verificación, no construcción) |
| Y por qué tampoco se pudo hacer | — | `WAITING_FOR_QUOTA` + `recurso UNKNOWN`, **y esta sesión no puede auditarla**: escribió el DP y sus 35 RED, y *el que implementa nunca audita su propio trabajo* |

**Busqué acta posterior que levantara el bloqueo de la Línea A y no existe:** `decisiones/` no tiene
nada después del 2026-07-28, y `revisiones/2026-08-02-revision-estrategica-roadmap.md` termina en
**§6 Alternativas de inversión** y **§7 Preguntas que solo el CEO puede responder**. La decisión
nunca se tomó.

**El cuello de botella del producto no es la cuota: es esa decisión.** Y arrastra lo más grave del
repositorio: **`ALERTA-006` sigue ABIERTA con PRIORIDAD MÁXIMA** (CEO, 2026-08-03) — *con el kill
switch ARMADO, AURA sigue borrando datos del usuario*. Su contención está implementada; su cierre
estructural depende de `DP-D-M-8-MOTOR-UNICO-DE-MUTACIONES`, **pendiente de aprobación**.

### 12.2 · Tarea ejecutada — `PROD-1` (Línea A)

**El `PLAN-DE-FORMACION-AURORA.md` declaraba ausentes o bloqueadas dos capacidades que ya están
construidas, cableadas en producción y probadas.** Es el patrón «declarado ≠ real» **número 10**,
esta vez con el signo invertido: no afirmaba de más, **afirmaba de menos**. Igual de caro — quien lo
lea puede reconstruir lo ya construido, y el CEO podía creer que AURORA no puede pedirle permiso.

| Verificado `[EJEC]` 2026-08-17 | Resultado |
|---|---|
| 018 · Pieza 2 (buzón de decisiones) | `975e465`, **acta del CEO 2026-08-10**; `hitl_diferido.py` cableado en `__main__.py:28` y `composicion.py:368,372` — **34 pruebas pasadas** |
| 018 · ruta «qué decisiones esperan mi aprobación» | **existe**: `2ae2416 feat(gobierno)` |
| 017 · motivo del bloqueo | **ya no es cierto**: `b48fbbd` hace que `intentos` *se lea para DECIDIR* — **9 pruebas pasadas** |

**Lo que NO se hizo, deliberadamente:** no se reclasificó ninguna capacidad. Mover 017 o 018 de 🔴
exige la regla de admisión —evidencia repetida del **uso real**— y, en 018, la **auditoría
independiente que sigue pendiente**. Regla del CEO: *ninguna capacidad se promueve mientras exista
una evidencia pendiente que pueda cambiar el veredicto*. Queda como **`D-FORM-1`**.

Cero ficheros de `walking-skeleton/` modificados. Cero agentes, cero inferencias, cero uso adicional
de cuota.

### 12.3 · Siguiente acción — y no la desbloquea el agente

`DECISION-CEO-INVERSION`: elegir la siguiente inversión del producto entre las alternativas de
`revisiones/2026-08-02-revision-estrategica-roadmap.md §6`, **o** aprobar `DP-D-M-8` para cerrar
`ALERTA-006`. Mientras no se decida, la Línea A solo puede verificar y corregir lo ya existente.

---

## 13 · Informe de decisión preparado — `DECISION-CEO-INVERSION`

**Artefacto:** [`milestones/m3-entry/INFORME-DECISION-CEO-INVERSION.md`](milestones/m3-entry/INFORME-DECISION-CEO-INVERSION.md) · 421 líneas.

**Qué es:** el material para que el CEO tome **una sola decisión explícita**. Desarrolla las seis
alternativas de `revisiones/2026-08-02-revision-estrategica-roadmap.md §6` —qué habilita, qué problema
resuelve, dependencia, riesgo, trabajo existente, trabajo nuevo, impacto en producto e impacto en
autonomía—, trata `DP-D-M-8` por separado, y separa **HECHOS VERIFICADOS** de **DECISIONES
PENDIENTES**.

**Qué NO es:** no recomienda, no crea alternativas, no modifica ningún DP, no implementa nada.
Verificado mecánicamente: **6/6 filas de §6 y 4/4 preguntas de §7 reproducidas literalmente**; cero
marcas de recomendación en el texto.

### Cuatro hechos que cambiaron desde la revisión y el CEO debe conocer antes de decidir

1. `[EJEC]` **El artefacto temporal de N2 ya fue mitigado** (`3e716d4`; `~/.aura/models/` es un
   directorio real). Era **uno de los tres motivos de la alternativa E**: E vale hoy menos que el
   2026-08-02. También **responde por los hechos la pregunta §7.4**.
2. `[EJEC]` **La contención F1 de ALERTA-006 está implementada** (`orchestrator.py:153`, `:221`) —
   pero **el bypass estructural sigue abierto**: `:1011` y `:1022` llaman a `borrar`/`refutar`
   **directamente**, no vía `motor.ejecutar`.
3. `[EJEC]` **La contrapartida de la alternativa F cambió en parte**: AURORA ya tiene proceso propio,
   panel de gobierno y buzón de decisiones. Sigue **sin voz y sin LLM viable**.
4. `[EJEC]` **La alternativa D sigue descartada, con evidencia nueva**: `EXP-REPRO` dio `NO_VIABLE` en
   las dos inferencias.

**Advertencia registrada:** las cifras de CPU, RAM, USB y swap de `§5` son `[LECT]` del 2026-08-02 y
**no se re-midieron** (el CEO prohibió la vigilancia de RAM). Si la decisión se apoya en ellas,
ejecutar antes `entorno/scripts/preflight-check.sh`.

**El estado de `DECISION-CEO-INVERSION` no ha cambiado: sigue pendiente del CEO.** Preparar la
decisión no es tomarla.

---

## 14 · DECISIONES DEL CEO 2026-08-17 · mapa de ejecución de `DP-D-M-8`

### 14.1 · Lo decidido, registrado

| Decisión | Estado registrado |
|---|---|
| **`DP-D-M-8` — Motor Único de Mutaciones** | **APROBADO.** Solo su alcance definido: F0–F6, HITL, PermissionManager, Kill Switch, auditoría, reversibilidad, Quality Gate. **No ampliar, no inventar fases** |
| **`DECISION-CEO-INVERSION`** | **RESUELTA: A — Hardware / entorno de inferencia.** `COMPLETED`: resolverla no es ejecutarla |
| **`INVERSION-A`** | **PREPARADA / PENDIENTE DE CONDICIONES** (`WAITING_FOR_HUMAN`). **No autoriza comprar, instalar ni modificar hardware** hasta resolver **D34** y **P1** |
| **`INVERSION-F`** | No se abre como fase de construcción. Su acoplamiento con A queda registrado |
| **Communication Plane · Codex · Orchestrator** | **No implementar.** Línea estratégica futura |

La cabecera de `DP-D-M-8` se actualizó a **APROBADO por el CEO el 2026-08-17**. Se hace por lo
aprendido en §12: el DP del canal permanente llevaba trece días diciendo «propuesto» **después** de que
el CEO lo aprobara y se construyera, y eso desinformó al Plan de Formación.

### 14.2 · Condiciones de entrada — verificadas

| # | Condición | Estado |
|---|---|---|
| CE-1 | Preflight del entorno | `[EJEC]` **ESTADO: APTO**. Riesgos abiertos declarados: swap en disco interno · Ollama apagado. **Ninguno bloquea F0** |
| CE-2 | Autorización formal registrada | `[EJEC]` Registrada en `estado.json` (`aprobaciones`, `tareas`) y en la cabecera del DP |
| CE-3 | No contradice CHECKLIST/Bible/ADR | `[EJEC]` `CHECKLIST §5.2` exigía *«decisión posterior a la revisión estratégica»*: **ya existe**. `DP §10` declara que no amplía el MVP (D23). El DP **refuerza** ADR-0003, ALERTA-005 e INV-9 |
| CE-4 | `mutaciones/motor-unico.toml` | `[EJEC]` **No existe.** Lo exige `§6`; se crea dentro de F0–F2 |
| CE-5 | Mecanismo que G-1 extiende | `[EJEC]` **Existe**: `architecture_manifest.toml` + `tests/unit/test_manifiesto_arquitectura.py` |
| CE-6 | Línea base verde del Quality Gate | **NO fijada en esta sesión.** El arnés de mutación aborta si la base no está en verde |
| CE-7 | **Aprobación de `ESPEC-G-1`** | ⛔ **NO EXISTE — bloquea F0.** Ver §14.4 |
| CE-8 | Auditoría independiente | ⚠️ **Sin resolver.** Ver §14.5 |

### 14.3 · Mapa de ejecución — las siete fases, tal como las fija `DP-D-M-8 §7`

| Fase | Contenido | Estado |
|---|---|---|
| **F0 · Red** | Escribir **G-1…G-7 en rojo** contra el código actual | ⛔ **BLOQUEADA por `D-G1-1`** |
| **F1 · Contención** | Guarda de dominio · `_foco` que no actúa ante duda · `refutar` comprueba `n` | ✅ **YA IMPLEMENTADA** — `orchestrator.py:153`, `:221`; 5/5 mutantes. **No rehacer** |
| **F2 · Kill switch universal** | Paso 0 en el motor | Espera F0 |
| **F3 · Ejecutor interno** | Contrato `simular`/`aplicar` + catálogo con `sujeto` | Espera F0 |
| **F4 · Migrar rutas** | Soberanía (borrar/refutar/**cablear `corregir`**) → reglas → señales | Espera F0 |
| **F5 · Reversibilidad** | Lápidas en memoria; retirar la reescritura | Espera F3 |
| **F6 · Limpieza** | Corregir `test_modelo_usuario_flujo.py`, *que hoy fija el bypass* | Cierra el ciclo |

**Las siete garantías que F0 debe escribir en rojo** (`§6`): G-1 ninguna mutación fuera del motor ·
G-2 el kill switch armado detiene TODA mutación · G-3 nada no catalogado se ejecuta · G-4 no se narra
éxito sin efecto · G-5 referente ambiguo no destruye · G-6 toda mutación reconstruible desde el audit ·
G-7 append-only donde se declara.

### 14.4 · ⛔ CONFLICTO PRESENTADO AL CEO — `D-G1-1`, no resuelto

**F0 exige escribir G-1 en rojo. El mecanismo de G-1 está especificado en
`ESPEC-G-1-RUTA-UNICA-DE-MUTACION.md`, que sigue *pendiente de aprobación del CEO*.**

Las dos salidas son inaceptables sin acta, y por eso no elijo:

- **Adoptar `ESPEC-G-1`** sería incorporar un documento no aprobado — contra la orden *«no amplíes el
  alcance»*.
- **Escribir G-1 sin ella** sería **inventar un mecanismo que el proyecto ya especificó**, con sus 3
  reglas AST, sus **6 falsos positivos y 6 falsos negativos ya identificados**, y una condición de
  viabilidad **medida**: *renombrar las operaciones mutantes lleva la resolución del 40 % al 100 %*.

El propio `DP-D-M-8 §9.4` lo anticipa: *«Que G-1 no es verificable por AST sin falsos positivos que
bloqueen el desarrollo (…) es el riesgo de implementación de la garantía madre»*.

**`G-2…G-7` no dependen de esa decisión** y podrían escribirse en rojo sin ella. **G-1 sí**, y es *«la
garantía madre»*.

### 14.5 · ⚠️ Segunda condición sin resolver — quién audita

`CLAUDE.md` es terminante: **el que implementa nunca audita su propio trabajo**, y para un incremento
de este tamaño la **orquestación es obligatoria**. Pero el **límite mensual de gasto está `PAUSED`** y
si los subagentes se cobran contra ese límite es `UNKNOWN` (§11.7). **No lo resuelvo inventando:** o el
CEO acepta que la auditoría la haga otra sesión posterior, o autoriza el gasto, o se mide primero si un
subagente arranca. Mientras tanto, **F0–F6 pueden escribirse pero no cerrarse**: sin auditoría
independiente no hay cierre válido.

### 14.6 · Decisiones que el propio DP deja abiertas para más adelante

No son de ahora, pero deben llegar decididas a su fase: **§5.2 · ¿«olvidar» debe purgar físicamente?**
El DP propone baja lógica inmediata + purga física diferida como lista roja, y dice literalmente *«No lo
decido aquí»*. **Se necesita antes de cerrar F5.**

---

## 15 · F0 PARCIAL — RED de G-2…G-7 entregado (`D-G1-1` opción **b**, CEO 2026-08-17)

**Fichero:** `walking-skeleton/tests/unit/test_garantias_motor_unico.py` — **33 pruebas · 9 en rojo ·
24 en verde · ruff PASS.** Cero ficheros de producción modificados.

### 15.1 · Resultado por garantía — el estado real, ejecutado

| Garantía | Resultado | Qué demuestra |
|---|---|---|
| **G-2** · el kill switch armado detiene TODA mutación | 🔴 **3 rojos** | Con la parada de emergencia **ARMADA**, `borrar`, `refutar` y `crear regla` mutan igual. Es el titular de ALERTA-006, ahora ejecutable |
| **G-3** · nada no catalogado se ejecuta | 🔴 **4 rojos** | Las 3 operaciones que el `DP §4.2` declara necesarias no existen en el catálogo — y el olvido **se ejecuta igual**: no es que se deniegue, es que nadie la mira |
| **G-4** · no se narra éxito sin efecto | 🟢 **verde** | **Ya lo cerró la contención F1** (`orchestrator.py:1021-1024`). Se fija para que F4 no lo rompa en silencio |
| **G-5** · referente ambiguo no destruye | 🟢 **verde** | **Ya lo cerró F1** (`_foco`) |
| **G-6** · toda mutación reconstruible desde el audit | 🔴 **1 rojo** | `olvidadas 1 entrada(s)` con `trace_id="-"`, **sin `user_id` y sin contenido**. El registro existe; lo borrado **no se puede reconstruir** |
| **G-7** · append-only donde se declara | 🔴 **1 rojo** | El JSONL pasa de **2 líneas a 1**. Caso de control en verde: `AlmacenReglas.desactivar` **anexa** — es el patrón que el `DP §5.2` manda imitar |

**Cada garantía lleva su caso de control.** Sin él, un rojo no distingue «la garantía falla» de «la
prueba está mal escrita» — y este proyecto ya se comió cuatro falsos PASS por ahorrárselo.

### 15.2 · Un falso PASS propio, detectado y cerrado

La primera versión sembraba `kind="modelo_usuario"`, que **no pertenece a
`modelo_usuario._TIPOS = ("semantica", "procedimental")`**. El predicado de `borrar` no casaba con
nada, el borrado no ocurría y **cuatro de los rojos pasaban en vacío**: el fichero habría certificado
que el sistema está sano. Corregido, y blindado con `test_la_siembra_es_realmente_borrable`, un
meta-control que falla si la siembra deja de ser alcanzable. **Se deja escrito porque es exactamente
el patrón que el proyecto persigue, cometido esta vez por la asistencia externa.**

### 15.3 · Independencia respecto de G-1 — verificada, no afirmada

`test_este_fichero_no_depende_del_mecanismo_de_G_1` comprueba **por ejecución** que el fichero no usa
análisis AST, ni `architecture_manifest.toml`, ni lista blanca — los tres elementos del mecanismo de
`ESPEC-G-1 §1`. Todas las pruebas son **de comportamiento**: ejecutan una mutación y observan su
efecto; ninguna necesita saber *quién llama a quién*. Las dos menciones a `ESPEC-G-1` son citas en
docstrings.

`test_las_garantias_escritas_son_exactamente_las_autorizadas` cierra el otro lado: falla si faltara
una garantía autorizada **o si apareciera un `test_g1_`**.

### 15.4 · Lo que sigue bloqueado por G-1

- **F0 no está completa.** Le falta G-1, *«la garantía madre»*.
- **F2…F6 no pueden avanzar**: el CEO prohibió expresamente avanzar a fases que requieran G-1.
- La **generalización estructural de G-4** —«ninguna ruta puede narrar éxito sin efecto»— solo es
  verificable inspeccionando todas las rutas, que es AST, que es G-1. Su forma **de comportamiento**
  sí está fijada aquí y está verde.

### 15.5 · Consecuencia que hay que saber

**El Quality Gate queda en ROJO por construcción** mientras F2–F6 no cierren las garantías: 9 fallos
deliberados. **Es el propósito de F0** —*«documenta el estado real»*—, no un defecto. La línea base
sin este fichero sigue intacta: **919 pasadas, 3 omitidas**, idéntica a la registrada.

### 15.6 · Auditoría independiente — `WAITING_FOR_QUOTA`, no `COMPLETED`

Esta sesión escribió el RED, y `CLAUDE.md` prohíbe que el implementador audite su propio trabajo. El
límite mensual de gasto sigue `PAUSED` y si los subagentes se cobran contra él sigue en `UNKNOWN`.
**No se autorizó gasto adicional y no se inventa disponibilidad.** Queda registrada como
`AUDITORIA-DMOCHO-F0: WAITING_FOR_QUOTA`.

---

## 16 · G-1 implementada — **DETENIDA ANTES DE GREEN** (CEO 2026-08-17)

**Ficheros:** `walking-skeleton/tests/unit/verificador_g1.py` (verificador) y
`tests/unit/test_g1_ruta_unica.py` (15 pruebas: **5 rojas, 10 verdes**, ruff PASS).
**Cero ficheros de `aura_skeleton/` modificados** — como anticipó el mapa de impacto.

Las 5 rojas fallan **todas por la misma causa**: `architecture_manifest.toml` no declara
`[mutaciones]`. Escribir esa sección es el paso GREEN, y **ahí me detengo**.

### 16.1 · ⛔ El hallazgo que obliga a parar — `D-G1-3`

**R-A devuelve CERO violaciones. No porque no existan: porque G-1 no las ve.**

Los **4 receptores no resolubles** que el verificador cuenta son, exactamente, las **4 rutas de
ALERTA-006**:

```
aura_skeleton/core/modelo_usuario.py:95    self._memoria.olvidar(objetivo)
aura_skeleton/core/modelo_usuario.py:113   self._memoria.marcar(objetivo, {...})
aura_skeleton/core/orchestrator.py:1287    self.automatizaciones.crear(regla)
aura_skeleton/core/orchestrator.py:1314    self.automatizaciones.desactivar(uid, existente)
```

La causa es **`ESPEC §3.3` capa 4**, funcionando según lo diseñado: *«ante un receptor no resoluble,
el verificador calla»*. Y no se resuelven porque `ModeloUsuario.__init__(self, memoria)`
(`modelo_usuario.py:30`) **no anota el tipo**.

**Medido sobre una copia temporal, sin tocar producción:** añadiendo la anotación
`memoria: PersistentMemory`, R-A pasa de **0 a 2** violaciones detectadas en ese fichero.

> **Por eso no escribo el manifiesto.** Hacerlo pondría G-1 en **VERDE** mientras es ciega a las
> cuatro rutas que motivaron su existencia. Sería el patrón «declarado ≠ real» **dentro de la
> garantía madre** — la undécima vez, y en el peor sitio posible.

La salida técnica cuesta dos anotaciones de tipo, **sin cambio de comportamiento**. Pero la orden 7
del CEO prohíbe tocar `aura_skeleton/`. **No lo resuelvo por interpretación.**

### 16.2 · ⛔ La lista blanca — `D-G1-2`, no la apruebo

**R-A: 0 entradas** (por 16.1). **R-B: 25 escrituras directas reales en 10 módulos.**

| Módulo | Escrituras | Evidencia de legitimidad | Estado |
|---|---|---|---|
| `modules/memory.py` | 5 | Es el almacén declarado. `ESPEC §3.1` lo lista en `persistencia_autorizada` | ✅ inequívoco |
| `core/reglas.py` | 2 | Ídem. Es además *«el modelo a imitar»* del `DP §5.2` | ✅ inequívoco |
| `observability.py` | 4 | Audit log append-only + sellado. Listado en `ESPEC §3.1` | ✅ inequívoco |
| `core/kill_switch.py` | 2 | Disparo fuera de banda por presencia de fichero (Bible 5.3 §5) | ⚠️ **DECISION_REQUIRED** |
| `core/estado_operativo.py` | 1 | **Almacén no declarado** — es el `FN-4` de la ESPEC | ⚠️ **DECISION_REQUIRED** |
| `core/decisiones.py` | 2 | **Almacén no declarado** (`AlmacenDecisiones`, Pieza 2) | ⚠️ **DECISION_REQUIRED** |
| `core/centro_gobierno.py` | 2 | Proyección en disco; ADR-0023 exige que sea regenerable | ⚠️ **DECISION_REQUIRED** |
| `conectores/auditoria.py` | 2 | Sin evidencia examinada en esta pasada | ⚠️ **DECISION_REQUIRED** |
| `adapters/programador.py` | 3 | `write_bytes` **sobre ficheros del usuario**; pasa por el Motor como adaptador | ⚠️ **DECISION_REQUIRED** |
| `adapters/computador.py` | 2 | `unlink`/`rename`; ídem | ⚠️ **DECISION_REQUIRED** |

**Tres inequívocos, siete dudosos.** No apruebo ninguno de los siete: dos son **almacenes que nadie
declaró**, y autorizarlos por mi cuenta convertiría un hallazgo en una excepción permanente.

### 16.3 · Tres defectos propios, detectados antes de dar nada por bueno

1. **R-B acusaba `str.replace`.** `orchestrator.py:375` es `resto.replace(marcador, " ")`. **FP-1
   cometido dentro del verificador que existe para evitar FP-1.** Corregido: `replace`/`remove` solo
   cuentan con receptor `os`. Bajó de 28 a 25 escrituras reales.
2. **El meta-test buscaba `"R-D"` por texto y se encontraba a sí mismo** en el descargo del
   verificador. Rehecho **sobre el AST**: comprueba que no exista *código* que implemente R-D, no que
   no se mencione.
3. **El verificador usaba `getattr()`** sobre un nodo AST. Legítimo en Python, pero hacía ambigua la
   garantía de no implementar R-D. Reescrito sin él.

### 16.4 · Lo que NO cambió

`G-2…G-7` siguen **exactamente igual: 9 rojas, 24 verdes**. **G-4 y G-5 siguen verdes.** No intenté
cerrarlas. Cero ficheros de producción modificados (`git status` sobre `aura_skeleton/`: vacío).

### 16.5 · Quality Gate

**FAIL — 14 fallos, 953 pasadas, 3 omitidas.** Los 14 son **exclusivamente** garantías RED: 9 de
G-2…G-7 y 5 de G-1. **Formato, lint, mypy y los 8 contratos PASAN.** El gate está rojo por lo que
falta implementar, no por nada roto.

---

## 17 · DOS LÍNEAS · G-1 en RED · clasificación A/B/C (CEO 2026-08-17)

### 17.1 · Lo decidido

`D-G1-3` y `D-G1-2` quedan **DECISION_REQUIRED**. **No se anotan tipos, no se declaran a mano las 4
rutas, no se escribe el manifiesto, no se aprueba ningún módulo dudoso.** **G-1 permanece en RED.**
La prueba temporal sobre copia se conserva como **evidencia**, no como modificación: producción
sigue con **cero ficheros tocados**.

### 17.2 · Clasificación de los 10 módulos — **ANÁLISIS, NO AUTORIZACIÓN**

**El manifiesto no se ha modificado y nada de esto concede permiso.**

#### A · Inequívocamente autorizables — la fuente existe

| Módulo | Nº | Fuente que lo autoriza |
|---|---|---|
| `modules/memory.py` | 5 | `ESPEC §3.1` lo lista en `persistencia_autorizada`; es el almacén declarado |
| `core/reglas.py` | 2 | `ESPEC §3.1` + **ADR-0023** (JSONL append-only con proyección); `DP §5.2` lo llama *«el modelo a imitar»* |
| `observability.py` | 4 | `ESPEC §3.1` lo lista; audit append-only + sellado |
| `core/estado_operativo.py` | 1 | **ADR-0023 lo reconoce explícitamente** como almacén append-only con proyección por `(objetivo_id, tarea_id)` |

`estado_operativo.py` **sube desde dudoso**: al buscar su fuente apareció que ADR-0023 ya lo
documenta como caso que adoptó el patrón correcto. **Existe autorización; falta el acto de
declararlo**, que es del CEO.

#### B · Requieren decisión humana

| Módulo | Nº | Qué hay | Por qué no basta |
|---|---|---|---|
| `core/decisiones.py` | 2 | Acta del CEO **2026-08-10** (Pieza 2, buzón) | Autoriza su **existencia**, no lo declara **almacén**. No está en ADR-0023 ni en la ESPEC: es el **`FN-4`** — un almacén que nadie declaró |
| `conectores/auditoria.py` | 2 | Escribe un cursor `seq` con `tmp`+`replace` atómico | **Ninguna fuente** lo declara almacén ni lo autoriza a persistir. Es estado pequeño, pero es estado |
| `adapters/programador.py` | 3 | `write_bytes` sobre ficheros del usuario | **Conflicto de la ESPEC** — ver 17.3 |
| `adapters/computador.py` | 2 | `unlink` / `rename` | **Conflicto de la ESPEC** — ver 17.3 |

#### C · No deberían pertenecer al mecanismo — propuesta con su fuente

| Módulo | Nº | Fuente | Razón |
|---|---|---|---|
| `core/kill_switch.py` | 2 | **Bible 5.3 §5** (`docs/libro-05-seguridad-y-confianza/5.3-…`) | No persiste estado: escribe y borra un fichero **centinela** cuya presencia *es* la señal de parada. Someterlo al Motor sería **circular** — el kill switch es el paso 0 del propio Motor |
| `core/centro_gobierno.py` | 2 | **ADR-0023** — *«el historial es la única fuente de verdad; todo lo demás es proyección»* | Escribe una **proyección regenerable** (`~/.aura/CENTRO-DE-GOBIERNO.md`). Gobernar su escritura no protege ningún dato: borrarla no pierde nada |

**C es una propuesta técnica, no una exclusión aplicada.** El verificador sigue reportando los 10.

### 17.3 · ⚠️ Conflicto nuevo — `C-ESPEC-F2-F3`, no resuelto

`ESPEC §2.2` clasifica **«F3 · Efecto externo observable | `subprocess.run`, adaptadores, egress de
red»**. Pero **R-B** —que gobierna F2, la escritura directa a disco— **detecta a los adaptadores
igual**, porque escriben ficheros.

Los adaptadores **son la ruta autorizada del Motor**: `MotorAutomatizacion.ejecutar` los invoca en su
paso 4. Tratarlos como violación de R-B acusaría al mecanismo legítimo; exceptuarlos sin decidirlo
abriría un hueco por omisión. **La ESPEC no dice cuál familia manda.** Lo presento sin resolverlo.

### 17.4 · Las dos líneas

| | **LÍNEA A · PRODUCTO** | **LÍNEA B · EVOLUCIÓN** |
|---|---|---|
| **Qué es** | `DP-D-M-8` · Motor Único de Mutaciones | Communication Plane · Claude Code ↔ Codex CLI |
| **Tarea actual** | **F0 · Red — INCOMPLETA** | `AUDITORIA-DP-CP` / diseño |
| **Autorización** | DP aprobado; G-1 solo dentro de `ESPEC §§1–3, §4.1, §4.2, §4.5` | Investigación, transporte, contratos, seguridad, identidad, handoff, recuperación, aislamiento, protocolo, **RED contractual** |
| **Bloqueos** | `D-G1-2` · `D-G1-3` · `C-ESPEC-F2-F3` · auditoría en `WAITING_FOR_QUOTA` | `D-CP-1` · `D-CP-2` · `D-CP-3` · auditoría del DP en `WAITING_FOR_QUOTA` |
| **Siguiente acción segura** | **NINGUNA** sin decisión: todo exige GREEN, tocar producción o aprobar la lista blanca | **Sección E** — si el campo libre `cuerpo` puede otorgar *de facto* la autoridad que el esquema prohíbe |
| **¿Requiere GREEN?** | **Sí** | **No** para lo autorizado |
| **¿Requiere decisión del CEO?** | **Sí** | Solo para GREEN |

**La Línea A está bloqueada por decisiones humanas; la Línea B tiene trabajo autorizado y disponible
que no consume cuota ni toca producción.** Es la asimetría que justifica mantener las dos abiertas.

---

## 18 · LÍNEA B avanzada — transporte Claude Code ↔ Codex (2026-08-17)

**Entregado:** `milestones/m3-entry/DISENO-CP-TRANSPORTE-CLAUDE-CODEX.md` (315 líneas) +
`entorno/communication-plane/test_red_transporte.py` (**14 RED contractuales**, ruff PASS).
Total RED del canal: **35 + 14 = 49**. **Nada implementado.** Línea A congelada, sin tocar.

### 18.1 · El hecho que gobierna D-CP-1

> **`codex` NO está instalado en esta máquina** `[EJEC]` — `command -v codex` ausente, sin `~/.codex`.
> Y el DP ya marcaba sus datos como `[LECT, documentación oficial]`. **Las 9 capacidades que el CEO
> pidió precisar son `UNKNOWN`**, y el documento las deja como preguntas con el comando exacto que
> las respondería. No se inventó ninguna.

### 18.2 · Dos trampas medidas que cambian el protocolo

1. **`claude -p --output-format json` devolvió `is_error: true` junto a `subtype: "success"`**, con
   **exit 1**. Fiarse de `subtype` daría por buena una ejecución fallida. Hay prueba contractual.
2. **El sobre publica `total_cost_usd` y `usage`** — coste *por invocación*. **No contradice**
   `usage_known: false`, que habla de *cuota restante*. El canal puede acumular coste sin estimar
   margen.

### 18.3 · Estado de las tres decisiones

- **D-CP-1** — resuelto *en lo que hoy se puede*: el transporte de referencia es **de fichero**,
  verificable aquí; **Codex es un adaptador más**, encerrado tras `entregar()`/`recoger()`. Su
  viabilidad depende de 9 verificaciones `UNKNOWN` + ToS. **Dos decisiones nuevas**: `D-CP-1.bis`
  (¿autorizar instalar Codex *solo para medir*? `npm 11.16.0` disponible) y `D-CP-1.ter` (ToS).
- **D-CP-3** — propuesto **N-2, identidad atestiguada** (`de` + `session_id` real + hash del estado
  leído). Gratis, usa un id que Claude ya emite. **Límite declarado: N-2 es trazabilidad, no
  autenticación.** No decidido.
- **D-CP-2** — diseñado GREEN por fases **B1** (canal de fichero, sin terceros) → **B2** (dos
  extremos `claude -p`) → **B3** (`TransporteCodex`). **B1 es el 80 % del valor y no toca a Codex.**

### 18.4 · Qué se puede probar sin Codex

**Un segundo proceso `claude -p` es un extremo real del canal**, no una simulación. **7 de los 8
casos de recuperación** son verificables hoy; el único que no lo es depende del timeout y la
recuperación del propio Codex.

## 19 · LÍNEA B — D-CP-4 cerrada (2026-08-23)

**Estado:** `D-CP-4 = C` (A + B), decidida por el CEO y **implementada, mutada y auditada**.

- **Parte A** — `es_automatizable()` contrasta el criterio contra el **catálogo real** del Motor
  Único, leído por AST de `walking-skeleton/aura_skeleton/core/permissions.py`. **No hay copia en el
  canal:** una segunda lista sería una segunda fuente de verdad. Si el catálogo no se encuentra,
  devuelve vacío y **rechaza todo** (verificado por el auditor renombrando el fichero).
- **Parte B** — `validar()` rechaza `criterio` en `cuerpo` **a cualquier profundidad**, con
  `CAMPOS_DE_EJECUCION` **separada** de la lista negra: `D-CP-5` sigue abierta y debe verse de qué
  decisión viene cada regla.
- **`DP-ORCH §14.bis` regla 2** reescrita por autorización expresa del CEO. Reglas 1, 3 y 4 intactas.
  `CLAUDE.md` **sin tocar**: la contradicción se resolvió **a su favor**.

**Medido:** suite 54 verdes / 46 rojas · mutación **8/8** (D-CP-4) y **9/9** (B4), sin supervivientes
· `ruff` PASS · producción **0 cambios** · sin commit.

**`test_v1` pasó a verde**: era la RED de la parte B y llevaba abierta desde la Sección E.

**Lo que sigue ABIERTO y no debe leerse de menos:** `D-CP-5` (esquema cerrado; los dos casos
anidados por sinónimo siguen rojos) · `D-CP-6` — **R-1: los argumentos NO se validan**, medido:
`es_automatizable({"criterio": "ejecutar_pruebas", "args": ["rm -rf /"]})` devuelve `True` ·
`D-CP-7` (`Bash(*)` sin hooks) · `D-CP-3`. **El veredicto de la Sección E sigue siendo (B).**

**Aviso para quien retome esto:** al tocar el módulo hay que **reejecutar las dos baterías de
mutación**, no solo la del incremento nuevo. Añadir `fuentes_de_criterio()` dejó AMBIGUO el mutante
M3 de B4 —el patrón `return ("control_plane",)` pasó a aparecer dos veces— y esa garantía se quedó
sin protección sin que ninguna prueba lo notara. Lo detectó el arnés, no la suite.

## 20 · LÍNEA B — D-CP-6 (a) cerrada (2026-08-23)

**Estado:** `D-CP-6 = (a)` **CERRADA en su alcance**, implementada, mutada y auditada de forma
independiente. **Su objetivo —«cerrar R-1 en la ruta del criterio»— queda PARCIAL**, y el motivo está
medido, no estimado (ver abajo).

**Esquema derivado, no inventado.** Las 4 capacidades del criterio no figuran en `ESPECIFICACIONES`;
`adapters/qa.py` declara literalmente que *«`args` no participa»* en construir el comando; `auditor.py`
y `diagnostico.py` reciben `args` y no lo usan. **Esquema = cero argumentos**, con la regla «lo no
declarado no se acepta» en lugar de una tabla escrita a mano.

**Medido:** D-CP-6 **11/11** · suite **65 verdes / 46 rojas** · mutación **6/6 + 8/8 + 9/9 = 23**, con
**0 supervivientes, 0 no aplicados, 0 ambiguos** · `ruff` PASS · producción **0 cambios** · sin commit.

### Los dos huecos que dejó la auditoría — ninguno se corrigió por iniciativa propia

1. **El nombre del campo `args` lo fijó el agente, no una fuente de verdad.** `argumentos`,
   `parametros`, `kwargs` y `Args` con `["rm -rf /"]` devuelven **`True`** `[EJEC]`. Por eso R-1 queda
   cerrado **para el campo `args`**, no para la ruta entera. Cerrarlo exige declarar qué campos puede
   tener una tarea, que es **`D-CP-5`**.
2. **Capacidades de LISTA ROJA pasan como criterio automatizable** `[EJEC]`: `pago`, `transferencia`,
   `accion_financiera`, `eliminar_informacion`, `terminar_proceso` → `True`. **Contradice `ADR-0003`**
   (*«una acción de lista roja exige confirmación humana siempre»*). **El origen es `D-CP-4`**, que dice
   «capacidad registrada» sin distinguir verde de roja. `D-CP-6` lo mejora —una roja **con** argumentos
   ya se rechaza— pero no lo cierra. **Presentado al CEO, no resuelto por interpretación.**

**Lo único que se corrigió fue una imprecisión propia:** el código decía «R-1 abierto para las otras
29»; son **9** —las que declaran esquema— porque las ~19 restantes quedan cerradas de rebote.

**Orden del CEO para lo que sigue:** resolver primero `D-CP-4` (lista roja) y **después** volver a
`D-CP-5`. **El orquestador autónomo NO se construye todavía.**

**Aviso permanente para quien retome esto:** al tocar el módulo, **reejecutar las TRES baterías de
mutación**. En dos incrementos seguidos el arnés encontró lo que las 111 pruebas no ven: primero un
mutante AMBIGUO (patrón duplicado), después dos NO APLICADOS (patrones movidos por un refactor). En
ambos casos había garantías sin red y ninguna prueba lo notaba.

## 21 · LÍNEA B — D-CP-5 cerrada y los 4 supervivientes resueltos (2026-08-23)

**`D-CP-5` = esquema CERRADO por tipo. DECIDIDA POR EL CEO el 2026-08-23** («La decisión vigente es
ESQUEMA CERRADO POR TIPO»), implementada, mutada y auditada. **La sección 20 de este mismo fichero
decía que seguía abierta: era falso y queda corregido aquí.**

**Campos declarados, todos derivados de pruebas y contratos previos, ninguno inventado:**
`TASK{objetivo:str, a:int, b:int, instruccion:str}` · `RESULT{suma:int, ok:bool}` ·
`ACK{verificado:bool}` · `DECISION_REQUIRED{pregunta:str}` · los otros cuatro tipos, sin campos.
**`criterio` NO se declara** — `D-CP-4` ya lo había decidido.

**B2/B3 preservados sin comodín:** bastó declarar `a`, `b` e `instruccion` **con su tipo**. No se
introdujo `Any`, ni `dict` libre, ni estructura genérica. Siguen 6/6.

### Los 4 mutantes supervivientes, clasificados por ejecución

| Mutante | Clasificación | Evidencia |
|---|---|---|
| `dcp4` M5, M6, M7 | **EQUIVALENTES** | el esquema cerrado rechaza `criterio` igual; el auditor lo confirmó en **11 casos** |
| `dcp5` M6 | **GARANTÍA DESPROTEGIDA** | sin la guarda, un cuerpo no-dict lanzaba `AttributeError` en vez de `MensajeInvalido` |

**No hubo regresión de `D-CP-5` sobre `D-CP-4`:** `criterio` sigue rechazado por **dos vías**. El
esquema cerrado **subsume** el veto de `D-CP-4` parte B y también la lista negra del `DP §4.2`, que
queda **funcionalmente muerta** y se conserva solo como defensa en profundidad.

**Medido:** suite **112 verdes / 43 rojas** · mutación **31 mutantes en 5 baterías, 0 supervivientes,
0 no aplicados, 0 ambiguos** · `ruff` PASS · producción **0 cambios** · sin commit.

### Lo que sigue abierto — no leer de menos

- **`D-CP-7`** y **`D-CP-3`**. **V3 abierto.** **Veredicto de la Sección E: sigue (B).**
- **R-1 parcial:** cerrado para el campo `args`; `argumentos`/`kwargs` aún lo esquivan.
- **El esquema cierra lo no declarado; NO obliga lo declarado.** Un `TASK` con cuerpo vacío se acepta.
- **Aviso para quien implemente `bloqueado_por`:** `test_v4_un_equivalente_semantico_no_desbloquea_una_decision`
  ahora falla **antes** de llegar a su aserción, porque el esquema rechaza el campo `nota`. Cuando
  `bloqueado_por` exista, esa prueba podría seguir roja **sin haber ejercido nunca** la garantía de
  persuasión que dice proteger. Hay que revisarla entonces.

## 22 · D-CP-7 CERRADA — frontera externa del Worker (2026-08-25)

**Resolución del CEO:** `F-DCP7 = GREEN respecto al WORKER ADMINISTRADO`. `bwrap` + user namespace es
**barrera de enforcement real** para el Worker una vez dentro de la jaula.

### Constraint arquitectónico PERMANENTE — no es deuda

> *«F-DCP7 no protege contra otro proceso perteneciente al mismo UID que controle el host. Sin
> privilegios/root no se considera posible cerrar esa frontera.»*

**No se registra como deuda ni como defecto.** Es una limitación estructural: en Linux la frontera de
seguridad **es el UID**, y se midió que cualquier proceso del mismo usuario alcanza y **modifica** el
interior de un namespace ajeno por `/proc/PID/root` — el proceso enjaulado ve el cambio en vivo.
**Prohibido seguir parcheándolo:** sin elevar privilegios, sin crear usuarios, sin `memfd`.

### Evidencia conservada `[EJEC]`

- `bwrap` + userns **sin root**; user namespaces sin privilegios habilitados.
- Dentro: **`CapEff = 0000000000000000`** y **grupos suplementarios eliminados** — el grupo `sudo` del
  host **no existe** en la jaula.
- **Worker real**: Claude Code 2.1.241 arranca, autentica, habla con la API y trabaja dentro.
- **Frente al Worker, desde dentro NO puede**: modificar la configuración de seguridad · borrar ni
  modificar el hook · borrar un fichero montado dentro de un directorio escribible *(«Dispositivo o
  recurso ocupado»)* · escribir fuera del workspace · ver el repositorio · recuperar acceso anidando
  `bwrap` · sobrescribir, borrar o reemplazar el directorio de su propio binario.
- **`--clearenv` + `HOME` + `PATH`** basta para arranque, autenticación y API; las 7 variables
  peligrosas no llegan.
- **`--dangerously-skip-permissions` NO evade `PreToolUse`**: el hook bloqueó la herramienta y el
  centinela no se creó.

### Límites que NO quedan cubiertos — ninguno está cerrado

| Límite | Estado |
|---|---|
| **Mismo UID** | **abierto** — constraint permanente |
| **Lanzador omitido** | **abierto** — `claude` es invocable directamente |
| **Manipulación externa durante la sesión** | **abierto** — `--ro-bind` es vista viva (TOCTOU) |
| **Credenciales y red** | **abierto** — credencial legible + `--share-net`: permite exfiltración sin romper la jaula |
| **Audit log** | **abierto** — `/estado` es `rw`: el Worker borra su historial |
| **Cobertura del hook** | **abierto** — solo `Bash`; medido que `Write` crea ficheros prohibidos |
| **Utilidades por `PATH`** | **abierto** — suplantables; explotado por auditoría |
| **Nombre corto** | **abierto** — `claude` resuelve dentro a `/usr/bin/claude` 2.1.197 |

**El Orquestador NO se construye.** El siguiente paso es una decisión del CEO.

## 23 · CODEX MVP — correccion de la auditoria (2026-08-24) · FASES 1-4 CERRADAS

**CODEX MVP = NO GREEN.** La auditoria independiente dio **FAIL** con 4 graves, todos del
**artefacto de prueba**, no de `delegar.sh` (que NO se ha modificado: sha `33bec337df1b560d`).

| Fase | Estado |
|---|---|
| **1 · seguridad** | **CERRADA.** `test_red_aislamiento_universal.sh` tenia **5** invocaciones contra AURA real sin `--solo-verificar` ni centinela. Reescrita: sujeto = worktree de un **clon en `/tmp`** con el mismo commit raiz, + **centinela obligatorio**. Con M13 la RED **falla** y 0 invocaciones alcanzan AURA. |
| **2 · residuos** | **CERRADA.** 4 residuos del auditor eliminados uno a uno, evidencia preservada con SHA-256. **A y B se conservan** como evidencia de GRAVE-4. |
| **3 · M8/M15** | **CERRADA.** Causa: el delimitador `\|` chocaba con `\|\|`, el patron casaba la cadena vacia y cambiaba 438 lineas. Reconstruidos en 1 linea, `bash -n` valido, causalidad demostrada. |
| **4 · inventario** | **CERRADA.** **M16 = M17** demostrado por ejecucion (copias byte a byte identicas) -> **18 degradaciones distintas**. |
| **5 · M9** | **CERRADA.** Reconstruido: la transformacion anterior dejaba `; then` huerfano. La nueva saca la asignacion del `if` conservando la estructura. **DETECTADO como TERMINAL_EJERCIDO**. |
| **6 · M1/M6/SKIP** | **CERRADA.** Dos RED nuevas con **una invocacion por asercion**, asi ninguna muere en el setup: M1 y M6 pasan a **DETECTADOS sin excepcion TER**. Y `SKIP` deja de ser `PASS`: tres estados **PASS(0) / FAIL(1) / NO_EJERCIDA(2)**. |

**Inventario canonico: 18 declarados · 18 DETECTADOS · 0 supervivientes · 0 no aplicados · 0 ambiguos
· 0 INVALIDOS · 0 NO_EJERCIDOS.** La bateria sale con `exit 0`.

**Leccion de diseño de FASE 6:** una RED cuyas aserciones comparten una sola invocacion es fragil —un
mutante que rompe el setup la mata entera y produce un DETECTADO falso—. **Una invocacion por
asercion** hace que el veredicto salga por causalidad y no necesite excepciones.

**CRITERIO FORMAL VIGENTE — «abortar antes de la garantia» vs «la garantia es no abortar»:**
regla general, si el mutado ejecuta < mitad de las aserciones del control -> **NO_EJERCIDO**;
excepcion **unica**, si declara `TER: <patron>` con su asercion terminal **y** el fallo coincide con
ella -> **TERMINAL_EJERCIDO -> DETECTADO**. Sin `TER:`, o con un `TER:` que no coincida, no hay
excepcion. La distincion tiene su propia RED: `test_red_clasificacion_mutantes.sh`.

**Dos defensas nuevas y permanentes en `bateria_mutacion.sh`:**
1. **Validez del mutante** — `bash -n` + tope de diff (`DIF:`). Un mutante que rompe la sintaxis no
   degrada: destruye, y cualquier RED falla por averia. Asi entraron M8, M9 y M15 como falsos DETECTADO.
2. **Anti-enmascaramiento** — el mutado debe producir >= la mitad de aserciones que el control. Menos
   = aborto temprano = **NO_EJERCIDO**. Destapo M1 (ya senalado por el auditor) y **M6, que nadie
   habia visto**.

**FASE 7 · trazabilidad — CERRADA.** Barrido completo del proyecto buscando conteos antiguos y
afirmaciones incompatibles. **6 obsoletas corregidas** (entre ellas «20 ad-hoc, NO reproducibles», que
seguia declarando la bateria inexistente, y el encabezado de `bateria_mutacion.sh`, que anunciaba 19).
**3 historicas conservadas** —los recuentos de GRAVE-3, FASE 3 y FASE 5 describen correctamente su
momento y NO se borran—. **Las «20/20» de `estado.json` NO se tocan: son de `D-CP-5`, otro contexto.**

**Taxonomia vigente:** `MUTANTE_INVALIDO` · `NO_APLICADO` · `MUTANTE_NO_EJERCIDO` ·
`MUTANTE_TERMINAL_EJERCIDO` · `DETECTADO` · `SUPERVIVIENTE`.
**Codigos de salida de las RED:** `PASS=0` · `FAIL=1` · `NO_EJERCIDA=2`. Un SKIP nunca es un PASS.

**SIGUIENTE PASO EXACTO:** FASE 8 — validacion final y, tras ella, la auditoria independiente, que ya
**no seria prematura**: no quedan supervivientes, invalidos, no aplicados, no ejercidos ni ambiguos.

**AURA intacta:** `aura_skeleton/` 0 modificados · worktree `790fafc` · principal `d933a08` · sin commit ni push.

### FASE 8 · el criterio TER era un falso positivo — CORREGIDO (2026-08-24)

**Defecto.** `TERMINAL_EJERCIDO` se concedia con solo ver la asercion `TER` marcada FALLO. Pero si el
mutante **mata** el sujeto, TODAS las aserciones fallan, incluida esa: la condicion se cumplia
**trivialmente**. Formalmente `P(TER falla | ataca la garantia terminal) = P(TER falla | muere por
otra causa) = 1` — **poder discriminante nulo**. Lo detecto la propia meta-RED escrita para impedirlo.

**Causa de fondo (segundo defecto, propio).** Aquella meta-RED usaba una RED que **invoca Codex real**
para probar logica de clasificacion: su veredicto cambiaba con el estado de la cuota. **No
determinista por construccion.**

**Nueva regla.** `TERMINAL_EJERCIDO` exige **tres evidencias simultaneas**:
**E1 precedencia** (`TER` es la primera asercion que falla) · **E2 causalidad** (la traza `bash -x`
demuestra que el proceso murio **en el punto atacado**) · **E3 firma** (el exit code es el declarado).
Falta una, se deniega. **E4** —control adversarial— es un caso permanente de la meta-RED.

**Evidencia.** `test_red_clasificacion_mutantes.sh` reescrita con **sujeto de juguete propio**, sin
red, sin Codex, sin inferencia, sin reloj: **11 aserciones PASS**, una de ellas verificando que dos
ejecuciones dan clasificaciones **identicas**. Los seis casos salen como deben, y cada denegacion
ocurre **por la evidencia que corresponde** (B por E2, C por E1).

**M9 queda PENDIENTE, no reclasificado.** Sale `SIN_CONTROL`: la cuota de Codex esta agotada
(*«try again at Sep 22nd, 2026»*), su RED no pasa **ni con el codigo intacto** y la bateria —
correctamente — **no concluye**.

**Bateria canonica: 18 declarados · 17 DETECTADOS · 0 supervivientes · 0 invalidos · 0 no aplicados ·
0 no ejercidos · 1 SIN_CONTROL.** `delegar.sh` sha `33bec337df1b560d` intacto · `aura_skeleton/` 0 ·
worktree `790fafc` · sin commit ni push.

### Communication Plane · G3 CERRADO (2026-08-24)

**`hilo` · `pendientes` · `marcar_procesado` · `retractar` · `handoff` · `verificar_integridad` ·
`lock_tomado_por_otro_proceso` · `intentar_lock_no_bloqueante`.**

**12/12 RED · 9/9 mutantes DETECTADOS · 0 supervivientes · CP 128 -> 138 passed, 0 regresiones.**

El ciclo de vida se registra **anexando eventos** al mismo log (`_evento`/`_sobre`), nunca
modificandolo: append-only (ADR-0023). `lock_tomado_por_otro_proceso` e `intentar_lock_no_bloqueante`
**reutilizan `_lock_libre` de G2**: una sola verdad sobre el lock.

**Tres supervivientes corregidos, los tres por pruebas que no discriminaban:**
1. la idempotencia solo se miraba en `pendientes` —vacio igualmente aunque se anexe un evento por
   llamada—; ahora se comprueba sobre el **log**;
2. todos los mensajes de la RED del hilo pertenecian al hilo, luego devolver el log entero daba el
   mismo resultado; ahora hay un **mensaje ajeno** que no debe aparecer;
3. `assert lock_tomado_por_otro_proceso() is False or True` era una **TAUTOLOGIA** — ninguna
   degradacion podia hacerla fallar. Sustituida por una asercion real.

**Defecto propio repetido:** por segunda vez escribi un **nodeid inventado** en el TOML de mutacion.
El arnes lo detuvo con BASE EN ROJO. Conviene verificar los nodeids contra `grep def test_` antes de
declarar una bateria.

**Estado:** G1, G2 y G3 GREEN. Siguen bloqueados **G4** (autoridad), **G6/D-CP-8** (decision) y
**M9** (cuota de Codex). `delegar.sh` sha `33bec337df1b560d` · `aura_skeleton/` 0 · sin commit ni push.

### Communication Plane · G5 CERRADO (2026-08-24)

**`TransporteAdapter` (entregar/recoger) · `Canal.sincronizar` · `abrir(sincronizacion_github=...)`.**
**4/4 RED · 5/5 mutantes DETECTADOS · 0 supervivientes · CP 138 -> 142 passed, 0 regresiones.**

GitHub es **espejo, nunca fuente**: su fallo se anota y el canal sigue. No hay sincronizacion real
—exigiria credenciales que `D24`/`ADR-0001` no autorizan— asi que `sincronizado` es False **con motivo
declarado**, sin fingir un exito que no existe (INV-9).

**Un superviviente, y no era un hueco de cobertura:** `G5-M2` sobrevivio porque estaba **mal
construido** —solo cambiaba el `motivo`, no el veredicto—. Reformulado para fingir el exito de verdad,
muere. Es el mismo patron de M8/M15 del Codex MVP: **un mutante que no ataca lo que dice atacar**.

**Estado del Communication Plane: G1, G2, G3 y G5 GREEN — 142 passed / 20 failed.** De los 20 rojos,
7 son las RED de `D-CP-8` conservadas a proposito. Quedan **G4** (autoridad, bloqueado) y el resto de
simbolos del contrato.

### Codex retirado del entorno operativo (2026-08-24)

**Desinstalado** `@openai/codex@0.147.0` y eliminado `~/.codex`. **Motivo:** cuota agotada hasta el
22-sep-2026 y un disco al 89%. **Recuperados ~400 MB** (6,0 -> 6,4 GB libres).

**Intactos:** node v24.18.0 · npm 11.16.0 · **claude-code 2.1.241** · **opencode-ai 1.18.22** · NVM ·
`~/.claude` · `~/.npm`. **Ningun cambio arquitectonico en AURA.**

**Consecuencia que hay que tener presente:** mientras Codex no este, **no existe via de auditoria
independiente externa** para M9 ni para el Codex MVP. `delegar.sh` se conserva intacto (sha
`33bec337df1b560d`) y Codex es reinstalable con `npm install -g @openai/codex` cuando haga falta.

**Nota forense:** `~/.codex` contenia 8 ficheros con referencias a `aura-project-bible` —sesiones de
las ejecuciones sobre AURA, incluidos los dos incidentes—. Se eliminaron con el resto. **Los residuos
A y B siguen intactos** en `walking-skeleton/`, y la evidencia del auditor sigue preservada con SHA-256.

**Claude Code continua siendo el cerebro principal. OpenCode es herramienta secundaria/arnes.**

### Bootstrap de autonomia (2026-08-24) — el mecanismo YA EXISTIA

**No se construyo nada nuevo.** `entorno/control-plane/control_plane.py` ya implementa el ciclo
completo, y su suite pasa **86/86**:

`iniciar_tarea` -> `debe_ejecutar` -> `completar_tarea` -> `checkpoint_sin_cambios` ->
`interrumpir` -> `registrar_bloqueo_de_cuota` -> `estado_vigente` -> `fijar_estado_tarea`.

Verificado en ejecucion: `checkpoint_sin_cambios` **detecto correctamente** que el CHECKPOINT habia
cambiado y devolvio False con motivo. La salvaguarda funciona.

**Unico ajuste realizado:** `siguiente_tarea` apuntaba a una decision ya cerrada (D-CP-7). Ahora
declara **`CP-G4-AUTORIDAD`, nivel PROPUESTA** — es decir, **bloqueada**: toca autoridad y esta ligada
al veredicto (B) de la Seccion E. **`bloques_AUTO_disponibles` = 0.**

**Procedimiento para el proximo bloque autonomo** (queda escrito en `estado.json`):

1. `cargar()` + `estado_vigente(commit)`.
2. `checkpoint_sin_cambios()`: si es False, **releer el checkpoint antes de actuar**.
3. `debe_ejecutar()`: si dice que no, **no ejecutar** — evita contar dos veces el mismo trabajo.
4. `iniciar_tarea` -> implementar -> pruebas -> mutacion declarada en `walking-skeleton/mutaciones/`.
5. `completar_tarea` con evidencia **medida**, nunca con la afirmacion del ejecutor.
6. `guardar()` + actualizar este documento.
7. Ante una decision humana: `fijar_estado_tarea(..., 'DECISION_REQUIRED')` y **detenerse**.
8. Si la cuota se agota a mitad: `interrumpir()` — **nunca un COMPLETED falso**.

**Conclusion honesta:** no hay bloque AUTO disponible. Todo lo que queda del Communication Plane
—G4, D-CP-8, M9— **requiere una decision del CEO**. La autonomia esta preparada, pero **sin trabajo
aprobado que ejecutar**: crear uno seria justo lo que AURA no puede hacer por si misma.

### Autonomia operativa · el ciclo ya se cierra (2026-08-25)

**Lo que faltaba era UNA pieza**, no un sistema: `control_plane.py` ya tenia todo el ciclo
(`interrumpir`, `debe_ejecutar`, `fijar_estado_tarea`, `registrar_bloqueo_de_cuota`,
`checkpoint_sin_cambios`, `estado_vigente`) pero **no sabia elegir la siguiente tarea**.

Añadidos `siguiente_auto()` y `siguiente_auto_con_motivo()`. **No introducen autoridad**: no deciden
que es AUTO — leen `tareas_AUTO`, que **solo el CEO llena**, y aplican `debe_ejecutar`. Con la lista
vacia devuelven `None` con motivo. **AURA no puede darse trabajo a si misma.**
**92/92 tests · 4/4 mutantes.**

**Como continua otra sesion, sin explicaciones previas:**
```python
import control_plane as cp
e = cp.cargar()                                   # estado.json
cp.checkpoint_sin_cambios(e, "CHECKPOINT-CONTINUIDAD.md")   # si False -> releer ANTES de actuar
tarea, motivo = cp.siguiente_auto_con_motivo(e)   # None = no hay trabajo autorizado
```
Si `tarea is None` -> **WAITING_FOR_HUMAN_DECISION**, registrar el motivo y **detenerse**.

**Arnes OpenCode endurecido.** El bypass medido en OPENCODE-BENCH —`python3 x && rm -rf y` con
`rm *: deny`, porque la politica casa por **prefijo**— queda cerrado por
`/tmp/opencode-hardening/validador.py`: **lista blanca de formas**, no lista negra de peligros.
Cualquier metacaracter (`; && || | < > \` $(`) deniega sin analizar. **21 casos RED · 5/5 mutantes.**
El comando exacto que evadio la allow-list ahora devuelve `DENEGADO`.

**`tareas_AUTO` = 0, a proposito.** G4, D-CP-8 y M9 esperan decision del CEO.

### Cadena AUTO ejecutada (2026-08-25) — G4-a y D-CP-8=C

**Primera cadena autonoma real:** el Control Plane selecciono, ejecuto y cerro dos tareas seguidas
sin intervencion, y se detuvo sola al agotarse la lista.

**G4-a · `bloqueado_por()` — GREEN.** Una decision permanece bloqueada hasta una aprobacion valida;
ningun mensaje del canal la levanta. **Fail-closed**: como `aprobar()` no existe (G4-b sigue
DECISION_REQUIRED), **nada** desbloquea hoy. **3/3 mutantes** tras anadir el caso que faltaba: nada
probaba que el bloqueo fuese ESPECIFICO de `DECISION_REQUIRED`, y bloquear cualquier tipo habria
congelado el canal sin que ninguna prueba lo notara.

**D-CP-8=C · `entregar()` — GREEN parcial.** Aplica `entregar_a_receptor()`, que existia y **nadie
invocaba**: «declarado != real» dentro del propio canal. **E-1: 2/2 · 4/4 mutantes.**
**Limite conocido y aceptado:** el enforcement es **opt-in** — quien llame a `leer()` sigue recibiendo
el crudo, porque cambiarlo tocaria el contrato de B1 que `D-CP-2` aprobo acotado.
**E-2 (5 RED) queda en ROJO POR DECISION**, no por omision: exigiria inventar que `cuerpo["objetivo"]`
nombra una capacidad, y ninguna fuente lo establece.

**Communication Plane: 145 passed / 17 failed** (de los 17, **5 son E-2 conservadas**).
**Control Plane: 131 passed.**

**Parada:** `siguiente_auto()` devuelve `None` — ambas tareas completadas y `tareas_AUTO` agotada.
**Pendientes de decision humana:** **G4-b** (forma de la prueba de autoridad), **M9** (= D, pendiente
explicito), **E-2 de D-CP-8** (requeriria ampliar el contrato).

### AUTO-01 · idempotencia de entrega (2026-08-25) — COMPLETED

`pendientes()` deduplica **por id**, no por contenido: el id ya ES el hash del contenido, y calcular
la identidad dos veces solo añade una via para que discrepen. **El log conserva las dos lineas
fisicas**: `publicar()` no se toco y `leer_desde(0)` sigue devolviendo 2.

**Un superviviente grave, corregido.** `A01-M3` —deduplicar **borrando** la linea repetida— hacia
pasar la asercion original igual de bien. Medido: el log pasaba de **2 a 1 lineas al consultar**.
Es decir, **una LECTURA escribia en el historial**, violando append-only (ADR-0023), y ninguna prueba
lo veia. Añadida la asercion que lo impide. **4/4 mutantes.**

**Communication Plane: 146 passed / 16 failed.** Los 16 rojos esperan decision humana:
3 `aprobar()` (G4-b) · 5 E-2 de D-CP-8 · 8 `test_v4` desfasadas frente a D-CP-5.

**`siguiente_auto()` = None.** Backlog AUTO agotado.

### Seccion E · 8 test_v4 alineadas con D-CP-5 (2026-08-25) — COMPLETED

**La garantia no cambia; cambia como se expresa.** Las 8 pruebas enviaban la frase persuasiva en un
campo `nota`, y desde que `D-CP-5` cerro el esquema eso lanza `MensajeInvalido`: **morian en el SETUP
y la garantia dejaba de ejercerse**, aunque el rojo pareciese cubrirla. Ahora la frase viaja en
`instruccion` —campo **declarado** como `str`—, asi que **entra al canal**, que es el escenario
peligroso de verdad, y se comprueba que aun dentro no desbloquea nada.

**Anadidos 2 casos** que conservan la barrera anterior: la misma frase en un campo no declarado **ni
siquiera entra**. Son dos defensas distintas —una impide entrar, otra impide tener efecto— y ahora
ambas estan probadas.

**`communication_plane.py` NO se modifico.** Solo pruebas. **Seccion E: 32/32.**

**4/4 mutantes**, tras un superviviente que merece recordarse: `SE-M3` sustituia
`sin_rutas = rutas_de_ejecucion_desde_el_cuerpo() == ()` por `True` fijo. Hoy da **el mismo valor**,
asi que nada lo detectaba — pero seguiria afirmando la garantia **el dia que exista una ruta**, que es
justo cuando dejaria de ser cierta. Es `INV-9`: no se finge capacidad no construida. Anadida
`test_el_limite_declarado_se_DERIVA_de_la_medicion_y_no_se_afirma`, que inyecta una ruta y exige que
el limite pase a False.

**Communication Plane: 157 passed / 8 failed.** Los 8 rojos que quedan esperan decision humana:
**3** de `aprobar()` (G4-b) y **5** de E-2 (D-CP-8). **`siguiente_auto()` = None.**

### Communication Plane CERRADO en lo determinado (2026-08-25)

**160 passed · 0 failed · 5 skipped.** El Communication Plane ya no tiene ninguna RED en rojo.

**G4-b · `aprobar()` — GREEN (opcion A del CEO).** La prueba de autoridad **procede del Control Plane
que ya existe**: un acreditativo de lectura con sello del contenido, verificado **releyendo**
`estado.json`, no creyendose lo que la prueba dice. Sin criptografia nueva ni fichero paralelo.
**Su alcance, dicho entero:** esto acredita procedencia, **no autentica identidad** — coherente con
`limites_de_identidad()`, que ya declara `autentica: False`. Fingir lo contrario seria INV-9.
**Lo que NO se implemento:** una lista de quien es autoridad. Ninguna fuente la determina y las
garantias del contrato se cumplen sin ella.
**4/4 mutantes**, tras dos supervivientes reales: probar solo `prueba=None` dejaba sin red lo que de
verdad importa —que la prueba se **verifique**—, asi que un dict cualquiera o un sello inventado
colaban sin que nada lo notara.

**D-CP-8 / E-2 · NO PROCEDENTE (opcion B).** Las 5 REDs **se conservan marcadas con su motivo
contractual**, no se borran: borrarlas eliminaria la evidencia de una decision arquitectonica.
El razonamiento queda en el codigo y en el DP — `AUTO` pertenece al Orchestrator y `D-CP-4` ya cerro
la puerta.

**`communication_plane.py`: 0 lineas eliminadas · `publicar`/`validar`/`leer` intactos · 0 semantica
nueva sobre `objetivo` · 0 segunda via de clasificacion.**

**M9 = SIN_CONTROL**, mantenido por decision del CEO. **`siguiente_auto()` = None.**

### `confirmar_checkpoint()` — la alarma vuelve a informar (2026-08-25)

`checkpoint_sin_cambios()` avisaba cuando el CHECKPOINT cambiaba, pero **no existia forma de
registrar que ya se habia releido**: el aviso quedaba encendido para siempre. Medido en tres
sesiones seguidas con `False`. **Una alarma que suena siempre deja de informar.**

Añadido `confirmar_checkpoint(estado, documento)`: sella la version leida. **No silencia el futuro**
—si el documento vuelve a cambiar, el aviso reaparece—, **falla cerrado** ante un documento
inexistente y **no toca `tareas_AUTO`**: leer no autoriza. **5/5 RED · 4/4 mutantes · 164 passed.**

**Como arranca la proxima sesion:**
```python
import control_plane as cp
e = cp.cargar()
ok, motivo = cp.checkpoint_sin_cambios(e, "CHECKPOINT-CONTINUIDAD.md")
if not ok:
    ...                                   # releer este documento
    e = cp.confirmar_checkpoint(e, "CHECKPOINT-CONTINUIDAD.md"); cp.guardar(e)
tarea, motivo = cp.siguiente_auto_con_motivo(e)   # None -> WAITING_FOR_HUMAN_DECISION
```

**Hueco registrado, NO resuelto:** `trabajo_completado` no enlaza con la propuesta que lo origino
—49 entradas, 0 con `origen_propuesta`—. La cadena `hallazgo -> propuesta -> tarea` existe; se corta
en el resultado. Es **PROPOSAL_ONLY**: cerrarla admite mas de una forma (ampliar `completar_tarea` o
enlazar a posteriori), y ampliar la firma de una API con 49 registros vivos no es decision del agente.

### Trazabilidad · opcion A implementada (2026-08-25)

**Decision del CEO: derivar en consulta.** `trazabilidad(estado, id_trabajo)` recompone
`hallazgo -> propuesta -> promocion -> tarea -> resultado` a partir de lo que **ya existe**
repartido entre `propuestas`, `tareas_AUTO` (`origen_propuesta`, `aprobado_por`) y
`trabajo_completado`. **No duplica el vinculo, no migra historia, no cambia firmas.**

Distingue tres situaciones que se confunden con facilidad:
- **cadena completa** -> `tiene_procedencia=True`, `coherente=True`;
- **sin procedencia** -> trabajo anterior al mecanismo. **No se le inventa un origen**;
- **cadena rota** -> la tarea declara una propuesta que ya no existe: `coherente=False`. Ausente y
  roto **no son lo mismo**, y confundirlos ocultaria justo el caso que hay que ver.

**6/6 RED · 6/6 mutantes · 170 passed.** Un superviviente corregido: `TRZ-M4` (devolver «la primera»
propuesta) sobrevivia porque el fixture tenia **una sola**; con dos, muere.

**Sobre el estado real:** las 6 tareas y las 49 entradas historicas salen `tiene_procedencia=False`
**y es correcto** — son anteriores al mecanismo de propuestas. `trabajo_completado` sigue con 49
entradas intactas y **ninguna gano campos**.

### DEC-DEFECTO-ESTADO-ESTRUCTURADO = B + contencion (CEO, 2026-08-25)

**La apertura de un defecto es un DATO, no una narracion.** Campo `apertura` con vocabulario
CERRADO —`ABIERTO` · `CERRADO` · `OBSERVACION` · `NO_CONSTA`—, leido por `apertura_de()`, que
compara contra el vocabulario y nada mas: **sin substring, sin parser, sin inferencia**. Ausencia y
valor no reconocido colapsan a `NO_CONSTA`, **jamas a ABIERTO**. La prosa historica se conserva
intacta y **nadie la consulta** para decidir apertura.

**Los defectos historicos NO se migraron.** `DEF-FLAKY-P2` y `DEF-CUERPO-LIBRE` siguen invisibles,
pero ahora **por una regla declarada (`NO_CONSTA`) y no porque su texto no coincidiera con un
literal**. Ningun registro fue reinterpretado.

**Contencion — ver mas no es poder mas.** Al abrir la visibilidad aparecio el problema real, medido
en el DP: `DEF-CUERPO-LIBRE` no tiene `fichero` ni `prueba`, el texto de zonas quedaba vacio,
ninguna zona coincidia y `clasificar()` lo devolvia **AUTO_EXECUTABLE**. **La falta de informacion
actuaba como permiso.** Ahora, sin `fichero` **y** `prueba`, ningun hallazgo alcanza
`AUTO_EXECUTABLE`: cae en `PROPOSAL_ONLY`, que ya exige aprobacion expresa del CEO. **No se
introdujo ningun nivel de autoridad nuevo.**

**12 RED · 7/7 mutantes detectados, 0 supervivientes · 182 passed · ruff PASS.**

Una prueba existente hubo que completarla, no corregirla:
`test_una_zona_DISTINTA_no_queda_bloqueada_por_coincidencia` describia un hallazgo `red_roja` **sin
campo `prueba`**, que `descubrir()` no puede producir —siempre pone `prueba = nodeid`—. Se anadio el
campo; **el veredicto esperado sigue siendo `AUTO_EXECUTABLE`**, que es lo que esa prueba mide.

### Decision Package de autonomia restante (2026-08-25)

`milestones/m3-entry/DECISION-PACKAGE-AUTONOMIA-RESTANTE.md`. Dos hallazgos que cambian lo que
estaba escrito:

**Los rojos de Linea A son 11, no 13** `[EJEC]`. G-1:2 · G-2:3 · G-3:4 · G-6:1 · G-7:1; G-4 y G-5
verdes. El 13 eran las **violaciones** que G-1 detecta (4+9), contadas como si fueran tests.

**Los 11 saldrian AUTO_EXECUTABLE** `[EJEC]`, y no porque el mecanismo falle: un hallazgo de red
roja declara como `fichero` **el de la prueba**, y las zonas se calculan sobre el. El trabajo real
vive en `aura_skeleton/` —zona bloqueada— y ninguno de los 11 la nombra. **La contencion no ve
donde esta el trabajo, solo donde esta la prueba.** Abierta `DEC-ZONA-POR-FICHERO-DE-TRABAJO`:
precondicion de cualquier promocion de Linea A.

`WAITING` sigue sin ningun caso real que lo ejerza. `AUDITORIA-DMOCHO-F0` (`WAITING_FOR_QUOTA`) no
sirve como caso: es un estado de tarea, no un hallazgo de Discovery.

### DEC-ZONA-POR-FICHERO-DE-TRABAJO — corregida (2026-08-25)

**Era una falla de contencion, no una mejora.** Las zonas se calculaban sobre el fichero que
COMPRUEBA el trabajo, no sobre el que habria que MODIFICAR. Por eso los 11 rojos de Linea A salian
`AUTO_EXECUTABLE`: su prueba esta en `tests/unit/` —fuera de toda zona— y su trabajo dentro de una
zona vetada.

**Lo que el contrato NO determina, y por eso no se implemento:** derivar automaticamente que fichero
hay que tocar para arreglar una prueba roja. **Ninguna fuente lo mapea** —comprobado sobre el codigo,
los TOML y `architecture_manifest.toml`— y deducirlo del nombre del test seria la heuristica que la
decision prohibe. Eso queda **NO_DETERMINADO**.

**Lo que si determina el contrato es que hacer cuando no se sabe.** El dato se DECLARA
(`fichero_de_trabajo`): si esta, manda sobre la zona; si falta, el hallazgo **nunca** alcanza
`AUTO_EXECUTABLE`. Misma forma que `apertura`, y misma regla del CEO: *ver mas no es poder mas*.

**14 RED · 7/7 mutantes, 0 supervivientes · 195 passed · ruff PASS.**

Dos cosas que conviene no perder:
- La prueba `test_el_control_plane_no_importa_nada_del_producto` **me pillo nombrando el producto en
  un comentario** del modulo. La garantia funciona; el comentario se reescribio sin nombrarlo.
- `test_p2_dos_escritores_concurrentes_pierden_una_escritura` falla de forma intermitente (medido:
  2 de 3 pasan). Es `DEF-FLAKY-P2`, ya registrado como OBSERVACION. **No es regresion.**

### Linea A reclasificada con la contencion corregida (2026-08-25)

Los 11 rojos entraron por Discovery con `fichero_de_trabajo` declarado **solo donde una fuente
existente lo nombra**. **0 AUTO_EXECUTABLE.**

**G-1 (2) -> DECISION_REQUIRED.** Sus fallos **enumeran los ficheros infractores con linea** `[EJEC]`:
R-A senala `core/modelo_usuario.py` y `core/orchestrator.py`; R-B, `adapters/computador.py`,
`adapters/programador.py`, `conectores/auditoria.py` y `core/decisiones.py`. Todos bajo el arbol del
producto, que es zona vetada — y uno cae ademas en la zona `orchestrator`. **Son los dos unicos
hallazgos de Linea A cuyo trabajo real esta determinado por evidencia.**

**G-2 (3) · G-3 (4) · G-6 (1) · G-7 (1) -> PROPOSAL_ONLY por FAIL-CLOSED.** Sus fallos dicen **que**
falla, nunca **donde** se arregla: «el kill switch no detuvo el borrado», «muta estado persistente
sin catalogar», «el audit no registra que se borro», «el almacen perdio lineas». Ninguna fuente
existente lo mapea, asi que `fichero_de_trabajo = None` y **no alcanzan AUTO**. No se dedujo del
nombre del test.

**Antes de la correccion los 11 salian AUTO_EXECUTABLE. Ahora ninguno.** Y las 9 de fail-closed lo
son por ignorancia declarada, no por veto: si alguien determina su fichero de trabajo, se
reclasifican solas — que es justo lo que debe pasar.

`propuestas` 3 -> 14 (las 3 previas intactas) · `tareas_AUTO` 6 sin cambios · **0 promociones**.

### Diagnostico de las 9 PROPOSAL_ONLY de Linea A (2026-08-25)

**8 de 9 tenian su fichero de trabajo determinado, y la evidencia estaba en las propias REDs.** No
se dedujo del nombre del test: las docstrings **citan fichero y linea** (`memory.py:196` para G-6),
o la asercion importa el simbolo que hay que ampliar (`CATALOGO`, de `core/permissions.py`, en G-3).

- **G-2 (3)** -> `core/modelo_usuario.py` (borrar, refutar) y `core/reglas.py` (crear). La rama de
  soberania no pasa por `authorize`, asi que no hay a quien preguntar por el kill switch.
- **G-3 (3 de 4)** -> `core/permissions.py`: faltan tres entradas en el catalogo.
- **G-6** y **G-7** -> `modules/memory.py`: el audit no registra QUE se borro, y `_persist()`
  reescribe el JSONL entero. Para G-7 **ya existe el patron a imitar**: `AlmacenReglas.desactivar`.

**Los 8 pasaron de `PROPOSAL_ONLY` a `DECISION_REQUIRED`** — no por veto nuevo, sino porque al
saber DONDE esta el trabajo se ve que cae en zona vetada. **El diagnostico no autorizo nada: le
quito la ambiguedad al bloqueo.**

**1 sigue indeterminada:** `test_g3_el_olvido_se_ejecuta_sin_estar_catalogado`. Su fallo es de
EFECTO, no de ubicacion: exige catalogar **y** enrutar la mutacion. Dos ubicaciones razonables, y
elegir seria inventar contrato.

`propuestas` 14 (9 actualizadas, ninguna creada ni borrada) · `tareas_AUTO` 6 · **0 promociones** ·
`aura_skeleton/` **0 modificaciones**.

### DECISION-PACKAGE-LINEA-A (2026-08-25)

`milestones/m3-entry/DECISION-PACKAGE-LINEA-A.md`. **Los 11 bloqueos se agrupan en 3 decisiones
nuevas + 2 ya registradas.** `D-M8-1` (kill switch / motor unico, G-2 x3 y G-3 #4) · `D-M8-2`
(catalogo, G-3 x3) · `D-M8-3` (audit §5.1 y append-only §5.2, G-6 y G-7).

**Un descarte por contrato, no una eleccion mia:** consultar el kill switch dentro de cada rama
crea la ruta alternativa que `ALERTA-005` prohibe. **No se crea decision para G-1:** `D-G1-2` y
`D-G1-3` ya existen y bloquean `G1-GREEN`.

**CONTRADICCION elevada, no reconciliada:** `D-G1-2` dice *«R-A: 0 entradas detectables»* y
`D-G1-3` *«G-1 detecta 0 de las 4 rutas de ALERTA-006»*; **medido hoy, R-A detecta 4 violaciones
con fichero y linea** en `core/modelo_usuario.py` y `core/orchestrator.py` — que son esas rutas.
Antes de decidir sobre esas dos notas hay que confirmar si siguen describiendo el estado real.

### La contradiccion G-1 no existia (2026-08-25)

`milestones/m3-entry/ANALISIS-CONTRADICCION-G1.md`. **El error fue mio:** lei el campo `nota` de
`D-G1-2`/`D-G1-3` e ignore su campo **`estado`, que dice APROBADA (2026-08-18)** en ambas; y lei
*«R-A: 0 entradas detectables»* como «0 violaciones» cuando significa **0 entradas de LISTA BLANCA**.

**Causa real, ESCENARIO C:** se escribio la seccion `[mutaciones]` de `architecture_manifest.toml`
—aplicando `D-G1-2`— y R-A detecta por **nombre de operacion clasificada**. Las 4 violaciones son
`olvidar`/`marcar` (de `memory.py`) y `crear`/`desactivar` (de `reglas.py`) llamadas desde fuera de
su almacen. **El codigo de produccion NO cambio:** las dos anotaciones de tipo que `D-G1-3` aprobo
**siguen sin aplicarse** —`ModeloUsuario.__init__` no anota— y **R-A ve las 4 rutas sin ellas**.

Dos consecuencias que conviene no perder:
- **Los 9 rojos de R-B no son deuda: son el resultado esperado de `D-G1-2`**, que dejo el Grupo B
  fuera a proposito. El propio manifiesto lo dice.
- `D-G1-3` temia que el manifiesto dejara G-1 *«en VERDE sobre un punto ciego»*. **Paso lo
  contrario:** la dejo en rojo y detectando.

`D-M8-1`, `D-M8-2` y `D-M8-3` **intactas**. Que bloquea hoy `G1-GREEN`: **NO_DETERMINADO**, no
investigado.

### D-M8-1 · la alternativa la determina el contrato, la autorizacion no existe (2026-08-25)

`milestones/m3-entry/DECISION-PACKAGE-D-M8-1.md`. **La pregunta «B o C» ya no procede: `DP-D-M-8 §7`
—APROBADO por el CEO el 2026-08-17— determina C.** F2 es el kill switch como **«Paso 0 en el
motor»**; F4 migra las rutas en orden **soberania -> reglas -> senales**; y la cabecera de §7 fija el
principio: *«el sistema esté protegido antes de ser refactorizado»*. **B contradice esa separacion.**

**NO se implemento, y el motivo es contractual, no de esfuerzo:** **no existe ESPEC de F2/F3** —el
unico `ESPEC-*` del milestone es el de G-1 `[EJEC]`— y `C-ESPEC-F2-F3` sigue abierta. Sin ella,
«paso 0 en el motor» no dice donde esta ese paso, que consulta ni que devuelve. Escribirlo por
cuenta propia repetiria el conflicto que `D-G1-1` ya planteo y que se resolvio **aprobando una
ESPEC, no improvisandola**. Bloqueo independiente: `F0` sigue `WAITING_FOR_INDEPENDENT_AUDIT`.

**PROXIMA CONTINUACION: resolver la decision D-M8-1. No repetir la investigacion.** Lo que falta no
es elegir alternativa —esta determinada— sino **autorizar `ESPEC-F2-KILL-SWITCH-UNIVERSAL` y
levantar `C-ESPEC-F2-F3`**, y decidir si F2 espera a `AUDITORIA-DMOCHO-F0`. Una vez aprobada,
**comenzar directamente en RED**. `D-M8-2` y `D-M8-3` siguen intactas.

### ESPEC-F2-KILL-SWITCH-UNIVERSAL escrita (2026-08-25)

`milestones/m3-entry/ESPEC-F2-KILL-SWITCH-UNIVERSAL.md` · **WAITING_FOR_HUMAN_DECISION**.

**El hallazgo que cambia la fase: el Paso 0 YA EXISTE.** `PermissionManager.authorize` consulta el
kill switch como **primera** comprobacion, antes que la lista roja `[LECT]`, y devuelve
`(False, "kill switch activo (5.3 §5)")`. **El defecto de G-2 no es que falte el control: es que hay
rutas que no llegan a el.** F2 deja de ser «construir» y pasa a ser «hacer inevitable».

**DETERMINADO:** la garantia · el orden `kill switch -> autorizacion -> ejecutor` (medido en
`permissions.py:118` y ejercido por la RED de control) · comportamiento armado/desarmado · las 6
invariantes · la evidencia que la RED debe producir (`§6` exige cobertura de **todo** el catalogo,
no muestreo) · los mutantes.

**NO_DETERMINADO / DECISION_REQUIRED (4):** **17.1 BLOQUEANTE** — donde vive el Paso 0: `§7` dice
«en el motor» pero hoy vive en `authorize`; (a) mover o (b) que el motor garantice el paso. **(c)
ambas esta DESCARTADA por contrato**: seria la consulta duplicada que `D-M8-1` rechazo. 17.2
`sujeto` · 17.3 `simular` con parada armada · 17.4 dependencia de la auditoria de F0 — **`§7` no
menciona auditoria en ninguna parte**; la exige el protocolo del proyecto, no el DP.

**PROXIMA CONTINUACION: resolver las 4 decisiones de ESPEC-F2, empezando por 17.1, que es
bloqueante. No repetir la investigacion contractual.** Aprobadas, **comenzar directamente en RED**;
con 17.1 resuelta el resto de la ESPEC basta para escribirla. `D-M8-2` y `D-M8-3` intactas.

### 17.1 consultada: sigue NO_DETERMINADA (2026-08-25)

**Comprobado, no reinvestigado:** ninguna fuente aprobada elige entre A y B, y **`estado.json` no
contiene decision del CEO sobre 17.1** — las unicas menciones a «Paso 0» y «17.1» son las que AURA
escribio. **No se implemento nada.**

**Dato nuevo que reduce la decision `[INFER]`, no medido:** la opcion A —mover el Paso 0 al motor—
solo es compatible con el descarte de C si **se retira la consulta de `authorize`**. Y entonces
`test_g2_control_el_kill_switch_detiene_las_acciones_del_catalogo` —**hoy en VERDE**, ejerce
`authorize` y exige «kill switch» en el motivo— dejaria de pasar. Es una RED de F0, que el CEO fijo
`TECHNICALLY_COMPLETE`. **Medirlo exigiria implementar A, asi que se declara `[INFER]`, no `[EJEC]`.**

B no tiene ese coste: deja la consulta donde esta y hace del motor la unica ruta.
**AURA no elige: el coste se informa, la decision es del CEO.**

**PROXIMA CONTINUACION: resolver 17.1 (A o B).** Con ella resuelta, 17.2/17.3/17.4 se clasifican y
**se entra directamente en RED F2** — la investigacion contractual esta cerrada y no se repite.

### 17.1 = B (CEO, 2026-08-25) · 17.2 determinada · quedan 17.3 y 17.4

**Decision del CEO:** el Paso 0 **permanece en `PermissionManager.authorize()`**. No se mueve al
motor. La obligacion derivada es que **el motor sea la unica ruta** por la que puede ejecutarse una
mutacion. Prohibido duplicar el kill switch o crear autorizacion paralela.

**17.2 · DETERMINADA por `DP-D-M-8 §7`** (aprobado 2026-08-17), y en sus dos mitades:
- **F2 antes que F3** — §7 los enumera en ese orden.
- **`sujeto` NO entra en F2** — §7 asigna «catalogo con `sujeto`» a **F3**. La entrada de F2 es la
  firma vigente `authorize(action, args, trace_id)`. **No se amplia la API.**

**17.3 · DECISION_REQUIRED** — que hace `simular()` con el kill switch armado. Ninguna fuente lo
determina. *Observacion de AURA, que no es decision:* la garantia de F2 habla de **mutacion** y
`simular()` no muta, asi que **ambas respuestas la satisfacen**; podria declararse **fuera del
alcance de F2** en lugar de resolverse ahora.

**17.4 · DECISION_REQUIRED** — y conviene separar las dos mitades porque solo una esta abierta:
- **Requisito contractual de F2: SATISFECHO.** §7 pide la red antes de refactorizar y **la red
  existe** (F0 `TECHNICALLY_COMPLETE`, `no_falta_construccion=true`). **§7 no menciona auditoria.**
- **Requisito del protocolo: abierto.** `AUDITORIA-DMOCHO-F0` sigue `WAITING_FOR_QUOTA`. Y CLAUDE.md
  es tajante: *«ninguna capacidad se promueve mientras exista una evidencia pendiente que pueda
  cambiar el veredicto»*. Si esa auditoria hallara defectos en las REDs de F0, **F2 se habria
  construido contra una red defectuosa**. El riesgo es real; la decision es del CEO.

**NO se escribio RED, ni GREEN, ni mutantes: CASO B del criterio.**

**PROXIMA CONTINUACION: responder 17.3 y 17.4.** Con ambas, la ESPEC queda cerrada y **se entra
directamente en RED F2** — sin repetir analisis contractual. `D-M8-2` y `D-M8-3` intactas.

### F2 · Kill switch universal — EJECUTADO (2026-08-25)

**Decisiones: 17.1 = B · 17.2 DETERMINADA · 17.3 FUERA DE ALCANCE · 17.4 F2 SE ADELANTA.**

**El resultado que importa: F2 no necesito una sola linea de produccion.** Con el Paso 0 en
`authorize` (17.1 = B), la garantia **ya se cumplia**: `MotorAutomatizacion.ejecutar` es camino
unico y llama a `permisos.authorize` **antes** de resolver el adaptador. Lo que faltaba no era
codigo: era **proteccion**, y eso lo demuestra la mutacion.

**RED 69/69** en `tests/unit/test_f2_kill_switch_universal.py`: efecto real (un adaptador que
escribe en disco), cobertura de **todo** `ALTERA_ESTADO` y **todo** `CATALOGO` —no muestreo, como
exige §6—, orden kill-antes-de-HITL, audit, meta-control de que el adaptador muta de verdad y caso
de control desarmado. Sin esos dos ultimos, un motor que no ejecutara nunca habria pasado la
bateria entera.

**Mutacion `f2-kill-switch-universal.toml`: 7 declarados · 6 DETECTADOS · 1 EQUIVALENTE DEMOSTRADO.**
`F2-M7` —borrar el `obs.log` de `_detener`— sobrevivio. **No se tapo con una prueba decorativa:** se
endurecio la asercion de audit, que usaba un `or` no discriminante, y se volvio a medir. Sigue
sobreviviendo, **y eso es la demostracion**: la invariante declarada `I-F2-3` («queda registro en el
audit») se sigue cumpliendo por el registro de `permissions.py`. Lo que M7 degrada —trazabilidad del
ejecutor: que accion y desde que origen— **F2 no lo declaro invariante**. Elevarlo seria otra
decision.

**Alcance que F2 NO cubre, y conviene no confundirlo:** las rutas huerfanas de soberania (G-2 x3 y
G-3 #4) **no se cierran aqui**. `DP-D-M-8 §7` las situa en **F4 · Migrar rutas**, y enrutarlas exige
el catalogo de F3/`D-M8-2` —`authorize` deniega lo no catalogado (RN-2), asi que enrutarlas hoy las
bloquearia SIEMPRE, no solo con la parada armada—. Sus rojos siguen vivos donde estaban.

Control Plane **195 passed** · ruff **PASS** · `aura_skeleton/` **0 modificaciones** ·
`AUDITORIA-DMOCHO-F0` sigue **WAITING_FOR_QUOTA**, intacta.

**PROXIMA CONTINUACION: `D-M8-2` (catalogo de operaciones, G-3 x3) — es la que desbloquea F3, y F3
es requisito de F4, donde se cierran los rojos de G-2.** `D-M8-3` sigue intacta.

### F3 + F4 · implementados, BLOQUEADOS por una contradiccion entre fuentes (2026-08-25)

**Lo hecho y verde en su propia bateria:**
- **F3 · catalogo + sujeto** — `permissions.py`: las tres entradas que `§4.2` nombra literalmente,
  `SUJETO_REQUERIDO` **derivado** del catalogo (sin segunda via) y `sujeto_declarado()` fail-closed
  —presente pero vacio no es declarado—. La comprobacion va **despues** del kill switch: `I-F2-5`
  intacta. `tests/unit/test_f3_catalogo_sujeto.py` **verde**.
- **F4 · soberania por el motor** — `ejecutor_modelo_usuario.py` (ejecutor interno con
  `simular`/`execute`, F3 de `§7`) y `ModeloUsuario(memoria, motor=None)`: `borrar` y `refutar` ya no
  llaman a `memoria.olvidar` directamente. **Sin motor no mutan** (fail-closed: una ruta directa de
  reserva volveria decorativa la migracion). Cableado en `composicion.py`.
  `tests/unit/test_f4_soberania_por_el_motor.py` **11/11 verde, incluido el E2E** que relee el
  almacen desde disco, con meta-control de que el borrado SI ocurre con la parada desarmada.
- **G-6 dentro del ejecutor**: el audit registra **que** se borro y **sobre quien**, leyendo las
  entradas ANTES de tocarlas — despues, lo perdido ya no se puede nombrar.

**EL BLOQUEO — dos fuentes aprobadas se contradicen y no lo resuelvo yo:**
- `§4.3` + `ADR-0017` empujan a **VERDE**: *«un "olvida esto" que pidiera confirmacion seria
  hostil»*, y *«pasar por el motor no es lo mismo que pedir confirmacion»*.
- `test_catalogo_acciones.py::test_criterio_de_reversibilidad_es_coherente`, **regla estructural hoy
  en verde**, empuja a **ROJA**: *«nada que altere o destruya puede estar en verde… impide que una
  futura ampliacion del catalogo cuele una accion destructiva en la lista verde por descuido»*.
  **Fue escrita para impedir exactamente esto.**
- `§4.2` nombra las tres operaciones pero **no fija su lista**.

Registrada como `D-M8-2-LISTA-DE-LAS-TRES-OPERACIONES`. **Bloquea de verdad**: con ROJA el flujo
necesita confirmador y con VERDE hay que ampliar una garantia estructural existente; la eleccion
cambia implementacion **y** pruebas, asi que seguir seria rehacer.

**ESTADO DEL ARBOL — importante para quien continue.** `walking-skeleton` queda con **20 pruebas en
rojo**, y no todas son lo mismo:
- **6** son la contradiccion (`test_catalogo_acciones`, 3+3).
- **~10** son fixtures que construyen `ModeloUsuario(mem)` **sin motor** y por tanto ya no mutan
  (`test_contencion_alerta006`, `test_modelo_usuario_flujo`, meta-control de
  `test_garantias_motor_unico`). **Su arreglo depende de la decision**: con ROJA necesitan
  confirmador; con VERDE basta inyectar el motor.
- **1** es una premisa que caduco a proposito: `test_g3_el_olvido_se_ejecuta_sin_estar_catalogado`
  afirma `"olvidar_informacion_usuario" not in CATALOGO`, y **ya no es cierto** — es el rojo de G-3
  cerrandose.
- **G-1** y `test_g2_...creacion_de_reglas` siguen como estaban: **reglas es el segundo tramo de F4**
  (`§7`: soberania -> reglas -> senales) y no se toco.

**No revertí.** Revertir habria dejado el analisis sin artefacto y la decision sin contexto; el
trabajo esta hecho y sirve para cualquiera de las dos ramas.

**PROXIMA CONTINUACION: resolver `D-M8-2-LISTA-DE-LAS-TRES-OPERACIONES` (A rojas / B verdes con la
regla estructural ampliada por `sujeto` / C otra).** Con la respuesta: ajustar catalogo y fixtures,
volver a verde, mutacion integrada y cerrar. **No repetir F3/F4: estan implementados.**

### D-M8-2 · la pregunta del CEO era la correcta (2026-08-25)

**¿Confundiamos «catalogo» con «lista verde»? SI — y el DP ya los separaba.** `§4.3` los enumera
como **dos filas distintas de la misma tabla**, y la fila que importa dice:

> Kill switch **SI** · Catalogo **SI** · Dry-run **SI** · Permisos **SI** · **HITL NO por defecto** ·
> Auditoria **SI** · Reversibilidad **SI**

Con la frase que lo gobierna: *«el motor aplica la politica; la politica puede eximir de HITL **sin
eximir de nada mas**»*. **El DP aprobado determina el COMPORTAMIENTO, no la etiqueta.** Yo asumi que
«sin HITL» equivalia a «lista verde» — y esa equivalencia la impone el CODIGO, no el contrato.

**Pero la contradiccion no se disuelve: se vuelve mas precisa.** El catalogo solo admite dos
etiquetas y `test_catalogo_es_la_unica_fuente_de_verdad` exige `GREEN|RED == CATALOGO`. Entonces:
- **VERDE** viola la regla estructural *«nada que altere o destruya puede estar en verde»*;
- **ROJA** viola `§4.3`, y **no se puede eximir del HITL** porque `ADR-0003` obliga a confirmacion
  **siempre** en lista roja — regla no negociable, protegida ademas por
  `test_toda_accion_roja_exige_confirmacion`.

**Ninguna de las dos etiquetas puede expresar la fila que §4.3 aprobo.** No son garantias
enfrentadas: es **vocabulario insuficiente**. Clasificacion: **D · decision realmente nueva**.

Alternativas: **A** rojas con HITL (contradice §4.3) · **B** tercera clase en el catalogo, p.ej.
`lista: "soberania"` —expresa la fila de §4.3 sin tocar la regla estructural, que habla de *verde*,
ni `ADR-0003`, que habla de *roja*; exige ampliar `GREEN|RED == CATALOGO`— · **C** verdes ampliando
la regla estructural con la dimension `sujeto`.

**Recomendacion tecnica, que no es veredicto: B es la que menos rompe**, y no por comodidad: es
literalmente la fila que `§4.3` describe, ni la verde ni la roja. **Crear vocabulario es del CEO.**

**Codigo a conservar: F3 y F4-soberania enteros.** Solo cambia la **etiqueta** de las tres entradas
y, con B, la derivacion de listas y una rama de `authorize`. **Nada de lo construido se tira.**

**PROXIMA CONTINUACION: el CEO elige A, B o C.** Con la respuesta: ajustar la etiqueta, alinear
`test_catalogo_acciones.py`, arreglar los fixtures que construyen `ModeloUsuario` sin motor, volver
a verde, mutacion integrada y cerrar F3+F4. **No repetir F2, F3 ni F4-soberania.**

### D-M8 · BLOQUE F3 + F4-soberania — decision B aplicada (2026-08-25)

**Tercera clase `soberania`**, que expresa la fila de `§4.3` sin tocar ninguna garantia previa: la
regla estructural habla de **verde**, `ADR-0003` habla de **roja**. Kill switch SI · catalogo SI ·
sujeto SI · dry-run SI · permisos SI · **HITL NO** · auditoria SI. El nombre es **consecuencia de la
decision B**, tomado del vocabulario de `ADR-0017`; no se atribuye al contrato.

**F3** — clase derivada del catalogo (una sola fuente de verdad), `SUJETO_REQUERIDO` derivado,
`sujeto_declarado()` fail-closed. La garantia estructural **se amplio, no se retiro**:
`GREEN | RED | SOBERANIA == CATALOGO` sin solapamientos, y lo que altera o destruye sigue sin poder
ser **verde** — ahora debe ser roja **o** soberania, y si es soberania **debe declarar sujeto**.

**F4-soberania** — `ModeloUsuario.borrar/refutar` enrutan por el motor. **Sin motor no mutan.**
Ejecutor interno con `simular`/`execute`; G-6 dentro: el audit dice **que** se borro y **sobre
quien**, leido ANTES de tocar nada.

**RED 145 verdes** en las cuatro baterias del bloque · **mutacion 9 declarados, 8 detectados, 1
EQUIVALENTE DEMOSTRADO POR EJECUCION** (`BLQ-M6`: los dos caminos de no-ejecucion del motor devuelven
el dict **sin** clave `resultado`, asi que el valor leido es 0 con guarda y sin ella; es defensa en
profundidad, no una garantia observable — **no se anadio prueba decorativa**).

**Dos supervivientes eran falta de cobertura MIA y se cerraron con casos reales:** `BLQ-M8` (refutar
lo ya refutado narraba efecto — INV-9) y `BLQ-M9` (el ejecutor atendia acciones ajenas).

**Una regresion real, mia, detectada y corregida:** al migrar `refutar` perdi el filtro «solo no
refutadas», y AURA respondia *«Entendido, lo corrijo»* sin haber corregido nada. La destapo
`test_contencion_alerta006`, no mi bateria.

**Fixtures cableados al motor** en 6 ficheros. **Ninguno cambio de veredicto**: sin motor habrian
pasado EN VACIO, que es el falso PASS de siempre. Y el RED de G-3 cuya premisa caduco
(*«olvidar_informacion_usuario not in CATALOGO»*) se **sustituyo** por la garantia que no caduca:
la operacion se ejecuta **porque esta catalogada y bien clasificada**, con control de que lo no
catalogado sigue denegandose.

**QUEDAN 7 ROJOS EN walking-skeleton, todos clasificados:**
- **G-1 x3** — zona prohibida (`D-G1-2`/`D-G1-3`). Uno es **efecto directo de F4**: G-1 ya no ve las
  rutas de ALERTA-006 porque ahora viven en el ejecutor autorizado. Actualizar su manifiesto es
  `D-G1-2`. Abierta `DEC-G1-MANIFIESTO-TRAS-F4`.
- **`test_g2_...creacion_de_reglas`** — **reglas es el segundo tramo de F4** (`§7`: soberania ->
  reglas -> senales). No ejecutado.
- **G-7** — `DEC-M8-3-G7` sigue abierta: `§5.2` se abstiene expresamente.
- **`test_garantias_vigentes` + `test_limite_reintentos`** — **NO son de este bloque** `[EJEC]`: el
  recuento paso de **130/409 a 130/418**, mismo 130 con mas denominador. Y `limite_reintentos` falla
  *por consecuencia*: su tarea sana ejecuta `diagnosticar_estado`, que audita garantias y bloquea si
  hay rotas — los 11 rojos de Linea A ya las rompian antes de esta sesion.

Control Plane **195 passed** · ruff **PASS**.

**PROXIMA CONTINUACION: F4 tramo 2 — reglas (`crear`/`desactivar`) por el motor**, que cierra
`test_g2_...creacion_de_reglas`. No repetir F3 ni F4-soberania. Decisiones abiertas: `DEC-M8-3-G7`,
`DEC-G1-MANIFIESTO-TRAS-F4`.

### D-M8 · tramo soberania COMPLETO; reglas y senales bloqueados (2026-08-25)

**`corregir` migrado** — §7 lo pedia con esas palabras («cablear `corregir`») y era **la ultima ruta
huerfana del grupo**: marcaba `refutada` sobre `_items` en RAM, sin motor y sin persistir. Corregir
son **dos** operaciones del catalogo —refutar lo anterior y registrar la version del usuario— y
ambas atraviesan el camino unico. Con la parada armada no ocurre **ninguna** de las dos.

**Rutas huerfanas de destruccion: CERO** `[EJEC]`. No queda ninguna llamada a `olvidar`, `marcar` o
`_persist` fuera del ejecutor.

**G-1 confirma la migracion de forma independiente** `[EJEC]`: R-A ya **no** señala
`core/modelo_usuario.py`. Ahora señala `core/ejecutor_modelo_usuario.py:90,95` —el punto autorizado
por diseño, que el manifiesto no declara— y `orchestrator.py:1287,1314` —reglas, sin migrar—.
Evidencia añadida a `DEC-G1-MANIFIESTO-TRAS-F4`.

**Mutacion del bloque: 10 declarados · 9 detectados · 1 equivalente demostrado (`BLQ-M6`).**
`BLQ-M10` se **retiro tras ser detectado**: exigia un metodo en PRODUCCION que solo servia al arnes,
y codigo muerto en el producto para sostener un mutante es peor negocio que el mutante. Su garantia
la cubren `BLQ-M5`, `BLQ-M11` y `test_corregir_sin_motor_no_muta`.

**BLOQUEO NUEVO Y REAL — `DEC-F4-TOCAR-ORCHESTRATOR`.** Los tramos 2 y 3 de F4 no son cuestion de
esfuerzo: **exigen modificar `orchestrator.py`, que este encargo prohibe.**
- **Reglas:** `_crear_regla` y `_desactivar_regla` son **SINCRONOS** (`def`, no `async def`). El
  motor es async, asi que migrarlas obliga a awaitarlas dentro de `orchestrator.py` (1287 y 1314).
- **Senales:** `AlmacenSenales` se construye en `orchestrator.py:843` y no recibe el motor.
- **Descartado:** consultar el kill switch dentro de `AlmacenReglas` es la alternativa **A** que
  `D-M8-1` ya rechazo por `ALERTA-005`; y `run_until_complete` desde codigo sincrono revienta con un
  loop ya corriendo.
- **Alcance minimo si se autoriza:** awaitar 2 llamadas y marcar 2 metodos como `async`. **Ninguna
  logica nueva.**

**7 rojos, ninguno nuevo:** G-1 x3 (zona `D-G1-2`) · `test_g2_...creacion_de_reglas` (reglas, este
bloqueo) · G-7 (`DEC-M8-3-G7`, abierta) · `garantias_vigentes` + `limite_reintentos` (**ajenos**:
el recuento sigue en **130** con el denominador subiendo 409 -> 418 -> 419).

Control Plane **195 passed** · ruff **PASS**.

**PROXIMA CONTINUACION: autorizar `DEC-F4-TOCAR-ORCHESTRATOR`** (o denegarla y cerrar D-M8 con el
tramo de soberania como alcance final). Con ella, reglas y senales se migran en una sola pasada.
Decisiones abiertas: `DEC-M8-3-G7`, `DEC-G1-MANIFIESTO-TRAS-F4`.

### D-M8 · F4 COMPLETO — reglas y senales migradas (2026-08-25)

**`DEC-F4-TOCAR-ORCHESTRATOR` ejecutada.** En `orchestrator.py` solo lo imprescindible: dos metodos
pasan a `async`, cuatro `await`, `AlmacenSenales` se construye **tras** el motor para recibirlo, y el
motor autoconstruido inscribe los ejecutores de sus propias rutas —sin eso fabricaba un motor que no
sabia ejecutar ni la soberania ni las automatizaciones, y esas operaciones fallaban por «ninguna
capacidad atiende»: un fallo **indistinguible de una denegacion legitima**. **Ninguna logica nueva.**

**Tramo 2 · reglas.** `EjecutorReglas` atiende `automatizacion`, capacidad que **ya existia** en el
catalogo —no se amplia `D23`—. `crear`/`desactivar` son ahora corrutinas que enrutan por el motor;
la escritura real vive en `_crear_en_disco`/`_desactivar_en_disco`, **que solo invoca el ejecutor**.
Sin motor no mutan. `desactivar` **sigue anexando**, nunca reescribe: `§5.2` lo llama «el modelo a
imitar» y la migracion no lo degrada. **Cerrado el rojo historico
`test_g2_el_kill_switch_armado_no_detiene_la_creacion_de_reglas`.**

**Tramo 3 · senales.** Cada senal entra por `registrar_informacion_usuario` —catalogada y con
sujeto—, cerrando el hueco que `§4.2` denunciaba. `guardar()` devuelve **cuantas se guardaron de
verdad**: con la parada armada son cero, y decir otra cosa seria narrar un efecto inexistente. El
`tipo` de memoria viaja con la senal, asi que **lo procedimental no se degrada a semantico**.

**Pruebas del bloque: 150 verdes, contadas** (F2 · F3 x2 · F4-soberania · F4-reglas-y-senales).
**Mutacion:** `f4-reglas-y-senales` **7 declarados · 6 detectados · 1 equivalente demostrado**
(`RSN-M2`) · `f3-f4-bloque-soberania` **10 · 9 · 1** (`BLQ-M6`). Ambos equivalentes por la misma
razon, **medida**: el dict de una operacion detenida no lleva clave `resultado`, asi que el valor
leido es el mismo con guarda y sin ella. **Tres supervivientes eran falta de cobertura MIA** y se
cerraron con casos reales: `RSN-M3` (ejecutor comodin), `RSN-M7` (la senal perdia su tipo) y los ya
citados del bloque anterior.

**G-1: R-A baja de 4 a 2 violaciones** `[EJEC]`. Las 2 restantes son `orchestrator.py:1304,1331`
llamando a `crear`/`desactivar`, que el manifiesto **declara mutantes**. Ya no lo son: son
envoltorios que enrutan. Actualizar esa declaracion es **`D-G1-2`** y no se toca.

**6 rojos, todos clasificados:** G-1 x3 (`DEC-G1-MANIFIESTO-TRAS-F4`) · G-7 (`DEC-M8-3-G7`, abierta)
· `garantias_vigentes` **131/426** —subio 1 durante el bloque, con el denominador subiendo de 409 a
426 por las pruebas nuevas; plausiblemente la garantia del RED de G-3 que se **renombro** al
sustituirlo, **no verificado**— · `limite_reintentos`, que falla **por consecuencia** del anterior.

Fixtures cableados al motor en **9 ficheros**; **ningun veredicto cambiado**.
Control Plane **195 passed** · ruff **PASS**.

**PROXIMA CONTINUACION:** `DEC-M8-3-G7` (semantica del olvido: lapida sin purga vs con purga
diferida) y `DEC-G1-MANIFIESTO-TRAS-F4`. **F2, F3 y F4 completos: no repetirlos.**

### D-M8 · las dos decisiones finales, resueltas de forma distinta (2026-08-25)

**`DEC-M8-3-G7` — DETERMINADA POR CONTRATO. No hay nada que preguntar.** `§5.2` del DP aprobado no
propone, **ordena**: *«olvidar: reescribe todo, destruye historia -> **lapida: anexar baja logica**»*
y *«**La memoria debe adoptar el patron que las reglas ya usan**, no inventar otro»*. Lo unico que
`§5.2` deja abierto —con un *«No lo decido aqui»* explicito— es la **purga fisica diferida**
(«olvidar del todo», que seria lista roja): una **capacidad adicional**, no un requisito de G-7. La
RED de G-7 pide `lineas_despues >= lineas_antes`, y **la lapida sola la satisface**. Ejecutable
directamente, sin nueva autorizacion.

**`DEC-G1-MANIFIESTO-TRAS-F4` — decision NUEVA del CEO (C).** No es aplicacion de `D-G1-2`: esa
decision aprobo la **lista blanca de persistencia** (grupos A/B/C), mientras que
`[[mutaciones.almacen]]` declara otra cosa, la **superficie mutante**. Cambiar
`mutantes = ["crear","desactivar"]` no aplica lo aprobado: **lo altera**.

Y hay un dato que decide, y va en contra de la actualizacion ingenua `[LECT]`: **R-C exige clasificar
«todo `def` PUBLICO de un almacen; los privados no entran»**. Si las operaciones mutantes pasaran a
`_crear_en_disco`/`_desactivar_en_disco`, que son **privadas**, **R-C dejaria de cubrirlas** — se
perderia cobertura a cambio de un verde. Tampoco caben en `neutros`: `crear` **si** muta, solo que
de forma **gobernada**, y el manifiesto solo tiene dos categorias. **Es el mismo patron de
vocabulario insuficiente que `D-M8-2`, en otro plano.**

**PROXIMA CONTINUACION: implementar la lapida de G-7** (patron de `AlmacenReglas`: anexar + proyeccion
que se queda con la ultima linea) — RED -> GREEN -> mutacion -> regresion. **Y esperar decision del
CEO sobre el manifiesto de G-1.** F2, F3 y F4 estan cerrados: no se repiten.

### G-7 CERRADO · D-M8 completo salvo la decision de gobernanza de G-1 (2026-08-25)

**Lapida append-only implementada** segun `§5.2`, sin preguntar nada: estaba determinada. `olvidar` y
`marcar` **anexan** en vez de reescribir; `_load` proyecta con `historial completo + ultima linea por
clave = estado logico`, que es el modelo de `AlmacenReglas`. **La purga fisica NO se implemento** —
`§5.2` la deja abierta y sigue fuera de alcance.

**11 RED verdes · mutacion 7/7 detectados, 0 supervivientes.** `G7-M7` sobrevivio en la primera
pasada —la clave de proyeccion sin `user_id`— y era **falta de cobertura mia**: probaba con un solo
usuario. Dos personas pueden declarar exactamente lo mismo, y el olvido de una no puede llevarse el
recuerdo de la otra (`P-ARQ-5`). Con el caso añadido, muere.

**Dos premisas caducadas, sustituidas y documentadas:** `test_LA_MEMORIA_VIOLA_EL_PRINCIPIO...` decia
literalmente *«no se arregla; se verifica que la garantia sepa verlo»* — **se arreglo, porque era lo
que §5.2 ordenaba**. Ahora comprueba que la memoria **CUMPLE**. Que el protocolo sepa ver un
incumplimiento sigue cubierto por dos casos con componentes **sinteticos**, que no caducan.

**Rutas huerfanas del alcance D-M8: CERO.** Quedan dos escrituras fuera de alcance y se declaran:
`orchestrator.py:1443` (memoria **episodica** — la conversacion, no conocimiento *sobre* la persona,
que es lo que `§4.2` gobierna) y `memory_semantic.py:95` (envoltorio del store). **`§7` no las
incluye en F4** y no se migran.

**5 rojos, todos de gobernanza o ajenos:** G-1 x3 (`DEC-G1-MANIFIESTO-TRAS-F4`, **decision del CEO**,
no se toca) · `garantias_vigentes` **131/433** —el 131 sigue clavado mientras el denominador sube:
**no lo mueve este bloque**— · `limite_reintentos`, que falla **por consecuencia** del anterior.

Control Plane **195 passed** · ruff **PASS**.

**D-M8: F2, F3, F4 (soberania + reglas + senales), G-6 y G-7 CERRADOS.** Lo unico pendiente es
`DEC-G1-MANIFIESTO-TRAS-F4`, que es gobernanza y no trabajo tecnico.

---

## D-M8 — COMPLETED (2026-08-25)

**Tecnicamente completado y formalmente cerrado por decision de gobernanza.**

F2 GREEN · F3 GREEN · F4 (soberania · reglas · senales) GREEN · G-6 GREEN · G-7 GREEN (11/11 RED,
7/7 mutantes) · E2E GREEN · **rutas huerfanas dentro del alcance D-M8 = 0** · Control Plane 195
passed · ruff PASS.

### G-1 permanece ROJO, y es una decision, no un descuido

**`DEC-G1-MANIFIESTO-TRAS-F4` = C (CEO, 2026-08-25): aceptar el rojo como limitacion conocida del
verificador AST.**

**Que el rojo NO significa:** que F4 este fuera del camino unico. F4 pasa por el motor, y esta
medido. **Que SI significa:** que el verificador no distingue un metodo publico que MUTA de uno que
**encapsula una mutacion gobernada**, y por eso sigue señalando `crear`/`desactivar`.

**Por que no se toca el manifiesto:** cambiar la superficie mutante a `_crear_en_disco` /
`_desactivar_en_disco` haria que **R-C dejara de cubrirlas**, porque R-C solo clasifica metodos
**PUBLICOS**. Se cambiaria **cobertura real por un verde**, que es exactamente lo que este proyecto
no hace.

**Sin modificar:** `architecture_manifest.toml` · `D-G1-2` · `D-G1-3`. **No** se declara
`core/reglas.py` modulo autorizado. **No** se crea tarea AUTO para G-1.

Queda como **deuda de gobernanza separada de D-M8**. Las tres pruebas rojas son R-A (2 violaciones),
R-B (9) y las 4 rutas de ALERTA-006.

### Continuidad

**D-M8 NO se reabre.** El proximo trabajo arranca desde aqui, con el siguiente Decision Package o
milestone pendiente. Decisiones vivas ajenas a D-M8: `DEC-G1-MANIFIESTO-TRAS-F4` (deuda aceptada),
quality-gate global, Orchestrator (`D-ORCH-1..5`), `M9`, `D-CP-1` y `D-CP-3`.

### Siguiente paquete: LINEA B · bloqueada por `D-CP-1` (2026-08-25)

**Antes de nada, un cierre que conviene dejar por escrito: `§7` del DP tenia SIETE fases, no cinco.**
Nunca las mencione en los informes, asi que lo verifico ahora: **F5 y F6 tambien estan cumplidas**,
de facto y como efecto de F4 y G-7 `[EJEC]`.
- **F5 · Reversibilidad** («lapidas en memoria; retirar la reescritura») = lo que hizo G-7.
- **F6 · Limpieza** («corregir `test_modelo_usuario_flujo.py`, que hoy fija el bypass; retirar
  exenciones temporales»): ese fichero **ya usa el motor** —se cableo al migrar F4— y el manifiesto
  **no declara ninguna exencion temporal**.

**El cierre de D-M8 era correcto, no prematuro.** Lo digo porque el CEO lo cerro sin que yo le hubiera
informado de que quedaban dos fases del §7 en el papel.

**`lineas_de_trabajo` estaba DESFASADO y se corrige** —registro de hechos, ninguna decision—: decia
*«G-1 · GREEN NO EJECUTADO»* y listaba `C-ESPEC-F2-F3`, `D-G1-2` y `D-G1-3` como bloqueos; los tres
estan resueltos. En Linea B se retiran `D-CP-4/5/7/8`, tambien resueltas.

**Linea A: agotada.** Sin trabajo determinado pendiente. Lo unico vivo es `AUDITORIA-DMOCHO-F0`, que
**desbloquea la cuota, no el CEO**.

**Linea B: bloqueada, y el orden lo fija `pendiente_ordenado`:** 1 `AUDITORIA-DP-CP` (cuota) ·
2 `D-CP-1` · 3 `D-CP-2` (ya APPROVED para B1) · 4 `D-CP-3` · 5 `CP-GREEN` («solo despues de 1-4»).

**`D-CP-1` gobierna todo el resto**, y su propia nota lo advierte: resolver `D-CP-2` antes seria
*«construir un tubo sin consumidor»*. Sus tres opciones registradas: **A** Codex CLI local —el CEO
ordeno **no integrar Codex**, y hoy esta desinstalado— · **B** API OpenAI —exige **enmendar D24**,
local-first sin claves de terceros; es `D-ORCH-1`— · **C** humano-transporte —**no cumple el
objetivo**—.

**Dato del que el CEO dispone y la nota de `D-CP-1` no recoge**, por ser posterior: esta sesion dejo
escrito `CONTRATO-AGENTE-EXTERNO-BAJO-DEMANDA.md` (instalar -> trabajar -> retirar), que es como se
manejo OpenCode. **No lo propongo como cuarta opcion**: lo señalo porque cambia lo que "integrar un
agente externo" significa hoy respecto a cuando se escribio `D-CP-1`.

**Nada que ejecutar sin decision.** No se creo tarea AUTO, no se promovio nada, no se toco codigo.

### D-CP-1 · RESUELTO — el ciclo bajo demanda existe y se ha ejercido de verdad (2026-08-25)

`entorno/agente-externo/ciclo_bajo_demanda.py` implementa el **§4** del contrato, que hasta hoy
estaba declarado *«conceptual — no implementado, no ejecutado»*. **No lo amplia**: cada regla cita
su clausula. Las dos barreras se aplican **antes de tocar la maquina** — `§2` (necesidad determinada
y justificada; *«un fallo del agente principal NO es motivo suficiente»*) y `§3` (solo fixtures
sinteticos mientras `AURA_APPROVED` este vacio).

**RED 20/20 · mutacion 10/10 detectados, 0 supervivientes, 0 no aplicados.** `AEX-M7` salio
`NO_APLICADO` tras anadir un paso —su linea habia desaparecido— y se **reapunto**: `NO_APLICADO` no
es «detectado», y darlo por bueno habria sido perder la garantia sin enterarse.

**E2E REAL, no simulado:** instalo `opencode-ai@1.18.22` (29 s), respondio `1.18.22`, se retiro y la
comprobacion posterior confirmo la ausencia.

**Y el E2E destapo un defecto de mi propia implementacion, que es justo para lo que sirve:** el ciclo
terminaba con `command -v opencode` en AUSENTE y **tres directorios en HOME**. `npm uninstall` retira
el paquete, **no el rastro**. Faltaba el paso `limpiar residuos` que el §4 pide **despues** de
desinstalar, y la comprobacion miraba solo al ejecutable: habria declarado **COMPLETED con residuo en
disco**. Anadido el paso, anadida la comprobacion de residuos, y **residuo es ahora cualquiera de las
dos cosas**. Los tres directorios se eliminaron y se verifico: **0**.

**Seguridad final:** opencode **AUSENTE** · codex **AUSENTE** · procesos **0** · npm global **0** ·
residuos **0** · credenciales **0** · `AURA_APPROVED` **vacio**.

**D-CP-2:** `D-CP-1` ya no lo bloquea, pero **mas alla de B1 sigue exigiendo levantar `CHECKLIST:235`
= `D-ORCH-5`**, que sigue abierta. B1+B2+B3 estan cerrados y auditados.
**D-CP-3:** **no bloquea nada** (`bloquea: []`). La identidad declarativa ya esta implementada y
probada; formalizarla sigue siendo decision del CEO, pero no detiene trabajo.

Control Plane **195 passed** · Communication Plane **160 passed / 5 skipped** · ruff **PASS**.

**PROXIMA CONTINUACION: `D-ORCH-5`** — levantar `CHECKLIST:235` para que `D-CP-2` pueda ir mas alla
de B1. Es lo unico que separa a la Linea B de continuar.

### D-ORCH-5 · el nombre engañaba (2026-08-25)

**`D-ORCH-5` NO es «modificar el Orchestrator».** Es levantar una **prohibicion general** del
`CHECKLIST §5.2`: *«**Iniciar cualquier incremento nuevo** sin decision posterior a la revision
estrategica»* **no esta autorizado** — y la tabla de §95 la ata a *«la siguiente inversion del
proyecto»*, que bloquea *«todo trabajo de construccion nuevo»*.

**Por que no ha bloqueado hasta ahora, y conviene decirlo:** el CEO ha ido autorizando **incremento a
incremento** —D-M8, sus fases, D-CP-1—, y **cada acta ES una «decision posterior a la revision
estrategica»**. La prohibicion se ha respetado, no eludido.

**Lo que `D-ORCH-5` pide es otra cosa:** una autorizacion **GENERAL** para construir este frente sin
acta por incremento. **Levantar una prohibicion del CHECKLIST es gobernanza del CEO**, y AURA no lo
hace.

**Sin ella no queda trabajo determinado en Linea B:** `D-CP-2` mas alla de B1 la exige, B1+B2+B3
estan cerrados, y `D-CP-3` no bloquea nada y ya esta implementada (`limites_de_identidad()`,
`autentica=False`) — formalizarla es decision del CEO, no trabajo.

**Y un hallazgo sobre `AUDITORIA-DP-CP` que cambia su bloqueo:** figuraba como `WAITING_FOR_QUOTA`.
El ciclo bajo demanda de `D-CP-1` **ya existe**, y §2 del contrato admite *«auditoria especializada»*
y *«segunda opinion independiente»* como motivo valido. Pero **§3 lo impide**: auditar el
Communication Plane exige enviar **codigo de AURA** a un externo, y `AURA_APPROVED` esta vacio.
**Hoy no la bloquea la cuota: la bloquea la politica de datos.**

**Nada que ejecutar sin decision.** 0 lineas de codigo en esta fase.

### D-ORCH-5 ejecutado · B2 GREEN con agente real (2026-08-25)

**`D-ORCH-5`: ejecutado.** El levantamiento se registro **donde vive la prohibicion** —
`CHECKLIST-CONTINUIDAD.md §5.2`— y no solo en `estado.json`: dejar el CHECKLIST afirmando algo que
ya no es cierto seria «declarado != real» en el documento que gobierna. **Levantado SOLO para la
Linea B**; sigue vigente para todo lo demas.

**Un desfase corregido antes de avanzar** `[EJEC]`: el registro decia *«B1+B2+B3 cerrados y
auditados»* y era **falso**. `PLAN-B2.md` empieza con *«**No ejecutado.** Requiere autorizacion
expresa: B2 consume cuota»* y `PLAN-B3.md` con *«**No ejecutado. B3 = READY_FOR_DECISION**»*. **Solo
B1 estaba cerrado.**

**B2 = GREEN, con las seis evidencias del §4 y una sola invocacion real.** Un agente real leyo
`canal.jsonl`, calculo la suma y publico el `RESULT`: `in_reply_to` correcto, `cuerpo.suma == 42`,
`seq: 2`, cadena integra, `is_error: false`, exit 0. **Coste medido: $0.2758.**

**Efecto colateral que el §6 anticipaba y ahora esta resuelto:** la invocacion **arranco**, luego
`claude -p` **no fallo por cuota**. Es dato directo para el `recurso_requerido: UNKNOWN` de
`AUDITORIA-DMOCHO-F0`.

**RED 12/12 con dobles, ANTES de gastar la invocacion** (lo pedia el §7). **Mutacion: 8 declarados ·
7 detectados · 1 EQUIVALENTE DEMOSTRADO POR EJECUCION.**

`B2-M8` —quitar `huecos_de_secuencia` de la integridad— sobrevivio, y al intentar cerrarlo **mi
hipotesis resulto falsa**: crei que una linea ilegible se descartaria dejando la cadena intacta y un
hueco en `seq`. Medido, las dos unicas formas de perder una linea dan lo contrario — intermedia:
`integro=False`; ultima: `integro=True` pero **sin hueco**, porque falta una cola, no un centro. **No
se puede construir `integro=True` con hueco de `seq`**, asi que el mutante no degrada nada
observable. **No se anadio prueba decorativa: se dejo escrito por que no se puede.**

**B3: BLOQUEADO.** Exige **Codex**, y `D-CP-1.bis` (instalarlo) y `D-CP-1.ter` (ToS) siguen abiertas.
El CEO ordeno no reinstalar Codex, y esta autorizacion **no lo cubre**.

**PROXIMA CONTINUACION: `D-CP-1.bis` y `D-CP-1.ter`** — son lo unico que separa a B3 de ejecutarse.

### D-CP-1.bis GREEN · D-CP-1.ter choca con D24 · B3 bloqueado (2026-08-25)

**`D-CP-1.bis` = GREEN, medido.** Codex se instalo bajo demanda (23 s), version **`codex-cli
0.149.1`**, y se retiro: **ausente, 0 residuos, 0 credenciales, 0 procesos**, verificado de forma
independiente. La extension del marco a Codex fue una entrada de **datos** en el registro de agentes;
el ciclo no cambio, y su bateria sigue en **10/10 detectados**.

**`D-CP-1.ter`: la medicion resuelve la incertidumbre, y el resultado es un choque contractual.**
`codex exec` **sin credenciales** devuelve `401 Unauthorized — Missing bearer or basic
authentication` contra `api.openai.com`, exit=1 `[EJEC]`. **No creo ningun fichero de credenciales.**

Consecuencia directa: **para que Codex EJECUTE hace falta autenticarse contra un tercero**, y eso es
una **credencial de terceros**, que **`D24` prohibe** — *«local-first, open source, sin claves de
terceros»*. El encargo era explicito: *«si aparece una obligacion nueva que cambie la gobernanza,
privacidad, coste, AUTENTICACION o D24, detenerse y elevar SOLO esa decision»*, y ademas prohibia
modificar D24. **No se aceptaron terminos en nombre del CEO.**

**`B3`: BLOQUEADO por D24, no por falta de instalacion.** El plan B3 exige *«Codex lee la TASK del
canal y publica el RESULT»*; sin autenticacion no hay ejecucion posible. **No es una duda tecnica
resoluble por evidencia: la evidencia ya esta, y lo que topa es una regla del proyecto.**

**B1 + B2: GREEN e integrados** — Communication Plane **172 passed / 5 skipped**. B3 no rompe nada
porque no llego a tocar el canal.

Control Plane **195 passed** · D-CP-1 **20 passed** · ruff **PASS** · **sin regresiones nuevas**.

**PROXIMA CONTINUACION — decision minima que falta:** ¿se enmienda `D24` para permitir una credencial
de terceros **solo** para el uso bajo demanda de Codex, o **B3 se cierra como NO EJECUTABLE** y la
Linea B se da por completa con B1+B2? **No la tomo yo: `D24` es regla no negociable del proyecto.**

### B3 sin romper D24 · investigacion dirigida (2026-08-25)

**Lo que B3 exige de verdad** `[LECT]`: su §1 pide *«un unico ida y vuelta con un **segundo tipo de
agente**»*, y la tarea es **17+25=42** — no exige inteligencia, solo leer el canal, calcular y
publicar. Su §4 anade que *«B1 ya es agnostico del destinatario (probado en B2)»*. **Lo que ata B3 a
Codex son sus precondiciones P-1..P-4 y los campos `para=codex` / `de=codex`**, no una capacidad
tecnica que solo Codex tenga.

**Tres candidatos, medidos, cada uno con una barrera DISTINTA:**

| Agente | Estado | Evidencia |
|---|---|---|
| **Codex** | BLOQUEADO por `D24` | `[EJEC]` 401 sin credenciales; ejecutar exige credencial de terceros |
| **OpenCode bajo demanda** | **candidato mas fuerte** | el CONTRATO §1 lo designa **el** agente externo bajo demanda; §3 admite **fixtures sinteticos** y 17+25 lo es; y midio que *«Zen atiende SIN credencial»*. `D24` quedaria **intacta**, y ya se instalo y retiro con exito en D-CP-1 |
| **Ollama local** (`qwen2.5:0.5b`, `qwen2.5:3b`) | disponible **sin autorizacion** | `[EJEC]` ambos modelos instalados; local-first puro, cero credenciales. **Pero el CHECKPOINT dice: «no hay autorizacion para la rama de capacidad del razonador ni para construir producto sobre el»** |

**Ninguna fuente determina la sustitucion**, asi que no se implementa ninguna: las tres chocan con
una regla distinta —`D24`, el plan B3 y la no-autorizacion del razonador— y elegir seria inventar la
decision. Registrada como `DEC-B3-QUE-AGENTE`.

**Sobre la duda que planteaba el encargo** —¿un agente local instalado bajo demanda es «externo» y a
la vez local-first?—: **el contrato no lo dice**. Su §1 nombra a OpenCode y a nadie mas. **No lo
afirmo sin fuente.**

**Ollama quedo detenido**: se arranco solo para listar modelos. **0 procesos.**

**PROXIMA CONTINUACION: `DEC-B3-QUE-AGENTE`** — una sola decision, tres opciones medidas.

### B3 ejecutado con OpenCode · el canal cumple, el agente no (2026-08-25)

**`DEC-B3-QUE-AGENTE` = OpenCode bajo demanda, aplicada.** Instalado (24 s, **1.18.22**), ejecutado,
retirado y verificado ausente: **0 residuos, 0 credenciales, 0 procesos, npm 0**. `D24` intacta y sin
tocar Codex ni Ollama.

**RED 8/8 con dobles · mutacion 5/5 detectados, 0 supervivientes, 0 no aplicados.** La bateria cubre
la **septima evidencia** que B3 anade sobre B2 —**quien firma el RESULT**—, sin la cual la respuesta
de B2 pasaria por resultado de B3.

**B3 = `CANAL_OK_AGENTE_NO_SIGUIO`.** El veredicto que `PLAN-B2 §4` obligo a distinguir, y aqui
importa: **el canal hizo su parte; el agente no pudo escribir en el.**

**El hallazgo que justifica el bloque entero, y es grave** `[EJEC]`: pedido a OpenCode un comando
trivial —`echo HOLA_DESDE_BASH > prueba.txt`— **mostro la linea `$ echo …`, dijo `(no output)` y
respondio `OK`… y el fichero NO se creo**. **Narro una ejecucion que no ocurrio.** Es `INV-9` —«no
se finge capacidad»— observado en un agente externo, y explica los tres intentos previos: dos modelos
colgados a 240 s y 420 s, y un tercero que responde texto en 51 s pero nunca publica.

**Lo que esto significa para el proyecto:** un segundo agente que **narra** efectos sin producirlos
no puede sostener B3, cuyo §5 exige un `RESULT` **firmado por el**. Y confirma por que este proyecto
verifica por efecto y no por retorno: con retorno, B3 habria pasado.

**B1 y B2 siguen GREEN e integrados** (`172 passed / 5 skipped`), y la convivencia B2+B3 en un mismo
canal esta probada con dobles: secuencia continua, cadena integra, cada RESULT distinguible por su
firma, y **un B3 fallido no corrompe el resultado de B2**.

Control Plane **195 passed** · D-CP-1 **20 passed** · ruff **PASS** · **sin regresiones nuevas**.

**PROXIMA CONTINUACION:** decidir si B3 se cierra como **NO EJECUTABLE con los agentes disponibles**
—Codex bloqueado por `D24`, OpenCode incapaz de efecto real— o si se abre una via distinta. **No la
tomo yo.**

### Diagnostico del agente externo · CORRIJO MI INFORME ANTERIOR (2026-08-25)

**Afirme que OpenCode «narro una ejecucion que no ocurrio» y lo llame INV-9 en un agente externo.
Era falso, y la causa era mia:** invoque con `env -C DIR` en lugar de `--dir DIR`, asi que el agente
trabajaba en un directorio distinto del que yo verificaba. **El agente no mintio; mi comando estaba
mal.**

**`AGENTE_EJECUTOR_VERIFICADO`** `[EJEC]`: con `opencode run --dir X`, el agente crea ficheros con
contenido exacto, encadena dos comandos, y un **verificador externo** (Python, fuera de OpenCode)
confirma el efecto. Hipotesis descartadas por medicion: **A** (sin shell), **C** (sandbox) y **D**
(necesita `--auto` — funciona sin el). **La causa era B**, y era imputable a mi invocacion.

**Lo que sigue sin explicar, y lo digo como lo que es:** con `--dir` correcto, `echo … > fichero`
funciona en ~50 s, pero `python3 publicar.py 42` agota 150-400 s **y el script funciona cuando lo
ejecuto yo**. **Causa NO DETERMINADA** con lo medido.

**B3: NO ALCANZADO.** El unico canal que llego a 2 lineas **lo publique YO** durante el diagnostico,
no el agente. **Se descarta**: contarlo como B3 seria fabricar trazabilidad, que es exactamente lo
que este proyecto no hace.

Las siete evidencias sobre el canal real del agente: `exit_cero` OK · `sin_error_en_sobre` OK ·
`integridad` OK · **`hay_result` NO** · `responde_a_la_tarea` NO · `suma_correcta` NO ·
`lo_firma_el_segundo_agente` NO. **Veredicto: `CANAL_OK_AGENTE_NO_SIGUIO`** — el canal cumple.

OpenCode **retirado**: ausente, 0 residuos, 0 credenciales, 0 procesos, npm 0. `D24` intacta.

### B3 · diagnostico escalonado de la publicacion (2026-08-25)

**Reduccion del problema, con timeouts cortos** `[EJEC]`:

| Prueba | Resultado |
|---|---|
| A · `python3 -c "print(1+1)"` | **OK** 24 s |
| B · script trivial | **OK** 22 s |
| C · script que **escribe un fichero** | **OK** 30-47 s |
| D · `import communication_plane` | **OK** 30-37 s |
| E1 · `import` + `cp.abrir(".")` | **OK** 34-57 s (**fallo 1 de 3**) |
| E2 · `publicar.py` (`import` + `abrir` + **`publicar`**) | **FALLA SIEMPRE**: 150, 200, 201, 241 s |

**Descartado por medicion, no por intuicion:** no es el script —**0-1 s cuando lo ejecuto yo**— · no
es el directorio —el mismo comando trivial funciona alli— · no es tener el canal presente —C funciona
con y sin el— · **no hay lock retenido** —publico en 0 s justo despues de un fallo— · no hay procesos
huerfanos · no es `--auto`, ni sandbox, ni falta de shell.

**Primera operacion que difiere: `Canal.publicar()` ejecutado BAJO OpenCode.** **Causa ultima: NO
DETERMINADA.**

**Un dato que impide cerrar el diagnostico y conviene no tapar:** los modelos free de Zen **no son
deterministas** — `E1` fallo 1 de 3 veces con el comando identico. Eso hace que «falla siempre» en
E2 (4 intentos) sea fuerte pero no concluyente.

**B3: NO ALCANZADO.** Y lo repito porque es facil de colar: **los dos canales que llegaron a publicar
los escribi YO** al comprobar que no habia lock retenido. **Ambos descartados.** Un `RESULT` firmado
`de: "opencode"` que en realidad escribio Claude Code pasaria las siete evidencias sin que nada lo
delatara.

OpenCode **retirado**: ausente, 0 residuos, 0 credenciales, 0 procesos, npm 0. `D24` intacta.

### B3 · sesion nocturna · el agente no llega a ejecutar (2026-08-25)

**El hallazgo que cierra el diagnostico:** se instrumento el script con marcas persistentes
(`pasos.log`, con `flush` + `fsync` en cada paso) para saber el ultimo paso completado aunque
quedara colgado. **Bajo OpenCode el fichero NUNCA se creo.** El proceso **no llega a lanzarse**: el
agente se atasca **antes de ejecutar**, no dentro de `Canal.publicar()`.

Ejecutado por Claude Code, el mismo script completa los siete pasos en **0,14 s**:
`INICIO → IMPORT_OK → ABRIR_OK → TID_OK → LOCK_TOMADO → LOCK_LIBERADO → PUBLICAR_OK`.

**Funciona bajo OpenCode** `[EJEC]`: `echo > fichero` (40-51 s) · `python3 -c print` (24-40 s) ·
script que escribe fichero (30-47 s) · `import communication_plane` (30-37 s) · `cp.abrir()`
(34-57 s, fallo 1 de 3).

**Falla siempre**: cualquier comando que llame a `Canal.publicar()` — **7+ intentos, 100-241 s**,
como script de 5 lineas y como comando inline, con el modulo en el directorio y sin el (dir de **782
bytes, 3 ficheros**).

**Descartado por medicion, uno por uno:** el canal · el lock (`flock`) · `fsync` · el script · el
modulo de 60 KB · el tamano del directorio · Python · **el servicio degradado** —un dir vacio
responde en 40 s— · procesos huerfanos · credenciales · sandbox · `--auto`.

**Causa ultima: NO DETERMINADA.** Pero el punto esta **localizado y es ajeno a AURA**: la
deliberacion del agente ante ese comando concreto. **No es «OpenCode no ejecuta»** —esta demostrado
que si— **ni «el canal esta roto»** —0,14 s fuera del agente—.

**B3 = NO ALCANZADO.** Sin `DECISION_REQUIRED` nueva: es tecnico, y se agotaron las reducciones
razonables (BLOQUE 12, puntos 1-6). **No se publico nada en nombre de OpenCode.**

OpenCode retirado: ausente · 0 residuos · 0 credenciales · 0 procesos · npm 0. `D24` intacta.

### B3 · diagnostico final: acotado, no determinado (2026-08-25)

**Patron medido, ~15 intentos y 4 modelos free distintos:** todo lo que **no toca el canal** funciona
(12-51 s); todo lo que **si lo toca** falla (100-241 s).

**La medicion mas limpia del bloque:**
- `wc -c canal.jsonl` -> **OK 22 s** (consulta el tamano, no el contenido)
- `python3 -c "print(len(open('canal.jsonl').read()))"` -> **FALLA 120 s** (lee el CONTENIDO)
- leer un fichero **trivial de 436 bytes** -> **OK 12 s**

**Variantes agotadas:** 4 modelos · script vs inline · con y sin el modulo en el directorio · sin
mencionar `canal.jsonl` en el script · sin hash en el comando · sin hash en la salida · directorio
minimo de **782 bytes** · instrumentacion con marcas persistentes.

**Causa ultima: NO DETERMINADA, pero ACOTADA** a cualquier operacion del agente que implique el
**contenido** del canal. **Es ajeno a AURA**: el mismo comando tarda **0,14 s** fuera del agente, con
las siete marcas completas.

**B3 = NO ALCANZADO.** Sin `DECISION_REQUIRED` nueva: es tecnico y las reducciones razonables estan
agotadas. **No se publico nada en nombre de OpenCode.**

**LINEA B: B1 GREEN · B2 GREEN · B3 NO ALCANZADO.**

## Cierre tecnico de Linea B (2026-08-25)

**B1 = GREEN · B2 = GREEN · B3 = NO ALCANZADO** — ni GREEN ni RED: no ejecutable bajo el
entorno/agente actual.

**Validado de nuevo, no heredado:** Communication Plane **180 passed / 5 skipped** · Control Plane
**196 passed** —el flaky `DEF-FLAKY-P2` paso esta vez sin deselect— · ciclo del agente externo **20
passed** · `ruff entorno/` **PASS**.

### CORRIJO una afirmacion mia del bloque anterior

Registre que el fallo de B3 estaba *«acotado a operaciones del agente sobre el CONTENIDO del canal»*,
porque `wc -c canal.jsonl` funcionaba (22 s) y leer el contenido fallaba. **La prueba de confirmacion
lo desmiente: ahora `wc -c` TAMBIEN falla (120 s).** La distincion **no se reproduce** y la acotacion
queda **retirada**.

Lo unico reproducible: **fuera del agente, 0 s siempre; bajo el agente, fallo no determinista al
tocar el canal.** **Causa ultima: NO DETERMINADA, y tampoco acotada de forma fiable.** No se atribuye
ni a OpenCode ni a AURA sin evidencia.

### Quality Gate: **FAIL** — 5 failed · 1139 passed · 3 skipped (249 s)

- **G-1 x3** — deuda de gobernanza **aceptada** (`DEC-G1-MANIFIESTO-TRAS-F4 = C`). Esperado.
- **`test_garantias_vigentes`: 154/456** — subio desde 131/433. **Denominador +23 y rotos +23,
  exactamente igual**; el origen **NO ESTA VERIFICADO** y no lo afirmo.
- **`test_limite_reintentos`** — falla por consecuencia del recuento anterior.

### Falla encontrada y NO corregida (restriccion de esta sesion)

`FIXTURE-MODELO-DATOS-SIN-AWAIT` — `tests/integration/test_modelo_datos.py:74`:
`retirar=lambda a: a.desactivar("u","r1")` llama a la corrutina **sin `await`**.
**Es de TEST, no de produccion**: `grep` confirma **0 llamadores sin await en `aura_skeleton/`**.
**Causa: mia** — al migrar F4 corregi `operar` del fixture y **no** `retirar`. El Quality Gate lo
denuncia con `RuntimeWarning`. **No se toca**: esta sesion solo autoriza CHECKPOINT/estado/doc.

### Estado

Sin cambios de produccion · sin decision arquitectonica nueva · sin autoridad nueva · commits **0** ·
push **0** · OpenCode y Codex **ausentes** · procesos **0** · residuos **0** · credenciales **0**.

**PENDIENTE DE GOBERNANZA:** elegir entre cerrar Linea B con B1+B2 (opcion A) o abrir una via tecnica
separada para B3 sin modificar AURA (opcion B).

### Fixture F4 corregido · Quality Gate sigue FAIL, con todo clasificado (2026-08-25)

**Corregido** `tests/integration/test_modelo_datos.py:74`:
`retirar=lambda a: asyncio.run(a.desactivar("u","r1"))`. **Verificado por comportamiento, no por
ausencia de warning**: audit `desactivada=True` · lineas **1 -> 2** (append-only) · estado
**`activa` -> `inactiva`** · el test pasa con `-W error::RuntimeWarning`. **Cero cambios de
produccion.**

Se busco el mismo patron en los tests: el unico candidato, `retirar=lambda m: m.olvidar(...)`
(linea 94), usa `PersistentMemory.olvidar`, que **es sincrono** — no es el mismo defecto y **no se
toca**.

**Quality Gate: baseline FAIL 5/1139/3 con 2 warnings -> tras el fix FAIL 5/1139/3 con 0 warnings.**
**Los mismos cinco, reproducidos en baseline. Cero regresiones nuevas.**

- **G-1 x3** -> **C · deuda de gobernanza ACEPTADA** (`DEC-G1-MANIFIESTO-TRAS-F4 = C`).
- **`test_garantias_vigentes` 154/456** -> **B · preexistente, y ahora con ORIGEN DETERMINADO**:
  `auditar_garantias` resuelve los ficheros de los TOML **relativos a `walking-skeleton`**, y las
  baterias que apuntan a `entorno/` —`b2-verificador`, `b3-segundo-agente`, `cp-*`,
  `adr0003-lista-verde`, `arnes-validador-comandos`— salen **todas AUSENTE**. Ya habia **131 rotas
  antes**, dos de ellas ajenas a esta linea de trabajo. **Retiro el «origen no verificado» anterior.**
- **`test_limite_reintentos`** -> **D · consecuencia**: `diagnosticar_estado` bloquea la tarea cuando
  hay garantias rotas.

**Por que no llega a PASS:** corregirlo exigiria tocar **produccion** (`auditar_garantias`) o
**gobernanza** (G-1), ambas prohibidas en esta sesion. **No se maquilla el resultado.**

**B1 = GREEN · B2 = GREEN · B3 = NO ALCANZADO · causa B3 = NO DETERMINADA · hipotesis del canal =
RETIRADA.** Communication Plane **180 passed / 5 skipped** · Control Plane **196 passed** · agente
externo **20 passed** · ruff **PASS** en `entorno/` y en `walking-skeleton/tests`.

Sin decision arquitectonica nueva · sin autoridad nueva · commits **0** · push **0** · procesos,
residuos, credenciales y locks: **0**.

## LINEA B — ESTADO CONSOLIDADO (2026-08-25)

**B1 = GREEN · B2 = GREEN · B3 = NO ALCANZADO.**

### B3 — diagnostico CERRADO

**Causa: NO DETERMINADA.** La hipotesis *«el fallo esta acotado a operaciones del agente sobre el
CONTENIDO del canal»* queda **explicitamente RETIRADA**: la prueba de confirmacion la desmintio.

**Lo unico que permanece demostrado:** fuera del agente las operaciones funcionan; bajo el agente el
comportamiento sobre el canal presenta **fallos no deterministas**. **No se extrapola mas alla.** No
se atribuye ni a AURA ni a OpenCode.

### Quality Gate = **FAIL**

Formulacion exacta: **FAIL por condiciones preexistentes / deuda conocida; cero regresiones nuevas
atribuibles a esta sesion.** No se convierte en PASS por clasificacion.

| Fallo | Clase | Accion |
|---|---|---|
| G-1 x3 | **C — deuda de gobernanza ACEPTADA** (`DEC-G1-MANIFIESTO-TRAS-F4 = C`) | **ninguna** |
| `test_todas_las_garantias_declaradas_siguen_vigentes` | **B — defecto preexistente del auditor** | no se modifica produccion |
| `test_e2e_una_tarea_que_falla_siempre…` | **D — consecuencia** (`diagnosticar_estado` bloqueado por garantias rotas) | depende de los dos anteriores |

### Auditor de garantias — la formulacion importa

`auditar_garantias` resuelve rutas relativas bajo `walking-skeleton`, por lo que las garantias
ubicadas **fuera** de esa raiz aparecen como `AUSENTE`.

> **Las 23 garantias adicionales no representan 23 garantias perdidas por F4. Corresponden a
> baterias anadidas que el auditor no puede resolver debido a su raiz de resolucion de rutas.**

Se dice **«aparecen ausentes por la resolucion de rutas del auditor»**, nunca «estan perdidas». Es un
**defecto de infraestructura de pruebas**, no un defecto de AURA, y se mantiene separado de la deuda
G-1 y de su consecuencia en el limite de reintentos.

### Verificado en esta sesion (sin repetir lo costoso, porque el codigo no cambio)

Fixture F4 **corregido y sin warning** (`6 passed` con `-W error::RuntimeWarning`) · Communication
Plane **180 passed / 5 skipped** · Control Plane **196 passed** · agente externo **20 passed** ·
ruff **PASS**. Seguridad: OpenCode y Codex **ausentes**, procesos **0**, residuos **0**, credenciales
**0**, sin temporales en el repositorio.

**Sin cambios de codigo en esta sesion. Sin commit. Sin push. D-M8 intacto.**

**PENDIENTE DE GOBERNANZA:** OPCION A (cerrar Linea B con B1+B2 y B3 no alcanzado) u OPCION B (abrir
una via tecnica independiente para B3, partiendo de una hipotesis nueva y sin modificar AURA sin
evidencia de falla propia).

---

# LINEA B — CERRADA (2026-08-25, decision del CEO)

**B1 = GREEN · B2 = GREEN · B3 = NO ALCANZADO.**

**B3 no se considera GREEN ni RED y permanece sin causa determinada.** No existen regresiones nuevas
atribuibles a la linea. Las condiciones que mantienen el Quality Gate en FAIL estan clasificadas y
**separadas de la implementacion funcional de B1/B2**.

### Situacion de B3, tal cual

> B3 no pudo ser alcanzado bajo el entorno/agente utilizado. La investigacion no determino una causa
> ultima. La hipotesis previa sobre operaciones especificas del contenido del canal fue retirada al
> no reproducirse de forma consistente. No existe evidencia suficiente para atribuir el
> comportamiento a AURA ni al agente. No se realizaron modificaciones de produccion para intentar
> forzar el resultado.

**No se anade ninguna hipotesis nueva. No se abre una via B3.**

### Quality Gate = FAIL — los cinco, clasificados

| Fallo | Clase | Causa | Accion |
|---|---|---|---|
| G-1 x3 | **C** — deuda de gobernanza aceptada (`DEC-G1-MANIFIESTO-TRAS-F4 = C`) | — | **ninguna** |
| garantias declaradas | **B** — defecto preexistente del auditor | resolucion incorrecta de rutas fuera de `walking-skeleton` | **pendiente separado** |
| limite de reintentos | **D** — consecuencia | `diagnosticar_estado` bloqueado por garantias rotas | depende de los anteriores |

**Ninguno se presenta como regresion de Linea B.**

### Fixture F4 — cambio valido que se conserva

`walking-skeleton/tests/integration/test_modelo_datos.py`: el callback de retirada espera
correctamente `AlmacenReglas.desactivar()`. **Evidencia: 6 passed con `-W error::RuntimeWarning`.**
Queda funcional.

### Estado del cierre

Quality Gate vigente **FAIL — 5 failed · 1139 passed · 3 skipped · 0 warnings**, **medido previamente
sobre este mismo estado de codigo**; no se reejecuta porque nada cambio desde entonces.

Sin cambios de produccion por B3 · **D-M8 intacto** · seguridad y limpieza correctas · **sin commit**
· **sin push**.

**PENDIENTES SEPARADOS de Linea B:** defecto de resolucion de rutas del auditor de garantias · deuda
G-1 aceptada · una eventual via B3, que si algun dia se abre debera partir de una hipotesis nueva y
no podra modificar AURA sin evidencia de falla propia.

## Siguiente bloque: NO DETERMINADO (2026-08-25)

**No existe un siguiente bloque autorizado determinable desde las fuentes de verdad, y no se
inventa uno.**

- **Linea A**: `DP-D-M-8` **CERRADO**; sin trabajo determinado pendiente.
- **Linea B**: **CERRADA** formalmente.
- **`siguiente_auto()`**: `None`.
- **`pendiente_ordenado`**: todo `DECISION_REQUIRED` del CEO o `WAITING_FOR_QUOTA`.
- **`dp_estado`**: `DP-COMMUNICATION-PLANE-AURORA` y `DP-DEVELOPMENT-ORCHESTRATOR` siguen
  **PROPUESTOS**; **ninguno aprobado**.
- **25 decisiones abiertas**, todas del CEO.

`CLAUDE.md` es explicito: *«Nada se construye sin Decision Package aprobado»*.

### Tres desfases del registro, corregidos con hechos medidos (ninguna decision)

1. `dp_estado.implementacion` afirmaba *«no existe entorno/communication-plane/
   communication_plane.py»* — **existe, 59.983 bytes, y su bateria da 180 passed / 5 skipped**
   `[EJEC]`. La nota era del 2026-08-17.
2. `lineas_de_trabajo.LINEA_B` decia *«B3 bloqueado por Codex (D-CP-1.bis / D-CP-1.ter)»* — **ambas
   estan resueltas**: `.bis` GREEN (`codex-cli 0.149.1` medido) y `.ter` por medicion (Codex exige
   credencial, bloqueado por `D24`). **B3 se cerro por otra razon.**
3. `estado_global_motivo` decia *«Linea B detenida en D-ORCH-5»* — **D-ORCH-5 fue levantado** por el
   CEO y Linea B esta cerrada.

**Se corrigen porque son justamente el patron «declarado != real» que este proyecto ya ha pagado
varias veces:** la proxima sesion habria arrancado sobre premisas falsas.

**Sin cambios de codigo · sin commit · sin push · Linea B no reabierta.**

---

## 10.duodecies · Controles del `§14` + criterios `§22` + deuda del `§21` — CERRADO (2026-08-30)

**La sesión anterior declaró la cola vacía. Era falso.** Lo vacío era la cola de `DEC-ORCH-2`
(`eliminar_codigo_muerto`, y no queda código muerto). Pero **un DP aprobado es un contrato**, y el
cierre de F1 había dejado escrito:

> | A6–A12 | worker, revisor, GitHub, seguridad, cuota, 0/7 | **FUERA DE F1** — dependen de F2–F5, bloqueadas |

F2, F3 y F4 se cerraron después. Solo uno de esos siete criterios seguía dependiendo de F5. **Los otros
seis llevaban semanas autorizados y sin demostrar, y nadie volvió a mirar.** Novena aparición de
`declarado ≠ real`, esta vez en su forma más silenciosa: nadie afirmó nada falso.

Descubrimiento dirigido sobre el perímetro autorizado → **11 tareas reales**, ninguna inventada, cada
una citando el apartado del DP que la ordena. Sin decisión humana nueva.

### Qué se construyó

- **`§14` · kill switch**: `ruta_parada()` / `parada_solicitada()`, consultado en **cada** iteración
  (no solo al entrar), con evento `parada_de_emergencia` y reversible. **No es `ruta_centinela()`**,
  que es el centinela del `flock`: confundirlos habría parado el bucle para siempre.
- **`§14` · tarea equivalente repetida**: `huella_de_tarea()` = `sha256` de *(acción, objetivo,
  ficheros ordenados)*. **Sin el `id`** —la amenaza es trabajo repetido, no id repetido—.
- **`§14` · exclusión mutua**: `mutacion_en_curso()` barre `/proc`; el ciclo se niega y lo registra.
- **`§14.bis` + A12 · criterio mecánico**: `fijar_criterio` (antes de invocar) · `criterio_de`
  (`CriterioAlterado` si cambió) · `verificar_criterio(directorio, id, ejecutor)` **sin parámetro por
  donde entre la afirmación del Worker** · `cerrar_tarea` atado por **huella Y origen**.
- **`§21`**: `CAMPOS_VEREDICTO` se deriva de `revisores.Veredicto`, no de una tupla a mano.

### Dos hallazgos que no se buscaban

1. **`zona_permitida` aceptaba incondicionalmente cualquier ruta bajo `/tmp`.** Un agujero en un
   guardarrail de **producción** abierto para que las pruebas pasaran. **17 pruebas de la batería
   pasaban por él** y creían ejercitar la regla real. Cerrarlo las rompió a las 17 — esa es la prueba
   de que el hueco era real. Ahora un sandbox se **declara** en la llamada, y una prueba vigila que
   ningún módulo de producción escriba ahí una ruta a mano.
2. **`--permission-mode acceptEdits` ANULA `--allowedTools`** para las herramientas de edición, medido
   contra `claude` 2.1.251. El `§14` llama a `--allowedTools` *«control primario `[EJEC]`»* sin
   mencionarlo. El orquestador emite siempre `plan`, así que **nunca estuvo expuesto** — pero nada lo
   impedía: `bypassPermissions` estaba prohibido por su nombre y `acceptEdits` hace lo mismo por otra
   vía. Ahora `permisos_de()` se niega ante cualquier modo fuera de `("plan","default")`.

### Y la cola siguió: `§13` y `§12`

Cerrado el `§14`/`§22`, el mismo método —leer el contrato y medir el código— dio dos filas más:

- **`§13` mecanismo 2**: el `--session-id` derivaba **solo del `tarea_id`**, no del sobre. El DP dice
  `uuid5(namespace, tarea_id + sha256(sobre))` y *«la misma tarea **con el mismo sobre**»*. Dos
  ejecuciones con permisos, presupuesto, criterio o versión de política distintos compartían
  identificador. **Las pruebas que había fijaban lo implementado, no lo acordado** — la deuda del
  `§21` otra vez, en otro sitio.
- **`§12` escritura interrumpida**: una sola línea truncada hacía que `leer_eventos`, `proyectar`,
  `verificar_integridad_log` y **`registrar_evento`** lanzaran `JSONDecodeError` `[EJEC]`. El Control
  Plane entero ilegible, y sin poder anotar siquiera que estaba roto. Ahora la cola truncada se
  descarta (y queda registrada); una línea rota **en medio** lanza `LogCorrupto`, porque eso no es una
  caída sino manipulación.
  **Corregido sobre la marcha**: la primera versión regeneraba el fichero entero, y `§5` dice de C1
  *«nunca: borrarse ni reescribirse»*. Ahora se **trunca**, y una prueba lo comprueba **por bytes**.

### Verificación

**457 passed** (antes 382) · 180/5 · 20 · `ruff` PASS · **170 mutantes en 8 arneses, 0 supervivientes,
0 `NO_APLICADO`** · Quality Gate **FAIL 5/1139/3 = baseline** · `estado.json` intacto · árbol limpio
tras mutar · **0 commits, 0 push**.

La primera pasada dio **7 supervivientes**: 4 huecos reales de cobertura míos, 2 listas de pruebas mal
declaradas por mí, y 1 **equivalente demostrado por ejecución** (`C14-M16`, retirado con su prueba).
Además **4 `NO_APLICADO`** en la regresión de arneses anteriores, todos por patrones que dejaron de
casar con mis cambios: reapuntados y muertos otra vez. `NO_APLICADO` nunca contó como detectado.

**A11 medido `[EJEC]` por primera vez** (`entorno/control-plane/medicion-a11.py`), cada capa con su
caso de control. Cierra las dos filas que `§14.ter` tenía como deuda de verificación.

### Lo que hay que saber para seguir

- **La exclusión mutua se dispara contra el propio arnés** (se lanza como `python -m
  herramientas.mutar`). No es un falso positivo: es el control funcionando. Las pruebas que trabajan
  sobre `tmp_path` **declaran** que no miden el árbol real, con un fixture `autouse` que lo dice por
  escrito. Y la prueba del detector usa una marca **construida en ejecución**: escrita como literal
  aparecía en la línea de órdenes del shell y el barrido la encontraba ahí.
- **Nueva oportunidad bloqueada `OB-5`**: `mutacion_en_curso()` detecta pero **no bloquea**; la mitad
  cooperativa vive en `walking-skeleton/herramientas/mutar.py`, fuera del perímetro de `DEC-ORCH-2`.
- **`max_derivadas` del `§14` NO se implementó**: el orquestador no crea tareas derivadas, así que el
  control no tiene nada que guardar. Es **observación**, no deuda. Construirlo hoy sería fabricar
  trabajo.

### Siguiente trabajo real

Los criterios `A1–A12` están **todos cumplidos**. Lo que queda exige acta del CEO: desbloquear F5
(`D-ORCH-1` + enmienda de D24), ampliar por acta el alcance de `REVIEW`, cerrar `D-ORCH-6`, o autorizar
`OB-2` / `OB-5` (ambas fuera del perímetro, en `walking-skeleton/`).

Cierre completo: [`milestones/m3-entry/CIERRE-CONTROLES-14-Y-CRITERIOS-22.md`](milestones/m3-entry/CIERRE-CONTROLES-14-Y-CRITERIOS-22.md).

---

## 10.terdecies · La auditoría independiente refutó mi cierre de A12 — CORREGIDO (2026-08-30)

**Declaré A12 cerrado en `10.duodecies`. No lo estaba.** Un auditor distinto del implementador
encontró **dos GRAVE**, y los dos son patrones que este proyecto ya tiene escritos en la pared.

| # | Qué | Clase |
|---|---|---|
| **GRAVE 1** | `control_plane.transicion()` cerraba a `COMPLETED` sin criterio mecánico. Mi puerta vivía **solo** en `agentes.cerrar_tarea`, y `transicion()` es la primitiva que usa toda la base, incluida `agentes.py` | **ALERTA-005** · *«ninguna ruta alternativa»* |
| **GRAVE 2** | El aparato del `§14.bis` **no estaba cableado**: nadie llamaba a `fijar_criterio()` antes de invocar, así que `criterio_registrado()` devolvía `None` para toda tarea real y la protección quedaba **inerte** | *«la composición no enciende las automatizaciones»* · `declarado ≠ real` **n.º 10** |
| MEDIO | `zona_permitida(ruta, raiz=…)` concedía el producto: con `raiz` dado dejaba de mirar la zona. Mi arreglo del hueco de `/tmp` había abierto otro con la misma forma | guardarrail sostenido por convención |
| MEDIO | Docstring y excepciones de `orquestador.py` decían *«el catálogo `AUTO` está vacío»*, falso desde `D-ORCH-3` | `INV-9` al revés |

**Por qué mis 34 pruebas no lo veían:** todas entraban por `cerrar_tarea`. **Probé la puerta que yo
había puesto, no el edificio.** La prueba que hoy sostiene A12 —
`test_TODAS_las_vias_publicas_a_COMPLETED_respetan_el_criterio`— no existía por eso.

### Cómo quedó

La regla vive **solo en el motor único**. `cp.transicion()` exige para `COMPLETED`:

- autoridad **no humana** → criterio fijado, ejecutado y **superado**;
- autoridad **humana** → puede cerrar sin criterio (`§14.bis` regla 4: lo no automatizable lo juzga una
  persona), pero **no puede saltarse uno ya fijado**.

`cerrar_tarea` dejó de escribir la regla por su cuenta —tenerla en dos sitios era el defecto del `§0`
de este mismo CHECKPOINT, en su versión cara: **la copia que faltaba era una ruta abierta**—. El bucle
y el circuito de `D-ORCH-3` fijan el criterio **antes** de invocar y registran `criterio_verificado`.

### Verificación tras la corrección

**472 passed** · 180/5 · 20 · `ruff` PASS · **176 mutantes en 8 arneses, 0 supervivientes,
0 `NO_APLICADO`** `[EJEC]` · árbol limpio tras mutar · `0 commits`, `0 push`.

Tres mutantes (`C14-M19/M20/M21`) **retirados con su motivo escrito**: mutaban la regla duplicada que
ya no existe. Su garantía la cubren `AUD-M1`, `AUD-M2` y `AUD-M9`.

### La lección

**Una garantía probada sobre su propia función no es una garantía del sistema.** Se prueba desde la
primitiva que cualquiera usaría, recorriendo **todas** las vías públicas. Y el proceso funcionó como
está diseñado: lo encontró un auditor independiente. *«El que implementa nunca audita su propio
trabajo»* no es burocracia — aquí fue la diferencia entre un control real y uno declarado.

---

## 10.quaterdecies · Segunda auditoría + cola del `§12` — CERRADO (2026-08-30)

### El mismo error, dos veces, en el mismo incremento

Tras la primera auditoría escribí `test_TODAS_las_vias_publicas_a_COMPLETED_respetan_el_criterio` con
esta justificación: *«`ALERTA-005` no se cierra probando una puerta… mi error fue probar la que yo
había puesto»*. **Y enumeré tres rutas a mano.** `completar_tarea` y `fijar_estado_tarea` —declaradas
`GOBERNADAS` desde F1, al mismo nivel que `transicion()`— quedaron fuera. La segunda auditoría cerró
una tarea con autoridad no humana en un intento.

**La corrección de fondo no fue añadir las dos que faltaban** —eso solo aplaza la tercera vez—:

- `FUNCIONES_GOBERNADAS` y `NO_CONCEDEN_ESTADO` viven ahora en `control_plane.py`, **una sola vez**.
- El barrido **consume la lista entera** y falla si la tabla de intentos diverge de ella.
- Las dos listas son **disjuntas** —lo destapó el mutante `AUD2-M4`: una función en ambas se restaba
  del barrido sin que nada fallara—.
- Un meta-control detecta cualquier función que nombre `COMPLETED` sin estar clasificada.

Y como `completar_tarea`/`fijar_estado_tarea` trabajan sobre el modelo **en memoria**, sin log donde
comprobar un criterio, exigen **acto humano** para `COMPLETED`. Inventarles una verificación habría
sido fingirla.

### Los otros hallazgos

| # | Qué | Cierre |
|---|---|---|
| GRAVE | forjar `criterio_fijado`/`criterio_verificado` en crudo cerraba la tarea | los tres eventos que conceden estado son `EVENTOS_GOBERNADOS`, cada uno con su puerta |
| MEDIO | `zona_permitida` sin `raiz` no resolvía symlinks: un enlace al producto pasaba | resuelve enlaces también en su forma por defecto |
| OBS | `test_..._otro_origen_no_cierra` era **decorativa**: nadie lee `veredicto["origen"]` | reescrita sobre la garantía real — el motor mira el **log**, no el diccionario |
| OBS | `test_A9_...` invocaba `cp.informe()`, **función inexistente**, tras un `if` siempre falso | medía 3 salidas creyendo medir 4; ahora las cinco se ejecutan |

### Cola del `§12` consumida — tres filas declaradas y sin implementar

- **Tarea ejecutada dos veces**: `sesion_ejecutada` en el log + `sesion_ya_ejecutada()`. El bucle no
  reejecuta la misma tarea con el mismo sobre, y **sí** la reejecuta si el sobre cambia. Vive en el
  historial, no en memoria: el caso que `§12` cubre es el proceso que se murió.
- **Respuesta de revisor duplicada**: `review_id` **derivado** del expediente. La segunda se descarta
  y **manda la primera** — si mandara la última, cambiar un veredicto sería volver a responder.
- **Respuesta perdida**: reintento **acotado** → `DECISION_REQUIRED`. Escalar **no es aprobar**
  (`1.1:85`); esperar en silencio para siempre era la peor de las tres opciones.

### Verificación

**493 passed** (antes 472) · 180/5 · 20 · `ruff` PASS · **193 mutantes en 9 arneses, 0 supervivientes,
0 `NO_APLICADO`** `[EJEC]` · Quality Gate **FAIL 5/1139/3 = baseline**, mismos 5 ids · árbol de
`entorno/control-plane/` limpio tras mutar · **0 commits, 0 push**, HEAD `790fafc`.

`F1-M22` sobrevivió una pasada por **defensa en profundidad** —dos capas cubrían su garantía— y se
reapuntó a la comprobación que solo cubre la suya. Un superviviente sin explicación es indistinguible
de un hueco, así que no se acepta ninguno «porque ya está cubierto de otra forma».

### Alcance de «árbol limpio», con precisión

Lo limpio es `entorno/control-plane/`. `walking-skeleton/aura_skeleton/` tiene modificaciones sin
commitear **anteriores a esta sesión** (investigación del razonador, `mtime` 2026-08-25), ajenas a este
incremento y no tocadas aquí. La segunda auditoría pidió esa precisión y tiene razón.

---

## 10.quindecies · Tercera auditoría + `§8.3` cableado + `§11` — CERRADO (2026-08-30)

**Tercera vez que la misma pregunta encuentra algo, y cada vez un nivel más abajo de donde miré.**

| # | Qué | Clase |
|---|---|---|
| **GRAVE** | `_registrar_evento_gobernado` aceptaba **cualquier** tipo: escribiendo un `estado_de_tarea` con `valor="COMPLETED"` se cerraba una tarea sin autoridad ni criterio, con la cadena de hashes intacta | **ALERTA-005**, tercera aparición |
| **GRAVE** | `registrar_sesion` se llamaba **antes** de invocar. Como `invocar()` se niega **siempre** hoy, **toda tarea `AUTO` quedaba marcada «ya ejecutada» en su primer intento sin haberse ejecutado nunca** | defecto **funcional vivo**, introducido por mí doce horas antes |
| MEDIO | `revisores.pedir_revision` —`§8.2`/`§8.3`, con degradación y escalada— no lo llamaba ningún módulo de producción | *«el aparato no estaba enchufado»*, otra vez |

**Mi meta-control no podía ver el primero**, y por tres motivos a la vez: descartaba lo que empieza
por `_`, descartaba lo que no fuese función suelta, y **solo miraba dentro de `control_plane.py`**.
La vía que abrió la auditoría era **exactamente** una función privada. Ahora recorre los siete módulos
del plano, privadas y métodos incluidos, y busca el estado **también por su constante** —la auditoría
demostró que una función hostil puede escribir `ESTADO_FINAL = "COMPLETED"` y no aparecer en un `grep`
del literal—.

**Y el barrido ampliado destapó algo por su cuenta**, sin que nadie lo buscara: `registrar_criterio_fijado`
aceptaba la **huella como parámetro**, así que dos llamadas legítimas encadenadas fijaban un criterio
con huella arbitraria y verificaban esa misma. La puerta la deriva ahora.

### Lo demás cerrado

- **`§8.3` en la ruta real**: `ejecutar_bajo_review` fabricaba el veredicto sin comprobar que hubiera
  revisor capaz. Ahora, sin revisor, **espera y no toca el fichero**.
- **`§11`**: *«`UNKNOWN` nunca se convierte en `WAITING_FOR_QUOTA`»*. Vía única `esperar_por_cuota()`,
  que exige ventana determinada **y** evidencia observada. `WAITING_FOR_QUOTA` **afirma** que una
  cuota concreta bloqueó y que se renovará; con `UNKNOWN` eso sería fabricar una explicación.
- **Una prueba decorativa mía más**: el barrido llamaba a `registrar_bloqueo_de_cuota` con los
  argumentos desordenados, así que se negaba por firma inválida y no por la garantía.

### Residual declarado — donde se lea, no en el docstring de una prueba

`_registrar_sin_lock` escribe el fichero y **no se puede gobernar desde dentro del proceso**: quien
pueda importarla puede también abrir `eventos.jsonl` con un editor de texto. Fingir lo contrario sería
`declarado ≠ real`. Lo que **sí** se garantiza:

1. **Ninguna ruta pública** concede estado sin gobierno — probado, y es lo que cerraron las tres auditorías.
2. La cadena `sha256` es **verificable**: una escritura cruda no pasa desapercibida; lo que no puede es impedirse.
3. El worker **no tiene** permiso de escritura sobre `entorno/control-plane/` — criterio A6, medido `[EJEC]`. Ese es el actor del que este diseño protege.

### Verificación

**514 passed** (antes 493) · 180/5 · 20 · `ruff` PASS · **205 mutantes en 10 arneses, 0 supervivientes,
0 `NO_APLICADO`** `[EJEC]` · Quality Gate **FAIL 5/1139/3 = baseline** · árbol de
`entorno/control-plane/` limpio tras mutar · **0 commits, 0 push**, HEAD `790fafc`.

### Nueva oportunidad bloqueada · `OB-6`

**Dos contratos de `Veredicto`** para lo mismo: tres campos en `autoconstruccion`, cinco en
`revisores` (`§8.2`). `INV-7` dice que el plan se interpreta **en un solo punto**. No se unifica
porque tocar el circuito que el CEO aprobó y vio funcionar es peor riesgo que la duplicación.
**Condición que lo promueve:** el día que una tarea `REVIEW` necesite algo que solo da el contrato de
cinco campos.

---

## 10.sedecies · Cuarta auditoría — CERRADO (2026-08-30)

**Dos afirmaciones mías eran falsas, y las dos estaban escritas en `§10.quindecies`.**

| # | Qué | Mi afirmación |
|---|---|---|
| **GRAVE** | `transicion()` aceptaba `WAITING_FOR_QUOTA` con solo autoridad y causa | *«`esperar_por_cuota` es la única vía»* — **no lo era** |
| **GRAVE** | `guardar()`/`actualizar_estado()` persistían un `COMPLETED` fabricado: `validar_tareas` comprobaba que los campos de gobierno **estuvieran**, no lo que decían | *«Ninguna ruta pública concede estado sin gobierno — probado»* — **tampoco** |

La segunda importa más de lo que parece: **`render_handoff()` lee de ese modelo**, y es de lo que
depende el Protocolo de Continuidad de `CLAUDE.md`. Un relevo habría presentado como terminado un
trabajo fabricado.

Y la diferencia con `_registrar_sin_lock` —que sí declaré residual— es la que la auditoría fue a
buscar expresamente: **este era cerrable en proceso**. Declarar irreducible algo que se puede cerrar
es la forma cómoda del `declarado ≠ real`.

### Tres MEDIO, también míos

- El **revisor nombrado a mano** no se validaba: se podía emitir un veredicto en nombre de alguien sin
  ficha. No alcanzable desde el ciclo real, pero es un contrato público que alguien usaría mal.
- El barrido seguía ciego a **`functools.partial`** y a las **clases anidadas**.
- **`MODULOS_DEL_PLANO` era una tupla escrita a mano** — el defecto exacto que llevo cuatro auditorías
  corrigiendo, cometido una vez más al arreglarlo la vez anterior. Ahora sale del **directorio**.

### La secuencia, que es la lección

Cuatro auditorías, cuatro veces la misma clase de agujero, **cada una un piso más abajo**: el
llamante → la lista escrita a mano → la puerta interna → el borde de persistencia. Ampliar la lista
una quinta vez solo aplaza la quinta auditoría; lo que cambió es **de dónde sale la lista de sitios
donde mirar**.

Tres mutantes sobrevivieron por **doble cobertura** —el motor ya rechazaba, así que quitarle la
comprobación al envoltorio no cambiaba el estado final—. No se aceptaron: se reapuntaron a lo que
**solo** cubre esa capa —que no quede escrita en el historial una observación de cuota que nadie
observó—. Un superviviente «cubierto de otra forma» que no se explica es indistinguible de un hueco.

### Verificación

**527 passed** (antes 514) · 180/5 · 20 · `ruff` PASS · **215 mutantes en 11 arneses, 0
supervivientes, 0 `NO_APLICADO`** `[EJEC]` · Quality Gate **FAIL 5/1139/3 = baseline** · árbol de
`entorno/control-plane/` limpio tras mutar · **0 commits, 0 push**, HEAD `790fafc`.

El documento de cierre (`milestones/m3-entry/CIERRE-CONTROLES-14-Y-CRITERIOS-22.md`) estaba dos
auditorías atrás —lo señaló la cuarta— y se ha puesto al día: su `§2.quater` cuenta las cuatro.

---

## 10.septdecies · MOTOR DE AUTONOMÍA — AURA descubre su propio trabajo (2026-08-31)

**El cambio de esta sesión no es una tarea más: es que Claude deja de ser quien entrega la siguiente.**

`ciclo_autonomo(directorio, **ficheros**, ...)` recibía la lista de ficheros desde fuera. **Ese
parámetro era el traspaso manual**: alguien —hasta ahora, la asistencia externa— decidía dónde mirar.
El ciclo sabía encadenar tareas; no sabía de dónde salen.

### Lo construido

| Módulo | Qué hace | Qué **no** hace |
|---|---|---|
| `descubrimiento.py` | 5 fuentes mecánicas · 4 clases · 8 piezas obligatorias por oportunidad | no decide autoridad |
| `planificador.py` | oportunidad autorizada → tarea; id **derivado**; sin duplicados; orden por riesgo | no ejecuta |
| `motor_autonomia.py` | encadena, redescubre en cada vuelta y para con motivo | **no ejecuta**: eso sigue en `review.ejecutar_bajo_review` |
| `aura.py` | punto de entrada acotado **que termina** | no es un demonio (`§23` lo prohíbe) |

**Descubrir trabajo no es concederse autoridad**, y por eso son dos decisiones separadas. De ahí las
cuatro clases: `OPORTUNIDAD_REAL` se ejecuta · `BLOQUEADA` se registra y **no** · `DECISION_REQUIRED`
se eleva · `FALSO_HUECO` se descarta **con su motivo**.

**No existe la rama «si no hay tareas → inventar una».** `siguiente()` devuelve `None`, y eso es una
respuesta completa. Una cola vacía dejó de significar *«no puedo hacer nada»* y significa *«no hay
trabajo autorizado ahora mismo»* — con las cuentas delante.

### Cómo lo usa AURA sin Claude

```bash
cd entorno/control-plane
python3 aura.py diagnosticar                  # qué ve, sin tocar nada
python3 aura.py trabajar --max-tareas 5       # una vuelta acotada, y termina
```

Códigos de salida: **0** trabajo hecho o cola agotada · **2** parada que alguien debe mirar · **3**
arranque roto. **Cola agotada sale 0 a propósito**: tratarla como error empujaría a quien lo automatice
a fabricar trabajo para que «pase».

Quien lo invoca es cosa de fuera —`cron`, un hook, una persona—. **No Claude**: si Claude fuera el
planificador, la autonomía no residiría en AURA.

### Evidencia, no declaración

- **Encadenado real** `[EJEC]`: sobre un árbol de tres módulos, AURA **descubrió** 3 oportunidades por
  su cuenta, ejecutó las 3, borró las funciones muertas, conservó las vivas, 4 vueltas,
  `actos_humanos_durante_el_ciclo = 0`. Efecto observable en disco, no estados internos.
- **Sobre el plano real** `[EJEC]`: 7 oportunidades · 0 ejecutables · 6 bloqueadas · 1 elevada
  (`D-ORCH-6`) → **`COLA_AGOTADA`**, salida 0.
- **El cero está medido**: 11 ficheros y 33 funciones privadas examinadas, 0 muertas. Es el detector
  corriendo, no un detector roto.

### Un defecto que solo apareció al ejecutarlo

El descubridor leía `decision_pendiente` **del log** y no las `decisiones_pendientes` de
`estado.json`, así que **`D-ORCH-6` le pasaba desapercibida**: decía «0 decisiones» con una registrada
desde hacía días. Lo destapó ejecutar el diagnóstico contra el plano real, no leerlo.

### Verificación

**558 passed** (antes 527) · 180/5 · 20 · `ruff` PASS · **238 mutantes en 12 arneses, 0
supervivientes, 0 `NO_APLICADO`** `[EJEC]` · Quality Gate **FAIL 5/1139/3 = baseline**, mismos 5 ids ·
árbol limpio tras mutar · **0 commits, 0 push**, HEAD `790fafc`.

Cuatro supervivientes diagnosticados: dos por **redundancia mutua** entre las comprobaciones del
constructor —solo se distinguen con una fuente hecha de espacios, que es lo que sale de rellenar el
campo por obligación—, uno **equivalente demostrado por ejecución** (`MOT-M6`, retirado con su prueba)
y uno **hueco real de cobertura mío**: ninguna prueba del motor corría sin revisor capaz, así que la
rama del `§8.3` —*«no se autoaprueba jamás»*— no se ejercitaba nunca.

### Siguiente trabajo AUTO_EXECUTABLE

**`NO_HAY_TRABAJO_AUTORIZADO`**, medido y registrado. Lo que hay son 6 oportunidades **bloqueadas**
(`OB-1`…`OB-6`) y 1 **decisión** (`D-ORCH-6`), todas esperando acta.

**La próxima oportunidad real se tomará sola**: no hace falta que nadie la entregue.

---

## 10.duodevicies · Auditoría del motor — tres GRAVE, todos míos (2026-08-31)

| # | Qué | Por qué importa |
|---|---|---|
| **GRAVE** | El meta-control decía *«la fuente apunta a algo que se puede ir a mirar»* y **solo comprobaba que la cadena no estuviera en blanco**. `fuente="de la nada"` producía una oportunidad **ejecutable** | la barrera contra inventar trabajo estaba en la disciplina de las cinco fuentes, no en la clase |
| **GRAVE** | `test_la_fuente_APUNTA_a_algo...` **no habilitaba `REVIEW`**, así que nunca había `OPORTUNIDAD_REAL`, el `continue` se disparaba siempre y **el `assert` no se ejecutaba jamás** | era justo la prueba que debía sostener lo anterior. **Séptima decorativa** de esta serie |
| **GRAVE** | `zona_permitida(x, raiz=<raíz del repo>)` concedía planos vecinos (`entorno/agente-externo/`). El docstring decía *«`raiz` solo puede ESTRECHAR»* | garantía documentada que no sostenía el código, sino la convención de que hoy hay un único llamador |

**Y el MEDIO que más duele:** `actos_humanos_durante_el_ciclo` se inicializaba a `0` y **no se
incrementaba nunca**. Era una constante que las pruebas leían como si fuera una medición — y es **la**
cifra que decide si esto es autonomía o teatro. Ahora se cuenta del historial, desde el `seq` del
arranque: los actos anteriores al ciclo no cuentan (el acta la firma el CEO **antes**, y contarla haría
que ningún ciclo pudiera dar 0).

Dos pruebas más resultaron decorativas: una prometía «ordena por riesgo» y solo medía pertenencia
—todas las oportunidades de código muerto traen el mismo riesgo, así que invertir el orden no cambiaba
nada—, y un `assert descubiertas >= 0` trivialmente cierto para cualquier entero.

**El arnés también acertó**: marcó un mutante `AMBIGUO` porque yo había declarado una prueba que **no
existía en ese fichero**. `AMBIGUO` nunca cuenta como éxito, y aquí evitó dar por medida una garantía
que nadie medía.

### Verificación

**564 passed** · 180/5 · 20 · `ruff` PASS · **244 mutantes en 12 arneses, 0 supervivientes,
0 `NO_APLICADO`, 0 ambiguos** `[EJEC]` · Quality Gate **FAIL 5/1139/3 = baseline** · árbol limpio ·
**0 commits, 0 push**, HEAD `790fafc`.

`python3 aura.py trabajar` sobre el plano real: **`NO_HAY_TRABAJO_AUTORIZADO`**, salida 0, 7
descubiertas · 6 bloqueadas · 1 elevada · **0 actos humanos**.

---

## 10.undevicies · AUTONOMÍA OPERATIVA — AURA ya puede trabajar sin Claude (2026-08-31)

**No existía ningún mecanismo para despertarla** `[EJEC]`: `crontab` vacío, sin timers de `systemd`,
sin hooks, y nada en el repositorio invocaba `aura.py`. El motor sabía trabajar; le faltaba quién lo
llamara.

### La trampa que había que evitar

Es facilísimo que **el que despierta acabe decidiendo**. Un despertador que consulta la cola para saber
si merece la pena arrancar, que reintenta cuando no hubo trabajo, o que decide cuántas tareas tocan
hoy, ha dejado de ser un despertador: es un planificador externo, y la autonomía se habría mudado
fuera de AURA **sin que nadie lo declarase**.

Por eso las garantías del despertador son **negativas**, y se prueban leyendo su `AST`:

| El despertador… | Comprobado |
|---|---|
| **no** importa `descubrimiento` ni `planificador` | no puede mirar la cola |
| **no** llama a `transicion`, `guardar`, `actualizar_estado` | no tiene autoridad |
| **no** tiene bucles, esperas ni reprogramación | `§23`: no es un demonio |
| **no** interpreta el informe de AURA | lo devuelve tal cual |
| el tope viene de fuera pero está **acotado a 10** | un despertador mal configurado no es un demonio |

Lo único que sí le toca decidir son **dos condiciones de seguridad, no de trabajo**: el kill switch, y
que no esté corriendo `herramientas.mutar` — porque con el árbol mutado, AURA trabajaría sobre
mutantes y registraría como hecho un trabajo sobre código que no existe.

### Cómo se despierta

```bash
entorno/scripts/despertar-aura.sh --max-tareas 3      # una vuelta, y termina
entorno/scripts/despertar-aura.sh --instrucciones     # imprime la línea de cron
touch entorno/control-plane/PARADA                    # parada fuera de banda
```

**La línea de `cron` NO está instalada.** Programar trabajo en la máquina del CEO es una decisión de
operación, no de código, y la propia FASE 8 exige `0 residuos`. Está impresa y lista.

### Evidencia

- **Tres despertares seguidos**, como haría un `cron`: `descubiertas=7 · ejecutadas=0 ·
  actos_humanos=0 · cola agotada`, salida **0** en los tres `[EJEC]`.
- **Parada fuera de banda**: con `PARADA`, rechaza con salida **2** y lo registra; retirada, vuelve a
  despertar `[EJEC]`.
- **Rastro**: 5 `aura_despertada` · 1 `despertar_rechazado` · 14 `descubrimiento_realizado` ·
  9 `ciclo_detenido`.

### Verificación

**574 passed** (antes 564) · 180/5 · 20 · `ruff` PASS · **253 mutantes en 13 arneses, 0
supervivientes, 0 `NO_APLICADO`, 0 ambiguos** `[EJEC]` · Quality Gate **FAIL 5/1139/3 = baseline** ·
árbol limpio · `PARADA` retirado · **0 commits, 0 push**, HEAD `790fafc`.

### Lo que AURA puede y no puede hacer sola

**Puede**: despertarse (cuando algo la llame), descubrir de cinco fuentes, clasificar en cuatro clases,
validar autoridad con el acta, planificar sin duplicados, ejecutar por el circuito gobernado, verificar
efecto, registrar y encadenar hasta agotar la cola o el tope.

**No puede**, y es deliberado: ampliar su perímetro, aprobar decisiones, tocar D24/Bible/ADR/roadmap,
convertir trabajo bloqueado en autorizado, ni inventar trabajo cuando no lo hay.

**Hoy no hay**: 0 ejecutables · 6 bloqueadas · 1 elevada. `NO_HAY_TRABAJO_AUTORIZADO`, medido.

---

## 10.vicies · DESPERTADOR INSTALADO — AURA operativa sin Claude (2026-08-31)

Por **autorización expresa del CEO**, instalado en su `crontab`:

```
*/30 * * * * <worktree>/entorno/scripts/despertar-aura.sh --max-tareas 3 >> /tmp/aura-despertar.log 2>&1
```

Servicio `cron`: **activo** `[EJEC]`. El `crontab` estaba vacío, así que no se pisó nada.

### Comprobado antes de instalar

Punto de entrada = el probado (10/10) · la instalación **no modifica código** · `§23` respetado (0
bucles, sin `sleep`/`Thread`/`Timer`/`fork`) · `--max-tareas 3` ≤ `TOPE_MAXIMO 10` ≤
`motor.MAX_TAREAS 25`.

### Comprobado después — ejecutando **literalmente** lo que ejecutará el cron

Lanzado con `env -i` y `PATH` mínimo, como lo hará `cron`: **salida 0**. AURA arrancó, descubrió de
sus cinco fuentes, decidió y terminó. `descubiertas=7 · ejecutadas=0 · actos_humanos=0 · cola agotada`.

**El despertador no decidió nada, y el orden de los eventos lo demuestra:**

```
seq 88  motor_iniciado
seq 89  descubrimiento_realizado   (5 fuentes — es AURA quien mira)
seq 90  ciclo_detenido             (cola agotada)
seq 91  aura_despertada            (el despertador, EL ÚLTIMO: solo anota el resultado)
```

Tareas planificadas por el despertador: **0**. Eventos que registra: solo `aura_despertada` y
`despertar_rechazado`.

**0 procesos residentes** `[EJEC]`: arranca, hace su vuelta y muere.

### Cómo se para y cómo se quita

```bash
touch entorno/control-plane/PARADA    # fuera de banda: no hace falta tocar el cron
crontab -e                            # y borrar el bloque «AURA · despertador»
```

### Riesgo declarado

La ruta apunta al **worktree**, y el código está **sin commitear** (0 commits, todo *untracked*). Si el
worktree se retira antes de integrar a `main`, el cron disparará cada 30 minutos contra una ruta que ya
no existe, y el fallo será silencioso salvo por `/tmp/aura-despertar.log`. Es la única ruta donde el
código existe hoy.

Y una precisión sobre el rastro: `/tmp/aura-despertar.log` es captura de `stdout` y se pierde al
reiniciar. **El historial auditable es `eventos.jsonl`**, que sí es durable y encadenado.
