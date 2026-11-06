---
documento: "Análisis: siguiente cuello de botella tras demostrar frame real"
tipo: "INVESTIGACIÓN + esqueleto de Decision Package (NO implementado, NO ratificado)"
fecha: 2026-09-28
estado: "PARADA — DECISION REQUIRED"
fuente: "código real del repo (HEAD 6dad6af); no memoria"
---

# El cuello de botella no es la percepción: es que la percepción está DESCONECTADA

## 1. Estado real (evidencia en código)
- `core/percepcion.py` (`PercepcionVisual`, `LecturaVisual`, `Frame`, `FuenteDeVision`) — existe, probado.
- `adapters/camara_rtsp.py`, `adapters/vision_local.py` — fuentes, probadas.
- `core/politica_superficie.py` — política por superficie, probada.
- **Frame real DEMOSTRADO** desde 2 fuentes heterogéneas: webcam local .38 (640×480, V4L2) y YCC/.110
  (1280×720, RTSP). Ambas por el mismo puerto `PercepcionVisual`.

## 2. Frontera arquitectónica actual (demostrada por grep)
```
fuente → frame → LecturaVisual → obs.log(audit) → (se descarta)
```
`PercepcionVisual` se referencia SOLO desde módulos pares (`camara_rtsp`, `vision_local`,
`politica_superficie`) y sus tests. **NO** aparece en `composicion.py` ni `orchestrator.py`; **NO** publica
al event bus; **NO** emite `Senal`; **NO** escribe memoria; **NO** alimenta `entorno.py` (que solo la
menciona en texto: «tiene cámara, pero no la uso»). Su única salida es `obs.log`.

## 3. Cuello de botella real
**La percepción visual es una isla: capacidad de laboratorio, no capacidad de sistema.** AURA (el
orchestrator en ejecución, la memoria, la superficie conversacional, el conocimiento del entorno) **nunca
recibe** una `LecturaVisual`. Un frame se adquiere y se pierde.

Consecuencia: añadir detección de movimiento / evento / persona / identidad AHORA sería prematuro —
ninguna de esas capas tendría consumidor tampoco. El prerequisito es **conectar la percepción al sistema**.

## 4. Siguiente capacidad a estudiar (NO implementar)
`FRAME → OBSERVACIÓN` conectada al sistema: que una `LecturaVisual` se convierta en una **observación**
(metadatos: fuente, superficie, tamaño, timestamp; SIN imagen, SIN identidad) que el orchestrator/entorno
pueda registrar y que la superficie conversacional pueda responder («recibí un frame de la cámara X,
1280×720; no interpreto su contenido»). La detección de EVENTO (movimiento) sería una grada POSTERIOR,
una vez exista consumidor.

## 5. DECISION REQUIRED
Sí. Conectar la percepción toca producto (`composicion.py`/`orchestrator.py`) y define cómo una
observación visual entra al contexto/memoria de AURA — decisión de representación y **retención** que la
acta de visión (§10) exige documentar ANTES de implementar. No se implementa sin Decision Package aprobado.

## 6. Esqueleto de Decision Package (borrador; NO ratificado)
- **Problema:** la percepción visual no tiene consumidor; el frame se descarta en `obs.log`.
- **Evidencia:** grep — 0 consumidores fuera de pares/tests; no wiring en composición/orchestrator; frame
  real demostrado en .38 y .110.
- **Objetivo:** que una `LecturaVisual` se convierta en una **observación ambiental** consumible por AURA,
  gobernada por `politica_superficie`, reducida a metadatos, sin identidad ni persistencia de imagen.
- **Alternativas:** (a) observación bajo demanda (AURA percibe cuando se le pregunta/ordena); (b) proveedor
  de contexto pasivo periódico; (c) evento disparado por la fuente. La (a) es la más simple y honesta primero.
- **Trade-offs:** (b)/(c) acercan a vigilancia continua (más riesgo de retención/privacidad); (a) mantiene
  a AURA reactiva y auditable.
- **Riesgos:** retención de imagen (debe seguir siendo cero por defecto); deriva hacia vigilancia; consumo
  en HC-1; que «observación» se confunda con «persona/identidad».
- **Pruebas necesarias:** RED de «percibir bajo demanda produce observación consumible»; que la política
  siga negando superficies no autorizadas; mutación (no emitir observación sin frame; no persistir imagen;
  observación no afirma persona/identidad); regresión de la cadena existente.
- **Criterios de aceptación:** AURA responde a «¿qué ves en la cámara X?» con una observación real
  (fuente+dimensiones+timestamp), gobernada por política, sin imagen almacenada, sin identidad; y lo
  recuerda como resultado de ejecución (M8) si aplica.

## 7. NO HACER (esta sesión y hasta DP aprobado)
Detección de movimiento/persona/identidad; almacenamiento de imagen/vídeo; audio de cámara; frontend;
tocar DVR .80; modificar Bible/ADR/DP/CHECKPOINT/invariantes/permisos; descargar modelos; commit/push/merge.
