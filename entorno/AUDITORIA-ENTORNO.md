---
documento: "Auditoría del Entorno de Instalación"
version: 1.0.0
autor: "Fable (CTO)"
fecha: 2026-07-18
estado: "En revisión (gate del CEO)"
---

# Auditoría del Entorno de Instalación (previa a run_demo_real.py)

## Alcance y honestidad del método

Esta auditoría combina: **(a)** revisión estática de los scripts `install-*` / `verify-*`; **(b)** verificación de cada paquete contra su **fuente oficial** (API JSON de PyPI, releases de GitHub, sitios oficiales); **(c)** prueba en vivo de las partes instalables en este entorno (pip de paquetes puros). **No pude ejecutar** los instaladores completos de macOS/Windows (no hay esas plataformas aquí) ni Ollama/modelos (2 CPU, ~1 GB RAM, sin GPU). Esos puntos quedan verificados por documentación oficial, no por ejecución — se declara explícitamente.

## 1. Fuentes oficiales (verificado)

| Dependencia | Fuente oficial | Verificación |
|---|---|---|
| Python | python.org / gestor del SO | — |
| nats-py | PyPI `nats-py` v2.15.0 (Apache-2.0) | ✅ API PyPI |
| nats-server | GitHub `nats-io/nats-server` releases (binario firmado) | ✅ descargado y ejecutado (v2.10.22) |
| Ollama | ollama.com (install.sh / .dmg / .exe) · brew · winget | ⚠️ documental (no ejecutable aquí) |
| faster-whisper | PyPI `faster-whisper` v1.2.1 + `ctranslate2` v4.8.1 | ✅ API PyPI |
| Piper | PyPI `piper-tts` v1.5.0 (wheels Linux/macOS/Windows) + voces del repo oficial | ✅ API PyPI |
| qdrant-client | PyPI `qdrant-client` v1.18.0 | ✅ instalado e importado aquí |

**Sin sorpresas de nombres:** todos los paquetes existen con el nombre usado en los scripts. **Corrección aplicada:** el mínimo real de Python es **3.11** (onnxruntime 1.27 lo exige); `stack-produccion.md` y requirements actualizados.

## 2. Automatizable al 100 % vs intervención manual

| Componente | Linux | macOS | Windows | Nota |
|---|---|---|---|---|
| Python + venv + pip libs | **Auto** | **Auto** | **Auto** | pip desde PyPI oficial |
| nats-server | **Auto** (descarga binario) | Auto (brew) | Semi (winget o descarga manual) | winget ID no verificable desde aquí → fallback manual documentado |
| Ollama runtime | Semi (`curl \| sh`) | Semi (brew + arrancar) | Semi (winget/.exe) | ver §4 seguridad de `curl\|sh` |
| Modelo LLM (`ollama pull`) | **Auto** | **Auto** | **Auto** | requiere Ollama corriendo |
| Modelo faster-whisper | **Auto** (1er uso, repos HF oficiales) | Auto | Auto | descarga única, cacheada |
| Voz Piper | **Manual/scriptable** | Manual/scriptable | Manual/scriptable | la voz `.onnx` se descarga aparte del repo oficial |
| GPU (CUDA/Metal) | Manual (drivers NVIDIA) | Auto (Metal) | Manual (drivers NVIDIA) | opcional; CPU funciona |

**Conclusión:** el 100 % automatizable son Python/libs, nats-server (Linux), modelo LLM y modelo Whisper. Requieren intervención puntual: prerrequisito de Homebrew (macOS), winget/EXE (Windows), arranque del servicio Ollama, descarga de la voz Piper y drivers GPU. Todo está documentado en el **Entorno de Desarrollo v1.0** con el comando exacto.

## 3. Riesgos detectados y resoluciones

- **`curl -fsSL https://ollama.com/install.sh | sh`** (Linux) ejecuta un script remoto. Resolución "cero sorpresas": el Entorno de Desarrollo ofrece la **alternativa auditable** (descargar el instalador, inspeccionarlo y ejecutarlo), y fija la versión.
- **winget puede no existir** en Windows anteriores a 10/11 actualizados. Resolución: fallback de descarga manual del `.exe`/`.zip` oficial (ya en el script y documentado).
- **Voz Piper no viene en el wheel.** Resolución: script/pasos para descargar la voz `es_MX`/`es_ES` del repo oficial de Piper.
- **Descargas en primer uso** (modelos Whisper/LLM) necesitan internet una vez; tras eso, **100 % offline** (coherente con local-first). No son APIs de terceros: son repos de modelos abiertos.

## Veredicto

Los scripts instalan desde fuentes oficiales y son correctos para las partes verificables. Con las correcciones aplicadas (Python 3.11, pins verificados, voz Piper y fallbacks documentados), el entorno es **reproducible**. La ejecución real de los instaladores por plataforma debe confirmarse en cada equipo objetivo con `verify-stack`, que es el gate previo obligatorio.
