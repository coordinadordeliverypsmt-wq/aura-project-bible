---
documento: "Acta de decisión CEO — CM1 (cuello de botella de latencia de R1)"
tipo: "PUERTA DE GOBIERNO. Presenta la decisión; NO la toma. Nada implementado, nada experimentado."
fecha: 2026-09-28
estado: "DECISION_REQUIRED — CM1 · IMPLEMENTACIÓN NO AUTORIZADA · EXPERIMENTACIÓN NO AUTORIZADA"
fuente: "DP-CM1-CUELLO-DE-BOTELLA-R1.md + mediciones [EJEC] 2026-09-15/28 + AURA_MASTER_DEVELOPMENT_MAP.md. NO memoria."
gobernanza: "Bible 2.2 §3.4/§3.5 (CM1–CM4) · CLAUDE.md (no publicar techos no derivables) · D24 local-first"
---

# ACTA DE DECISIÓN CEO — CM1

> Sin elección, sin ranking, sin puntuación, sin ganador. La decisión es del CEO.

## 1. Criterio vigente
**CM1 = P50 ≤ 800 ms por turno**, en local. Puerta de aceptación de R1/MVP (Bible 2.2). **No se modifica.**

## 2. Evidencia [EJEC]
HC-1 = Celeron N4020, 2 núcleos, 3,6 GiB, sin GPU/NPU.
- STT whisper-tiny (orden 2 s): **4,79 s** · STT whisper-base: **10,99 s** (2026-09-28).
- STT base (utterance larga): 27,5 s · TTS Piper (frase corta): **13,3 s** · turno determinista: **29,4 s** ·
  turno con LLM: 374,7 s (STT 58,7 / LLM 285,9 / TTS 30,0) (2026-09-15).
- Wake word Vosk (gramática cerrada): near-real-time (~0,1–0,2 s/s de audio) [evidencia campaña previa].

## 3. Cuello de botella
[EJEC] **Inferencia neuronal CPU-bound** (Whisper STT + Piper TTS + qwen LLM) en un Celeron N4020 sin
acelerador. El Core determinista ya evita el LLM en consultas deterministas; el piso está en **STT + TTS**.

## 4. Alternativas (documentadas en DP-CM1; ninguna seleccionada)
- **A — Hardware acelerado** (GPU/NPU/más núcleos). [HIPÓTESIS] podría reducir inferencia; local-first se
  mantiene si es HW local; reversible (despliegue).
- **B1 — STT streaming/parcial.** [HIPÓTESIS] reduce *time-to-first-response*; el **turno completo** podría
  NO alcanzar 800 ms.
- **B2 — Vía rápida Vosk** (gramática cerrada, ya presente como wake word). [HIPÓTESIS] STT de órdenes
  comunes podría acercarse; cobertura limitada; **no cierra CM1 por sí sola** (TTS sigue lento).
- **B3 — Modelo cuantizado/acelerado.** [HIPÓTESIS] ganancias marginales (tiny ya 4,79 s); tradeoff de
  exactitud.
- **C — Reconsiderar el criterio CM1.** [DECISIÓN de gobernanza, no técnica] modificar el gate/Bible.

## 5. Evidencia faltante (por alternativa)
- A: P50 por etapa (STT/TTS/LLM) en HW candidato. — B1: time-to-first-response + P50 del turno completo con
  streaming; exactitud de parciales. — B2: latencia end-to-end Vosk + **cobertura** real sobre turnos
  históricos + turno completo (incl. TTS). — B3: P50/exactitud del STT candidato. **Ninguna medida aún.**

## 6. Riesgos
Declarar «cumple CM1» sin medición (INV-9). B2 sin abordar TTS → turno completo seguiría fuera. B1 → actuar
sobre parcial erróneo (seguridad de acción). C → alterar la Bible sin acta. A → dependencia de HW específico
/ romper el suelo HC-1 del alcance. B3 → regresión de exactitud (choca con la corrección de alucinación que
motivó `base`).

## 7. Trade-offs
Velocidad vs exactitud (B2/B3), responsividad vs corrección del turno completo (B1), coste/despliegue vs
latencia (A), alcance/gobernanza vs criterio absoluto (C). Ninguno se resuelve sin medición o acta.

## 8. Dependencia STT/TTS/LLM
CM1 del **turno completo** depende de **STT y TTS** (y del LLM en turnos conversacionales). Una solución de
solo-STT **no basta**: hay que abordar también TTS (o mover la respuesta a texto donde no se requiera voz).

## 9. Opciones de experimentación (si el CEO las autoriza; hoy NO AUTORIZADAS)
- Medir latencia+cobertura de la vía rápida Vosk sobre órdenes cerradas (B2).
- Medir P50/exactitud de un STT alternativo/cuantizado (B3).
- Medir time-to-first-response y P50 del turno completo con streaming (B1).
- Medir P50 por etapa en un HW acelerado candidato (A).
- Medir el turno completo (STT+routing+TTS) en cada caso, contra P50 ≤ 800 ms.

## 10. Decisión requerida
**¿Qué camino se autoriza para continuar el análisis experimental de CM1?** — A / B1 / B2 / B3 / C /
combinación explícita. Y, si se autoriza experimentación: **¿qué mediciones concretas quedan autorizadas?**

## 11. Acciones expresamente NO AUTORIZADAS (esta sesión y hasta acta)
Implementar A/B1/B2/B3; cambiar Whisper/Vosk/Piper/qwen; cambiar el default base→tiny; cuantizar; cambiar
hardware; modificar el hot path; modificar CM1/Bible/ADR/gate; ejecutar experimentos físicos; crear código
de producto; adaptar tests; tocar L3/L4/R4/main; merge/cherry-pick/rebase; commit de implementación.

## 12. Próximo paso posterior a la decisión
Solo tras autorización explícita: ejecutar **exactamente** las mediciones aprobadas (sin implementar aún) →
registrar evidencia → comparar con CM1. **Una medición positiva NO equivale a autorización de
implementación:** la implementación requiere su propia decisión + Decision Package.

---
**Estado:** `DP-CM1 = PREPARADO` · `ACTA CEO = PREPARADA` · **CM1 = DECISION_REQUIRED** ·
IMPLEMENTACIÓN = NO AUTORIZADA · EXPERIMENTACIÓN = NO AUTORIZADA. L3 (voz E2E, R1) intacto; L4 (f81361a, R4,
diferido) intacto; main d933a08 intacto; worktree original intacto.
