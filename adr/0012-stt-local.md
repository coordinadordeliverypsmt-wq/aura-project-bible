---
numero: ADR-0012
titulo: "Motor de reconocimiento de voz (STT) local"
estado: accepted
fecha: 2026-07-18
fecha-resolucion: 2026-07-18
decisor: "Mauricio (CEO)"
proponente: "Fable (CTO)"
impacta: ["6.2","2.5"]
origen: "Acta D24 (stack local-first, análisis comparativo por ADR)"
reabre: "—"
supersede: "—"
superseded-por: "—"
motivo-rechazo: "—"
---

# ADR-0012 — Motor de reconocimiento de voz (STT) local

## Contexto

La voz (6.2) requiere STT local (ADR-0008 eligió Whisper). El acta D24 exige análisis comparativo open source. Conforme al acta D24, se elige entre alternativas **open source y autoalojables**, sin claves de terceros, con análisis comparativo por los seis criterios exigidos por el CEO.

## Alternativas consideradas (open source)

| Opción | Pros | Contras |
|---|---|---|
| **faster-whisper** (CTranslate2) | ~4x más rápido que whisper original; misma precisión; CPU+GPU; streaming; Python; MIT | Requiere CTranslate2 |
| whisper.cpp | C++, mínimas deps; excelente en CPU/edge; GGUF cuantizado | Integración algo más manual |
| openai-whisper (original) | Referencia de precisión | Lento; pesado |
| Vosk | Muy ligero; streaming | Precisión menor |

## Decisión

**faster-whisper** como STT local oficial (precisión de Whisper con 4x de velocidad, CPU+GPU, streaming para el presupuesto de latencia 2.5 §5.1). **whisper.cpp** se registra como alternativa oficial para hardware de recursos muy limitados (edge/CPU puro). Confirma y precisa ADR-0008.

## Justificación (criterios del acta D24)

- **Rendimiento:** faster-whisper es el mejor equilibrio precisión/velocidad en CPU y GPU.
- **Mantenimiento:** paquete Python estable; modelos descargables.
- **Comunidad:** amplia; derivado directo de Whisper.
- **Portabilidad:** Linux/macOS/Windows.
- **Integración:** Python (ADR-0005); tras el contrato del adaptador de voz (6.2).
- **Largo plazo:** modelos Whisper abiertos; sin lock-in.

## Impacto (acta D11)

| Dimensión | Impacto |
|---|---|
| Seguridad | Positivo: audio procesado local |
| Privacidad | Positivo máximo: la voz no sale del perímetro |
| Modularidad | Positivo: tras el contrato de voz |
| Costo | Bajo: gratis |
| Experiencia de usuario | Streaming ayuda a la latencia (2.5 §5.1) |
| Mantenimiento futuro | Positivo: sustituible por whisper.cpp |

## Trazabilidad

Capítulos: 6.2 (voz), 2.5 (latencia). Confirma ADR-0008. Producción: faster-whisper (modelo small/base según hardware).
