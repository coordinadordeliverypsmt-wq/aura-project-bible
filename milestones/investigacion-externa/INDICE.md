---
documento: "Investigación técnica externa — índice"
creado: 2026-10-22
mantenido-por: "APUS-5 (CTO)"
regla: "Antes de investigar un repositorio externo, buscar aquí. Si ya hay ficha, actualizarla solo con evidencia nueva."
---

# Investigación técnica externa

Estas fichas guardan lo aprendido de proyectos de código abierto **sin instalarlos en AURA**. Persistir una ficha no
entrena a ningún modelo: la continuidad la dan estos ficheros, este índice y el CHECKPOINT.

Origen: orden del CEO del 2026-10-22, «Protocolo permanente de inteligencia técnica externa». Antes solo existía
`milestones/m3-entry/ESTUDIO-MUSE-GADGET-SDK.md` (registrado abajo como IE-000).

## Plantilla de ficha (`IE-NNN-<repo>.md`)

```
---
id: IE-NNN
titulo: ...
fuente: <URL>
rama-revision: <rama por defecto> @ <commit corto o fecha del último push examinado>
fecha-revision: AAAA-MM-DD
licencia: ...
area: hogar | camaras-moviles | asistentes | redes-seguridad | firmware
estado: investigado | validado | adoptado | descartado | pendiente
cobertura: <qué ficheros se leyeron y qué NO>
relacionadas: [IE-…]
---
## Qué se examinó (rutas y símbolos)
## Patrones relevantes          (marcar cada afirmación: [CÓDIGO] observado · [README] declarado · [INFER] · [PROPUESTA])
## Límites, riesgos y dependencias (hardware, nube, seguridad, mantenimiento)
## Comparación con AURA          (ruta:símbolo de AURA, estado actual, brecha real o «ya cubierto»)
## Decisión                      (adoptar patrón · adaptar · investigar más · descartar — y por qué)
## Validación mínima              (prueba o experimento que demostraría la mejora)
## Licencia y precauciones
```

**Uso ante un defecto difícil:** ver [`PROCEDIMIENTO-DEFECTO-DIFICIL.md`](PROCEDIMIENTO-DEFECTO-DIFICIL.md) (13 pasos; la base orienta y **no** autoriza cambios).

## Índice por área

| ID | Repositorio | Área | Estado | Decisión en una línea |
|---|---|---|---|---|
| IE-000 | facebookincubator/muse-gadget-sdk | asistentes | descartado | `system.run` + nube Meta; patrones ya cubiertos (`../m3-entry/ESTUDIO-MUSE-GADGET-SDK.md`) |
| IE-001 | hansb001/smarthome | hogar | investigado | Descartar: contraejemplo (MQTT sin auth/TLS, sin acuses); el patrón gateway ya lo cubren `bus_nats.py` y el Motor Único. Sin licencia: no copiar |
| IE-002 | smartHomeHub/SmartIR | hogar | adoptado (concepto) | **Estado asumido** (`assumed_state`): HA puede «ver» un estado que no ha leído del aparato → implementado en el veredicto de hogar (2026-10-22). Su actualización remota sin hash ni validación de rutas se descarta |
| IE-003 | Tjstock/swipe-navigation-card | hogar | investigado | Descartar: el patrón «la UI declara, otro ejecuta» ya existe (Motor Único) |
| IE-004 | Nerwyn/universal-remote-card | hogar | pendiente | Adaptar el patrón de datos: declarar qué controles admite cada dispositivo (`supported_features`). Necesita DP propio (cambia el contrato de `entorno`) |
| IE-005 | FunkeyFlo/ps5-mqtt | hogar | adoptado (concepto) | PS5 en reposo ≠ apagada; no se enciende desde apagada. Cambiar `ESTADOS_APAGADA` es **decisión del CEO**. PSN/nube excluida (D24). Hay `sh.exec` con interpolación: no copiar |
| IE-006 | cameraui/camera.ui | camaras-moviles | investigado | Descartar: NVR con grabación; AURA observa de forma efímera por decisión |
| IE-007 | danielealbano/android-remote-control-mcp | camaras-moviles | investigado | Sin código (GPL). Aporta **12 controles mínimos** para cualquier capacidad móvil futura (ver ficha). Ninguna herramienta suya pide confirmación humana |
| IE-008 | DimCyan/iOS-remote | camaras-moviles | descartado | Contraejemplo: sin autenticación, `shell=True` con texto del usuario, `debug=True`; abandonado (2021) |
| IE-009 | open-jarvis/OpenJarvis | asistentes | investigado | Adaptar solo el patrón de medición por etapa con `trace_id` común (mediana/p95; NODO-01 sin vatímetro → energía «no medida») |
| IE-010 | microsoft/JARVIS | asistentes | investigado | Descartar código (OpenAI/HF, D24). Lista de verificación de contrato para el Motor: dependencias con fallos, referencias adelantadas; reescribir el plan viola INV-7 |
| IE-011 | sukeesh/Jarvis | asistentes | descartado | Ejecución arbitraria por diseño; `capability_registry` ya es un superconjunto controlado |
| IE-012 | We5ter/Scanners-Box | redes-seguridad | investigado | Catálogo, no dependencia. Brechas: sin escaneo de secretos ni auditoría de dependencias (instalar exige decisión). `ruff --select S`: 17 avisos; los 4 S314 de `red_local.py` triados como **falso positivo** (DOCTYPE/ENTITY rechazados, cuerpo acotado, expat 2.6.1 medido) |
| IE-013 | arismelachroinos/lscript | redes-seguridad | descartado | Archivado y ofensivo: no se adopta nada; el patrón instalar/retirar simétrico ya existe en `entorno/nodos/` |
| IE-014 | miyurudassanayake/sni-injector | redes-seguridad | descartado | Solo lista de controles. AURA: `nodo_agente.py:397` `check_hostname=False` compensado con CA privada + `CERT_REQUIRED` + `VERIFY_X509_STRICT`; falta una prueba de que rechaza una CA ajena |
| IE-015 | Open-Smartwatch/open-smartwatch-os | firmware | investigado | Solo ideas (GPL): versión de esquema en la config del nodo y diagnóstico de solo lectura, cuando haya un bloqueo observado |

### Misión «DVR Amtech + evolución de agentes + cámaras» (2026-10-22) — IE-016 … IE-031

Síntesis, matriz y diseño: `SINTESIS-2026-10-22-DVR-AGENTES-CAMARAS.md`.

**DVR / protocolos / firmware**

| ID | Repositorio | Área | Estado | Decisión en una línea |
|---|---|---|---|---|
| IE-016 | OpenIPC/python-dvr | dvr | investigado | **ADOPTAR PATRÓN / PROBAR EN AISLAMIENTO (P0)**: único canal que el DVR `.80` expone (DVRIP/34567). Lista de métodos de LECTURA y de ESCRITURA prohibidos; 205 = veto de IP. MIT |
| IE-017 | BigNerd95/Avtech-Firmware-Tools | firmware | descartado | Formato Avtech; no aplica a la plataforma Xiongmai observada. GPL-3.0 |
| IE-018 | zzHAMZAzz/Custom-Firmware-For-Chinese-CCTV-DVR | firmware | investigado | SOLO REFERENCIA: qué leer en la pantalla de información (versión). Sin licencia; nada de firmware |
| IE-019 | rosteleset/Simple-DVR | camaras-moviles | investigado | DESCARTAR: es un **servidor** de grabación HLS (sin auth), no un cliente; contradice lo efímero. GPL-3.0 |
| IE-020 | Breakthrough/DVR-Scan | camaras-moviles | investigado | SOLO REFERENCIA: MOG2 sobre archivos, eventos con inicio/fin; sin uso real que lo pida. BSD-2-Clause |

**Agentes / autoevaluación / evolución**

| ID | Repositorio | Área | Estado | Decisión en una línea |
|---|---|---|---|---|
| IE-021 | kayba-ai/recursive-improve | asistentes | investigado | ADOPTAR PATRÓN: detectores deterministas sobre trazas + línea base + `plateau_patience`. Apache-2.0 |
| IE-022 | KorroAi/mue-x | asistentes | descartado | Controles declarados que el código no cumple; solo la huella de error recurrente. MIT |
| IE-023 | EXOAI-1/genesis-phase | asistentes | investigado | SOLO REFERENCIA: instantánea de rescate antes de una operación destructiva. Nube + auto-push |
| IE-024 | RobertoN0/stem_agent | asistentes | investigado | ADOPTAR PATRÓN: aceptar solo si mejora un **conjunto retenido** frente al padre (su gen 2 mejora validación y empeora el retenido). MIT |
| IE-025 | Lycorecoil/ouroboros | asistentes | descartado | Shell sin límite, salto de permisos del CLI, auto-push. Contraejemplo |
| IE-026 | viko-nexus/viko-assistant | asistentes | investigado | DESCARTAR: parche no encontrado se reporta como aplicado; licencia no comercial |
| IE-027 | NullLabTests/Aurogene | asistentes | investigado | DESCARTAR: salto de permisos del CLI, commit+push automáticos, nube |
| IE-028 | china-nyx/poiesis | asistentes | investigado | **PATRÓN P1**: candidato en worktree desechable, verificado en otro proceso, promoción ff-only, rollback. Sin licencia: solo la idea |
| IE-029 | Cole-Will-I-Am/Heka | asistentes | descartado | `review_passed=True` sin consultar el veredicto; sin tests ni licencia |

**Cámara / visión / comunicación**

| ID | Repositorio | Área | Estado | Decisión en una línea |
|---|---|---|---|---|
| IE-030 | SharpAI/DeepCamera | camaras-moviles | investigado | ADAPTAR solo el contrato de evento (procedencia, `retriable`, p95). Facial/ReID/nube descartados (Decisión B, D24). MIT |
| IE-031 | crazyrob425/aistalker | camaras-moviles | descartado | Reconocimiento facial + seguimiento de personas: contraejemplo exacto de la Decisión B. GPL-3.0 |
| IE-032 | Louis-CFM/coucou | herramientas-de-desarrollo | prototipo-aislado-futuro | Supervisión de sesiones de Claude Code: hooks globales que reenvían toda la sesión y aprobación de un clic sin lista roja. No en el equipo real; prototipo aislado solo con acta y 9 controles; patrones reutilizables. MIT (marca reservada) |
| IE-033 | yujinrobot/korus | robotica | descartado | ROS1 Hydro/Indigo, Python 2, abandonado desde 2015, sin licencia y con dependencias privadas; no gestiona nodos de cómputo; no hay robótica en el cronograma |
| IE-034 | hexo-ai/sia | asistentes (auto-mejora) | descartado como código | Sin compuerta entre generaciones y `bypassPermissions` en el host. Lección: la métrica de aceptación no puede estar al alcance de quien propone (HAL-034-1, contrastado en AURA: brecha de defensa en profundidad, MEDIA). MIT |
| IE-035 | A-EVO-Lab/a-evolve | asistentes (auto-mejora) | descartado | Compuerta que acepta sin datos retenidos; issue de seguridad #28 abierta; sin fichero LICENSE. Referencia: rollback como commit nuevo |
| IE-036 | ANative-Lab/EvoAgentX | asistentes (auto-mejora) | descartado | `bash -c` con lista negra por regex; el HITL inactivo se autoaprueba; issues de seguridad abiertas. MIT |
| IE-037 | selfimproving-agent/Awesome-Self-Improving-Agents | asistentes (bibliografía) | referencia | Lista curada con 15 entradas pertinentes **sin verificar**; contiene enlaces erróneos y no es fuente primaria. Leer CTIM-Rover antes de cualquier DP de memoria de experiencias (HAL-037-1). MIT |
| IE-038 | Tencent-Hunyuan/Hy-Memory | asistentes (memoria) | no adoptar el motor | Usa nube por defecto (claves DeepSeek y DashScope) y deja que el LLM decida las contradicciones (contra ADR-0014). Referencia: esquema hecho↔experiencia con procedencia (HAL-038-1, MEDIA). Apache-2.0 |
| IE-039 | dp-web4/SAGE | asistentes (memoria) | adaptar solo la idea | Consolidación determinista con procedencia (fuentes con sha256 y versiones `vN` con `supersedes`, sin borrar), HAL-039-1, ALTA. **AGPL-3.0 y PATENTS no comercial: no copiar código** |
| IE-040 | microsoft/agent-governance-toolkit | redes-seguridad | referencia | `allow` por defecto sin políticas; mTLS acepta un certificado autofirmado sin registro. Encontró una **brecha confirmada en AURA**: borrar la cola del log no se detecta (HAL-040-2, `[EJEC-AURA]`, deuda, requiere DP). MIT |
| IE-041 | agent-passport-system/agent-passport-system | redes-seguridad | adaptar ideas | Catálogo de rechazos «firma válida, afirmación inválida» (HAL-041-1) y vínculo tarea↔resultado obligatorio (HAL-041-2), para la delegación. Gateway fuera del repositorio. Apache-2.0 |
| IE-042 | oxdeai/oxdeai | redes-seguridad | adaptar el patrón | Guard que falla cerrado; campos mínimos de la orden firmada (HAL-042-1); verificador sin modo permisivo (HAL-042-2). Ojo: su `verifyAuthorization` es permisivo por defecto. Apache-2.0 |
| IE-043 | aws-samples/sample-agentstorming (threat-model.md) | redes-seguridad | adoptar el método | Método de modelo de amenazas y verificación de órdenes firmadas sobre los bytes exactos, con frescura y monotonía (HAL-043-1); SO_PEERCRED para el firmador (HAL-043-3). Ejemplo sin pentest. MIT-0 |
| IE-044 | airemoteagent/AI-Remote-Agent | redes-seguridad | descartado como código | Razona en la nube (remoteagent.online), un Bearer único sin firma ni anti-replay, y el LLM verifica sus resultados. Identidad, JIT y recibos declarados pero no cableados. Único hueco parcial: techo de tasa en el Motor (INVESTIGAR MÁS; el 30/min no es transferible). MIT |
| IE-045 | agent-wall/agent-wall | redes-seguridad | descartado como código | Proxy MCP (AURA no tiene MCP; sería segunda vía, ALERTA-005); dashboard sin autenticación; HMAC desactivado. Hueco NUEVO: redacción de secretos y PII (INVESTIGAR MÁS; se descarta si el grep de registros reales sale vacío). MIT |
| IE-046 | openclaw/openclaw | redes-seguridad | referencia | Un solo operador de confianza, inyección no considerada vulnerabilidad, más de 190 extensiones de nube. Hueco NUEVO: alta asistida de nodos (INVESTIGAR MÁS; no amortiza con un solo NODO-01) y sandbox parcial. Solo se leyeron módulos citados. MIT |

Síntesis de IE-044 … IE-046 (2026-11-09): `SINTESIS-2026-11-09-AGENTES-REMOTOS-FIREWALL-OPENCLAW.md`. No amplía M3 ni crea capacidades (D23).

## Candidatas pendientes (ordenadas; ninguna se construye sin DP o decisión)

1. `supported_features` antes de llamar (IE-004): necesita DP (cambia el contrato de `entorno`/`estado_actual`).
2. PS5 en reposo ≠ apagada (IE-005): decisión del CEO sobre `ESTADOS_APAGADA`.
3. Medición por etapa con `trace_id` (IE-009): necesita DP de medición.
4. Prueba de que el agente del nodo rechaza un certificado de otra CA (IE-014): prueba nueva, pequeña.
5. Triage de los 13 avisos `ruff S` restantes (IE-012).
