# Decision Package — AURORA Development Orchestrator

**Estado:** PROPUESTO · **Fecha:** 2026-08-17 · **Decide:** CEO · **Propone:** APUS-5 (asistencia externa)
**Origen:** encargo del CEO de 2026-08-17 — «que Claude Code y el agente revisor/CTO puedan comunicarse
y continuar trabajo autorizado sin que Mauricio tenga que actuar como mensajero entre ambos».
**Clasificación D47:** `[EJEC]` medido ejecutando · `[LECT]` leído · `[INFER]` deducido · `[HIPO]` no verificado.

> ⚠ **ADVERTENCIA SOBRE LAS CITAS AL «ENCARGO», señalada por la auditoría independiente.**
> Este DP cita en varios puntos «§4 / §13 / §20 del encargo» y entrecomilla frases suyas. **El encargo
> es una instrucción conversacional del CEO de esta sesión, NO un artefacto versionado del
> repositorio**: `find . -iname "*encargo*"` no devuelve nada. CLAUDE.md §6 exige citar siempre el
> artefacto verificable y advierte que *«la memoria de la herramienta no es un artefacto del
> proyecto»*.
> **Por tanto: toda referencia a «el encargo» debe leerse como `[HIPO]`, no como `[LECT]`.** Un auditor
> no puede abrirla. Si el CEO quiere que esos requisitos sean verificables, deben quedar registrados
> como acta o como sección de este DP. **Ninguna decisión de §25 depende de esas citas**; sí dependen
> de ellas algunos requisitos de §7.1, §13 y §20, que quedan marcados como origen conversacional.

> **NADA DE ESTE DOCUMENTO ESTÁ IMPLEMENTADO.** Es una fase de diseño. No se creó ningún demonio, no se
> llamó a ninguna API externa, no se instaló nada y no se ejecutó ninguna inferencia. Lo único escrito
> en el árbol son este DP y las pruebas del modelo conceptual descritas en §21.

---

## 0 · Qué es esto, y sobre todo qué NO es

**Es infraestructura de DESARROLLO.** Coordina el trabajo *sobre* AURORA. **No es AURORA y no le
concede ninguna capacidad.** Se somete al mismo listón que ya se impuso el Control Plane
(`entorno/control-plane/README.md:5-15`): vive fuera de `walking-skeleton/`, no importa un solo módulo
del producto, y una prueba lo verifica leyendo el texto del fuente.

**La autonomía de AURORA sigue en 0/7 y este DP no la mueve.** Confundir «autonomía para desarrollar
AURORA» con «autonomía de AURORA» sería, en palabras del propio README del Control Plane, *«el error
más caro posible aquí»*.

**Distinción que gobierna todo el documento:**

| | Qué es | Quién la tiene |
|---|---|---|
| **Autonomía operacional** | ejecutar trabajo ya autorizado sin pedir permiso paso a paso | lo que este DP propone conceder |
| **Autonomía estratégica** | decidir *qué* es correcto, cambiar reglas, ampliar la propia autoridad | **permanece íntegramente en el CEO** |

---

## 1 · El problema, medido `[EJEC]`

Cinco hechos verificados en esta sesión, no supuestos:

| # | Hecho | Evidencia |
|---|---|---|
| **P1** | **El CEO es el bus de mensajes.** Todo intercambio entre el ejecutor y el revisor pasa hoy por una persona copiando texto entre dos ventanas | Modo de trabajo observado en esta misma sesión |
| **P2** | **El Control Plane no tiene bloqueo de concurrencia.** `guardar()` es atómico (`tmp`+`os.replace`+`fsync`) pero no hay lockfile: si dos procesos cargan y guardan, el último gana y el otro **pierde sus cambios en silencio** | `control_plane.py:120`; `grep -nE "lock\|fcntl\|flock"` → **1 acierto y es un falso positivo**: `:298 estado["quota_block"]`, subcadena de «lock». **Ningún mecanismo de bloqueo.** Demostrado además por ejecución en §21 |
| **P3** | **El Control Plane no tiene event log.** `estado.json` se sobrescribe entero en cada guardado. El único rastro histórico es la lista `trabajo_completado` dentro del propio JSON: sin `seq`, sin `sha256`, sin rotación | `control_plane.py:76-94` |
| **P4** | **`fijar_estado_tarea` no valida el estado previo.** Acepta cualquier estado del vocabulario sin comprobar de dónde viene: nada impide pasar de `COMPLETED` a `WORKING` | `control_plane.py:254` |
| **P5** | **Ningún agente de `.claude/agents/` lee ni escribe el Control Plane.** No existe puente entre los agentes y el estado que gobierna el trabajo | grep sobre `.claude/agents/`: 0 referencias a `estado.json` |

**P2, P3 y P4 no son defectos del Control Plane tal como se usa hoy** —un solo agente, en serie, con
un humano mirando—. **Se convierten en defectos el día que haya dos escritores.** Y un orquestador
es, por definición, un segundo escritor.

**El problema real no es «que los modelos hablen».** Es que **hoy no existe un sustrato donde dos
actores puedan escribir sin pisarse, ni un historial que permita reconstruir qué pasó.** Sin eso, un
canal entre modelos es un chat con estado en la memoria de un proceso — exactamente lo que §4 del
encargo prohíbe.

---

## 2 · Objetivo

Que el trabajo **ya autorizado** avance sin que el CEO actúe de mensajero, y que su intervención quede
reservada a lo que de verdad requiere autoridad humana.

**Criterio de éxito, medible:** el número de intervenciones humanas por incremento cae, **y** el número
de decisiones estratégicas tomadas sin el CEO permanece en **cero**. Las dos condiciones a la vez. La
segunda no es negociable: un orquestador que acelera el trabajo ampliando su propia autoridad es un
fracaso del diseño, no un éxito parcial.

---

## 2.bis · Product Demo Preview — qué podrá hacer el CEO al terminar

*(Sección obligatoria por el Principio 1 del estándar de trabajo, `estandar…:27-30`.)*

**Advertencia de honestidad, porque este DP es infraestructura y no producto:** lo que sigue **no es
una conversación nueva con AURORA**. La experiencia de usuario de AURORA **no cambia en absoluto**. Lo
que cambia es la experiencia del **CEO como director del trabajo**.

**Hoy:**

> El CEO abre una sesión. Lee dónde quedó todo. Pide un incremento. Espera. Copia el resultado a otra
> ventana para que lo revisen. Copia la revisión de vuelta. Vuelve a esperar. Si cierra el portátil,
> el hilo se detiene hasta que él vuelva.

**Tras la Fase 1 (event log + lock):**

> El CEO escribe `python3 control_plane.py historia T-042` y ve, en orden y con `timestamp`, qué se
> intentó, qué evidencia se produjo, quién lo hizo y por qué se detuvo — **sin abrir una sesión de
> asistencia y sin gastar un token**. Si dos procesos tocaron el estado, ninguno perdió su escritura.

**Tras la Fase 2 (solo tareas AUTO):**

> El CEO aprueba una lista de tareas y se va. Al volver, `handoff` le dice: tres completadas con su
> evidencia, una detenida en `DECISION_REQUIRED` esperándole **con la pregunta concreta formulada**, y
> ninguna tocó nada fuera de lo autorizado.

**Lo que NO podrá hacer, y conviene decirlo aquí:** no podrá delegar ninguna decisión. Seguirá teniendo
que decidir exactamente lo mismo que hoy; lo que se le ahorra es **el transporte**, no el criterio.

---

## 2.ter · Matriz obligatoria — «Capacidad nueva → Potencia a»

*(Sección obligatoria por el Principio 2, `estandar…:32-35`.)*

| Capacidad nueva | Potencia a | Cómo |
|---|---|---|
| **Event log del plano de desarrollo** (C1) | `CHECKPOINT-CONTINUIDAD.md` | Deja de reconstruirse a mano: la historia se consulta, no se redacta de memoria |
| | Control Plane | `estado.json` pasa a ser proyección reconstruible → cumple ADR-0023 por su propio criterio |
| | Auditorías independientes | El auditor lee hechos con `timestamp` en vez de reinterpretar conversaciones |
| **Lock + transiciones gobernadas** (C2) | Control Plane | Cierra P2 y P4: soporta un segundo escritor sin corromperse |
| | Los 4 agentes de `.claude/agents/` | Podrían escribir estado sin pisarse — hoy ninguno lo toca |
| **Sobre mínimo suficiente** (§7.1) | Todo incremento futuro | Menos contexto por tarea → más trabajo por ventana |
| **Idempotencia por `--session-id`** (§13) | Protocolo de continuidad | Un relevo interrumpido deja de arriesgar trabajo duplicado |
| **Presupuesto por tarea** (C7) | Gobierno de coste | Hace acotable lo que hoy no lo es, **sin** afirmar cuota |
| **Política versionada** (C6) | ADR-0003 / `permissions.py` | Extiende al plano de desarrollo la disciplina que el producto ya tiene |

**Ninguna fila potencia una capacidad de AURORA.** Todas potencian el proceso de construirla. **0/7 sin
cambios** — y esa es exactamente la línea que este DP no cruza.

---

## 3 · Estado actual verificado `[EJEC]`

### 3.1 · Lo que existe y se reutiliza

| Pieza | Estado | Uso en este diseño |
|---|---|---|
| `entorno/control-plane/control_plane.py` | 523 líneas, 66 pruebas en verde | **Autoridad operacional. Se extiende, no se sustituye** |
| Vocabulario de estados | `WORKING · WAITING_FOR_QUOTA · WAITING_FOR_ENVIRONMENT · DECISION_REQUIRED · WAITING_FOR_HUMAN · COMPLETED · FAILED · WAITING_FOR_NEXT_TASK` | Se conserva íntegro |
| `debe_ejecutar()` · `completar_tarea()` idempotente | probados | Base de la idempotencia (§13) |
| Estado por tarea + decisiones que bloquean solo lo que declaran | probado | Base del paralelismo (§9) |
| Dos ventanas de cuota independientes | probado | Base de §11 |
| `CHECKPOINT-CONTINUIDAD.md` | autoridad narrativa | **Manda sobre el estado observado** |
| Protocolo de transiciones del producto | `estado_operativo.py:44-58` | **Patrón a replicar** (no importable) |
| `AuditLog` con `seq`, `fsync`, rotación sellada, `sha256` | `observability.py:64-152` | **Patrón a replicar** (no importable) |
| `.githooks/pre-push` → Quality Gate | hook activo | Puerta de calidad ya existente |
| `.claude/agents/` (4 agentes) | definidos | Ejecutores especializados ya disponibles |

**Por qué «replicar y no importar»:** `test_el_control_plane_no_importa_nada_del_producto`
(`test_control_plane.py:501`) prohíbe expresamente importar `aura_skeleton` desde la infraestructura de
desarrollo. El patrón está probado en producción; la clase no puede cruzar la frontera. **Esa prueba es
correcta y se respeta.**

### 3.2 · Capacidades reales de Claude Code, verificadas contra el binario instalado `[EJEC]`

Versión **2.1.233**. Todo lo siguiente se comprobó ejecutando `claude --help`, no leyendo documentación:

| Capacidad | Flag verificado | Para qué sirve aquí |
|---|---|---|
| Ejecución no interactiva | `-p` / `--print` | Entregar una tarea y recibir el resultado |
| Salida estructurada | `--output-format text\|json\|stream-json` | Evidencia legible por máquina |
| **Salida validada por esquema** | `--json-schema <schema>` | El resultado **cumple un contrato o falla** |
| **ID de sesión fijado por quien invoca** | `--session-id <uuid>` | **Clave de la idempotencia (§13)** |
| **Tope de gasto** | `--max-budget-usd <amount>` | Presupuesto por tarea (§13 del encargo) |
| Permisos | `--permission-mode` ∈ `{acceptEdits, auto, bypassPermissions, manual, dontAsk, plan}` | Superficie de ejecución acotada |
| Allow/deny de herramientas | `--allowedTools` / `--disallowedTools` | Restricción por tarea |
| Reanudación | `--resume`, `--continue`, `--fork-session` | Continuidad tras caída |
| Aislamiento | `--worktree <name>` | Paralelismo sin pisarse |
| Sin persistir sesión | `--no-session-persistence` | Tareas de solo lectura |
| **Observabilidad de sesiones vivas** | `claude agents --json` | **Reconciliar tareas huérfanas (§12)** |

**Salida real de `claude agents --json`, ejecutada** `[EJEC]`:

```json
[{"pid":1001866,"id":"d6cb894c","cwd":"…/m3-entry","kind":"background",
  "startedAt":1786993309346,"sessionId":"d6cb894c-…","status":"busy","state":"working"}]
```

**Corrección por ejecución — un «declarado ≠ real» evitado a tiempo:** la documentación menciona
`--max-turns`, pero **ese flag NO existe en 2.1.233** (`claude --help | grep -c max-turns` → `0`). Un
diseño que apoyara el límite de iteraciones en él habría fallado al implementarse. El tope de
iteraciones debe imponerlo el orquestador, y el de coste `--max-budget-usd`.

### 3.3 · Lo que NO existe hoy — y no se inventa

- **Ninguna clave de terceros, ningún `.env`, ninguna llamada a API externa** en todo el repositorio.
  El único acierto de `api_key|OPENAI|ANTHROPIC` es un comentario en `requirements.txt:9`.
- **Ninguna implementación de la minimización** que exige ADR-0001 regla 5.
- **Ningún reporte de costes** (`docs/…/1.5:78` reconoce que no está inicializado).
- **Ninguna infraestructura de secretos.**
- **Ningún `.github/`, ningún CI remoto.**
- **Cuota de Claude Code no observable de forma fiable fuera de una sesión interactiva.**

### 3.4 · Entorno de ejecución `[EJEC]`

Linux Mint 22.3 · Python 3.12.3 · `systemd --user` activo · `flock` disponible · `crontab` sí,
`at` no · 3,7 GB de RAM total · remoto `origin` en GitHub por HTTPS, sin CI.

---

## 4 · Arquitectura propuesta

```
                      ┌──────────────────────────────┐
                      │   CEO (autoridad estratégica)│
                      └───────────────┬──────────────┘
                                      │ solo DECISION_REQUIRED
                                      │ y lista roja
        ┌─────────────────────────────▼──────────────────────────────┐
        │  CONTROL PLANE  — autoridad operacional, estado + registro │
        │  estado.json (proyección)  ·  eventos.jsonl (historia)     │
        └─────────────────────────────┬──────────────────────────────┘
                                      │ lee/escribe con lock
                      ┌───────────────▼───────────────┐
                      │  DEVELOPMENT ORCHESTRATOR     │
                      │  bucle finito, sin autoridad  │
                      └───┬───────────────────────┬───┘
                          │                       │
              ┌───────────▼──────┐      ┌─────────▼──────────┐
              │  WorkerAdapter   │      │  ReviewerAdapter   │
              │  → Claude Code   │      │  → revisor         │
              │  EJECUTA         │      │  OPINA             │
              └───────────┬──────┘      └─────────┬──────────┘
                          │                       │
                          └───────────┬───────────┘
                                      ▼
                            EVIDENCIA (artefactos + eventos)
                                      │
                                      ▼
                               CONTROL PLANE
```

### Las cuatro reglas que sostienen la arquitectura

1. **El Orchestrator no tiene autoridad.** Es un bucle que lee estado, invoca adaptadores y registra
   resultados. **No decide qué es correcto.** Materializa; no autoriza.
2. **El Reviewer opina; no autoriza.** Su salida es *evidencia*, nunca un permiso. Un `aprobado` del
   revisor es un dato más en el expediente, con el mismo estatus que la salida de los tests.
3. **La autorización vive en la política, escrita antes y por el CEO** — no en el plan del orquestador
   ni en el juicio de un modelo. **Esto es INV-7 aplicado literalmente**: *«materialización y
   autorización son responsabilidades separadas; la ejecución nunca consulta el plan»*.
4. **Ningún actor puede ampliar su propia autoridad.** §14 lo hace estructural, no confiable.

---

## 5 · Componentes

| # | Componente | Responsabilidad | Nunca |
|---|---|---|---|
| **C1** | **Event log** `eventos.jsonl` | Historia append-only, `seq` monotónico, `fsync`, `sha256` por línea | Borrarse ni reescribirse |
| **C2** | **Extensión del Control Plane** | Lock, transiciones gobernadas, proyección desde el log | Sustituir `estado.json` |
| **C3** | **Orchestrator** (bucle finito) | Leer estado → elegir tarea ejecutable → invocar → registrar | Decidir política, editarse a sí mismo |
| **C4** | **WorkerAdapter** | Traducir tarea → invocación de Claude Code; recoger evidencia | Ejecutar sin permisos declarados |
| **C5** | **ReviewerAdapter** (interfaz) | Pedir revisión y devolver un veredicto estructurado | Autorizar; ser requisito para operar |
| **C6** | **Policy** (fichero versionado) | Mapa acción → AUTO/REVIEW/HUMAN | Ser escrito por C3, C4 o C5 |
| **C7** | **Presupuesto** | Topes por tarea y por ciclo | Inventar cuota |

**C1 y C2 son el 80 % del valor y no requieren ningún servicio externo.** Se pueden construir,
probar y usar sin resolver ninguna de las decisiones pendientes de §25.

---

## 5.bis · Por qué NO es un componente nuevo

*(Obligatorio: «prohibido crear un componente sin demostrar antes que no existe equivalente, que no
puede extenderse uno existente y que aumenta el IMA» — CEO 2026-08-03; regla 13 de ADR-0004; D26.)*

| Pieza | ¿Existe equivalente? | Resolución |
|---|---|---|
| **C1 · event log** | **Sí en el producto** — `AuditLog` (`observability.py:64-152`) con `seq`, `fsync`, rotación sellada y `sha256` | **Se replica el patrón, no se importa la clase.** `test_el_control_plane_no_importa_nada_del_producto` (`test_control_plane.py:501`) lo prohíbe, y esa prueba es correcta. **No existe equivalente fuera del producto** `[EJEC]` |
| **C2 · transiciones** | **Sí en el producto** — `TRANSICIONES` + `TransicionInvalida` (`estado_operativo.py:52-62`), con autoridad y causa obligatorias | Mismo caso: patrón sí, import no. El Control Plane **se extiende**; no se crea otro módulo de estado |
| **C2 · lock** | **No** `[EJEC]` — el único acierto del grep es `quota_block` (subcadena); no existe mecanismo de bloqueo | Se añade `flock`, disponible en la máquina `[EJEC]`. **Sin dependencia nueva** (D26) |
| **C3 · Orchestrator** | **No** `[EJEC]` — grep de «Development Orchestrator» en `*.md`: 0 resultados. No hay diseño previo abandonado | Se crea. Es la única pieza genuinamente nueva |
| **C4 · Worker** | **No**, pero **no hace falta inventar el mecanismo**: el CLI ya ofrece `-p`, `--json-schema`, `--session-id`, `--max-budget-usd` `[EJEC]` | Adaptador delgado sobre capacidades verificadas |
| **C5 · Reviewer** | **Sí, parcialmente** — `.claude/agents/` ya define `auditor-consistencia` y `arquitecto-evaluador` | **Se usan esos.** No se crea un revisor nuevo ni se contrata un proveedor |
| **C6 · Política** | **Sí** — ADR-0003 (verde/roja), D22 (delegación y reservas), `permissions.py:29-83` (criterio por reversibilidad) | **Se instrumenta la existente.** §10 no inventa política; la hace legible por máquina |
| **C7 · Presupuesto** | **No**, y no puede reutilizarse la cuota porque **no es observable** `[EJEC]` | Se añade acotado a coste por tarea |

**Conclusión:** de siete componentes, **cuatro son patrón replicado o política existente**, uno es un
adaptador sobre capacidades ya verificadas, y **solo C3 es realmente nuevo**. Un `git mv` no habría
bastado; una extensión del Control Plane, sí — y eso es exactamente lo que se propone.

---

## 5.ter · Conformidad con las garantías, una por una

| Garantía | Cómo se cumple |
|---|---|
| **ADR-0003** — lista roja exige confirmación humana **siempre**, tolerancia cero a falsos negativos | Todo lo que altera producto, política o gobernanza es `HUMAN`. Sin regla → `HUMAN` («ante la duda, roja») |
| **ADR-0003** — niveles superiores de autonomía **solo por decisión del CEO, nunca automáticamente** | `REVIEW` no se activa por este DP: queda bloqueado en §25.2 |
| **`1.1:93`** — *«su autoridad de aprobación no es delegable a ningún agente»* | El `Veredicto` **no tiene campo de autorización**. Estructuralmente ningún modelo puede aprobar |
| **`1.1:85`** — *«el silencio no constituye aprobación»* | Prohibida la autoaprobación por timeout. Sin revisor → se **espera**, no se avanza (§8.3) |
| **ADR-0014 regla 4** — *«ninguna garantía puede depender de que un modelo se comporte como se espera… si no se puede escribir esa prueba, no es una garantía: es una expectativa»* | **El veredicto del revisor NUNCA sustituye al Quality Gate, a las pruebas ni a la mutación.** Se **suma** a ellos como evidencia. Las garantías siguen siendo código determinista |
| **ADR-0023** — historial → proyección; lo derivado no es fuente de verdad | C1 es el historial; `estado.json` pasa a ser proyección **eliminable y regenerable** (criterio de `ADR-0023:82-85`) |
| **INV-7** — materialización ≠ autorización; la ejecución nunca consulta el plan | El plan del Orchestrator **no autoriza nada**. La autorización sale de la política, escrita antes por el CEO |
| **INV-8** — la autonomía nunca escala con la capacidad efectiva | Que el orquestador funcione bien **no amplía** lo que puede decidir. La política es independiente del rendimiento |
| **INV-9** — no se finge capacidad no construida | §3.3 enumera lo que NO existe. El `RevisorExterno` se declara **inerte**, no «disponible» |
| **ALERTA-005** — motor único, sin rutas alternativas; *«una acción autorizada que nadie puede ejecutar debe ser un error explícito, nunca un éxito silencioso»* | Una tarea sin ejecutor capaz → `FAILED` explícito, **nunca** `COMPLETED`. El Orchestrator no inventa rutas: invoca adaptadores declarados |
| **D34** — no se fabrican entornos para aprobar | Las pruebas de §21 son del **modelo conceptual**, declaradas como tales; no simulan un sistema que no existe para declararlo bueno |
| **D47** — clasificación de evidencia y verificación por ejecución | Todo dato de §3 lleva `[EJEC]` o `[LECT]`. `--max-turns` se descartó **por ejecución** |
| **`permissions.py:66-69`** — `proponer_cambio` es **roja**: *«ROJA aunque el cambio se revierta solo si la verificación falla: que sea reversible reduce el daño, no la necesidad de consentimiento»* | Precedente aplicado literalmente: que el orquestador pueda revertir un cambio **no lo autoriza** a hacerlo sin consentimiento |
| **Aislamiento del Control Plane** | El Orchestrator vive fuera de `walking-skeleton/` y hereda las dos pruebas de aislamiento |

---

## 5.quater · Ataque a la propuesta

*(D47 principio 2: la hipótesis se destruye antes de defenderse.)*

| Ataque | Respuesta honesta |
|---|---|
| **«Esto es sobre-ingeniería para un desarrollador con un portátil de 3,7 GB»** | **Ataque parcialmente acertado, y por eso la recomendación es la Fase 1 y parar.** C1+C2 se justifican **sin** orquestador: cierran P2/P3/P4, que son defectos medidos hoy. Las fases 2-5 sí son una apuesta, y se marcan como tal (§25.4) |
| **«Un orquestador acelerará el trabajo equivocado»** | Riesgo real (R2). Mitigación: la política la escribe el CEO, el revisor no autoriza, y la métrica de §2 **exige que la autonomía estratégica siga en cero**. Pero no hay defensa técnica contra una política mal escrita: **esa responsabilidad se queda con el CEO, y se declara** |
| **«El revisor será un oráculo al que nadie contradice»** | Por eso ADR-0014 regla 4 se cita explícitamente: su veredicto **no sustituye ninguna prueba determinista**. Si el revisor dice «conforme» y el Quality Gate dice `FAIL`, **manda el gate** |
| **«Ya existe un canal de ficheros propuesto (DP-CANAL-PERMANENTE)»** | Cierto, y **se reutiliza su razonamiento entero** (§18.1). Aquel DP resuelve CEO↔AURORA (producto); éste, ejecutor↔revisor (proceso). Comparten patrón y no compiten. Si el CEO aprueba aquél primero, este DP **no cambia** |
| **«El event log crecerá y llenará el disco, que ya iba justo»** | Riesgo real y con precedente en este proyecto (el laboratorio de medición llenó el disco). Mitigación: rotación sellada, patrón ya probado. **Debe medirse el crecimiento antes de dejarlo permanente**, igual que exigió el DP del canal |
| **«Dos escritores es un problema que hoy no existe»** | Correcto: **hoy no existe**. Por eso P2/P3/P4 se declaran «defectos ante un segundo escritor», no defectos actuales. **El orden importa**: el lock debe existir *antes* que el orquestador, no después |
| **«Un fichero de estado es falsificable»** | Cierto y ya asumido por el proyecto: el kill switch, que es la defensa última, es igual de falsificable. En un entorno local monousuario, **quien controla la cuenta ya puede escribirlo**. No empeora la postura; la iguala |
| **«¿Y si el CEO deja de leer lo que se hace en su nombre?»** | R8, y es el riesgo más serio de todos porque es humano, no técnico. Mitigación parcial: `DECISION_REQUIRED` **detiene** el trabajo en vez de continuar por defecto. Si el CEO no responde, **no avanza nada** — la omisión es denegación, nunca aprobación (`1.1:85`) |

---

## 6 · Flujo de estados

Se conserva el vocabulario existente y se añade **un solo estado**, `WAITING_FOR_REVIEW`:

```
            ┌──────────────────────────────────────────┐
            ▼                                          │
   WAITING_FOR_NEXT_TASK ──► WORKING ──► WAITING_FOR_REVIEW ──► COMPLETED
            ▲                  │  │              │                (final)
            │                  │  │              └──► DECISION_REQUIRED ──► (solo humano)
            │                  │  │
            │                  │  ├──► WAITING_FOR_ENVIRONMENT ──┐
            │                  │  ├──► WAITING_FOR_QUOTA ────────┤
            │                  │  └──► FAILED ───────────────────┤
            └──────────────────────────────────────────────────-─┘
```

**Transiciones gobernadas, replicando `estado_operativo.py:52-58`:**

```python
TRANSICIONES = {
    "WAITING_FOR_NEXT_TASK": ("WORKING",),
    "WORKING":               ("WAITING_FOR_REVIEW", "WAITING_FOR_ENVIRONMENT",
                              "WAITING_FOR_QUOTA", "DECISION_REQUIRED", "FAILED", "COMPLETED"),
    "WAITING_FOR_REVIEW":    ("WORKING", "DECISION_REQUIRED", "COMPLETED", "FAILED"),
    "WAITING_FOR_ENVIRONMENT": ("WORKING", "FAILED"),
    "WAITING_FOR_QUOTA":     ("WORKING", "FAILED"),
    "DECISION_REQUIRED":     ("WORKING", "FAILED"),   # solo por acto humano registrado
    "WAITING_FOR_HUMAN":     ("WORKING", "FAILED"),   # solo por acto humano registrado
    "COMPLETED":             (),                      # FINAL
    "FAILED":                ("WORKING",),            # reintento explícito y contado
}
```

**`COMPLETED` no figura como origen de ninguna transición.** Es la traducción directa de la garantía
que el producto ya tiene: *«`terminada` y `descartada` son estados finales… antes de esto cualquier
componente podía reabrir una tarea cerrada sin declarar por qué»*.

**Salir de `DECISION_REQUIRED` exige un evento de autoridad humana**, con su registro. Ningún adaptador
puede producirlo.

---

## 7 · Protocolo Claude ↔ Orchestrator

### 7.1 · Lo que Claude Code recibe: el sobre mínimo suficiente

El encargo lo pide explícitamente: *«Claude no debe recibir toda la historia innecesariamente»*.

```json
{
  "tarea_id": "T-042",
  "objetivo": "una frase: qué debe ser cierto al terminar",
  "contexto_minimo": "solo los hechos que no puede deducir del repo",
  "ficheros_relevantes": ["ruta/uno.py", "ruta/dos.py"],
  "restricciones": ["no tocar walking-skeleton/", "no commit", "no push"],
  "permisos": {"allowedTools": ["Read","Grep","Edit(milestones/**)"],
               "permission_mode": "acceptEdits"},
  "precondiciones": ["quality gate en verde", "rama limpia"],
  "resultado_esperado": {"json_schema": {"…contrato de salida…"}},
  "criterio_de_finalizacion": "los tests X pasan y el fichero Y existe",
  "presupuesto": {"max_budget_usd": 0.50, "max_reintentos": 1},
  "stop": "al cumplir el criterio, PARA. No abras trabajo nuevo."
}
```

**El sobre no lleva la historia del proyecto.** Lleva punteros. `CHECKPOINT-CONTINUIDAD.md` sigue
siendo la autoridad narrativa y Claude Code puede leerlo si lo necesita; el orquestador no se lo
inyecta «por si acaso», porque eso es exactamente el consumo de contexto que se quiere reducir.

### 7.2 · Invocación

```bash
claude -p "<sobre>" \
  --session-id "<uuid derivado de la tarea>" \
  --output-format json \
  --json-schema '<contrato de salida>' \
  --allowedTools "…" \
  --permission-mode acceptEdits \
  --max-budget-usd 0.50 \
  --worktree "tarea-T-042"
```

Cada flag está **verificado en 2.1.233** (§3.2). El `--session-id` derivado de la tarea es lo que hace
la ejecución idempotente (§13).

### 7.3 · Lo que devuelve

`{result, session_id, total_cost_usd, usage, structured_output}` más los artefactos escritos en disco.
**La evidencia es el artefacto y el evento, nunca el stdout** — el encargo lo exige y coincide con la
regla del proyecto de que la autoridad viene de la evidencia.

---

## 8 · Protocolo Reviewer ↔ Orchestrator

### 8.1 · Qué se puede hacer HOY, sin inventar nada

**No existe forma de que un proceso local invoque «ChatGPT» desde el filesystem.** Lo que existe:

| Vía | Requiere | Disponible hoy | Nota |
|---|---|---|---|
| **Revisor humano (el CEO)** | nada | **Sí** | Es el modo por defecto. Buzón de ficheros |
| **Subagente de Claude Code** (`.claude/agents/`) | nada nuevo | **Sí** | `auditor-consistencia`, `arquitecto-evaluador` ya existen |
| **Modelo local** (Ollama) | nada nuevo | **Sí, pero inútil hoy** | Medido: FAIL en toda la campaña; 0/7 |
| **API de terceros (GPT u otro)** | clave, red, secretos, minimización | **NO** | Choca con D24/CHECKLIST §5.4 → §25 |

**Consecuencia de diseño, y es la más importante del documento:** el revisor por defecto **no es GPT**.
Es **un subagente de Claude Code con un rol de revisión**, que ya existe, no cuesta una clave nueva y
no abre ninguna decisión pendiente. El `ReviewerAdapter` externo queda como **punto de extensión
inerte** hasta que el CEO resuelva §25.1.

### 8.2 · Contrato del adaptador

Siguiendo el patrón que el proyecto ya usa (`ModelProvider` en `contracts.py:44-48`), **replicado, no
importado**:

```python
class ReviewerAdapter(Protocol):
    nombre: str
    def revisar(self, expediente: Expediente) -> Veredicto: ...
```

```python
@dataclass(frozen=True)
class Veredicto:
    veredicto: str          # "conforme" | "objeciones" | "rechazo" | "fuera_de_alcance"
    motivos: tuple[str, ...]
    evidencia_citada: tuple[str, ...]   # rutas y líneas; sin cita, no cuenta
    revisor: str
    instante: str
    # NO existe campo "autoriza". Deliberadamente.
```

**Implementaciones previstas:** `RevisorSubagente` (hoy), `RevisorHumano` (buzón, hoy),
`RevisorLocal` (Ollama, hoy pero sin capacidad), `RevisorExterno` (**bloqueado**, §25.1).

**Condiciones heredadas de ALERTA-003, que ya las fijó por escrito** para cualquier proveedor de nube:
selección por configuración explícita · minimización previa · **nunca por defecto** · nunca cableado en
el llamador · **con enmienda documentada de D24**.

### 8.3 · Degradación

Si no hay revisor disponible, la tarea que exige revisión pasa a `WAITING_FOR_REVIEW` y **espera**.
**No se autoaprueba jamás.** Las tareas `AUTO` siguen avanzando: el sistema no se detiene entero
porque falte el revisor.

---

## 9 · Integración con el Control Plane

**El Control Plane sigue siendo la autoridad operacional. El Orchestrator es su cliente.**

Tres cambios, todos aditivos:

**9.1 · Event log (C1).** `eventos.jsonl` append-only junto a `estado.json`. `estado.json` pasa a ser
una **proyección reconstruible** del log — exactamente el criterio que ADR-0023 exige de toda
proyección: *«debe poder eliminarse por completo y regenerarse desde el historial sin alterar el
comportamiento»*. Bórralo y se reconstruye. Eso lo convierte en desechable, no en segunda fuente de
verdad.

**9.2 · Lock (cierra P2).** `flock` sobre un fichero centinela alrededor de leer-modificar-escribir.
Está disponible en la máquina `[EJEC]`. Sin esto, dos escritores se pisan en silencio.

**9.3 · Transiciones gobernadas (cierra P4).** `fijar_estado_tarea` pasa a validar el estado previo
contra la tabla de §6 y a exigir **autoridad y causa**, como ya hace el producto.

**Propiedades que se conservan, y que ya están protegidas por pruebas:**

| Propiedad | Se conserva porque |
|---|---|
| Tarea A bloqueada → B independiente continúa | `debe_ejecutar` mira `bloquea`, que declara a quién afecta |
| A en `DECISION_REQUIRED` → B continúa si no depende de A | igual |
| A en `WAITING_FOR_QUOTA` → B continúa si no consume cuota | el presupuesto es por tarea |
| `COMPLETED` no se repite | `debe_ejecutar` + `COMPLETED` sin transiciones de salida |
| `DECISION_REQUIRED` no se resuelve solo | solo un evento de autoridad humana lo levanta |

**Si el estado y el checkpoint discrepan, manda el checkpoint.** Sin cambios.

---

## 10 · Autoridad y permisos

### 10.1 · La política ya existe — se instrumenta, no se inventa

El encargo dice: *«No inventes una política nueva si ya existe una equivalente»*. **Existe:**

| Fuente | Qué aporta |
|---|---|
| **ADR-0003** | Lista **verde** (automática) y lista **roja** (confirmación humana **siempre**, tolerancia cero a falsos negativos) |
| **D22** | El CEO **ya delegó** en el CTO la aprobación de ejecución, con tres criterios: (1) que no cambie el alcance, (2) que respete todas las decisiones previas, (3) las cinco preguntas de D21 |
| **D22 (reservas)** | **No delegado**: selecciones de tecnología con alternativas, todo guardrail ético, toda decisión de rango 1, **toda Alerta de Arquitectura** |
| **D21** | Cinco preguntas; si alguna sale negativa → **ALERTA DE ARQUITECTURA obligatoria** |

### 10.2 · Matriz propuesta

| Nivel | Origen en la política existente | Ejemplos | Quién ejecuta |
|---|---|---|---|
| **AUTO** | lista verde (ADR-0003) | tests, lint, formato, análisis, documentación, tareas ya aprobadas nominalmente | Worker, sin preguntar |
| **REVIEW** | criterio ejecutivo delegado por **D22** | refactors, cambios no triviales, experimentos ya autorizados | Worker ejecuta, Reviewer opina, **Control Plane registra** |
| **HUMAN** | lista roja + reservas de D22 | arquitectura, Bible, ADR, políticas, `n`, protocolo experimental, benchmark congelado, todo `DECISION_REQUIRED` | **Solo el CEO** |

**La política vive en un fichero versionado que ningún componente del orquestador puede escribir.**
Si no hay regla para una acción, **la acción es HUMAN**. Es la aplicación literal de *«ante la duda,
roja»*.

### 10.3 · Advertencia que el CEO debe leer antes de aprobar

**Primero, lo que YA está decidido y no admite diseño alternativo** `[LECT]`:

> *«Su autoridad de aprobación **no es delegable a ningún agente**»* — `1.1:93`
> *«El silencio o la ausencia de objeción **no** constituye aprobación: solo la aprobación explícita del
> CEO cambia el estado de un documento normativo»* — `1.1:85`

**Ningún modelo puede aprobar nada.** El diseño lo cumple por construcción: el `Veredicto` carece de
campo de autorización y ninguna espera vencida produce un «aprobado».

**Segundo, lo que NO está decidido.** `REVIEW` no existe hoy como nivel: ADR-0003 define **dos** listas,
no tres, y fija que *«los niveles superiores de autonomía solo se habilitan por política y decisión del
usuario/CEO, nunca automáticamente»*. Y D22 delegó en un **CTO humano**.

La pregunta residual, ya acotada, es **más estrecha** que «¿puede un modelo aprobar?» (eso está
respondido: **no**). Es: *¿puede el veredicto de un modelo ser **condición previa** para que el
orquestador ejecute una tarea que el CEO clasificó como `REVIEW`, sin que el CEO intervenga en esa
ejecución concreta?* No lo resuelvo: **§25.2**.

**Tercero, un precedente que apunta al núcleo del asunto** `[LECT]`. El catálogo de permisos ya
clasificó el caso más parecido —`proponer_cambio`, «AURORA propone cambios sobre su propio código»—
como **roja**, con este razonamiento (`permissions.py:66-69`):

> *«ROJA aunque el cambio se revierta solo si la verificación falla: que sea reversible **reduce el
> daño, no la necesidad de consentimiento**»*

En cambio, las capacidades que **solo examinan** —`ejecutar_pruebas`, `verificar_calidad`,
`auditar_garantias`, `diagnosticar_estado`— son **verdes**. Esa frontera ya trazada —*leer y medir es
verde; proponer cambios de código es rojo*— es la guía más fiable para poblar §10.2, y sugiere que
`AUTO` debería empezar siendo **casi exclusivamente lectura y medición**.

---

## 11 · Cuota — SHORT_4H30 y WEEKLY

**`usage_known = false` se mantiene.** Verificado `[EJEC]`: no hay forma fiable de conocer la cuota
restante fuera de una sesión interactiva. El módulo **nunca** afirma cuánto queda.

**Distinción que el diseño necesita, y que es real:**

| Concepto | Observable | Uso |
|---|---|---|
| **Cuota de la cuenta** | **NO** | `UNKNOWN`. Nunca se estima |
| **Coste de una invocación** | **SÍ** — `total_cost_usd` y `usage` en la salida JSON `[EJEC]` | Presupuesto operacional (§13 del encargo) |

Un presupuesto operacional **no es** conocimiento de cuota. Se puede topar el gasto por tarea sin
saber cuánto queda en la cuenta.

**Ante evidencia real de agotamiento** se registra: `timestamp` · `mensaje exacto observado` · `tarea` ·
`último checkpoint` · `estado` · `ventana afectada` ∈ `{SHORT_4H30, WEEKLY, UNKNOWN}` · `evidencia` ·
`siguiente acción segura`.

**Reglas que no se tocan:** una ventana **no** arrastra a la otra · renovación de `SHORT_4H30` **≠**
renovación de `WEEKLY` · si no puede determinarse la ventana, `UNKNOWN` · `UNKNOWN` **nunca** se
convierte en `WAITING_FOR_QUOTA` · desconocer la cuota no es tenerla (trabajo barato sí, caro no).

---

## 12 · Recuperación

| Fallo | Detección | Respuesta |
|---|---|---|
| Claude Code cerrado / terminal cerrado | `claude agents --json` no lista la sesión `[EJEC]` | Tarea `IN_PROGRESS` sin evidencia → `FAILED`, reejecutable. **Nunca `COMPLETED`** |
| Máquina reiniciada | `estado.json` + `eventos.jsonl` en disco | Reconciliación al arrancar: toda tarea en curso sin evidencia → `FAILED` |
| Orchestrator detenido | es un bucle finito, sin estado en memoria | Se relanza y lee el log |
| Revisor no disponible | timeout del adaptador | `WAITING_FOR_REVIEW`. **Nunca autoaprobación** |
| Internet caído | fallo de red | Solo afecta a `REVIEW` externo. `AUTO` sigue |
| GitHub no disponible | fallo de push | **Nada se detiene**: GitHub es espejo, no fuente (§15) |
| Cuota agotada | mensaje observado | `WAITING_FOR_QUOTA` **con evidencia**; ventana `UNKNOWN` si no consta |
| Proceso muerto a mitad | evento `TASK_STARTED` sin `TASK_COMPLETED` | `FAILED` + reintento contado |
| Escritura de evidencia interrumpida | `sha256` de la línea no cuadra / línea truncada | Línea descartada del log, tarea `FAILED` |
| Respuesta del revisor perdida | sin evento `REVIEW_COMPLETED` | Reintento acotado, luego `DECISION_REQUIRED` |
| Respuesta duplicada | mismo `review_id` | Segunda descartada por idempotencia |
| Tarea ejecutada dos veces | mismo `--session-id` derivado | Detectada; la segunda no se registra |

**Invariante duro:** *una tarea `IN_PROGRESS` cuya evidencia no demuestra finalización **NUNCA** se
convierte automáticamente en `COMPLETED`.* Ya está protegido por `interrumpir()` y se extiende.

---

## 13 · Idempotencia

Cuatro mecanismos, en capas:

1. **`debe_ejecutar()`** — una tarea `COMPLETED` no se reejecuta. Ya existe y está probado.
2. **`--session-id` derivado** — `uuid5(namespace, tarea_id + sha256(sobre))`. La misma tarea con el
   mismo sobre produce el mismo identificador: la doble ejecución es **detectable**, no una cuestión de
   disciplina.
3. **`completar_tarea()` idempotente** — completar dos veces no duplica. Ya existe y está probado.
4. **Eventos con `seq` + clave natural** — un evento repetido se reconoce y descarta al proyectar.

**`COMPLETED` exige evidencia que demuestre el criterio de finalización.** Sin ella, `FAILED`. Un
`COMPLETED` falso es el fallo más caro de un relevo: el siguiente lector da por hecho un trabajo que
nunca ocurrió y nadie vuelve a mirarlo.

---

## 14 · Seguridad contra bucles autónomos

**Este es el apartado crítico. Los controles son estructurales, no confianza.**

| Amenaza | Control |
|---|---|
| **Bucle infinito** | Bucle **finito por construcción**: `max_iteraciones` por ciclo. Sin trabajo elegible → `WAITING_FOR_NEXT_TASK` y **sale** |
| **Tarea repetitiva** | `debe_ejecutar` + idempotencia + detección de tarea equivalente repetida (misma huella) |
| **Claude cambia su propia autorización** | **Control primario `[EJEC]`:** el sobre nunca concede `Edit` sobre la política ni sobre `entorno/control-plane/`; `--allowedTools` y `--disallowedTools` existen y acotan por tarea. **Control secundario `[LECT]`, NO verificado por ejecución:** un hook `PreToolUse` con `exit 2` bloquearía la acción. ⚠ Esta segunda capa está **leída, no medida**, y es deuda de verificación declarada — ver §14.ter |
| **El revisor se autoautoriza** | `Veredicto` **no tiene campo de autorización**. Estructuralmente no puede conceder permisos |
| **Una tarea crea tareas sin límite** | Las tareas derivadas nacen en `DECISION_REQUIRED` si superan `max_derivadas`; profundidad de derivación acotada y registrada |
| **Escalada de permisos** | Permisos **por tarea**, mínimos, declarados en el sobre. Sin `bypassPermissions` en ningún flujo automático |
| **Modificar el propio Control Plane** | `entorno/control-plane/` y la política en la **lista de rutas prohibidas** al worker. Cambiarlos es `HUMAN` |
| **Modificar Bible/ADR/decisiones** | `HUMAN`, sin excepción |
| **Ejecutar una tarea bloqueada** | `debe_ejecutar` se consulta **antes** de cada invocación, no al planificar |
| **Kill switch** | Fichero centinela consultado en **cada** iteración. Replica el patrón ya aprobado y en producción (`kill_switch.py:29-31`), *«mecanismo fuera de banda»* según Bible 5.3 |
| **Medir mientras el árbol está mutado** | **Exclusión mutua global sobre el worktree.** `herramientas.mutar` muta los ficheros **en el sitio**: mientras corre, el árbol NO contiene el código real. Ya ocurrió — una auditoría midió el producto en paralelo y estuvo a un paso de reportar como rota la garantía INV-9, que estaba sana. Para el orquestador **no es una preferencia: es un lock que impide toda otra tarea**, y si hay que medir en paralelo se hace sobre una copia exportada (`git archive`), nunca sobre el worktree |
| **Autoaprobación por silencio** | Prohibida por `1.1:85`. Ningún timeout produce «aprobado»: produce `WAITING_FOR_REVIEW` indefinido o `DECISION_REQUIRED` |

**Regla de cierre, con la precisión que exigió la auditoría independiente:** *el componente C3 no
puede conceder autoridad porque no tiene ninguna primitiva para hacerlo* — eso es cierto y es
estructural. **Pero la propiedad del componente no se hereda automáticamente al sistema compuesto**, y
afirmarlo sin matiz sería el mismo error que ALERTA-005 documentó: *«las pruebas pasaban porque
verificaban la pieza, no el sistema»*. Ver §14.bis.

### 14.bis · El hueco que encontró la auditoría — quién verifica al que verifica

**Defecto de diseño detectado por auditoría independiente, no por el autor** `[LECT]`:

> En el diseño de §7, **el Worker escribe la evidencia y nadie contrasta de forma independiente que
> esa evidencia demuestre el `criterio_de_finalizacion`.** El Quality Gate —única verificación
> determinista del proyecto— corre en `pre-push`, es decir **al publicar, no por tarea**. Una tarea
> podía llegar a `COMPLETED` sobre lo que el propio ejecutor afirma haber verificado.

Eso viola el principio que el proyecto ya tiene escrito: *«el que implementa nunca audita su propio
trabajo»*, y es exactamente el vector de auto-certificación que había que cerrar.

**Corrección incorporada al diseño — el criterio de finalización debe ser MECÁNICO:**

1. **El `criterio_de_finalizacion` lo fija quien crea la tarea, nunca quien la ejecuta**, y se escribe
   en el event log **antes** de invocar al Worker. Un criterio añadido o alterado después es inválido.
2. **El criterio debe referenciar una CAPACIDAD REGISTRADA del catálogo**, gobernada por el Motor
   Único —`ejecutar_pruebas`, `verificar_calidad`—, **nunca una orden libre del sistema operativo**.
   Sigue siendo ADR-0014 regla 4 aplicada al orquestador —*«si no se puede escribir esa prueba, no es
   una garantía: es una expectativa»*—, pero lo verificable se nombra **por el resultado**, no por la
   herramienta.

   > **Modificada por decisión del CEO el 2026-08-23 (`D-CP-4` = alternativa C).** La redacción
   > anterior exigía *«un comando verificable de terceros»* y contradecía `CLAUDE.md` (CEO
   > 2026-08-03): *«AURORA nunca ejecuta instrucciones arbitrarias del sistema operativo: solo
   > CAPACIDADES registradas»*. El CEO autorizó cambiar **únicamente esta regla**; las reglas 1, 3 y 4
   > quedan intactas y `CLAUDE.md` no se toca. **La contradicción queda así resuelta a favor de
   > `CLAUDE.md`.**
   >
   > **Lo que esta regla NO resuelve, y se declara:** los **argumentos** con que se invoca la
   > capacidad siguen sin esquema —`D-CP-6`, hueco R-1—. Acotar *qué* se ejecuta no acota *con qué*.
3. **Lo ejecuta el Orchestrator, no el Worker**, tras la invocación y contra el árbol resultante.
   `COMPLETED` **exige que ese comando pase**; la afirmación del Worker no basta y no se consulta.
4. **Si el criterio no es expresable como comando, la tarea no es `AUTO`.** Sube a `REVIEW` o a
   `HUMAN`. Una tarea cuyo éxito solo puede juzgarse leyendo prosa **no es automatizable** por
   definición, y pretender lo contrario es fabricar la apariencia de verificación.

**Consecuencia honesta:** esto reduce el alcance de lo automatizable, y es lo correcto. Coincide con el
precedente de `permissions.py`: lo verde es lo que se puede *medir*.

**Riesgo residual que NO cierra esta corrección, y se declara:** si `D-ORCH-2` se resolviera
permitiendo que un subagente de Claude Code haga de revisor de un Worker que es Claude Code, revisor y
ejecutado comparten proveedor y modo de fallo. **La composición sí tendría una ruta de
auto-certificación IA↔IA** aunque ningún componente aislado la tenga. Por eso el criterio mecánico del
punto 3 es innegociable: es lo único de la cadena que **no** depende de un modelo.

### 14.ter · Deuda de verificación declarada — lo que este DP NO midió

**El apartado §14 se titula «controles estructurales, no confianza». Una parte de él es, hoy, lectura.**
Declararlo es obligatorio (INV-9: no se finge capacidad no construida).

| Control | Estado | Qué falta |
|---|---|---|
| `--allowedTools` / `--disallowedTools` acotan la superficie | `[EJEC]` los flags existen en 2.1.233 | Medir que una escritura fuera de la allowlist **falla de verdad** |
| Hook `PreToolUse` con `exit 2` bloquea una acción | **`[LECT]`, no medido** | **Ejecutarlo contra un intento real de escritura prohibida.** Es la única barrera citada contra autoescalada y **no está verificada** |
| El kill switch detiene el bucle | `[LECT]` por analogía con `kill_switch.py`, que sí está en producción | Medirlo en el bucle del orquestador |

**Criterio de aceptación añadido (A11):** *ninguna de estas tres capas se declara operativa hasta
haberse medido con un intento real de violación que falle.* Un control de seguridad citado de
documentación y nunca ejecutado es exactamente el patrón «declarado ≠ real» aplicado a la seguridad —
el sitio donde más caro sale.

---

## 15 · Git y GitHub

| Función | GitHub | Local |
|---|---|---|
| Fuente operacional | **NUNCA** | **Control Plane** |
| Auditoría | espejo útil | `eventos.jsonl` |
| Backup | sí | — |
| Handoff entre máquinas | sí | fichero |
| Revisión / PR | posible más adelante | — |
| Historial | sí | log + git |

**Si GitHub no está disponible: no pasa nada.** El ciclo continúa entero; solo se pospone el espejo.
Esa es la diferencia entre canal de coordinación y fuente de verdad, y es también la lectura correcta
de D37: lo prohibido es la **dependencia funcional**.

**No se propone CI remoto.** El Quality Gate ya corre en `pre-push` y es un hook activo. Añadir CI es
una dependencia nueva y D26 exige beneficio medible demostrado.

---

## 16 · Funcionamiento offline

**El sistema completo funciona sin Internet, salvo el revisor externo — que no es el revisor por
defecto (§8.1).**

| Componente | Sin red |
|---|---|
| Control Plane, event log, políticas | **funcionan** |
| Orchestrator | **funciona** |
| Worker (Claude Code) | necesita red **para su propio servicio**, ajeno a este diseño |
| Revisor subagente | igual que el worker |
| Revisor humano | **funciona** |
| Revisor local (Ollama) | **funciona** (sin capacidad útil hoy) |
| Espejo GitHub | se pospone, no bloquea |

---

## 17 · Riesgos

| # | Riesgo | Gravedad | Mitigación |
|---|---|---|---|
| **R1** | **Confundir autonomía de desarrollo con autonomía de AURORA** | **Alta** | §0 explícito + pruebas de aislamiento + 0/7 declarado en cada informe |
| **R2** | El orquestador acelera el trabajo **equivocado** | Alta | La política la escribe el CEO; `REVIEW` no autoriza; métrica de §2 exige *ambas* condiciones |
| **R3** | Dos escritores corrompen el estado | Alta | Lock (§9.2) **antes** de cualquier segundo escritor. **Es prerrequisito, no mejora** |
| **R4** | Dependencia de un proveedor externo para revisar | Alta | Adaptador sustituible; revisor por defecto no externo; D21 pregunta 2 |
| **R5** | Coste descontrolado | Media | `--max-budget-usd` verificado + topes por ciclo |
| **R6** | El event log crece sin límite | Media | Rotación sellada, patrón ya probado en `observability.py` |
| **R7** | Sobre-ingeniería: construir un orquestador para un solo desarrollador | **Media-alta** | Fases (§20): C1+C2 primero, que valen por sí solas. **Si el CEO para tras la Fase 1, lo entregado sigue siendo útil** |
| **R8** | El CEO deja de leer lo que se hace en su nombre | Alta | El handoff sigue siendo legible por humano; `DECISION_REQUIRED` obliga a parar |
| **R9** | Fuga de contenido del repo a un tercero | Alta | Sin revisor externo no aplica. Con él, exige minimización — **que no existe** (§3.3) |

---

## 18 · Alternativas consideradas

### 18.1 · Canal de coordinación

| | Persist. | Resil. | Segur. | Latencia | Offline | Recup. | Auditoría | Corrupción | Compl. | Mint | Sin humano |
|---|---|---|---|---|---|---|---|---|---|---|---|
| **A · Ficheros** | **alta** | **alta** | alta | **mín.** | **sí** | **trivial** | **alta** | baja con lock+atómico | **mín.** | **sí** | **sí** |
| **B · Git** | alta | alta | alta | media | sí | alta | **máxima** | baja | media | sí | sí |
| **C · GitHub** | alta | **baja sin red** | media | alta | **NO** | media | alta | baja | alta | sí | sí |
| **D · Ficheros + GitHub** | **alta** | **alta** | alta | mín. | **sí** | alta | **alta** | baja | media | sí | **sí** |
| **E · Daemon** | media | media | media | mín. | sí | media | media | media | alta | sí (systemd --user) | sí |
| **F · API local** | baja | media | media | baja | sí | media | media | media | alta | sí | sí |
| **G · Cola (Redis…)** | media | media | media | baja | sí | media | media | media | **muy alta** | sí | sí |

**Recomendado: D — ficheros como fuente operacional, GitHub como espejo de auditoría y backup.**

**Por qué no un daemon (E), aunque `systemd --user` esté disponible `[EJEC]`:** el proyecto ya rechazó
por escrito un servidor local para el canal CEO↔AURORA, y no por principio sino por coste: *«no aporta
nada que el fichero no dé»*, añade superficie, y **en esta máquina un proceso residente compite con el
modelo por la memoria** — algo medido hasta la saciedad en la campaña del razonador. El Orchestrator se
invoca; no reside. Si más adelante se quisiera periodicidad, `crontab` está disponible `[EJEC]` y no
introduce dependencia nueva.

**Por qué ficheros y no una base de datos:** el kill switch **ya es exactamente esto** — un fichero
consultado con `os.path.exists`, armable desde otro proceso sin reiniciar nada. Es un precedente propio
aprobado y en producción, no una analogía.

### 18.2 · Por qué un simple chat Claude → GPT → Claude es insuficiente

El encargo pide evaluarlo explícitamente. **Cinco razones, cada una suficiente por sí sola:**

1. **El estado viviría en la memoria de un proceso.** Al cerrarse, desaparece. Viola la regla del
   proyecto de que *toda capacidad importante sobrevive al reinicio de sesión*.
2. **No hay idempotencia.** Sin estado persistente no se puede saber si una tarea ya se hizo: el
   `COMPLETED` falso entra por esa puerta.
3. **No hay trazabilidad.** El encargo exige poder reconstruir tarea, estado anterior, resultado,
   evidencia, decisión, agente, timestamp, siguiente acción, motivo de bloqueo y **autoridad**. Un chat
   deja transcripción, no expediente.
4. **La conversación se convierte en la autoridad.** Lo que dos modelos acuerdan pasaría a ser el plan.
   Eso es exactamente lo que INV-7 separa: el plan no autoriza.
5. **No hay frontera de permisos.** En un chat, «te autorizo» es una frase. En este diseño, la
   autorización es una entrada de una tabla que ninguno de los dos puede escribir.

---

## 19 · Recomendación

**Construir C1 (event log) y C2 (lock + transiciones gobernadas) primero, y detenerse ahí a evaluar.**

Razones:

- **Cierran defectos reales y medidos hoy** (P2, P3, P4), que existen **con o sin** orquestador.
- **No requieren ninguna decisión pendiente**: ni clave, ni proveedor, ni nivel de autonomía nuevo.
- **Valen por sí solas** aunque el CEO no apruebe nunca el resto: dan historia auditable y estado
  seguro frente a dos escritores.
- **Sin ellas, cualquier orquestador es peligroso**: un segundo escritor sobre un estado sin lock ni
  historia es el generador perfecto de «declarado ≠ real».

**El revisor por defecto debe ser un subagente de Claude Code o el propio CEO, no un proveedor
externo.** Es lo único que no abre decisiones nuevas y ya está disponible.

---

## 20 · Fases de implementación

| Fase | Qué | Depende de | Valor si se para aquí |
|---|---|---|---|
| **F1** | **C1 + C2**: event log, lock, transiciones gobernadas, proyección reconstruible | nada | **Alto**: cierra P2/P3/P4 |
| **F2** | **C3 + C4**: Orchestrator (bucle finito) + WorkerAdapter, solo tareas **AUTO** | F1 | Alto: ejecuta trabajo aprobado sin mensajero |
| **F3** | **C6 + C7**: política versionada + presupuestos | F2 | Medio |
| **F4** | **C5** con `RevisorSubagente` / `RevisorHumano` | F3 + **§25.2** | Medio |
| **F5** | `RevisorExterno` | **§25.1 + enmienda de D24** | **Bloqueada** |

**Cada fase se cierra con Decision Package propio, RED→GREEN→mutación→Quality Gate→auditoría
independiente**, según el protocolo vigente. Este DP autoriza *diseñar*, no construir.

---

## 21 · Pruebas necesarias

**Del modelo conceptual — ESCRITAS Y EN VERDE** `[EJEC]`:
`entorno/control-plane/test_modelo_orquestador.py`, **39 pruebas, 0 fallos, `ruff` PASS**. Junto a las
66 del Control Plane: **105 en verde**. Demuestran los invariantes **antes** de que exista una línea
del orquestador. Sin red, sin procesos persistentes, sin APIs externas, sin inferencias.

**Dos de ellas no verifican el modelo: demuestran los defectos que §1 afirma** — porque una afirmación
de defecto sin un caso que falle es una opinión:

- `test_p2_dos_escritores_concurrentes_pierden_una_escritura` — lanza **dos procesos reales** que
  cargan y guardan el mismo estado. **Una de las dos escrituras se pierde, sin error.** La prueba
  documenta que el día que el Control Plane gane un lock, **esta prueba fallará, y eso será la señal de
  que P2 está cerrado**.
- `test_p4_hoy_se_puede_pasar_de_completed_a_working_sin_validacion` — ejecuta el salto prohibido
  contra el código actual y comprueba que **hoy se permite**, y que el modelo propuesto lo impide.

**Defecto encontrado y corregido en las propias pruebas, que merece registrarse:** cuatro de ellas
inspeccionaban su propio fuente buscando términos prohibidos y **se encontraban a sí mismas** — la
lista literal vivía en el fichero inspeccionado. Es el mismo patrón que produjo ≥4 falsos PASS en la
historia del proyecto. Corregido concatenando los términos y descartando las líneas que los construyen.
También se eliminó una aserción decorativa (`... or True`, siempre cierta).

**Verificación de las verificaciones, hecha por la auditoría independiente** `[EJEC]`: inyectó
`import socket`, `while True`, `ab_format` y `cuota_restante` en copias del fichero y **las cinco
pruebas de auto-inspección detectaron la mutación**. No son decorativas. Y repitió la prueba de P2
**diez veces** comprobando el `exitcode` de ambos procesos: los dos terminan en 0 y aun así se pierde
consistentemente una escritura — **la condición de carrera es real, no un proceso que falló al
arrancar**.

**Limitación declarada de una de las pruebas.** `test_el_veredicto_no_tiene_ningun_campo_de_autorizacion`
compara dos tuplas escritas a mano **en el mismo fichero y por el mismo autor**: no existe todavía una
clase `Veredicto` real contra la que contrastar. Tiene caso de control —añadir `"autoriza"` la hace
fallar, comprobado por la auditoría— pero **su poder de detección frente a una implementación futura
que se desvíe es nulo**. Cuando C5 se implemente, esta prueba debe apuntar a la clase real o se
convierte en decoración. Queda como deuda explícita del DP, no como garantía.

| # | Invariante demostrado |
|---|---|
| 1 | `COMPLETED` no tiene transiciones de salida: una tarea terminada no se reabre |
| 2 | Salir de `DECISION_REQUIRED` exige un evento de autoridad humana |
| 3 | Una tarea `IN_PROGRESS` sin evidencia **nunca** llega a `COMPLETED` |
| 4 | Dos escritores concurrentes sin lock **pierden** una escritura (demuestra P2) |
| 5 | El mismo sobre produce el mismo `session-id` derivado (idempotencia) |
| 6 | Una tarea bloqueada no impide avanzar a otra independiente |
| 7 | El `Veredicto` del revisor no puede conceder autorización (no existe el campo) |
| 8 | El bucle es finito: sin trabajo elegible, termina |
| 9 | Una acción sin regla en la política se clasifica `HUMAN` |
| 10 | `usage_known` permanece `false`; ningún porcentaje de cuota aparece jamás |
| 11 | Una ventana de cuota no arrastra a la otra |
| 12 | El estado se reconstruye íntegro desde el event log (proyección desechable) |

**De la implementación futura (no ahora):** mutación sobre el cableado, no solo sobre la lógica — el
mutante *«la composición no enciende las automatizaciones»* sobrevivió con 426 pruebas en verde.

---

## 22 · Criterios de aceptación

**Comportamiento demostrado, nunca «las pruebas pasan».**

| # | Criterio | Cómo se demuestra |
|---|---|---|
| **A1** | El estado se reconstruye completo tras borrar `estado.json` | borrarlo, reproyectar, comparar |
| **A2** | Dos procesos concurrentes no pierden escrituras | dos procesos reales, contar eventos |
| **A3** | Una tarea completada no se reejecuta ni tras reinicio | ejecutar, matar, relanzar |
| **A4** | Una tarea interrumpida queda `FAILED`, nunca `COMPLETED` | `SIGKILL` a mitad |
| **A5** | `DECISION_REQUIRED` no se resuelve sin acto humano registrado | intentarlo por todas las vías del código |
| **A6** | El worker no puede escribir la política ni el Control Plane | intentarlo y ver el bloqueo |
| **A7** | Sin revisor, `AUTO` sigue avanzando y `REVIEW` espera | desconectar el revisor |
| **A8** | Sin GitHub, el ciclo completo funciona | desconectar la red |
| **A9** | Ningún informe afirma un porcentaje de cuota | prueba que falla ante cualquier insinuación |
| **A10** | La autonomía de AURORA sigue en **0/7** | medición existente, sin cambios |
| **A11** | **Ningún control de seguridad se declara operativo sin un intento real de violación que falle** | ejecutar la violación (escritura fuera de allowlist, hook `PreToolUse`, kill switch) y ver que se bloquea |
| **A12** | **`COMPLETED` solo tras ejecutar el criterio mecánico**, no tras la afirmación del Worker | falsear la evidencia del Worker y comprobar que la tarea NO se completa |

---

## 23 · Qué NO debe implementarse todavía

1. **Nada, hasta que el CEO apruebe este DP.**
2. **El `RevisorExterno`** — bloqueado por §25.1.
3. **El nivel `REVIEW` ejercido por un modelo** — bloqueado por §25.2.
4. **Ningún daemon ni watcher permanente.** El Orchestrator se invoca y termina.
5. **Ningún CI remoto.** D26 exige beneficio medible.
6. **Ninguna gestión de secretos.** No hace falta mientras no haya revisor externo.
7. **Ninguna capacidad del producto.** Este DP no toca `walking-skeleton/`.
8. **Ninguna automatización que escriba Bible, ADR, `decisiones/` o la política.**
9. **Ninguna integración con el experimento A/B.** `EXP-REPRO`, `EXP-CAMPANA`, `ANALISIS-AB`, `n=3`,
   los casos A–E y el instrumento **quedan intactos**.

---

## 24 · Retorno sobre Tokens

- **Hoy cada relevo entre ejecutor y revisor consume una intervención humana y un contexto nuevo.** Con
  el sobre mínimo (§7.1), el worker recibe punteros en vez de historia: **menos contexto por tarea**.
- **Hoy una tarea repetida por error se paga entera.** La idempotencia por `--session-id` derivado la
  hace detectable: **el trabajo duplicado deja de gastarse**.
- **Hoy no hay tope de gasto por tarea.** `--max-budget-usd` está verificado `[EJEC]`: **el coste pasa
  a ser acotado por diseño**.
- **Hoy reconstruir «qué pasó» exige releer conversaciones.** El event log lo responde con `grep`:
  **cero tokens**.
- **Riesgo honesto en sentido contrario:** un orquestador **puede aumentar** el consumo si multiplica
  ciclos de baja calidad. Por eso el presupuesto y el tope de iteraciones son parte del diseño, no un
  añadido, y por eso la métrica de §2 exige que la intervención humana baje **sin** que suba la
  autonomía estratégica.

---

## 25 · DECISIONES ESTRATÉGICAS QUE NO RESUELVO — `DECISION_REQUIRED`

Conforme al §20 del encargo y al régimen de cambio del proyecto, se registran sin resolver.

### 25.1 · `D-ORCH-1` — ¿Alcanza D24 a la infraestructura de desarrollo?

**Contradicción documental genuina, verificada:**

| Permite | Prohíbe |
|---|---|
| `adr/0001:41` — la nube puede usarse para *«(a) consultar modelos de IA»* | `acta:170` (D24), cláusula final **sin ámbito**: *«no se solicitan claves de API ni soluciones propietarias salvo justificación arquitectónica documentada y aprobada»* |
| `adr/0001:47,52` — regla 5 presupone envío a modelos externos con minimización | `CHECKLIST-CONTINUIDAD.md:237` — *«ni adoptar claves de terceros (D24)»*, enunciado plano |
| `acta:357` (D37) — *«local-first no es local-only»* | `adr/0019:65-66` — *«sin proveedor real: no se añaden credenciales, llamadas de red…»* |

La única delimitación de alcance escrita —*«D24 aplica al stack de ejecución, no al alojamiento del
código»* (`revisiones/2026-07-21-revision-pre-M3.md:94`)— **no tiene rango de acta** y resuelve GitHub,
no esto.

**Precedente procedimental:** ALERTA-003 ya dictaminó que incluso la vía correcta para un proveedor de
nube exige *«enmienda documentada de D24»*.

**Nota de D21:** un revisor atado a un proveedor responde **NO** a la pregunta 2 (*«¿reduce la
dependencia de un proveedor?»*) → **exige ALERTA DE ARQUITECTURA**, que D22 reserva al CEO.

**Lo que decide el CEO:** si D24 alcanza a la infraestructura de desarrollo; y si procede enmienda o
Alerta de Arquitectura. **Mientras tanto, `RevisorExterno` permanece inerte y el diseño funciona sin
él.**

### 25.2 · `D-ORCH-2` — ¿Puede el veredicto de un modelo condicionar una ejecución `REVIEW`?

**Lo que NO se pregunta, porque ya está decidido** `[LECT]`: si un modelo puede *aprobar*. **No puede**
— `1.1:93`: *«su autoridad de aprobación no es delegable a ningún agente»*. El diseño lo respeta
estructuralmente.

**Lo que sí se pregunta:** el nivel `REVIEW` **no existe** en ADR-0003 (dos listas, no tres), y D22
delegó en un **CTO humano**. ¿Puede el CEO crear un nivel intermedio en el que el orquestador ejecute
una tarea **previamente clasificada por él** tras un veredicto no-objetante de un revisor, sin
intervenir en esa ejecución concreta?

Es una elevación de autonomía y **solo el CEO puede concederla** (*«nunca automáticamente»*). Nota
adicional: el precedente de `permissions.py:66-69` sugiere que, si se concede, debería empezar
restringida a **lectura y medición**, no a modificación de código.

### 25.3 · `D-ORCH-3` — ¿Qué acciones concretas entran en `AUTO`?

La matriz de §10.2 es una **propuesta**. La lista exacta la fija el CEO. Sin lista aprobada, **todo es
`HUMAN`**.

### 25.4 · `D-ORCH-4` — ¿Se construye siquiera?

R7 es real: esto es infraestructura para un equipo de una persona. **La Fase 1 se justifica sola**
(cierra defectos medidos). Las fases 2–5 son una apuesta sobre el volumen de trabajo futuro, y esa
apuesta la hace el CEO.

### 25.5 · `D-ORCH-5` — Autorización de proceso, previa a todo lo demás

**Bloqueo formal detectado** `[LECT]`: `CHECKLIST-CONTINUIDAD.md:235` declara **no autorizado**
*«iniciar cualquier incremento nuevo sin decisión posterior a la revisión estratégica»*, y `:234`
mantiene cerrada la fase de integración.

**Diseñar no lo activa; construir sí.** Aunque el CEO apruebe el contenido de este DP, **la Fase 1
sigue necesitando el levantamiento expreso de esa prohibición**. Se señala para que la aprobación no
se dé por implícita.

### 25.6 · Contradicciones documentales encontradas — se reportan, no se resuelven

| # | Contradicción | Evidencia |
|---|---|---|
| **1** | **Tres taxonomías de rol coexisten y no están reconciliadas**: `1.1:91-97` (CEO/CTO/Architect/EM/Assistant), D47 `:25-30` (Director/Arquitectos/Ingenieros/Operario) y `CLAUDE.md` §2 (Opus/Sonnet/Exploradores/Auditores). **Ninguna contempla un modelo no-Claude con rol.** Un revisor externo no tiene hoy silla en ninguna tabla de autoridad | `[LECT]` |
| **2** | **«Decision Package» no está definido en ninguna parte de la Bible** — `grep -rn "Decision Package" docs/` → **cero resultados**. Existe como práctica en `CLAUDE.md` y como ~19 ficheros, sin plantilla normativa, sin estados normados | `[EJEC]` |
| **3** | **Los estados de DP son inconsistentes entre sí**: `propuesto`, `PROPUESTO — y así permanece`, `propuesta pendiente de aprobación`, `DIRECCIÓN APROBADA`, `APROBADO como documento… la implementación NO está autorizada`. Cinco formulaciones, cuatro semánticas de «aprobado» | `[LECT]` |
| **4** | **«Seis principios» vs «ocho principios»**: el estándar de trabajo se titula *«Los ocho principios»* y enumera 8; los tres añadidos (continuidad, orquestación, reducir dependencia de la herramienta) son precisamente los que más gobiernan a un orquestador | `[LECT]` |
| **5** | **ALERTA-003: índice desfasado.** `decisiones/alertas/README.md:9` la declara *«Activa — pendiente de gate extraordinario»*; el encabezado de la propia alerta dice *«RESUELTA — parche rechazado definitivamente»*. Es justo la alerta relevante para §25.1 | `[LECT]` |

**Ninguna se ha tocado.** Conforme al régimen de cambio (*«detenerse, presentar la evidencia y esperar
decisión explícita del CEO»*), se presentan como evidencia.

---

## 26 · Observaciones registradas, ajenas a este DP

**O-1 · `entorno/control-plane/` no está commiteado** `[EJEC]` y `CHECKPOINT-CONTINUIDAD.md` ya lo
referencia como existente. Si se perdiera el árbol de trabajo, el checkpoint describiría algo que no
está. **No commiteo por orden expresa**; se señala como riesgo de «declarado ≠ real».

**O-0 · Este DP fue auditado de forma independiente antes de presentarse** `[EJEC]`. El auditor
—distinto del autor, conforme a *«el que implementa nunca audita su propio trabajo»*— reejecutó las
comprobaciones, verificó una muestra amplia de citas fichero:línea (**todas exactas**), inyectó
mutaciones en las pruebas para comprobar que detectan, y repitió la prueba de P2 diez veces.

**Resultado: 0 BLOQUEANTES · 3 IMPORTANTES · 1 MENOR · 2 DEUDA.** Los tres IMPORTANTES **están
corregidos en esta versión** y son la razón de que existan §14.bis, §14.ter y la advertencia de la
cabecera:

| Hallazgo | Gravedad | Resolución |
|---|---|---|
| El Worker se autocertifica: nadie contrasta su evidencia | IMPORTANTE | **§14.bis** — criterio de finalización mecánico, fijado antes y ejecutado por el Orchestrator |
| El hook `PreToolUse` es `[LECT]`, no medido, y es la única barrera citada contra autoescalada | IMPORTANTE | **§14.ter** — reclasificado y convertido en criterio A11 |
| Las citas al «encargo» no son verificables: no es un artefacto del repo | IMPORTANTE | **Advertencia en cabecera** — reclasificadas como `[HIPO]` |
| «grep 0 aciertos» no era literalmente exacto (1 falso positivo: `quota_block`) | MENOR | **Corregido en §1 y §5.bis** |
| La prueba del `Veredicto` es autoconsistencia, no verificación | DEUDA | **Declarada en §21** |
| El cierre de §14 sonaba más categórico que el resto del documento | DEUDA | **Matizado**: la propiedad del componente no se hereda al sistema compuesto |

**O-2 · Precedente que este DP debe tener presente** `[LECT]`: `PLAN-DE-FORMACION-AURORA.md:48-53`
registra que una capacidad se declaró aprendida, *«era falsa y la publicó APUS-5… es el patrón
"declarado ≠ real" número 9 del proyecto, y el primero cuyo autor fue la asistencia externa»*.

**El autor de este DP es la misma asistencia externa.** Por eso todo dato de §3 lleva `[EJEC]` o
`[LECT]` con su comando, `--max-turns` se descartó ejecutando en vez de citando, y §21 propone
demostrar los invariantes **antes** de implementar. La contramedida al precedente no es una promesa:
es que cada afirmación de este documento sea verificable por quien lo lea.

---

## 27 · Qué se pide aprobar

1. **El diagnóstico de §1** — P2, P3 y P4 son defectos reales del Control Plane ante un segundo
   escritor. *(Pregunta cerrada: ¿se acepta el diagnóstico?)*
2. **La arquitectura de §4** — Control Plane como autoridad, Orchestrator sin autoridad, revisor que
   opina y no autoriza. *(¿Se acepta la separación?)*
3. **La Fase 1 (§20)** — event log, lock y transiciones gobernadas, **con su propio DP de
   implementación y sin construir nada del orquestador todavía**. *(¿Se autoriza a escribir ese DP?)*
4. **Que el revisor por defecto NO sea un proveedor externo**, sino un subagente ya existente o el
   propio CEO (§8.1). *(¿Se acepta?)*
5. **Resolver o aplazar explícitamente** `D-ORCH-1` … `D-ORCH-5` (§25). *(Cinco respuestas.)*
6. **Levantar o mantener** la prohibición de `CHECKLIST:235` para el caso concreto de la Fase 1
   (§25.5). *(Sin esto, nada puede construirse aunque se apruebe todo lo demás.)*

**Qué tendría que demostrarse para cambiar esta decisión:** que P2/P3/P4 no son alcanzables ni siquiera
con dos escritores (invalidaría la Fase 1); que existe ya un event log fuera del producto
(invalidaría C1); o que el volumen de trabajo no justifica coordinación alguna (invalidaría las fases
2-5, no la 1).

**No se implementa nada hasta que el CEO apruebe.** La autonomía de AURORA permanece en **0/7**.
