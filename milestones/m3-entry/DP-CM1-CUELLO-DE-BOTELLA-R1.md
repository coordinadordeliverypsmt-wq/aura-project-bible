---
documento: "Decision Package — CM1: cuello de botella de latencia de R1"
tipo: "DECISION PACKAGE — BORRADOR. NO APROBADO. NADA IMPLEMENTADO. Prepara la decisión, no la toma."
fecha: 2026-09-28
autor: "APUS-5 (CTO)"
estado: "DECISION_REQUIRED — CM1 (esperando al CEO)"
fuente: "mediciones [EJEC] 2026-09-15 y 2026-09-28 (HC-1) + AURA_MASTER_DEVELOPMENT_MAP.md + evidencia-voz/. NO memoria."
gobernanza: "Bible 2.2 §3.4/§3.5 (CM1–CM4, aceptación R1) · CLAUDE.md (no publicar techos numéricos no derivables) · D24 local-first"
---

# DP-CM1 — El cuello de botella de latencia de R1

> **No se implementa ninguna alternativa en este DP. No se modifica CM1.** Presenta evidencia, alternativas
> e impacto para UNA decisión del CEO.

## 1. Contexto
R1/MVP es el horizonte activo del cronograma (M1+M2+M3). Su aceptación exige sostener **CM1–CM4** en uso
real (Bible 2.2 §3.4). **CM1 = P50 ≤ 800 ms por turno** en local. Es el **bloqueo nº 1** del proyecto.

## 2. Problema
En el hardware de referencia **HC-1 (Celeron N4020, 2 núcleos, 3,6 GiB, sin GPU/NPU)**, un turno de voz mide
**segundos**, no milisegundos. CM1 no se alcanza por optimización ordinaria de código.

## 3. Evidencia [EJEC]
| Etapa | Medida | Fuente |
|---|---|---|
| STT whisper-tiny (orden 2 s) | **4,79 s** (+6,0 s carga) | 2026-09-28 |
| STT whisper-base (orden 2 s) | **10,99 s** (+9,0 s carga) | 2026-09-28 |
| STT base (utterance larga) | 27,5 s | 2026-09-15 |
| TTS Piper (frase corta) | 13,3 s | 2026-09-15 |
| Turno determinista (sin LLM) | 29,4 s | 2026-09-15 |
| Turno con LLM | 374,7 s (STT 58,7 / LLM 285,9 / TTS 30,0) | 2026-09-15 |
| Wake word Vosk (gramática cerrada) | ~0,1–0,2 s por s de audio (near-real-time) | evidencia campaña voz previa |

## 4. CM1 actual
P50 ≤ 800 ms por turno, criterio de la Bible para aceptación de R1. Hoy el turno más rápido medible (STT
tiny 4,79 s, solo STT) es **~6× el objetivo**; con TTS (~13 s) el turno completo es **~20–40×**.

## 5. Cuello de botella (demostrado)
**Inferencia neuronal CPU-bound**: Whisper (STT) y Piper (TTS) — y qwen (LLM) cuando se usa — sobre un
Celeron N4020 de 2 núcleos sin acelerador. El routing/memoria/Core determinista NO es el coste (el Core ya
evita el LLM en consultas deterministas). **El piso está en STT+TTS.**

## 6. Restricción HC-1
Es el hardware de referencia del MVP. La Bible mide «por criterios de salida, no por fechas»; CM1 asume un
umbral. HC-1 no tiene aceleración neuronal. **HECHO:** ni tiny alcanza el objetivo (4,79 s solo STT).

## 7. Alternativa A — Hardware con aceleración
- **Mecanismo:** ejecutar sobre un dispositivo con GPU/NPU o más núcleos → acelera STT/TTS/LLM.
- **Qué cambia:** el tiempo de inferencia; **qué NO cambia:** arquitectura, local-first (sigue offline), código.
- **Latencia potencial:** [HIPÓTESIS] podría acercarse a CM1; **requiere medición** en el HW candidato.
- **Privacidad/offline:** se preserva si es hardware local (no nube). **Reversible** (elección de despliegue).
- **Riesgo:** coste, disponibilidad; que HC-1 deje de ser el suelo de referencia (decisión de alcance).
- **Evidencia faltante:** P50 real por etapa en el HW candidato.
- **NO se recomienda un HW concreto aquí.**

## 8. Alternativa B1 — STT streaming / parcial
- **Mecanismo:** transcripción incremental; responder al resultado parcial sin esperar el fin.
- **Latencia potencial:** [HIPÓTESIS] mejora el *time-to-first-response*; el turno completo sigue CPU-bound
  → **P50 del turno completo podría NO alcanzar 800 ms**; **requiere medición**.
- **Precisión:** los parciales son menos exactos (riesgo de actuar sobre transcripción incompleta).
- **Complejidad:** alta (Whisper streaming/pseudo-streaming, gestión de hipótesis parciales).
- **Privacidad/offline:** sin cambio. **Reversible.** **Impacto arquitectónico:** medio-alto (cambia el hot path de STT).

## 9. Alternativa B2 — Gramática cerrada / vía rápida (Vosk)
- **Mecanismo:** para **órdenes frecuentes**, usar el reconocedor **Vosk de gramática cerrada** (el MISMO
  que ya hace el wake word, near-real-time en este CPU) como **vía rápida**, con fallback a Whisper para
  consultas abiertas.
- **Latencia potencial:** [HIPÓTESIS, la más prometedora en HC-1] Vosk corre ~0,1–0,2 s/s de audio → una
  orden corta **podría** entrar en el rango de CM1; **requiere medición** end-to-end (incl. TTS, que sigue
  siendo ~13 s → **ojo: TTS también debe abordarse** para el turno completo).
- **Cobertura:** limitada al vocabulario/gramática definido; lo no cubierto cae a Whisper (lento). Decisión de
  cobertura necesaria.
- **Precisión:** alta dentro de la gramática; nula fuera. **Privacidad/offline:** sin cambio (Vosk local).
- **Complejidad:** media (router: gramática→Vosk, resto→Whisper). **Reversible.** **Reutiliza** un componente ya presente.
- **Nota:** B2 ataca STT pero **no** TTS; el turno completo exige también reducir TTS (Piper ~13 s) → B2 sola
  no cierra CM1 del turno completo salvo que se combine (p. ej. TTS más rápido / caché / frases cortas).

## 10. Alternativa B3 — Modelo acelerado / cuantizado
- **Mecanismo:** STT más ligero/cuantizado (tiny ya es int8; distil-whisper, otro engine CTranslate2, o TTS
  más rápido).
- **Latencia potencial:** [HIPÓTESIS] ganancias marginales; **tiny ya mide 4,79 s** → rendimientos
  decrecientes sin un modelo/engine fundamentalmente distinto. **Requiere medición.**
- **Precisión:** menor con modelos más pequeños (choca con la corrección de alucinación que motivó `base`).
- **Complejidad:** baja-media. **Reversible.**

## 11. Alternativa C — Reconsiderar el criterio CM1
- **Mecanismo:** definir CM1 como **dependiente de hardware** o contextual, en vez de un absoluto de 800 ms.
- **Impacto:** afecta la **aceptación de R1** y es criterio de la **Bible** (2.2). Choca con la regla del CEO
  («no publicar un techo numérico que no pueda derivarse formalmente») — cambiar CM1 exige acta y quizá ADR.
- **NO es autorización:** es una alternativa para la decisión.

## 12. Impacto arquitectónico
- A: nulo (solo despliegue). B1: medio-alto (hot path STT). B2: medio (router STT + fallback). B3: bajo.
  C: nulo en código, alto en gobernanza.

## 13. Seguridad
Ninguna alternativa introduce superficie nueva si se mantiene local-first. B2 reutiliza Vosk (ya auditado
como wake word). Verificar que un fallback no exponga datos. [INFERENCIA]

## 14. Privacidad
Todas preservan procesamiento local si no se introduce nube. Ninguna cambia retención. [HECHO/INFERENCIA]

## 15. Offline / local-first (D24)
A/B1/B2/B3 son compatibles con offline (HW local, modelos locales). **Ninguna debe introducir nube.** C no
afecta offline. [HECHO]

## 16. Reversibilidad
A: total (despliegue). B1/B2/B3: alta (aditivas/config). C: media (cambio de criterio, revisable por acta).

## 17. Tests necesarios (por alternativa)
- **A:** medir P50 por etapa (STT/TTS/LLM) en el HW candidato; muestra ≥ N turnos; distribución.
- **B1:** medir *time-to-first-response* y P50 del turno completo con streaming; exactitud de parciales.
- **B2:** medir latencia Vosk end-to-end para órdenes de la gramática; **cobertura** (qué % de turnos reales
  cubre) usando el historial; falsos positivos/negativos; y el turno COMPLETO (incl. TTS).
- **B3:** medir P50 STT del modelo candidato vs tiny; exactitud (regresión de alucinación).
- **Común:** definir el conjunto de turnos representativo para P50; hardware fijo; modelos precargados.

## 18. Métrica de aceptación
CM1: **P50 ≤ 800 ms** por turno (criterio actual, no modificado). Cualquier alternativa debe **demostrarlo
por medición**, no por estimación. Sin medición, el estado es «podría / requiere validación».

## 19. Riesgos
- Declarar que una alternativa «cumple CM1» sin medición (INV-9). — prohibido.
- B2: reducir STT y olvidar que **TTS (~13 s) también viola CM1** → el turno completo seguiría fuera.
- B1: actuar sobre transcripción parcial errónea (seguridad de acción).
- C: relajar CM1 sin acta = alterar la Bible sin proceso.
- A: introducir dependencia de HW específico / romper el suelo HC-1 del alcance.

## 20. Dependencias
CM1 depende de STT **y** TTS (y LLM en turnos conversacionales). Una solución de turno completo debe abordar
**ambos** (o mover la respuesta a texto para los turnos donde el TTS no sea necesario — otra sub-decisión).

## 21. Evidencia faltante
- P50 por etapa en HW con acelerador (A).
- Latencia + cobertura reales de la vía rápida Vosk sobre turnos representativos (B2).
- P50/exactitud de un STT alternativo (B3).
- Time-to-first-response con streaming (B1).
- Ninguna se mide en este DP (es preparación de decisión).

## 22. Decisión requerida
**¿Qué camino se toma para CM1 (o qué combinación), y qué experimentos de medición se autorizan para
fundamentarlo?** — Opciones: **A** (hardware con acelerador), **B1** (STT streaming), **B2** (vía rápida
Vosk + abordar TTS), **B3** (modelo acelerado), **C** (reconsiderar el criterio CM1). Ninguna se implementa
ni se prioriza aquí; la decisión y la autorización de experimentos son del CEO. **Observación del CTO (no
decisión):** el turno completo exige atacar STT **y** TTS; B2 (Vosk, ya presente) es el candidato más
prometedor de medir para STT de órdenes comunes, pero por sí solo no cierra CM1 sin una solución de TTS.
