# Mapa de dependencias — Línea A y Línea B

**Fecha:** 2026-08-18 · **Prepara:** APUS-5 · **Decide:** CEO
**No recomienda. No cierra ninguna decisión. No cambia ningún estado a `COMPLETED`.**
**Objetivo:** dejar el tablero listo para decidir y **empezar construcción real**, no seguir
analizando.

---

## 1 · `P1` — escenario de despliegue

### 1.1 · Lo que YA está decidido, y conviene no reabrir

`[LECT]` **`D36` ya oficializó los dos escenarios**, y `ADR-0018` ya derivó su consecuencia técnica:

| Escenario | Definición literal (`ADR-0018`) | Estado |
|---|---|---|
| **E1** | *«uso personal, un solo proceso»* | **escenario inicial oficializado** |
| **E2** | *«hogar inteligente, multi-proceso»* | *«objetivo de la primera versión estable»* |

`ADR-0018` decidió el bus por escenario: **InProcess oficial en E1, NATS reservado a E2** — y
`run_demo_nats.py` ya validó empíricamente la sustitución `[LECT]`.

### 1.2 · Qué decide exactamente `P1`, entonces

**`P1` NO es «¿E1 o E2?»** — eso lo cerró `D36`. `CHECKLIST §3` lo enuncia así:

> **`P1 · Escenario de despliegue` — *¿es esta máquina el objetivo?*** · pendiente desde 2026-07-21 ·
> bloquea **3 de las 5 fases de M3**.

**`P1` decide sobre qué máquina corre E1.** Tres consecuencias medidas que dependen de esa respuesta:

1. **La alternativa A de inversión** (hardware): si esta máquina no es el objetivo, medir su latencia
   deja de ser el criterio.
2. **N2**: su umbral es **8 GB** y esta máquina tiene **3,6 GB** `[EJEC, revisión §5]`. En esta
   máquina N2 **nunca se materializa**.
3. **Hallazgo nuevo de este mapa — identidad fuerte (`R-3`).** Una identidad no falsificable exige
   **aislamiento del SO** (usuarios distintos por agente, llavero). Eso **es una propiedad del
   escenario de despliegue**. `P1` no solo condiciona el hardware: **condiciona si `D-CP-3/N-3` es
   siquiera posible.**

**No se elige escenario.**

---

## 2 · `D-CP-7` — quién lanza al agente

| | **A · lo lanza el usuario** *(estado actual)* | **B · lo lanza AURORA** | **C · híbrido** |
|---|---|---|---|
| **Permisos** | Usuario — `Bash(*)` `[EJEC]` | AURORA, vía `--permission-mode` / `--allowedTools` / `--disallowedTools` `[EJEC: existen]` | Usuario en la sesión interactiva; AURORA en las ejecutoras |
| **Herramientas** | Claude Code, según config del usuario | AURORA elige el subconjunto **antes** de arrancar | Doble régimen |
| **Hooks** | Usuario — **ninguno configurado** `[EJEC]` | AURORA los impone con `--settings` | AURORA solo en las que lanza |
| **Filesystem** | Sin restricción | Acotado con `--add-dir` | Acotado solo en las ejecutoras |
| **Qué puede AURORA** | **Registrar lo que el agente le cuente. Nada más** | **Definir el perímetro antes de que exista el proceso** | Gobernar el trabajo automatizado |
| **Qué NO puede** | **Impedir ninguna acción** | Lo que el agente haga *con las herramientas concedidas*; ni impedir que el usuario abra otra sesión sin restricciones | Lo mismo, y conviven dos perímetros |
| **Dependencia con `P1`** | Ninguna | **Sí** — lanzar procesos es una propiedad del escenario (E1 es *«un solo proceso»*) | **Sí** |
| **Dependencia con `D-CP-3/4/5/6`** | **Ninguna, y ese es el problema:** sin perímetro, esas cuatro decisiones son **documentales** | **Total: solo con B tienen efecto real** | Real en el perímetro gobernado |

> **Lo que la comparación revela y no es opinión:** `D-CP-4`, `D-CP-5` y `D-CP-6` **solo producen una
> frontera real bajo B o C**. Bajo A siguen siendo documentación. **`D-CP-7` no es una decisión más
> de la lista: es la que determina si las otras sirven de algo.**

**Tensión declarada, no resuelta:** **E1 es *«un solo proceso»***. Que AURORA lance agentes es
**multi-proceso**. `[INFER]` O B/C exigen revisar el alcance de E1, o exigen E2. **No lo resuelvo.**

---

## 3 · `D-CP-6` — agrupación de las 33 capacidades

| Grupo | Nº | Capacidades |
|---|---|---|
| **Con esquema de argumentos** (`ESPECIFICACIONES`) | **10** | `abrir_archivo`, `borrar_archivo`, `buscar_archivo`, `copiar_archivo`, `escribir_archivo`, `leer_archivo`, `listar_directorio`, `mover_archivo`, `renombrar_archivo`, `consultar_estado_sistema` |
| **Sin esquema** | **23** | el resto, **incluidas las 4 que `D-CP-4/A` usaría como criterio** |
| **Efecto destructivo** (`destruye`) | 2 | `borrar_archivo` *(con esquema)*, `eliminar_informacion` *(sin esquema)* |
| **Efecto externo** | 7 | `abrir_cerradura`, `accion_financiera`, `accion_legal`, `compra`, `mensaje_a_tercero`, `pago`, `transferencia` — **todas sin esquema** |
| **Ya pasan por controles existentes** | **33** | Las 33 pasan por `PermissionManager` (listas + HITL + kill switch) y por el dry-run del Motor cuando alteran estado `[EJEC]` |

**La distinción que importa:** *«pasa por controles»* ≠ *«sus argumentos están validados»*. Las 33
pasan por política; **10 tienen validados los argumentos**.

### 3.1 · Esquema mínimo que necesitaría el Motor Único

Derivado de lo que ya existe, sin inventar: los **cinco campos de la Mutación** (`DP-D-M-8 §2.1`) más
la lista blanca de argumentos que `ESPECIFICACIONES` ya usa en las 10.

| Campo | Ya existe | Qué falta |
|---|---|---|
| `operacion` | ✅ catálogo | — |
| `args` | ⚠️ solo en 10 | **declarar en las 23 restantes** |
| `origen` | ✅ el Motor lo exige | — |
| `trace_id` | ✅ | — |
| `sujeto` | ❌ | **campo nuevo** de `DP-D-M-8 §2.1`: distingue borrar un fichero de borrar un hecho declarado por el usuario |

**Regla mínima:** por operación, **lista blanca de nombres de argumento** + tipo + si es ruta
(→ contención y TOCTOU, ya implementados). **No se implementa aquí.**

---

## 4 · La frontera completa, y lo que se le escapa

```
CAPACIDAD ──▶ ARGUMENTOS ──▶ POLÍTICA ──▶ AUTORIZACIÓN ──▶ MOTOR ──▶ EFECTO
 D-CP-4       D-CP-6         permissions   Control Plane    G-1      adaptador
   ❌            ❌              ✅             ✅            ❌         ✅
```

**Bypass que permanecen aun resolviendo `D-CP-4` + `D-CP-5` + `D-CP-6`:**

| # | Bypass | Lo cierra |
|---|---|---|
| **B-1** | **El agente no usa el canal.** Con `Bash(*)` no necesita ninguna de esas puertas | **`D-CP-7` (B o C)** — no lo cierra ninguna decisión del canal |
| **B-2** | **Rutas que mutan sin pasar por el Motor** — 6 de las 7 ramas del turno | **G-1 / `D-M-8` F2–F6 · Línea A, congelada** |
| **B-3** | **Identidad suplantable** | `D-CP-3/N-3`, que a su vez depende de **`P1`** |
| **B-4** | **Persuasión semántica** en campos de texto legítimos | **Nada la cierra.** Se acota su efecto, no su ocurrencia |

---

## 5 · Línea A — qué depende de `P1`, `D-CP-7` o del canal

| Decisión de Línea A | ¿Depende? | De qué |
|---|---|---|
| `D-G1-2` · lista blanca | **No** | Solo del CEO |
| `D-G1-3` · anotaciones de tipo | **No** | Solo de autorizar tocar producción |
| `C-ESPEC-F2-F3` · adaptadores F2/F3 | **No** | Ambigüedad de la ESPEC |
| `D-ORCH-5` · levantar `CHECKLIST:235` | **No** | Solo del CEO |
| `D-M-8` F2–F6 | **No** | Secuencia interna del DP |
| **`ORCH-FASE-1`** | **Sí** | **`D-CP-7`**: un orquestador que no controla el perímetro del agente no gobierna nada |

**Y en sentido inverso, el hallazgo estructural de este mapa:**

> **`D-CP-4/A` y `D-CP-6` son trabajo de Línea A con etiqueta de Línea B.** El catálogo de
> capacidades y `ESPECIFICACIONES` viven en `aura_skeleton/` —producción—, y su valor como frontera
> depende de que **el Motor Único sea ruta única**, que es **G-1**. **Las dos líneas convergen aquí.**

---

## 6 · El tablero

### 6.1 · Decisiones del CEO

| Id | Asunto | Línea |
|---|---|---|
| `P1` | ¿Es esta máquina el objetivo de E1? | ambas |
| `D-CP-7` | Quién lanza al agente: A / B / C | B |
| `D-CP-4` | Criterio: catálogo / fuera de `cuerpo` / ambas | B |
| `D-CP-5` | Lista negra → esquema cerrado | B |
| `D-CP-6` | Esquema de argumentos para 23 capacidades | **A materialmente** |
| `D-CP-2` | Autorizar GREEN del canal | B |
| `D-CP-3` | Identidad N-2 / N-3 | B |
| `D-G1-2`, `D-G1-3`, `C-ESPEC-F2-F3`, `D-ORCH-5` | Línea A | A |

### 6.2 · Dependencias

```
P1 ──▶ D-CP-7 ──▶ (D-CP-4, D-CP-5, D-CP-6 dejan de ser documentales)
 └───▶ D-CP-3/N-3

D-CP-4 ──▶ D-CP-5   (si `criterio` es campo del esquema)
D-CP-6 ──▶ D-CP-4/A (sin argumentos acotados, el catálogo no basta)
D-CP-7 ──▶ ORCH-FASE-1
G-1    ──▶ que el Motor sea ruta única, de lo que depende TODA la frontera
```

### 6.3 · Resolubles de forma independiente

`D-G1-2` · `D-G1-3` · `C-ESPEC-F2-F3` · `D-ORCH-5` · `D-CP-5` *(pero no cierra V1 sola)* ·
`D-CP-6` *(es trabajo de Línea A y no espera al canal)*.

### 6.4 · Primer incremento que podría entrar en GREEN

**Dos candidatos, con sus precondiciones exactas. No elijo.**

| Candidato | Precondiciones | RED ya escrito |
|---|---|---|
| **G-1 en verde** (Línea A) | `D-G1-2` + `D-G1-3` | **15 pruebas** `[EJEC]` |
| **Canal B1** — transporte de fichero, un extremo | `D-CP-2` + `D-CP-5` + `D-CP-4` | **79 pruebas** `[EJEC]` |

**Ambos tienen su RED escrito y ejecutándose en rojo.** Ninguno espera a Codex, a cuota ni a hardware.

### 6.5 · Qué NO debe construirse todavía

`communication_plane.py` · integración de Codex · Agent Orchestrator · `F2`–`F6` de `D-M-8` ·
`G-2b`, `R-D`, `M0–M5` · identidad N-3 · cualquier excepción en el manifiesto de G-1 ·
**y ninguna modificación de producción sin autorización explícita.**

---

**Ninguna decisión se cierra en este documento. Ningún estado pasa a `COMPLETED`.**
