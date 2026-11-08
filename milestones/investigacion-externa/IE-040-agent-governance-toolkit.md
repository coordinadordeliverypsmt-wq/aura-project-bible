---
id: IE-040
titulo: microsoft/agent-governance-toolkit — gobernanza de agentes (políticas, identidad, auditoría, sandbox)
fuente: https://github.com/microsoft/agent-governance-toolkit
rama-revision: main @ 46b370e77b7c13569d7525e337e31a9d3216c0b9 (commit del 2026-10-26, verificado por GitHub)
fecha-revision: 2026-10-26
licencia: MIT (LICENSE, © Microsoft Corporation). TRADEMARKS.md aparte. Licencias de las dependencias no auditadas
area: redes-seguridad
estado: referencia
cobertura: Lectura remota con `gh api` (metadatos, árbol de 4 982 ficheros, colaboradores, releases) y de README.md, docs/security/threat-model.md, policy-engine/README.md, agent-mesh/.../identity/mtls.py, governance/audit.py (parcial). NO se leyeron el núcleo Rust del policy-engine (`policy-engine/core/src/lib.rs`), handshake.py, delegation.py, el runtime de anillos ni los SDK de TS/.NET/Go/Rust. Sin clonar, instalar ni ejecutar
relacionadas: [IE-041, IE-042, IE-043, IE-032, DP-DELEGACION-NODOS]
---

Base de las citas: `B = https://github.com/microsoft/agent-governance-toolkit/blob/46b370e77b7c13569d7525e337e31a9d3216c0b9`.

Clasificación: **[CÓDIGO]** leído en el commit fijado · **[README]** declarado por los autores (incluye docs/) ·
**[TESTS-DECLARADOS]** pruebas que el repo dice tener, no ejecutadas · **[REPRODUCIDO-POR-TERCEROS]** con fuente ·
**[INFER]** inferencia.

## Qué se examinó (rutas y símbolos)

**Metadatos y procedencia** [CÓDIGO, `gh api`]:

- Propietario: organización `microsoft`. Creado el 2026-03-02; último push el 2026-10-26; ~6,5 k estrellas; 114 issues abiertas.
- Colaboradores principales: `dependabot[bot]` (947 commits), `imran-siddique` (864), `finnoybu` (229). Releases `v4.0.0` (2026-06-01) y `v4.1.0` (2026-06-09).
- Monorepo enorme: SDK en Python (2 641 ficheros: `agent-os`, `agent-mesh`, `agent-sre`, `agent-hypervisor`, `agent-sandbox`…), TypeScript, .NET, Go y Rust; un `policy-engine` en Rust (`agent-control-spec`); plugins para Claude Code, Codex, Copilot, OpenCode y Antigravity.
- Estado declarado: **«Public Preview … May have breaking changes before GA»** (`B/README.md#L37`) [README].

**Dependencias** [README]: variables opcionales `AZURE_CLIENT_ID/TENANT_ID/CLIENT_SECRET` para funciones integradas con Azure (`B/README.md#L312`); guías de despliegue en Azure, AWS, GCP y Docker Compose; integración Entra ID (`agentmesh/identity/entra*.py`, solo el nombre del fichero). El núcleo de políticas se puede usar sin nube [INFER: no verificado ejecutando].

## Patrones relevantes

| # | Afirmación | Evidencia | Clase |
|---|---|---|---|
| 1 | Modelo de amenazas con **STRIDE**, cuatro fronteras (humano→agente, agente→agente, agente→herramienta, agente→plano de control) y mapa amenaza→control por paquete | `B/docs/security/threat-model.md#L29-L94`, `#L163-L172` | [README] |
| 2 | **Sin políticas cargadas, la acción por defecto es `allow`**; el modo `permissive` permite todo; registrar una herramienta con otro nombre esquiva reglas por nombre; importar el módulo sin configurar da un falso estado «gobernado» | `B/docs/security/threat-model.md#L201-L211` | [README] |
| 3 | Esos vectores de bypass los identificó un **red-team externo** (Periculo, «15 bypass vectors») | `B/docs/security/threat-model.md#L213` | [REPRODUCIDO-POR-TERCEROS] (citado por el repo; el informe de Periculo **no** se leyó) |
| 4 | El policy-engine declara: determinista, y **fallo cerrado** ante errores de ejecución (`deny` con razón `runtime_error:*`) | `B/policy-engine/README.md#L75-L76` | [README] (el código Rust no se leyó) |
| 5 | Las intenciones `escalate` se normalizan a **`deny` con metadatos de aprobación**: la escalada a humano parte de una denegación, no de un permiso | `B/policy-engine/README.md#L158` | [README] |
| 6 | La telemetría de decisiones **no es portante**: «A sink that raises is caught and swallowed» | `B/policy-engine/README.md#L202` | [README] |
| 7 | mTLS: el servidor exige certificado de cliente por defecto (`require_client_cert=True`); en cliente, `verify_peer=False` desactiva **toda** verificación (`CERT_NONE`, sin hostname) | `B/agent-governance-python/agent-mesh/src/agentmesh/identity/mtls.py#L54-L57`, `#L185-L194` | [CÓDIGO] |
| 8 | Sin certificado configurado, genera uno **autofirmado efímero** | `mtls.py#L157-L180` | [CÓDIGO] |
| 9 | `verify_peer_certificate` da por **válido** un certificado **autofirmado** Ed25519 que contenga un DID `did:mesh:*`. Solo cruza la clave con un registro **si hay registro**; sin registro, `key_bound = True` | `mtls.py#L198-L250`, `#L286-L287` | [CÓDIGO] |
| 10 | Auditoría: `MerkleAuditChain` (hash encadenado + árbol Merkle) en una **lista en memoria**; la persistencia depende de un `AuditSink` **opcional** | `B/.../agentmesh/governance/audit.py#L568-L584`, `#L658` | [CÓDIGO] |
| 11 | Riesgos residuales que el propio repo admite: políticas válidas pero demasiado permisivas, **aprobadores humanos bajo presión**, credenciales que persisten entre tareas, incoherencia de métodos DID entre SDK | `B/docs/security/threat-model.md#L174-L199` | [README] |
| 12 | Cobertura «10/10 OWASP Agentic Top 10» | descripción del repositorio | [README] (afirmación de marketing; no verificada) |

## Límites, riesgos y dependencias

- **Superficie y peso:** monorepo de ~5 000 ficheros, cinco lenguajes y plugins de terceros. Para HC-1 (Celeron N4020, 3,6 GiB) solo cabría un componente aislado; el conjunto no [INFER].
- **Postura por defecto abierta** (fila 2): la gobernanza depende de la configuración, no de la construcción. Es la clase de defecto «declarado ≠ real» que AURA ya ha pagado [INFER].
- **Identidad que no es identidad** (fila 9): sin registro, un DID dentro de un certificado autofirmado solo prueba **posesión de una clave**, no **quién** es. Un atacante genera su clave, pone el DID que quiera y pasa la verificación [CÓDIGO + INFER].
- **Nube y claves de terceros:** opcionales, pero muy presentes en la documentación (Azure, Entra). Chocan con D24/ADR-0001 si entran en la ruta de ejecución [INFER].
- **Mantenimiento:** actividad muy alta; ~1/3 de los commits son de dependabot; bus factor bajo en el núcleo (un autor con 864 commits) [CÓDIGO].
- **Madurez:** Public Preview con cambios de ruptura anunciados.

## Comparación con AURA

| AURA | Relación | Clase |
|---|---|---|
| Lista roja y confirmación humana siempre (ADR-0003); `EVENTOS_GOBERNADOS` y `AutoridadNoHumana` (`entorno/control-plane/control_plane.py:1240`, `:1487`) | AURA ya es **deny-by-default por construcción** para eventos gobernados (`registrar_evento_si` niega antes de evaluar la condición, `:1941-1954`). AGT es **allow por defecto sin políticas** (fila 2). **AURA ya está mejor** | [LECT] |
| `escalate → deny + aprobación` (fila 5) | Mismo principio que la lista roja de AURA: la escalada no concede. **Ya cubierto** | [INFER] |
| `verificar_integridad_log` (`control_plane.py:1957-1976`): cadena de hash persistente, append-only, con punto de ruptura | AGT añade árbol Merkle y pruebas de inclusión, pero en memoria y con persistencia opcional. AURA persiste siempre. Ninguno de los dos ancla la **cabeza** de la cadena fuera del log (ver HAL-040-2) | [LECT] + [INFER] |
| Identidad de nodos: TLS mutua con **CA privada** (`entorno/nodos/red_hc1.py:_pki`) y receptor que rechaza un latido cuyo `nodo_id` no coincide con el subject (`walking-skeleton/aura_skeleton/adapters/receptor_nodos.py:106-111`) | AURA autentica por **cadena de CA**, no por autofirma: **ya es más fuerte** que la fila 9 sin registro. La brecha propia de AURA es otra: falta fijar **qué** servidor (SPKI, A3 de `DP-DELEGACION-NODOS.md` §11) | [LECT] |
| `review.py` con veredicto determinista; motor único | AGT ofrece un PDP genérico (OPA/Cedar/YAML). AURA no lo necesita: su autoridad es un conjunto cerrado de capacidades registradas | [INFER] |

## Hallazgos

**HAL-040-1 · La gobernanza que depende de la configuración falla abierta.**
- Problema: sin políticas, o en modo `permissive`, AGT permite todas las acciones.
- Mecanismo: acción por defecto `allow`; el estado «gobernado» se deduce de importar el módulo.
- Evidencia primaria: `B/docs/security/threat-model.md#L201-L213`.
- Grado de verificación: [README] + [REPRODUCIDO-POR-TERCEROS] (Periculo, citado; no leído). El código del valor por defecto no se leyó.
- Componente AURA: `control_plane.py` (`EVENTOS_GOBERNADOS`, `registrar_evento_si`, `transicion`), lista roja.
- Alternativa existente en AURA: niega los eventos gobernados **por construcción**, antes de evaluar nada.
- Beneficio / coste: confirma la decisión vigente de AURA; coste cero.
- Riesgos y condiciones de rechazo: no aplica (no se adopta nada).
- Criterio de aceptación de una prueba futura: una prueba que construya el control-plane **sin** configuración ni acta y compruebe que un evento gobernado se rechaza (`AutoridadNoHumana`), con un mutante que invierta el valor por defecto y muera.
- Autorización requerida: ninguna para la prueba de regresión; DP si cambia código.
- Clasificación: **PRIORIDAD MEDIA** (como prueba de regresión del valor por defecto cerrado; el patrón de AGT, **NO ADOPTAR**).

**HAL-040-2 · Un log con cadena de hash no detecta que le corten el final si la cabeza no se ancla fuera.**
- Problema: las tres implementaciones revisadas (AGT `MerkleAuditChain`, IE-042 `HashChainedLog`, IE-043 `AuditChain`) y AURA verifican la continuidad **desde el génesis**. Borrar los últimos eventos completos deja una cadena válida.
- Mecanismo: sin un hash de cabeza registrado fuera del fichero (checkpoint firmado, copia en otro medio, testigo), la verificación no sabe cuántos eventos debería haber.
- Evidencia primaria: `audit.py#L540-L559` (AGT); AURA `control_plane.py:1957-1976`.
- Grado de verificación: [CÓDIGO] (lectura) + [INFER] sobre el ataque; no ejecutado.
- Componente AURA: `verificar_integridad_log`, `eventos.jsonl`, `CHECKPOINT-CONTINUIDAD.md`.
- Alternativa existente en AURA: detección de cola **truncada a medias** (`_leer_con_cola`, `:1823`), que cubre caídas, no borrados limpios.
- Beneficio / coste: detectar retrocesos del log (ataque o restauración errónea) a cambio de guardar `(seq, hash)` de la cabeza en un segundo sitio.
- Riesgos y condiciones de rechazo: rechazar si el ancla vive en el mismo directorio y con los mismos permisos que el log (no añade nada), o si exige un servicio de terceros (D24).
- Criterio de aceptación: prueba que borre los N últimos eventos completos y compruebe que la verificación **con ancla** lo reporta y la verificación actual no (caso de control).
- Autorización requerida: Decision Package del CEO (toca el control-plane).
- Clasificación: **PRIORIDAD ALTA**.

**HAL-040-3 · Un certificado autofirmado con un DID no es identidad.**
- Problema: `verify_peer_certificate` acepta como válido cualquier certificado Ed25519 autofirmado con un `did:mesh:*` cuando no hay registro.
- Mecanismo: la autofirma solo prueba posesión de la clave; el DID lo escribe quien genera el certificado.
- Evidencia primaria: `mtls.py#L246-L250`, `#L286-L287`.
- Grado de verificación: [CÓDIGO] (lectura; no ejecutado).
- Componente AURA: identidad de nodos (`red_hc1.py`, `receptor_nodos.py`), delegación A1/A2/A3.
- Alternativa existente en AURA: CA privada + correspondencia subject/`nodo_id`; SPKI fijada propuesta (A3).
- Beneficio / coste: sirve como **caso de prueba negativo** para la delegación: «certificado autofirmado con el `nodo_id` correcto → rechazado».
- Riesgos y condiciones de rechazo: no adoptar el mecanismo de AGT.
- Criterio de aceptación: en la batería de §10.3 del DP de delegación, añadir el caso «autofirmado con id válido» además del «misma CA, otra huella».
- Autorización requerida: ninguna para anotarlo en el DP (documental); acta para implementar la delegación.
- Clasificación: **REFERENCIA** (como caso negativo); el mecanismo, **NO ADOPTAR**.

**HAL-040-4 · AGT como dependencia o herramienta.**
- Problema / mecanismo: monorepo en preview, multi-lenguaje, con integraciones de nube y valores por defecto abiertos.
- Evidencia primaria: `B/README.md#L37`, `#L312`; filas 2 y 9.
- Grado de verificación: [CÓDIGO] + [README].
- Componente AURA: ninguno.
- Alternativa existente en AURA: control-plane propio, más pequeño y cerrado por defecto.
- Beneficio / coste: bajo beneficio; coste alto de superficie, de RAM en HC-1 y de dependencias.
- Riesgos y condiciones de rechazo: viola el criterio «no crear componente sin demostrar que no existe equivalente» (§4 de CLAUDE.md).
- Criterio de aceptación: no aplica.
- Autorización requerida: acta del CEO para cualquier uso.
- Clasificación: **NO ADOPTAR**.

## Decisión

**Investigar más solo como referencia documental; NO ADOPTAR código ni dependencia.** Lo útil es el modelo de amenazas
como **lista de comprobación** (fronteras, STRIDE, vectores de bypass por configuración) y dos casos negativos para las
pruebas de AURA (HAL-040-1 y HAL-040-3). HAL-040-2 es un hueco **propio** de AURA que esta revisión hace visible.

## Validación mínima

1. Prueba de truncado limpio con y sin ancla externa (HAL-040-2), con su caso de control.
2. Prueba de valor por defecto cerrado del control-plane sin configuración, con mutante (HAL-040-1).
3. Caso «autofirmado con id válido → rechazado» en la batería de §10.3 de `DP-DELEGACION-NODOS.md` (HAL-040-3).

## Licencia y precauciones

- Código MIT. Las marcas de Microsoft no se licencian (`TRADEMARKS.md`).
- Las citas literales son de ≤ 3 líneas con su URL. No se copió código a AURA.
- No se instaló, descargó ni ejecutó nada. Las copias de texto para leer estuvieron en `/tmp` y se borraron.
- **Una declaración de gobernanza no es un control**: lo examinado muestra valores por defecto abiertos y un camino de identidad que, sin registro, no autentica.

## Contraste del orquestador sobre HAL-040-2 (2026-10-26): **CONFIRMADO en AURA `[EJEC-AURA]`**

**Lectura `[LECT]`:** `entorno/control-plane/control_plane.py`, `verificar_integridad_log`, en el entorno de L1955-1975:

- comprueba la continuidad de `seq` desde 1, `hash_anterior` y el hash de cada evento;
- **no compara** la cabeza con ningún ancla externa;
- `estado.json` no guarda ni el último `seq` ni el hash de cabeza.

**Ejecución `[EJEC]`:**

- Sobre una **copia** del `eventos.jsonl` real (3729 líneas), en un temporal del job, se borraron los **2 últimos eventos
  completos**.
- `verificar_integridad_log` devolvió `{'integro': True, 'eventos': 3727, 'cola_truncada': False}`.
- El original no cambió: sha `56a37569…` antes y después.

**Conclusión:**

- El borrado de **eventos finales completos** es **indetectable** con la verificación actual.
- `cola_truncada` solo detecta una línea final **parcial**.
- Es **deuda** (`CLAUDE.md` §7: puede producir pérdida de información), no una observación.

**Criterio de aceptación de una corrección futura:**

1. Una prueba RED que borre N eventos de cola y espere `integro: False`.
2. Un caso de control con el log intacto, que debe dar `integro: True`.
3. Un mutante que quite la comparación con el ancla y no sobreviva.
4. Un ancla **fuera del log**: hash de cabeza y `seq` en un fichero aparte, firmados o al menos escritos de forma
   atómica bajo el mismo `lock_estado`.
5. La compatibilidad con los logs existentes: el primer anclaje adopta la cabeza actual.

**Autorización:** Decision Package. Toca `control_plane.py`, que figura en `_INTOCABLES`.
