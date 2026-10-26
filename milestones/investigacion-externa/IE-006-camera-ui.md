---
id: IE-006
titulo: camera.ui — plataforma de videovigilancia autohospedada
fuente: https://github.com/cameraui/camera.ui
rama-revision: master @ 451090c (2026-10-22, «release(server): v2.4.0»)
fecha-revision: 2026-10-22
licencia: MIT (declarada por la API de GitHub y el README; funciones con * requieren suscripción)
area: camaras-moviles
estado: investigado
cobertura: LEÍDO (remoto, solo metadatos y texto) — README, listado de la raíz, SECURITY.md, API de repo y último commit. NO leído — server/, service/, shared/, ui/, externals/, docs.cameraui.com, AI_POLICY.md, código de plugins, formato de grabación, protocolos de streaming. Nivel de inspección: README + metadatos (bajo). No se clonó ni ejecutó nada.
relacionadas: [IE-007, IE-008]
---
## Qué se examinó (rutas y símbolos)
- `README.md`, raíz del repo (carpetas `server`, `service`, `shared`, `ui`, `externals`, `scripts`), `SECURITY.md`, metadatos de la API (licencia, rama, `pushed_at`).
- No se abrió ningún fichero de código; no hay símbolos citables.

## Patrones relevantes
- [README] «Self-hosted platform for your security cameras»; «no mandatory cloud, your footage stays with you». Instalación: app de escritorio, Docker, Proxmox, Linux bare-metal, apps móviles.
- [README] Núcleo «free and open source». Con asterisco (suscripción): grabación 24/7, búsqueda semántica, notificaciones push. Es decir, lo abierto es visión en vivo, detección «on-device», integración domótica y ecosistema de plugins; **grabación continua, búsqueda semántica y push son de pago**.
- [README] Detección de IA «on-device» (no se verificó el motor ni los modelos).
- [README] «Extensible plugin ecosystem»; [INFER] por la estructura `server/service/shared/ui` + `requirements.txt` + `pyrightconfig.json` hay un servicio Python además del servidor TypeScript. El README no describe la arquitectura.
- [README] SECURITY.md solo define cómo reportar (correo o aviso privado de GitHub); no documenta modelo de autenticación ni aislamiento de plugins. Cualquier afirmación sobre ambos queda sin evidencia.
- No se pudo determinar: protocolos de streaming, formato/retención de grabaciones, canal de notificaciones.

## Límites, riesgos y dependencias
- Es un NVR completo; AURA no despliega otro NVR (decisión del encargo). Adoptarlo como dependencia traería servidor, UI, plugins y un modelo de suscripción.
- [README] Parte de la funcionalidad útil para el hogar (push, grabación 24/7) es de suscripción: dependencia comercial, aunque el núcleo sea MIT.
- Mantenimiento: activo (push el día de la revisión; v2.4.0).
- [INFER] Un ecosistema de plugins de terceros dentro del mismo proceso sería superficie de ataque; no verificado.

## Comparación con AURA
| Fuente@rev | Evidencia | Problema | Relevancia | Estado AURA (ruta) | Brecha | Riesgo/coste | Licencia | Decisión | Validación |
|---|---|---|---|---|---|---|---|---|---|
| camera.ui@451090c | [README] separación abierto/suscripción; on-device AI; plugins | Videovigilancia autohospedada con IA local | Baja: AURA no es NVR; ve bajo demanda | `aura_skeleton/adapters/camara_rtsp.py:CamaraRTSP` (captura bajo demanda); `composicion.py:712` (`AURA_CAMARA_RTSP` del propietario); `core/politica_superficie.py:Superficie` (deny-by-default); `core/percepcion.py` (observación efímera, sin identificar, nunca cámara→acción) | Ninguna funcional. AURA elige no grabar ni indexar: la ausencia de grabación continua es decisión (Decisión B), no carencia | Alto si se integrara (servicio extra, suscripción) | MIT | Descartar como dependencia; no hay patrón nuevo con evidencia | N/A |
- [INFER] Si el propietario ya usa camera.ui, bastaría que exponga RTSP y AURA lo consuma vía `AURA_CAMARA_RTSP`; no requiere código nuevo. No verificado que camera.ui re-emita RTSP.

## Decisión
Descartar como adopción; sin patrón que AURA no tenga. Documentar la separación abierto/suscripción como criterio de evaluación de futuras fuentes (el patrón «núcleo local + extras en la nube de pago» es lo que AURA debe evitar, D24).

## Validación mínima
Ninguna requerida. Si se quisiera interoperar: con una URL RTSP de prueba local, comprobar que `CamaraRTSP` captura un fotograma efímero y que no queda fichero en disco (prueba ya existente en la línea de percepción; no ejecutada por esta investigación).

## Licencia y precauciones
MIT. No copiar código. Funciones con * son de suscripción. Revisión solo de README/metadatos: no inferir más de lo escrito aquí.
