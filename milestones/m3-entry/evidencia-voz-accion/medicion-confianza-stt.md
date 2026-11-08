# Medición de la confianza del STT (DP-VOZ-ACCION §8 C4 / §5)

Evidencia `[EJEC]`. Modelo Whisper `base` (defecto de AURA, `AURA_WHISPER_MODEL` sin definir), mismo camino que el
producto (`WhisperPiperVoice._stt_sync`: margen de silencio, vocabulario, `sin_eco`). Todo en memoria: **no se
guardó audio**. El JSON (`medicion-confianza-stt.json`) contiene solo métricas y el texto transcrito.
Herramienta: `walking-skeleton/herramientas/medir_confianza_stt.py` (`--reanalizar` recalcula sin transcribir).
135 casos: 105 de orden/«sí»/«no» sintetizados con Piper `es_MX-ald-medium` (3 velocidades × limpio y 2 colores de
ruido × SNR 20/10/5 dB), 26 que NO son orden (silencio, ruido blanco/rosa a 3 amplitudes, 3 tonos, voz cortada a
0,5 s, frases ajenas) y 4 tomas de ruido ambiental real del micrófono (3 s, capturadas con `parecord --raw`).

## Hallazgos

1. **Fabricados por el STT: 1 de 30 entradas que no son orden** (3 %): la voz cortada «apaga la tele de la sala»
   (0,5 s) salió como «Vale.», que `hogar.confirmacion` reconoce como «sí». **Ninguna orden de hogar fue
   fabricada**, ni a partir de silencio, ruido, tonos ni ambiente. N pequeño: el intervalo es amplio (0,1-17 % al 95 %).
   Lo que sí fabrica Whisper es texto: las 30 entradas no-orden produjeron texto (p. ej. «¿Qué hiciste?» con
   silencio, «No, no, no, no…» con ruido ambiental y con «mañana llueve»).
2. **`no_speech_prob` separa el no-habla sintético de la voz** y nada más. Silencio/ruido/tono: 0,167-0,458.
   Voz real entendida: 0,008-0,071; voz mal entendida: máx 0,095; voz que no es orden: máx 0,028.
   Umbral 0,15 corta todo el no-habla sintético (11/11) sin perder ninguna orden/«sí» entendida (22/22).
3. **Ruido ambiental real del micro: NO separable.** Tomas 0-2: nsp 0,024-0,031 y logprob -0,60/-0,87/-1,06,
   dentro del rango de voz real; solo la toma 3 (nsp 0,18, logprob -4,34) cae por los dos umbrales. 3 de 4 pasan
   el filtro (transcribieron «No se me permiten ver este paso también.», «¿Qué haces aquí?», «No, no, no…»:
   ninguna es orden ni «sí», pero un filtro de confianza no las habría frenado).
4. **`avg_logprob` solo sirve como red de seguridad para la basura larga:** transcripciones de ruido/tono con
   -1,7 a -4,5 y 5 dB con «sí». Entre voz entendida (-0,48 a -1,03) y el único fabricado («Vale.», -0,797) NO hay
   separación: exigir -0,7 elimina el fabricado pero también 12 de 22 órdenes/«sí» entendidas (10/22 conservadas).
5. **Límite del propio STT con la voz de Piper (no es de los umbrales):** «apaga» salió casi siempre como «para»/
   «apara» incluso en limpio: 0 de 63 repeticiones de las tres órdenes fueron entendidas como orden; «sí» 5/21 y
   «no» 17/21. Con voz sintética no se puede medir cuántas órdenes humanas pierde el filtro; solo se mide que
   no hay órdenes fabricadas. Habría que repetir con voz humana grabada del CEO (con su consentimiento y sin guardar audio).
6. **Coste:** la transcripción de 2 s de ruido tardó ~170-210 s con la máquina cargada (Whisper cae en decodificación
   con temperaturas alternas). Por encima del límite de transcripción de AURA, ese turno acabaría en
   `VozNoDisponible` por tiempo, no por confianza.

## Distribuciones (mín / mediana / máx)

| Clase de entrada | n | no_speech_prob | avg_logprob | pasan (0,15; -1,2) |
|---|---|---|---|---|
| Orden/«sí»/«no» entendida | 22 | 0,008 / 0,022 / 0,071 | -1,032 / -0,736 / -0,479 | 22/22 |
| Orden/«sí»/«no» mal entendida | 83 | 0,001 / 0,011 / 0,095 | -3,758 / -0,531 / -0,164 | 78/83 |
| Voz que no es orden (cortada, ajena) | 15 | 0,001 / 0,007 / 0,028 | -1,227 / -0,938 / -0,110 | 14/15 |
| No-habla sintético (silencio, ruido, tono) | 11 | 0,167 / 0,297 / 0,458 | -4,465 / -1,459 / -0,482 | 0/11 |
| Ruido ambiental real (micro) | 4 | 0,024 / 0,031 / 0,180 | -4,345 / -0,964 / -0,601 | 3/4 |
| **Fabricados** (orden o «sí» a partir de no-orden) | 1 | 0,018 | -0,797 | 1/1 pasa |

## Umbrales recomendados

- `UMBRAL_NO_HABLA = 0.15` (rechazar si `no_speech_prob` > 0,15). Respaldo medido: máximo de lo entendido 0,071,
  mínimo del no-habla sintético 0,167. Margen estrecho por arriba (0,167): conviene revisarlo con voz humana.
- `UMBRAL_LOGPROB = -1.2` (rechazar si `avg_logprob` < -1,2). Respaldo: mínimo de lo entendido -1,032. Elimina la
  basura de ruido/tono (≤ -1,7) y no recorta ninguna orden/«sí» entendida.
- Efecto conjunto: 0 de 11 no-habla sintético pasa; 22/22 entendidas conservadas; **sigue pasando 1 fabricado
  («Vale.») y 3/4 tomas del micro**. No hay separación limpia para esos casos con estas dos métricas: el filtro
  de confianza no basta como única defensa. La barrera que sí los frena es la ya existente (la orden de lista roja
  exige confirmación humana, y `Vale.` solo vale como «sí» si hay una propuesta pendiente).
- Alternativa estricta (-0,7): elimina el fabricado a costa de perder 12/22 (55 %) de lo entendido. No recomendada.
- Condición para endurecer: repetir con voz humana y ≥ 20 tomas de ambiente real antes de fijar nada más fino.
