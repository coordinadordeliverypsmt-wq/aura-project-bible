# CHECKPOINT DE CONTINUIDAD — AURA

**Protocolo PCC (CEO, 2026-08-03).** Este fichero se lee **antes que nada** al reanudar. No rehacer
análisis ya cerrado. No recorrer el repositorio salvo que aquí se indique. No reabrir decisiones
aprobadas.

**Fecha:** 2026-08-03 · **Motivo de la parada:** límite de contexto de la sesión.

**El Protocolo de Continuidad es PERMANENTE** (CEO, 2026-08-03) y vive en `CLAUDE.md` §0: parada automática por debajo del ~2 % de contexto, sin esperar a que el CEO lo pida.

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

> **1) Construir el ROADMAP del Sistema Operativo Interno** (ver seccion "ENCARGO EN COLA").
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

## Modo de trabajo vigente (CEO, 2026-08-03)

1. **No abrir nuevos Decision Packages ni alertas**, salvo bloqueo crítico para la implementación.
2. **Prioridad: cerrar deuda, no crear documentación.**
3. Detenerse al ~98 % de contexto y escribir este checkpoint.
4. Al reanudar: leer este fichero y continuar desde el paso pendiente.
