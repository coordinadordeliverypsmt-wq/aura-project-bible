---
id: IE-045
titulo: agent-wall/agent-wall — proxy MCP por stdio con política YAML, escáner de respuestas y kill switch
fuente: https://github.com/agent-wall/agent-wall
rama-revision: main @ 940120730b34959e3b1a578e4dd220b76fb6c4a7 (último commit 2026-02-17)
fecha-revision: 2026-11-09
licencia: MIT. Licencias de las dependencias transitivas no auditadas [HIPO]
area: redes-seguridad
estado: descartado como código; un hueco nuevo para INVESTIGAR MÁS (redacción de secretos y PII)
cobertura: Clon local leído por un explorador y evaluado por separado por el arquitecto y el revisor de seguridad (proxy.ts, policy-engine.ts, ResponseScanner, auditoría, kill switch, dashboard). NO se leyó el resto de paquetes ni las dependencias. Nada se instaló ni se ejecutó
relacionadas: [IE-040, IE-042, IE-044, IE-046]
---

Fuentes de esta ficha: `HALLAZGOS-EXPLORADORES.md` §B y `EVALUACIONES.md` §B (2026-11-09). AURA evaluada en
`integracion/m3-entry @ 803b72f`. `W = walking-skeleton/aura_skeleton`, `CP = entorno/control-plane`.
Clasificación: **[CÓDIGO]** · **[README]** · **[INFER]** · **[HIPO]**. Lo declarado no es lo garantizado.

## Qué es de verdad

| Aspecto | Declarado [README] | Real según el código [CÓDIGO] |
|---|---|---|
| Alcance | Cortafuegos para agentes MCP | Proxy MCP por stdio (`StdioProxy`, `proxy.ts:118`) que **solo filtra `tools/call`**. `resources`, `prompts`, `sampling` y `tools/list` pasan sin filtro (`proxy.ts:485-500`). Un `tools/call` malformado **se reenvía** (fail-open) |
| Pipeline | Defensa por capas | kill switch → inyección (regex) → egress (léxico, **sin DNS**) → política YAML de primera coincidencia (por defecto `prompt`; `deny` en modo estricto, `policy-engine.ts:265-315`) → detector de cadenas |
| Aprobación humana | Prompt al usuario | Prompt por `/dev/tty` que falla cerrado, pero **sin TTL y sin ligar la aprobación a un hash de los argumentos**; sin anti-replay |
| Auditoría | JSONL con HMAC | Argumentos redactados; el **HMAC encadenado está desactivado por defecto**; con clave aleatoria no persistida la cadena no es verificable |
| Dashboard | Panel HTTP/WS | Escucha en **todas las interfaces**, sin autenticación vista |
| Pruebas | ~279 casos (conteo aproximado del explorador [INFER]) | Sin test de `proxy.ts` ni del pipeline completo |

Resumen [INFER]: componente razonable para el ecosistema MCP, pero AURA **no tiene MCP**; las protecciones
valiosas son las que no dependen de MCP (kill switch, escáner de respuestas).

## Patrones con evidencia y veredicto

| # | Patrón | Evidencia | Equivalente en AURA | Veredicto |
|---|---|---|---|---|
| 1 | Proxy MCP entre agente y servidores | `proxy.ts:118,485-500` [CÓDIGO] | No aplicable: AURA no tiene MCP; un proxy sería una **segunda vía de ejecución** (ALERTA-005). Cobertura parcial ya en IE-042 L63 | DESCARTAR |
| 2 | Kill switch por fichero, señal o API | pipeline de `proxy.ts` [CÓDIGO] | Por fichero ya cubierto: `W/core/kill_switch.py:11-29`. Por señal o API no hay bloqueo observado | DESCARTAR |
| 3 | **ResponseScanner**: ~17 patrones de secretos y PII sobre las respuestas, con redactar o bloquear | ResponseScanner [CÓDIGO] | **No cubierto**: grep vacío en `observability` y `automatizacion`. Hueco **NUEVO**, no está en IE-040 a IE-043 | **INVESTIGAR MÁS** |
| 4 | Detección de inyección por regex | pipeline [CÓDIGO] | Superficie inexistente: no hay LLM con texto externo en el bucle | DESCARTAR |
| 5 | Prompt humano por tty que falla cerrado | `/dev/tty` [CÓDIGO] | Ya cubierto y mejor: `hitl_diferido` con huella (`W/adapters/hitl_diferido.py:44-63`) | DESCARTAR |
| 6 | Dashboard HTTP/WS | dashboard [CÓDIGO] | Incompatible: sin autenticación y en todas las interfaces | DESCARTAR |

### Detalle del único patrón a investigar

**Redacción de secretos y PII en lo que AURA registra o devuelve (patrón 3).** El valor no es el escáner de
agent-wall (regex, defensa en profundidad), sino la pregunta de si AURA escribe secretos o datos personales en sus
registros.

- **Prueba de refutación:** grep de patrones de clave, token y PII en los `audit.jsonl` y `eventos.jsonl` reales.
  **Si no hay nada, no hay riesgo que lo justifique y el patrón se descarta.**
- **Condición mínima:** envoltura y escaneo de respuestas son **solo defensa en profundidad, nunca garantía**
  (la regex no demuestra ausencia). Un fallo del redactor no puede abrir el registro.
- **Nota de procedimiento:** la medición debe hacerse sobre copias exportadas, nunca sobre un worktree con el arnés
  de mutación en marcha (CLAUDE.md §2).

## Riesgos de seguridad

| Severidad | Riesgo | Evidencia |
|---|---|---|
| HIGH | Inyección: regex como única defensa; `resources`/`prompts`/`sampling` sin filtro; `tools/call` malformado reenviado (fail-open) | `proxy.ts:485-500` |
| HIGH (si se adoptara) | Dashboard en todas las interfaces sin autenticación | dashboard |
| HIGH | Anti-replay y TOCTOU: aprobación sin TTL ni hash de argumentos | prompt tty |
| HIGH | HMAC de auditoría desactivado por defecto; con clave efímera no es verificable | auditoría |
| HIGH (transversal) | No verifica resultados con una fuente independiente del LLM; en AURA lo hace el Core (ADR-0014) | n/a |
| INFO | Egress léxico sin DNS: un nombre inocuo puede resolver a una dirección interna [INFER] | pipeline |

## Instrucciones embebidas detectadas e ignoradas

Ninguna instrucción dirigida a agentes en los ficheros leídos. Contenido externo tratado solo como datos; nada se
ejecutó ni se descargó.

## Prueba de refutación de la ficha

Queda refutada si el grep sobre los registros reales de AURA encuentra secretos o PII (el hueco se convierte en
deuda real y exigiría DP), o si una lectura completa de `proxy.ts` muestra que el filtrado cubre más que `tools/call`.

## Decisión

**Descartar como código; un hueco nuevo para INVESTIGAR MÁS** (redacción de secretos y PII), condicionado a que el
grep sobre los registros reales lo justifique. No amplía M3 ni crea capacidades; cualquier adopción exige DP y acta (D23).

## Limitaciones de esta investigación

- Sin ejecución: todo es [CÓDIGO]/[README] por lectura. El comportamiento fail-open ante `tools/call` malformado y la
  ausencia de autenticación del dashboard no se reprodujeron.
- No se leyeron en profundidad los tests (~279, conteo aproximado [INFER]); que falte test de `proxy.ts` es observación del explorador.
- Proyecto de actividad corta (último commit 2026-02-17): su mantenimiento posterior es [HIPO].
- La cifra de ~17 patrones del escáner es aproximada (explorador); no se inventarió cada patrón.
- Licencias de dependencias transitivas: [HIPO]. Recomendación: solo patrones, sin copiar código.

## Validación mínima

Solo lectura y de bajo coste: grep de patrones de clave, token y PII en los `audit.jsonl` y `eventos.jsonl` reales,
sobre una copia exportada. Si hay resultados y se autoriza un DP: prueba de que un secreto sembrado no llega
al registro, con caso de control (texto sin secreto, intacto) y mutante («el redactor no actúa», debe morir).

## Licencia y precauciones

- MIT. No se copió código; solo patrones.
- No se instaló, descargó ni ejecutó nada. El escáner regex es defensa en profundidad, no garantía.
- Conteos de tests aproximados y no verificados ejecutando.
