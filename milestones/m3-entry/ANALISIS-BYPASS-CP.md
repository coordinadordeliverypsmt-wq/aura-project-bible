# Análisis de los tres bypass — R-1, R-2, R-3

> **ACTUALIZACIÓN 2026-08-25 — `D-CP-7` CERRADA:** `F-DCP7 = GREEN respecto al WORKER ADMINISTRADO`. `bwrap` + user namespace es enforcement real para el Worker dentro de la jaula. **Constraint arquitectónico permanente, no deuda:** no protege frente a otro proceso del **mismo UID**; sin privilegios esa frontera no se considera cerrable. **Siguen ABIERTOS** —y no se presentan como cerrados— el lanzador omitible, el TOCTOU, credencial+red, el audit log `rw` y la cobertura incompleta del hook. **Sigue abierta `D-CP-3`.**


> **ACTUALIZACIÓN 2026-08-23 — `D-CP-5` YA ESTÁ DECIDIDA E IMPLEMENTADA:** esquema CERRADO por tipo, con RED, GREEN, mutación 6/6 sin supervivientes y auditoría independiente. **Decisión del CEO del 2026-08-23** (mensaje de encargo: *«La decisión vigente es ESQUEMA CERRADO POR TIPO»*), registrada tardíamente el mismo día tras una auditoría independiente que señaló su ausencia como artefacto. Lo detectó esa misma auditoría: cinco documentos seguían declarándola abierta mientras el código ya la implementaba — «declarado ≠ real», esta vez del lado de la gobernanza. **Siguen abiertas `D-CP-7` y `D-CP-3`.**


**Fecha:** 2026-08-18 · **Prepara:** APUS-5 · **Decide:** CEO
**No recomienda A/B/C. No convierte ningún `UNKNOWN` en supuesto. No modifica fuentes de verdad.**
**Clasificación D47:** `[EJEC]` medido · `[LECT]` leído · `[INFER]` deducido · `[UNKNOWN]` no verificado.

---

## 1 · R-1 · Argumentos de una capacidad catalogada

### 1.1 · Lo que hay, medido

`[EJEC]` El catálogo tiene **33 capacidades**: 17 verdes, 16 rojas.
`[EJEC]` `core/operaciones.py::ESPECIFICACIONES` declara esquema de argumentos para **10** de ellas.

**Las 10 con esquema declarado** llevan `args`, `rutas` y `permite_comodin`, y pasan por
`validar()` → `ruta_en_ambito()` contra `raices_por_defecto()`. El adaptador añade **protección
TOCTOU** (revalida el descriptor tras abrirlo) y **rechazo de enlaces simbólicos** `[EJEC]`.

### 1.2 · El hallazgo que decide la pregunta del CEO

> **Las capacidades que la alternativa A usaría como criterio —`ejecutar_pruebas`,
> `verificar_calidad`, `auditar_garantias`, `diagnosticar_estado`— NO tienen esquema de argumentos
> declarado.** `[EJEC]` Ninguna de las cuatro está en `ESPECIFICACIONES`.

**Por tanto, y esto no es opinión: el catálogo cerrado de `D-CP-4/A` NO sería suficiente por sí solo.
Necesita una segunda frontera para argumentos.** Un `ejecutar_pruebas(ruta="…")` con ruta
controlada por el emisor no está acotado hoy por ningún esquema.

### 1.3 · Clasificación

| Clase | Criterio **medido** | Capacidades |
|---|---|---|
| **SAFE** | `efecto = ninguno` | `consulta` |
| **CONTROLABLE** | esquema de argumentos + contención de ruta + TOCTOU | `abrir_archivo`, `buscar_archivo`, `copiar_archivo`, `leer_archivo`, `listar_directorio`, `consultar_estado_sistema`, **y las rojas** `borrar_archivo`, `escribir_archivo`, `mover_archivo`, `renombrar_archivo` |
| **PELIGROSA** | `efecto` destruye/altera/externo **y sin esquema de argumentos** | `eliminar_informacion`, `instalar_software`, `modificar_configuracion`, `proponer_cambio`, `terminar_proceso`, `abrir_cerradura`, `accion_financiera`, `accion_legal`, `compra`, `mensaje_a_tercero`, `pago`, `transferencia` |
| **UNKNOWN** | sin esquema y sin efecto destructivo declarado | `apagar_dispositivo`, `encender_dispositivo`, `automatizacion`, `monitoreo`, `organizacion`, `recordatorio`, **`auditar_garantias`, `diagnosticar_estado`, `ejecutar_pruebas`, `verificar_calidad`** |

**Nota sobre las rojas «PELIGROSA»:** todas pasan por `PermissionManager` (HITL con previsualización)
y quedan auditadas aunque no exista adaptador `[LECT, DP-D-M-8 §3]`. **La lista roja las frena; lo que
no existe es validación de sus argumentos.** Son dos controles distintos.

---

## 2 · R-2 · Herramientas propias del agente — **el punto prioritario**

### 2.1 · Lo medido en esta máquina, hoy

| Qué | Valor `[EJEC 2026-08-18]` |
|---|---|
| `.claude/settings.json` **del proyecto** | `{"worktree": {"bgIsolation": "none"}}` — **sin `permissions`, sin `hooks`** |
| `~/.claude/settings.json` **del usuario** | `permissions.allow = ["Bash(*)"]` |
| `hooks` en cualquier nivel | **NINGUNO** |
| Hook de git del repositorio | `.githooks` — `pre-push` con Quality Gate |

### 2.2 · Lo que esto significa, sin suavizarlo

> **`Bash(*)` es shell sin restricción.** Una sesión de Claude Code en esta máquina puede leer,
> escribir, borrar y ejecutar cualquier cosa que el usuario del sistema pueda. **No necesita el
> Communication Plane para nada.**

Y corrige por medición un punto que `DP-ORCH §14.ter` dejó como `[LECT]` no medido: **el hook
`PreToolUse` —única barrera citada contra la autoescalada— no está configurado.** No es que sea
débil: **no existe aquí**.

**La única barrera real y medida es el `pre-push`**, y gobierna **publicar**, no **actuar**.

### 2.3 · Clasificación de controles

| Mecanismo | Quién lo controla | Evidencia |
|---|---|---|
| Catálogo, listas verde/roja, HITL, kill switch, dry-run | **1 · AURORA** | `permissions.py`, `automatizacion.py` `[EJEC]` — **pero solo sobre acciones que pasen por su Motor** |
| `--permission-mode`, `--allowedTools`, `--disallowedTools`, `--add-dir`, `--max-budget-usd` | **2 · Claude Code** | existen `[EJEC]`, **no están en uso en esta sesión** |
| `permissions.allow`, hooks, qué sesión se lanza y cómo | **3 · El usuario** | `Bash(*)` configurado por el usuario `[EJEC]` |
| Todo lo que el agente haga fuera del Motor: shell, ficheros, git, red | **4 · NO CONTROLADO por AURORA** | consecuencia directa de `Bash(*)` |
| Qué hará Codex con sus propias herramientas | **5 · UNKNOWN** | no está instalado |

### 2.4 · Respuesta a la pregunta del CEO

**¿Puede la arquitectura de AURORA gobernar a un agente externo que posee herramientas propias?**

> **Hoy, no.** Y no por un defecto de AURORA: **el agente no está dentro de AURORA.** AURORA gobierna
> lo que entra por su Motor Único; un agente con `Bash(*)` no tiene ninguna obligación de entrar.
>
> **Solo puede gobernarlo si AURORA es quien lo lanza**, imponiendo `--permission-mode`,
> `--allowedTools`, `--add-dir` y un hook `PreToolUse`. **Si lo lanza un humano con `Bash(*)`, la
> frontera es documental.**

---

## 3 · R-3 · Identidad — qué garantiza N-2

| Propiedad | ¿La da N-2? | Por qué |
|---|---|---|
| **Trazabilidad** | **SÍ, parcial** | `de` + `sesion_id` real + `estado_leido` permiten reconstruir quién dijo qué y sobre qué estado |
| **Integridad** | **SÍ, del LOG** | La cadena de hashes detecta manipulación **posterior**. **NO** garantiza integridad del emisor |
| **Autenticación** | **NO** | Nada prueba que quien escribió `de: "claude-code"` sea Claude Code |
| **Autorización** | **NO, y nunca** | La autorización vive en el Control Plane. Si la identidad la concediera, `TRANSPORTE = AUTORIDAD` |
| **No repudio** | **NO** | Sin firma, un agente puede negar haber emitido un mensaje, y nadie puede demostrar lo contrario |

**N-2 es trazabilidad e integridad del log. No es autenticación.** Decirlo de otro modo sería INV-9.

### 3.1 · Qué necesitaría una identidad fuerte, y su coste

| Requisito | Coste real |
|---|---|
| Secreto por agente + HMAC de cada mensaje | Gestión de secretos: generación, almacenamiento, rotación |
| Aislamiento del secreto | **Aquí está el problema** `[INFER]`: en una máquina **monousuario**, cualquier proceso del usuario puede leer el fichero del secreto. Una firma que el atacante puede producir no autentica nada |
| Aislamiento real | Usuarios del SO distintos por agente, o llavero del sistema. **Cambia el modelo de despliegue** — y `P1` sigue sin decidir |

> **Conclusión de coste:** una identidad fuerte **no es un problema de criptografía, es un problema de
> aislamiento del sistema operativo**. Sin `P1` resuelto, N-3 daría **apariencia** de autenticación.
> **No se cambia N-2.**

---

## 4 · Matriz de controles

| Control | Existe hoy | Quién lo controla | Qué bypass cubre |
|---|---|---|---|
| Catálogo de capacidades | ✅ 33 `[EJEC]` | AURORA | V1 parcial |
| Esquema de argumentos | ⚠️ **solo 10 de 33** `[EJEC]` | AURORA | **R-1: insuficiente** |
| Contención de ruta + TOCTOU + symlinks | ✅ `[EJEC]` | AURORA | R-1 en las 10 |
| Listas verde/roja + HITL | ✅ `[EJEC]` | AURORA | V1 parcial |
| Kill switch | ✅ pero **no alcanza a 6 de 7 ramas** `[EJEC]` | AURORA | Línea A, congelada |
| Motor Único como ruta única | ❌ **G-1 en RED** | AURORA | Línea A, congelada |
| Esquema cerrado del mensaje | ❌ `D-CP-5` sin decidir | canal | V4 |
| Criterio acotado | ❌ `D-CP-4` sin decidir | canal | V1, V3 |
| Identidad fuerte | ❌ N-2 es trazabilidad | canal | R-3 |
| `--allowedTools` / `--permission-mode` | ✅ existen, **sin usar** `[EJEC]` | Claude Code | **R-2** |
| Hook `PreToolUse` | ❌ **no configurado** `[EJEC]` | usuario | **R-2** |
| `pre-push` Quality Gate | ✅ `[EJEC]` | repositorio | publicación, no acción |

---

## 5, 6, 7 · Qué resuelven y qué no `D-CP-4` y `D-CP-5`

| | Resuelve | **NO resuelve** |
|---|---|---|
| **`D-CP-4`** | Que `cuerpo` transporte una orden ejecutable (V1). En su variante A, acota lo ejecutable (V3 parcial) | **R-1** — 23 de 33 capacidades sin esquema de argumentos, incluidas las 4 que A usaría · **R-2** · **R-3** |
| **`D-CP-5`** | Contrabando por nombre y por anidamiento (V4) | **V1** si el esquema declarase `criterio` · persuasión semántica en campos de texto legítimos · **R-1**, **R-2**, **R-3** |
| **Ambas juntas** | El canal deja de ser fuente de autoridad accidental | **Los tres bypass siguen abiertos.** R-2 no lo puede cerrar el canal |

---

## 8 · Arquitectura mínima para que la frontera sea real

```
agente ──▶ Communication Plane ──▶ Control Plane ──▶ Motor Único ──▶ capacidad
```

Cinco condiciones. **Cuatro faltan y una está bloqueada:**

| # | Condición | Estado |
|---|---|---|
| **C-1** | **AURORA lanza al agente**, no un humano — imponiendo `--permission-mode`, `--allowedTools`, `--add-dir` | ❌ hoy lo lanza el usuario con `Bash(*)` |
| **C-2** | **Hook `PreToolUse` activo**, que rechace lo que no pase por el Motor | ❌ no existe en ningún nivel `[EJEC]` |
| **C-3** | **Esquema de argumentos para toda capacidad usada como criterio** | ❌ faltan 23 de 33 |
| **C-4** | **G-1 en verde**: ninguna mutación fuera del Motor | ❌ **Línea A congelada** |
| **C-5** | **Esquema cerrado + criterio acotado** | ❌ `D-CP-4`, `D-CP-5` sin decidir |

> **Sin C-1 y C-2, las otras tres no bastan:** un agente con shell sin restricción no está obligado a
> usar ninguna de las puertas que las otras condiciones vigilan. **C-1 y C-2 no las decide el canal:
> las decide quien lanza el agente.**

---

## 9 · Decisiones que requieren aprobación humana

| Id | Asunto | Estado |
|---|---|---|
| `D-CP-4` | Criterio: A / B / C | `DECISION_REQUIRED` |
| `D-CP-5` | Lista negra → esquema cerrado | `DECISION_REQUIRED` |
| `D-CP-3` | Identidad: N-2 se mantiene | sin cambios; N-3 exige resolver `P1` |
| **`D-CP-6`** *(nueva)* | **Esquema de argumentos para las 23 capacidades que no lo tienen** | **`DECISION_REQUIRED`** |
| **`D-CP-7`** *(nueva)* | **¿Quién lanza al agente ejecutor y con qué restricciones (C-1, C-2)?** | **`DECISION_REQUIRED`** |
| `P1` | Escenario de despliegue | condiciona la identidad fuerte |
| `D-G1-*` | Línea A | congelada |

**Ninguna se resuelve en este documento.**
