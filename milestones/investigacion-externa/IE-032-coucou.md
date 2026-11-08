---
id: IE-032
titulo: Louis-CFM/coucou — supervisión de sesiones de agentes (isla/bandeja, aprobaciones, móvil)
fuente: https://github.com/Louis-CFM/coucou
rama-revision: main @ 47d1c2da12bf1dce8fb28b825757d497c1e1d88d (commit del 2026-10-23, firmado SSH)
fecha-revision: 2026-10-26
licencia: MIT (LICENSE, © 2026 Louis Raillé); LICENSE-ASSETS.md reserva el nombre «Coucou»/«Mochi», el personaje, los iconos, los sonidos y los media; código Android y phone_link © Rhytam Biswas, MIT. Licencias de las dependencias no auditadas
area: herramientas-de-desarrollo
estado: prototipo-aislado-futuro (pendiente de acta); patrones reutilizables ya
cobertura: Lectura remota con `gh api` (contents, trees, releases, issues) de hooks.rs, config_file.rs, hook/src/{main,unix,reply}.rs, pipe.rs, phone_link/{mod,server,pairing}.rs, settings.rs, log.rs, voice/mod.rs, flow/os_linux.rs, linux.yml, LICENSE*. Sin clonar, instalar ni ejecutar. Contrastado por un auditor independiente y una revisión de seguridad
relacionadas: [IE-033, DP-MENSAJERO-RELEVO, DP-DELEGACION-NODOS]
---

Base de las citas: `B = https://github.com/Louis-CFM/coucou/blob/47d1c2da12bf1dce8fb28b825757d497c1e1d88d`.

Clasificación de cada afirmación:

- **[CÓDIGO]** verificado en el código y **contrastado** por el auditor independiente;
- **[CÓDIGO*]** leído por un solo agente, sin contraste;
- **[README]** declarado por los autores;
- **[INFER]** inferencia;
- **[PENDIENTE]** solo verificable ejecutando.

## Qué se examinó (rutas y símbolos)

**Metadatos:**

- Repositorio creado el 2026-09-27; 773 commits hasta el ref.
- En los últimos 100 commits, el autor «Claude» aparece 58 veces y «Louis» 22.
- Unas 6,5 k estrellas, 136 issues abiertas y 364 PR abiertas.
- Release `linux-v0.5.3` (`.deb`, `.rpm`, AppImage) con un `SHA256SUMS` generado en el mismo CI (`.github/workflows/linux.yml#L114`) **[CÓDIGO]**. No se comprobó si falta otro tipo de firma **[PENDIENTE]**.

**Arquitectura:**

- La app de Linux y Windows usa Tauri 2 (`windows/src-tauri`), con el binario de hooks `coucou-hook` (`windows/hook`).
- En Linux requiere WebKitGTK 4.1, layer-shell, appindicator, GStreamer y Secret Service (`windows/src-tauri/tauri.linux.conf.json`) **[CÓDIGO*]**.
- Es una app GUI de bandeja; no hay modo headless **[INFER]**.

## Patrones relevantes

| # | Afirmación | Evidencia | Clase |
|---|---|---|---|
| 1 | Instala **12 hooks globales sin `matcher`**: SessionStart, SessionEnd, UserPromptSubmit, Pre/PostToolUse, PostToolUseFailure, PermissionRequest, Notification, Stop, StopFailure y Subagent* | `B/windows/src-tauri/src/hooks.rs#L26-L39`, `#L125-L131` | [CÓDIGO] |
| 2 | La instalación es **a demanda** (botón), con backup, diff y fusión que conserva los hooks ajenos. Si el fichero cambió desde el preview, rechaza la escritura | `hooks.rs#L110-L137`, `#L221-L229`; `config_file.rs#L254-L306` | [CÓDIGO*] |
| 3 | El detector `entry_is_ours` actúa **por grupo** (`command.contains(MARKER)`): puede borrar un grupo de hooks del usuario que comparta entrada | `hooks.rs#L86-L99`, `#L124`; issue #854 | [CÓDIGO] (el valor de MARKER no está leído) |
| 4 | Hay un backup `settings.json.bak-<sello>` por cada modificación, creado 0600 en Unix, **sin rotación** | `config_file.rs#L265-L283` | [CÓDIGO] (no se leyó `keep_mode`) |
| 5 | El hook **reenvía a la app** prompts, `tool_input.command`, `cwd`, variables de terminal y el contenido de Edit/Write (≤ 256 KB por campo, ≤ 512 KB por evento). Descarta `tool_response`, `tool_output` y `transcript_path` | `B/windows/hook/src/main.rs#L44-L60`, `#L249-L274` | [CÓDIGO] |
| 6 | La aprobación **solo** responde `allow`, `deny` o `answers` al `PermissionRequest` (el hook espera hasta 110 s). Sin decisión, decide el terminal. «always» equivale a un `allow` simple | `pipe.rs#L340-L360`, `#L243`; `hook/src/reply.rs` | [CÓDIGO] |
| 7 | **No distingue por herramienta ni tiene lista roja**: un Bash destructivo se aprueba con el mismo gesto que un `ls`. Mitigación: desde el móvil no se puede aprobar un comando truncado (`hub.rs#L742`) | `pipe.rs#L344-L349` | [CÓDIGO*] |
| 8 | IPC local: socket Unix en `$XDG_RUNTIME_DIR`, 0600 y SO_PEERCRED con el mismo uid | `B/windows/hook/src/unix.rs#L21-L37`, `#L99-L114`; `pipe.rs#L104-L150` | [CÓDIGO*] |
| 9 | El phone link escucha en **0.0.0.0:47821**, filtra IP privadas y usa TLS autofirmado (hasta 2124) con fijación y un **token único global** de 192 bits que viaja en el QR. **Apagado por defecto** | `phone_link/mod.rs#L213-L214`; `settings.rs#L159`; `server.rs#L201-L212`; `pairing.rs#L48-L95` | [CÓDIGO] (0.0.0.0 y default) / [CÓDIGO*] (resto) |
| 10 | El phone link acepta mensajes `ping`, `decision`, `answer`, `getDiff`, `bye` y **`chat*`**. No se verificó que `chat` no pueda llegar a una sesión de Claude Code | `phone_link/server.rs#L341-L374` | [CÓDIGO] + **[PENDIENTE]** |
| 11 | La herramienta de voz `open_app` acaba en `gtk-launch`. No se verificó si hay una confirmación en otra capa | `voice/mod.rs#L382`, `#L511` | [CÓDIGO] + **[PENDIENTE]** |
| 12 | El dictado pega en la app que esté en primer plano mediante XTest o el portal RemoteDesktop (opt-in) | `flow/os_linux.rs#L173-L175` | [CÓDIGO*] |
| 13 | Chat, voz y resúmenes usan **claves de terceros** opcionales (Anthropic, OpenAI…). Sin telemetría declarada | `claude.rs#L7-L23`; README L92 | [CÓDIGO*] / [README] |
| 14 | El log está en `~/.local/share/coucou/coucou.log` (0600, 1 MB) y registra eventos y decisiones, no contenido | `log.rs#L1-L32`; `pipe.rs#L222-L357` | [CÓDIGO*] |
| 15 | La doc dice «Your own hooks are never touched» y «Claude Code is never blocked». El código desmiente la primera (fila 3) y matiza la segunda (espera de 110 s) | `windows/README` L170-171 frente a `hooks.rs`/`main.rs` | [CÓDIGO] |

## Límites, riesgos y dependencias

- **Hardware (HC-1: Celeron N4020, 2 núcleos, 3,6 GiB, eMMC al 94 %).**
  - WebView WebKitGTK y tokio, más un proceso `coucou-hook` por evento (unos 3 o más por cada llamada a herramienta) **[INFER]**.
  - El consumo de RAM y CPU no está medido **[PENDIENTE]**.
  - Puede alterar las mediciones de CM1/CM2 (latencia y carga) **[INFER]**.
- **Seguridad** (`security-reviewer`):
  - **ALTO-1:** el contenido de sesión sale de Claude Code hacia otra app, y con ello los secretos que aparezcan en comandos o ediciones. `coucou-hook` es un binario que se ejecuta en cada evento.
  - **ALTO-2:** aprobación de un clic, también desde el móvil, sin lista roja. Contradice en espíritu ADR-0003, porque no es una confirmación *informada*.
  - **ALTO-3:** cadena de suministro. Proyecto de 4 semanas con mayoría de commits generados por IA, artefactos con solo `SHA256SUMS` del mismo CI y un actualizador.
  - **MEDIO:**
    - backups de `settings.json` que **duplican las claves en claro** sin rotación;
    - si se activa el phone link, la superficie de LAN compartida con IoT, DVR, PS5 y el nodo;
    - voz y dictado.
  - **BAJO:** el socket local está bien resuelto.
- **Mantenimiento:** actividad muy alta, bus factor de 1 más la IA, e issues de robustez abiertas (#854, #855, #858, #859).

## Comparación con AURA

| AURA | Relación | Clase |
|---|---|---|
| `walking-skeleton/aura_skeleton/core/notificaciones.py:1-12`: centro **único** de notificaciones del **producto**, con fuentes cerradas; «el centro no ejecuta nada por su cuenta» | Planos distintos. Coucou supervisa **Claude Code**, no a AURA. Integrarlo como fuente violaría las fuentes cerradas y la regla de que «actuar no es un atajo» | [INFER] (arquitecto-evaluador) |
| `entorno/control-plane/observatorio.py:1`: «mirar a AURA sin tocarla» | Sin conflicto: el observatorio mira a AURA y Coucou mira a Claude Code | [INFER] |
| `milestones/m3-entry/DP-MENSAJERO-RELEVO.md` (PROPUESTA) | Solapamiento parcial: los dos observan sesiones. Coucou **no** sustituye el relevo, porque no envía prompts (salvo lo pendiente en la fila 10), y sus hooks son **globales** cuando el DP restringe la señal al proyecto (`:54`, `:74-75`) | [LECT] |
| PARADA, lista roja (ADR-0003) y autoridad humana del control-plane | Una aprobación en Coucou **no** es una autorización de AURA. Coucou no puede ni debe tocar PARADA | [INFER] |
| `.claude/rules/orquestacion-herramientas.md:7`, `:59` | Las herramientas son externas a AURORA. Tocar el `settings.json` global exige **autorización expresa del CEO** | [LECT] |

## Decisión

**Recomendación: `PROTOTIPO AISLADO FUTURO`** (pendiente de acta), más la **reutilización de ideas ya**.

| Modalidad | Arquitecto | Seguridad | Decisión consolidada |
|---|---|---|---|
| (a) Herramienta externa en el equipo real, sin integración | ENCAJA CON CONDICIONES: acta para los hooks globales, phone link apagado, sin claves de terceros, voz desactivada | **NO RECOMENDADO**: ALTO-1, 2 y 3 se materializan sobre el entorno real, con hooks globales y claves | **No ahora.** La seguridad prevalece: el `settings.json` global contiene claves y lo comparten todos los proyectos |
| (b) Prototipo de laboratorio aislado, no productivo | ENCAJA CON CONDICIONES; tensiona «no abrir frentes fuera del plan» (`CHECKLIST-CONTINUIDAD.md:265`) | ACEPTABLE CON CONDICIONES (los 9 controles de abajo) | **Futuro, solo con acta del CEO** y si existe una necesidad observada (regla de evidencia del uso real) |
| (c) Reutilizar ideas sin código | ENCAJA | RECOMENDADO | **Sí**, como notas de diseño para el DP de relevo o de delegación, siempre vía DP |

**Patrones reutilizables** (sin adoptar código):

- socket Unix 0600 con comprobación SO_PEERCRED por uid;
- backup, diff y huella antes de reescribir una configuración, rechazando la escritura si cambió desde el preview;
- **fallo abierto hacia el terminal** (sin decisión, decide el humano en su terminal, nunca `allow`);
- **no aprobar remotamente lo que no se ha mostrado completo** (truncado);
- espera acotada.

## Validación mínima (para la modalidad b, solo con acta)

Los 9 controles mínimos de la revisión de seguridad:

1. Usuario o contenedor separado, con un `HOME` propio y un `settings.json` sintético **sin claves**.
2. Phone link desactivado y el puerto 47821 bloqueado; sin QR ni mDNS.
3. **No registrar `PermissionRequest`**: solo observación.
4. Compilar desde el commit fijado tras revisarlo, con `Cargo.lock` auditado. Sin binarios precompilados ni actualizador.
5. Sin red saliente para el proceso.
6. Voz y dictado desactivados, comprobado ejecutando.
7. Prueba controlada de que una regla `deny` sigue mandando.
8. Borrado de los `.bak-*` y comprobación de que no pasa ningún secreto real.
9. Desinstalación verificada con diff y plan de reversión.

**Criterios:**

- RAM y CPU medidas sin alterar CM1/CM2;
- **0 aprobaciones** emitidas por Coucou;
- confirmar o refutar las filas 10 y 11.

## Licencia y precauciones

- El código es MIT. **El nombre, el personaje, los iconos y los sonidos no lo son** (`LICENSE-ASSETS.md`): un fork o una redistribución exigiría renombrar y sustituir los assets.
- Las licencias de las dependencias (Cargo) no están auditadas.
- No se instaló, descargó ni ejecutó nada. Las copias de texto que se usaron para leer se borraron de `/tmp`.

## Contrato de seguridad para cualquier integración futura (Coucou o similar)

1. **AURA conserva la autoridad.** Una aprobación en una interfaz externa **no** es una autorización de AURA. Las acciones de AURA siguen pasando por el motor único, la lista roja (ADR-0003) y la confirmación humana **informada**.
2. **Una interfaz externa no puede armar ni desarmar PARADA**, ni escribir en `entorno/control-plane/`, `estado.json` o `eventos.jsonl`.
3. **Una notificación no es evidencia de ejecución.** Solo cuenta el resultado verificado (INV-9).
4. **Una aprobación local no sustituye** la autenticación de tareas y resultados de los nodos (`DP-DELEGACION-NODOS` §11: firmas y fijación SPKI).
5. **No se exponen puertos ni se activa una conexión móvil** sin un análisis de amenazas explícito, emparejamiento autenticado, autorización y política de red.
6. **Las credenciales nunca** van a código, logs, backups acumulados ni ficheros de evidencia. El `settings.json` global no se modifica sin acta, y nunca con claves dentro de un entorno de prueba.
7. **Los hooks externos no pueden sobrescribir en silencio** la configuración existente: diff previo, backup controlado, identificación precisa de entradas y desinstalación verificada.
8. **Toda integración debe poder desactivarse y revertirse limpiamente**, sin hooks huérfanos.
9. **Ninguna herramienta externa es dependencia crítica** del control-plane ni del cronograma. Si falta, AURA funciona igual.
