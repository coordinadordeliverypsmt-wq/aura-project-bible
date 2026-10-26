---
documento: "Decision Package — CM1 vía hardware/aceleración (DP-CM1-HW-ACCEL)"
tipo: "DECISION PACKAGE — BORRADOR. NO APROBADO. NADA IMPLEMENTADO. CM1 NO se modifica."
fecha: 2026-09-28
autor: "APUS-5 (CTO)"
estado: "EJECUTADO 2026-09-29 (CEO autorizó 1 y 2) → CM1 NO ALCANZADO. Resultado: RESULTADO-CM1-HW-ACCEL.md. Queda abierta SOLO la vía (3) hardware y las rutas con root (fuera de autorización)."
fuente: "inspección física [EJEC] 2026-09-28 + DP-CM1 + ACTA-DECISION-CEO-CM1 + mediciones previas. NO memoria."
gobernanza: "Bible 2.2 (CM1) · D24 (local-first, sin descargas de terceros) · ADR-0001 · CLAUDE.md"
---

# DP-CM1-HW-ACCEL — Romper el muro físico de CM1

> CM1 (P50 ≤ 800 ms) **no se modifica**. Este DP estudia rutas de hardware/aceleración/TTS para el muro
> físico. Nada implementado; el iGPU y las alternativas requieren decisiones (descargas/hardware).

## 1. Problema
CM1 = **P50 ≤ 800 ms** del turno completo, criterio de aceptación de R1. En HC-1 no se alcanza. STT es
resoluble (Vosk 415 ms); **el muro restante es TTS** (Piper CPU) y, en general, inferencia CPU-bound.

## 2. Evidencia anterior [EJEC]
- STT: Whisper tiny 4,79 s · base 10,99 s · **Vosk (gramática cerrada) 415 ms**.
- TTS Piper precargado: «Sí.» 559 ms · 19c 2231 ms · 31c 3107 ms (~100 ms/char).
- **Piso inferior secuencial derivado** (no P50 E2E medido): STT Vosk 415 + TTS «Sí.» 559 = **974 ms > 800 ms**.
- B1 (streaming) no arregla el P50 del turno completo; B2 (Vosk) resuelve STT; B3 no eliminó el muro TTS.

## 3. Cuello físico
Inferencia neuronal **CPU-bound** en Celeron N4020 (2 núcleos, sin acelerador). TTS (Piper/onnxruntime CPU)
escala con la longitud de la respuesta y supera 800 ms para cualquier frase no trivial. STT ya no es el muro.

## 4. iGPU actual [EJEC 2026-09-28]
- **Intel UHD Graphics 600** (GeminiLake), `/dev/dri/renderD128`, driver **i915 cargado**. Presente y accesible.
- **Backends de aceleración: TODOS AUSENTES** — `openvino`, `onnxruntime-openvino`, `pyopencl`, `level-zero`,
  `clinfo`: ninguno instalado.
- **onnxruntime PRESENTE pero solo `CPUExecutionProvider`** (sin OpenVINO EP, sin GPU).
- **ctranslate2 (Whisper): 0 CUDA**, y no tiene backend iGPU → **STT no puede usar la iGPU**. Vosk (Kaldi) es CPU.
- **Piper usa onnxruntime** → la iGPU solo sería aplicable a **TTS**, y solo con onnxruntime-openvino (ausente).
- **Conclusión [HECHO]:** la iGPU existe pero **no es alcanzable por el stack actual sin instalar backends**.

## 5. OpenVINO / oneAPI
- **Ausentes.** Habilitar la iGPU para TTS exigiría instalar: OpenVINO runtime + `onnxruntime-openvino` EP +
  runtime de cómputo Intel GPU (level-zero / intel-compute-runtime). **Todo son descargas** → **decisión D24**
  (local-first, sin dependencias de terceros no aprobadas).
- **[HIPÓTESIS] no medida:** aun instalado, la UHD 600 (Gen9.5, gama baja) acelerando Piper podría **no**
  bajar de 800 ms para una frase; requiere **medición post-instalación**. STT no se beneficia (ctranslate2/Vosk CPU).
- **No afirmar aceleración sin medir.**

## 6. TTS
- Ruta real: `voice_real._tts_sync → PiperVoice.load(...).synthesize_wav(text, wave)`; onnxruntime CPU;
  precarga una vez; síntesis ~100 ms/char [EJEC].
- **Alternativas** (todas requieren descarga → D24, y traen tradeoffs):
  - Voz Piper «low» (menor calidad, más rápida) — no está en la USB; descarga.
  - Motor TTS más ligero/streaming — descarga + integración.
  - TTS por iGPU (§5) — descarga de backends.
- **[HIPÓTESIS]:** una TTS < ~385 ms combinada con Vosk STT (415 ms) **podría** cerrar CM1 para turnos de
  respuesta corta; **no medido**, depende de descarga/instalación.

## 7. Hardware alternativo
- **[HIPÓTESIS]** un dispositivo con **NPU o dGPU** (o CPU con más núcleos) reduciría la inferencia. HC-1 es
  el **suelo de referencia** del MVP; cambiarlo es decisión de alcance/hardware. No se adquiere HW aquí.
- Requisito técnico mínimo estimado: acelerador con soporte OpenVINO/onnxruntime-GPU o CUDA para STT+TTS.

## 8. Combinaciones
- **Vosk STT (CPU, 415 ms) + TTS acelerada** (iGPU o modelo más rápido): la única combo con posibilidad de
  ≤ 800 ms para respuestas cortas. **[HIPÓTESIS], requiere instalar/medir.**
- STT acelerado no aporta (Vosk ya < objetivo; y la iGPU no acelera ctranslate2/Vosk).

## 9. Dependencias
OpenVINO runtime · onnxruntime-openvino · intel level-zero / compute-runtime (para §5); o un modelo TTS más
rápido (§6); o hardware acelerado (§7). **Todas fuera del entorno actual → descarga o hardware.**

## 10. Riesgos
- Instalar backends podría desestabilizar el entorno (drivers/level-zero) — reversible pero no trivial.
- [HIPÓTESIS de fracaso] la UHD 600 puede no dar la aceleración suficiente → esfuerzo sin cerrar CM1.
- TTS más ligera → pérdida de calidad de voz (funcionalidad).
- Depender de la iGPU/OpenVINO añade una dependencia de plataforma (menos portable).

## 11. Privacidad
Ninguna ruta cambia la retención: todo sigue local (offline). No se almacena audio/contenido. [HECHO]

## 12. Seguridad
Instalar backends = revisar procedencia/integridad de paquetes (level-zero, OpenVINO). No introducir binarios
no verificados. Sin secretos.

## 13. Reversibilidad
- iGPU/OpenVINO: reversible (desinstalar; el pipeline vuelve a CPU). Config por EP.
- TTS alternativa: reversible (config de voz/modelo).
- Hardware: decisión de despliegue.

## 14. Coste
- iGPU: coste de tiempo de integración + riesgo; HW ya presente (sin coste de compra).
- Hardware alternativo: coste de adquisición (no evaluado; no se compra).

## 15. Impacto en local-first (D24)
Todas las rutas pueden mantenerse **offline** (backends y modelos locales). El punto de fricción con D24 es
**la descarga inicial** de backends/modelos — requiere que el CEO la autorice como dependencia local legítima.

## 16. Pruebas necesarias
- Tras instalar OpenVINO+onnxruntime-openvino+level-zero: medir Piper por iGPU (onnxruntime OpenVINO EP) —
  P50 de síntesis de frases representativas.
- Medir el **turno completo E2E** (Vosk STT + routing determinista + TTS acelerada) contra **P50 ≤ 800 ms**,
  muestra ≥ N, distribución. **P50 E2E real, no suma de etapas.**
- Regresión de exactitud de la voz si se cambia de modelo.

## 17. Criterios de éxito
**P50 E2E ≤ 800 ms** medido de forma reproducible (no time-to-first-response, no suma parcial, no una sola
etapa). Sin romper funcionalidad/exactitud/privacidad/L3/L4.

## 18. Plan de implementación (SI el CEO autoriza; no ejecutado)
1. Autorizar (D24) instalar OpenVINO runtime + onnxruntime-openvino + level-zero en un entorno aislado.
2. Medir Piper por iGPU (frases cortas y normales).
3. Si TTS iGPU + Vosk STT ≤ 800 ms E2E → preparar la integración (fast-path Vosk + EP OpenVINO en voice_real)
   como incremento con su propio DP de implementación (RED→GREEN→mutación→gate).
4. Si no → evaluar §6 (TTS más rápida) o §7 (hardware).

## 19. Plan de rollback
Desinstalar backends / revertir la config de EP → el pipeline vuelve a CPU (estado actual). Sin cambios de
código commiteados hasta la integración autorizada.

## 20. Decisión requerida
**¿Qué se autoriza para intentar romper el muro de CM1?** (una o varias, con las mediciones que impliquen):
- **(1) Habilitar la iGPU:** autorizar la **instalación local (excepción D24)** de OpenVINO + onnxruntime-
  openvino + level-zero para **medir** Piper por la UHD 600 (STT seguiría en Vosk/CPU). [No implementado]
- **(2) TTS más rápida:** autorizar descargar/evaluar una voz/motor TTS local más ligero (tradeoff calidad).
- **(3) Hardware con acelerador:** reconsiderar el dispositivo de referencia (decisión de alcance/hardware).
- **(0) No hacer nada aún:** CM1 permanece NO ALCANZADO en HC-1 (documentado), R1 bloqueado por hardware.

**Qué habilitaría cada decisión:** (1) permite medir si la iGPU cierra TTS (única aceleración disponible en
HC-1 hoy, solo para TTS); (2) permite bajar TTS por modelo (sin depender de la iGPU); (3) resuelve STT+TTS
pero cambia el hardware de referencia. **Nada se implementa ni se instala sin la decisión.**
