---
documento: "Informe de capacidades multimodal del ecosistema — audio + video + cámaras + DVR"
tipo: "INVESTIGACIÓN TÉCNICA (sin implementación). No es decisión, ADR ni cambio de producto."
fecha: 2026-09-28
version: "2 (profundizada: comunicación app↔dispositivo, interfaz local de .110, perfil documental del DVR)"
estado: "INVESTIGACIÓN MULTIMODAL — COMPLETADA (reduce incertidumbre; deja PF y candidatos de DP)"
fuente: "evidencia [EJEC] de esta sesión y previas + código real (HEAD 6dad6af) + Home Assistant local + connect-check controlado + documentación pública. NO memoria."
alcance: "SOLO investigación. Sin implementación, sin arquitectura nueva, sin tocar el DVR (IP locked), sin consumir contenido privado, sin credenciales."
---

# Informe de capacidades multimodal del ecosistema de AURA

**Método (repetido).** IP/hostname/etiqueta/SDP/fabricante/documentación **≠** capacidad demostrada por
AURA. Se separan estrictamente los niveles (§20): *protocolo existe ≠ dispositivo soporta ≠ interfaz local
accesible ≠ AURA consume ≠ AURA interpreta ≠ AURA responde ≠ dispositivo reproduce*. Estados:
**DEMOSTRADO · OBSERVADO · ANUNCIADO · DISPONIBLE-NO-VALIDADO · PENDIENTE-PRUEBA-FÍSICA · NO-ENCONTRADO ·
BLOQUEADO · NO-AUTORIZADO**. Cada conclusión responde **«¿cómo lo sabemos?»**.

**Por qué inline (CLAUDE.md §2 exige justificarlo).** Consolidación de evidencia + una comprobación de red
mínima y controlada + lectura documental + revisión de código; no hay implementación que dividir ni módulos
independientes que paralelizar. Auditoría independiente (evidencia vs. afirmación) queda como paso separado
si el CEO lo pide. Credenciales de capturas del propietario: **no reproducidas, no escritas** (§23).

**Qué añade la v2 sobre la v1:** (1) evidencia medida de que **.32 no tiene servicio local** (RST en 6
puertos, host vivo) → cloud/P2P confirmado; (2) hallazgo de **interfaz HTTP local en .110** (`Ginatex-
HTTPServer`, config web) y ONVIF documentado en puerto 80 para esa familia; (3) perfil documental del DVR:
**DVRIP/Sofia transporta video+audio y permite TTS por parlante**, con integraciones HA locales existentes —
pero este equipo sigue BLOQUEADO.

---

## 1. Resumen ejecutivo
- **VER:** DEMOSTRADO solo en **.110** (RTSP 554, frame 1280×720) y webcam **.38**. .32 y DVR: sin video
  para AURA hoy.
- **ESCUCHAR (audio de cámara):** **NO existe ruta en AURA.** `camara_rtsp.py` lee solo video (cv2). PCMA de
  .110 = **OBSERVADO** en SDP, sin receptor. Único oído real = micrófono del PC.
- **PERCIBIR EVENTOS:** ninguna cámara/DVR entrega eventos a AURA hoy; la percepción no emite `Senal`.
- **RAZONAR:** el orchestrator ya razona sobre texto/memoria/entorno; una observación visual bajo demanda ya
  se integra (DP FRAME→OBSERVACIÓN), pero sin audio ni evento.
- **COMUNICARSE (audio-salida a dispositivo):** hoy **solo el parlante del PC** (Piper). Rutas a parlante de
  dispositivo: **.32** = solo-nube (NO local); **.110** = posible ONVIF Profile-T backchannel (ANUNCIADO, NO
  validado) o app-nube (no local-first); **DVR** = DVRIP/Sofia soporta TTS-a-parlante **localmente**
  (ANUNCIADO por integraciones HA existentes) pero está BLOQUEADO.
- **Interfaces locales por dispositivo (medido/observado hoy):** .32 = **ninguna** (todos los puertos RST);
  .110 = **RTSP 554 + HTTP 80** (config web `Ginatex`); DVR = DVRIP 34567 (BLOQUEADO) + RTSP con SDP vacío.
- **Consecuencia:** el bucle multimodal completo (ver+oír+evento→razonar→responder→hablar por el dispositivo)
  **no puede cerrarse hoy** por ninguna superficie de cámara. La ruta local más capaz por plataforma es el
  **DVR (DVRIP)**, pero requiere **acción física** (desbloqueo). La ruta local más accesible ya hoy es
  **.110** (video demostrado; audio-in y ONVIF por validar).

---

## 2. Evidencia de las tres superficies (¿cómo lo sabemos?)

| Hecho | Evidencia | Estado |
|---|---|---|
| .110 RTSP 554 abierto; frame 1280×720 | connect-check 2026-09-28 (554 ABIERTO) + frame previo [EJEC] | DEMOSTRADO |
| .110 audio PCMA/8000 | SDP anunciado (previo) | OBSERVADO |
| **.110 HTTP 80 abierto (config web)** | connect-check + `curl -sI` → 302 /index.asp, `Server: Ginatex-HTTPServer` [EJEC 2026-09-28] | OBSERVADO (nuevo) |
| .110 ONVIF en puerto 80 | documentación de familia YCC365Plus (ispyconnect) | ANUNCIADO |
| **.32 sin servicio local** | connect-check: 80/443/554/8000/8080/8899 **RST (refused)**, host vivo [EJEC 2026-09-28] | DEMOSTRADO (no hay interfaz local) |
| .32 opera por nube/P2P | inferido de RST en todos los puertos entrantes + doc ULooka/Espressif | OBSERVADO/ANUNCIADO |
| DVR DVRIP 34567 video+audio, TTS-parlante | doc XMEye/Sofia + integraciones HA (xmeye-control, hass-xmeye) | ANUNCIADO (plataforma) |
| DVR este equipo | `[205] IP locked` + RTSP SDP vacío (previo) | BLOQUEADO |
| HA solo 2 TVs, 0 cámaras | `GET /api/states` local [EJEC 2026-09-28] | DEMOSTRADO |
| `camara_rtsp.py` solo video | lectura de código (cv2, 1 frame, sin pista de audio) | DEMOSTRADO |

**Nota de método sobre el connect-check:** fue **connect-only** (TCP SYN/ACK), sin datos, sin credenciales,
sin rutas, timeout 1 s, 6 puertos, solo **.32 y .110** — nunca **.80**. Es caracterización de interfaz
legítima (§16), no escaneo agresivo ni intento de login.

---

## 3. DVR .80 — Xiongmai / XMEye (seguridad exterior) — INVESTIGACIÓN OFFLINE
**Regla absoluta aplicada:** NO tocado. Cero conexiones a .80 esta sesión (`ss` lo confirma). Todo lo de
abajo es documentación + evidencia previa, **sin nueva interacción**.

| Aspecto | Evidencia/¿cómo lo sabemos? | Estado |
|---|---|---|
| Arquitectura | Xiongmai (uc-httpd); DVRIP = protocolo «Sofia» en 34567 | OBSERVADO/ANUNCIADO |
| RTSP 554 | DESCRIBE 200 con **SDP vacío** (previo) | NO-ENCONTRADO (stream utilizable) |
| DVRIP 34567 | `[205] IP locked` (previo) — el propio equipo se defendió | BLOQUEADO |
| DVRIP transporta audio | doc: firma `0x000001fa` (audio), `0x000001fc` (I-frame video) | ANUNCIADO |
| ONVIF | Xiongmai nominal en 8899, pero «hablan DVRIP, no ONVIF»; ONVIF genérico suele no hallar nada | ANUNCIADO/NO-VALIDADO |
| Audio-salida (TTS por parlante) | integración HA `TheJenos/xmeye-control` ofrece «TTS through the device speaker» vía DVRIP local | ANUNCIADO (plataforma), NO-VALIDADO (este equipo) |
| Integración local existente | `Moxnatiy/hass-xmeye`, `xmeye-control` (DVRIP local, sin nube) | ANUNCIADO (ruta local probada por terceros) |
| Cámaras exteriores: micrófono/parlante | bullets exteriores típicamente sin micro/altavoz | ANUNCIADO-genérico/NO-VALIDADO |
| Eventos (movimiento/pérdida de vídeo/alarma) | DVRIP los soporta | ANUNCIADO |

**Síntesis DVR:** por **plataforma** es la superficie **local** más capaz (video+audio+PTZ+eventos y hasta
TTS-a-parlante por DVRIP, con integraciones HA locales que lo demuestran en otros equipos). En **este**
equipo, **BLOQUEADO**: nada llega a AURA hoy. Desbloquearlo y habilitar stream = **PENDIENTE-ACCIÓN-FÍSICA
DEL PROPIETARIO** sobre el propio DVR. Que las bullets exteriores tengan micro/altavoz es dudoso y quedaría
por validar físicamente.

---

## 4. ULooka .32 — cámara interior (módulo Espressif)
**Identidad:** IP .32, app «ULooka», OUI Espressif. **¿Cómo se comunica la app con el dispositivo?** —
pregunta central de la misión.

**Evidencia medida (connect-check 2026-09-28):** los seis puertos entrantes estándar
(80/443/554/8000/8080/8899) devolvieron **RST (connection refused)**. RST ≠ timeout: el **host está vivo**
y con pila de red, pero **no escucha ningún servicio local entrante**. **¿Cómo lo sabemos?** medición
connect-only, sin credenciales.

**Interpretación (con documentación):** las cámaras ULooka/Espressif de bajo coste operan por **conexión
saliente a la nube del fabricante** (registro + relay/P2P tipo PPPP): el dispositivo **inicia** la conexión
hacia el servicio; la app llega a la cámara **a través de ese intermediario**, no por un servicio local
entrante. Por eso no hay puerto local que abrir.

| Capacidad | ¿Cómo lo sabemos? | Estado |
|---|---|---|
| Ruta LAN entrante | RST en 6 puertos, host vivo | NO-ENCONTRADO (no hay servicio local) |
| Video local (RTSP/HTTP) | 554/80 refused | NO-ENCONTRADO (local) |
| Audio-in local | sin transporte local | NO-ENCONTRADO (local) |
| Parlante (audio-out) local | sin interfaz local | NO-ENCONTRADO (local) |
| Micrófono/parlante del dispositivo | típico de cámara interior | ANUNCIADO (por nube) |
| Comunicación app↔dispositivo | vía **servicio intermedio (nube/P2P)**, no directa | OBSERVADO/ANUNCIADO |
| Eventos | por nube | NO-ENCONTRADO (local) |
| API cloud/P2P | nube ULooka | ANUNCIADO / NO-AUTORIZADO (local-first, sin claves de terceros) |

**Conclusión .32:** para AURA bajo local-first (D24/ADR-0001), **BLOQUEADA localmente**: no hay ruta que no
pase por la nube del fabricante. No es candidata a integración salvo que el firmware exponga una interfaz
local (no observada). «Solo-cloud» deja de ser hipótesis: es **evidencia medida** para las interfaces
entrantes estándar.

---

## 5. YCC365Plus / CloudCam .110 — cámara interior («habitacion»)
**Identidad:** IP .110, MAC 88:E6:28:BB:69:C1, modelo CloudCam, app YCC365Plus (firmware 3.5.1.1108),
servidor RTSP `TAS-Tech`, servidor HTTP `Ginatex-HTTPServer`. Superficie **interior** → gated por política.

| Capacidad | Evidencia / ¿cómo lo sabemos? | Estado |
|---|---|---|
| Video (RTSP 554) | frame 1280×720 por PercepcionVisual (previo); 554 ABIERTO (hoy) | DEMOSTRADO |
| Substream | SDP `/1/av0` (previo) | OBSERVADO |
| Micrófono (PCMA/8000) | SDP anunciado | OBSERVADO |
| Audio-in accesible (transporte) | pista de audio en el RTSP; **AURA no la abre** | DISPONIBLE-NO-VALIDADO |
| Audio-in decodificable | PCMA = G.711 a-law, estándar (ffmpeg) | ANUNCIADO |
| STT sobre audio de cámara | requiere adaptador inexistente + Whisper | PENDIENTE-PRUEBA-FÍSICA |
| **Interfaz HTTP local (80)** | `curl -sI` → `Server: Ginatex-HTTPServer`, 302 → /index.asp | OBSERVADO (UI de config web) |
| ONVIF local | familia YCC anuncia ONVIF **en puerto 80**; 8000/8899 cerrados aquí | ANUNCIADO / NO-VALIDADO (este equipo) |
| Parlante (audio-out) local | ONVIF Profile-T backchannel = vía teórica local; app = nube | ANUNCIADO / NO-VALIDADO |
| Audio bidireccional | función de app (nube/P2P) | ANUNCIADO / NO-AUTORIZADO local |
| Eventos (movimiento) | posiblemente por ONVIF/API local no verificada; percepción de AURA no los consume | NO-VALIDADO (dispositivo) / NO IMPLEMENTADO (AURA) |
| Control/PTZ | no investigado por red (evitar sobre-sondeo) | NO-ENCONTRADO (evidencia actual) |
| Integración HA | HA no la conoce | NO-ENCONTRADO |
| API cloud/P2P | YCC365Plus (nube) | ANUNCIADO / NO-AUTORIZADO local |

**Conclusión .110:** es la cámara **más accesible localmente**: video demostrado + micrófono anunciado por
RTSP + interfaz HTTP/ONVIF local por caracterizar. Las capacidades locales de **audio-in E2E** y de
**ONVIF (eventos / backchannel de parlante)** son las incertidumbres que quedan, y ambas se pueden reducir
con pruebas **controladas y autorizadas** (no ejecutadas aquí).

---

## 6. Video (transversal)
AURA obtiene frame por `CamaraRTSP → PercepcionVisual` de **.110** (1280×720) y **.38** (640×480).
**DEMOSTRADO.** .32 sin ruta local; DVR bloqueado. Frame = dimensiones, **sin** interpretación de contenido
ni identidad. Grada de **evento** (movimiento) no existe (DP identificado).

## 7. Audio de entrada (micrófono → AURA)
Hoy AURA solo oye por el **micrófono del PC** (Vosk wake word + Whisper STT; wake word validado por el aire
2026-09-28). **Audio de cámara: sin receptor** (`camara_rtsp.py` no abre pista de audio; no hay `AudioRTSP`).
PCMA de .110 = OBSERVADO en SDP, no recibido → **NO VALIDADO E2E**.

## 8. Audio de salida (AURA → parlante)
Hoy AURA solo habla por el **parlante del PC** (Piper → `paplay`). Hacia dispositivos:
- **.32:** NO-ENCONTRADO local (solo-nube).
- **.110:** ONVIF Profile-T backchannel = vía **teórica local** (ANUNCIADO/NO-VALIDADO); app = nube (no
  local-first).
- **DVR:** DVRIP/Sofia soporta **TTS por el parlante del dispositivo** (ANUNCIADO por integraciones HA
  locales) → **única ruta de audio-salida local documentada del ecosistema**, pero **BLOQUEADA** (IP locked)
  y sujeta a que exista parlante físico en el equipo/cámaras.

## 9. Eventos
AURA no recibe eventos de ninguna superficie. La percepción visual **no** publica al event bus ni emite
`Senal` (ver CUELLO-DE-BOTELLA-PERCEPCION.md). Fuentes documentadas de eventos: ONVIF de .110 (no validado),
DVRIP del DVR (bloqueado). **Grada de evento en AURA = PENDIENTE (DP).**

## 10. Comunicación (con el entorno) — síntesis
| Ruta | Local viable hoy | Nota |
|---|---|---|
| AURA → parlante PC | **SÍ (DEMOSTRADO)** | Piper |
| AURA → parlante .110 | NO (teórica: ONVIF backchannel) | ANUNCIADO/NO-VALIDADO |
| AURA → parlante .32 | NO | solo-nube |
| AURA → parlante DVR | NO hoy (BLOQUEADO); plataforma lo soporta local | requiere desbloqueo físico |
| AURA ← audio .110 | NO hoy (falta adaptador) | PCMA disponible, DP requerido |

## 11. Home Assistant (consulta local pasiva, 2026-09-28)
`GET /api/states` → 10 entidades: 2 `media_player` + 2 `remote` (las 2 TVs), 4 `sensor`, 1 `zone`, 1
`event`. **Cero** cámaras/audio/media de cámara. HA **no** aporta ruta a cámaras ni al DVR hoy. *Ausencia en
HA ≠ ausencia física* (las cámaras existen; simplemente no están integradas en HA). Para el DVR existe una
ruta HA local por DVRIP (integraciones de terceros), no instalada.

## 12. Arquitectura de AURA (qué existe, sin modificar)
| Componente | Entrada/qué hace | Qué NO hace |
|---|---|---|
| `adapters/camara_rtsp.py` | RTSP → **1 frame de video** (cv2); sanea credenciales | **no abre pista de audio**; no mantiene conexión |
| `adapters/vision_local.py` | webcam V4L2 → frame | ídem |
| `core/percepcion.py` | `Frame`/`LecturaVisual`/`Observacion`/`PercepcionBajoDemanda` (metadatos) | no audio; no identidad; no evento; no persistencia |
| `core/politica_superficie.py` | política por superficie (deny-by-default) | **no tiene flag de audio** (no existe audio de cámara) |
| `adapters/escucha.py` | wake word Vosk sobre micrófono del **PC** | no cámara |
| `adapters/voice_real.py` | STT Whisper (`_stt_sync`, wav→16 kHz) + TTS Piper — micrófono/parlante del **PC** | no cámara |
| event bus / `Senal` (ALERTA-002) | canal interno de señales | percepción **no** emite señales |
| `core/entorno.py` | inventario/estados del ecosistema (datos) | no adquiere audio/video |

**Dónde encajaría (sin implementar):** VIDEO entra por `camara_rtsp`→`percepcion`. AUDIO-in entraría por un
**adaptador nuevo** (RTSP audio → PCM 16 kHz) hacia `voice_real._stt_sync` — **no existe**. EVENTOS
requerirían productor (ONVIF/DVRIP/detector local) + emisión de `Senal` + consumidor — **no existen**. Una
observación se vuelve contexto por el camino ya abierto de FRAME→OBSERVACIÓN (bajo demanda). **No se creó
ningún manager nuevo.**

## 13. Interfaces LOCALES (medido/observado)
- **.110:** RTSP 554 (video+audio-pista), HTTP 80 (`Ginatex`, config web), ONVIF/80 (anunciado, no
  validado). **Es la única cámara con interfaz local real hoy.**
- **.32:** **ninguna** (todos los puertos entrantes RST).
- **DVR .80:** DVRIP 34567 (capaz, **BLOQUEADO**), RTSP 554 (SDP vacío).
- **PC .38:** V4L2 (webcam), ALSA/PulseAudio (micrófono/parlante) — superficie propia de AURA.

## 14. Interfaces CLOUD / P2P
- **.32 ULooka:** nube/P2P del fabricante (saliente). NO-AUTORIZADO para AURA (local-first, sin claves de
  terceros).
- **.110 YCC365Plus:** nube/P2P para acceso remoto e intercom bidireccional. NO-AUTORIZADO local-first.
- **DVR XMEye:** P2P XMEye (cloud) además de DVRIP local. La ruta a preferir sería **DVRIP local**, no la
  nube.

## 15. Capacidades DEMOSTRADAS
Frame .110 (1280×720) y .38 (640×480) por PercepcionVisual · wake word por micrófono del PC · STT/TTS del PC
· control de 2 TVs por HA/Motor Único · **.110 con HTTP 80 y RTSP 554 abiertos; .32 sin servicio local**
(connect-check).

## 16. Capacidades OBSERVADAS
SDP de .110 (H264 1280×720 + PCMA/8000 + substream) · `Ginatex-HTTPServer` en .110:80 · HA solo 2 TVs · DVR
RTSP SDP vacío · .32 host vivo sin puertos entrantes.

## 17. Capacidades ANUNCIADAS
Audio bidireccional de .110/.32 (app-nube) · ONVIF de .110 en puerto 80 · eventos por ONVIF/DVRIP · DVRIP
transporta audio y permite TTS-a-parlante (integraciones HA) · decodificación PCMA por ffmpeg · default
`admin/123456` en familia YCC (ver §23).

## 18. Capacidades NO VALIDADAS (interfaz existe/plausible, nunca probada E2E)
Audio de micrófono de .110 → STT de AURA · ONVIF local de .110 (eventos, Profile-T backchannel a parlante) ·
RTSP/DVRIP del DVR con stream real tras desbloqueo · audio-salida por DVR.

## 19. Capacidades BLOQUEADAS / NO-AUTORIZADAS
DVR .80 (IP locked — NO tocar) · .32 (solo-nube; sin ruta local) · toda API de nube de fabricante
(local-first D24/ADR-0001).

## 20. Pruebas físicas pendientes (preparadas, NO ejecutadas)

**PF-1 · VIDEO (cámara→frame→AURA→descripción).** *Ya cubierto para .110/.38 (DEMOSTRADO).* Reejecutable
como demo. Precondición: superficie autorizada. PASS: frame con dimensiones + descripción honesta sin
interpretar contenido. FAIL: sin frame / se afirma contenido. Demuestra: adquisición de video. NO demuestra:
percepción de evento/identidad.

**PF-2 · AUDIO-IN (cámara→micrófono→PCM→STT→AURA).** *Requiere DP-AUDIO-CÁMARA (adaptador inexistente).*
Precondiciones: propietario presente + autorización explícita + micrófono del PC **cerrado** (para no
confundir fuentes). Comandos (diseño): abrir pista RTSP `.../1/av0` (**PCMA/G.711 a-law, 8 kHz, 1 canal**),
decodificar a **PCM 16 kHz mono** (ffmpeg), alimentar `voice_real._stt_sync`. Evidencia esperada: texto que
corresponde a lo dicho ante la cámara. PASS: transcripción correcta cuyo transporte es la **URL RTSP** (no
`parecord`/alsa). FAIL: sin audio / transcripción del micrófono del PC. Latencia: t(captura RTSP)→t(texto).
Demuestra: cámara→AURA por audio. NO demuestra: comprensión ni salida.

**PF-3 · PARLANTE (AURA→TTS→dispositivo→parlante).** *Requiere determinar interfaz local:* ONVIF Profile-T
en .110 (por validar) **o** DVRIP en el DVR (bloqueado). Distinguir 4 niveles: comando enviado → dispositivo
aceptó → audio transmitido → **parlante reprodujo físicamente** (confirmación = alguien lo oye). Sin interfaz
local demostrada, PF-3 no se diseña en firme aún; su precondición es una prueba ONVIF controlada (§25).

**PF-4 · MULTIMODAL (persona habla + cámara observa → AURA → respuesta → parlante).** Depende de PF-2 + PF-3.
Hoy solo cerraría con: frame de cámara + **micrófono del PC** + **parlante del PC**. La versión «todo por la
cámara» requiere los DP de audio-in y audio-out.

**PF-VOZ-PC (independiente):** turno de conversación completo por el aire (wake→STT→memoria→voz). Cabe en
RAM (camino de memoria determinista, sin LLM). Wake word ya validado 2026-09-28.

**PF-DVR (acción física del propietario):** en el propio DVR, desbloquear IP + habilitar RTSP/ONVIF con
stream real; solo entonces evaluar `CamaraRTSP` (video) y, en fases posteriores, audio/eventos por DVRIP.

## 21. Riesgos
- **Deriva a vigilancia:** un adaptador de audio de cámara acerca a «micrófono ambiental siempre-escucha».
  Cualquier DP debe nacer **bajo demanda**, **audio-cero de persistencia**, gated por política — simetría con
  la acta de percepción visual.
- **Dependencia de nube:** integrar .32/.110 por app viola local-first; solo rutas locales son admisibles.
- **DVR:** re-tocarlo puede prolongar el bloqueo; el equipo ya se defendió una vez.

## 22. Privacidad
Cámaras interiores = superficie sensible. Prohibido hoy: captura/visualización continua, interpretación/
identidad de personas, reconocimiento facial, almacenamiento de frame/audio, escucha o vigilancia continua.
Prueba futura de contenido = **autorización explícita → prueba puntual → evidencia mínima → sin
persistencia** salvo DP aprobado. Esta investigación no consumió contenido (solo metadatos/cabeceras).

## 23. Seguridad
- **.110 RTSP sin desafío de auth** (DESCRIBE 200 sin auth, previo) + **default documentado `admin/123456`**
  para la familia YCC. **No se probó** ninguna credencial (prohibido). Riesgo real: stream interior accesible
  en LAN con credencial débil/ausente → **recomendar al propietario endurecer credencial local**.
- **.110 HTTP 80 (`Ginatex`)** = superficie de configuración local; exposición de UI web embebida (histórico
  de vulnerabilidades en servidores OEM). No se accedió a `/index.asp`.
- **.32** sin puertos entrantes = menor superficie de ataque local (bueno), pero depende de nube (traslada la
  confianza al fabricante).
- **DVR** IP-lock = mecanismo de defensa activo; respetarlo.
- **Credenciales re-pegadas** en misiones previas (ULooka/DVR/YCC): **no usadas ni escritas**; **rotar** por
  haber circulado en texto/imágenes.

## 24. Candidatos de Decision Package (CANDIDATO — no aprobar)
1. **DP-AUDIO-CÁMARA-BAJO-DEMANDA** — adaptador `AudioRTSP` (.110 PCMA → PCM 16 kHz → STT), bajo demanda,
   audio-cero, gated (nuevo flag `audio_processing_allowed`), sin escucha continua. Precondición de PF-2.
2. **DP-SALIDA-PARLANTE-CÁMARA** — solo si se demuestra interfaz **local** (ONVIF Profile-T en .110, o DVRIP
   en el DVR desbloqueado). Descartar si la única vía es nube. Precondición de PF-3.
3. **DP-GRADA-DE-EVENTO** — frame/stream local → movimiento/evento, en memoria, sin identidad, con
   consumidor (podría alimentarse de ONVIF de .110 o DVRIP del DVR).
4. **DP-INTEGRACIÓN-DVR** — tras PF-DVR (desbloqueo físico), integración local por DVRIP/Sofia (la más capaz:
   video+audio+PTZ+eventos+TTS-parlante), evitando la nube XMEye.

## 25. Recomendación técnica (NO evaluativa) — siguiente incertidumbre a resolver
La incertidumbre de mayor palanca, reducible con **una prueba controlada y autorizada** (no ejecutada aquí),
es: **¿expone .110 un servicio ONVIF local real en el puerto 80** (GetCapabilities/GetServices), y **con
qué perfiles** (¿eventos? ¿Profile-T backchannel de audio-salida)? Resolverlo decidiría, con evidencia y
**sin depender del DVR bloqueado ni de la nube**, si existe una ruta **local-first** para (a) eventos de
cámara y (b) audio-salida a parlante — las dos piezas hoy ausentes del bucle multimodal. Es una consulta
SOAP unautenticada mínima, con el propietario presente; si exige credencial, se detiene. En paralelo, la
audio-**entrada** de .110 ya es reducible por PF-2 (previa aprobación de DP-AUDIO-CÁMARA). El DVR queda
supeditado a acción física.

## 26.bis · VALIDACIÓN ONVIF .110 (prueba controlada, 2026-09-28)

Resuelve la incertidumbre de mayor palanca de §25. Prueba de **plano de control ONVIF, sin credenciales,
sin contenido** (ni stream, ni snapshot, ni audio, ni suscripciones persistentes).

1. **Método:** WS-Discovery (UDP 3702, un Probe) + SOAP HTTP a los endpoints ONVIF de :80. Operaciones
   **solo de lectura** (Get*). Sin Set*, sin reboot, sin credenciales, sin abrir RTP/stream.
2. **Autorización:** validación de superficie comisionada por el propietario (esta misión) sobre su propio
   dispositivo; ya autorizada explícitamente en validaciones previas de .110. Plano de control, sin
   consumo de contenido; la ausencia física del propietario solo condiciona pruebas de contenido/físicas.
3. **Endpoint:** WS-Discovery devolvió `XAddrs: http://192.168.20.110/onvif/device_service`,
   `Types: NetworkVideoTransmitter, Device`. GetServices dio XAddrs por servicio (`/onvif/Device`,
   `/onvif/Media`, `/onvif/Events`, `/onvif/Imaging`, `/onvif/DeviceIO`, `/onvif/Analytics`).
4. **Respuesta:** `GetCapabilities`, `GetServices`, `GetDeviceInformation`, `GetAudioSources`, `GetProfiles`
   respondieron **HTTP 200 SIN autenticación**. **¿Cómo lo sabemos?** SOAP sin cabecera WS-Security → 200.
5. **Capabilities / servicios:** Device, **Media (ver10)**, Events, Imaging (ver20), **DeviceIO** (ver10),
   Analytics (ver20); PTZ declarado en capabilities. **No** hay Media2 (ver20/media). Identidad ONVIF:
   **EYEPLUS / EYEPLUS_DEV / fw 3.5.1.1108 / HardwareId 88**.
6. **Servicios (clasificación):** Device management = **FUNCIONAL — METADATA** (DEMOSTRADO, sin auth).
   Media = FUNCIONAL-METADATA (GetProfiles 200: `Profile_1`, `Profile_2`, video **H264**). Events, Imaging,
   DeviceIO, Analytics, PTZ = **ANUNCIADOS** (declarados; no todos validados).
7. **Audio de entrada (micrófono):** `GetAudioSources` → **`AudioSourceChannel1`** (200). Micrófono
   **CONFIRMADO por metadata ONVIF** (corrobora el PCMA/8000 del SDP RTSP). *Matiz:* los perfiles Media no
   mostraron `AudioEncoderConfiguration` ligada; el audio viaja por la pista RTSP (SDP), no por un perfil
   ONVIF con audio-encoder evidente. Estado: **audio-in ANUNCIADO/OBSERVADO**, E2E **NO VALIDADO** (sin
   adaptador; PF-2).
8. **Audio de salida (parlante) / backchannel:** `GetAudioOutputs` → **fault «Optional Action Not
   Implemented»**. El flag `AudioOutputs` de capabilities **no está implementado**. Sin Media2 → **sin
   Profile T** → sin backchannel ONVIF estándar. **Conclusión: NO existe ruta local ONVIF de audio-salida
   en este dispositivo.** El parlante solo por app-nube (no local-first). Estado: **NO-ENCONTRADO (local)**.
9. **Eventos:** servicio Events **ANUNCIADO** con XAddr `/onvif/Events`, pero `GetEventProperties` **no
   respondió** sin autenticación (endpoint no devolvió metadata). Estado: **ANUNCIADO / topics NO-VALIDADO**
   (probable WS-Security o suscripción requerida). Analytics (ver20) presente podría aportar movimiento,
   tampoco validado. No se dejaron suscripciones ni listeners.
10. **Autenticación:** Device/Media/DeviceIO(sources)/Profiles respondieron **SIN auth**. Events no
    respondió (posible AUTH_REQUIRED). No se probó ninguna credencial (prohibido).
11. **Qué quedó DEMOSTRADO:** ONVIF **funcional sin auth** (Device management + Media metadata); micrófono
    declarado (`AudioSourceChannel1`); **audio-salida NO implementada** (fault explícito); no Profile T.
12. **Qué quedó ANUNCIADO:** Events, Imaging, DeviceIO, Analytics, PTZ (servicios declarados no validados);
    audio-in por RTSP (transporte disponible).
13. **Qué queda PENDIENTE-PRUEBA-FÍSICA:** audio-in E2E de la cámara → STT (requiere DP-AUDIO-CÁMARA y un
    adaptador RTSP-audio); enumeración de eventos ONVIF (requiere resolver auth de Events, prueba controlada
    con el propietario). **Audio-salida a parlante local queda descartada por esta vía** (no implementada).

**Respuestas al criterio de éxito (§17 de la misión):**
- **P1 ¿ONVIF funcional?** SÍ — Device management responde sin auth (DEMOSTRADO).
- **P2 ¿Servicios?** Device, Media(ver10), Events, Imaging, DeviceIO, Analytics (+PTZ).
- **P3 ¿Eventos?** Servicio anunciado; topics NO-VALIDADO (Events no respondió sin auth).
- **P4 ¿Audio de entrada?** SÍ declarado (`AudioSourceChannel1`); E2E NO validado.
- **P5 ¿Audio de salida/backchannel?** **NO** — GetAudioOutputs «not implemented»; sin Profile T.
- **P6 ¿Ruta local-first cámara→ONVIF/RTSP→AURA sin nube?** **SÍ para VER (video) y, potencialmente, ESCUCHAR
  (audio-in por RTSP)**; **NO para HABLAR (parlante)**. El control/metadata/PTZ y (con auth) eventos son
  locales por ONVIF; el audio-salida NO tiene ruta local.

**Hallazgo de seguridad (relevante):** el ONVIF Device Management de .110 responde a GetDeviceInformation,
GetCapabilities, GetServices, GetAudioSources y GetProfiles **sin autenticación** en la LAN — modelo/
firmware y enumeración completa de capacidades y perfiles accesibles por cualquiera en la red, sumado al
RTSP abierto. **Recomendar al propietario endurecer credenciales/segmentar la cámara.** (No es acción de
esta sesión.)

**Impacto en los candidatos de DP:** **DP-SALIDA-PARLANTE-CÁMARA por .110 queda descartado** (sin interfaz
local); la única ruta local de audio-salida del ecosistema sería el **DVR por DVRIP** (bloqueado, acción
física). **DP-GRADA-DE-EVENTO** gana una fuente local candidata (Events/Analytics ONVIF de .110), pendiente
de resolver la auth de Events. **DP-AUDIO-CÁMARA-BAJO-DEMANDA** se confirma como la vía para audio-in local.

## 26.ter · VALIDACIÓN ONVIF EVENTS .110 (prueba controlada, 2026-09-28)

Continúa §26.bis. Objetivo único: **qué eventos ONVIF expone .110**. Read-only, sin credenciales, sin
contenido, sin suscripciones persistentes.

1. **Método:** `GetEventProperties` al XAddr confirmado `http://192.168.20.110/onvif/Events`, **con
   cabeceras WS-Addressing** (`Action` + `To` + `MessageID`) que faltaban en el intento previo; primero vía
   urllib, luego socket crudo HTTP/1.0 `Connection: close` leyendo hasta EOF (cap 400 KB).
2. **Autenticación:** **no fue necesaria.** El servicio respondió **sin WS-Security**. La conclusión previa
   («no respondió sin auth») era un artefacto de **faltar WS-Addressing**, no un AUTH_REQUIRED. No se probó
   ninguna credencial.
3. **GetEventProperties (respuesta):** el servidor devolvió `HTTP` con `Content-Length: 4388308` (~4,4 MB)
   pero **entregó solo 2078 bytes de cuerpo** (la apertura del `env:Envelope` + declaraciones de namespaces)
   y **cerró la conexión** sin enviar el `TopicSet`. **¿Cómo lo sabemos?** `IncompleteRead(2078 bytes read,
   4386230 more expected)` en urllib y, con socket crudo, 2078 bytes de cuerpo de un Content-Length de
   4.388.308, sin aparecer el elemento `TopicSet`. Es un **defecto de la implementación ONVIF del
   dispositivo** (Content-Length falso / TopicSet no entregado), común en stacks OEM.
4. **TopicNamespace:** **no entregado** (el cuerpo se cortó antes del TopicSet).
5. **TopicSet:** **no entregado.** 0 elementos `wstop:topic="true"` recibidos.
6. **Eventos encontrados:** **ninguno confirmable.** (Los términos «analytics/imaging/ptz» que aparecen en
   los 2078 bytes son **declaraciones `xmlns`**, no topics — no cuentan como evidencia.)
7. **Eventos NO encontrados / no verificables:** Motion, CellMotion, MotionAlarm, VideoSource, Tampering,
   Audio, DigitalInput, VideoLoss, Person/Human/Object — **ninguno pudo leerse** del contrato.
8. **Soporte ANUNCIADO:** el servicio Events existe (capabilities + XAddr `/onvif/Events`) y **responde**;
   por familia OEM (EYEPLUS/YCC365Plus) suele exponer detección de movimiento por ONVIF. **ANUNCIADO.**
9. **Soporte NO VALIDADO:** el **contrato de topics** (qué eventos y su forma) es **NO-OBTENIBLE** por
   `GetEventProperties` en este dispositivo (respuesta rota). Sin el contrato, no hay evento confirmado.
10. **Implicaciones para percepción:** la cadena candidata *movimiento ONVIF → señal → AURA → (frame bajo
    demanda) → PercepcionVisual* **no puede fundarse hoy** sobre este dispositivo: sin contrato de eventos
    legible, no hay señal ONVIF fiable. Obtenerla exigiría o un firmware que responda bien a
    GetEventProperties, o **crear una suscripción PullPoint** y hacer PullMessages — **fuera de alcance**
    (esta misión prohíbe suscripciones persistentes) y sería una **prueba física/posterior** con el
    propietario. `evento ≠ percepción ≠ comprensión ≠ decisión` se mantiene.
11. **Privacidad:** no se capturó contenido (ni frame, ni audio, ni stream); solo plano de control. La
    respuesta recibida contenía únicamente namespaces. No se dejaron suscripciones ni listeners.
12. **Siguiente incertidumbre:** ¿entrega .110 su `TopicSet` mediante otra vía (p. ej. una suscripción
    PullPoint efímera con PullMessages, con el propietario presente y autorizando la prueba), o su ONVIF
    Events está tan roto que la ruta de eventos local-first por ONVIF **no es viable** en este equipo? Eso
    decidiría si **DP-GRADA-DE-EVENTO** puede apoyarse en ONVIF de .110 o debe buscar otra fuente
    (detección de movimiento **propia** sobre el frame RTSP, ya local-first, sin depender del ONVIF roto).

**Respuestas al criterio de éxito (§16 de la misión):**
- **¿Qué eventos ONVIF expone .110?** No determinable de forma no invasiva: el servicio Events responde sin
  auth pero su `GetEventProperties` entrega una respuesta **rota** (Content-Length 4.388.308, cuerpo 2.078
  bytes, sin TopicSet). Contrato de eventos = **NO-OBTENIBLE / NO-VALIDADO**.
- **¿Existe un evento local de movimiento utilizable como señal previa a la percepción visual?** **NO
  VALIDADO.** ANUNCIADO por familia; no confirmable en este equipo sin suscripción (prohibida aquí).

**Impacto en DP:** **DP-GRADA-DE-EVENTO** no puede apoyarse hoy en los eventos ONVIF de .110 (contrato no
legible). Alternativa local-first **más robusta**: detección de movimiento **propia de AURA** sobre el frame
RTSP (bajo demanda), que no depende del ONVIF Events roto del dispositivo. Queda como incertidumbre a
decidir.

## 26. Estado final
- **INVESTIGACIÓN MULTIMODAL — COMPLETADA.** Interfaces mapeadas, capacidades clasificadas, incertidumbres
  restantes identificadas, PF preparadas, candidatos de DP documentados.
- **Git:** HEAD `6dad6af` intacto; **ningún `.py` de producto modificado** por esta sesión; cambios solo en
  docs (este informe + CHECKPOINT). Sin commit/push/merge.
- **DVR:** no tocado (0 conexiones a .80).
- **Privacidad/credenciales:** sin consumo de contenido; sin credenciales usadas ni escritas.

---

### DECISION_REQUIRED — HUMANO
Nada aquí autoriza construir. Para avanzar en multimodal de cámara la familia debe decidir, por separado y
con evidencia: **DP-AUDIO-CÁMARA-BAJO-DEMANDA** (¿construir la entrada de audio de .110, bajo demanda, sin
persistencia?) y **DP-SALIDA-PARLANTE-CÁMARA** (dependiente de que la prueba ONVIF de §25 halle una ruta
**local**). El DVR y .32 quedan fuera hasta que haya **acción física** que abra una ruta local. Ningún DP se
aprueba automáticamente.

---

## Fuentes de documentación consultadas (pública; no secretos)
- YCC365Plus — RTSP/ONVIF/puertos: ispyconnect.com/camera/ycc365-plus · ycc365plus.com (RTSP url/port FAQ).
- Xiongmai/XMEye/Sofia (DVRIP 34567), audio/eventos y TTS-a-parlante local (HA): github.com/TheJenos/xmeye-control
  · github.com/Moxnatiy/hass-xmeye · ispyconnect.com/camera/xmeye.
- Modelo cloud/P2P de cámaras Espressif/OEM: doc general de la categoría (relay saliente).
