---
numero: ADR-0008
titulo: "Voz (STT/TTS): Whisper + Piper locales"
estado: accepted
fecha: 2026-07-18
fecha-resolucion: 2026-07-18
decisor: "Mauricio (CEO)"
proponente: "Fable (CTO)"
impacta: ["6.2", "3.6", "2.5"]
origen: "Acta D3 (4 niveles); capítulo 3.6"
reabre: "—"
supersede: "—"
superseded-por: "—"
motivo-rechazo: "—"
---

# ADR-0008 — Voz (STT/TTS): Whisper + Piper locales

## Contexto

La interacción por voz (6.2) y el presupuesto de latencia (2.5 §5.1) requieren motores de STT y TTS. Selección de tecnología con alternativas → 4 niveles (D3), decisión del CEO. Las cuatro alternativas y su recomendación viven en el capítulo 3.6 §3.

## Decisión

**Aprobada por el CEO (2026-07-18): Nivel Balanceado.** Se adopta **Whisper (STT) + Piper (TTS) ejecutándose localmente**, usando servicios externos **únicamente como contingencia cuando sea estrictamente necesario**. Regla del CEO: *"La prioridad continúa siendo Local-First."* Toda salida a nube pasa por minimización (regla 5 ADR-0001).

## Consecuencias

Positivas: cumple local-first (ADR-0001), sustituibilidad (P-ARQ-4) y sostenibilidad por equipo pequeño (regla 13 ADR-0004). Negativas: la optimización a niveles superiores exige un ADR (o Alerta si cambia un principio). Riesgos aceptados: si el rendimiento no basta, se escala por el instrumento correspondiente.

## Impacto (acta D11 — obligatorio)

| Dimensión | Impacto |
|---|---|
| Seguridad | Positivo: audio procesado local, sin enviar voz a la nube por defecto |
| Privacidad | Positivo máximo: refuerza ADR-0001; la voz no sale del perímetro |
| Modularidad | Positivo: motores tras el contrato del adaptador de voz (3.4) |
| Costo | Bajo/medio: local, puede requerir GPU (3.6/7.4) |
| Experiencia de usuario | Positivo: latencia local menor; sujeto a 2.5 §5.1 |
| Mantenimiento futuro | Positivo: motores sustituibles por contrato |

## Trazabilidad

Capítulos: 6.2 (pipeline de voz), 2.5 (latencia), 3.6. Código futuro: adaptador de voz.
