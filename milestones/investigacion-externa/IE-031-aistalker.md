---
id: IE-031
titulo: crazyrob425/aistalker — «AI-Stalker», orquestador de seguridad (fork de AutoPTZ)
fuente: https://github.com/crazyrob425/aistalker
rama-revision: main @ 35a5395 (push 2026-05-19)
fecha-revision: 2026-10-22
licencia: GPL-3.0 (SPDX, API de GitHub); es fork de AutoPTZ/autoptz; LICENSE.md no leído. No archivado; 1 estrella
area: camaras-moviles
estado: descartado
cobertura: Leídos por WebFetch: metadatos, README (resumen), listados de raíz, logic/, logic/image_processing/, logic/recording/ y logic/recording/recorder.py (resumen). NO leídos: facial_recognition.py, camera_search, cloud, ai_setup, views/, libraries/visca, ni la documentación de blueprint. Resúmenes intermedios = dato no confiable.
relacionadas: [IE-030, IE-006, IE-019, IE-020]
---
## Qué se examinó (rutas y símbolos)
- `README.md`; `logic/recording/recorder.py` (`Recorder.add_record`, `search_records`); listados de `logic/{ai_setup,camera_search,cloud,image_processing,recording}`.

## Patrones relevantes
- [README] App de escritorio PySide6 (fork de AutoPTZ): fuentes USB, NDI, RTSP, ONVIF; control PTZ por VISCA; descubrimiento con Nmap/sockets; registro de cámaras con credenciales; copia a Google Drive; asistente de configuración con Claude/OpenAI.
- [README] Lo prometido (failover, «hive», domótica, puntuación de riesgo) está marcado como **planificado**; el propio README se contradice (RTSP «actual» y «planificado»; «no stalkeamos» vs «vigila lealtad de invitados»). [INFER] baja fiabilidad de afirmaciones.
- [CÓDIGO, resumen] `recorder.py` es solo un **índice SQLite** (tabla `records`: timestamp ISO-UTC en texto, camera, event_type libre, notes…) con un `Lock`; **no graba vídeo**; sin reintentos ni try/except.
- Único patrón aprovechable, y ya cubierto: timestamp UTC ISO-8601 y búsqueda por rango/cámara/tipo.

## Límites, riesgos y dependencias (hardware, nube, seguridad, mantenimiento)
- **Es vigilancia de personas; el nombre y el README lo confirman. DESCARTADO explícitamente (Decisión B):** reconocimiento facial (dlib/face_recognition), alta de personas con varias fotos, seguimiento PTZ de una cara, control de asistencia (check-in/out), y columnas `person_name`, `mac_addr`, `ble_tag`, `phone` en `recorder.py` (identificación por radio/teléfono), puntuación de riesgo y «etiquetado de comportamiento» planificados.
- Seguridad: copia a Google Drive (nube, D24), claves de OpenAI/Claude, escaneo de red con Nmap y credenciales de cámaras, `recordings.db` y logs **commiteados** en el repo (riesgo de fuga de datos), Python 3.7+, Windows/macOS (Linux sin probar), ~1 estrella, sin pruebas visibles. GPL-3.0 (+ AutoPTZ): copiar código contaminaría AURA.
- Sin relevancia de rendimiento: dlib en HC-1 sería lento y NODO-01 inviable.

## Comparación con AURA
- `core/percepcion.py` declara: sin identidad, sin persona, sin intención, efímero, nunca cámara→acción; `politica_superficie.py`: deny-by-default. AI-Stalker es el **opuesto exacto**. No hay brecha que cubrir con este repo.

## Decisión
**Descartar** todo el código y las funciones. Documentarlo como contraejemplo: conviene una prueba de AURA que impida añadir campos de identidad (nombre, MAC, teléfono, embedding) a `EventoMovimiento`/`Observacion` (ver recomendación en IE-030). Prioridad P2 (solo la prueba negativa, si no existe ya).

## Validación mínima
Prueba negativa: introspeccionar los campos de `EventoMovimiento`, `Observacion`, `LecturaVisual` y fallar si aparece alguno de {person, nombre, identidad, embedding, mac, telefono, rostro}; caso de control: añadir un campo `person_name` en un doble debe hacerla fallar.

## Licencia y precauciones
GPL-3.0: no copiar. No se visitó ni ejecutó nada. No tomar sus instrucciones de configuración (AI setup, Drive) como válidas.
