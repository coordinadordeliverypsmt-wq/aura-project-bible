---
id: IE-042
titulo: oxdeai/oxdeai — autorización determinista de ejecución antes de efectos (PDP + PEP con artefactos firmados)
fuente: https://github.com/oxdeai/oxdeai
rama-revision: main @ b4beddf2bbe135990d4ead5ab1e2fd2761b225f3 (commit del 2026-10-26, verificado por GitHub)
fecha-revision: 2026-10-26
licencia: Apache-2.0 (LICENSE; cabeceras SPDX Apache-2.0 en los fuentes leídos). Licencias de las dependencias no auditadas
area: redes-seguridad
estado: adaptar el patrón
cobertura: Lectura remota con `gh api` de metadatos, árbol (819 ficheros), README.md, docs/audits/2.0-residual-scope.md, packages/core/src/types/authorization.ts, packages/core/src/verification/verifyAuthorization.ts, packages/core/src/audit/HashChainedLog.ts, packages/guard/src/guard.ts (comentarios de contrato y puntos de verificación), package.json de core y guard, cabecera de replayStore.ts. NO se leyeron PolicyEngine.ts ni sus módulos, verifyDelegation.ts, gateway.ts, secureGuard.ts, los vectores de conformidad ni las pruebas. Sin clonar, instalar ni ejecutar
relacionadas: [IE-040, IE-041, IE-043, DP-DELEGACION-NODOS]
---

Base de las citas: `B = https://github.com/oxdeai/oxdeai/blob/b4beddf2bbe135990d4ead5ab1e2fd2761b225f3`.

Clasificación: **[CÓDIGO]** · **[README]** (incluye docs/) · **[TESTS-DECLARADOS]** · **[REPRODUCIDO-POR-TERCEROS]** · **[INFER]**.

## Qué se examinó (rutas y símbolos)

**Metadatos y procedencia** [CÓDIGO, `gh api`]:

- Organización `oxdeai`; creado el 2026-02-26; último push el 2026-10-26; 14 estrellas; 32 issues abiertas.
- Colaboradores: `AngeYobo` (715 commits), `Whatsonyourmind` (21), otro (1). **Bus factor 1.**
- Releases por paquete (`sdk-v2.0.2`, `guard-v2.0.3`, 2026-10-21). Monorepo TypeScript (pnpm) con `core`, `guard`, `sdk`, `conformance`, `cli` y adaptadores (LangGraph, OpenAI Agents, OpenClaw, CrewAI, AutoGen); verificadores en Go, Python y Rust para una parte del protocolo.

**Dependencias** [CÓDIGO]: `@oxdeai/guard` depende solo de `@oxdeai/core` (`B/packages/guard/package.json`); `core` no declara
dependencias de ejecución (solo `devDependencies`). Usa `node:crypto`. Hay un `ReplayStore` en Redis opcional
(`packages/guard/src/replayStore.redis.ts`). Sin nube ni claves de terceros en el núcleo [CÓDIGO]. El *quick start* usa un
secreto HMAC de demostración en una variable de entorno [README].

## Patrones relevantes

| # | Afirmación | Evidencia | Clase |
|---|---|---|---|
| 1 | Modelo `(intent, state, policy) → ALLOW | DENY` determinista; si `ALLOW`, emite un `AuthorizationV1` firmado que liga `intent_hash`, `state_hash`, `policy_id`, `audience`, `expiry` y `nonce` | `B/README.md#L1-L45`; `B/packages/core/src/types/authorization.ts#L3-L23` | [README] + [CÓDIGO] |
| 2 | El **PEP** (`OxDeAIGuard`) exige `trustedKeySets` no vacío al construirse; si falta, error de configuración | `B/packages/guard/src/guard.ts#L145-L154` | [CÓDIGO] |
| 3 | El guard verifica la autorización con **modo estricto y firma obligatoria** antes de llamar a `execute()` | `guard.ts#L585-L593`, `#L314-L318`; orden documentado en `#L90-L135` | [CÓDIGO] |
| 4 | La **función de biblioteca** `verifyAuthorization`, sin opciones, es **permisiva**: sin `trustedKeySets` ni `requireSignatureVerification`, una autorización con firma Ed25519 —o sin material de firma— devuelve `ok: true` con `signatureVerified: false` | `B/packages/core/src/verification/verifyAuthorization.ts#L403-L421`, `#L462-L493` | [CÓDIGO] (lectura; no ejecutado) |
| 5 | La documentación advierte que, sin `trustedAuthorizationAuthorities`, **no hay comprobación de autoridad**, y que eso es inaceptable en un punto de aplicación | `verifyAuthorization.ts#L43-L61` | [CÓDIGO] (comentario normativo) |
| 6 | El proyecto declara **qué no prueba una firma**: ni verdad semántica, ni autoridad, ni actualidad, ni frescura del estado | `B/docs/audits/2.0-residual-scope.md#L99-L115`; `B/README.md#L238-L252` («Signature ≠ trust») | [README] |
| 7 | **TOCTOU externo no cubierto**: la autorización prueba qué premisas se evaluaron, no que sigan vigentes cuando ocurre el efecto | `2.0-residual-scope.md#L43-L53` | [README] |
| 8 | **Hueco de auditoría**: si `execute()` empieza y lanza, no queda registro de decisión en ningún flujo | `2.0-residual-scope.md#L55-L70`; `guard.ts#L126-L135` | [README] + [CÓDIGO] (comentario) |
| 9 | **No hay aprobación humana** (STEP_UP) en 2.0; está solo diseñada | `2.0-residual-scope.md#L72-L80` | [README] |
| 10 | Una herramienta ausente de `tool_limits` **se permite por defecto** (issue #214 abierta) | `2.0-residual-scope.md#L160` | [README] |
| 11 | **`ExecutionReceiptV1` (prueba de ejecución) está solo planificado** | `B/README.md#L389`; `2.0-residual-scope.md#L153-L158` | [README] |
| 12 | El `ReplayStore` por defecto es en memoria y para desarrollo: pierde el estado al reiniciar | `B/packages/guard/src/replayStore.ts` (cabecera, L26 y L69-L74) | [CÓDIGO] |
| 13 | `HashChainedLog` es **en memoria**; `drain()` vacía la cadena pero conserva la cabeza, así que `verify()` posterior no puede reconstruirla desde el génesis | `B/packages/core/src/audit/HashChainedLog.ts#L16-L79` | [CÓDIGO] + [INFER] (consecuencia no ejecutada) |
| 14 | Ellos mismos recomiendan **no** usar su artefacto separable salvo verificación independiente o premisas inalcanzables; en otro caso, un PDP/PEP en línea (OPA, Cedar) | `B/README.md#L139-L160` | [README] |
| 15 | La no elusión solo vale **para las llamadas que pasan por el guard**; una ruta alternativa al mismo efecto no queda protegida | `2.0-residual-scope.md#L117-L123` | [README] |
| 16 | Revisión externa prevista por OpenZeppelin | `2.0-residual-scope.md#L10` | [README] (no se encontró informe publicado; **no** es reproducción de terceros) |

## Límites, riesgos y dependencias

- **Frontera honesta, valores por defecto mixtos:** el PEP es cerrado (filas 2-3), pero la función de biblioteca es abierta por defecto (fila 4) y las herramientas no listadas se permiten (fila 10). Integrar mal la biblioteca da una «autorización» que no verificó nada [CÓDIGO + INFER].
- **Lo que AURA más necesita está pendiente en oxdeai:** aprobación humana (fila 9) y prueba de ejecución (fila 11).
- **Mantenimiento:** un solo autor principal; proyecto de ocho meses, aunque con un documento de alcance residual inusualmente explícito [CÓDIGO + README].
- **Plataforma:** Node 20+ y pnpm. No encaja en el walking skeleton de Python sin reimplementar [INFER].

## Comparación con AURA

| AURA | Relación | Clase |
|---|---|---|
| Motor único; ninguna ruta alternativa (ALERTA-005); solo capacidades registradas | **Mismo principio que la fila 15**: el PEP solo protege lo que pasa por él. AURA ya lo eleva a regla no negociable | [LECT] |
| `review.py`: veredicto determinista y `TareaSinContratoQueLaAutorice` (`entorno/control-plane/review.py:127`) | Equivale al PDP determinista con cierre por defecto. AURA no emite un artefacto separable; según la fila 14, **no le hace falta** mientras PDP y PEP vivan en HC-1 | [LECT] + [INFER] |
| Lista roja con confirmación humana **siempre** (ADR-0003) | oxdeai **no tiene** aprobación humana (fila 9). AURA va por delante | [LECT] |
| Delegación a nodos: firma de tareas por HC-1 (A1), `caduca_en`, `(tarea, intento, id_ejecucion)`, rechazo de replay (§10.2, §12.3) | Es exactamente el caso en que oxdeai **sí** justifica un artefacto separable: el ejecutor (nodo) está en otra zona de confianza. `AuthorizationV1` liga `audience` (= nodo), `intent_hash`, `state_hash`, `expiry` y `nonce` de un solo uso | [INFER] |
| Verificación independiente del resultado en HC-1 (M3) | oxdeai no la ofrece (fila 11). Sin cambios: M3 sigue siendo imprescindible | [LECT] |
| `verificar_integridad_log` persistente | Más sólido que el `HashChainedLog` en memoria (fila 13) | [LECT] |

## Hallazgos

**HAL-042-1 · El contenido mínimo de una orden firmada para un nodo.**
- Problema: A1 (firma de tareas por HC-1) está abierto y el DP no fija aún **qué** campos liga la firma.
- Mecanismo: `AuthorizationV1` liga a la vez destinatario (`audience`), hash canónico de la intención, hash del estado evaluado, política, emisión, caducidad, `nonce` (**opcional** en el tipo, `nonce?`; su carácter de un solo uso es [INFER], porque no se leyó `replayStore`) y algoritmo/`kid`, con separación de dominio en la firma.
- Evidencia primaria: `B/packages/core/src/types/authorization.ts#L3-L23`; `verifyAuthorization.ts#L380-L440`.
- Grado de verificación: [CÓDIGO] (lectura).
- Componente AURA: A1 de `DP-DELEGACION-NODOS.md` §11 y la fila «T · manipulación de la tarea» de §12.3.
- Alternativa existente en AURA: `{tarea, intento, id_nodo, id_ejecucion, capacidad, caduca_en}` (§10.2), sin `audience` explícito separado de `id_nodo`, sin hash de la política ni etiqueta de dominio.
- Beneficio / coste: cerrar una orden reenviada a otro nodo, a otra versión de la lista delegable o a otro protocolo; coste de unos pocos campos.
- Riesgos y condiciones de rechazo: rechazar si añade una dependencia de Node o del formato de oxdeai; se adopta **solo** la lista de campos y la separación de dominio.
- Criterio de aceptación (prueba futura): una tarea firmada para el nodo A, presentada al nodo B → rechazada; firmada con otra versión de la lista delegable → rechazada; firma válida con otra etiqueta de dominio → rechazada. Cada caso con su control positivo y su mutante.
- Autorización requerida: acta del CEO sobre A1 (ya pendiente en el DP).
- Clasificación: **PRIORIDAD ALTA**.

**HAL-042-2 · El verificador debe fallar cerrado cuando le falta configuración de confianza.**
- Problema: en oxdeai, la función de verificación sin claves de confianza devuelve `ok: true` sin haber verificado la firma.
- Mecanismo: el modo por defecto es permisivo; solo `strict` o `requireSignatureVerification` lo cierran.
- Evidencia primaria: `verifyAuthorization.ts#L403-L421`, `#L486-L493`.
- Grado de verificación: [CÓDIGO] (lectura; no ejecutado).
- Componente AURA: futuros verificadores en el nodo (tareas firmadas) y en HC-1 (resultados firmados).
- Alternativa existente en AURA: el DP pide fallo cerrado para la SPKI (A3), pero no lo enuncia para el verificador de firmas.
- Beneficio / coste: un único verificador sin modo permisivo evita el error de integración; coste nulo.
- Riesgos y condiciones de rechazo: ninguno.
- Criterio de aceptación: prueba que construya el verificador sin claves de confianza y compruebe que **rechaza** toda tarea; mutante que permita pasar sin claves → debe morir.
- Autorización requerida: ninguna para escribirlo en el DP; acta para implementar.
- Clasificación: **PRIORIDAD ALTA**.

**HAL-042-3 · La autorización no prueba la ejecución ni cierra el TOCTOU del recurso.**
- Problema: entre autorizar y ejecutar, el recurso puede cambiar; y una autorización válida no dice si el efecto ocurrió.
- Mecanismo: oxdeai solo protege su propio estado con CAS; la prueba de ejecución está planificada.
- Evidencia primaria: `2.0-residual-scope.md#L43-L53`, `#L153-L158`.
- Grado de verificación: [README].
- Componente AURA: estados `declarada_ejecutada` / `verificada` y verificador M3.
- Alternativa existente en AURA: «solo `verificada` concede `completada`» (§10.1).
- Beneficio / coste: confirma el diseño de AURA; ningún coste.
- Riesgos y condiciones de rechazo: no aplica.
- Criterio de aceptación: ya definido en §10.3 («resultado inverificable → fallo»).
- Autorización requerida: ninguna.
- Clasificación: **REFERENCIA**.

**HAL-042-4 · Registrar también el fallo después de empezar a ejecutar.**
- Problema: oxdeai deja sin registro una ejecución que empezó y lanzó una excepción.
- Mecanismo: sus dos flujos de auditoría cubren la denegación y el rechazo previo, no el fallo posterior.
- Evidencia primaria: `2.0-residual-scope.md#L55-L70`.
- Grado de verificación: [README] + [CÓDIGO] (comentario de `guard.ts#L126-L135`).
- Componente AURA: motor único y eventos del control-plane.
- Alternativa existente en AURA: [INFER] probablemente cubierto por los estados de tarea y la recuperación tras caídas (`DP-RECUPERACION-TRAS-CAIDAS`); **no verificado** en esta revisión.
- Beneficio / coste: no perder evidencia de un efecto parcial.
- Riesgos y condiciones de rechazo: ninguno.
- Criterio de aceptación: prueba en la que una capacidad lance tras empezar y se compruebe que queda un evento terminal en la cadena (y no un `completada`).
- Autorización requerida: ninguna para la prueba de caracterización.
- Clasificación: **PRIORIDAD MEDIA**.

**HAL-042-5 · oxdeai como dependencia.**
- Problema / mecanismo: TypeScript, bus factor 1, sin aprobación humana ni prueba de ejecución.
- Evidencia primaria: metadatos; filas 9 y 11.
- Grado de verificación: [CÓDIGO] + [README].
- Componente AURA: ninguno.
- Alternativa existente en AURA: `review.py` y el control-plane.
- Beneficio / coste: bajo; coste de pila nueva.
- Riesgos y condiciones de rechazo: viola «no crear componente si existe equivalente».
- Criterio de aceptación: no aplica.
- Autorización requerida: acta del CEO.
- Clasificación: **NO ADOPTAR**.

## Decisión

**Adaptar patrón, no adoptar código.** Es el proyecto más alineado con AURA de los cuatro revisados: autorización
determinista antes del efecto, fallo cerrado en el PEP y un documento de límites que no exagera. Aporta dos insumos
directos para A1 (HAL-042-1 y HAL-042-2) y confirma tres decisiones ya tomadas por AURA: motor único, lista roja humana
y verificación del resultado.

## Validación mínima

Cuando se autorice la delegación: los casos de HAL-042-1 (destinatario, versión de lista, dominio) y HAL-042-2
(verificador sin claves) en la batería aislada de §10.3 de `DP-DELEGACION-NODOS.md`, cada uno con caso de control y
mutante. Ahora mismo: la prueba de caracterización de HAL-042-4.

## Licencia y precauciones

- Apache-2.0. Si se reutilizara texto normativo, citar la fuente y conservar el aviso.
- No se instaló, descargó ni ejecutó nada. Las citas son de ≤ 3 líneas con su URL. Las copias para leer estuvieron en `/tmp` y se borraron.
- Las afirmaciones de rendimiento y de conformidad multilenguaje son [README]/[TESTS-DECLARADOS]; no se verificaron.
