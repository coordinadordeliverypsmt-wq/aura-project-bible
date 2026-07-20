---
documento: "T2 — Resultado (T2.a validación STT + T2.b contrato de voz)"
version: 1.0.0
autor: "CTO"
fecha: "2026-07-20"
estado: "Completada"
---

# T2 — Resultado

Alcance autorizado: **T2.a** (validación STT) y **T2.b** (contrato `VoiceAdapter`).
Captura de micrófono, VAD, barge-in y canales dedicados **quedan fuera**, como hito independiente.

## T2.b — Contrato `VoiceAdapter` formalizado

`contracts.py` define ahora un Protocol `runtime_checkable` para voz. Hasta hoy `stt`/`tts` eran
**convención tácita** entre el mock y la implementación real.

Pruebas de contrato: **el mock y `WhisperPiperVoice` cumplen el mismo Protocol.** Esa segunda
comprobación es la que da valor al contrato — garantiza que sustituir el doble por el stack real no
altera la interfaz que consume el orquestador.

Se definió **antes** de cualquier implementación de captura o barge-in (riesgo RA-2 del plan): de otro
modo la interfaz habría quedado fijada por accidente. El docstring deja constancia de que streaming y
cancelación serán una **extensión versionada**, no una ruptura (ADR-0004).

## T2.a — Validación del STT: bucle cerrado TTS → STT

| Etapa | Resultado |
|---|---|
| Piper sintetiza | `resp_t2a.wav`, 199.724 bytes, **10.134 ms** |
| Whisper transcribe | **50.659 ms** |
| Similitud | **89%** (8/9 palabras), umbral 70% |
| **Veredicto** | **PASS** |

> Original: *"Hola, soy AURA, tu sistema operativo de inteligencia personal"*
> Transcrito: *"Hola, soy **ahora** tu sistema operativo de inteligencia personal."*

**ADR-0012 queda validado.** Estaba aceptado desde el 2026-07-18 y nunca se había ejecutado.

### Diseño anti-passthrough

La entrada de `stt()` es una **ruta a WAV**, no texto: la rama de *passthrough* del adaptador ni se
toca. Además hay aserción explícita de que el resultado no sea la ruta recibida. Sin estas dos
salvaguardas, la validación habría pasado sin que Whisper llegara a ejecutarse — el defecto exacto que
la auditoría T1 erradicó.

## Hallazgo: el STT no reconoce el nombre del producto

El único error de transcripción fue **"AURA" → "ahora"**. No es anecdótico:

- El sistema se llama AURA y la conversación por voz es su interfaz principal.
- Cualquier futura palabra de activación (*wake word*) chocará con esta confusión fonética: en español
  latino, "AURA" y "ahora" son casi homófonas.
- Afecta también a la memoria: si el usuario dice *"AURA, recuerda esto"*, el núcleo recibirá "ahora".

**No se corrige aquí** (fuera del alcance autorizado). Se registra como entrada para el hito de
conversación continua, donde deberá decidirse entre *prompt* inicial de Whisper con vocabulario propio,
un modelo mayor, o una palabra de activación fonéticamente distinta.

## Latencias observadas (no válidas como métrica)

STT de **50.659 ms** para ~4 s de audio, frente al objetivo de **≤250 ms** (6.2 §2). Mismo origen que
HC-1: hardware por debajo del mínimo. No se abre alerta — D24 ya gobierna este escenario.

## Estado

Quality Gate **PASS**: 49 pruebas + 6 contratos (1 saltada: el bucle cerrado tarda ~60 s y no corre por
defecto; se activa con `AURA_TEST_VOZ_REAL=1`).

**T2 CERRADA.** Deuda técnica de M1 saldada: T1 ✅ · T2 ✅ · HC-1 documentado como riesgo (D24).
