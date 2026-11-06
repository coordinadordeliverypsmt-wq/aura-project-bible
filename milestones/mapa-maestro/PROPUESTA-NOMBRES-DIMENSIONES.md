---
documento: "PROPUESTA (para decisión del CEO) — nombres de las dimensiones A–Q del índice de madurez"
fecha: 2026-10-22
estado: "PROPUESTA — no aplicada. El panel sigue mostrando letras hasta que el CEO apruebe."
---

# Nombres de las dimensiones A–Q — propuesta fundamentada

## 1. Qué existe y qué no

- `[LECT]` `capacidades.json` agrupa las 82 capacidades por letra (`dim`: A–Q) y **no** define nombres.
  `indice_madurez.py` tampoco. Ningún acta, ADR, DP ni libro de la Bible contiene una tabla letra → nombre (búsqueda del
  explorador del 2026-10-22, y `grep "Relación familiar"`: una sola aparición en todo el repositorio).
- `[LECT]` La única huella de nombres es `AURA_MASTER_DEVELOPMENT_MAP.md:119-121`: el «Índice por dimensión
  (lanzamiento)» de la **línea base del 2026-09-27**, con 12 nombres y sus valores, **sin letra**.

## 2. Método (sin fórmula paralela)

Se calculó el índice MVP por letra con el índice oficial (`indice_madurez.calcular(capacidades, "MVP")`, 2026-10-22) y se
comparó con los valores de la línea base. Donde el nivel de las capacidades no ha cambiado desde entonces, el valor
coincide exactamente y la correspondencia es **evidencia**; donde cambió, se asigna **por contenido** y se marca como
inferencia.

| Letra | Nombre propuesto | Fundamento | MVP hoy | Línea base | Contenido (capacidades) |
|---|---|---|---:|---:|---|
| A | Identidad del ser | contenido `[INFER]` | 73,3 | 70,8 | estado real, no finge, identidad estable, sobre de hardware |
| B | Memoria | valor exacto `[EJEC]` | 70,4 | 70,4 | memoria personal, corrección, reinicio, olvido, CM2 |
| C | Inteligencia | valor exacto `[EJEC]` | 66,7 | 66,7 | inferencia local, razonamiento formal, frontera cognitiva |
| D | Audición | contenido `[INFER]` | 83,3 | 61,1 | micrófono, Whisper, palabra de activación |
| E | Voz | valor exacto `[EJEC]` | 72,2 | 72,2 | Piper, altavoz, conversación por voz, barge-in |
| F | *(sin nombre en la línea base)* | — | — | — | cámara, presencia visual, visión, reconocimiento |
| G | *(sin nombre en la línea base)* | — | 100,0 | — | no perfilar a terceros, multiusuario, identificación por voz |
| H | Comunicación | valor exacto `[EJEC]` | 70,8 | 70,8 | conversación general, superficies deterministas, multiturno |
| I | Presencia | contenido `[INFER]` | 79,6 | 60,0 | HA, encender/apagar, volumen, descubrimiento, entorno |
| J | Acción | contenido `[INFER]` | 86,1 | 90,0 | Motor Único, permisos, kill switch, buzón HITL |
| K | Relación familiar | valor exacto `[EJEC]` | 33,3 | 33,3 | preferencias, memoria familiar, historias, humor |
| L | *(sin nombre en la línea base)* | — | — | — | guardián, anomalías, emergencias |
| M | Proactividad | valor exacto + contenido | 61,1 | 61,1 | automatizaciones, notificaciones, anticipación |
| N | *(sin nombre en la línea base)* | — | — | — | oportunidades, ciclo autónomo, autoconstrucción |
| O | *(sin nombre en la línea base)* | — | — | — | delegación, aislamiento, revisión delegada |
| P | Aprendizaje | valor exacto + contenido | 61,1 | 61,1 | señales del usuario, modelo de usuario, patrones |
| Q | Gobierno | valor exacto `[EJEC]` | 91,7 | 91,7 | audit log, Quality Gate, PARADA, registro de decisiones |

M y P empatan en 61,1; se separan por contenido (automatizar/anticipar → Proactividad; señales y patrones → Aprendizaje).
G entró en el ámbito MVP después de la línea base. F, L, N y O no tienen capacidades MVP y nunca tuvieron nombre.

## 3. Qué requiere aprobación del CEO

1. Adoptar los 8 nombres con valor exacto (B, C, E, H, K, M, P, Q).
2. Adoptar los 4 inferidos por contenido (A, D, I, J). «Presencia» para I es el menos evidente: hoy I es sobre todo
   control del hogar.
3. Nombrar G, F, L, N y O (no hay base documental; cualquier nombre sería nuevo).
4. Dónde vive el mapeo: propuesta del ejecutor, una clave `dimensiones` en `capacidades.json` (fuente única), que el panel
   leería sin calcular nada. **No cambia el índice ni la metodología** (todas las dimensiones siguen pesando igual).

Hasta entonces el panel muestra solo letras.
