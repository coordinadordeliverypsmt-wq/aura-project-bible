# CHECKPOINT DE CONTINUIDAD

**Cerrado:** 2026-08-15 · **Rama:** `worktree-m3-entry` · **HEAD:** `c202de5` · **Árbol limpio**
**`main` = `origin/main` = `d933a08`** — el incremento **NO está integrado**, y así debe permanecer
hasta que el CEO lo ordene.

> **Este fichero se escribió por orden expresa del CEO y NO está commiteado**, porque en el mismo
> mensaje prohibió nuevos commits. Existe en disco y sobrevive al cambio de conversación. Para
> hacerlo durable basta:
> `git add CHECKPOINT-CONTINUIDAD.md && git commit -m "docs(checkpoint): cierre del tramo"`

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

## 8.bis · Medición del razonador — APROBADA por el CEO, 2026-08-15. En curso

DP: [`milestones/m3-entry/DP-MEDICION-RAZONADOR-LOCAL.md`](milestones/m3-entry/DP-MEDICION-RAZONADOR-LOCAL.md),
commiteado en `f9c942d`. **Aprobados ambos brazos**, el ensayo con `qwen2.5:0.5b` como baseline
experimental (sin implicación alguna sobre hardware), los casos 4–7 como control de veracidad, y las
dos reglas de gobierno: **prompt congelado** y **0/7 es resultado válido**.

**Orden explícita del CEO:** ejecutar **primero y sólo** el ensayo de humo con `0.5b`. Si revela un
problema del protocolo, **detenerse y corregirlo** antes de gastar la tanda de 30.

**Siguiente paso exacto:** construir el arnés en `milestones/m3-entry/medicion-razonador/` y correr
únicamente el humo.

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
