# Protocolo de orquestación de herramientas — AURA

**Fuente única.** Esta es la definición del método de trabajo por defecto en TODA sesión y prompt de AURA.
`CLAUDE.md §8` remite aquí; los agentes de `.claude/agents/` remiten aquí. No copiar su contenido en otros
ficheros: enlazar a este.

Las herramientas son EXTERNAS a AURORA (no parte de su arquitectura). Se consideran **por defecto**, se
comprueba su disponibilidad, y se usan las capacidades pertinentes — sin invocarlas ciegamente en cada
operación trivial. Si una falta o su integración no funciona, se documenta; no se finge que se usó.

## Roles

- **Graphify** — capa de conocimiento del repositorio. Orienta ANTES de explorar código: usa el grafo
  existente (`~/.graphify/venv/bin/graphify query|explain|path`, desde la raíz del repo) para localizar
  componentes, dependencias y pruebas, y acotar las lecturas. No reconstruir el grafo completo sin
  necesidad; `graphify update` solo tras cambios estructurales. Verificar siempre la conclusión contra el
  código real. Un hook `PreToolUse` global ya recuerda esto a todos los agentes.
- **ECC** — capa de agentes y capacidades de ingeniería (revisión, delegación, gestión de contexto).
  Agentes en `~/.claude/agents/` (`security-reviewer`, `code-reviewer`) y en `.claude/agents/` del proyecto
  (`explorador-repositorio`, `arquitecto-evaluador`, `auditor-consistencia`, `verificador-mutacion`).
  Reutilizar sus skills/reglas (`~/.claude/rules/ecc/`). Reservar `security-reviewer`/`code-reviewer`/
  `verificador-mutacion` para riesgos y cambios REALES del incremento.
- **Claude Code** — orquestador principal. Divide el trabajo, entrega a cada agente el **contexto mínimo
  suficiente** (ficha común: nodos/rutas/líneas/pruebas/hallazgos previos), consolida resultados y NO
  repite investigaciones. Serializa cambios sobre un mismo fichero/worktree; paraleliza solo tareas
  independientes.
- **Codex / OpenCode** — revisión o ejecución INDEPENDIENTE cuando estén disponibles (responsabilidades
  diferenciadas; evitar auditoría duplicada). Comprobar con `command -v`. Si no están, documentar la
  limitación; **no instalarlos** salvo necesidad técnica real que Claude Code no cubra.
- **OmniRoute** — herramienta externa y experimental de enrutamiento a proveedores. **Nunca** parte del
  runtime/dependencias de AURA ni enruta código privado a terceros sin proveedor y tratamiento autorizados.
  Antes de delegarle trabajo: comprobar instalación, salud, ruta efectiva, compatibilidad de herramientas
  y recuperación de sesión. No asumir que funciona por estar instalado.

## Reglas de eficiencia (reducir consumo de contexto)

1. Graphify orienta → leer solo los archivos estrictamente necesarios.
2. Reutilizar evidencia y resultados previos; no repetir salidas de comandos ya registradas ni auditorías
   ya válidas. Mantener un resumen acumulativo y el `CHECKPOINT` recuperables.
3. Ficha de evidencia común por agente; cada agente responde SOLO con hallazgos, evidencia (rutas:líneas),
   pruebas y veredicto.
4. No asignar la misma auditoría a varios agentes. Modelos económicos para exploración/mecánica; los más
   capaces para decisiones arquitectónicas o riesgos críticos.

## Ficha de evidencia compartida (mecanismo para reducir tokens)

Para que Graphify dé contexto compartido y compacto sin que cada agente re-explore:

1. **Una ficha por incremento activo**, en `.claude/ficha-evidencia.md` (efímera, de proyecto; NO en
   `~/.aura`). La puebla el **primer** agente/el orquestador con el resultado de **una** consulta dirigida
   de Graphify: nodos, rutas:líneas, pruebas y restricciones relevantes al incremento.
2. **Los demás agentes LEEN la ficha primero** y solo consultan Graphify para **información nueva** que la
   ficha no cubra. No repiten la consulta ya hecha ni releen archivos ya citados.
3. El orquestador **pasa la ficha** (o su ruta) a cada subagente en el prompt, con su tarea delimitada.
   Cada agente responde SOLO con hallazgos/evidencia/veredicto; el orquestador consolida y actualiza la
   ficha si hay algo nuevo. Al cerrar el incremento, la ficha se descarta.
4. **Recordatorios de Graphify:** el hook global `graphify hook-guard` emite un aviso en cada
   `Bash|Grep|Read|Glob`. Reducir re-exploración (puntos 1-3) reduce esos disparos. Silenciar el aviso en
   sí exige tocar `~/.claude/settings.json` (global, afecta a todos los proyectos): NO se hace sin
   autorización explícita del CEO.

## Ante error / bloqueo

- **Técnico** (error, FAIL, bloqueo): diagnosticar y resolver dentro de las autorizaciones vigentes,
  verificar la corrección con evidencia, registrar.
- **Gobernanza** (arquitectura, privacidad, Bible/ADR/DP, autorización humana): detenerse y elevar como
  `DECISION_REQUIRED`; no inventar aprobaciones (ver `CLAUDE.md §6`).
