---
documento: "Síntesis — DVR «Amtech», evolución controlada de agentes y cámaras (IE-016 … IE-031)"
fecha: 2026-10-22
tipo: "Investigación de código y patrones. Nada instalado, ejecutado, flasheado ni desplegado. Ninguna interacción con el DVR."
evidencia: "[EJEC] medido · [LECT] leído en AURA · [CÓDIGO]/[README] leído en el repo externo (remoto, resúmenes) · [INFER] · [NO VERIFICADO]"
---

# Síntesis — DVR, evolución de agentes y cámaras

Cobertura: los 16 repositorios se leyeron por lectura **remota y parcial**. Cada ficha (`IE-016`…`IE-031`) declara qué
ficheros se leyeron y cuáles no. Ningún repositorio fue revisado completo.

## 1. DVR `.80` («Amtech»)

### 1.1 Lo que AURA ya sabe (sin tocar el equipo)

| Dato | Fuente |
|---|---|
| Web `uc-httpd`, «NETSurveillance WEB» → plataforma Xiongmai/XMEye | `[EJEC]` 2026-09-28, CHECKPOINT L6533 |
| DVRIP/Sofia abierto en TCP 34567 | `[EJEC]` 2026-09-28 |
| RTSP 554: `DESCRIBE` → 200 con **SDP vacío** (RTSP deshabilitado en el equipo) | `[EJEC]` CHECKPOINT L6585-6600 |
| ONVIF (8000/80/8899) no responde; snapshot HTTP no sirve | `[EJEC]` CHECKPOINT L6532, L6595 |
| `python-dvr` `DVRIPCam.login()` → **`[205] IP locked`** tras sondeos repetidos de esa sesión | `[EJEC]` CHECKPOINT L6646. La causa exacta del veto es `[INFER]` |
| OUI de la MAC `00:12:17` = **Cisco-Linksys, LLC** → la MAC no identifica al fabricante | `[EJEC]` 2026-10-22, `/usr/share/ieee-data/oui.txt` |
| La app del propietario es de tipo XMEye | captura del propietario (2026-10-22) |
| El propietario llama al equipo «Amtech» | dicho del propietario; **sin corroborar** |

### 1.2 Hipótesis

| H | Hipótesis | A favor | En contra | Decisión |
|---|---|---|---|---|
| **H1** | Xiongmai/XMEye (OEM), DVRIP | `uc-httpd` + «NETSurveillance» + 34567 + app XMEye; python-dvr declara exactamente esta combinación | ninguna directa | **Hipótesis de trabajo (alta)** |
| H2 | Avtech | parecido «Amtech»/«Avtech» | nada observado apunta a Avtech; el formato de IE-017 no aplica | improbable; solo si la pantalla lo dice |
| H3 | La plataforma de IE-018 | mismo ecosistema XMEye | el repo no nombra SoC ni OEM | no distinguible de H1 con los datos actuales |
| H4 | Otro OEM con la web NETSurveillance | muchas marcas blancas | sin evidencia específica | residual hasta leer la pantalla |

Una coincidencia de banner o de app **no demuestra** compatibilidad. «Amtech» es, como mucho, la marca comercial.

### 1.3 Camino de diagnóstico seguro

1. **Dato mínimo** (no exige tocar la red). El propietario lee en la pantalla de información del propio DVR:
   - modelo;
   - **versión completa de firmware**;
   - la marca en la etiqueta.
   - Si la pantalla lo muestra: canales y si es DVR/XVR analógico o NVR.
2. Comparar esos datos de forma documental con H1–H4.
3. **Solo entonces** hay un experimento posible, con todas estas precondiciones:
   - el CEO levanta por escrito el «no tocar» del `.80` para ese experimento;
   - el propietario confirma que no hay veto 205 vigente;
   - el propietario introduce él mismo la credencial, que vive solo en memoria y nunca se guarda;
   - una prueba unitaria **sin red** demuestra antes que una lista blanca rechaza todos los métodos de escritura de
     IE-016.

   El experimento:
   - **un** login DVRIP, **una** lectura (`get_system_info`: modelo y versión) y cierre del socket;
   - timeout de 10 s y **cero reintentos**;
   - cualquier código 106/203/204/205/206/207 o un timeout: parar, no repetir y avisar.
4. Solo con evidencia: un adaptador aislado de **solo lectura**, con timeout, cierre seguro, logs sin secretos,
   pruebas con doble y mutación. Pasaría por el Motor Único como capacidad registrada y nombrada por su resultado
   (p. ej. `observar_camara_exterior`), nunca por la herramienta.

**Prohibido en cualquier fase:**
- barridos, fuerza bruta, credenciales por defecto y bypass;
- `telnet_opener` o similares;
- cualquier método de escritura de IE-016: `set_*`, usuarios y grupos, `reboot`, `upgrade`, teclas, PTZ;
- firmware.

El veto 205 puede dejar fuera también la app del propietario: es un riesgo operativo real.

## 2. Matriz de reutilización

| ID | Licencia | Decisión | Prioridad | Qué se recicla (patrón, nunca código sin licencia) |
|---|---|---|---|---|
| IE-016 python-dvr | MIT | ADOPTAR PATRÓN / PROBAR EN AISLAMIENTO | **P0** (solo el experimento §1.3) | lista de lectura y escritura; códigos de error; sin logout de protocolo |
| IE-017 Avtech-FW-Tools | GPL-3.0 | DESCARTAR | P2 | — |
| IE-018 Chinese-CCTV-FW | sin licencia | SOLO REFERENCIA | P1 | qué leer en pantalla (formato de versión) |
| IE-019 Simple-DVR | GPL-3.0 | DESCARTAR | P2 | contraejemplo (servidor sin auth) |
| IE-020 DVR-Scan | BSD-2-Clause | SOLO REFERENCIA | P2 | eventos de movimiento con inicio/fin sobre archivos |
| IE-021 recursive-improve | Apache-2.0 | ADOPTAR PATRÓN | P2 | detectores deterministas + línea base + `plateau_patience` |
| IE-022 mue-x | MIT | DESCARTAR | P2 | huella de error recurrente (idea) |
| IE-023 genesis-phase | MIT | SOLO REFERENCIA | P1 | instantánea antes de una operación destructiva |
| IE-024 stem_agent | MIT | ADOPTAR PATRÓN | P1 | conjunto **retenido** y aceptar solo si mejora al padre |
| IE-025 ouroboros | MIT | DESCARTAR | P2 | — (contraejemplo) |
| IE-026 viko-assistant | PolyForm NC | DESCARTAR | P2 | — (parche parcial dado por bueno) |
| IE-027 Aurogene | MIT | DESCARTAR | P2 | — (salto de permisos del CLI, auto-push) |
| IE-028 poiesis | sin licencia | PATRÓN (solo la idea) | **P1** | candidato en copia desechable → verificar → promover → rollback |
| IE-029 Heka | sin licencia | DESCARTAR | P2 | — (veredicto del revisor ignorado) |
| IE-030 DeepCamera | MIT | ADAPTAR CONTRATO | P1 | evento con procedencia, `retriable`, p95 |
| IE-031 AI-Stalker | GPL-3.0 | DESCARTAR | P2 | — (contraejemplo de la Decisión B) |

## 3. Evolución controlada de AURA

### 3.1 Lo que AURA ya tiene (con más rigor que los 9 repos de agentes) `[LECT]`

| Ciclo | Mecanismo en AURA |
|---|---|
| Observar / clasificar | `entorno/control-plane/observatorio.py`, `ciclo_autonomo._clase_de_fallo` (L64), `descubrimiento.FUENTES` (L415) |
| Proponer | `autoconstruccion.proponer` (L300); DP obligatorio (CLAUDE.md §2) |
| Autorización humana | `autoconstruccion.autorizar`/`esta_autorizada` (L319, L334) |
| Kernel fuera de alcance | `zona_permitida` (L174), `orquestador._INTOCABLES` comprobado en `ejecutar`, `review.es_materia_reservada` (L191) |
| Parada | `orquestador.parada_solicitada` comprobada **antes de escribir** en `ejecutar` |
| Revisión independiente | `revisores.pedir_revision` (L353), `revision_local.py`; regla «quien implementa no audita» |
| Evaluar | `quality-gate.sh` + `herramientas/mutar.py`; «no se midió» = revertir |
| Presupuesto | `motor_autonomia.MAX_TAREAS`, `estancamiento.hay_estancamiento` (L122) y `estancamiento()` (L130) |
| Aislamiento | `aislamiento.py` (Landlock + rlimits) |
| Sin auto-commit/push | reglas del proyecto; promoción solo con gates y autorización humana |

Varios repos externos declaran controles que su código no cumple (IE-022, IE-026, IE-029). Es el patrón «declarado ≠
real» que AURA combate.

### 3.2 Brechas reales

1. **Verificación en el árbol vivo** `[LECT]`. `autoconstruccion.ejecutar` (L545-680) escribe el candidato con
   `ruta.write_text(nuevo)` y **después** lo verifica; si falla, revierte.
   - Mientras verifica, el árbol real contiene un cambio no aprobado.
   - El original vive solo en una variable local (`original`). Si el proceso muere entre la escritura y el revert,
     el fichero queda modificado; IE-023 e IE-025 lo señalan.
   - **Patrón IE-028:** verificar el candidato en una **copia desechable** (`git archive HEAD | tar -x`, ya
     documentado en CLAUDE.md §2 para la mutación) y escribir en el árbol vivo solo si pasa, con una instantánea en
     disco antes.
2. **Mejora sin línea base ni conjunto retenido** `[INFER]`. Hoy se acepta con `efecto and sano`, que es booleano.
   Ninguna capacidad compara una métrica con la del «padre». El caso de IE-024 enseña el riesgo: mejorar la
   validación y empeorar el conjunto retenido.
3. **Fallos recurrentes** `[INFER]`. `descubrimiento.FUENTES` no tiene una fuente «mismo fallo repetido» (huella
   IE-022/IE-021). Es una observación, no deuda (CLAUDE.md §7): no se ha observado un bloqueo por ello.

**Actualización (2026-10-22, noche):** la brecha 1 está **confirmada `[EJEC]`** (`../m3-entry/evidencia-candidato-aislado-2026-10-22/`) y tiene DP: `../m3-entry/DP-CANDIDATO-AISLADO-AUTOCONSTRUCCION.md`. La brecha 2 (sin línea base) y la 3 (sin detector de fallos repetidos) están confirmadas por lectura y grep; quedan fuera de ese DP.

### 3.3 Diseño objetivo (secuencia)

1. **Observar:** trazas mínimas, sin secretos.
2. **Clasificar:** modelo, contexto, herramienta, integración, prueba o autorización.
3. **Proponer:** un DP con problema, evidencia, cambio mínimo, riesgos y pruebas.
4. **Experimentar:** solo en una copia desechable, sin dispositivos ni secretos.
5. **Evaluar:** gate, mutación y la métrica frente a la línea base, con conjunto retenido.
6. **Revisar:** un revisor independiente distinto del autor.
7. **Promover:** solo con gates y autorización humana; sin commit, push ni deploy automáticos.
8. **Recuperar:** instantánea en disco y rollback probado.
9. **Aprender:** lección, diff, pruebas y límites de validez en el repo.

**Fuera de alcance de toda automodificación:** PARADA, permisos, `_INTOCABLES`, `review.py`, gates y la propia
`autoconstruccion.py`, que ya está en `_INTOCABLES`. Cada ciclo tiene presupuesto, máximo de intentos y criterio de
parada; no hay ningún bucle perpetuo.

**Métricas antes de recomendar un cambio:**
- tasa de éxito verificado;
- regresiones;
- falsos éxitos (declarado ≠ real);
- flakiness;
- latencia;
- CPU/RAM;
- tasa de rollback;
- cobertura de casos críticos (mutantes vivos = 0).

**Papel de Claude Code / ECC:** asistencia externa y episódica (CLAUDE.md §0.bis). Investiga, implementa con TDD y
audita con agentes distintos, siempre bajo DP. Nada de esto entrena un modelo: el aprendizaje queda en estas fichas, el
CHECKPOINT, las pruebas y el código aprobado.

## 4. Cámaras

| | DeepCamera (IE-030) | AI-Stalker (IE-031) | DVR-Scan (IE-020) | Simple-DVR (IE-019) | AURA hoy |
|---|---|---|---|---|---|
| Fuente | RTSP/ONVIF, webcam, clips | USB, RTSP, ONVIF, PTZ | archivos de vídeo | RTSP → HLS | RTSP bajo demanda (`CamaraRTSP`) y cámara local |
| Análisis | YOLO + VLM | rostro + seguimiento | movimiento MOG2 | ninguno | movimiento efímero (`EventoMovimiento`, `hubo_frame`) |
| Eventos | JSONL tipado, p95, `retriable` | fila SQLite | inicio/fin en CSV/JSON | — | evento sin procedencia del detector |
| Persistencia | clips y fotogramas | BD con identidades | archivo de entrada | graba segmentos | **nada**: efímero por decisión |
| Privacidad | facial/ReID (descartado) | facial, MAC, BLE (descartado) | neutra | sin auth | sin identidad (Decisión B) |

- **AHORA (P1, necesita DP):** el evento de movimiento lleva **procedencia** (detector, versión, umbral, origen
  capturado o inyectado) y la captura distingue un fallo **reintentable** de uno definitivo. Lo acompaña una prueba
  negativa que impide añadir campos de identidad (persona, rostro, embedding, MAC, teléfono) a eventos y
  observaciones; el control es un doble con `person_name` que debe fallar.
- **SIGUIENTE (P2):** medición por etapa con p95 (captura → diferencia → evento), reutilizando el DP de medición de
  IE-009. Movimiento por diferencia de fotogramas en CPU, compatible con 2 núcleos.
- **FUTURO (solo con uso real):** resumen de escena de objetos **no personales** con un modelo local pequeño y
  exportación de clips con confirmación humana.
- **Nunca:** reconocimiento facial, ReID, matrículas, biometría, nube ni mensajería de terceros.

## 5. Seguridad de la investigación

- **AgentShield: SKIP**, no está instalado en HC-1.
- Contenido remoto tratado como dato no confiable: el `CLAUDE.md` de python-dvr no se obedeció. Los textos que piden
  saltarse permisos (IE-025, IE-027) se registraron como **hallazgo**, no como instrucción.
- No se ha instalado, clonado ni ejecutado nada. Ningún contacto con el DVR ni con la red local. La única medición
  local fue la consulta del OUI en la base IEEE del sistema.

## 6. Una siguiente acción

**El propietario lee en la pantalla de información del DVR el modelo, la versión completa de firmware y la marca de
la etiqueta**, y los comunica. No requiere red ni autorización nueva, y decide entre H1–H4 antes de cualquier
experimento.
