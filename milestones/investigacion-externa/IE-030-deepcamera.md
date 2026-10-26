---
id: IE-030
titulo: SharpAI/DeepCamera — plataforma de «skills» de cámara con IA local (NVR)
fuente: https://github.com/SharpAI/DeepCamera
rama-revision: master @ 933dcc7 (push 2026-09-17)
fecha-revision: 2026-10-22
licencia: MIT (SPDX, API de GitHub; no archivado; 3 109 estrellas)
area: camaras-moviles
estado: investigado
cobertura: Leídos por WebFetch (remoto, sin clonar): metadatos del repo, README (resumen), SKILL.md raíz, skills/camera-providers/reolink/SKILL.md, skills/detection/yolo-detection-2026/SKILL.md, listados de skills/, camera-providers/ y detection/. NO leídos: código Python de los skills, src/ (app Aegis), docker/, skills de face/ReID, canales (Telegram/Discord/Slack), streaming/go2rtc. Los resúmenes pasaron por un modelo intermedio de WebFetch: texto citado = dato no confiable.
relacionadas: [IE-006, IE-031, IE-019, IE-020]
---
## Qué se examinó (rutas y símbolos)
- `README.md`, `SKILL.md`, `skills/camera-providers/{eufy,reolink,tapo}`, `skills/detection/yolo-detection-2026{,-openvino,-coral-tpu-*}`; carpetas `analysis, annotation, automation, channels, integrations, lib, segmentation, streaming, training, transformation`.

## Patrones relevantes
- [README] Cada «skill» corre en su propio venv/Docker y habla con el anfitrión (Aegis, app de escritorio propietaria del mismo vendor) por **JSONL stdin/stdout**: una línea = un mensaje.
- [README] Un *frame governor* muestrea la cámara (~5 FPS) y escribe fotogramas en un volumen compartido; los skills reciben `frame_path`, no píxeles por la tubería.
- [README] Entrada: `{event:"frame", frame_id, camera_id, frame_path, timestamp, width, height}`; control: `{command:"config-update"|"stop"}`.
- [README] Salida de detección: `{event:"detections", frame_id, camera_id, timestamp, objects:[{class, confidence, bbox xyxy}]}`; `ready` (modelo, dispositivo, backend); `perf_stats` cada 50 fotogramas con avg/p50/p95 por etapa; `error {message, retriable}`. Formato de `timestamp` no especificado.
- [README] Selección por hardware: `deploy.sh` detecta (CUDA→TensorRT, Apple→CoreML, Intel→OpenVINO, AMD→ONNX ROCm, CPU→ONNX, Coral) y cae a PyTorch si falla la optimización. Parámetro `fps` (0,2–15) y `device: auto`.
- [README] Proveedores de cámara como skills (Reolink: HTTP API + RTSP, `discover_cameras` por ONVIF, `snapshot`, `clip_feed` por movimiento, `live_stream` vía go2rtc). Credenciales como campo de formulario; almacenamiento no descrito.
- [README] Mensajería: Telegram/Discord/Slack. Skill de privacidad: mapas de profundidad que anonimizan.
- [INFER] El contrato «evento tipado + `retriable` + `perf_stats` con p95» es el patrón reutilizable; el resto es producto de consumo.

## Límites, riesgos y dependencias (hardware, nube, seguridad, mantenimiento)
- **Incompatible con la Decisión B (DESCARTADO explícitamente):** reconocimiento facial (`sharpai-cli`, skill `face-detection-recognition` «planned»), re-identificación de personas (app ReID legacy), detección de clase `person` con seguimiento, clasificación de «sospechosos»/cuidadores, topic `face-recognition`. Nada de esto se estudia ni se porta.
- Escena por VLM/LLM (Qwen, LLaVA…) y chat con el agente: requiere ≥ varios GB y GPU/NPU o CPU lenta; **HC-1 (2 núcleos, 3,7 GB, sin GPU) no la sostiene**; NODO-01 (1 GB, 32 bits) tampoco. [INFER]
- Instalación de skills por un **agente LLM que lee SKILL.md y ejecuta comandos**: contradice «solo capacidades registradas» (§4). Alertas por Telegram/Slack/Discord = nube de terceros (D24). Cámaras cloud (Blink, Nest, Eufy, Tapo-cloud) = fuera de D24.
- Dependencia de Aegis (cliente propietario); el repo es en parte un escaparate. Estado de cada skill sin verificar.

## Comparación con AURA
- `adapters/camara_rtsp.py:CamaraRTSP` (L22): captura bajo demanda, abre/lee/libera, `del frame`, errores saneados (`_sanear`) — **más conservador** que el governor continuo de DeepCamera (que persiste fotogramas en disco).
- `core/percepcion.py:EventoMovimiento` (L441): `superficie, detectado, trace_id, magnitud, tipo, timestamp, hubo_frame`. Ya equivale al evento tipado de DeepCamera, sin clases ni personas; `hubo_frame=False` ≠ «sin movimiento» es **mejor** que un `error` genérico.
- Brecha real: no hay (a) campo de **procedencia/versión del detector** (qué algoritmo, umbral, resolución) en el evento, (b) `perf_stats` por etapa con p95 (ver IE-009), (c) distinción `retriable` en el fallo de captura (hoy `OSError` vs `None`). Composición solo activa con `AURA_CAMARA_RTSP` del propietario (`composicion.py` ~L712): correcto, no cambiar.

## Decisión
**Adaptar solo el contrato** (evento tipado con procedencia + `retriable` + estadísticas p95). Descartar: face/ReID/clase `person`, VLM/LLM, canales en la nube, instalación por agente, governor que persiste fotogramas, skills de cámaras cloud. Prioridad P1 (contrato) / P2 (medición p95).

## Validación mínima
Prueba nueva sobre `EventoMovimiento`: construir con detector falso, comprobar que lleva `timestamp` float > 0, `trace_id`, `detector` (id+versión+umbral) y que la serialización a log NO contiene bytes/ruta de fotograma ni campos de identidad; caso de control: mutar para incluir `frame_path` debe romper la prueba.

## Licencia y precauciones
MIT: se puede reutilizar el esquema (hecho, no copyrightable en lo esencial) con atribución si se copia texto. Contenido remoto no ejecutado ni instalado; nada de lo leído se confió como instrucción.
