# DP — Mensajero de relevo entre sesiones de desarrollo (control plane)

**Estado: PROPUESTA — DECISION_REQUIRED.** Nada construido. Redactado 2026-10-18 a petición del CEO
(«Misión: agente mensajero de continuidad»). Ámbito: **herramienta de desarrollo**, fuera de AURORA
(`entorno/control-plane/README.md:7-15`); no concede capacidad al producto.

## 1. Problema

Cuando una sesión de Claude Code se acerca a su límite (5 h o semanal), el trabajo debe pasar a otra sesión
(«aura v2 conectada», vía OmniRoute) sin reconstruir contexto ni duplicar ejecuciones.

## 2. Qué existe ya (reutilizable) `[LECT]` salvo indicación

| Necesidad | Mecanismo existente | Cubre |
|---|---|---|
| Carga útil del relevo | `control_plane.py:734` `render_handoff` + CLI `handoff` (:796) | Sí, pero **lee `estado.json`, desfasado** (`actualizado: 2026-09-01`) `[EJEC]` |
| Fuente de verdad | `CHECKPOINT-CONTINUIDAD.md` (CLAUDE.md §0); README: «manda el documento» | Sí |
| Exclusión / claim | `control_plane.py:1523` `lock_estado` (flock) | Lock sí; **lease/TTL no** |
| Traza | `registrar_evento` (:1835) + hash + `verificar_integridad_log` (:1906) | Sí |
| Bloqueo por cuota | `interrumpir` :455, `registrar_bloqueo_de_cuota` :467, `esperar_por_cuota` :1706 | Sí |
| Parada | `PARADA` (`orquestador.py:317-334`) | Sí |
| Disparo | patrón despertador (`despertador.py`, §23: sin daemons ni watchers) | Sí |

**No existe:** estados preparado/entregado/recibido/reclamado, lease con caducidad, acuse, carga útil
derivada del CHECKPOINT.

## 3. Hechos verificados sobre la plataforma (2026-10-18)

- **Señal de cuota:** solo el JSON de entrada del **statusLine** trae `rate_limits.five_hour|seven_day.
  used_percentage|resets_at` (Pro/Max, tras la primera respuesta). Ningún hook la recibe; no hay evento de
  «cerca del límite» (`StopFailure`/`rate_limit` llega **después**). Fuente: docs oficiales statusline/hooks
  (vía `claude-code-guide`). Versión mínima: **no confirmada**.
- **Canal de entrega:** `ListAgents`/`SendMessage` entre sesiones locales (Claude Code ≥2.1.224; aquí 2.1.302).
  `[EJEC]` La sesión receptora local (PID 3220, `claude --model claude/combo/aura-v2`, nombre derivado
  `aura-project-bible-2e`) está viva y anuncia `peerProtocol 1` con socket, **pero no aparece en `ListAgents`
  y `SendMessage` falla** («not reachable») tanto con «aura v2 conectada» como con su nombre derivado.
  Causa **no verificada** `[HIPO]`: sesión autenticada por gateway. → **Entrega E2E NO demostrada.**

## 4. Diseño propuesto (mínimo, extensión del control plane)

1. **Subcomando `relevo`** en `control_plane.py` (no un sistema nuevo): `preparar | entregar | recibir |
   reclamar | completar | bloquear | estado`.
2. **Estados como eventos** en `eventos.jsonl` (hash existente): `relevo_preparado → relevo_entregado →
   relevo_recibido → relevo_reclamado → relevo_completado | relevo_bloqueado`. El estado se **deriva del log**
   (sin fichero de estado paralelo).
3. **Carga útil** derivada de lo real, no de `estado.json`: rama, HEAD, `main`/`origin/main`, nº de cambios
   pendientes (`git status`), última sección del CHECKPOINT, pruebas declaradas y siguiente acción. Hash de
   la carga → idempotencia (mismo hash = relevo duplicado, se rechaza).
4. **Claim sin duplicar:** `reclamar` bajo `lock_estado`; lease con TTL **derivado del log** (instante del
   evento + TTL). Un segundo reclamo dentro del TTL se rechaza; tras caducar, se puede re-reclamar
   (recuperación tras interrupción).
5. **Protección de cambios pendientes:** `preparar` **nunca** hace stash/commit/checkout; registra la lista
   de ficheros modificados y su hash; `reclamar` avisa si el árbol difiere.
6. **Señal de cuota:** fuente primaria = statusLine de **proyecto** (`.claude/settings.json`) que vuelque
   `rate_limits` a un fichero efímero ignorado por git; umbral configurable. Si el campo falta:
   `usage_known: false` → **relevo preventivo** marcado como tal (nunca se inventan porcentajes).
7. **Entrega:** la propia sesión emisora ejecuta `SendMessage` con el texto canónico («AURA V2 conectada: …
   Hay un relevo disponible. Lee el CHECKPOINT, verifica el repositorio y continúa el trabajo autorizado»)
   y registra `relevo_entregado` solo si el envío devuelve éxito; la receptora registra `relevo_recibido`
   al leerlo. Sin daemon (§23).
8. **Gobernanza intacta:** respeta `PARADA`; `completar` no puede marcar COMPLETED una tarea que exige
   autoridad humana (`validar_tareas` :153-188); un relevo nunca transporta autorizaciones nuevas.

## 5. Pruebas exigidas (RED antes de GREEN)

Preparar/recuperar · duplicado por hash · cambios pendientes no tocados · reclamo único bajo lock ·
re-reclamo tras TTL · señal de cuota ausente → preventivo · PARADA bloquea · `completar` sin autoridad
rechazado · integridad del log tras cada transición · E2E real emisor→receptor (si el canal funciona).
Mutación sobre: comprobación de duplicado, TTL, PARADA, guarda de autoridad.

## 6. Decisiones requeridas al CEO

- **D-REL-1:** ¿se autoriza construir §4.1-4.5 y 4.8 en el control plane? (alcance acotado, reversible).
- **D-REL-2:** ¿se autoriza un `statusLine` de **proyecto** para la señal de cuota (§4.6)? Toca
  `.claude/settings.json` del repo; no la configuración global.
- **D-REL-3 (bloqueo externo):** que la sesión «aura v2 conectada» sea alcanzable por `SendMessage`. Si la
  sesión vía gateway no se anuncia como par, alternativas: receptora sin gateway en la misma máquina, o
  relevo **solo por CHECKPOINT** (pull: la receptora lo lee al arrancar), que ya funciona hoy.

## 7. Retorno sobre tokens

Evita reconstruir contexto en cada relevo (la carga útil sustituye a releer el CHECKPOINT entero) y elimina
ejecuciones duplicadas. Coste: un subcomando y ~10 pruebas sobre infraestructura existente.
