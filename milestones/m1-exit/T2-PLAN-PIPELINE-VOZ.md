---
documento: "T2 — Plan del pipeline de voz (STT + TTS + interrupciones)"
version: 1.0.0
autor: "CTO"
fecha: "2026-07-20"
estado: "Propuesta — pendiente de autorización del CEO. NO se ha escrito código."
---

# T2 — Plan del pipeline de voz

> **Hallazgo que condiciona el encuadre:** T2 se autorizó como *deuda técnica de M1*. La validación del
> STT sí es deuda. **Las interrupciones (barge-in) no lo son: son alcance de RF-2 que nunca se
> construyó.** No hay captura de micrófono, ni VAD, ni cancelación de audio en el código. Llamarlo
> "validación" ocultaría que es un desarrollo nuevo de tamaño medio. Ver §6 para la propuesta de alcance.

## 1. Qué existe actualmente del pipeline de voz

| Componente | Estado real | Evidencia |
|---|---|---|
| **TTS Piper** | ✅ **Funciona** | `piper-tts` 1.5.0 instalado; voz `es_MX-ald-medium` (63 MB) en USB; WAV válido generado (PCM 16-bit mono 22050 Hz) |
| **TTS integrado en el orquestador** | ✅ Funciona | `voice_real.py::tts()` → subprocess Piper; ejercitado en la demo oficial |
| **STT `faster-whisper`** | ❌ **No instalado** | `import faster_whisper` falla. ADR-0012 aceptado pero **nunca validado** |
| **STT en el adaptador** | ⚠️ Código escrito, nunca ejecutado | `_stt_sync()` existe; solo se activa si `audio_ref` es un `.wav` existente |
| **Ruta real usada hasta hoy** | *passthrough* de texto | La demo pasa texto, no audio: `stt()` devuelve la cadena tal cual |
| **Captura de micrófono** | ❌ **No existe** | Ninguna línea de código captura audio |
| **VAD (detección de voz)** | ❌ No existe | — |
| **Barge-in / cancelación** | ❌ No existe | `tts()` es un `subprocess.run(...)` **bloqueante**: no es interrumpible |
| **Canales dedicados de baja latencia** | ❌ No implementados | Diseñados en ALERTA-001/3.2, sin código |
| **Contrato formal de voz** | ❌ **No existe** | `contracts.py` define `EventBus`, `MemoryStore`, `ModelProvider` y `Adapter`. **No hay Protocol de voz**: `stt`/`tts` son convención |

**Hardware verificado:** micrófono presente (`ALC257 Analog`, PipeWire, `alsa_input` disponible).
**Dependencias de audio en Python:** ninguna instalada (`sounddevice`, `soundfile`, `webrtcvad` ausentes).

## 2. Qué falta para cumplir T2

Requisitos de la Bible (2.5 RF-2, 6.2 §2):

| Requisito | Objetivo | Estado |
|---|---|---|
| STT local operativo | ADR-0012 | ❌ sin instalar |
| Captura + VAD | ≤150 ms | ❌ inexistente |
| STT streaming | ≤250 ms | ❌ inexistente |
| Primer audio TTS | ≤300 ms | ⚠️ no medido |
| **Barge-in** | **≤300 ms** | ❌ inexistente |
| Voz español latino | 2.4 §6 | ✅ cumplido |
| Privacidad del micrófono | 6.2 §4 | ❌ sin diseño ni control |

## 3. Cambios que requieren ÚNICAMENTE validación

Trabajo acotado y de bajo riesgo — no altera arquitectura:

| # | Tarea | Detalle |
|---|---|---|
| V1 | Instalar `faster-whisper` + modelo | Modelo `base` int8 al USB (D31). **Aviso: 616 MB libres**, margen mínimo |
| V2 | Validar transcripción real | WAV conocido → texto; medir latencia de STT |
| V3 | Validar TTS integrado extremo a extremo | Ya funciona; falta **medir** el tiempo al primer audio (≤300 ms) |
| V4 | Eval de cadena de voz | STT(audio) → núcleo → TTS(audio), con aserciones que no puedan pasar por *passthrough* |

**V4 es crítica por la lección de T1:** la ruta actual de `stt()` devuelve el texto de entrada sin
transcribir nada. Una eval mal escrita pasaría sin que Whisper llegue a ejecutarse. La aserción debe
partir de un **WAV real** y verificar que el texto proviene de la transcripción.

## 4. Cambios que requieren IMPLEMENTACIÓN NUEVA

| # | Componente | Por qué es nuevo | Tamaño |
|---|---|---|---|
| I1 | **Contrato formal de voz** (`VoiceAdapter` Protocol) | No existe; toda la interfaz siguiente depende de él | Pequeño |
| I2 | **Captura de micrófono** | Ninguna línea de código captura audio | Medio |
| I3 | **VAD** | Detectar inicio/fin de habla | Medio |
| I4 | **TTS cancelable** | `subprocess.run` bloqueante → no interrumpible. Requiere reemplazarlo por proceso gestionado con cancelación | Medio |
| I5 | **Orquestación de barge-in** | Coordinar "usuario habla → callar en ≤300 ms" | Medio |
| I6 | **Canales dedicados** (ALERTA-001) | El bus no puede sostener 300 ms de barge-in | Medio-Alto |
| I7 | **Controles de privacidad del micrófono** (6.2 §4) | Micrófono siempre-escucha sin diseño de consentimiento ni corte | Medio |

**Dependencias nuevas requeridas** (sujetas a D26 — justificación de beneficio medible):
`faster-whisper`, `sounddevice` o `pyaudio`, `soundfile`, `webrtcvad`.

## 5. Riesgos arquitectónicos

**RA-1 — Micrófono siempre-escucha (el mayor riesgo del hito).** I2+I3 convierten a AURA en un sistema
que captura audio del entorno de forma continua. Es la superficie de privacidad más sensible del
proyecto y toca directamente el pilar local-first (ADR-0001) y el guardarraíl de no-vigilancia
(ALERTA-002). **Recomendación: diseñar el control de privacidad y su integración con el kill switch
ANTES de escribir la captura**, no después. Mismo orden que hizo que M1 terminara en verde.

**RA-2 — Definir el contrato antes que la implementación.** No existe Protocol de voz. Si se implementa
streaming y cancelación sin contrato previo, la interfaz se fijará por accidente. La disciplina de
ADR-0014 (contratos del Core primero) exige I1 antes que I2-I5.

**RA-3 — El barge-in no cabe sobre el bus de eventos.** ALERTA-001 ya resolvió que los streams van por
canales dedicados. Implementar barge-in sobre el bus reintroduciría el problema que esa alerta cerró.
I6 es prerrequisito arquitectónico de I5, no un extra.

**RA-4 — El TTS actual es incancelable por diseño.** `subprocess.run(...)` no admite interrupción. I4
no es un ajuste: es sustituir el mecanismo de invocación de Piper.

**RA-5 — Espacio.** 616 MB libres en el USB principal. El modelo Whisper entra, pero sin margen para
artefactos de audio de las pruebas. `swapfile_aurora` sigue ocupando 4 GB sin prestar servicio.

**RA-6 — Buena noticia:** el barge-in **no depende del LLM**. Mide el tiempo entre voz detectada y
audio detenido, sin inferencia por medio. **Es medible en este hardware**, a diferencia de HC-1. Es la
primera métrica de latencia de la Bible que sí podemos validar aquí.

## 6. Tiempo estimado y propuesta de alcance

Estimación en **sesiones de trabajo**, no en días de calendario. Cada iteración con stack real cuesta
minutos de máquina, lo que limita el ritmo.

| Bloque | Contenido | Estimación |
|---|---|---|
| **T2.a — Validación STT** | V1, V2, V3, V4 | **1-2 sesiones** |
| **T2.b — Contrato de voz** | I1 | **0,5 sesión** |
| **T2.c — Captura + VAD + privacidad** | I2, I3, I7 | **2-3 sesiones** |
| **T2.d — TTS cancelable + barge-in** | I4, I5 | **2-3 sesiones** |
| **T2.e — Canales dedicados** | I6 | **2-3 sesiones** |
| **Total si T2 abarca todo** | | **8-12 sesiones** |

### Recomendación del CTO

**Dividir T2 en dos decisiones separadas:**

1. **T2 (deuda técnica de M1) = T2.a + T2.b.** Cierra ADR-0012 —aceptado y nunca validado—, formaliza el
   contrato de voz y cuesta **1,5-2,5 sesiones**. Es genuinamente deuda: algo que se dio por hecho y no
   se verificó.

2. **Barge-in y captura (T2.c/d/e) = alcance propio, con su gate.** Son **8-10 sesiones**, introducen la
   superficie de privacidad más delicada del proyecto y tocan la arquitectura de canales. Tratarlos como
   "deuda técnica" los metería por la puerta de atrás, sin el escrutinio que un cambio de este calibre
   merece.

Mi recomendación es **autorizar T2.a + T2.b ahora** y decidir el resto como hito propio — antes o
después de M2, según prefieras priorizar. Si el objetivo es que AURA sea usable durante un día entero,
el barge-in pesa más que las manos digitales; si el objetivo es demostrar acción real, M2 va primero.

**No se ha escrito ninguna línea de código.**
