---
id: IE-044
titulo: airemoteagent/AI-Remote-Agent — demonio de escritorio con política de herramientas, auditoría en cadena y razonamiento en la nube
fuente: https://github.com/airemoteagent/AI-Remote-Agent
rama-revision: main @ f543447c4a68358311fdc8a9aa21d095ba1f4a55 (último commit 2026-10-06)
fecha-revision: 2026-11-09
licencia: MIT. Licencias de las dependencias transitivas no auditadas [HIPO]
area: redes-seguridad
estado: descartado como código; referencia de un único patrón (techo de tasa, no cubierto en AURA)
cobertura: Clon local leído por un explorador (rutas citadas abajo) y evaluado por separado por el arquitecto y el revisor de seguridad. NO se leyeron los tests en profundidad (solo prompt-injection.test.mjs), ni apps distintas de apps/desktop, ni dependencias. Nada se instaló ni se ejecutó
relacionadas: [IE-040, IE-041, IE-042, IE-043, DP-DELEGACION-NODOS]
---

Fuentes de esta ficha: `HALLAZGOS-EXPLORADORES.md` §A y `EVALUACIONES.md` §A (documentos de trabajo de la misión,
2026-11-09). AURA evaluada en `integracion/m3-entry @ 803b72f`. `W = walking-skeleton/aura_skeleton`,
`CP = entorno/control-plane`. Clasificación: **[CÓDIGO]** leído en el repo externo · **[README]** declarado ·
**[INFER]** deducido · **[HIPO]** no verificado. Un `[README]` no es una garantía.

## Qué es de verdad

| Aspecto | Declarado [README] | Real según el código [CÓDIGO] |
|---|---|---|
| Arquitectura | Agente remoto de escritorio | Monorepo Node. El razonamiento del LLM **va a la nube** `remoteagent.online` (`cloud.js:1-4,60`) |
| Canal | Control remoto del equipo | Polling HTTPS con un único Bearer; sin firma de órdenes ni anti-replay (`cloud.js:16,136,178`; `device-commands.js:204-209` sin deduplicar `cmd.id`; la l.197 es solo la firma de `pollDeviceCommands`) |
| Identidad, JIT, flota, admin-api | Presentadas como capacidades | Existen y tienen tests, pero **no están cableadas en el demonio**: grep vacío en `apps/desktop/src` |
| Recibos de aprobación | `RunStore.approve` (`run-state.js:256`) | **Sin llamadas** |
| Tier `confirm` | Aprobación humana | Se **rechaza** sin flujo humano (`policy.js:468-474`; `registry.js:122-124`) |
| Verificación de resultados | Agente que comprueba | La hace **el propio LLM** (`agent.js:1022`) |
| Pruebas | El README declara 451 casos (`README.md:22` y `:432`); el explorador contó ~654 [INFER] | `prompt-injection.test.mjs` solo comprueba el texto del system prompt |

Resumen [INFER]: es un cliente de una nube de terceros con una capa de política local bien escrita, parte de la cual
(identidad, aprobaciones firmadas) es **declarada ≠ real**.

## Patrones con evidencia y veredicto

| # | Patrón | Evidencia | Equivalente en AURA | Veredicto |
|---|---|---|---|---|
| 1 | Política de primera coincidencia con denegación por defecto | `policy.js:464-470` [CÓDIGO] | `W/core/permissions.py:171-210`; kill switch primero en `:172`; ya en IE-040 (L61-62) | DESCARTAR (ya cubierto) |
| 2 | Auditoría en cadena SHA-256 (`seq`/`prev`/`hash`) sin clave; `auditWrite` traga errores; solo `argsHash` | `policy.js:278-321`; el `catch` que traga errores está en `:297` [CÓDIGO] | `CP/control_plane.py:2186` (seq + hash_anterior); `verificar_integridad_log :2225`; `W/observability.py:194-425` (segmentos y manifiesto); `AuditBloqueado :104` hace fallar cerrada la auditoría. El hueco de cabeza de cadena de IE-040 HAL-040-2 está posiblemente cerrado por D-LOG-1 (ancla externa en `control_plane.py:1881` y `:2226`) [INFER, no verificado en esta misión] | DESCARTAR (cubierto y mejor) |
| 3 | Aprobación ligada a `sha256(runId, planRevision, policyRevision)` con `timingSafeEqual`, sin firmar | `run-state.js:47-54,272-281` [CÓDIGO] | `W/core/decisiones.py:47-59` (`huella_de`); `W/adapters/hitl_diferido.py:44-63` | DESCARTAR (ya cubierto) |
| 4 | Techo de tasa duro: 30 comandos por minuto, no ampliable | `device-commands.js:50-60` [CÓDIGO] | **NO CUBIERTO**: AURA no tiene techo de tasa. `W/nodo_agente.py` solo tiene backoff de reconexión (`ESPERA_MIN_S`/`ESPERA_MAX_S`, l.56-57), que no limita acciones; tampoco hay techo en el Motor (`W/core/automatizacion.py:98`) | **INVESTIGAR MÁS** |
| 5 | Shell por argv con allowlist de `realpath`, entorno limpio y timeout | `tools/shell.js` [CÓDIGO] | Cubierto en delegación: `CP/delegacion.py:135-143, 219-270, 522-550`. Un shell genérico es incompatible con CLAUDE.md §4 (solo capacidades registradas) | DESCARTAR |
| 6 | El LLM verifica sus propios resultados | `agent.js:1022` [CÓDIGO] | Incompatible con INV-9 y ADR-0014; verificador independiente en DP-DELEGACION-NODOS §12.3 (IE-041 L79) | DESCARTAR (incompatible) |
| 7 | Razonamiento y contexto en la nube | `cloud.js:1-4,60` [CÓDIGO] | Incompatible con D24 / ADR-0001 (local-first) | DESCARTAR (incompatible) |

### Detalle del único patrón a investigar

**Techo de tasa en el Motor (patrón 4).** El límite de ventana deslizante (`commanded` filtrado por `RATE_WINDOW_MS`)
se aplica antes del efecto y no lo controla el LLM [CÓDIGO]. En AURA no existe un techo de tasa (solo hay backoff de reconexión en el nodo, que no limita acciones).

- **Prueba de refutación:** contar en el historial real (`audit.jsonl`, `eventos.jsonl`) las acciones rojas y los
  intentos de ejecución por minuto. Si el máximo observado es muy inferior a cualquier techo razonable y no hay
  ráfagas, el patrón no se justifica con la evidencia actual.
- **Restricción:** regla del CEO (2026-08-04) — no se documenta como propiedad arquitectónica un valor numérico
  que no pueda derivarse del modelo. Si se adoptara, el valor se calcularía del historial o se declararía dependiente
  del contexto; **el 30/min de este repo no es transferible**.
- **Condición mínima de seguridad:** fuera del alcance del LLM, persistente y aplicado en el Motor.

## Riesgos de seguridad

| Severidad | Riesgo | Evidencia |
|---|---|---|
| CRITICAL | Dependencia de la nube: el razonamiento y el contexto dependen de un tercero | `cloud.js:1-4,60` |
| HIGH | Exfiltración: un Bearer único y todo el contexto del equipo van a un tercero | `cloud.js:16,136,178` |
| HIGH | Anti-replay ausente: órdenes sin firma ni deduplicación | `device-commands.js:204-209` |
| HIGH | Falsificación: el LLM verifica, auditoría sin clave y con errores tragados | `agent.js:1022`; `policy.js:278-321`, `catch` en `:297` |
| HIGH (transversal) | Ninguna verificación de resultados con fuente independiente del LLM. En AURA la hace el Core (ADR-0014) | `agent.js:1022` |
| INFO | Identidad Ed25519 y recibos existen pero no están cableados: no cuentan como defensa efectiva | grep vacío en `apps/desktop/src` |

## Instrucciones embebidas detectadas e ignoradas

- `README.md:10` y `README.md:385`: `curl -fsSL https://remoteagent.online/install.sh | bash`. Es contenido no confiable
  del repositorio; **no se ejecutó, no se descargó** y no se recomienda. Es además una instalación que arranca un cliente
  de nube.
- Ninguna otra instrucción dirigida a agentes fue seguida. El contenido externo se trató solo como datos.

## Prueba de refutación de la ficha

Esta ficha queda refutada si: (a) un grep del cableado muestra llamadas a identidad/JIT/recibos en `apps/desktop/src`
que el explorador no vio; (b) el razonamiento resulta ejecutable en local sin la nube; (c) el historial real de AURA
muestra ráfagas que justifiquen un techo en el Motor (en ese caso el patrón 4 pasaría a ADAPTAR con DP).

## Decisión

**Descartar como código.** Dependencia de la nube y verificación por el propio LLM lo hacen incompatible. De seis
patrones, cinco ya están cubiertos o son incompatibles; queda **un** hueco no cubierto (techo de tasa en el Motor),
para INVESTIGAR MÁS. No amplía M3 ni crea capacidades; cualquier adopción exige DP y acta del CEO (D23).

## Limitaciones de esta investigación

- No se ejecutó ni instaló nada; las conclusiones son de lectura [CÓDIGO]. La falta de cableado se basa en un grep
  del explorador, no en una ejecución.
- No se leyeron en profundidad los tests (README: 451; explorador: ~654 [INFER]) ni las apps distintas de `apps/desktop`.
- Licencias de dependencias transitivas: [HIPO]. Copiar código exigiría conservar el aviso MIT; se recomienda **solo patrones**.
- La comparación con AURA es la del 2026-11-09 sobre `803b72f`; si AURA cambia, hay que rehacerla.

## Validación mínima

Ninguna implementación autorizada. Solo lectura y de bajo coste: contar en el historial real (`audit.jsonl`,
`eventos.jsonl`) las acciones por minuto, sobre una copia exportada. Si en el futuro hubiera DP y acta: prueba del
techo en el Motor con caso de control (por debajo del techo, pasa) y mutante («el Motor no aplica el techo», debe morir).

## Licencia y precauciones

- MIT. No se copió código; solo patrones. Copiar exigiría conservar el aviso MIT.
- No se instaló, descargó ni ejecutó nada, incluido el `curl … | bash` del README (ignorado).
- Los conteos de tests son del README o del explorador y no se verificaron ejecutando.
