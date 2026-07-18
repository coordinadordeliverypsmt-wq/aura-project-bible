---
numero: ADR-0011
titulo: "Base de datos vectorial para la memoria (confirmación con análisis)"
estado: accepted
fecha: 2026-07-18
fecha-resolucion: 2026-07-18
decisor: "Mauricio (CEO)"
proponente: "Fable (CTO)"
impacta: ["4.1","3.5","3.6"]
origen: "Acta D24 (stack local-first, análisis comparativo por ADR)"
reabre: "—"
supersede: "—"
superseded-por: "—"
motivo-rechazo: "—"
---

# ADR-0011 — Base de datos vectorial para la memoria (confirmación con análisis)

## Contexto

La memoria (4.1) requiere búsqueda vectorial (RAG). ADR-0007 eligió Qdrant a nivel Balanceado; el acta D24 exige análisis comparativo open source antes de adoptar definitivamente. Conforme al acta D24, se elige entre alternativas **open source y autoalojables**, sin claves de terceros, con análisis comparativo por los seis criterios exigidos por el CEO.

## Alternativas consideradas (open source)

| Opción | Pros | Contras |
|---|---|---|
| **Qdrant** | Rust, rápido; filtrado avanzado; modo embebido o servidor; Apache-2.0; buena comunidad; autoalojable | Un servicio más que operar |
| **pgvector** | Reutiliza PostgreSQL (ya en ADR-0007): **un motor menos** (regla 13 ADR-0004); SQL + vectores juntos | Rendimiento vectorial menor que motores dedicados a gran escala |
| Chroma | Python-nativo, fácil | Menos maduro a escala; menos filtrado |
| Milvus | Muy potente y escalable | Pesado (etcd/MinIO); sobredimensionado para 1 usuario |
| Weaviate | Rico en features | Más pesado |
| FAISS | Librería rapidísima | Sin persistencia/filtrado listos; más integración |

## Decisión

**Qdrant** se confirma como base vectorial primaria por su rendimiento y filtrado, en modo embebido para el despliegue local. **pgvector** se registra como **alternativa ligera oficial**: para despliegues de huella mínima reutiliza el PostgreSQL de ADR-0007 y evita un servicio extra (regla 13). El walking skeleton en hardware objetivo puede comparar ambos; el contrato de memoria (4.1) es idéntico para los dos.

## Justificación (criterios del acta D24)

- **Rendimiento:** Qdrant lidera en búsqueda+filtrado; pgvector suficiente a escala de 1 usuario.
- **Mantenimiento:** pgvector = un motor menos; Qdrant = servicio autoalojable simple.
- **Comunidad:** ambas fuertes y open source.
- **Portabilidad:** Qdrant embebido y pgvector corren en Linux/macOS/Windows.
- **Integración:** ambos tras el contrato de 4.1; intercambiables (P-ARQ-4).
- **Largo plazo:** sin lock-in; Qdrant escala mejor, pgvector simplifica.

## Impacto (acta D11)

| Dimensión | Impacto |
|---|---|
| Seguridad | Positivo: datos locales cifrados |
| Privacidad | Positivo: local (ADR-0001) |
| Modularidad | Positivo: tras el contrato de memoria |
| Costo | Bajo: gratis |
| Experiencia de usuario | Positivo: recuperación semántica rápida |
| Mantenimiento futuro | Positivo: pgvector reduce servicios |

## Trazabilidad

Capítulos: 4.1 (memoria), 3.5/3.6. Confirma y matiza ADR-0007. Producción: Qdrant embebido (o pgvector en huella mínima).
