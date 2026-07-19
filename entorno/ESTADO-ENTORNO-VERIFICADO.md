---
documento: "Estado verificado del entorno de ejecucion"
version: 1.0.0
autor: "Fable (CTO)"
fecha: 2026-07-19
estado: "Vigente — verificado en el momento de generar el reporte"
---

# Estado verificado del entorno — 2026-07-19 14:45

> **Politica (CEO, 2026-07-19):** todo informe de entorno se basa en una **verificacion ejecutada al generar el reporte**, nunca en estados historicos. Este documento se re-verifica antes de cada uso.

## 1. Hardware y recursos (verificado)

| Recurso | Valor medido | Minimo documentado (stack-produccion.md) | Cumple |
|---|---|---|---|
| CPU | 2 nucleos | >= 4 nucleos (R1) | **NO** |
| RAM fisica | 3,6 GB (1,5 GB disponibles) | **>= 12 GB (R1)** | **NO** |
| GPU | ninguna | opcional (necesaria para R2) | n/a |
| Disco libre | **892 MB (99% usado)** | ~8 GB libres | **NO** |
| Swap | `/swapfile` 4 GB (1,8 GB en uso), en disco **interno** | red de estabilidad, no sustituye RAM | — |
| USB `/dev/sda1` | 7,5 GB, presente y **sin usar** | — | — |

## 2. Stack real (verificado)

| Componente | Estado |
|---|---|
| **Ollama** | **INSTALADO y respondiendo en :11434** |
| **Modelo `qwen2.5:3b`** | **DESCARGADO (1,9 GB)** |
| psutil, nats (cliente py), qdrant-client | instalados |
| faster-whisper (STT) | **NO instalado** |
| piper (TTS) | **NO instalado** |
| nats-server (binario) | **NO instalado** (:4222 no responde) |

## 3. Medicion real de referencia (evidencia)

**Una sola inferencia** con `qwen2.5:3b` via Ollama en esta maquina: **> 120.000 ms** (supero el limite de 120 s sin completar).

- Objetivo HC-1 R1: **P50 <= 1.200 ms**. La medicion observada esta **~100x por encima**.
- Causa: 2 nucleos, 3,6 GB de RAM con 1,8 GB ya en swap, sin GPU. El modelo (1,9 GB) no cabe holgadamente en RAM disponible -> swapping durante la inferencia.
- **Por la regla aprobada, una medicion con swapping no es valida**; ademas, esta maquina **no cumple el minimo documentado**, por lo que **no constituye una prueba de HC-1**.

## 4. Conclusion operativa

- **HC-1 NO puede validarse en esta maquina.** Permanece *Pendiente de validacion en hardware objetivo* (>= 12 GB RAM; GPU para R2).
- **La validacion completa del stack real tampoco puede ejecutarse aqui:** faltan faster-whisper, piper y nats-server, y el disco (892 MB libres) no admite instalarlos con sus modelos con margen seguro.
- **Riesgo activo:** disco al 99%. Un disco lleno ya provoco la perdida de `validar_m1.py` (truncado y comprometido vacio). Antes de instalar nada mas o someter el sistema a carga, **liberar espacio** (el USB de 7,5 GB esta libre y sin usar).
- **Si utilizable ahora:** evals de comportamiento del LLM real (`evals_m1.py --real`), que son validas aunque sean lentas (miden conducta, no latencia). Coste estimado: varios minutos por llamada.
