---
numero: ADR-0013
titulo: "Motor de síntesis de voz (TTS) local"
estado: accepted
fecha: 2026-07-18
fecha-resolucion: 2026-07-18
decisor: "Mauricio (CEO)"
proponente: "Fable (CTO)"
impacta: ["6.2","2.4"]
origen: "Acta D24 (stack local-first, análisis comparativo por ADR)"
reabre: "—"
supersede: "—"
superseded-por: "—"
motivo-rechazo: "—"
---

# ADR-0013 — Motor de síntesis de voz (TTS) local

## Contexto

La voz (6.2) requiere TTS local (ADR-0008 eligió Piper). El acta D24 exige análisis comparativo open source. Conforme al acta D24, se elige entre alternativas **open source y autoalojables**, sin claves de terceros, con análisis comparativo por los seis criterios exigidos por el CEO.

## Alternativas consideradas (open source)

| Opción | Pros | Contras |
|---|---|---|
| **Piper** | Rápido y ligero (ONNX); buena calidad; **voces en español**; CPU-friendly; MIT | Menos expresivo que modelos grandes |
| Coqui XTTS | Alta calidad; clonación de voz | Pesado; prefiere GPU; consideraciones de licencia |
| Mimic3 | Ligero | Proyecto menos activo |
| eSpeak-NG | Ultraligero | Voz robótica |

## Decisión

**Piper** como TTS local oficial: rápido, ligero, CPU-friendly, con voces en **español latino** (identidad de AURA, 2.4 §6). **Coqui XTTS** se registra como opción futura de mayor calidad/expresividad cuando haya GPU y se justifique. Confirma y precisa ADR-0008.

## Justificación (criterios del acta D24)

- **Rendimiento:** síntesis rápida en CPU; adecuado al presupuesto de latencia (TTS ≤300ms, 2.5 §5.1).
- **Mantenimiento:** modelos ONNX simples de gestionar.
- **Comunidad:** activa; usado en Home Assistant (sinergia con 6.3).
- **Portabilidad:** Linux/macOS/Windows.
- **Integración:** tras el contrato de voz (6.2); voces en español disponibles.
- **Largo plazo:** open source; evolucionable a XTTS por contrato sin rediseño.

## Impacto (acta D11)

| Dimensión | Impacto |
|---|---|
| Seguridad | Positivo: síntesis local |
| Privacidad | Positivo: voz local |
| Modularidad | Positivo: tras el contrato de voz; XTTS futuro por sustitución |
| Costo | Bajo: gratis |
| Experiencia de usuario | Voz natural en español (2.4 §6) |
| Mantenimiento futuro | Positivo: ligero y sustituible |

## Trazabilidad

Capítulos: 6.2 (voz), 2.4 §6 (voz base español). Confirma ADR-0008. Producción: Piper con voz es_ES/es_MX.
