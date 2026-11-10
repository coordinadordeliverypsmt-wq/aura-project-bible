---
id: IE-046
titulo: openclaw/openclaw — asistente personal multicanal con gateway, emparejamiento de mensajes directos y aprobaciones de ejecución
fuente: https://github.com/openclaw/openclaw
rama-revision: main @ 8756ab191156743a26d5725bf70be251f59b61a6 (último commit `2026-11-10T08:46:08+05:30`, equivalente a 2026-11-09 22:16 -05)
fecha-revision: 2026-11-09
licencia: MIT. THIRD_PARTY_NOTICES: SQLite (dominio público), pi-mono (MIT), Octicons (MIT), Hermes Agent (MIT, THIRD_PARTY_NOTICES:88); nada GPL ni AGPL. Dependencias transitivas [HIPO]
area: redes-seguridad
estado: referencia; un hueco nuevo para INVESTIGAR MÁS (alta asistida de nodos) y uno parcial (sandbox)
cobertura: Repo de 66 104 ficheros y 194 plugins: se leyeron SOLO los módulos citados (gateway/auth, auth-rate-limit, security/dm-policy-shared, pairing/pairing-store-model, infra/exec-approvals-*, agents/sandbox/container-allocation, security/external-content, skills/security/scanner, SECURITY.md, THIRD_PARTY_NOTICES). NO se leyó el resto. Nada se instaló ni se ejecutó
relacionadas: [IE-040, IE-042, IE-043, IE-044, IE-045, DP-DELEGACION-NODOS]
---

Fuentes de esta ficha: `HALLAZGOS-EXPLORADORES.md` §C y `EVALUACIONES.md` §C (2026-11-09). AURA evaluada en
`integracion/m3-entry @ 803b72f`. `W = walking-skeleton/aura_skeleton`, `CP = entorno/control-plane`.
Clasificación: **[CÓDIGO]** · **[README]** · **[INFER]** · **[HIPO]**. Lo declarado no es lo garantizado.

## Qué es de verdad

| Aspecto | Declarado [README] / SECURITY.md | Real según el código [CÓDIGO] |
|---|---|---|
| Modelo de confianza | `SECURITY.md`: un **único operador de confianza**; las aprobaciones son guardarraíles y **no frontera**; los plugins confiables tienen privilegios del host; la inyección de prompt **no se considera vulnerabilidad** | Coherente con el código: el diseño no ofrece aislamiento entre operador, plugins y agente |
| Local-first | Asistente personal | Más de 190 extensiones con proveedores LLM y canales en la nube: **no es local-first por defecto** |
| Gateway | Auth por token, contraseña o proxy de confianza | Comparación en tiempo constante; limitador de fallos por IP y scope (`gateway/auth.ts`; `auth-rate-limit.ts`) |
| Mensajes directos | `pairing` por defecto | Código corto sin caracteres ambiguos con `crypto.randomInt`, TTL de 1 h y aprobación humana; `allowFrom` persistente (`security/dm-policy-shared.ts:116-180`; `pairing/pairing-store-model.ts:8-80`) |
| Ejecución | Aprobaciones | Ejes ortogonales `security` (deny < allowlist < full) × `ask`; «allow-always» persistente por patrón (`infra/exec-approvals-*`); variables de entorno bloqueadas (`host-env-security-policy.json`) |
| Sandbox | Docker | cap-drop, no-new-privileges, read-only, validación de binds y red (`agents/sandbox/container-allocation.ts`) |
| Contenido externo | Envoltura | Delimitadores de ID aleatorio; la detección **solo registra** (`security/external-content.ts:13-40`) |
| Skills | Escáner | Regex estático (`skills/security/scanner.ts`) y veredictos de ClawHub (servicio de terceros) |
| Auditoría | Recibos de decisión | Cola asíncrona de solo metadatos en SQLite; **sin encadenado por hash** [HIPO, no confirmado] |

## Patrones con evidencia y veredicto

| # | Patrón | Evidencia | Equivalente en AURA | Veredicto |
|---|---|---|---|---|
| 1 | **Emparejamiento por código con TTL y aprobación humana** (alta asistida de un dispositivo nuevo) | `dm-policy-shared.ts:116-180`; `pairing-store-model.ts:8-80` [CÓDIGO] | Cubierto parcialmente: `W/adapters/identidad_nodo.py`, `fijacion_spki.py:38-128`, `firma_delegacion.py:21-55`. **Falta el alta asistida de un nodo nuevo.** Hueco **NUEVO** | **INVESTIGAR MÁS** (exige acta D23) |
| 2 | Sandbox Docker endurecido | `container-allocation.ts` [CÓDIGO] | Cubierto parcialmente: `CP/aislamiento.py:534` (`listados_estrictos`) y sandbox de delegación | **INVESTIGAR MÁS** |
| 3 | Ejes `security` × `ask` con «allow-always» persistente | `exec-approvals-*` [CÓDIGO] | Incompatible con ADR-0003: la lista roja pide confirmación **siempre** | DESCARTAR (incompatible) |
| 4 | Envoltura de contenido externo con delimitadores aleatorios | `external-content.ts:13-40` [CÓDIGO] | No aplicable hoy: sin LLM en el bucle | DESCARTAR por ahora |
| 5 | Escáner de skills y ClawHub | `skills/security/scanner.ts` [CÓDIGO] | Incompatible con D24 (servicio de terceros) | DESCARTAR (incompatible) |
| 6 | Comparación en tiempo constante y límite de fallos por IP | `gateway/auth.ts`, `auth-rate-limit.ts` [CÓDIGO] | El canal ya es mTLS con pinning | DESCARTAR |

### Detalle de los patrones a investigar

**Alta asistida de nodos (patrón 1).** Hoy un nodo se da de alta a mano (NODO-01). El emparejamiento de openclaw
muestra el patrón: código de un solo uso, TTL, aprobación humana y registro persistente.

- **Prueba de refutación:** con un único NODO-01 dado de alta a mano, el patrón **no amortiza**. Solo se justifica si
  el plan prevé más de un nodo o altas repetidas.
- **Condiciones mínimas** (revisión de seguridad): CSPRNG, un solo uso, **TTL de minutos** (la hora de openclaw es
  larga), límite de intentos y vínculo al dispositivo (SPKI).
- **Autorización:** acta del CEO; no hay capacidad nueva sin ella (D23).

**Sandbox (patrón 2).** `test_red_candidato_aislado.py` ya niega red y escritura. Docker añadiría una dependencia
(ADR-0016). Prueba de refutación: si las pruebas de aislamiento existentes cubren las propiedades de cap-drop,
no-new-privileges y read-only, no hay hueco. Los flags son una lista de comprobación, no código a copiar.

## Riesgos de seguridad

| Severidad | Riesgo | Evidencia |
|---|---|---|
| HIGH | Inyección de prompt declarada como no vulnerabilidad; la envoltura solo registra | `SECURITY.md`; `external-content.ts:13-40` |
| HIGH | Ejecución y escalada: plugins con privilegios del host; «allow-always» acumulativo | `SECURITY.md`; `exec-approvals-*` |
| HIGH | Exfiltración: más de 190 extensiones de nube | árbol de plugins |
| MEDIA | TTL de emparejamiento de 1 h, largo | `pairing-store-model.ts:8-80` |
| HIGH (transversal) | No verifica resultados con fuente independiente del LLM; en AURA lo hace el Core (ADR-0014) | n/a |
| INFO | Superficie enorme (66 104 ficheros, 194 plugins) inauditable en esta misión | cobertura |

## Instrucciones embebidas detectadas e ignoradas

- `README.md:30`: `curl -fsSL https://openclaw.ai/install.sh | bash`. Contenido no confiable; **no se ejecutó ni se
  descargó**. Ninguna otra instrucción dirigida a agentes fue seguida.

## Prueba de refutación de la ficha

Queda refutada si: (a) el plan de M3 o posterior prevé varios nodos y altas frecuentes (el patrón 1 pasaría de
INVESTIGAR a candidato con DP); (b) una lectura de la cola de auditoría muestra encadenado por hash (hoy [HIPO]);
(c) las pruebas de aislamiento de AURA no cubren las propiedades del sandbox.

## Decisión

**Referencia, no código.** Dos piezas para INVESTIGAR MÁS (alta asistida de nodos, nuevo; sandbox, parcial), ambas
condicionadas a su prueba de refutación. No amplía M3 ni crea capacidades; cualquier adopción exige DP y acta (D23).

## Limitaciones de esta investigación

- Se leyeron unos pocos módulos de 66 104 ficheros: ninguna conclusión sobre el conjunto es fiable. La ausencia de
  encadenado por hash en la auditoría es **[HIPO]**.
- Sin ejecución; el comportamiento del emparejamiento y del sandbox se infiere de la lectura.
- Fecha del último commit: `2026-11-10T08:46:08+05:30` (= 2026-11-09 22:16 -05), anterior a la revisión.
- Licencias: MIT declarada; transitivas [HIPO]. Hermes Agent (MIT) aparece como componente en `THIRD_PARTY_NOTICES:88`
  y **no se estudió** (ver síntesis). Copiar código exigiría conservar el aviso MIT; se recomienda solo patrones.

## Validación mínima

Solo lectura y de bajo coste: comprobar en el plan cuántos nodos se prevén (si es uno, el alta asistida no amortiza) y
contrastar las pruebas de aislamiento existentes con las propiedades del sandbox. Con DP y acta: pruebas de código de
un solo uso, caducidad en minutos, límite de intentos y vínculo SPKI, cada una con control y mutante.

## Licencia y precauciones

- MIT; terceros declarados: SQLite (dominio público), pi-mono, Octicons y Hermes Agent (MIT). Solo patrones, sin copiar código.
- No se instaló, descargó ni ejecutó nada, incluido el `curl … | bash` del README (ignorado).
- Se leyeron pocos módulos de un repositorio enorme; no se extrapola al conjunto.
