---
id: IE-020
titulo: Breakthrough/DVR-Scan — detección de movimiento en vídeo grabado
fuente: https://github.com/Breakthrough/DVR-Scan
rama-revision: main @ último push 2026-10-17 (SHA no capturado)
fecha-revision: 2026-10-22
licencia: BSD-2-Clause (pyproject y LICENSE; la API de GitHub devuelve NOASSERTION/«Other» por el formato del fichero). Terceros (OpenCV, FFmpeg, CUDA, NumPy) en LICENSE-THIRDPARTY.
area: camaras-moviles
estado: investigado
cobertura: LEÍDO (remoto, resumido): metadatos, árbol, README.md, LICENSE, pyproject.toml, dvr_scan/subtractor.py, dvr_scan/scanner.py, dvr_scan/report.py. NO LEÍDO: controller.py, detector.py, cli.py, config.py, region.py, encoder.py, video_input.py, docs HTML (valores por defecto de threshold/min-event no confirmados).
relacionadas: [IE-006, IE-019]
---
## Qué se examinó (rutas y símbolos)
`subtractor.py` (MOG2, CNT, MOG2 CUDA), `scanner.py` (`MotionScanner.scan()`, máquina de estados de eventos), `report.py` (CSV/JSON), `pyproject.toml`.

## Patrones relevantes
- Algoritmo [CÓDIGO]: sustracción de fondo sobre fotograma en gris. MOG2 de OpenCV por defecto (historial 500, umbral de varianza 16.0, sombras
  desactivadas, tasa de aprendizaje automática); variante CNT (requiere el módulo contrib de OpenCV) y variante CUDA (requiere OpenCV con CUDA).
  Filtro morfológico «open» con núcleo impar para quitar ruido; detección sobre imagen reducida (factor de reducción) y fotogramas saltables.
- Parámetros [CÓDIGO]: umbral de puntuación de movimiento, longitud mínima de evento (ventana deslizante donde todas las puntuaciones superan el umbral),
  tiempo previo/posterior al evento, ventana de fusión de eventos, longitud máxima de evento, umbral máximo, área/ancho/alto máximos de la caja de movimiento,
  máximo de eventos, región de interés (README: editor interactivo o puntos por línea de órdenes).
- Salida [CÓDIGO]: lista de eventos con inicio y fin (marcas de tiempo de presentación del propio vídeo, no relojes de pared); CSV (nº, inicio/fin/duración, fotogramas,
  segundos con 6 decimales) y JSON versionado (esquema 1, generador, creado, ficheros de entrada, nº de eventos); miniatura opcional del fotograma de mayor puntuación.
  Recorte de clips opcional (README: modo ffmpeg).
- Hilos [CÓDIGO]: decodificación en un hilo, detección en el principal, codificación en un tercero, colas acotadas de 4.
- Coste de CPU [INFER]: proporcional a fotogramas procesados × resolución reducida; el README no da cifras; no medido. El salto de fotogramas y la reducción lo bajan.
- Dependencias [CÓDIGO]: Python ≥ 3.10, numpy, opencv-python y opencv-contrib-python (< 4.13), scenedetect[pyav], pillow, tqdm, platformdirs, screeninfo, tkinterdnd2 (GUI).

## Límites, riesgos y dependencias
Trabaja sobre archivos de vídeo: exige grabar antes (contradice la observación efímera de AURA) o tener un fichero que el propietario aporte.
Dependencias pesadas para un adaptador del núcleo (OpenCV ×2, PyAV, GUI). Dos paquetes OpenCV a la vez es un conflicto de empaquetado conocido en la práctica [INFER].

## Comparación con AURA
Sin equivalente: AURA no detecta movimiento (`core/percepcion.py` solo guarda observaciones efímeras; `adapters/camara_rtsp.py` captura imágenes puntuales).
El DVR de .80 no entrega vídeo hoy (RTSP deshabilitado). Brecha: ninguna con evidencia de uso real; la capacidad no tiene bloqueo observado repetido
(regla del CEO 2026-08-04: sin evidencia repetida no se desarrolla).

## Decisión
**SOLO REFERENCIA**, con un patrón adoptable si algún día hiciera falta: eventos como intervalos [inicio, fin] con relleno previo/posterior y ventana de fusión, y
umbral mínimo de duración para evitar disparos por ruido. Código no se adapta (BSD-2 lo permitiría, pero es innecesario y pesado). Prioridad P2.

## Validación mínima
Si se activa: tomar un clip corto aportado por el propietario, ejecutar en una copia exportada (no en el worktree) con valores por defecto y comparar el número de eventos
con lo que él ve; medir CPU/tiempo. No requiere tocar el DVR.

## Licencia y precauciones
BSD-2-Clause: conservar el aviso de copyright si se reutiliza. No instalar ahora.
