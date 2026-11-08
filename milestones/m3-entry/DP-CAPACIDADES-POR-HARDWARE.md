---
documento: "Decision Package — Capacidades por hardware (sobre de capacidad, ADR-0021/0020)"
tipo: "DECISION PACKAGE — BORRADOR. NO APROBADO. Prepara la decisión D46 por capacidad; no la toma."
fecha: 2026-09-29
autor: "APUS-5 (CTO)"
estado: "DECISION_REQUIRED"
depende_de: "DetectorHardwareLocal (implementado 2026-09-29, ADR-0021 accepted) · RESULTADO-CM1-HW-ACCEL.md · kit_cm1_HC-1.json"
---

# DP — Capacidades por hardware

## 1. Qué existe ya (no se propone construirlo)

- **Arquitectura (ADR-0021 y ADR-0020, accepted):** Registry + Capability Manager puro (INV-1) + `PerfilHardware`
  (métricas, sin marcas) + estados ACTIVA / DEGRADADA / LATENTE. Elección «por capacidad EFECTIVA», bidireccional.
- **Detector real (2026-09-29).** `DetectorHardwareLocal` mide `ram_mb`, `ram_disponible_mb`, `nucleos`, `isa_*`,
  `carga_1m`, `disco_libre_mb` y `gpu_render`. `--verificar` en HC-1 [EJEC]: `ram_mb=3719, nucleos=2, isa_avx2=0,
  isa_sse4_2=1, gpu_render=1`.
- **Catálogo:** UNA capacidad, `memoria` (N1 si `ram_mb` < 8000, N2/N3 por encima). Es la única que hoy se adapta
  sola al hardware.

## 2. El hueco

La voz y el razonamiento local **se eligen por variables de entorno** (`AURA_WHISPER_MODEL`, `AURA_TTS_MOTOR`,
`AURA_LLM_MODEL`), no por el sobre medido.
- En HC-1 eso funciona porque alguien fijó a mano lo que cabe.
- En un equipo mejor, **AURA no usaría lo que tiene**: seguiría con los mismos valores hasta que un humano los cambie.
- En uno peor, arrancaría algo que no cabe. Ejemplo medido: `qwen2.5:3b` en HC-1 agotó 600 s en swap.

Esto contradice el principio del CEO («funciona con el hardware que tiene y aprovecha automáticamente más
capacidad»).

## 3. Propuesta: tres capacidades nuevas en el catálogo (una decisión D46 por cada una)

Cada una se declara con los diez campos de ADR-0021. El Manager decide su estado; la composición solo consume
`plan.decision(...)`. **Las variables de entorno siguen mandando si se fijan**, porque la decisión explícita del usuario
prevalece; lo nuevo es el defecto cuando no se fijan.

| Capacidad | ACTIVA (promoción) | DEGRADADA (piso) | Umbral: de dónde sale |
|---|---|---|---|
| **razonar_local** (tamaño del modelo) | modelo 3B si `ram_mb` ≥ R3 | 0.5B | [cálculo]: el modelo entero en RAM junto al sistema. [medido]: 3B en 3,6 GB colapsa (swap, 600 s); 0.5B funciona (146 s/turno) |
| **transcribir_voz** (modelo Whisper) | `base` si hay GPU CUDA o una PRUEBA de STT ≤ T ms | `tiny` / `base` según la precisión medida | [medido]: base 6,6-11 s y tiny 3-6,8 s en HC-1; la precisión de tiny es peor (5/15 frente a 6/15) |
| **sintetizar_voz** (motor TTS) | Piper si una PRUEBA de TTS ≤ S ms | Piper igualmente (**espeak NO es el piso automático**: su regresión de calidad la decide el usuario) | [medido]: Piper 0,3-3,4 s en HC-1; espeak 0,6-5 ms con WER ~2× |

**R3, T y S no se proponen como constantes arquitectónicas.** La regla del CEO lo prohíbe si no son derivables. Se
proponen como:
- **R3**: tamaño del fichero del modelo + consumo base medido de AURA + margen. Se **calcula** en el arranque a partir de
  lo instalado, no es una cifra fija.
- **T y S**: se derivan del presupuesto de CM1 (§8.2 de `entorno/ANALISIS-PLATAFORMA-OBJETIVO-R1.md`: STT ≤ 150 ms,
  TTS ≤ 100 ms). Exigen **pruebas reales** (`Fuente.PRUEBA`, D44).

## 4. La parte D44 (pruebas de rendimiento propias)

Para que AURA sepa **qué puede hacer** y no solo **qué tiene**, necesita medirse. Propuesta:
- se reutilizan las mediciones del kit (`kit_cm1.py`);
- se ejecutan **bajo demanda** (`--medir-capacidad`) o una sola vez por cambio de hardware (huella del perfil);
- **nunca en cada arranque**: en HC-1 costaría ~30-60 s [medido: carga de Piper 6,6 s y de Whisper 4,8-6,9 s].

El resultado se guarda como métricas en `AURA_DATOS`. No se guarda audio: la voz de prueba es sintética y vive en
memoria.

## 5. Efecto esperado [HIPÓTESIS: debe medirse]

- **HC-1:** nada cambia en la práctica. Todo queda como hoy (0.5B, Whisper base, Piper), pero ahora es **decidido y
  declarado** por el Manager en `--verificar`, no fijado a mano.
- **Equipo con más RAM, AVX2 o GPU:** AURA sube de modelo o de nivel **sola**, y lo declara. La aceptación de CM1 sigue
  siendo el E2E de §8.5.

## 6. Riesgos

- **Decisiones que oscilan:** usar métricas estables (`ram_mb`, ISA, GPU) y no volátiles (`carga_1m`,
  `ram_disponible_mb`) en las reglas.
- **Subir de modelo sin haberlo verificado:** la promoción exige que el modelo esté INSTALADO (sondeo de Ollama existente)
  y, para la voz, una PRUEBA superada. Sin prueba no hay promoción.
- **Choque con decisiones previas:** el acta D-3 fija «`qwen2.5:0.5b` no se cambia ni se agranda» por iniciativa propia.
  **Esta capacidad sí lo cambiaría** en equipos con más RAM. Por eso es una **decisión del CEO**, no una
  implementación directa.

## 7. Decisión requerida

1. ¿Se aprueban **razonar_local**, **transcribir_voz** y **sintetizar_voz** como capacidades del catálogo (D46),
   con la regla «el entorno manda si se fija; si no, decide el Manager»?
2. Para **razonar_local**: ¿se autoriza que el Manager promueva el modelo por encima de 0.5B cuando el hardware lo
   soporte? Esto enmienda el límite del acta D-3 **solo** en equipos que lo soporten.
3. ¿Se autoriza la medición propia **bajo demanda** (§4), con resultados en `AURA_DATOS` y sin audio?

Hasta que se decida, **no se toca el catálogo**. El detector ya aporta el conocimiento del sobre sin cambiar ninguna
decisión.
