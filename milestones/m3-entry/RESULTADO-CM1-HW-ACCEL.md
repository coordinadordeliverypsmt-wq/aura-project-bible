---
documento: "Resultado del bloque vertical CM1 — iGPU UHD 600 + TTS alternativa"
fecha: 2026-09-29
autor: "APUS-5 (CTO)"
decision_ceo: "CM1 se mantiene (P50 ≤ 800 ms). Autorizado: (1) experimento controlado iGPU UHD 600, (2) evaluación de TTS local más rápida. No autorizado: hardware, cambio de CM1."
estado_cm1: "NO ALCANZADO"
evidencia: "milestones/m3-entry/evidencia-cm1-hw/ (mediciones/*.json, kernel_i915_gpu_hang.log, arneses/*.py, via-rapida-v2/)"
---

# Resultado CM1 — iGPU + TTS alternativa

## 0. Veredicto

**CM1 = NO ALCANZADO en HC-1.** Ninguna ruta autorizada produce un **P50 E2E ≤ 800 ms**. Criterio medido tal como lo define la
Bible 2.5 §5.1: *de fin-de-habla a inicio-de-respuesta hablada*, con AURA real, por el aire y cronometrado sobre el
micrófono de un observador independiente.

| Medición E2E física (AURA real) | Válidos | P50 válidos | P95 | P50 todos (fallo = ∞) | Respuestas correctas |
|---|---|---|---|---|---|
| **Línea base: camino por defecto** (Whisper base + Piper, ventana fija de 5 s), 8 turnos, sala en silencio | 4/8 | **32,1 s** | 42,0 s | ∞ | 0/3 |
| Vía rápida v1 (espeak + Vosk libre, fin de habla 300 ms) | 8/24 | **995 ms** | 5,9 s | ∞ | 0/5 |
| Vía rápida v2 (espeak + gramática del Core + libre, 450 ms) | 7/24 | **1070 ms** | 1,54 s | ∞ | 0/8 |
| Caso más favorable (solo preguntas de la gramática) | 3/16 | 880 ms (820, 880, 1620 en frío) | — | ∞ | — |

- El mejor turno aislado medido fue de 650 ms. Ningún P50 queda por debajo de 800 ms.
- Con la vía rápida activada, AURA **guardó datos falsos en memoria** («Tu color favorito es en.», nombre «amor eso»).
  Por eso esa vía se **retiró** del código activo (§5).

Referencias anteriores: la línea base del acta D-4 era **7,4 s** en HC-1, y el suelo secuencial derivado era 974 ms
(Vosk 415 + Piper «Sí.» 559). La línea base medida hoy con el mismo instrumento es **32,1 s**. Los mejores turnos de
la vía rápida (0,65–1,1 s) son unas 30× más rápidos que esa línea base, pero **no cumplen CM1** y su precisión
no es aceptable.
No se modificó CM1, no se usó el tiempo hasta la primera respuesta como sustituto y no se compró hardware.

## 1. Ruta (1): iGPU UHD 600 — NO UTILIZABLE [EJEC]

| Paso | Resultado |
|---|---|
| Backend instalado | OpenVINO 2026.4.0 (y 2024.6.0) en `--target` aislado, más el runtime Intel NEO 23.43 (`intel-opencl-icd`, `libigc1`, LLVM 14…) extraído sin root desde el archivo firmado de Ubuntu. sha256 verificados |
| iGPU enumerada | **Sí**: `Intel(R) UHD Graphics 600 (iGPU)`, arch v9.4, FP16+FP32, 12 EU, 3,2 GB compartidos |
| Level Zero | **No funciona**: `zeInit` devuelve `0x78000001` (UNINITIALIZED); la llamada siguiente hace segfault en el cargador. OpenVINO GPU usa OpenCL, así que L0 no está en el camino crítico |
| Modelo en la GPU | **No**: **GPU HANG del i915 en cualquier kernel**, incluido un modelo mínimo de una convolución. 4 hangs registrados (`kernel_i915_gpu_hang.log`) con OpenVINO 2026.4, 2024.6 y `ForcePreemptionMode=2`. No hubo estado `wedged` |
| Mejora de latencia | **No medible** (no ejecuta) |

Se detuvo tras 4 hangs porque cada uno reinicia un contexto de la GPU que da vídeo al escritorio del usuario. Lo que queda
sin probar exige root o cambios de sistema, fuera de lo autorizado: otro NEO (rama legacy1), parámetros del i915 (preempt timeout)
u otro kernel.

**Hallazgo colateral:** OpenVINO **CPU** tarda **50–58 s por inferencia** de Piper. El 99,6 % del tiempo es
`Convolution ref_any_f32`: el Celeron N4020 **solo tiene SSE4.2** (sin AVX) y oneDNN recurre al kernel de referencia para las
convoluciones dilatadas del decodificador HiFi-GAN. onnxruntime (MLAS) no tiene ese problema.

## 2. Ruta (2): TTS alternativa [EJEC]

Inferencia P50 (N=10, sin contar el calentamiento):

| Motor | «Sí.» | «Te llamas Mauricio.» | 34 caracteres | Inteligibilidad (WER ida y vuelta, 12 frases) |
|---|---|---|---|---|
| Piper es_MX medium (actual) | 626 ms | 2222 ms | 3406 ms | **0,18** |
| Piper es_ES carlfm **x_low** | 552 ms | 1032 ms | 1409 ms | — |
| **espeak-ng** (voz `es`, 175 ppm) | **0,6 ms** | **2,7 ms** | **4,3 ms** | 0,33–0,35 (`es-419`: 0,51) |

- **x_low**: 2,2–2,4× más rápida, pero con un **suelo ≥ 550 ms**, así que no cabe. Descargada de `rhasspy/piper-voices`, dataset de
  dominio público, sha256 verificado.
- **espeak-ng**: es la única TTS que cabe en el presupuesto. No requiere descarga (`libespeak-ng1` del sistema; Piper usa la misma
  librería para fonemizar). Tiene una **regresión de calidad medible** (aproximadamente el doble de errores de transcripción).
- La inteligibilidad se midió con un indicador de máquina (TTS → Vosk en memoria), no con oyentes humanos.

## 3. Dónde se va el tiempo (turno real) [EJEC]

| Etapa | Medido |
|---|---|
| `parecord` con latencia por defecto | **~2000 ms de búfer** (P50 2002). Con `--latency-msec=20` + `paplay --latency-msec=30`, la ida y vuelta por el aire es de 85 ms |
| Orquestador, turno determinista + síntesis espeak + WAV | 17–27 ms |
| Fin de habla (VAD propio). El endpointer de Vosk 0.3.45 espera 0,5–1 s y no se puede acortar | 300 ms corta frases («cuál es…», 4/4); **450 ms** no corta |
| Decodificación Vosk | libre: RTF 0,38–0,44, FinalResult 55–158 ms; gramática: RTF 0,09–0,12, 21–49 ms |
| Fin de la persona → AURA publica la respuesta (turnos válidos) | 525–1071 ms |
| Publicación → primer sonido | 76–666 ms (arranque de `paplay` bajo carga) |

**Suelo físico:** fin de habla sin cortar (≥ 450 ms) + captura/decodificación (≥ ~170 ms) + arranque del audio (≥ ~76 ms)
≈ 700 ms en el mejor caso, y 1–1,5 s lo típico, sin margen para errores. Además, la precisión del STT rápido (Vosk small)
sobre habla libre es insuficiente: «¿Cómo me llamo?» → «tuvo media hago» incluso con audio limpio. El STT preciso
(Whisper) tarda 4,8–11 s.

## 4. Condiciones de medición

- HC-1 con Firefox abierto (~60 % de CPU) durante todas las mediciones, igual que en uso real. Sin swap.
- La «persona» es voz sintética (Piper) por el altavoz, al 85 % de volumen (se restauró el 150 % original).
- La última ejecución favorable (`e2e_v2_favorable2.json`) quedó **contaminada** por sonido ajeno en la sala: ruido ambiente medido de
  RMS 1882 frente a 390–455 en las buenas. No se usa para el veredicto.
- Ninguna prueba guardó audio: el observador solo registra RMS por trama; la voz de la persona vivió en un directorio privado temporal y
  se borró.

## 5. Cambios en el código (estado final)

**Se conserva (opcional o independiente):**
- `adapters/tts_espeak.py` (nuevo) + `WhisperPiperVoice(sintetizador=…)` + `composicion._sintetizador_de_entorno`:
  **`AURA_TTS_MOTOR=espeak`** es opcional. **El defecto sigue siendo Piper.**
- `escucha._FlujoDelMicrofono`: `parecord --latency-msec=20` elimina ~2 s de búfer en la escucha de la palabra de activación. Se ejerció
  en decenas de activaciones correctas durante los E2E.
- `microfono.reproducir`: `paplay --latency-msec=30`.

**Se retiró** (copia de referencia en `evidencia-cm1-hw/via-rapida-v2/`): la vía rápida de STT (`escuchar_orden`, VAD propio,
gramática `ORDENES_DE_VOZ` derivada del Core, `AURA_ORDEN_VOSK`). No cierra CM1 y, activada, corrompe la memoria.

## 5.bis Verificación del código conservado [EJEC]

| Control | Resultado |
|---|---|
| Auditoría independiente (auditor ≠ implementador) | APROBADO CON OBSERVACIONES → **todas corregidas**. Grave: estado global de libespeak-ng (2 instancias → WAV vacío y SIGSEGV), ahora a nivel de módulo, con prueba real. Grave: cableado de `composicion.py` sin cubrir, ahora con prueba de integración |
| Mutación `mutaciones/cm1-voz-espeak.toml` | **20/20 detectados**, exit 0, repetido después del formateo. M12 (cableado, ALERTA-005) y M1 (retener el callback) caen por aserción |
| Hallazgo de la mutación | Una prueba del callback era decorativa: el doble retenía el callback en su registro de llamadas. Se corrigió el doble |
| Pruebas dirigidas (voz, escucha, micrófono, composición) | Verde, con 1 xfail previo (DECISION_REQUIRED del CEO) |
| Quality Gate (`quality-gate.sh`) | **FAIL por causas previas, ninguna del incremento** (`mediciones/quality_gate.log`): |
| · formato | 31 ficheros previos sin formatear. Los 2 nuevos del incremento ya están formateados. En los 4 mixtos, los bloques pendientes son de código previo |
| · lint | OK |
| · mypy | 3 errores previos (`core/entorno.py:390`, `adapters/camara_rtsp.py:51,53`); ficheros no tocados |
| · pruebas | **2612 passed, 2 failed, 3 skipped, 1 xfailed**. Los 2 fallos son previos: `test_cognicion_local` (un comentario con «say» en `orchestrator._finalizar_turno`) y `test_garantias_vigentes` (30 garantías obsoletas de otros incrementos; ninguna CM1) |
| · contratos | 8/8 OK |

## 6. Entorno experimental y rollback

- Todo lo instalado vive en `~/.aura-exp/cm1-hw/` (756 MB): el wheel de OpenVINO, la raíz del runtime NEO, la voz x_low y `env.sh`.
  **Nada en el sistema** (sin sudo), nada en `~/.local` y nada referenciado por AURA.
- Hashes y origen: `evidencia-cm1-hw/mediciones/INSTALADO.sha256`.
- **Rollback del entorno:** `rm -rf ~/.aura-exp/cm1-hw`. Se conserva por si el CEO quiere repetir con otro runtime.
- **Rollback del código:**
  - quitar `adapters/tts_espeak.py`, sus pruebas y los kwargs/funciones citados en §5;
  - para volver al búfer por defecto, quitar los dos `--latency-msec`.
  - Con `AURA_TTS_MOTOR` sin definir, el comportamiento ya es el anterior.

## 7. Siguiente decisión real (del CEO)

Con el hardware autorizado, CM1 no se alcanza. Las palancas restantes caen fuera de esta autorización:
- **Hardware** con aceleración real (vía (3), no autorizada), o una CPU con AVX2: el propio OpenVINO CPU dejaría de usar kernels de
  referencia.
- **Runtime GPU con root**: otro NEO o parámetros del i915. Riesgo de estabilidad del escritorio (4 GPU HANG ya registrados).
- **Decisión de producto**: aceptar la calidad de espeak y la cobertura cerrada de órdenes. Aun así, lo medido no baja de 800 ms de P50.
