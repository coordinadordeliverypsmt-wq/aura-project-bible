---
documento: "Decision Package CONSOLIDADO — Percepción multimodal local-first de cámara (VER · ESCUCHAR · EVENTO)"
tipo: "DECISION PACKAGE — APROBADO por el CEO (2026-09-28) e IMPLEMENTADO (Alt 4: VER+ESCUCHAR+EVENTO)."
fecha: 2026-09-28
estado: "APROBADO + IMPLEMENTADO. Ver §APÉNDICE DE IMPLEMENTACIÓN al final."
autor: "APUS-5 (CTO), por encargo del CEO (prompt maestro de ejecución vertical)"
fuente: "evidencia [EJEC] de las misiones multimodal 2026-09-28 + INFORME-CAPACIDADES-MULTIMODAL-ECOSISTEMA.md + código real HEAD 6dad6af. NO memoria."
gobernanza: "Bible · ADR-0014/0003/0001 · D24 · INV-9 · ALERTA-002 · acta-percepcion-visual-e-identidad (2026-09-27)"
---

# DP CONSOLIDADO — Percepción multimodal local-first de cámara

> **Rectificación del CEO (2026-10-22):** la zona de una cámara es METADATO y no deniega el acceso; todas las cámaras domésticas
> autorizadas son integrables sea cual sea su ubicación (`decisiones/2026-10-22-acta-camaras-zona-como-metadato.md`). Las menciones de
> «superficie interior sensible» o «interior autorizada» de abajo se leen con esa regla. La observación sigue siendo efímera, sin identidad.

> **STOP de gobernanza (§11 del prompt maestro).** Este paquete NO está aprobado y NADA se implementa hasta
> el acta del CEO. Presenta el bloque **completo** para una sola decisión consolidada.

## 1. Objetivo
Dar a AURA percepción **multimodal de cámara, local-first, bajo demanda y sin persistencia**, extendiendo el
patrón ya integrado FRAME→OBSERVACIÓN (visual) a **audio** (oír de la cámara) y, opcionalmente, a una **grada
de evento** (movimiento) — sin identidad, sin vigilancia, sin nube.

## 2. Problema
AURA hoy solo VE (frame bajo demanda de .110/.38) y solo oye/habla por el **micrófono/parlante del PC**. No
tiene audio de cámara ni eventos de cámara. El PCMA de .110 se anuncia pero no se recibe; los eventos ONVIF
de .110 no son legibles; el audio-salida a parlante de cámara no tiene ruta local. El bucle multimodal
(ver+oír+evento → razonar → responder) no cierra por ninguna superficie de cámara.

## 3. Estado actual (evidencia)
- **VER:** DEMOSTRADO — `CamaraRTSP → PercepcionVisual → Observacion`, integrado en el orchestrator
  (`percepcion_visual`, `es_consulta_visual`, dominio `percepcion_visual`) y cableado en `composicion.py`.
- **ESCUCHAR (cámara):** NO existe ruta. `camara_rtsp.py` lee solo video (cv2); no hay adaptador de audio.
- **EVENTOS:** ninguna cámara entrega eventos a AURA; percepción no emite `Senal`.
- **.110:** RTSP 554 (video demostrado; audio **PCMA/8000 OBSERVADO** en SDP), HTTP 80 (config `Ginatex`),
  **ONVIF funcional sin auth** (EYEPLUS/EYEPLUS_DEV/fw 3.5.1.1108); micrófono ONVIF `AudioSourceChannel1`
  confirmado; **audio-salida ONVIF NO implementada** («Optional Action Not Implemented», sin Profile T);
  **eventos ONVIF NO obtenibles** (GetEventProperties devuelve respuesta rota: Content-Length 4.388.308 vs.
  2.078 bytes entregados).
- **.32 (ULooka):** sin servicio local (RST en 6 puertos, host vivo) → **solo-nube**; BLOQUEADA local-first.
- **DVR .80:** **BLOQUEADO** (IP locked); DVRIP capaz por plataforma (video+audio+TTS-parlante) pero requiere
  **acción física** del propietario. No tocado.
- **HA:** solo 2 TVs; 0 entidades de cámara.

*(Detalle y «¿cómo lo sabemos?» en `INFORME-CAPACIDADES-MULTIMODAL-ECOSISTEMA.md`, §26.bis/§26.ter.)*

## 4. Evidencia — clasificación
- DEMOSTRADO: video .110/.38; ONVIF funcional sin auth; micrófono declarado (AudioSourceChannel1); audio-out
  ONVIF no implementado; eventos ONVIF no legibles; .32 sin servicio local.
- OBSERVADO: PCMA/8000 en SDP; HTTP Ginatex.
- ANUNCIADO: audio bidireccional por app-nube; DVRIP del DVR con audio/TTS.
- BLOQUEADO: DVR .80; audio-salida local; .32.

## 5. Arquitectura actual (relevante)
`adapters/camara_rtsp.py` (video-only) · `adapters/vision_local.py` · `core/percepcion.py`
(Frame/LecturaVisual/Observacion/PercepcionVisual/**PercepcionBajoDemanda**/es_consulta_visual) ·
`core/politica_superficie.py` (deny-by-default; **sin flag de audio**) · `adapters/voice_real.py`
(`_stt_sync(wav)` Whisper + Piper) · `adapters/escucha.py` (Vosk, micrófono PC) · `orchestrator.py`
(cascada determinista; `percepcion_visual` en 1474/1655-1664) · event bus + `Senal` (ALERTA-002).

## 6. Flujo actual
`«¿qué ves en la cámara X?» → es_consulta_visual → PercepcionBajoDemanda.observar → CamaraRTSP(frame) →
Observacion(metadatos) → describir_observacion → respuesta` · **sin memoria, sin evento, sin identidad.**

## 7. Flujo objetivo (del bloque)
Simetría auditiva: `«¿qué se oye en la cámara X?» → es_consulta_auditiva → PercepcionAuditivaBajoDemanda →
AudioRTSP(PCMA→PCM 16 kHz) → voice_real._stt_sync → ObservacionAuditiva(texto+metadatos) → respuesta`,
**bajo demanda, audio-cero de persistencia, gated por política, sin escucha continua.** (Evento: ver Alt.)

## 8. Gaps
(a) Sin adaptador de audio RTSP; (b) `politica_superficie` sin flag de audio; (c) sin reconocedor
`es_consulta_auditiva`; (d) sin cableado en orchestrator/composición; (e) evento: sin productor ni consumidor
(ONVIF de .110 roto); (f) audio-salida: sin ruta local (no construible sin DVR desbloqueado).

## 9. Dependencias
Decodificar PCMA→PCM: **PyAV `av` 18.0.0 está PRESENTE** [EJEC 2026-09-28] (trae libs ffmpeg embebidas; abre
RTSP y decodifica G.711 **sin binario externo y sin descargas**, cumple D24). El `ffmpeg` CLI está ausente
pero **no se necesita**. `faster_whisper.decode_audio` disponible. Whisper ya presente. Sin dependencias de
nube. → **Alt 2 es factible con las dependencias ya instaladas.**

## 10. Alternativas (reales)
- **Alt 1 — DIFERIR (no construir ahora).** Registrar «percepción auditiva de cámara» como **capacidad
  candidata** en `PLAN-DE-FORMACION-AURORA.md` y no construir hasta que exista **evidencia repetida de
  bloqueo operativo real** (regla CEO 2026-08-04). Coste: 0. Riesgo: 0. Deuda: se mantiene el gap.
- **Alt 2 — AUDIO-IN BAJO DEMANDA (espejo del visual).** Construir `AudioRTSP` + `PercepcionAuditivaBajoDemanda`
  + `es_consulta_auditiva` + flag `audio_processing_allowed` en política + cableado. AURA transcribe el audio
  de la cámara **solo cuando se le pregunta**; audio-cero de persistencia; sin escucha continua. Reutiliza
  Whisper y el patrón ya aprobado (acta de percepción visual).
- **Alt 3 — GRADA DE EVENTO PROPIA (movimiento) sobre frame RTSP.** En vez de audio, detección de movimiento
  **propia de AURA** sobre frames (no depende del ONVIF roto), como señal ambiental sin micrófono → menor
  riesgo de privacidad que el audio. Requiere definir productor de `Senal` + consumidor.
- **Alt 4 — AUDIO-IN + EVENTO (Alt 2 + Alt 3).** Bloque multimodal completo construible localmente. Mayor
  alcance, mayor superficie de riesgo/privacidad, más pruebas.

*(Audio-SALIDA a parlante y eventos-ONVIF quedan FUERA de lo construible: sin ruta local demostrada.)*

## 11. Comparación de alternativas
| Criterio | Alt 1 Diferir | Alt 2 Audio-in | Alt 3 Evento propio | Alt 4 Ambos |
|---|---|---|---|---|
| Coste/tokens | nulo | medio | medio | alto |
| Riesgo privacidad | nulo | **alto** (micrófono ambiental) | medio | alto |
| Riesgo autonomía/deriva | nulo | vigilancia auditiva | vigilancia visual | ambos |
| Reversibilidad | total | alta (bajo demanda) | alta | alta |
| Alineación regla evidencia-de-uso (CEO 2026-08-04) | **plena** | débil (idea, no bloqueo observado) | débil | débil |
| Acerca a AURORA a auto-mejora | indirecto | dudoso | dudoso | dudoso |
| Reutiliza patrón aprobado | — | sí (visual) | parcial | sí |

## 12. Riesgos
- **Deriva a vigilancia** (audio ambiental de un interior). Aunque sea bajo demanda, la capacidad *existe*.
- **STT alucina** con audio ruidoso/corto (ya documentado como riesgo que bloquea voz→acción).
- **Falsos «hechos»**: una transcripción de cámara no es un hecho verificado (ADR-0014, INV-9).
- **Coste HC-1**: Whisper + RTSP en 3,6 GiB RAM (ya medido tenso).

## 13. Seguridad
- **.110 expone ONVIF y RTSP SIN autenticación en LAN** + default documentado `admin/123456` → exposición
  real. Construir audio-in **no debe** depender de credencial débil; y se recomienda que el propietario
  endurezca la cámara (acción suya, fuera de este DP).
- Credenciales de cámara: nunca en código/log/informe (regla vigente); rotar las re-pegadas.

## 14. Privacidad
Choca de frente con la superficie interior sensible. Cualquier construcción exige: **bajo demanda**,
**audio-cero de persistencia**, gated por `politica_superficie`, sin escucha/grabación continua, y
tratamiento de terceros (ALERTA-002 `SenalDeTercero`: un interior puede captar voces de terceros). Debe
heredar el marco de la **acta de percepción visual** (2026-09-27): retención documentada ANTES de implementar.

## 15. Impacto físico
Ninguno de escritura (no se controla la cámara; no hay audio-salida). Solo lectura de audio/frame bajo demanda.

## 16. Impacto en autonomía
Marginal para la auto-mejora de AURORA. La regla CEO 2026-08-03 («si no acerca a comprender/planificar/
ejecutar/verificar/aprender/mejorarse, no pertenece a la hoja de ruta principal») pone en duda que el audio
de cámara sea prioridad frente a capacidades del anillo autónomo.

## 17. Impacto en memoria
**Ninguno por defecto** (audio-cero, como la observación visual no escribe memoria). Cualquier
`observación → memoria` sería decisión aparte (fuera de este DP).

## 18. Impacto en superficies
Añade una intención determinista nueva («¿qué se oye en la cámara X?») en la cascada del orchestrator, sin
tocar las superficies existentes (mismo patrón que la visual, que no las alteró).

## 19. Impacto en dispositivos
Solo lectura RTSP de .110 (superficie interior autorizada). No .32 (sin ruta local). No DVR (bloqueado).

## 20. Tests necesarios (por alternativa que se apruebe)
RED de «percibir audio bajo demanda produce observación auditiva consumible»; política niega superficies no
autorizadas para audio; **casos negativos** (sin audio, RTSP caído, PCMA inválido, timeout); que la
observación auditiva **NO** escriba memoria; que NO haya escucha continua; regresión de la cadena visual y de
la voz del PC.

## 21. E2E necesario
Con propietario presente y autorización: hablar frente a .110 → AURA transcribe **solo al pedírselo** → sin
persistencia → distinguible del micrófono del PC (transporte RTSP vs. `parecord`).

## 22. Criterios de aceptación (comportamiento demostrado)
AURA responde a «¿qué se oye en la cámara X?» con una transcripción real del audio de esa cámara, gobernada
por política, sin audio almacenado, sin identidad, sin escucha continua; y una superficie no autorizada no
produce audio. **Nunca «las pruebas pasan».**

## 23. Rollback
Todo el bloque es aditivo y bajo demanda: revertir = quitar el adaptador y el flag; sin migraciones ni estado
persistente que deshacer.

## 24. Cambios de Bible
Ninguno propuesto por este DP (extiende un patrón existente). Si se aprueba audio, la Bible debería reflejar
la nueva superficie de percepción auditiva — **decisión del CEO**, no unilateral.

## 25. ADR afectados
ADR-0014 (Core única fuente de verdad; una transcripción NO es hecho), ADR-0001/D24 (local-first, sin nube).
Ninguno se modifica; se respetan.

## 26. DP afectados
Sustituye/consolida los candidatos previos: **DP-AUDIO-CÁMARA-BAJO-DEMANDA** (= Alt 2), **DP-GRADA-DE-EVENTO**
(= Alt 3), **DP-SALIDA-PARLANTE-CÁMARA** (DESCARTADO: sin ruta local), **DP-INTEGRACIÓN-DVR** (PENDIENTE
acción física, fuera de este bloque).

## 27. Alcance
Percepción de **entrada** de cámara (.110), local-first, bajo demanda, sin persistencia. Audio y/o evento
según la alternativa aprobada.

## 28. Fuera de alcance
Audio-salida/parlante (sin ruta local); eventos ONVIF de .110 (rotos); identidad/reconocimiento;
persistencia de audio/video; escucha continua; .32 (nube); DVR (bloqueado); modificar Bible/ADR; commit/push.

## 29. Plan de implementación (si se aprueba; por defecto Alt 2 como unidad mínima)
RED (prueba que falla) → `AudioRTSP` (PCMA→PCM 16 kHz, credencial saneada como en CamaraRTSP) →
`PercepcionAuditivaBajoDemanda` + `es_consulta_auditiva` → flag `audio_processing_allowed` en política →
cableado en `orchestrator`/`composicion` → GREEN → integración → E2E → casos negativos → **mutación** (declarar
mutantes en `mutaciones/`) → regresión → auditoría independiente → Quality Gate → CHECKPOINT.

## 30. Plan de validación
Unit + integración (patrón de los tests visuales existentes) + E2E físico autorizado + mutación (incl.
«la observación auditiva escribe memoria» debe morir; «percibe sin autorización» debe morir) + regresión
completa + Quality Gate (BLOCKING/IMPORTANT/DEBT).

## 31. Decisiones humanas requeridas (DECISION_REQUIRED — BLOQUE COMPLETO)
1. **¿Se construye percepción multimodal de cámara ahora, o se difiere?** — Alt 1 (diferir, registrar en
   PLAN-DE-FORMACION) vs. Alt 2/3/4. *Tensión de gobernanza (deber de disenso, CLAUDE.md §6):* la regla CEO
   2026-08-04 dice que las capacidades nacen de **bloqueos observados y repetidos en la operación real**, no
   de ideas; hoy **no hay evidencia registrada** de que la falta de audio/evento de cámara haya bloqueado la
   operación diaria. Recomendación honesta del CTO: **Alt 1 (diferir)** salvo que el CEO declare este bloque
   como objetivo estratégico explícito — en cuyo caso, **Alt 2** (audio-in bajo demanda) es la unidad mínima
   más segura y reutiliza el patrón visual ya aprobado.
2. **Si se construye:** ¿Alt 2 (audio), Alt 3 (evento propio), o Alt 4 (ambos)?
3. **Marco de privacidad/retención** del audio: ¿hereda la acta de percepción visual (bajo demanda, cero
   persistencia, sin identidad) — sí/no, y con qué matices para terceros (ALERTA-002)?
4. **Endurecimiento de .110** (ONVIF/RTSP sin auth): ¿acción del propietario recomendada antes de construir
   audio-in sobre esa superficie?

---

### Resumen para el CEO
El bloque multimodal de cámara se reduce, tras la investigación, a **una** capacidad construible localmente:
**audio-in de .110 bajo demanda** (Alt 2), opcionalmente con **evento propio de movimiento** (Alt 3). El
audio-salida y los eventos-ONVIF **no tienen ruta local** en el equipo actual; el DVR está bloqueado. La
pregunta de fondo no es técnica sino **de prioridad y gobernanza**: ¿este bloque nace de un bloqueo real de
la operación, o es una idea que puede diferirse? **DECISION_REQUIRED — BLOQUE COMPLETO.** No implemento hasta
tu acta.

---

## APÉNDICE DE IMPLEMENTACIÓN (2026-09-28) — APROBADO CEO (Alt 4) e IMPLEMENTADO

**Decisión del CEO:** aprobado el bloque completo VER + ESCUCHAR + EVENTO (Alt 4), ejecución vertical, audio
bajo demanda / sin persistencia / sin identidad / sin escucha continua; parlante de cámara fuera de alcance;
hardening de .110 como acción separada del propietario (no bloqueante).

### Qué se construyó (código real, HEAD 6dad6af + working tree)
- `core/percepcion.py`: contratos de AUDIO (`AudioPCM`, `LecturaAuditiva`, `ObservacionAuditiva`,
  `PercepcionAuditiva`/`PercepcionAuditivaBajoDemanda`, `es_consulta_auditiva`, `describir_observacion_auditiva`)
  y de EVENTO (`EventoMovimiento`, `DetectorDeMovimiento`, `PercepcionDeEventoBajoDemanda`, `es_consulta_evento`,
  `describir_evento`). Imagen/audio-cero: sin campos de persona/identidad/pcm; la transcripción NO va al audit.
- `core/politica_superficie.py`: flag `audio_processing_allowed` + `puede_procesar_audio` (deny-by-default).
- `adapters/camara_pyav.py`: `CamaraPyAV` (VER por PyAV, resuelve `cv2` ausente) y `DetectorMovimientoPyAV`
  (EVENTO: diff de 2 frames gris 32×32; píxeles no salen del adapter).
- `adapters/audio_rtsp.py`: `AudioRTSP` (PCMA→PCM16k por PyAV; PCM transitorio, no persistido).
- `orchestrator.py`: superficies `percepcion_auditiva`/`percepcion_evento` (dominios propios), EVENTO y AUDIO
  evaluados ANTES que VISUAL (fix de colisión, ver abajo).
- `composicion.py`: cableado por variables de entorno `AURA_CAMARA_RTSP`/`AURA_CAMARA_AUDIO_RTSP`
  (sin hardcode, sin secretos, deny-by-default).

### Evidencia [EJEC]
- **VER**: frame real 1280×720 de .110 por el stack completo (PyAV). DEMOSTRADO E2E.
- **EVENTO**: detección real sobre 2 frames de .110 (magnitud 0.0002 en sala quieta). DEMOSTRADO E2E.
- **ESCUCHAR**: decode PCMA→PCM demostrado (PyAV, sin ffmpeg CLI, sin nube); pipeline + integración verdes.
  **E2E cámara→AURA BLOQUEADO por dispositivo**: .110 no entrega pista de audio en el stream accesible
  (av0 rechaza; /0/video0 audio=0). Superficie de audio en deny-by-default hasta acción del propietario
  (habilitar audio/acceso av0). Es el gate §5 del CEO no satisfecho por el dispositivo, no por el código.
- **Pruebas**: audio 11 + evento 9 + adapters 11 + integración 9 (incl. regresión de colisión) + visual 10 —
  todas verde. **Mutación 8/8 detectados, 0 supervivientes** (`mutaciones/multimodal-camara.toml`).
- **Failure test**: cámara inaccesible → degrada honestamente (VER «no recibí imagen», EVENTO «no detecté
  movimiento»), sin crash.

### Auditoría independiente (el que implementó NO auditó)
- **Seguridad**: sin CRITICAL/HIGH. Credenciales nunca expuestas/logueadas; sin persistencia de PCM/píxeles;
  transcripción fuera del audit; deny-by-default antes de tocar hardware; sin escucha continua; sin nube; sin
  hardcode. Deuda menor (defensa en profundidad): `raise ... from None` no borra `__context__` (sin fuga hoy);
  `_sanear` no cubre credencial en query-string (riesgo bajo).
- **Consistencia**: encontró **1 bug GRAVE** (reconocedores colisionaban: «que hay» visual vs «hay
  movimiento/alguien» evento → evento enmascarado) y **1 MENOR** (audio-solo sin superficie). **Ambos
  corregidos**: EVENTO/AUDIO se evalúan antes que VISUAL (+ prueba de regresión); superficie "camara" se crea
  con cualquiera de las dos variables. Resto verificado correcto (imagen/audio-cero, no-memoria,
  deny-by-default, no-hardcode, frozen sin identidad).

### Deuda / limitaciones (clasificadas)
- **DEBT**: E2E de audio cámara→AURA pendiente de acción física del propietario en .110 (habilitar audio).
- **DEBT (seguridad, defensa en profundidad)**: limpiar `__context__`/`__cause__` de excepciones saneadas si
  algún día se imprime traceback completo; ampliar `_sanear` a credenciales en query-string.
- **OBSERVACIÓN**: `DetectorMovimientoPyAV` ante cámara inaccesible reporta `detectado=False` (fail-safe, sin
  falso positivo); una grada futura podría distinguir «no pude vigilar».
- **Fuera de alcance (respetado)**: parlante de cámara (sin ruta local), eventos ONVIF (rotos), .32 (nube),
  DVR (bloqueado), identidad/persona.
