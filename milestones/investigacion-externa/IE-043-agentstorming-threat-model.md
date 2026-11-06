---
id: IE-043
titulo: aws-samples/sample-agentstorming — modelo de amenazas de salas multiagente firmadas (método y amenazas aplicables)
fuente: https://github.com/aws-samples/sample-agentstorming/blob/main/docs/security/threat-model.md
rama-revision: main @ e154ec224b32a93f0a21c957ab4b49c06756846c (commit del 2026-09-15; el documento entró en c1d35ea, misma fecha). El `pushed_at` del 2026-10-24 corresponde a ramas de dependabot, no a `main`
fecha-revision: 2026-10-26
licencia: MIT-0 (LICENSE, «MIT No Attribution», © Amazon.com, Inc. or its affiliates; SPDX MIT-0 en los fuentes leídos)
area: redes-seguridad
estado: adoptar el método (documental)
cobertura: Lectura completa de docs/security/threat-model.md (240 líneas). Contraste en código de tres mitigaciones que el documento declara: packages/storm-broker/storm_broker/roommode.py, peercred.py y audit.py (completos). NO se leyeron policy.py, server.py, la especificación (docs/specification.md), los ADR ni las pruebas. Sin clonar, instalar ni ejecutar
relacionadas: [IE-040, IE-041, IE-042, IE-032, DP-DELEGACION-NODOS]
---

Base de las citas: `B = https://github.com/aws-samples/sample-agentstorming/blob/e154ec224b32a93f0a21c957ab4b49c06756846c`.
Documento: `TM = B/docs/security/threat-model.md`.

Clasificación: **[CÓDIGO]** · **[README]** (el documento de amenazas es declaración de los autores) ·
**[TESTS-DECLARADOS]** · **[REPRODUCIDO-POR-TERCEROS]** · **[INFER]**.

## Qué se examinó (rutas y símbolos)

**Metadatos y procedencia** [CÓDIGO, `gh api`]: organización `aws-samples` (repositorios de ejemplo de AWS). Creado el
2026-09-15 con un único commit de contenido de Yudho Ahmad Diponegoro; 2 estrellas; 11 issues abiertas. Es un **ejemplo de
referencia, no un producto**, y el propio documento dice que **no ha pasado una prueba de penetración** (`TM#L13-L16`).
**Mantenimiento:** prácticamente nulo tras la publicación, salvo dependabot [CÓDIGO].

**Dependencias del sistema descrito** [README]: Postgres, FastAPI, SSE; despliegue de ejemplo en AWS (ECS, RDS, S3, KMS,
Secrets Manager, AgentCore) con Terraform; proveedores de LLM de terceros, que **leen el contenido de la sala**
(`TM#L130-L136`). No aplica a AURA como dependencia; solo se extrae el método.

## Método del documento

| Elemento | Qué hace | Evidencia | Clase |
|---|---|---|---|
| Activos ordenados por valor para el atacante (A1-A9), con **dónde viven** | Separa claves privadas, raíz de gobernanza, credenciales, tokens, autoridad del moderador, historial y gasto | `TM#L37-L53` | [README] |
| **Fronteras de confianza** (B1-B7) con diagrama; una tabla amenaza · mitigación · **residual** por frontera | No es STRIDE; cada fila obliga a escribir lo que queda abierto | `TM#L55-L164` | [README] |
| **Fuera de alcance explícito** (operador con shell, E2EE, análisis de tráfico, DDoS, propietario malicioso, comportamiento del modelo) | Evita que el revisor infiera garantías inexistentes | `TM#L166-L180` | [README] |
| **Defectos encontrados y corregidos** como evidencia de que el modelo es real | «A threat model that has never caught anything is a document, not a control» | `TM#L182-L198` | [README] |
| **Huecos conocidos: especificado pero no implementado** | Separa lo que un lector de la especificación daría por hecho | `TM#L200-L216` | [README] |
| **Obligaciones del desplegador** | Lo que el código no puede garantizar | `TM#L218-L240` | [README] |

## Patrones relevantes

| # | Afirmación | Evidencia | Clase |
|---|---|---|---|
| 1 | **El agente es la parte no confiable para su propio broker**: las credenciales viven solo en el broker (otro uid) y el agente recibe resultados, nunca secretos | `TM#L29-L33`, `#L116-L128` | [README] |
| 2 | El broker **no cree al agente** cuando dice «la sala está activa»: exige el evento `mode_promoted` **firmado por el servidor**, verifica la firma **sobre los bytes exactos**, comprueba sala, emisor `system`, modo válido, antigüedad ≤ 24 h, reloj ≤ 5 min adelantado y **monotonía** (no reaplica uno igual o anterior) | `B/packages/storm-broker/storm_broker/roommode.py#L71-L148` | [CÓDIGO] |
| 3 | Fue un **defecto real**: el broker confiaba en la afirmación del agente y el modo de planificación era decorativo (ADR-008) | `TM#L192` | [README] |
| 4 | Comprobación `SO_PEERCRED` por uid en el socket Unix; **en plataformas no soportadas lanza**, no omite la comprobación | `B/packages/storm-broker/storm_broker/peercred.py#L28-L78` (`#L63`) | [CÓDIGO] |
| 5 | Identidad **derivada de la clave** (`PID = base64url(sha256(pubkey))@room`), no afirmada; firma Ed25519 por evento sobre JCS (RFC 8785); ventana de nonces y desfase de 30 s | `TM#L98-L101` | [README] (no contrastado en código) |
| 6 | **Servidor malicioso:** no puede falsificar eventos, pero **sí censurar, reordenar, retener y leer** | `TM#L103` | [README] |
| 7 | **Inyección de prompt sin solución:** «A peer can talk your agent into misusing its own legitimate authority» → acotar lo que el agente **puede** hacer, no lo que **dice** | `TM#L112`, `#L238-L240` | [README] |
| 8 | Autoridad del moderador = **identidad del asiento**, no un umbral numérico; el defecto `power_level < 50` dejaba pasar a cualquier miembro en diez endpoints | `TM#L113`, `#L190` | [README] |
| 9 | **Tool poisoning sin mitigar**: la fijación SHA-256 de la descripción de herramientas está especificada pero **ningún código la calcula** | `TM#L138-L143`, `#L207` | [README] (declaración de hueco) |
| 10 | Registro de auditoría append-only con **HMAC-SHA-256 encadenado** en JSONL; verificación desde el génesis; anclaje externo (Rekor) solo como intención futura | `B/packages/storm-broker/storm_broker/audit.py#L4-L14`, `#L69-L101` | [CÓDIGO] |
| 11 | Defectos operativos reales: contraseña en `cloud-init-output.log` por `set -x`; correo de seguridad en un dominio **no registrado**; instrucciones de `pip install` de nombres **libres** en PyPI/npm | `TM#L194-L196` | [README] |
| 12 | Escáneres (Bandit, Checkov, Semgrep, Grype…) limpios y 210 pruebas, **explícitamente no equivalentes a un pentest** | `TM#L210` | [README] + [TESTS-DECLARADOS] |

## Límites, riesgos y dependencias

- Es un **documento de amenazas de un ejemplo**, con un solo autor y sin mantenimiento; su valor es metodológico [CÓDIGO + INFER].
- Solo tres mitigaciones se contrastaron en código (filas 2, 4 y 10). El resto es declaración [README].
- El registro de la fila 10 tiene las mismas limitaciones que el de AURA frente a un borrado limpio del final (ver HAL-040-2), y compara el HMAC con `!=` en vez de en tiempo constante (`audit.py#L94-L99`) [CÓDIGO; impacto bajo, local].
- B6 (operador con shell en el host) queda fuera de alcance: lo mismo ocurre en AURA para HC-1 [INFER].

## Comparación con AURA

| AURA | Relación | Clase |
|---|---|---|
| `DP-DELEGACION-NODOS.md` §12 (STRIDE con columna «Estado» ABIERTO/REQUERIDO) | El método de agentstorming añade tres columnas o secciones que el DP **no** tiene: **dónde vive cada activo**, **riesgo residual** tras la mitigación y **fuera de alcance explícito** | [LECT] |
| Nodo con **tabla de funciones fija**, sin `exec` ni shell; lista delegable aprobada por el CEO (M5) | Mismo principio que las filas 1 y 7: el ejecutor no es confiable, se acota lo que **puede** hacer | [LECT] |
| Firma de tareas por HC-1 (A1) con `caduca_en` y rechazo de replay | La fila 2 es un **patrón concreto ya probado** para verificar en el nodo una orden firmada: verificar sobre bytes exactos sin re-canonicalizar, leer los datos **solo** de los bytes verificados, comprobar destinatario, frescura y **monotonía** | [CÓDIGO] + [INFER] |
| Receptor que rechaza un latido cuyo `nodo_id` no coincide con el subject (`receptor_nodos.py:106-111`) | Análogo a «identidad derivada, no afirmada» (fila 5), aplicado al canal | [LECT] |
| Procesos con uid propio; socket Unix | El firmador único de N2 (`DP-DELEGACION-NODOS.md` §12.6) es la misma idea que el broker en otro uid (fila 4). La comprobación por `SO_PEERCRED` con fallo cerrado es directamente aplicable a ese firmador | [INFER] |
| Registro de capacidades por **resultado** («no se nombran por herramienta») | La fila 9 recuerda que una descripción de capacidad que cambia sin detectarse es un vector; en AURA las capacidades están en código, no las describe un servidor externo | [INFER] |

## Hallazgos

**HAL-043-1 · Verificación de una orden firmada en el nodo: bytes exactos, frescura y monotonía.**
- Problema: A1 exige que el nodo verifique la tarea «antes de nada», pero el DP no fija cómo evitar la deriva de canonicalización ni el replay tras un cambio de estado.
- Mecanismo: el verificador recibe los **bytes canónicos exactos** firmados, verifica la firma, y solo entonces lee los datos de esos mismos bytes; comprueba destinatario, emisor, antigüedad máxima, desfase de reloj y que el `iat` sea **estrictamente posterior** al último aceptado.
- Evidencia primaria: `roommode.py#L71-L148`.
- Grado de verificación: [CÓDIGO] (lectura; no ejecutado).
- Componente AURA: `nodo_agente.py` (futuro verificador de tareas), A1 y fila «R · replay» de §12.3.
- Alternativa existente en AURA: `caduca_en` absoluto y firmado; rechazo de lo emitido antes del arranque del nodo (propuesto).
- Beneficio / coste: cierra el replay de una orden antigua y la deriva entre dos serializadores (Python en HC-1 y en el nodo); unas decenas de líneas propias.
- Riesgos y condiciones de rechazo: la monotonía exige guardar el último `iat` aceptado; si el nodo no guarda estado (§10.2 «cae el nodo: no guarda estado»), se sustituye por «rechazar lo emitido antes del arranque» + `id_ejecucion` en memoria. Rechazar si obliga a persistir estado de seguridad en el nodo sin acta.
- Criterio de aceptación: pruebas aisladas con (a) firma válida sobre bytes re-serializados de otra forma → rechazo, (b) orden válida reenviada tras otra más reciente → rechazo, (c) orden con reloj adelantado más allá de la tolerancia → rechazo; cada una con control positivo y mutante.
- Autorización requerida: acta del CEO sobre A1 (pendiente en el DP).
- Clasificación: **PRIORIDAD ALTA**.

**HAL-043-2 · Completar el STRIDE de la delegación con activos, residual, fuera de alcance y huecos «especificado ≠ implementado».**
- Problema: §12 del DP lista amenazas y controles, pero no **dónde vive cada activo**, **qué queda abierto tras la mitigación** ni **qué se excluye expresamente**.
- Mecanismo: el método de agentstorming (tablas por frontera con columna «Residual», sección «fuera de alcance» y sección «huecos conocidos»).
- Evidencia primaria: `TM#L37-L53`, `#L94-L164`, `#L166-L216`.
- Grado de verificación: [README] (es método, no código).
- Componente AURA: `milestones/m3-entry/DP-DELEGACION-NODOS.md` §12.
- Alternativa existente en AURA: columna «Estado» y la regla D47; el patrón «declarado ≠ real» de §5 de CLAUDE.md.
- Beneficio / coste: el auditor ve el residual sin inferirlo; la sección de huecos es la defensa directa contra «declarado ≠ real». Coste documental bajo.
- Riesgos y condiciones de rechazo: ninguno.
- Criterio de aceptación: revisión independiente (`security-reviewer`) que confirme que cada fila tiene residual y que todo lo «REQUERIDO, no implementado» aparece también en la sección de huecos.
- Autorización requerida: ninguna (documental, dentro de la propuesta ya autorizada como solo documental).
- Clasificación: **PRIORIDAD MEDIA**.

**HAL-043-3 · `SO_PEERCRED` con fallo cerrado para el firmador único de HC-1.**
- Problema: N2 exige que solo la vía planificador → `review` → PARADA → lista roja pueda pedir firmas; otros procesos del usuario de HC-1 no.
- Mecanismo: socket Unix; el firmador lee el uid del par con `SO_PEERCRED` y rechaza cualquier uid no autorizado; en plataformas sin soporte, lanza.
- Evidencia primaria: `peercred.py#L28-L78`; `TM#L125`.
- Grado de verificación: [CÓDIGO] (lectura).
- Componente AURA: firmador único de N2 (`DP-DELEGACION-NODOS.md` §12.6).
- Alternativa existente en AURA: ninguna implementada; IE-032 ya registró este patrón como reutilizable.
- Beneficio / coste: separa por uid quién puede firmar; coste bajo. **Residual:** cualquier proceso con el mismo uid del cliente autorizado pasa (`TM#L125`).
- Riesgos y condiciones de rechazo: no basta por sí solo; debe ir con un uid dedicado para el planificador.
- Criterio de aceptación: prueba con dos procesos de uid distinto: el no autorizado → rechazado; control con el autorizado.
- Autorización requerida: acta del CEO sobre N2.
- Clasificación: **PRIORIDAD MEDIA**.

**HAL-043-4 · Sección «defectos encontrados» como evidencia de que el modelo de amenazas controla algo.**
- Problema / mecanismo: un modelo de amenazas sin defectos encontrados no demuestra que funcione.
- Evidencia primaria: `TM#L182-L198`.
- Grado de verificación: [README].
- Componente AURA: DP de delegación; registro de errores de §5 de CLAUDE.md.
- Alternativa existente en AURA: §12.6 ya recoge correcciones de la revisión independiente (N1-N10).
- Beneficio / coste: ya practicado en AURA de hecho.
- Riesgos y condiciones de rechazo: ninguno.
- Criterio de aceptación: no aplica.
- Autorización requerida: ninguna.
- Clasificación: **REFERENCIA**.

## Decisión

**Adoptar el método (documental) y adaptar dos patrones de código sin copiarlo.** El método completa el STRIDE de la
delegación (HAL-043-2). La verificación del modo firmado (HAL-043-1) es la mejor plantilla de las cuatro fichas para que el
nodo verifique una orden de HC-1. `SO_PEERCRED` (HAL-043-3) sirve para el firmador único. Nada se integra como dependencia.

## Validación mínima

- Documental, ya: revisión independiente del §12 ampliado con activos, residual, fuera de alcance y huecos (HAL-043-2).
- Con acta sobre A1 y N2: las pruebas de HAL-043-1 y HAL-043-3 en la batería aislada de §10.3, nunca contra NODO-01, con sus mutantes.

## Licencia y precauciones

- MIT-0: permite reutilizar sin atribución; aun así se cita la fuente por trazabilidad.
- No se instaló, descargó ni ejecutó nada. Las citas son de ≤ 3 líneas con su URL. Las copias para leer estuvieron en `/tmp` y se borraron.
- El documento describe un **ejemplo sin pentest**: sus mitigaciones no son garantías, y la de tool poisoning no existe en el código.
