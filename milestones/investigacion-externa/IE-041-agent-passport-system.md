---
id: IE-041
titulo: Agent Passport System (APS) — identidad, delegación acotada, aplicación previa y recibos firmados
fuente: https://github.com/agent-passport-system (organización) → repositorio identificado: https://github.com/agent-passport-system/agent-passport-system
rama-revision: main @ f95c9168187cbac0493099fe4a7cddaff653bf39 (commit del 2026-10-23, verificado por GitHub)
fecha-revision: 2026-10-26
licencia: Apache-2.0 (LICENSE). El directorio LICENSES/ incluye además MIT, CC-BY-3.0 y LicenseRef-IETF-Trust-TLP para partes concretas (no se auditó a qué ficheros aplica cada una)
area: redes-seguridad
estado: adaptar ideas
cobertura: Lectura remota con `gh api` de la cuenta (18 repositorios), metadatos, árbol (1 448 ficheros), README.md, THREAT_MODEL.md, package.json, MIGRATION.md (sección del gateway), src/core/gateway.ts, src/core/execution-attestation.ts y src/core/tool-integrity.ts (parcial); README de agent-passport-gateway. NO se leyeron src/v2/, delegation.ts, los verificadores de recibos, la suite de conformidad ni el gateway (`@aeoess/gateway`). Sin clonar, instalar ni ejecutar
relacionadas: [IE-040, IE-042, IE-043, DP-DELEGACION-NODOS]
---

Base de las citas: `B = https://github.com/agent-passport-system/agent-passport-system/blob/f95c9168187cbac0493099fe4a7cddaff653bf39`.

Clasificación: **[CÓDIGO]** · **[README]** (incluye THREAT_MODEL y MIGRATION) · **[TESTS-DECLARADOS]** ·
**[REPRODUCIDO-POR-TERCEROS]** · **[INFER]**.

## Identificación del repositorio

La URL recibida es de una **cuenta**, no de un repositorio. `gh api users/agent-passport-system` la identifica como
**organización** «Agent Passport System (APS)», creada el 2026-05-05, web `agent-passport.org`, 18 repositorios
públicos. Entre ellos hay SDK (Python, Go, Rust), servidores MCP, un gateway, demos e integraciones.

El repositorio **`agent-passport-system/agent-passport-system`** es inequívocamente el «Agent Passport System»:

- tiene el mismo nombre que la organización;
- su descripción es «Open protocol and TypeScript SDK for AI agent authority…»;
- los demás repos remiten a él como SDK de referencia (p. ej. el README de `agent-passport-gateway`);
- es el único con estrellas significativas (56; el resto, 0-4).

**Estado de identificación: VERIFICADO.** Matiz de procedencia: el README del gateway enlaza a `aeoess/agent-passport-system`,
y el colaborador principal es `aeoess` (1 125 commits). Esto sugiere que el repositorio vivió antes en la cuenta personal
`aeoess` y se transfirió [INFER].

## Qué se examinó (rutas y símbolos)

**Metadatos** [CÓDIGO, `gh api`]: creado el 2026-02-18; último push el 2026-10-23; 10 issues abiertas; releases
`v8.0.0` (2026-10-14) y `v8.0.1` (2026-10-15). Ocho versiones mayores en ocho meses. Autor de los commits recientes:
Tymofii Pidlisnyi. Colaboradores: `aeoess` (1 125), `dependabot[bot]` (40), el resto ≤ 7. **Bus factor 1.**

**Dependencias** [CÓDIGO]: en ejecución solo `libsodium-wrappers` y `uuid` (`B/package.json`). El gateway que aplica la
autorización **no está en este repositorio**: `ProxyGateway` lanza `Error(MOVED)` y remite a `@aeoess/gateway`
(`B/src/core/gateway.ts#L3-L8`; `B/MIGRATION.md#L479-L491`). El gateway público de la organización
(`agent-passport-gateway`) usa SQLite y, de forma opcional, Stripe y la red de pagos Nano [README]. Una insignia del README
consulta `gateway.aeoess.com` [README].

## Patrones relevantes

| # | Afirmación | Evidencia | Clase |
|---|---|---|---|
| 1 | Identidad Ed25519 («passports»), `did:aps`; acepta también `did:key`, `did:web`, SPIFFE y OAuth | `B/README.md` §Core Protocol | [README] |
| 2 | **Delegación con estrechamiento monótono**: una subdelegación solo puede reducir el alcance; revocación en cascada | `B/README.md` §Core Protocol; `B/THREAT_MODEL.md#L26`, `#L53` | [README] |
| 3 | «3-signature action chain: agent signs intent, policy engine signs evaluation, agent signs execution receipt. The agent cannot skip the check» | `B/README.md#L67` | [README]. **El gateway que lo aplica no está en el repo** (fila 9) |
| 4 | **Cada recibo declara su `scope_of_claim`** (`asserts` / `does_not_assert`). Un `ActionReceipt` **no** prueba que el efecto se completara ni que el resultado fuera correcto | `B/README.md#L95-L123` | [README] |
| 5 | Lista de **usos indebidos que un verificador debe rechazar aunque la firma sea válida**: recibo de otro tipo, delegación caducada o revocada, evidencia autodeclarada presentada como observada, replay y **`POLICY_NOT_EXECUTED`** («A permit is not a proof that the action ran») | `B/README.md#L125-L138` | [README] + [TESTS-DECLARADOS] (fixtures en `tests/conformance/`, no ejecutados) |
| 6 | El modelo de amenazas separa **capa criptográfica** y **capa de contexto** (delegación vigente, presupuesto, principal, versión de la política, ventana de replay) y admite que todo depende de que el verificador las ejecute | `B/THREAT_MODEL.md#L59-L76` | [README] |
| 7 | Admite defectos de fallo abierto **pasados**: «Before 6.0.0 several verifiers read a timestamp they could not parse and treated it as no bound at all» | `B/THREAT_MODEL.md#L116-L118` | [README] |
| 8 | Admite que algunos verificadores de bajo nivel **autentican contra una clave que trae el propio artefacto**: integridad, no autoridad del firmante | `B/THREAT_MODEL.md#L99-L102` | [README] |
| 9 | El `ProxyGateway` (105 KB) se movió a `@aeoess/gateway`; el SDK conserva solo los tipos | `B/src/core/gateway.ts#L3-L8`; `B/MIGRATION.md#L479-L491` | [CÓDIGO] |
| 10 | `verifyExecutionAttestation` recibe la clave del atestador **del llamante** (bien), pero la vinculación con el recibo de política es **opcional**: sin `receipt`, `receiptBindingValid` queda en `true` | `B/src/core/execution-attestation.ts#L158-L183` | [CÓDIGO] |
| 11 | La atestación compara `parameterHash` con `intentParameterHash`, ambos **calculados por el propio atestador**: prueba coherencia interna de lo que el atestador dice, no corrección del resultado | `execution-attestation.ts#L185-L189` | [CÓDIGO] |
| 12 | Las marcas de tiempo ilegibles **fallan** («an unreadable clock is never a passing clock») | `execution-attestation.ts#L191-L205` | [CÓDIGO] |
| 13 | Integridad de herramientas: hash SHA-256 de la implementación y del manifiesto; un cambio de metadatos exige **re-aprobación** | `B/src/core/tool-integrity.ts#L109-L135`, `#L586` | [CÓDIGO] (parcial) |
| 14 | Cobertura «97 % líneas / 89 % ramas», fuzzing con Jazzer.js, CodeQL, SLSA, OpenSSF | insignias y `THREAT_MODEL.md#L108-L127` | [README] (no verificado) |

## Límites, riesgos y dependencias

- **La garantía central está fuera del repositorio** (fila 9). El SDK firma y verifica artefactos; quien decide y ejecuta es un gateway publicado aparte. Revisar este repo no permite afirmar que «el agente no puede saltarse la comprobación» [CÓDIGO + INFER].
- **Superficie enorme para un protocolo joven:** comercio, carteras, reputación bayesiana, EU AI Act, pagos x402, BBS+… en ~1 450 ficheros y ocho versiones mayores en ocho meses [CÓDIGO]. Riesgo de rotura y de deriva entre especificación y código [INFER].
- **Mantenimiento:** bus factor 1; ritmo muy alto [CÓDIGO].
- **Nube y claves:** el SDK no las exige; el gateway y las integraciones (Stripe, Nano, 1Password, ClickHouse) sí pueden [README].
- **Firma ≠ autorización ≠ resultado:** el propio proyecto lo dice (filas 4-6), y las filas 10-11 muestran dónde el código deja esa frontera en manos del verificador.

## Comparación con AURA

| AURA | Relación | Clase |
|---|---|---|
| `DP-DELEGACION-NODOS.md` §12.3: «La firma prueba **quién**, no **que sea correcto**»; sin verificador independiente en HC-1 (M3), la capacidad no es delegable | **Mismo principio** que `scope_of_claim` y `POLICY_NOT_EXECUTED` (filas 4-5). AURA ya lo tiene como requisito; APS aporta un **vocabulario** de rechazos | [LECT] |
| Estados `aceptada` / `declarada_ejecutada` / `verificada` (§10.1) | Equivalen a la separación APS entre `self_attested`, `gateway_observed` y la verificación del contexto. **Ya cubierto en diseño** | [LECT] + [INFER] |
| Firma de tareas por HC-1 (A1) y de resultados por el nodo (A2), con `hash_tarea` | Encaja con «intent firmado + atestación firmada por el ejecutor con su clave». La lección de la fila 10 aplica: **la vinculación tarea↔resultado debe ser obligatoria**, nunca opcional | [INFER] |
| Lista de capacidades delegables configurada en HC-1 y aprobada por el CEO, nunca autodeclarada (M5) | Equivale al estrechamiento monótono (fila 2) con un solo salto. AURA **no** permite subdelegación; no la necesita | [LECT] |
| Autoridad humana y `AutoridadNoHumana` (`control_plane.py:1487`) | APS tiene «human approval thresholds» en comercio [README]; AURA es más estricta (lista roja **siempre**) | [LECT] |

## Hallazgos

**HAL-041-1 · Catálogo de rechazos «firma válida, afirmación inválida» para los resultados remotos.**
- Problema: un resultado de nodo correctamente firmado puede usarse fuera de lo que afirma (otra tarea, otro intento, un permiso sin ejecución, una autodeclaración tomada como verificación).
- Mecanismo: cada artefacto declara qué afirma y qué no; el verificador corre la capa criptográfica **y** la de contexto, y rechaza con un código explícito.
- Evidencia primaria: `B/README.md#L125-L138`; `B/THREAT_MODEL.md#L68-L76`.
- Grado de verificación: [README] + [TESTS-DECLARADOS] (no ejecutados).
- Componente AURA: `resultado_remoto_rechazado{motivo}` (§10.2 de `DP-DELEGACION-NODOS.md`), verificador M3.
- Alternativa existente en AURA: el DP ya exige los cuatro campos de correlación y la verificación en HC-1; **no** tiene una lista cerrada de motivos de rechazo.
- Beneficio / coste: motivos de rechazo enumerados y uno por prueba → auditoría legible; coste documental.
- Riesgos y condiciones de rechazo: rechazar si se adoptan los formatos de APS (dependencia de un protocolo inmaduro); adoptar **solo** la idea.
- Criterio de aceptación: en la batería §10.3, un caso por motivo (`tarea_ajena`, `intento_no_en_curso`, `caducada`, `sin_ejecucion`, `autodeclarado_no_verificado`, `replay`), cada uno con su control positivo.
- Autorización requerida: ninguna para añadirlo al DP como propuesta; acta para implementarlo.
- Clasificación: **PRIORIDAD ALTA**.

**HAL-041-2 · La vinculación tarea↔resultado no puede ser opcional.**
- Problema: en APS, si el llamante no pasa el recibo, la atestación se da por vinculada.
- Mecanismo: parámetro opcional con valor por defecto `true` en la comprobación.
- Evidencia primaria: `B/src/core/execution-attestation.ts#L171-L183`.
- Grado de verificación: [CÓDIGO] (lectura; no ejecutado).
- Componente AURA: futura verificación de `resultado_remoto` (A2 + M3).
- Alternativa existente en AURA: el DP exige `hash_tarea` en el resultado firmado (§12.3, fila T de resultado).
- Beneficio / coste: evita un fallo abierto de diseño; coste nulo si se escribe en el contrato.
- Riesgos y condiciones de rechazo: no aplica.
- Criterio de aceptación: prueba que presente un resultado bien firmado **sin** `hash_tarea` o con el de otra tarea → rechazado; mutante que haga opcional la comprobación → debe morir.
- Autorización requerida: ninguna para el DP; acta para implementar.
- Clasificación: **PRIORIDAD ALTA**.

**HAL-041-3 · Un fichero de modelo de amenazas con «qué prueba» y «qué no prueba».**
- Problema: AURA reparte su análisis entre §10, §11 y §12 del DP de delegación.
- Mecanismo: APS cierra cada artefacto con una «Scope of claim» (`Proves` / `Does not prove`).
- Evidencia primaria: `B/THREAT_MODEL.md#L132-L136`.
- Grado de verificación: [README].
- Componente AURA: `DP-DELEGACION-NODOS.md` §12.
- Alternativa existente en AURA: D47 (clasificación de la evidencia) y las tablas STRIDE.
- Beneficio / coste: menor ambigüedad para el auditor; coste de redacción bajo.
- Riesgos y condiciones de rechazo: ninguno.
- Criterio de aceptación: no aplica (documental).
- Autorización requerida: ninguna.
- Clasificación: **REFERENCIA**.

**HAL-041-4 · APS como dependencia o protocolo.**
- Problema / mecanismo: SDK joven y muy amplio, con la aplicación real fuera del repo y un único mantenedor.
- Evidencia primaria: filas 9 y 14; metadatos.
- Grado de verificación: [CÓDIGO] + [README].
- Componente AURA: ninguno.
- Alternativa existente en AURA: el diseño de A1/A2/M3 ya cubre lo necesario con un esquema propio y mínimo.
- Beneficio / coste: bajo; coste alto (Node en el nodo, superficie, deriva de versiones).
- Riesgos y condiciones de rechazo: bus factor 1; ocho versiones mayores en ocho meses.
- Criterio de aceptación: no aplica.
- Autorización requerida: acta del CEO para cualquier uso.
- Clasificación: **NO ADOPTAR**.

## Decisión

**Adaptar ideas, sin código ni dependencia.** Son útiles el vocabulario de rechazo y la distinción
autodeclarado / observado / verificado (HAL-041-1), y el principio de que la vinculación tarea↔resultado es obligatoria
(HAL-041-2). Ambos refuerzan requisitos que `DP-DELEGACION-NODOS` ya tiene. No hay que construir nada nuevo hasta que se
apruebe la delegación.

## Validación mínima

- En la batería aislada de §10.3, cuando se autorice: un caso negativo por motivo de rechazo y el caso «sin vinculación → rechazado», cada uno con su mutante.
- Comprobar ejecutando que un resultado autodeclarado nunca lleva una tarea a `completada` sin pasar por `verificada`.

## Licencia y precauciones

- Apache-2.0 con ficheros bajo otras licencias (`LICENSES/`). Si algún día se reutilizara texto o código, habría que revisar la cabecera SPDX de cada fichero.
- No se instaló, descargó ni ejecutó nada. Las citas son de ≤ 3 líneas con su URL. Las copias para leer estuvieron en `/tmp` y se borraron.
- Las insignias (conformidad, OpenSSF, OpenChain «self-certified») son **autodeclaraciones**; no se verificaron.
