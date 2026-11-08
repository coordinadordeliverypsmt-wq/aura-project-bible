---
id: IE-007
titulo: android-remote-control-mcp — servidor MCP que corre en el móvil Android
fuente: https://github.com/danielealbano/android-remote-control-mcp
rama-revision: main @ 379ba18 (2026-10-19, merge PR #194 «Relicense to GPL-3.0-or-later»)
fecha-revision: 2026-10-22
licencia: GPL-3.0-or-later con permiso adicional §7 (Google Play services); el campo de la API dice NOASSERTION. Copyleft fuerte
area: camaras-moviles
estado: investigado
cobertura: LEÍDO (remoto) — README completo, docs/MCP_TOOLS.md (primeros 100000 de 105896 caracteres), API de repo y último commit. NO leído — código Kotlin (app/), módulo privacy/, channel-plugin/, e2e-tests/, docs de seguridad, THIRD_PARTY_LICENSES. Nivel de inspección: README + referencia de herramientas (medio-bajo). No se clonó ni ejecutó nada.
relacionadas: [IE-008, IE-006]
---
## Qué se examinó (rutas y símbolos)
- `README.md`, `docs/MCP_TOOLS.md`; estructura raíz (`app`, `privacy`, `privacy-benchmark`, `channel-plugin`, `e2e-tests`, `docs`).

## Patrones relevantes
- [README] App Android que aloja un servidor MCP (Ktor/Netty, Streamable HTTP en `/mcp`, solo JSON). «57 herramientas en 14 categorías»: introspección de pantalla, acciones de sistema, táctiles, gestos, nodos, texto, utilidades, ficheros, apps, cámara, intents, notificaciones, ubicación, compartir. Prefijo `android_` (con slug de dispositivo).
- [README] Introspección compacta (`get_screen_state`) con árbol de accesibilidad + captura anotada opcional; requiere el Servicio de Accesibilidad (acceso especial).
- [README] Permisos en capas: (1) permisos Android normales/en ejecución (CAMERA, RECORD_AUDIO, ubicación, medios; opcionales, solo desactivan lo dependiente); (2) conmutadores por herramienta y por parámetro (`tool_permissions` con `disabled_tools` / `disabled_params`); (3) ubicaciones de almacenamiento autorizadas por el usuario (SAF), con `allow_write` / `allow_delete` por ubicación [MCP_TOOLS].
- [README] Autenticación: token Bearer estático (UUID) y OAuth 2.1 propio con aprobación en el dispositivo (código de 2 dígitos); ambos activos por defecto; sin autenticación solo si se apagan ambos, con aviso y confirmación; vaciar el token con Bearer activo devuelve 401 (falla cerrado).
- [README] Exposición: enlaza a `127.0.0.1:8080` por defecto; `0.0.0.0` expone a la red local; HTTPS opcional (autofirmado o .p12); túneles Cloudflare/ngrok opcionales (desactivados por defecto); configuración sin interfaz solo por ADB (`android.permission.DUMP`).
- [README] Ficheros: límite 50 MB (1–500), descargas HTTP y HTTPS no verificado desactivadas por defecto. Cámara: foto 1920x1080 base64, vídeo máx. 30 s [MCP_TOOLS].
- [README] Registros: visor en la app de llamadas MCP y eventos de túnel; sin información de retención/formato.
- [README] «Privacy Mode»: oculta datos personales en el dispositivo con reglas + NER local; «mejor esfuerzo, no una garantía» (nombres: 0,8 % en su propio benchmark).
- [MCP_TOOLS] Contenido derivado del dispositivo se antepone con aviso de «contenido no confiable» (defensa contra inyección de prompts).
- [MCP_TOOLS] Herramientas de riesgo alto: `send_intent` (actividades, broadcasts, servicios, flags de permisos), `write_file`/`delete_file`, `notification_reply` (envía mensajes como el usuario), `notification_action`, `get_clipboard`, `take_camera_photo`/`save_camera_video` (audio por defecto), `get_location`, `download_from_url`.
- [MCP_TOOLS] **Ninguna herramienta exige confirmación humana por llamada**; la puerta principal es el token Bearer. Es la brecha de diseño más relevante para AURA (ADR-0003 exige confirmación para lista roja).
- El README no cita una categoría «accesibilidad» propia, pero el Servicio de Accesibilidad es requisito de las herramientas de UI.

## Límites, riesgos y dependencias
- [README] Declarado «solo para investigación y educación, tal cual».
- Control total del móvil con un único secreto estático; la exposición por túnel público de Internet es opuesta a local-first (D24).
- Dependencia de un cliente MCP; Accesibilidad + Notification Listener son poderes muy amplios en Android.
- GPL-3.0-or-later: no se puede copiar código a AURA sin licenciar AURA igual; solo se toman ideas/contratos.
- Mantenimiento: muy activo (relicenciado hace 3 días).

## Comparación con AURA
| Fuente@rev | Evidencia | Problema | Relevancia | Estado AURA (ruta) | Brecha | Riesgo/coste | Licencia | Decisión | Validación |
|---|---|---|---|---|---|---|---|---|---|
| android-remote-control-mcp@379ba18 | [README][MCP_TOOLS] 57 tools, permisos por herramienta/parámetro/ubicación, Bearer+OAuth, loopback por defecto | Controlar un móvil Android por MCP con autorización granular | Media como lista de CONTROLES, nula como código | `tests/unit/test_entorno.py:70` (teléfono = dispositivo, nunca persona); `tests/unit/test_notificaciones.py:56` (Android/NAS fuera hasta R2); `milestones/mapa-maestro/capacidades.json` («Teléfono/Android/wearables», nivel bajo); `core/politica_superficie.py:Superficie` (deny-by-default por flags) | AURA no tiene capacidad móvil: brecha deliberada (D23). Un móvil se modela como Superficie con flags; falta un tipo «actuar sobre móvil» no definido | Alto si se construyera (Accesibilidad = lectura total de pantalla) | GPL-3.0+ | Adaptar solo ideas: ver CONTROLES. No construir ahora | Ver validación |

### CONTROLES mínimos que AURA debería exigir antes de cualquier capacidad móvil (derivados de IE-007 e IE-008) [PROPUESTA]
1. **Sin capacidad por defecto**: móvil desactivado hasta acta del CEO (D23) y propietario explícito; deny-by-default (patrón `Superficie`).
2. **Dispositivo autorizado y emparejado explícitamente** por el propietario (no descubrimiento automático); identidad del dispositivo ≠ persona.
3. **Capacidades nombradas por resultado** (p. ej. `leer_estado_de_pantalla`, no `tap`), registradas y por el Motor Único con permisos y dry-run; nada de ejecución arbitraria ni `send_intent`/shell/`adb` crudo.
4. **Permisos por capacidad y por parámetro**, revocables, con lista blanca (no lista negra); todo lo no declarado, denegado.
5. **Clasificación rojo/verde por acción**: leer pantalla, portapapeles, notificaciones, ubicación, cámara/micrófono, enviar mensajes, borrar/escribir ficheros, instalar/lanzar apps = lista roja con **confirmación humana en cada llamada** (IE-007 no la tiene).
6. **Solo local**: enlace a loopback/red local, sin túneles ni nube; TLS con certificado fijado si sale del equipo; sin servicio abierto.
7. **Autenticación con credencial rotable y por dispositivo**, falla cerrada si falta; sin modo «sin autenticación».
8. **Datos del móvil = no confiables**: etiquetar el contenido (anti-inyección) y no reinterpretarlo como instrucciones (INV-7); nunca móvil→acción sin plan aprobado.
9. **Efímero y mínimo**: capturas/pantallas/notificaciones sin persistir ni a logs ni a memoria (como `percepcion.py`); sin identificar personas por lo que se ve.
10. **Límites duros**: tamaño de fichero, duración de grabación, tasa de llamadas, tiempo de sesión; ficheros solo en ubicaciones autorizadas y separadas lectura/escritura/borrado.
11. **Auditoría**: registro de cada acción (quién, qué, resultado, aprobación) sin contenido sensible; botón de parada inmediata.
12. **Dependencia de versión y licencia vetadas** (IE-008: soporte atado a WDA/iOS; GPL): comprobar compatibilidad al arrancar y fallar de forma explícita en lugar de fingir (INV-9).

## Decisión
Investigar más solo si el CEO abre la capacidad móvil; hoy, adoptar únicamente la lista de controles como criterio de aceptación futuro. No copiar exposición remota (túneles, `0.0.0.0`).

## Validación mínima
Candidata (única): una prueba de contrato que fije que **ningún tipo de Superficie móvil/teléfono puede estar autorizado por defecto ni con `actuar=True` sin confirmación**, y que un teléfono jamás se resuelva como persona. Caso de control: construir una Superficie de tipo teléfono con valores por defecto y comprobar `autorizado=False`; mutante: cambiar el valor por defecto a `True` debe hacer fallar la prueba. (No ejecutada; ubicación sugerida junto a `tests/unit/test_entorno.py:70`.)

## Licencia y precauciones
GPL-3.0-or-later: no incorporar código. Sin ejecutar ni instalar. El README declara uso solo investigación; no usar como referencia de seguridad lista para producción.
