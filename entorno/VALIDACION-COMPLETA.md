---
documento: "Runbook — Validación completa de AURA en tu máquina"
version: 1.0.0
autor: "Fable (CTO)"
fecha: 2026-07-18
estado: "Vinculante"
---

# Runbook — Validación completa de AURA (stack real, local, en tu máquina)

Instrucciones de cero a resultado HC-1. **100 % local y open source, sin claves de terceros** (D24). El código de AURA no cambia entre plataformas.

## 0. Prerrequisitos

- **Python ≥ 3.11**. **RAM ≥ 12 GB** (R1 CPU) o **GPU ≥ 6-8 GB** (R2). ~8 GB de disco libre.
- Internet solo para instalar y descargar modelos (una vez); luego, offline.
- macOS: Homebrew. Windows: winget (o descargas manuales — ver Entorno de Desarrollo).

## 1. Obtener el proyecto

```bash
cd ~/Documentos/AURA/aura-project-bible          # o donde clones el repo
```

## 2. Instalar el stack (elige tu SO)

```bash
# Linux
bash entorno/scripts/install-linux.sh
# macOS
bash entorno/scripts/install-macos.sh
# Windows (PowerShell)
powershell -File entorno\scripts\install-windows.ps1
```

Esto instala: venv + librerías (nats-py, faster-whisper, piper-tts, qdrant-client), el binario **nats-server**, **Ollama**, y descarga el **modelo LLM** (`qwen2.5:3b` por defecto; ~2-4 GB — la descarga mayor).

## 3. Descargar la voz de Piper (español) — paso puntual

La voz no viene en el paquete pip. Descarga una voz en español del repo oficial de Piper y anota su ruta:

```bash
mkdir -p entorno/voces && cd entorno/voces
# Voz es_MX (o es_ES) del repo oficial rhasspy/piper-voices en HuggingFace:
curl -fLO https://huggingface.co/rhasspy/piper-voices/resolve/main/es/es_MX/ald/medium/es_MX-ald-medium.onnx
curl -fLO https://huggingface.co/rhasspy/piper-voices/resolve/main/es/es_MX/ald/medium/es_MX-ald-medium.onnx.json
cd ../..
export AURA_PIPER_VOICE="$PWD/entorno/voces/es_MX-ald-medium.onnx"   # Windows: $env:AURA_PIPER_VOICE=...
```

## 4. Arrancar los servicios

```bash
nats-server -p 4222 &                 # o entorno/.bin/nats-server
ollama serve &                         # si no corre ya como servicio
ollama list                            # confirma que el modelo esta descargado
```

## 5. Verificar el entorno (gate OBLIGATORIO)

```bash
bash entorno/scripts/verify-stack.sh   # Windows: verify-stack.ps1
# NO continues hasta ver: "STACK OPERATIVO — listo para el Walking Skeleton"
```

## 6. Quality Gate (calidad del código, debe PASS)

```bash
source entorno/.venv/bin/activate                      # Windows: .venv\Scripts\activate
pip install -r walking-skeleton/requirements-dev.txt   # ruff, mypy, pytest
bash walking-skeleton/quality-gate.sh                  # espera: QUALITY GATE: PASS
```
En tu máquina, las **pruebas del stack real** (que aquí se saltan) se ejecutarán porque Ollama/NATS estarán arriba.

## 7. Ejecutar el Walking Skeleton

```bash
cd walking-skeleton
# (a) Sanity con bus real + LLM mock (rapido, valida el flujo):
python3 run_demo_nats.py
# (b) VALIDACION HC-1 con stack REAL (NATS + Ollama + Whisper + Piper):
python3 run_demo_real.py --text "Enciende la luz de la sala" --iterations 30
#     con audio real (mide STT tambien):
python3 run_demo_real.py --audio /ruta/a/muestra.wav --iterations 30
```

## 7.bis Validación oficial de M1 con registro automático de métricas

```bash
pip install -r walking-skeleton/requirements-validacion.txt   # psutil (opcional, D26)
cd walking-skeleton
# Demostracion oficial de M1 (producto, principio a fin):
python3 demo_capacidad_m1.py --real
# Arnes de metricas (registra latencia/CPU/RAM/almacenamiento/errores -> resultados-m1.json):
python3 validar_m1.py --real --iterations 50 --text "Enciende la luz de la sala"
#   con audio real (mide STT): python3 validar_m1.py --real --audio muestra.wav --iterations 50
```
`resultados-m1.json` contiene: latencia por etapa (STT/LLM/TTS), e2e P50/P95, recursos (CPU/RAM/almacenamiento) antes/despues, y estabilidad (errores/recuperaciones). **Compártelo** para el cierre de M1.

## 8. Interpretar el resultado HC-1

`run_demo_real.py` imprime la latencia por etapa (STT/LLM/TTS) y de extremo a extremo (P50/P95), y compara contra:

- **R1 (CPU local): P50 ≤ 1200 ms** → objetivo del baseline reproducible.
- **R2 (GPU/optimizado): P50 ≤ 800 ms**.

**HC-1 se marca Validado** cuando el P50 cumple el umbral de su release de forma sostenida (N ≥ 50). Si **no** se cumple: **no se ajusta el umbral en silencio** — el CTO levanta una **Alerta de Arquitectura (D15)** con el análisis (p. ej. modelo más pequeño, GPU, o streaming por etapas para solapar STT→LLM→TTS y bajar la latencia percibida por debajo de la suma).

## 9. Solución de problemas

| Síntoma | Causa probable | Acción |
|---|---|---|
| `verify-stack` marca Ollama FAIL | servicio no arrancado / sin modelo | `ollama serve &` ; `ollama pull qwen2.5:3b` |
| STT lento / OOM | modelo Whisper grande o poca RAM | usar modelo `base`/`small`; cerrar apps |
| Piper falla | voz no descargada o `AURA_PIPER_VOICE` sin definir | repetir §3 y exportar la variable |
| NATS no conecta | server no corriendo | `nats-server -p 4222 &` |
| P50 alto en CPU | modelo grande / sin GPU | modelo 3B cuantizado; considerar R2 con GPU |

## 10. Qué NO cambiar

No modifiques `aura_skeleton/` para "arreglar" el entorno: todas las diferencias de plataforma viven en `entorno/`. Cualquier cambio de arquitectura o de contrato requiere ADR (1.2). Toda funcionalidad nueva se integra con sus pruebas (Plan de Calidad y Validación).
