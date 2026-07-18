---
numero: ADR-0010
titulo: "Runtime de inferencia de LLM local"
estado: accepted
fecha: 2026-07-18
fecha-resolucion: 2026-07-18
decisor: "Mauricio (CEO)"
proponente: "Fable (CTO)"
impacta: ["4.2","3.6"]
origen: "Acta D24 (stack local-first, análisis comparativo por ADR)"
reabre: "—"
supersede: "—"
superseded-por: "—"
motivo-rechazo: "—"
---

# ADR-0010 — Runtime de inferencia de LLM local

## Contexto

La orquestación (4.2) necesita un motor de inferencia local para modelos abiertos, que sea el camino por defecto y de validación (D24), sin depender de APIs de nube. Los modelos de nube (D2) quedan como recursos opcionales tras el mismo contrato. Conforme al acta D24, se elige entre alternativas **open source y autoalojables**, sin claves de terceros, con análisis comparativo por los seis criterios exigidos por el CEO.

## Alternativas consideradas (open source)

| Opción | Pros | Contras |
|---|---|---|
| **Ollama** | DX excelente; API compatible con OpenAI (encaja en el contrato del router 4.2); registro de modelos; multiplataforma (Linux/macOS/Windows); CPU+GPU; comunidad muy activa; envuelve llama.cpp; Apache-2.0 | Ligera sobrecarga vs llama.cpp puro; opinado |
| llama.cpp | Máximo rendimiento y control; mínimas dependencias; cuantización GGUF; edge/CPU | Bajo nivel; más trabajo de integración y de servidor HTTP |
| vLLM | Alto throughput; excelente en GPU | Orientado a GPU y servidor; pesado; sobredimensionado para 1 usuario local/CPU |
| LocalAI | API OpenAI; multi-backend | Más pesado y menos pulido; más superficie de mantenimiento |
| GPT4All / LM Studio | Fáciles de escritorio | Orientados a GUI; menos scriptables/headless para servidor |

## Decisión

**Ollama** como runtime de LLM local oficial. Expone una API compatible con OpenAI que encaja directamente en el contrato de proveedor del router (4.2), por lo que los modelos locales y los de nube (D2) comparten el mismo adaptador. **llama.cpp** queda como ruta de optimización de bajo nivel (Ollama lo envuelve) si una medición lo justifica.

## Justificación (criterios del acta D24)

- **Rendimiento:** bueno en CPU con modelos cuantizados; escala a GPU sin cambiar la integración.
- **Mantenimiento:** actualizaciones y gestión de modelos triviales (`ollama pull`); un solo servicio.
- **Comunidad:** de las más activas del ecosistema local; amplio catálogo de modelos.
- **Portabilidad:** binario nativo Linux/macOS/Windows; el mismo código de AURA no cambia.
- **Integración:** API OpenAI-compatible = cero fricción con el router 4.2 y sustituible (P-ARQ-4).
- **Largo plazo:** open source, sin lock-in; permite cambiar de modelo o a llama.cpp por contrato.

## Impacto (acta D11)

| Dimensión | Impacto |
|---|---|
| Seguridad | Positivo: inferencia local, sin enviar datos a la nube (ADR-0001) |
| Privacidad | Positivo máximo: refuerza local-first |
| Modularidad | Positivo: tras el contrato del router; sustituible |
| Costo | Bajo: gratuito; costo = hardware propio |
| Experiencia de usuario | Depende del hardware; en GPU cumple R2 ≤800ms |
| Mantenimiento futuro | Positivo: un servicio, actualizaciones simples |

## Trazabilidad

Capítulos: 4.2 (el router lo usa como proveedor local), 3.6 (stack). Reemplaza la dependencia de claves de nube para el baseline (D24). Producción: servicio Ollama local.
