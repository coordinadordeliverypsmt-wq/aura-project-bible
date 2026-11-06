---
documento: "Mapa del ecosistema físico de AURA — inventario + caracterización"
tipo: "INVESTIGACIÓN (sin implementación). No es decisión ni ADR."
fecha: 2026-09-28
estado: "PARADA — investigación cerrada; una decisión estratégica identificada (§ Brechas H)"
fuente: "evidencia [EJEC] de esta sesión + Home Assistant local; no memoria"
---

# Mapa del ecosistema físico observable por AURA

**Advertencia de método:** IP/hostname/etiqueta ≠ ubicación/persona. Las zonas físicas por dispositivo
NO están demostradas; se marcan DESCONOCIDO salvo declaración explícita del propietario.

> **Nota (2026-10-22):** donde este documento dice «interior», «gated por política» o «superficie interior», es histórico. La zona
> es METADATO y nunca deniega (acta `decisiones/2026-10-22-acta-camaras-zona-como-metadato.md`); la .110 se llama «habitacion» y la
> activa el propietario (§10).

## 1. Inventario (evidencia de red + HA)

| IP | Identidad (OUI/HA) | Categoría | Integración HA | Control | Fuente visual | Estado |
|---|---|---|---|---|---|---|
| .1 | router (Hefei Radio / MiniUPnPd IGD) | RED/gateway | no | no | no | DESCUBIERTO |
| .20 | Samsung UN55KU6000 (TV 55") | MEDIA | **sí (samsungtv)** | power/vol/mute/fuente | no | INTEGRADO |
| .29 | Samsung UN43RU7100 (TV 43") | MEDIA | **sí (samsungtv)** | power/vol/mute/fuente (efecto verificado) | no | INTEGRADO |
| .32 | ULooka (Espressif) | VISIÓN | no | no | **solo-nube** (sin puertos locales) | IDENTIFICADO |
| .80 | DVR Xiongmai/XMEye | VISIÓN/SEGURIDAD ext. | no | no | RTSP off; DVRIP/34567; **IP locked** | CARACTERIZADO · NO TOCAR |
| .110 | cámara (Shenzhen Kezhonglong; TAS-Tech RTSP 554) | VISIÓN | no | no | **RTSP local presente** (interior; gated por política) | CARACTERIZADO |
| .24/.93/.94/.96 | teléfonos (Android/iOS) | PRESENCIA | no | no | no | DESCUBIERTO (presencia técnica, NO persona) |
| .38 | equipo local de AURA | PLATAFORMA | — | — | **webcam: frame real demostrado** | superficie propia |

HA conoce hoy SOLO las 2 TVs (2× samsungtv, 2 media_player, 2 remote, 4 sensores diag, zona home). Sin
entidades camera/light/switch/binary_sensor.

## 2. Fuentes de percepción hacia CamaraRTSP → PercepcionVisual → política
- **Cámara local .38**: frame real DEMOSTRADO (640×480, en memoria, sin guardar).
- **.110 (interior)**: RTSP local existe; frame gobernado por política de superficie interior (no lo
  decodifica AURA por defecto; lo autoriza/opera el propietario).
- **DVR .80 (exterior)**: ruta DVRIP legítima identificada, pero IP bloqueada por el equipo; RTSP off.
- **.32 ULooka / YCC**: solo-nube; sin ruta local/estándar.

## 3. Fuentes de control
- HA → 2 TVs, por el Motor Único (INTENCIÓN→AUTORIZACIÓN→Motor→HA→dispositivo). Sin lectura de contenido.

## 4. Relaciones
| Relación | Evidencia | Estado |
|---|---|---|
| cualquier dispositivo → habitación/zona | ninguna | DESCONOCIDA |
| teléfono → persona | ninguna | DESCONOCIDA (no se infiere) |
| cámara ↔ TV (misma sala) | ninguna | HIPÓTESIS |

## 5. Brechas
- **A. AURA ya puede:** encender/apagar en 2 TVs (efecto verificado en .29); recibir un frame real de su cámara
  local. **Corrección 2026-10-22 (declarado ≠ real):** este punto afirmaba también volumen, silencio y fuente, pero
  NO había código para ello; Home Assistant los ANUNCIA (`supported_features` 24509), y eso no es lo mismo que
  poder usarlos. Volumen y silencio se construyen el 2026-10-22 (acta `decisiones/2026-10-22-acta-ecosistema-domestico.md`
  §4), probados con dobles y con el efecto real aún PENDIENTE de verificarse con la TV encendida. La fuente sigue sin
  implementar.
- **B. Observa pero no comprende:** el frame local (lo recibe; no hay detección/identidad).
- **C. Controla pero no observa:** las TVs (controla; no ve contenido ni pantalla).
- **D. Observa pero no controla:** cámara local; presencia de dispositivos en red.
- **E. Requiere percepción:** interpretar frames (evento/persona) — no implementado.
- **F. Requiere nueva interfaz:** contenido/app de TV (no expuesto por samsungtv); ULooka/YCC (nube).
- **G. Requiere config física del dispositivo:** DVR (habilitar RTSP/ONVIF + desbloquear IP); .110
  (habilitar RTSP + credencial local en la app).
- **H. Requiere DECISIÓN arquitectónica:** grada de percepción de EVENTO (frame→movimiento/evento, local,
  sin identidad) y, aparte y posterior, persona/identidad (choque ALERTA-002 + retención). No implementado.
- **I. Desconocido:** .96; zonas físicas; a quién pertenece cada teléfono.

## 6. Cuello de botella principal
La percepción visual se detiene en **«frame recibido»**: no existe la grada de **detección de evento**, y
las fuentes de frame de red están bloqueadas por configuración del propio dispositivo (DVR IP-locked/RTSP
off; .110 interior gated). El control de TV no puede leer contenido.

## 7. Siguiente acción mínima (NO ejecutada)
Ninguna implementación en esta fase. La siguiente capacidad candidata —grada de **evento** sobre frames
locales (movimiento, en memoria, sin identidad)— es una **DECISIÓN** (nueva capacidad de percepción), no un
arreglo. Se propondría como Decision Package si el CEO lo aprueba.

---

## Addendum 2026-09-28 · correlaciones, telemetría TV, frontend

- **YCC365Plus = .110** (MAC 88:E6:28:BB:69:C1 idéntica; serie AJWL200708101YP47Q874KI4TR112829). Es la
  cámara con **RTSP local** (`TAS-Tech`, 554). Superficie INTERIOR → gated por política; frame lo autoriza/
  opera el propietario (necesita habilitar RTSP + credencial local en la app YCC). No es solo-nube.
- **Telemetría TV vs visión** [OBSERVADO/NO DISPONIBLE]: por HA (samsungtv) hay power/volumen/mute/
  source_list y CONTROL. NO hay app/media_title/contenido. `RemoteControlReceiver` = envío de teclas de una
  vía, sin feedback de contenido. `MediaRenderer`/AVTransport solo refleja lo empujado por DLNA, NO las apps
  nativas (Netflix/YouTube). ⇒ **Saber qué app/contenido muestra la TV, sin visión = NO DISPONIBLE.**
  Imagen de pantalla de la TV = NO DISPONIBLE (sin interfaz local de captura en estos modelos Samsung).
- **Frontend** [OBSERVADO]: el repo NO tiene frontend de aplicación (solo `publicado/html/` = la Bible
  renderizada). Superficies actuales: conversacional (texto/voz) + conectores. El modelo del ecosistema vive
  en `core/entorno.py` (InventarioEntorno/Dispositivo) + `core/politica_superficie.py`. Un dashboard del
  ecosistema sería **greenfield** y consumiría ese modelo (no crear uno paralelo). Requiere Decision Package.

**Capacidades candidatas (NO implementar; requieren Decision Package):**
1. Grada de percepción de **EVENTO** (frame local → movimiento, sin identidad, sin persistencia).
2. **Frontend/dashboard** del ecosistema sobre el modelo `entorno.py`+`politica_superficie.py`.
3. Autorización de **superficie interior** (YCC/.110) para captura por el propietario.

---

## Addendum 2026-09-28b · FRAME REAL de YCC365Plus/.110 [DEMOSTRADO]

Validación vertical solicitada, sin modificar producto (HEAD 6dad6af).

- **Identidad**: YCC365Plus = .110 (MAC 88:E6:28:BB:69:C1) — DEMOSTRADO.
- **SDP (metadatos, sin decodificar)**: RTSP **abierto (sin auth)**, `H264 1280×720` + audio `PCMA/8000`
  (micrófono), control `rtsp://192.168.20.110:554/0/video0`, live (`npt=now-`).
- **Cadena RTSP**: OPTIONS 200 · DESCRIBE 200 (sin desafío de auth) · stream real presente.
- **FRAME REAL [DEMOSTRADO]**: por `PercepcionVisual(CamaraRTSP, superficie=ycc_110, politica)` — superficie
  interior **autorizada explícitamente por el propietario para esta validación**. Resultado: recibido=True,
  **1280×720**, persona=None, identidad=None, ~4,7 s. **La imagen NO se vio, NO se interpretó, NO se guardó**
  (reducida a dimensiones); sin identidad; sin persistencia. La política gobernó el acceso; el producto no
  se modificó.
- **Comparación .38 (webcam local)**: ambas alcanzan FRAME REAL por el mismo puerto `PercepcionVisual`
  (.38 640×480 vía V4L2; .110 1280×720 vía RTSP). Confirma que el puerto de percepción es agnóstico a la
  fuente. NO se extrapola nada más (detección/identidad siguen sin implementar).
- **Capacidad candidata revelada (NO implementar)**: .110 expone **audio (micrófono PCMA)** además de vídeo
  → futura entrada de audio de cámara. Requiere Decision Package.

**Clasificación:** stream real + frame 1280×720 = DEMOSTRADO. Detección/persona/identidad = NO IMPLEMENTADO.
Micrófono de cámara = OBSERVADO (SDP), no capturado. Sin cambios de producto, sin commit/push/merge.

## 6. Observación del 2026-10-22 (06:16-06:30, jueves) — solo lectura, métodos pasivos o dirigidos

Métodos `[EJEC]`:
- `red_local.descubrir()` de AURA: ARP, mDNS (avahi) y SSDP (M-SEARCH estándar).
- Lectura de `/api/states` en el HA real.
- Un eco ICMP a cada IP del censo del 2026-09-27; es dirigido, no es un barrido.
- Una búsqueda DDP de PlayStation (UDP 9302/987) a las 00:5x del mismo día.

No se sondearon puertos ni se probaron credenciales. **La ausencia de respuesta NO prueba que un dispositivo no exista:** a
esa hora los teléfonos y las TV suelen estar en reposo o fuera de casa.

| IP | Identificación | Estado observado | Método | Integración | Confirmado / inferido / desconocido |
|---|---|---|---|---|---|
| .1 | router; SSDP «Ubuntu router», InternetGatewayDevice; mDNS `cable-gw63E` (SSH/SFTP solo por IPv6) | responde | ARP, SSDP, mDNS | ninguna (fuente «router» no autorizada) | confirmado |
| .20 | Samsung UN55KU6000 (HA `media_player.samsung_6_series_55_un55ku6000`) | HA: `off` desde el 21-10 23:01 UTC; ICMP sin respuesta | HA, ICMP | **integrada** (samsungtv), encender/apagar | confirmado por HA |
| .29 | TV de la sala Samsung UN43RU7100 (`media_player.tv_sala_fmilia_medina_un43ru7100fxza`) | HA: `off` desde el 20-10 22:38 UTC; ICMP sin respuesta | HA, ICMP | **integrada**: encender/apagar (nivel 5); volumen y silencio (nivel 4); consulta de estado (apagada, real) | confirmado por HA |
| .80 | DVR (censo: Xiongmai, «NO TOCAR»); MAC con prefijo 00:12:17 | responde | ICMP, ARP | ninguna, **no se toca** | presencia confirmada; identidad del censo previo |
| .110 | cámara (censo: TAS-Tech, RTSP 554) | sin respuesta | ICMP | sin integrar (limitada por política) | desconocido hoy |
| .24 / .93 / .94 / .96 | teléfonos (censo: solo presencia técnica) | sin respuesta | ICMP | ninguna | desconocido hoy |
| .32 | ULooka (solo nube, D24) | sin respuesta | ICMP | excluida (D24) | desconocido hoy |
| — | PS5 | 0 respuestas DDP | DDP | ninguna | **desconocido**: puede estar apagada o con la red en reposo |
| — | relojes, auriculares | no aparecen por ARP, mDNS ni SSDP | — | ninguna | desconocido. Sus integraciones habituales son por Bluetooth o la nube (Bluetooth bloqueado por software en este equipo; la nube, por D24) |

**Funciones que exponen las TV:** `supported_features` 24509, es decir volumen (por pasos, fijado y silencio), fuente,
reproducción, encender y apagar. Con la TV apagada no hay atributos de volumen ni de contenido. Qué expone con la TV
encendida (`volume_level`, `source`, `app_name`, `media_title`) está **pendiente**.

### 6.1 Actualización 07:12-07:20 del 2026-10-22: la cámara .110 VUELVE a estar en línea

- **06:5x `[EJEC]`:** la .110 no respondía. ARP `INCOMPLETE`, TCP 554 y 80 sin respuesta, 0 respuestas WS-Discovery: nada
  contestaba ni siquiera a nivel de enlace. No era concluyente; probablemente estaba en reposo o fuera de la Wi-Fi.
- **07:12 `[EJEC]`:** el descubrimiento de AURA, ampliado hoy con WS-Discovery/ONVIF (ver el registro del mapa maestro), la
  ENCUENTRA:
  - `tipo_declarado` = cámara, con `video_entrada`;
  - identidad ONVIF `urn:uuid:1df2e14e-1dd2-11b2-8323-88e628bb69c1`, cuyo sufijo coincide con la MAC del censo,
    88:E6:28:BB:69:C1;
  - TCP 554 (RTSP) y 80 abiertos (10 ms); ARP con la MAC del censo.
  - Su ProbeMatch trae los *scopes* vacíos: el nombre «EYEPLUS» del censo salió de `GetDeviceInformation`, que este
    descubrimiento NO consulta (no sigue XAddrs).
- **Estado:** descubierta → identificada → **accesible** (RTSP abierto). **NO** se capturó ningún frame. Para hacerlo, el
  propietario tiene que activar `AURA_CAMARA_RTSP`, la superficie «interior» de `composicion.py` que hoy no define ningún
  lanzador, y estar presente (criterio E2E del `DP-PERCEPCION-MULTIMODAL-CONSOLIDADO.md` §21). Sin persona ni identidad
  (decisión B); audio solo bajo demanda y con su propia variable.
- **PS5:** 0 respuestas DDP también a las 07:12, con el productor nuevo de AURA. No es concluyente.

### 6.2 ~~Procedimiento para la PRIMERA captura real de la .110~~ — RETIRADO el 2026-10-22 a las 11:30

> **RETIRO REVOCADO (2026-10-22, tarde; acta `decisiones/2026-10-22-acta-camaras-zona-como-metadato.md`):** el motivo
> (dormitorio ⇒ restringido) ya no rige. El procedimiento vigente es el del §10.

**Retirado:** la app de la cámara, en una captura del propietario, la nombra **«habitacion»**: es un DORMITORIO. La política de superficies (corrección del CEO del 2026-09-28) dice que «un canal privado (dormitorio) queda restringido», y este procedimiento lo habría autorizado con la zona «interior», que inventa la composición. NO se ejecuta. Ver §7.

Texto original, conservado como registro:

Requisitos (`DP-PERCEPCION-MULTIMODAL-CONSOLIDADO.md` §21 y acta de percepción del 2026-09-27): **propietario presente
y activación expresa**. La activación es definir la URL, que equivale a autorizar la superficie «interior» en
`composicion.py`. Solo VÍDEO: el audio tiene su propia variable y NO se activa. Sin persona ni identidad (decisión B). El
DVR .80 no se toca. No se modifica nada en la cámara.

1. Comprobar que la cámara está en línea (solo lectura): `ip neigh show 192.168.20.110` debe dar la MAC
   `88:e6:28:bb:69:c1`, y el puerto 554 debe estar abierto.
2. El propietario arranca AURA en modo texto con la variable SOLO en ese proceso, sin dejarla en ningún lanzador:
   `cd walking-skeleton && AURA_CAMARA_RTSP=rtsp://192.168.20.110:554/0/video0 python3 -m aura_skeleton`.
   La .110 no exige credencial; si alguna vez la exigiera, sería `REQUIERE CREDENCIAL DEL PROPIETARIO`, nunca forzarla.
3. Preguntar «¿qué ves en la cámara?». Debe responder «Puedo mirar: «camara», «local»», sin capturar. Después preguntar
   «¿qué ves en la cámara camara?»: una sola captura y una observación ambiental y efímera (fuente y dimensiones).
4. Comprobar que no queda ningún fichero de imagen, que el audit no contiene la URL ni píxeles y que no se escribió nada
   en la memoria.
5. Cerrar AURA. La variable desaparece con el proceso.

**Hallazgo de uso, sin corregir hoy:** la superficie de red se llama `"camara"`, y por eso se pide «la cámara camara».
Darle un nombre propio (por ejemplo «sala», que es lo que usan las pruebas y el DP) es una decisión de configuración del
propietario sobre la zona y el propósito del canal.

## 7. Inventario aportado por el propietario (capturas del 2026-10-22) frente a lo observado por AURA

**Fuente:** 7 capturas de pantalla del propietario. Son **pistas de identificación, no pruebas de conexión**. **No se
registran secretos:** la captura de la app de configuración muestra la contraseña de la Wi-Fi del extensor (no se copia;
si la captura salió del control del propietario, conviene cambiarla); tampoco se copian el EID del iPhone ni los números
de serie completos. La observación de AURA es del 2026-10-22 11:25 (ARP pasivo, más un eco ICMP a las IP conocidas).

| Equipo | Lo que dice el propietario | Lo que observa AURA (11:25) | Estado | Interfaz real para AURA | Bloqueo |
|---|---|---|---|---|---|
| Cámara .110 | App «CloudCam», nombre **«habitacion»** (dormitorio), firmware 3.5.1.1108, MAC 88:E6:28:BB:69:C1 | responde; ARP con esa MAC; ONVIF con identidad cuyo sufijo es esa MAC; RTSP 554 abierto | IDENTIFICADO + ACCESIBLE (flujo RTSP H264 confirmado por DESCRIBE, sin captura) | ONVIF/RTSP, ya integrados (`CamaraPyAV`) | ~~zona privada → restringida~~ **CORREGIDO por el CEO el 2026-10-22: la zona es metadato** (acta `decisiones/2026-10-22-acta-camaras-zona-como-metadato.md`); elegible. La captura sigue pendiente de la activación del propietario (§10) |
| Cámara .32 | App de configuración de Wi-Fi: IP 192.168.20.32 en el extensor `Claro_61630E-EXT` | sin respuesta en esta comprobación | DESCUBIERTO en censos previos (ULooka, Espressif, solo nube) | ninguna local conocida | D24 (solo nube) |
| DVR .80 | otra captura: app con serie del tipo XMEye, usuario `admin`, «contraseña nula por defecto» | responde; ARP 00:12:17:a4:aa:fd | presencia confirmada; **NO SE TOCA** | — | marcado «no tocar». **Riesgo para el propietario:** si esa app es el DVR, tiene credenciales por defecto vacías. AURA no las prueba |
| TV sala .29 | — | sin ICMP; **ARP sí** (d0:03:df:8f:eb:92), es decir, en reposo con la red activa; HA: `off` | INTEGRADO (HA samsungtv) | HA | volumen real pendiente con la TV encendida |
| TV .20 | — | sin respuesta | INTEGRADO (HA) | HA | — |
| iPhone | Wi-Fi 30:3B:7C:30:15:EF, BT 30:3B:7C:32:B3:0E, operador Tigo, 128 GB | no visto (iOS usa dirección Wi-Fi privada por red: la MAC de la captura puede no ser la que ve el router) | DESCUBIERTO por el propietario | ninguna integrada | iOS no expone control general; las vías posibles son una app que hable con AURA o la app oficial de Home Assistant (§9) |
| Samsung A12 (SM-A127M) | IPv4 .200 en el momento de la captura, MAC del teléfono 0C:02:BD:08:63:18, batería al 2 % | .200 sin respuesta | DESCUBIERTO por el propietario | ninguna integrada | Android: app de HA o app propia (§9) |
| Samsung (modelo NO identificado) | IPv4 .94, MAC E4:92:82:54:71:89, BT E4:92:82:54:71:88 | sin respuesta en esta comprobación | DESCUBIERTO; **modelo desconocido** (no aparece en la captura) | — | no confundir con el A12: MAC e IP distintas |
| Garmin Instinct 2 Camo | software 17.22, BLE/ANT 1.04 | no aplica por IP (es BLE) | DESCUBIERTO por el propietario | vía oficial: Garmin Connect (nube, D24); vía local: puente BLE en un teléfono (p. ej. Gadgetbridge en Android) | D24 (nube); **datos de salud**: privacidad, decisión del CEO; Bluetooth bloqueado por software en HC-1 |
| PS5 | — | 0 respuestas DDP hoy | sin evidencia actual | DDP local (estado: encendida/en reposo); el juego en curso solo por PSN | D24 (PSN) |

## 8. Cámara .110: identificación técnica completa (2026-10-22, 12:xx) y frontera de privacidad

- `[EJEC]` La identifican tres evidencias independientes, sin credenciales y sin tocar ninguna imagen:
  1. WS-Discovery con una identidad ONVIF cuyo sufijo es su MAC (88e628bb69c1);
  2. ARP con esa misma MAC;
  3. `GetDeviceInformation` ONVIF en la MISMA IP: **EYEPLUS / EYEPLUS_DEV / firmware 3.5.1.1108**, igual que la
     captura de la app del propietario.
- El inventario de AURA la registra como cámara, con fabricante y modelo, y sin conflicto.
- **RESUELTO el 2026-10-22 (acta «zona como metadato», ver §10):** lo que sigue es histórico.
- **Frontera:** es un DORMITORIO («habitacion»). La composición la registraría como zona «interior» (valor inventado), y
  existe una autorización del 28-09 dada sin saberlo. Pendiente del CEO: `DECISION-REQUERIDA-ZONA-CAMARA-110-DORMITORIO.md`.
  Hasta entonces, **sin captura**.

## 9. Teléfonos y reloj: vías reales de integración (propuesta; nada implementado ni instalado)

| Objetivo | Vía local y legítima | Requiere | Estado |
|---|---|---|---|
| Hablar con AURA desde el teléfono, recibir respuestas y avisos | **App oficial de Home Assistant** (Companion), conectada al HA local; avisos por `notify.mobile_app_*`; sensores (batería, red) como entidades | Que el propietario instale la app y la vincule al HA; acceso a la LAN, o una vía remota, que es una decisión aparte | `[HIPO]` no instalada; HA ya existe |
| Voz del teléfono hacia AURA | Asistente de la app de HA, o una app o página propia de AURA en la LAN | Un DP propio (superficie de entrada de voz nueva; opción C para actuar) | concepto |
| Android (A12, el .94) | Lo anterior; en Android, más permisos para sensores | Permisos que concede el propietario en el teléfono | `[HIPO]` |
| iPhone | Lo mismo con la app de HA para iOS. **iOS no expone control general del sistema**: solo lo que hace la app | — | `[HIPO]` |
| Garmin Instinct 2 | Vía oficial: Garmin Connect (**nube**, excluida por D24). Vía local: un puente BLE en un teléfono Android (p. ej. Gadgetbridge, de código abierto) | **Decisión de privacidad**: son datos de salud; además, el puente afecta al emparejamiento con Garmin Connect | bloqueado: CEO (privacidad + D24) |

**Ninguna de estas vías se ha probado.** El siguiente paso con más valor es que el propietario instale la app de Home
Assistant en un teléfono. Con eso, AURA podría enviar avisos verificables, que es una entidad nueva en HA, y leer la batería
del teléfono como estado observado.


## 10. Rectificación del CEO (2026-10-22, tarde): todas las cámaras son integrables; la zona es metadato

- Acta: `decisiones/2026-10-22-acta-camaras-zona-como-metadato.md`. Resuelve `DECISION-REQUERIDA-ZONA-CAMARA-110-DORMITORIO.md`
  y deja sin efecto la retirada del §6.2 y la «restricción» del §7/§8.
- `[EJEC]` La .110 sigue en 192.168.20.110 con la MAC del censo. RTSP `OPTIONS` y `DESCRIBE` en `rtsp://192.168.20.110:554/0/video0`
  responden 200 OK **sin pedir credencial**, con UNA pista de **vídeo H264/90000**. Este SDP no anuncia audio, así que el
  audio NO se da por disponible. **No se capturó ningún fotograma** (sin `SETUP` ni `PLAY`).
- **Procedimiento vigente para la primera captura** (activación del propietario, mecanismo aprobado; observación efímera,
  sin identificar personas):
  ```
  cd walking-skeleton && AURA_CAMARA_RTSP=rtsp://192.168.20.110:554/0/video0 \
      AURA_CAMARA_NOMBRE=habitacion AURA_CAMARA_ZONA=dormitorio python3 -m aura_skeleton
  ```
  Después: «¿qué ves en la cámara?» enumera las cámaras que puede intentar mirar, y «¿qué ves en la cámara habitacion?»
  hace una captura y una observación ambiental. La zona «dormitorio» es solo una etiqueta: no concede ni quita nada.

## 11. Verificación física real (2026-10-22, 18:55-18:58)

Detalle y evidencia en `evidencia-tv-real-2026-10-22/RESULTADO.md`.

| Equipo | Lectura | Acción | Resultado |
|---|---|---|---|
| TV de la sala (.29, `media_player.tv_sala_fmilia_medina_un43ru7100fxza`) | HA `off` → `on` | **una** orden «enciende la tele de la sala» por AURA | **PHYSICAL_EFFECT_VERIFIED por estado de HA** (10,6 s; sin inspección visual) |
| TV 55" (.20, `media_player.samsung_6_series_55_un55ku6000`) | HA `on`, volumen 0,4, sin silencio | ninguna | no se tocó |
| PS5 (.36) | DDP `200 Ok`, `host-type: PS5` (despierta) | ninguna (solo `SRCH`) | AURA identifica la consola, pero **no guarda** despierta/reposo (`observacion_ddp`); sin integración en HA |

**Actualización (2026-10-22, 19:45):** AURA conserva ya el estado operativo DDP de la PS5. Distingue despierta y en
reposo, con la hora de lectura; sin lectura, el estado es desconocido; «apagada» nunca. Solo observación. **En reposo
no se ha observado en real**, solo con respuestas simuladas. Ver `../investigacion-externa/IE-005-ps5-mqtt.md`.
