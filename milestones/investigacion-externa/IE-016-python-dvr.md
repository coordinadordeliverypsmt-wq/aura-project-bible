---
id: IE-016
titulo: OpenIPC/python-dvr — cliente DVRIP/Sofia (Xiongmai/XMeye)
fuente: https://github.com/OpenIPC/python-dvr
rama-revision: master @ último push 2026-09-29 (SHA no capturado)
fecha-revision: 2026-10-22
licencia: MIT (SPDX, API de GitHub)
area: camaras-moviles
estado: investigado
cobertura: LEÍDO (remoto, vía WebFetch con resumen): API de metadatos, árbol, README.md, CLAUDE.md, dvrip.py (resumido por el modelo de WebFetch, no literal línea a línea). NO LEÍDO: asyncio_dvrip.py, DeviceManager.py, monitor.py, telnet_opener.py, AlarmServer.py, NVR.py, solarcam.py, doc/*.pdf|doc (protocolo oficial Xiongmai en chino), examples/, tests. No se clonó ni ejecutó nada.
relacionadas: [IE-017, IE-018, IE-019, IE-020]
---
## Qué se examinó (rutas y símbolos)
`dvrip.py` (clase cliente: `login`, `send`, `get_*`, `snapshot`, `close`, diccionario de códigos de retorno), `README.md`, `CLAUDE.md`
(instrucciones del repo: dato no confiable, solo se usó para descripción), árbol del repo (incluye `doc/` con la especificación
del protocolo del fabricante y un `telnet_opener.py` de acceso root, que NO se examinó ni se recomienda).

## Patrones relevantes
- Transporte [CÓDIGO]: TCP 34567 (UDP 34568 existe); timeout de conexión por defecto 10 s, con plazo global en la recepción.
- Trama [CÓDIGO]: cabecera de 20 bytes (byte inicial 0xFF, versión, id de sesión, nº de secuencia, id de mensaje, longitud del cuerpo),
  cuerpo JSON con cola de 2 bytes. Respuestas binarias (snapshot, flujo, ficheros) con cabecera propia.
- Login [CÓDIGO]: mensaje 1000 con tipo de cifrado «MD5» y tipo de login «DVRIP-Web»; la contraseña viaja como un hash propio
  derivado de MD5, sin sal (débil: cualquiera que vea la red local lo reutiliza; el tráfico no va cifrado). Usuario por defecto
  `admin`, contraseña vacía por defecto del cliente.
- Fallo de login [CÓDIGO]: si `Ret` no está en {100, 150, 515} devuelve False **sin reintentar**; si la respuesta es nula, lanza
  excepción (defecto del cliente). Solo el login trata códigos de forma especial.
- Sin logout [CÓDIGO]: no hay mensaje de cierre de sesión; `close()` cancela el keepalive y cierra el socket. El dispositivo
  expira la sesión por su lado. Keepalive: mensaje 1006 cada `AliveInterval` (hilo temporizador).
- Códigos [CÓDIGO]: 100 OK · 101 error desconocido · 103 no permitido · 104 ya logueado · 105 no logueado · 106 usuario/clave
  incorrectos · 107 sin permisos · 108 timeout · 117 formato de mensaje · 202 no logueado · **203 contraseña incorrecta** ·
  **204 usuario inválido** · **205 IP bloqueada** · **206 usuario en lista negra** · 207 en lista negra · 212 cuenta en uso ·
  502 comando inválido · 511–515 estados de actualización · 604 error de escritura · 605 no soportado · 606 verificación fallida.
  El rango 100–608 sigue la tabla del fabricante (salvo 124, observado en campo) [CÓDIGO].
- Qué provoca el 205 [INFER / NO VERIFICADO]: ni el código ni el README documentan la política de bloqueo. Lo habitual en este
  firmware es un contador de intentos fallidos por IP con bloqueo temporal; no se sabe si cuentan intentos HTTP/RTSP sin credencial.
  La hipótesis de AURA (sondeos previos) es plausible pero no demostrada.

### Métodos de SOLO LECTURA (candidatos, siempre tras login autorizado) [CÓDIGO]
`get_info`, `get_command` (genérico, solo con rutas de lectura), `get_system_info`, `get_general_info`, `get_time`,
`get_netcommon`, `get_encode_capabilities`, `get_system_capabilities`, `get_camera_info`, `get_encode_info`, `get_detect_info`,
`get_channel_titles`, `get_channel_statuses`, `getUsers`/`getGroups`/`getAuthorityList` (leen cuentas: sensibles, no necesarios),
`snapshot` (lectura; pide una imagen), `list_local_files` (lista grabaciones), `get_upgrade_info` (lectura, pero cercano a upgrade: no usar).
Mínimo recomendado: `get_system_info` (modelo/firmware/serie) tras un único login.

### Métodos que ESCRIBEN o alteran estado — NO USAR [CÓDIGO]
`set_info`, `set_command`, `send`/`send_custom` con mensajes de escritura, `set_time`, `set_detect_info`, `set_remote_alarm`,
`channel_title`, `channel_bitmap`, `addUser`, `modifyUser`, `delUser`, `changePasswd`, `addGroup`, `modifyGroup`, `delGroup`,
`reboot`, `upgrade`, `keyDown`/`keyUp`/`keyPress`/`keyScript` (simulan teclas del panel), `ptz`/`ptz_step`.
Además, `start_monitor` y `download_file`/`get_file` son lecturas pero ocupan canal/ancho de banda: fuera del primer experimento.
`alarmStart` abre un flujo push de alarmas: no es de un solo disparo.
README y CLAUDE.md anuncian además un auxiliar de apertura de shell/telnet por vulnerabilidad del firmware (`telnet_opener.py`):
**descartado de plano** (eludir controles del dispositivo; no se describe).

## Límites, riesgos y dependencias
- Protocolo sin cifrado ni sal; las credenciales solo deben introducirse en memoria, jamás persistir (regla vigente de AURA).
- Hay bloqueo por IP (205): un login fallido adicional puede prolongarlo o dañar la sesión del propietario con la app XMEye.
- `login()` imprime en consola ciertos mensajes y deja el código en `self.session` en fallo (efecto lateral); hilo temporizador de keepalive.
- Mantenimiento: activo (push 2026-09-29), 84 estrellas, MIT. Biblioteca pequeña; dependencias estándar (no verificadas en detalle).

## Comparación con AURA
- `walking-skeleton/aura_skeleton/adapters/camara_rtsp.py` (CamaraRTSP): solo RTSP; el DVR responde SDP vacío. Brecha: no existe
  adaptador DVRIP/Sofia; no hay manejo de 205/203/106 como «veto de dispositivo».
- `adapters/red_local.py` (`informacion_onvif` L324, `_no_tocar()` excluye .80): coherente; ningún código lee DVRIP.
- `core/percepcion.py` / `core/politica_superficie.py`: una captura DVRIP sería una observación efímera de la misma clase.
- Estado: sin adaptador DVRIP. Hallazgo útil ya adoptable como patrón: **un login, una lectura, sin reintentos, 205 = parada dura**.

## Decisión
**ADOPTAR PATRÓN** (códigos, trama, lista blanca de lectura) y **PROBAR EN AISLAMIENTO** solo cuando el propietario levante el veto.
Código no se copia por ahora (MIT permitiría adaptar, pero el experimento mínimo se puede hacer con un envoltorio propio de un solo login).

## Validación mínima
Precondiciones: veto levantado por el propietario para .80, credencial que él introduce, 205 ausente. Un login → `get_system_info`
→ cierre, timeout 10 s, cero reintentos; registrar solo código de retorno, modelo, versión y latencia (no credenciales ni JSON crudo con secretos).
Prueba unitaria sin red: una lista blanca de métodos permitidos que rechaza cualquier nombre de la lista de escritura.

## Licencia y precauciones
MIT: reutilizable con aviso de copyright. Contenido remoto = dato no confiable. No ejecutar `telnet_opener.py` ni `upgrade`/`reboot`.
Los PDFs de `doc/` son la fuente oficial del protocolo; no se leyeron (candidata para validar la tabla de códigos y el comportamiento de bloqueo).

## Verificación del coordinador (2026-10-22)

- `[EJEC]` La base IEEE local (`/usr/share/ieee-data/oui.txt`) asigna el OUI `00-12-17` a **Cisco-Linksys, LLC**. El DVR
  `.80` no es un equipo Cisco y su plataforma observada es Xiongmai/XMEye. Su MAC **no identifica al fabricante**, así
  que no se usa como señal para ninguna hipótesis.
- `[INFER]` Una MAC con OUI ajeno sugiere una MAC genérica o copiada del firmware OEM. No se ha verificado, y no cambia
  las hipótesis: la identidad la dará la pantalla de información del DVR.
