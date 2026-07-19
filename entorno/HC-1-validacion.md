---
documento: "Procedimiento de validación de HC-1 en entorno objetivo"
version: 1.0.0
autor: "Fable (CTO)"
fecha: 2026-07-18
estado: "Vinculante"
---

# HC-1 — Validación de latencia en entorno objetivo (local, sin proveedores)

**Estado de HC-1:** *Pendiente de validación en entorno objetivo* (acta D24). No es un fallo: el entorno de job actual no tiene el hardware mínimo (Ollama/Whisper). Este procedimiento valida HC-1 en un equipo que cumpla los mínimos de `stack-produccion.md`, **100% local y open source**.

## Objetivos (acta HC-1)

- **R1 (baseline local en CPU):** P50 de inicio de respuesta hablada ≤ **1200 ms**.
- **R2 (hardware optimizado / GPU):** P50 ≤ **800 ms**.

## Requisitos

Equipo con ≥ 4 cores y ≥ 12 GB RAM (R1 CPU) o GPU ≥ 6-8 GB VRAM (R2). Stack instalado y verificado (abajo).

## Pasos

```bash
# 1. Instalar el stack (elige tu SO)
bash entorno/scripts/install-linux.sh        # o install-macos.sh / install-windows.ps1

# 2. Arrancar servicios
nats-server -p 4222 &                          # o el binario en entorno/.bin/
ollama serve &                                 # si no corre como servicio

# 3. Verificar que TODO esta operativo (gate previo, obligatorio)
bash entorno/scripts/verify-stack.sh           # debe decir "STACK OPERATIVO"

# 4. Ejecutar el Walking Skeleton con el stack REAL y medir latencia
python3 walking-skeleton/run_demo_real.py --iterations 50   # (proxima entrega: sustituye los mocks por STT/LLM/TTS reales)
```

## Qué se mide

Por turno, latencia de extremo a extremo (fin de habla → inicio de respuesta hablada) y por etapa: STT (faster-whisper), primer token del LLM (Ollama), TTS (Piper), bus (NATS). Se reportan P50/P95 sobre N iteraciones y se comparan contra R1 ≤ 1200 ms / R2 ≤ 800 ms. Registro automatico (2.2 §3.4), sin intervencion subjetiva.

## Condicion de validez: sin swapping

Antes de dar por buena cualquier medicion, comprueba en `resultados-m1.json` que **`"medicion_valida": true`** y **`"hubo_swapping": false`**. El swap (archivo/mmc/USB) es mucho mas lento que la RAM: si la inferencia entra en swap, los numeros no representan el rendimiento real y **la medicion no es valida**. Repite liberando RAM o con mas memoria fisica. Ver la salvedad en `stack-produccion.md`.

## Criterio de cierre de HC-1

HC-1 se marca **Validado** cuando, en el hardware objetivo, el P50 cumple el umbral de su release (R1 o R2) de forma sostenida sobre N≥50 turnos. El resultado se registra en un CEO Executive Summary y, si un umbral no se alcanza, se levanta una Alerta de Arquitectura (D15) en vez de ajustar silenciosamente.

## Nota

`run_demo_real.py` (sustitucion de los mocks de STT/LLM/TTS por faster-whisper/Ollama/Piper tras el **mismo contrato**) es la proxima entrega de construccion; el bus real (NATS) ya esta integrado en `run_demo_nats.py`.
