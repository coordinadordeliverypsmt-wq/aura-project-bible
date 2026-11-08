---
id: IE-019
titulo: rosteleset/Simple-DVR — servidor de grabación HLS (Node.js + ffmpeg)
fuente: https://github.com/rosteleset/Simple-DVR
rama-revision: main @ último push 2026-07-07 (SHA no capturado)
fecha-revision: 2026-10-22
licencia: GPL-3.0 (SPDX, API de GitHub) — no copiar código a AURA
area: camaras-moviles
estado: investigado
cobertura: LEÍDO (remoto, resumido): metadatos, árbol (12 ficheros), README.md, server.js. NO LEÍDO: cleanup-worker.js, config.example.json, INSTALL*.md, WEBRTC-SRS-HOWTO*.md, nginx_server.include.
relacionadas: [IE-006, IE-020]
---
## Qué se examinó (rutas y símbolos)
`server.js` (rutas HTTP, arranque de ffmpeg), `README.md`, árbol.

## Patrones relevantes
- **Es un SERVIDOR de grabación, no un cliente** [README+CÓDIGO]: un proceso Node lanza un ffmpeg por cámara, graba segmentos fMP4 en disco
  (`<cámara>/AAAA-MM-DD/HH/*.m4s`) y sirve listas HLS en vivo y de archivo, exporta MP4 por rango y miniaturas de un minuto.
  Entrada: URL/ruta de origen por cámara (RTSP admitido; otros no listados). Salida: HLS; WebRTC no es nativo (se delega a SRS + nginx con push RTMP opcional) [README].
- Retención por cámara (días) y tarea de limpieza periódica [README].
- Ffmpeg se lanza con vector de argumentos, sin shell [CÓDIGO]; aun así acepta opciones libres desde la configuración [CÓDIGO].

## Límites, riesgos y dependencias
Observados en `server.js` (resumen de WebFetch) [CÓDIGO]: ninguna autenticación en ninguna ruta; escucha en todas las interfaces, HTTP sin TLS;
nombre de cámara sin validar en la mayoría de rutas (riesgo de recorrido de rutas); la ruta de archivo lanza un ffmpeg por petición sin límite
(riesgo de denegación de servicio); manejadores globales que apagan el servicio ante cualquier error. Es un contraejemplo de seguridad.
Dependencias: Node.js, ffmpeg, express.

## Comparación con AURA
AURA observa de forma efímera por decisión (misma conclusión que IE-006): `core/percepcion.py` no persiste vídeo; una grabadora contradice la política
(`core/politica_superficie.py`). No sirve para el DVR de .80: RTSP está deshabilitado y el SDP responde vacío, así que ni siquiera tendría entrada.
`adapters/camara_rtsp.py` ya cubre la lectura puntual cuando RTSP está habilitado.

## Decisión
**DESCARTAR** (como componente). Referencia mínima para listas de verificación de cualquier futuro servidor de medios: autenticación, validación de nombres, límites.

## Validación mínima
Ninguna. Nada que probar en aislamiento.

## Licencia y precauciones
GPL-3.0: no incorporar. No ejecutar. No exponer nada parecido en la red doméstica.
