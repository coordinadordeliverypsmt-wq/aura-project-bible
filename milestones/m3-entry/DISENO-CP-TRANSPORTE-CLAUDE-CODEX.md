# Diseño — Transporte Claude Code ↔ Codex CLI (Communication Plane)

**Estado:** DISEÑO · **Fecha:** 2026-08-17 · **Decide:** CEO · **Propone:** APUS-5
**Autorización:** CEO 2026-08-17 — investigación y diseño de Línea B. **No implementar
`communication_plane.py`, no integrar Codex, no lanzar Codex, no construir el Orchestrator.**
**Clasificación D47:** `[EJEC]` medido · `[LECT]` leído · `[INFER]` deducido · `[UNKNOWN]` no verificable hoy.

> ## El hecho que gobierna todo este documento
>
> **`codex` NO está instalado en esta máquina.** `[EJEC 2026-08-17]` — `command -v codex` → ausente;
> `~/.codex` no existe.
>
> Y el `DP-COMMUNICATION-PLANE-AURORA` ya lo declaraba: sus datos sobre Codex están marcados
> **`[LECT, documentación oficial]`**, no medidos.
>
> **Consecuencia:** *todas* las capacidades de Codex de §2 son **`[UNKNOWN]`** en este entorno. Este
> documento **no las inventa**: las enumera como preguntas con su método de verificación exacto. La
> mitad del canal que sí puedo medir —Claude Code— está medida en §1.

---

## 1 · Lo que SÍ está verificado hoy `[EJEC 2026-08-17]`

`claude --version` → **2.1.234**.

### 1.1 · Claude Code como extremo del canal

| Capacidad | Estado | Evidencia |
|---|---|---|
| **Ejecución no interactiva** | ✅ | `claude -p "…"` — *«Print response and exit»* |
| **Salida estructurada** | ✅ | `--output-format json` devuelve **un único sobre JSON** |
| **Esquema de salida** | ✅ | `--json-schema <schema>` existe |
| **Identidad de sesión** | ✅ | `--session-id <uuid>`, y el sobre devuelve `session_id` |
| **Tope de gasto** | ✅ | `--max-budget-usd <amount>` |
| **Aislamiento de permisos** | ✅ | `--permission-mode`, `--allowedTools`, `--disallowedTools`, `--add-dir` |
| **Código de retorno** | ✅ | **exit 1** en fallo — medido con `--model` inexistente |
| **`--output-schema`** | ❌ **NO existe** | Es un flag de Codex según su documentación, no de Claude |

**Campos del sobre**, medidos: `is_error` · `subtype` · `terminal_reason` · `api_error_status` ·
`session_id` · `uuid` · `num_turns` · `duration_ms` · `duration_api_ms` · `total_cost_usd` ·
`usage` · `modelUsage` · `permission_denials` · `stop_reason` · `result` · `type`.

### 1.2 · ⚠️ Dos trampas medidas, y las dos cambian el protocolo

> **`subtype` NO es la señal de éxito.** En el fallo medido, el sobre traía
> **`is_error: true` junto a `subtype: "success"`**. Un lector que se fíe de `subtype` dará por buena
> una ejecución fallida. **La señal válida es `is_error`, corroborada por el código de retorno.**

> **El sobre publica el coste de la invocación** (`total_cost_usd`, `usage`, `modelUsage`). Esto
> **no contradice** `usage_known: false` del Control Plane: aquello dice que Claude Code no publica
> *cuánta cuota queda*; esto dice que sí publica *cuánto costó esta llamada*. Son cosas distintas y
> el canal puede **acumular coste por mensaje** sin estimar nada.

### 1.3 · Primitivas de transporte en disco, ya medidas

| Hecho | Valor | Consecuencia de diseño |
|---|---|---|
| `flock` tras `SIGKILL` | **se libera** | Un agente muerto no deja el canal bloqueado |
| Anexado concurrente | 4 procesos × 800 líneas → **0 corruptas** | El log del canal puede ser append-only sin lock de escritura |
| `PC_PIPE_BUF` | **4096** | Cuerpos > 4 KB **por referencia**, nunca en línea |

---

## 2 · D-CP-1 · Transporte — **qué es exactamente `[UNKNOWN]`**

El CEO pidió precisión sobre nueve capacidades de Codex CLI. **Ninguna es verificable hoy.** Para
cada una: qué haría falta saber y **el comando exacto que lo respondería**, para que la verificación
sea mecánica cuando se autorice.

| # | Capacidad | Estado | Cómo se verificaría (una sola vez, sin bucle) |
|---|---|---|---|
| 1 | **Entrada** no interactiva | `[UNKNOWN]` | `codex exec "<prompt>"` y `codex exec < fichero`; comprobar que no abre TUI |
| 2 | **Salida estructurada** | `[UNKNOWN]` | `codex exec --json`; y si `--output-schema <f.json> -o <salida>` produce JSON validable |
| 3 | **Lectura/escritura de archivos** | `[UNKNOWN]` | `--sandbox workspace-write` sobre un directorio de usar y tirar; comprobar qué escribe y dónde |
| 4 | **Ejecución no interactiva** | `[UNKNOWN]` | ejecutar sin TTY (`setsid`, `</dev/null`) y ver si completa |
| 5 | **Códigos de retorno** | `[UNKNOWN]` | provocar éxito, fallo de auth y fallo de modelo; anotar `$?` de cada uno **sin tubería** |
| 6 | **Errores** | `[UNKNOWN]` | ¿van a `stderr` o al JSON? ¿hay un campo equivalente a `is_error`? |
| 7 | **Timeout** | `[UNKNOWN]` | ¿existe flag propio, o hay que envolver en `timeout(1)`? |
| 8 | **Recuperación** | `[UNKNOWN]` | ¿`codex exec resume`? ¿el estado sobrevive a `SIGKILL`? |
| 9 | **Identificación de agente** | `[UNKNOWN]` | ¿el JSON trae identificador de sesión/turno estable? |

**Y dos preguntas previas a las nueve, que el CEO debe resolver antes:**

- **¿Se autoriza instalar Codex?** `npm 11.16.0` está disponible `[EJEC]`, así que la instalación es
  posible. **No se ha hecho.**
- **Términos de servicio** `[INCIERTO]`: el `DP §R5` ya registró que usar autenticación de
  suscripción en un bucle automático **puede** incumplir los ToS. **No asumido, no verificado.**

### 2.1 · Consecuencia de diseño: el transporte es un adaptador, y eso ya lo aísla

La incertidumbre **no bloquea el diseño**, porque el canal **no habla con Codex**: habla con un
`TransporteAdapter`. El `DP §14` ya lo fijó así. Nueve incógnitas quedan encerradas detrás de una
interfaz de dos métodos:

```
TransporteAdapter
  ├─ entregar(mensaje) -> AcuseDeEntrega        # deja trabajo para el otro extremo
  └─ recoger() -> list[Mensaje]                 # recoge lo que el otro extremo produjo
```

**Implementaciones previstas** — ninguna construida:

| Adaptador | Estado hoy | Qué necesita |
|---|---|---|
| `TransporteFichero` (mismo disco, dos procesos locales) | **Diseñable y probable HOY** | nada externo |
| `TransporteCodex` | `[UNKNOWN]` | resolver §2 y autorizar la instalación |
| `TransporteAurora` (worker interno futuro) | no diseñado | el propio AURORA |

**Esto responde técnicamente a D-CP-1 en lo que hoy se puede responder:** el transporte de referencia
es **de fichero**, verificable en esta máquina y sin terceros; **Codex es un adaptador más**, y su
viabilidad depende de nueve verificaciones y de una decisión de ToS que no son técnicas.

---

## 3 · Arquitectura del canal

```
   Claude Code ──┐                                        ┌── Codex CLI  [UNKNOWN]
                 │                                        │
                 ▼                                        ▼
        ┌───────────────────────── canal/ ─────────────────────────┐
        │  canal.jsonl        log append-only, encadenado por hash │
        │  procesados.jsonl   acuses: idempotencia                 │
        │  canal.lock         flock — solo para SECUENCIAR         │
        │  adjuntos/<sha256>  cuerpos > 4 KB, por referencia       │
        │  ESTADO.md          proyección legible, REGENERABLE      │
        └──────────────────────────────────────────────────────────┘
                 ▲                                        ▲
                 └──────────── Control Plane ─────────────┘
                     autoridad · qué está autorizado
```

**Tres reglas estructurales:**

1. **El canal transporta; no autoriza.** La autoridad vive en el Control Plane y en las políticas
   escritas por el CEO. Un mensaje **no puede** conceder lo que el Control Plane no concede.
2. **El log es la fuente de verdad; `ESTADO.md` es proyección** — ADR-0023. Debe poder borrarse y
   regenerarse desde `canal.jsonl` sin perder nada.
3. **`flock` solo secuencia.** No protege contra un agente malicioso ni contra otra máquina: es
   coordinación entre procesos cooperantes en un disco local.

---

## 4 · Protocolo de mensajes

### 4.1 · El ciclo que pidió el CEO, con sus tipos

```
Claude Code                 Communication Plane                 Codex
    │  ENCARGO ────────────────────▶ canal.jsonl ────────────────▶ │
    │                                                              │  trabaja
    │  ◀──────────────── canal.jsonl ◀──────────── RESULTADO ──────┤
    │  verifica                                                    │
    │  ACUSE ──────────────────────▶ procesados.jsonl              │
```

### 4.2 · Sobre del mensaje

Campos obligatorios; **ningún campo concede autoridad** —los prohibidos están enumerados abajo y una
prueba contractual lo fija.

| Campo | Qué es |
|---|---|
| `seq` | entero monotónico por canal; ordena y detecta huecos |
| `id` | **determinista**: `sha256(tipo · de · para · in_reply_to · cuerpo_hash)` — el mismo contenido produce el mismo id, y por eso el duplicado se reconoce solo |
| `tipo` | uno de los ocho del `DP §4` |
| `de` / `para` | identidad declarada (§5) |
| `in_reply_to` | `id` del mensaje que contesta, o `null` |
| `instante` | ISO-8601 local |
| `estado_leido` | **hash del `estado.json` que el emisor leyó** — responde *«¿qué versión del estado leyó?»* |
| `cuerpo` o `cuerpo_ref` | en línea si < 4 KB; si no, `adjuntos/<sha256>` |
| `hash_anterior` / `hash` | cadena de integridad del log |

**Campos que NO existen, y su ausencia es el contrato:** `autoriza`, `aprueba`, `permiso`, `permite`,
`autorizacion`, `override`.

### 4.3 · Lo que cada agente debe poder responder — punto 4 del encargo

| Pregunta del CEO | Dónde se responde | Verificable hoy |
|---|---|---|
| ¿qué tarea está autorizada? | `estado.json` → `tareas[id].estado` y `aprobaciones` | ✅ `[EJEC]` — el Control Plane ya lo modela |
| ¿qué tarea está bloqueada? | `decisiones_pendientes[].bloquea` | ✅ ya implementado en `debe_ejecutar()` |
| ¿quién produjo el artefacto? | `de` + `firma` (§5) | ⚠️ identidad declarativa — D-CP-3 |
| ¿qué versión del estado leyó? | `estado_leido` (hash) | ✅ diseñable y probable hoy |
| ¿qué cambió? | `cuerpo.diff` + `cuerpo.ficheros[]` | ✅ |
| ¿qué pruebas ejecutó? | `cuerpo.verificacion` — orden, salida y **código de retorno** | ✅ |
| ¿qué queda pendiente? | `cuerpo.pendiente[]` | ✅ |
| ¿cuándo detenerse y devolver la decisión al CEO? | `tipo = DECISION_REQUERIDA`; **bloqueante y no se desbloquea sola** | ✅ ya hay prueba RED que lo fija |

### 4.4 · Regla de finalización, heredada del `DP-ORCH §14.bis`

Un agente **no certifica su propio trabajo**. El criterio de finalización lo fija quien crea la
tarea, se escribe en el canal **antes** de invocar al ejecutor, y debe ser **una orden verificable**
(`pytest …`, `ruff …`) cuyo código de retorno decide. **Si no hay orden verificable, la tarea no es
automatizable.**

---

## 5 · D-CP-3 · Modelo de identidad

### 5.1 · Lo que hay hoy, medido

| Agente | Identificador disponible | Estado |
|---|---|---|
| **Claude Code** | `session_id` (UUID) en el sobre JSON; además `--session-id` lo fija el invocador | ✅ `[EJEC]` |
| **Codex** | ¿existe? | `[UNKNOWN]` — §2, capacidad 9 |
| **AURORA (futuro)** | no existe el worker | `[UNKNOWN]` |

### 5.2 · Tres niveles, y el proyecto solo puede pagar el primero hoy

| Nivel | Mecanismo | Contra qué protege | Coste |
|---|---|---|---|
| **N-1 · Declarativa** | el campo `de`, sin más | **Nada.** Cualquiera puede escribir `de: "claude-code"` | cero |
| **N-2 · Atestiguada** | `de` + `session_id` real + hash del estado leído | Confusión accidental, mensajes viejos, agente que miente sobre qué leyó | bajo, **hoy** |
| **N-3 · Firmada** | HMAC con secreto por agente | Suplantación deliberada | exige gestionar secretos |

**Propuesta que NO decido:** adoptar **N-2** como línea base. Es gratis, usa un identificador que
Claude Code ya emite `[EJEC]`, y cierra el hueco realista en una máquina monousuario —confundir dos
sesiones— sin inventar gestión de secretos. **N-3 queda para cuando el canal cruce máquinas**, que es
la condición que el `DP-CP §D-CP-3` ya declaró.

**Límite declarado:** ni N-1 ni N-2 impiden que quien tenga acceso de escritura al disco falsifique un
mensaje. **N-2 no es autenticación; es trazabilidad.** Decirlo de otro modo sería INV-9.

---

## 6 · Recuperación ante fallos — los ocho casos del encargo

| # | Fallo | Mecanismo | Verificable hoy |
|---|---|---|---|
| 1 | **Proceso muerto** | `flock` se libera con `SIGKILL` `[EJEC]`. Un `ENCARGO` sin `RESULTADO` ni acuse queda **huérfano** y se detecta por `seq` | ✅ |
| 2 | **Timeout** | El invocador envuelve en `timeout(1)`; al expirar escribe `INTERRUMPIDO` con el motivo. **Nunca `COMPLETED`** | ✅ |
| 3 | **Fichero parcialmente escrito** | Cuerpos < 4 KB: el anexado es atómico `[EJEC]`. Mayores: van a `adjuntos/<sha256>` y **el hash no cuadra** hasta estar completo | ✅ |
| 4 | **Mensaje duplicado** | `id` **determinista** sobre el contenido: el duplicado tiene el mismo `id` y `procesados.jsonl` lo descarta | ✅ |
| 5 | **Mensaje fuera de orden** | `seq` monotónico + `in_reply_to`. Un hueco en `seq` es detectable; un `in_reply_to` a un `id` ausente se rechaza | ✅ |
| 6 | **Tarea no autorizada** | El ejecutor consulta el **Control Plane**, no el mensaje. `debe_ejecutar()` ya devuelve `(False, motivo)` | ✅ `[EJEC]` |
| 7 | **Cambio simultáneo del estado** | `estado_leido` guarda el hash del estado que se leyó. Si al aplicar no coincide, **se rechaza y se reintenta**: es control de concurrencia optimista | ✅ |
| 8 | **Cuota agotada** | El sobre trae `is_error` y `terminal_reason` `[EJEC]`. Se registra con `registrar_bloqueo_de_cuota()`, ventana `UNKNOWN` si no se distingue, y la tarea queda `WAITING_FOR_QUOTA` — **nunca `COMPLETED`** | ✅ `[EJEC]` |

**Siete de los ocho son verificables hoy sin Codex.** El único que depende del extremo desconocido es
el comportamiento de Codex ante su propio timeout y recuperación (§2, capacidades 7 y 8).

---

## 7 · Qué puede probarse localmente sin integrar Codex

**Un segundo proceso `claude -p` es un extremo real del canal.** No es una simulación: es Claude Code
ejecutándose no interactivamente, con `--session-id` propio, salida JSON y código de retorno. Permite
ejercitar **el canal entero** —encargo, resultado, acuse, duplicado, orden, concurrencia,
recuperación— **sin Codex y sin decidir nada sobre ToS**.

Probable hoy, sin cuota, con dobles deterministas:

1. El sobre y su `id` determinista.
2. La cadena de hashes y la detección de manipulación.
3. Idempotencia y descarte de duplicados.
4. Huecos y desorden por `seq`.
5. `estado_leido` y el rechazo por estado cambiado.
6. `flock` liberado tras `SIGKILL`.
7. Cuerpos > 4 KB por referencia.
8. Que **ningún campo del mensaje conceda autoridad**.
9. Que `DECISION_REQUERIDA` **bloquee y no se desbloquee sola**.

**Requiere cuota (no ahora):** un intercambio extremo a extremo con dos procesos `claude -p` reales.
**Requiere Codex:** solo el adaptador `TransporteCodex`.

---

## 8 · D-CP-2 · Cómo se autorizaría GREEN — diseñado, no implementado

**Precondiciones acumulativas.** Ninguna es opcional y **ninguna la puede declarar el agente**:

| # | Precondición | Estado |
|---|---|---|
| 1 | `D-CP-1` resuelto: qué transporte se construye | **pendiente** |
| 2 | `D-CP-3` resuelto: nivel de identidad | **pendiente** — §5 propone N-2 |
| 3 | Auditoría independiente del `DP-CP` recogida | `WAITING_FOR_QUOTA` |
| 4 | `CHECKLIST §5.2` levantado para esta línea | `D-ORCH-5`, **pendiente** |
| 5 | Las 35 pruebas RED existentes, verdes | por construcción |

**GREEN por fases, la primera sin ningún tercero:**

- **B1 · Canal de fichero + un solo extremo.** Escribir y leer con `claude -p` local. Cierra la
  dependencia de que el CEO copie y pegue.
- **B2 · Segundo extremo real.** Dos procesos, encargo→resultado→acuse.
- **B3 · `TransporteCodex`.** Solo si §2 se verifica **y** los ToS se aclaran.

**B1 es el 80 % del valor y no toca a Codex.**

---

## 9 · Qué requiere decisión del CEO

| Id | Decisión | Por qué no la toma el agente |
|---|---|---|
| **D-CP-1** | Transporte: ¿se construye `TransporteFichero` como referencia y Codex queda para B3? | Elección de arquitectura |
| **D-CP-1.bis** | **¿Se autoriza instalar Codex para ejecutar las 9 verificaciones de §2?** | El CEO ordenó no integrarlo; instalar para *medir* no es integrar, pero **no lo decido yo** |
| **D-CP-1.ter** | **ToS de la autenticación de suscripción en bucle automático** `[INCIERTO]` | Riesgo legal, no técnico |
| **D-CP-2** | Autorizar GREEN, y en qué fase (B1/B2/B3) | Rango 1 |
| **D-CP-3** | Nivel de identidad: N-1, **N-2** o N-3 | Postura de seguridad |

---

## 10 · Compatibilidad con el objetivo de largo plazo

```
Claude Code + Codex + ChatGPT → transición controlada → AURORA → agentes internos
```

El diseño lo sostiene por **una sola propiedad**: el canal no conoce a sus extremos. Añadir AURORA
como agente es escribir un `TransporteAurora`; el protocolo, la identidad y la recuperación **no
cambian**. Y la propiedad que debe sobrevivir a toda la transición está en §3 regla 1: **el canal
transporta, no autoriza.** Mientras eso se cumpla, cambiar de agentes no cambia quién manda.

**Autonomía de AURORA: 0/7, sin cambios.** Este documento no construye nada.
