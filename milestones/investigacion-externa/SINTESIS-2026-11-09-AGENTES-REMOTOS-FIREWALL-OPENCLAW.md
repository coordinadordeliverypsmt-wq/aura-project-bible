---
documento: "Síntesis — agente remoto, cortafuegos de agentes y OpenClaw (IE-044 … IE-046)"
fecha: 2026-11-09
tipo: "Investigación de código y patrones. Nada instalado, ejecutado ni desplegado."
evidencia: "[CÓDIGO]/[README] leído en el repo externo · [INFER] · [HIPO] no verificado. Comparación con AURA sobre integracion/m3-entry @ 803b72f"
---

# Síntesis — agentes remotos, firewall y OpenClaw

Fichas: [IE-044](IE-044-ai-remote-agent.md) · [IE-045](IE-045-agent-wall.md) · [IE-046](IE-046-openclaw.md).
Cobertura: lectura parcial de clones locales (cada ficha declara qué NO se leyó). Ningún repositorio se revisó completo.
Ninguna recomendación fija prioridad: decide el CEO.

## 1. Conclusión

Ninguno de los tres aporta algo no registrado ya en IE-040 a IE-043, **salvo dos huecos nuevos** para INVESTIGAR MÁS:
la **redacción de secretos y PII** (IE-045) y el **alta asistida de nodos** (IE-046). Además quedan dos cubiertos
parcialmente el **sandbox** (IE-046); el **techo de tasa en el Motor** (IE-044) no está cubierto.

## 2. Patrones útiles (INVESTIGAR MÁS)

| Patrón | Origen | Hueco en AURA | Prueba de refutación |
|---|---|---|---|
| Redacción de secretos y PII en registros y respuestas | IE-045 (ResponseScanner) | **Nuevo.** Grep vacío en `observability` y `automatizacion` | Grep de patrones de clave, token y PII en `audit.jsonl` y `eventos.jsonl` reales. Si no hay nada, se descarta |
| Alta asistida de un nodo nuevo (código de un solo uso, TTL, aprobación humana) | IE-046 (pairing) | **Nuevo.** Existe identidad, pinning SPKI y firma, no el alta asistida (`W/adapters/identidad_nodo.py`, `fijacion_spki.py:38-128`) | Con un solo NODO-01 dado de alta a mano no amortiza |
| Techo de tasa en el Motor | IE-044 (`device-commands.js:50-60`) | **NO CUBIERTO**: AURA no tiene techo de tasa; `W/nodo_agente.py` solo tiene backoff de reconexión (l.56-57) y no hay techo en `W/core/automatizacion.py:98` | Contar en el historial real las acciones rojas por minuto. El valor 30/min **no** es transferible (regla del CEO, 2026-08-04) |
| Sandbox endurecido | IE-046 (`container-allocation.ts`) | Parcial: `CP/aislamiento.py:534`; `test_red_candidato_aislado.py` ya niega red y escritura | Si las pruebas existentes cubren las propiedades, no hay hueco; Docker añadiría dependencia (ADR-0016) |

## 3. Patrones ya cubiertos por AURA (DESCARTAR)

| Patrón | Dónde en AURA |
|---|---|
| Política de primera coincidencia con denegación por defecto (IE-044) | `W/core/permissions.py:171-210` (kill switch en `:172`); IE-040 L61-62 |
| Auditoría en cadena SHA-256 (IE-044) | `CP/control_plane.py:2186, 2225`; `W/observability.py:194-425`; `AuditBloqueado :104`; hueco de cabeza de IE-040 HAL-040-2 posiblemente cerrado por D-LOG-1 (ancla externa en `control_plane.py:1881` y `:2226`) [INFER] |
| Aprobación ligada a un hash (IE-044) | `W/core/decisiones.py:47-59`; `W/adapters/hitl_diferido.py:44-63` |
| Prompt humano por tty (IE-045) | `hitl_diferido` con huella |
| Kill switch por fichero (IE-045) | `W/core/kill_switch.py:11-29` |
| Shell por argv con allowlist (IE-044) | `CP/delegacion.py:135-143, 219-270, 522-550` |
| Autenticación en tiempo constante y límite por IP (IE-046) | Canal mTLS con pinning |

## 4. Patrones incompatibles

| Patrón | Regla que lo impide |
|---|---|
| Razonamiento y contexto en la nube (IE-044; extensiones de nube de IE-046) | D24 / ADR-0001 |
| El LLM verifica sus propios resultados (IE-044) | INV-9, ADR-0014; verificador independiente de DP-DELEGACION-NODOS §12.3 |
| Shell genérico (IE-044) | CLAUDE.md §4: solo capacidades registradas |
| Proxy MCP (IE-045) | AURA no tiene MCP; sería una segunda vía de ejecución (ALERTA-005) |
| «allow-always» persistente (IE-046) | ADR-0003: la lista roja pide confirmación siempre |
| Escáner de skills / ClawHub (IE-046) | D24 (servicio de terceros) |
| Dashboard sin autenticación en todas las interfaces (IE-045) | Seguridad |

Descartados por ahora (sin superficie): detección de inyección por regex y envoltura de contenido externo, porque
no hay LLM con texto externo en el bucle.

## 5. Riesgos

| Severidad | Riesgo | Ficha |
|---|---|---|
| CRITICAL | Dependencia de la nube para razonar | IE-044 |
| HIGH | Exfiltración (Bearer único + contexto; más de 190 extensiones de nube) | IE-044, IE-046 |
| HIGH | Anti-replay ausente o aprobación sin TTL ni hash | IE-044, IE-045 |
| HIGH | Inyección sin defensa efectiva (regex fail-open; declarada como no vulnerabilidad) | IE-045, IE-046 |
| HIGH | Ejecución y escalada (plugins con privilegios del host; allow-always) | IE-046 |
| HIGH (transversal) | Ninguno verifica resultados con fuente independiente del LLM; en AURA lo hace el Core (ADR-0014) | las tres |
| HIGH | Auditoría sin clave o con HMAC desactivado, y con errores tragados (`policy.js:297`) | IE-044, IE-045 |
| MEDIA | TTL de emparejamiento de 1 h | IE-046 |

Declarado ≠ real: IE-044 declara identidad, JIT y recibos que **no están cableados** en el demonio.

**Condiciones mínimas si algún patrón se adoptara** (revisión de seguridad):

- Gate: denegación por defecto con pruebas, lista roja no anulable y fail-closed.
- Techo de tasa: fuera del alcance del LLM, persistente y aplicado en el Motor.
- Cadena de auditoría: con clave fuera del proceso o con ancla externa; fallo de escritura = acción bloqueada.
- Aprobación: hash canónico de la acción completa, nonce de un solo uso, TTL corto, consumo atómico, nunca generada por el LLM.
- Emparejamiento: CSPRNG, un solo uso, TTL de minutos, límite de intentos y vínculo al dispositivo.
- Entorno: lista blanca, no lista negra.
- Envoltura y escaneo de respuestas: solo defensa en profundidad, nunca garantía.

## 6. Licencias

| Repositorio | Licencia | Nota |
|---|---|---|
| AI-Remote-Agent | MIT | Transitivas [HIPO] |
| agent-wall | MIT | Transitivas [HIPO] |
| openclaw | MIT | THIRD_PARTY_NOTICES: SQLite (dominio público), pi-mono (MIT), Octicons (MIT), Hermes Agent (MIT); nada GPL ni AGPL |

Copiar código exigiría conservar el aviso MIT. **Recomendación: solo patrones, sin copiar código.**

## 7. Recomendación de aprendizaje

1. Guardar las fichas y esta síntesis como referencia; las comprobaciones de refutación (grep de secretos y PII en
   registros reales, historial de acciones por minuto, plan de número de nodos) son baratas y de solo lectura.
2. Ejecutar la refutación **solo si** un bloqueo real y repetido del uso diario lo pide (regla del CEO, 2026-08-04: el
   desarrollo lo guía la evidencia del uso real). Si la refutación sobrevive, entonces proponer un Decision Package.
3. Las mediciones se hacen sobre una copia exportada, nunca con el arnés de mutación en marcha (CLAUDE.md §2).
4. Lección transversal: la verificación del resultado y la aprobación no pueden quedar al alcance del LLM; AURA ya lo cumple.

## 8. Relación con el roadmap vigente

**Esta síntesis NO amplía M3 ni crea capacidades.** Ningún patrón entra en la hoja de ruta. Cualquier adopción exige
Decision Package aprobado y acta del CEO (D23: alcance funcional del MVP cerrado). Las herramientas estudiadas son
externas a AURORA (CLAUDE.md §4).

## 9. Discrepancia de continuidad D-INT-1

Hallazgo de proceso detectado al preparar esta misión, **fuera del alcance de la investigación**:

- El merge `1d23c788b880667e296acf8c1537f0c423e437cf` **está en `origin/main`**.
- El `CHECKPOINT-CONTINUIDAD.md` de `main` todavía presenta D-INT-1 como **«DECISIÓN REQUERIDA»** en la línea 3891.
- Causa: el cierre se registró en `eacce22` («docs(checkpoint): D-INT-1 integrada en main; F5 completa»), commit
  **posterior al merge** que está en `integracion/m3-entry` (líneas 12003-12010 de su checkpoint) y en `feat/m3-tv-lectura`, pero **no en `origin/main`**.
- La sección antigua de la línea 3891 **no está marcada como superada**: un lector que reanude desde `main` podría
  creer que D-INT-1 sigue abierta (variante del patrón «declarado ≠ real»).
- **Recomendación:** anotar «superado por eacce22» en la sección de la línea 3891, en una misión documental autorizada.
- **Esta síntesis NO modifica el checkpoint.**

Evidencia: verificado por la auditoría de consistencia: el checkpoint de `origin/main` :3891 dice DECISIÓN REQUERIDA; `eacce22` no es ancestro de `origin/main` [LECT].

## 10. Secundarias no estudiadas

- `NVIDIA/NemoClaw` y `NousResearch/hermes-agent` **NO se estudiaron** en esta misión.
- Hermes Agent aparece como componente MIT en `THIRD_PARTY_NOTICES` de openclaw (`:88`).
- **Pendiente.** Estudiarlos solo con orden explícita; no se asume nada sobre ellos.
