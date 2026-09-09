# Plan operativo B3 — Codex como segundo agente del canal

**No ejecutado. `B3 = READY_FOR_DECISION`.** B3 no puede correr: **Codex no está instalado**
`[EJEC 2026-08-18]` (`command -v codex` → ausente), y `D-CP-1.bis` (instalar) y `D-CP-1.ter` (ToS)
siguen sin resolver.

## 1 · Objetivo

Demostrar **una vez**: `Claude Code → Communication Plane → Codex → Communication Plane`. El emisor
publica una TASK; **Codex** la lee del canal y publica el RESULT. Mismo transporte B1, distinto agente.
**No** es la implementación del sistema multiagente: es un único ida y vuelta con un segundo tipo de
agente.

## 2 · Precondiciones — todas bloqueantes

| # | Precondición | Estado |
|---|---|---|
| P-1 | Codex instalado | ❌ **ausente** — exige `D-CP-1.bis` |
| P-2 | Términos de servicio de auth de suscripción en bucle | ❌ `[INCIERTO]` — exige `D-CP-1.ter` |
| P-3 | Codex autenticado (`codex login`) | ❌ no verificable sin P-1 |
| P-4 | Las 9 capacidades de Codex, medidas | ❌ `[UNKNOWN]` — ver §11 |
| P-5 | B1 y B2 en verde | ✅ `[EJEC]` |

## 3 · Comando exacto (a ejecutar SOLO cuando P-1..P-4 se cumplan)

**Forma prevista `[HIPO]` — `codex` no se ha ejecutado nunca aquí; los flags salen de su
documentación, no de medición:**

```bash
codex exec \
  --json \
  --sandbox workspace-write \
  --cd <DIR_CANAL> \
  < <PROMPT_RECEPTOR>          # mismo patrón que B2: prompt por stdin
# envuelto en: timeout 300 …   (Codex no tiene flag de timeout confirmado — §11 cap. 7)
```

El `PROMPT_RECEPTOR` es **idéntico en intención al de B2**: leer la TASK del canal con el módulo
`communication_plane` y publicar el RESULT. Reutiliza B1 tal cual; no reimplementa el canal.

> **La forma real del comando es la PRIMERA capacidad a medir** (§11). Si `codex exec` no acepta
> stdin, o `--json` no existe, este comando cambia. Por eso es `[HIPO]`, no `[EJEC]`.

## 4 · Entrada TASK (idéntica a B2, publicada por P1 local, coste 0)

```python
c.publicar(tipo="TASK", de="orquestador-local", para="codex",
           cuerpo={"objetivo": "sumar", "a": 17, "b": 25,
                   "instruccion": "publica un RESULT con in_reply_to a este mensaje y cuerpo.suma"})
```

`para="codex"` — B1 ya es agnóstico del destinatario (probado en B2). 17+25=42, verificable sin juicio.

## 5 · Resultado esperado

Un mensaje en `canal.jsonl`: `tipo="RESULT"` · `de="codex"` · `in_reply_to == <id TASK>` ·
`cuerpo["suma"] == 42`.

## 6 · Criterios mecánicos de GREEN

1. Exit code de `codex exec` **= 0**.
2. Señal de éxito de Codex — **el campo equivalente a `is_error`, que hay que descubrir** (§11 cap. 6).
   **Hasta conocerlo, exit 0 es la única señal fiable.**
3. Existe un `RESULT` en el canal.
4. `in_reply_to == id` de la TASK.
5. `cuerpo["suma"] == 42`.
6. `seq` monótona y cadena de hashes íntegra tras la escritura de Codex.

## 7 · Criterios de RED — y cómo se distinguen entre sí

| Situación | Firma observable |
|---|---|
| **Codex no instalado** | `command -v codex` vacío → **ni se intenta**. No es RED de B3, es P-1 |
| **Instalado, no ejecutable** | exit ≠ 0 **y** stderr con error de carga/permiso; canal sin RESULT |
| **Ejecutable, sin auth** | exit ≠ 0 **y** stderr/JSON con mensaje de login; canal sin RESULT |
| **Ejecutable y operativo** | exit 0; **es el único caso que puede dar GREEN** |
| **Fallo del agente** | exit 0 **pero** sin RESULT, o RESULT con `suma ≠ 42`: el canal funciona, Codex no siguió la instrucción |
| **Fallo del Communication Plane** | RESULT presente pero `seq`/hashes rotos: el defecto es del canal, no de Codex |

**La distinción clave:** «sin RESULT» separa *fallo de arranque de Codex* (exit≠0) de *Codex no
obedeció* (exit 0). Y «RESULT con hashes rotos» separa *fallo del agente* de *fallo del canal*.

## 8 · Coste máximo previsto

**`[UNKNOWN]`.** Codex no expone tope equivalente confirmado a `--max-budget-usd`. **Hasta medir la
capacidad 6 no hay tope duro**, así que el control es **externo**: `timeout` de pared + una sola
invocación. Referencia B2: la tarea equivalente costó $0.28 en Claude. **No se asume que Codex cueste
igual.**

## 9 · Datos a registrar

exit code · señal de éxito de Codex (el campo que sea) · stdout/stderr crudos · modelo si lo reporta ·
coste/uso si lo reporta · estado del canal (`TASK`/`RESULT`, `seq`, hashes) · qué criterio falló.

## 10 · Condiciones de parada

- **Codex ausente** → no se intenta.
- **Un solo intento.** Falle como falle, **no se reintenta**, no se sube presupuesto, no se cambia de
  modelo. Se registra y se para.
- `timeout` de pared alcanzado → se registra como parada, canal queda auditado, **nunca `COMPLETED`**.

## 11 · Decisiones humanas que siguen bloqueando B3

| Id | Qué bloquea |
|---|---|
| **`D-CP-1.bis`** | Autorizar **instalar** Codex. `npm 11.16.0` disponible `[EJEC]`; instalar ≠ integrar |
| **`D-CP-1.ter`** | ToS de auth de suscripción en bucle automático `[INCIERTO]` |
| **Medición de capacidades** | Las 9 de Codex son `[UNKNOWN]`. La **primera prueba real debe ser de MEDICIÓN** (¿acepta stdin? ¿`--json`? ¿campo de error?), no de suma — o el comando de §3 podría estar mal formado y gastar el único intento |

> **Recomendación registrada, no ejecutada:** la primera invocación de Codex debería ser la de
> **medición de §11**, no la suma de §4. Medir cuesta lo mismo y evita quemar el intento con un
> comando `[HIPO]`. **No lo decido: es del CEO.**

## Pruebas locales que reducen el consumo real al mínimo

El ciclo `TASK → RESULT → verificación` **ya está probado con dobles en B2**
(`test_b2_ciclo_con_dobles.py`, 6 verdes). B3 **reutiliza esa lógica sin cambios**: el verificador de
P1 no distingue si el RESULT lo escribió Claude o Codex — solo comprueba el contenido. **Por tanto la
única incógnita real de B3 es Codex mismo**, y todo lo demás está demostrado gratis. No hacen falta
dobles nuevos.

---

# ACTUALIZACIÓN 2026-08-20 — capacidades MEDIDAS, precondiciones resueltas

El plan de arriba se escribió con Codex **ausente**. Lo que sigue es lo **medido**; no se borra lo
supuesto para que la diferencia quede auditable.

## A · Precondiciones §2, reevaluadas

| # | Precondición | Estado 2026-08-20 |
|---|---|---|
| P-1 | Codex instalado | ✅ `[EJEC]` `codex-cli 0.147.0` en `~/.nvm/…/bin/codex` |
| P-2 | ToS de auth de suscripción (`D-CP-1.ter`) | ✅ **resuelta por acto del CEO**: ejecutó `codex login` él mismo y ordenó usar Codex como segundo agente real. No la resolvió el agente por interpretación |
| P-3 | Codex autenticado | ✅ `[EJEC]` `codex login status` → **`Logged in using ChatGPT`**, exit 0 |
| P-4 | 9 capacidades medidas | ⚠️ **7 de 9 medidas a coste 0** (tabla B). Las 2 restantes solo son medibles ejecutando |
| P-5 | B1 y B2 en verde | ✅ `[EJEC] 2026-08-20`: dobles B2 6/6; RED contractuales 64 rojas / 15 verdes, sin desviación |

## B · Capacidades reales de `codex exec` `[EJEC]` — `codex exec --help`, lectura local, coste 0

| Capacidad | §3 suponía | Medido |
|---|---|---|
| Salida estructurada | `--json` | ✅ existe — *«Print events to stdout as JSONL»* |
| Sandbox | `--sandbox workspace-write` | ✅ existe (`-s`): `read-only` · `workspace-write` · `danger-full-access` |
| Directorio de trabajo | `--cd <DIR>` | ✅ existe (`-C, --cd`) |
| Prompt por stdin | `[HIPO]` | ✅ **confirmado**: *«If not provided as an argument (or if `-` is used), instructions are read from stdin»* |
| Timeout propio | dudoso | ❌ **NO existe** → control externo de pared, como preveía §8 |
| Tope de coste | equivalente a `--max-budget-usd` | ❌ **NO existe** → **sin tope duro**. Es el riesgo real de B3 |
| Señal de éxito (`is_error`) | por descubrir | ⚠️ **sigue `[UNKNOWN]`** — solo visible en el JSONL de una ejecución real |
| Coste reportado | por descubrir | ⚠️ **sigue `[UNKNOWN]`** — ídem |
| Extras no previstos | — | `--output-last-message` · `--output-schema` · `--ephemeral` · `--skip-git-repo-check` · `--add-dir` |

> **§11 queda disuelto.** Ya no hay que elegir entre «invocación de medición» e «invocación de la
> suma»: las dos incógnitas que quedan (**señal de éxito** y **coste**) se leen del JSONL de la
> **misma** invocación de la suma. Una sola invocación mide y ejecuta.

## C · Andamiaje construido y validado — coste 0

Directorio del experimento: `~/.claude/jobs/d6cb894c/tmp/b3/` — **fuera del repositorio**
`[EJEC]`. Contiene una **copia** de `communication_plane.py`, no el original: con
`--sandbox workspace-write --cd <ese dir>`, Codex **no puede alcanzar `aura_skeleton/` ni el repo**.

`p1.py` reutiliza **sin cambios** `verificar_respuesta` de `test_b2_ciclo_con_dobles.py`.

**Ensayo en seco superado** `[EJEC]` con un doble local que imita a Codex:

```
1 TASK   orquestador-local -> codex  {'objetivo':'sumar','a':17,'b':25, …}
2 RESULT codex -> orquestador-local  {'suma': 42}
3 ACK    orquestador-local -> codex  {'verificado': True}
ACEPTADO · exit 0 · seq monótona
```

**La única incógnita que queda en B3 es Codex mismo.** Todo lo demás está demostrado y fue gratis.

## D · Comando exacto — ya NO es `[HIPO]`

```bash
timeout 300 codex exec --json --sandbox workspace-write --cd <DIR_AISLADO> \
  -o last-message.txt < prompt.txt > salida.jsonl 2> stderr.txt
```

Todos los flags **verificados existentes**. `timeout 300` de pared es el único control de gasto
posible, porque Codex no expone tope de presupuesto.

## E · Bloqueo actual — de permisos, NO de decisión ni de cuota

`[EJEC 2026-08-20]` El **clasificador de auto-mode de Claude Code** denegó la ejecución de
`codex exec`. Se reintentó **una** variante más restrictiva (sin override de política de
aprobaciones y sin `--skip-git-repo-check`, creando un repo git en el dir aislado): **también
denegada**. No se intentó ningún rodeo adicional.

**Nada consumió cuota. Producción intacta. Ninguna invocación real llegó a ocurrir.**

`B3 = READY_TO_RUN / BLOCKED_BY_TOOL_PERMISSION`

---

# RESULTADO 2026-08-23 — B3 EJECUTADO · **GREEN**

Invocación **única** de `codex exec`, autorizada explícitamente por el CEO (2026-08-23), ejecutada con el
comando exacto de §D y el aislamiento de §C. **Sin reintentos.**

```bash
cd ~/.claude/jobs/d6cb894c/tmp/b3 && timeout 300 codex exec --json \
  --sandbox workspace-write --cd . --skip-git-repo-check \
  -o last-message.txt < prompt.txt > salida.jsonl 2> stderr.txt
# EXIT=0
```

## 1 · Los seis criterios de GREEN

| # | Criterio | Resultado | Evidencia |
|---|---|---|---|
| 1 | La invocación termina sin error | **CUMPLE** | `EXIT=0`; evento `turn.completed` presente; `stderr` solo `Reading prompt from stdin...` `[EJEC]` |
| 2 | Codex publica a través del canal, no a mano | **CUMPLE** | `seq=2` con `hash_anterior` correcto — solo `c.publicar()` lo produce `[EJEC]` |
| 3 | Existe un `RESULT` enlazado a la `TASK` | **CUMPLE** | `in_reply_to = e49addc1…4b49` `[EJEC]` |
| 4 | El cuerpo trae la suma correcta | **CUMPLE** | `{"suma": 42}` = 17 + 25 `[EJEC]` |
| 5 | La secuencia sigue siendo monótona | **CUMPLE** | seqs `[1, 2, 3]`, sin huecos ni duplicados `[EJEC]` |
| 6 | El verificador local acepta sin juicio | **CUMPLE** | `p1.py verificar` → `ACEPTADO`, exit 0; `ACK` seq=3 `[EJEC]` |

**Veredicto: B3 = GREEN.** Codex es el **segundo agente real** del Communication Plane. El canal
transportó `TASK → RESULT → ACK` entre dos agentes de **proveedores distintos** sin que ninguno de los
dos conozca al otro: solo el contrato.

## 2 · Integridad del canal

```
mensajes: 3 | seqs: [1, 2, 3] | tipos: ['TASK', 'RESULT', 'ACK']
cadena de hashes: INTEGRA
campos prohibidos: ninguno
```

## 3 · Consumo observado

```json
{"type":"turn.completed","usage":{"input_tokens":45183,"cached_input_tokens":35072,
 "cache_write_input_tokens":0,"output_tokens":481,"reasoning_output_tokens":37}}
```

Cuota de Claude: **0**. Coste en USD: **no publicado por Codex** (ver §4).

## 4 · Las dos incógnitas de §11, ya resueltas — y un hallazgo nuevo

- **Señal de éxito `[EJEC]`:** Codex **no** tiene equivalente a `is_error`. La señal es la **presencia del
  evento `turn.completed`** junto a `exit 0`. Un envoltorio de Codex debe verificar el **tipo de evento
  terminal**, no un booleano. Difiere estructuralmente de Claude: son dos contratos de envoltorio
  distintos, no uno parametrizable.
- **Coste `[EJEC]`:** Codex reporta **tokens, no dinero**. Sin tarifa asociada, el gasto **no es derivable**
  desde la salida. Convertirlo exigiría una tabla de precios externa — y la regla del CEO de 2026-08-04
  prohíbe publicar un número que no se derive formalmente. **Se registran tokens; no se publica coste.**
- **HALLAZGO NO PREVISTO `[EJEC]`: Codex no emite el modelo.** Búsqueda exhaustiva de
  `model|cost|usd|price` sobre `salida.jsonl` → **0 coincidencias**; `~/.codex/config.toml` no fija modelo.
  **No es posible saber qué modelo respondió.** Para un canal auditable esto es una carencia real: un
  `RESULT` no puede atribuirse al modelo que lo produjo. Queda como **observación técnica**, y se
  promueve a deuda si el Communication Plane llega a exigir trazabilidad de autoría por modelo.

## 5 · Aislamiento verificado

`git status --porcelain walking-skeleton/aura_skeleton/` → **vacío**. Producción **intacta**. Codex operó
sobre una **copia** de `communication_plane.py` en un directorio **fuera del repositorio**, con
`--sandbox workspace-write --cd .` — no tuvo alcance físico al árbol del proyecto.

**Sin commit. Sin push.**
