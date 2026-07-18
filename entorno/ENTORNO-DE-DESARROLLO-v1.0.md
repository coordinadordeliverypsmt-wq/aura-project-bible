---
documento: "Entorno de Desarrollo de AURA (v1.0)"
version: 1.0.0
autor: "Fable (CTO)"
fecha: 2026-07-18
estado: "En revisión (gate del CEO)"
---

# Entorno de Desarrollo de AURA — v1.0

Guía única para cualquier desarrollador nuevo. Todo el stack es **local-first, open source y sin claves de terceros** (acta D24). **El código de AURA no cambia entre plataformas**: solo cambia la preparación del entorno (§4).

## 0. Requisitos generales

- **Python ≥ 3.11** (obligatorio; onnxruntime lo exige).
- **Hardware:** R1 (CPU) ≥ 4 cores y ≥ 12 GB RAM; R2 (latencia ≤800 ms) GPU ≥ 6-8 GB VRAM. ~8 GB de disco (modelos).
- **Internet:** solo para instalar y descargar modelos una vez; en ejecución, offline.

## 1. Instalación rápida

```
# Linux
bash entorno/scripts/install-linux.sh && bash entorno/scripts/verify-stack.sh
# macOS (requiere Homebrew)
bash entorno/scripts/install-macos.sh && bash entorno/scripts/verify-stack.sh
# Windows (PowerShell)
powershell -File entorno\scripts\install-windows.ps1 ; powershell -File entorno\scripts\verify-stack.ps1
```

`verify-stack` es el **gate obligatorio**: no se ejecuta el Walking Skeleton hasta que diga "STACK OPERATIVO".

## 2. Dependencias — instalar / actualizar / desinstalar / verificar

### Python + librerías de AURA
- **Instalar:** `python3 -m venv .venv && source .venv/bin/activate && pip install -r entorno/scripts/requirements-stack.txt` (Windows: `.venv\Scripts\activate`).
- **Actualizar:** `pip install -U -r entorno/scripts/requirements-stack.txt`.
- **Desinstalar:** borrar la carpeta `.venv/`.
- **Verificar:** `python -c "import nats, faster_whisper, qdrant_client, piper; print('libs OK')"`.

### NATS server (Event Bus, ADR-0006)
- **Instalar:** Linux → binario de GitHub releases (lo hace el script); macOS → `brew install nats-server`; Windows → `winget install Synadia.NATS.Server` o descarga del release oficial.
- **Actualizar:** reemplazar el binario por el release nuevo; macOS `brew upgrade nats-server`.
- **Desinstalar:** borrar el binario; macOS `brew uninstall nats-server`.
- **Verificar:** `nats-server --version` y `verify-stack` comprueba el puerto 4222.

### Ollama (LLM local, ADR-0010)
- **Instalar:** Linux → `curl -fsSL https://ollama.com/install.sh | sh` (alternativa auditable: descargar el script, revisarlo, ejecutarlo); macOS → `brew install ollama` o el `.dmg` oficial; Windows → `winget install Ollama.Ollama` o el `.exe` de ollama.com/download/windows.
- **Actualizar:** re-ejecutar el instalador; macOS `brew upgrade ollama`. Modelos: `ollama pull <modelo>`.
- **Desinstalar:** Linux → `sudo rm /usr/local/bin/ollama` y `~/.ollama`; macOS → quitar la app y `~/.ollama`; Windows → desinstalar desde Configuración y borrar `%USERPROFILE%\.ollama`.
- **Verificar:** `ollama --version`; `ollama list` (debe mostrar el modelo); `curl http://127.0.0.1:11434/api/tags`.

### faster-whisper (STT, ADR-0012)
- **Instalar:** `pip install faster-whisper` (incluido en requirements). El modelo (`base`/`small`) se descarga al primer uso desde los repos oficiales de HuggingFace.
- **Actualizar:** `pip install -U faster-whisper`.
- **Desinstalar:** `pip uninstall faster-whisper ctranslate2`; borrar caché de modelos (`~/.cache/huggingface`).
- **Verificar:** `python -c "from faster_whisper import WhisperModel; print('whisper OK')"`.

### Piper (TTS, ADR-0013)
- **Instalar:** `pip install piper-tts` (incluido). **La voz se descarga aparte** (una sola vez): voz `es_MX`/`es_ES` del repo oficial de voces de Piper a `entorno/voces/`.
- **Actualizar:** `pip install -U piper-tts`; voces nuevas del repo oficial.
- **Desinstalar:** `pip uninstall piper-tts onnxruntime`; borrar `entorno/voces/`.
- **Verificar:** `python -c "import piper; print('piper OK')"` y existencia del `.onnx` de voz.

### Qdrant (memoria vectorial, ADR-0011)
- **Instalar:** `pip install qdrant-client` (modo **embebido**, sin servidor). Alternativa: servidor Qdrant vía binario oficial, o **pgvector** sobre PostgreSQL.
- **Actualizar:** `pip install -U qdrant-client`.
- **Desinstalar:** `pip uninstall qdrant-client`; borrar el directorio de datos embebido.
- **Verificar:** `python -c "from qdrant_client import QdrantClient; QdrantClient(':memory:'); print('qdrant OK')"`.

### SQLite / PostgreSQL (datos, ADR-0007)
- SQLite: incluido en Python (stdlib), sin instalación. PostgreSQL (opcional, escala): gestor del SO; `pip install "psycopg[binary]"`.

## 3. Qué es 100 % automatizable vs manual

Ver `AUDITORIA-ENTORNO.md §2`. Resumen: **auto** = Python/libs, nats-server (Linux), modelos LLM y Whisper. **Manual/puntual** = Homebrew (macOS), winget/EXE (Windows), arranque de Ollama, voz Piper, drivers GPU.

## 4. Incompatibilidades entre plataformas (y su resolución SIN tocar el código de AURA)

| Diferencia | Resolución (fuera del código de AURA) |
|---|---|
| Activación de venv (`bin/` vs `Scripts\`) | Los scripts por SO la manejan; el código usa solo imports relativos |
| NATS: binario (Linux) vs servicio (macOS/Win) | AURA siempre conecta a `nats://127.0.0.1:4222`; el transporte es idéntico |
| Ollama: instalador distinto por SO | El **endpoint es idéntico** (`127.0.0.1:11434`) en las 3 plataformas → AURA no cambia |
| GPU (CUDA/Metal/none) | faster-whisper y Ollama detectan el dispositivo (`device=auto`); es configuración, no código |
| Fin de línea CRLF vs LF | `.gitattributes` normaliza; los `.sh` se mantienen LF |
| Rutas de datos/caché | Se derivan de variables del SO; AURA usa rutas relativas del proyecto |

**Principio:** las diferencias viven en `entorno/`, nunca en `aura_skeleton/`. Es la aplicación de la Evolución Permanente (ADR-0004) al entorno.

## 5. Política de "cero sorpresas" (acta D24)

Si en cualquier etapa se detecta que hará falta una herramienta/librería/servicio nuevo, el CTO lo informa de inmediato: **qué**, **por qué**, **en qué fase**, **cómo se instala** y **si es automatizable**, y prepara el script antes de que bloquee. Ninguna dependencia entra sin este aviso previo.

## 6. Siguiente paso

Con este entorno aprobado y verificado (`verify-stack` = OPERATIVO en el equipo objetivo), se autoriza construir `walking-skeleton/run_demo_real.py` (adaptadores reales tras los **mismos contratos**, sin tocar la arquitectura) y validar HC-1 según `HC-1-validacion.md`.
