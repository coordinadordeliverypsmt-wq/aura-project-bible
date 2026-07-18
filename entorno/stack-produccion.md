---
documento: "Stack de Producción de AURA (local-first, open source)"
version: 1.0.0
autor: "Fable (CTO)"
fecha: 2026-07-18
estado: "Vinculante"
---

# Stack de Producción de AURA — local-first, open source (acta D24)

Todos los componentes son **gratuitos, open source y autoalojables**, sin claves de terceros ni dependencia de proveedores (D24). Los modelos de nube (D2) son recursos **opcionales** tras el router (4.2); el camino por defecto y de validación es **local**. El mismo código de AURA no cambia entre entornos — solo varía la preparación (scripts en `scripts/`).

## Componentes oficiales

| Capa | Componente | ADR | Licencia | Puerto/Modo |
|---|---|---|---|---|
| Lenguaje/runtime | **Python 3.11+** | ADR-0005 | PSF | — |
| Event Bus | **NATS** (`nats-server`) + `nats-py` | ADR-0006 | Apache-2.0 | 4222 |
| LLM local | **Ollama** + modelo cuantizado (p. ej. `qwen2.5:3b` / `llama3.2:3b`) | ADR-0010 | MIT / open weights | 11434 |
| Memoria vectorial | **Qdrant** (embebido) — o **pgvector** en huella mínima | ADR-0011 | Apache-2.0 / PostgreSQL | embebido / 6333 |
| STT | **faster-whisper** (modelo `base`/`small`) | ADR-0012 | MIT | in-proc |
| TTS | **Piper** + voz `es_*` | ADR-0013 | MIT | in-proc |
| Base de datos | **SQLite** (local) / **PostgreSQL** (escala) | ADR-0007 | Dominio público / PostgreSQL | archivo / 5432 |
| Avatar | **Live2D** (fase posterior) | ADR-0009 | — | — |

## Requisitos mínimos por componente

| Componente | CPU | RAM | Almacenamiento | SO | Dependencias |
|---|---|---|---|---|---|
| NATS server | 1 core | ~50 MB | ~20 MB (binario) | Linux/macOS/Windows | ninguna (binario estático) |
| Ollama + modelo 3B (Q4) | 4 cores (GPU opcional) | **~4-6 GB** para el modelo | ~3-4 GB por modelo | Linux/macOS/Windows | Ollama runtime |
| faster-whisper (base) | 2-4 cores | ~2 GB | ~150 MB (modelo base) | multiplataforma | CTranslate2 (pip) |
| Piper (voz es) | 1-2 cores | ~300 MB | ~60 MB por voz | multiplataforma | onnxruntime (pip) |
| Qdrant embebido | 1 core | ~200 MB | según memoria | multiplataforma | qdrant-client (pip) |
| Python + libs AURA | — | ~300 MB | ~500 MB (venv) | 3.11+ | ver requirements |

**Hardware recomendado para el sistema completo (R1 CPU-only):** ≥ 4 cores, **≥ 12 GB RAM**, ~8 GB de almacenamiento libre.
**Hardware objetivo para R2 (P50 ≤ 800 ms):** GPU (≥ 6-8 GB VRAM) o CPU de gama alta con modelo cuantizado optimizado.

> **Nota de entorno (proactiva, D24):** el entorno de job actual (2 cores, ~1 GB RAM libre, sin GPU) **está por debajo** del mínimo para Ollama/Whisper. Por eso HC-1 queda **Pendiente de validación en entorno objetivo**. Estos scripts preparan un equipo que sí cumpla los mínimos.

## Descargas que realizan los scripts (avisadas por adelantado)

- **Ollama runtime** (~ pocos cientos de MB) + **1 modelo LLM** (~2-4 GB, la descarga más grande).
- **nats-server** binario (~6 MB).
- **Modelo faster-whisper `base`** (~150 MB) y **voz Piper es** (~60 MB) — se descargan al primer uso.
- **Paquetes pip** (nats-py, faster-whisper, piper-tts, qdrant-client) en un venv.

Total aproximado de descarga: **~3-5 GB** (dominado por el modelo LLM). Todo local tras la instalación; sin llamadas a terceros en ejecución.
