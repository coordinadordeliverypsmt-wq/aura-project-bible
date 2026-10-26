# Salidas de consola literales — bloque CM1 iGPU + TTS (2026-09-29, HC-1)

Estas mediciones `[EJEC]` se ejecutaron en esta sesión e imprimieron por consola sin guardar fichero. Aquí se
transcribe su salida **literal**. Los arneses que las produjeron están en `../arneses/`. Condiciones: HC-1
(Celeron N4020, 2 núcleos, solo SSE4.2), Firefox abierto (~60 % de CPU), sin swap.

## Dispositivos OpenVINO (OpenVINO 2026.4.0 + NEO 23.43 extraído sin root) — `env.sh`
```
OV devices: ['CPU', 'GPU']
name Intel(R) UHD Graphics 600 (iGPU)
DEVICE_ARCHITECTURE GPU: vendor=0x8086 arch=v9.4.0
OPTIMIZATION_CAPABILITIES ['FP32', 'BIN', 'FP16', 'EXPORT_IMPORT']
GPU_DEVICE_TOTAL_MEM_SIZE 3194462208
GPU_EXECUTION_UNITS_COUNT 12
DEVICE_TYPE Type.INTEGRATED
```

## Level Zero
```
zeInit 0x78000001
Violación de segmento (`core' generado)   <- zeDriverGet tras un zeInit fallido; exit 139
```
`0x78000001` = `ZE_RESULT_ERROR_UNINITIALIZED`: no hay driver L0 para Gen9.5 en este runtime.

## Piper en OpenVINO CPU — `probe_ov.py CPU`
```
[    3.0s] read [('input', <PartialShape: [?,?]>), ('input_lengths', <PartialShape: [?]>), ('scales', <PartialShape: [3]>)]
[   10.7s] compiled
[   76.2s] infer0 65462 ms out=[1,1,1,8192]
[  128.2s] infer1 52002 ms out=[1,1,1,7424]
[  183.2s] infer2 54992 ms out=[1,1,1,7680]
```

## Perfil OpenVINO CPU con forma fija (noise_w=0) — `probe_ov2.py CPU`
```
infer0 50471 ms out=[1,1,1,6912]
infer1 52027 ms out=[1,1,1,6912]
infer2 58484 ms out=[1,1,1,6912]
    53309.8 ms  Convolution            ref_any_f32
      114.8 ms  Convolution            jit_sse42_f32
       48.3 ms  ConvolutionBackpropData jit_gemm_f32
       15.7 ms  Convolution            jit_sse42_1x1_f32
```
Banderas ISA de la CPU (`/proc/cpuinfo`, filtradas a sse4_2/avx/avx2/avx512f/fma/f16c): `sse4_2` únicamente.

## Piper en la iGPU — `probe_ov.py GPU`
```
RuntimeError: ... [GPU] ProgramBuilder build failed!
[GPU] clWaitForEvents, error code: -14 CL_EXEC_STATUS_ERROR_FOR_EVENTS_IN_WAIT_LIST
```

## Modelo mínimo (una conv1d dilatada 192x192x3) — `probe_gpu_min.py`
```
OpenVINO 2026.4:                   CPU OK 9.56 ms/infer | GPU: clFinish -5 CL_OUT_OF_RESOURCES (abort)
OpenVINO 2024.6:                   CPU OK 12.27 ms/infer | GPU FALLA
OpenVINO 2026.4 + NEOReadDebugKeys=1 ForcePreemptionMode=2: CPU OK 9.06 ms/infer | GPU FALLA
```
Los 4 GPU HANG correspondientes están en `kernel_i915_gpu_hang.log`.

## Latencia de E/S por el aire (tono de 1 kHz, 6 repeticiones) — `probe_io.py`
```
play=None rec=None: p50=2002 ms min=1953 max=2007 (6/6)
play=None rec=20: p50=96 ms min=74 max=171 (6/6)
play=30 rec=20: p50=85 ms min=74 max=96 (6/6)
```
Servidor: `PulseAudio (on PipeWire 1.0.5)`.

## Silencio inicial del audio de espeak (voz es, 175 ppm)
```
Entendido.                     dur=0.61s silencio_inicial=0 ms
Te llamas Mauricio.            dur=1.01s silencio_inicial=33 ms
No tengo ningún recuerdo regis dur=2.62s silencio_inicial=0 ms
¿Sí?                           dur=0.32s silencio_inicial=4 ms
```

## Turno determinista del orquestador con TTS espeak (AURA_DATOS temporal) — `probe_orq.py`
```
componer 476 ms
'¿Cómo me llamo?'                p50=   16.6 ms  prov=core dom=modelo_usuario est=hecho say='Te llamas Mauricio.'
'¿Cuál es mi color favorito?'    p50=   17.5 ms  prov=core dom=modelo_usuario est=ausencia
'¿Qué hora es?'                  p50=   18.0 ms  prov=core dom=memoria est=ausencia
'¿Qué día es hoy?'               p50=   25.7 ms  prov=core dom=memoria est=ausencia
'¿Cuánto es tres por cuatro?'    p50=   26.8 ms  prov=core dom=memoria est=ausencia
```

## Decodificador Vosk small, audio limpio sin micrófono, bloques de 20 ms — `probe_decod.py`
```
libre     ¿Cuál es mi color favorito?  audio=2.79s RTF=0.38 FinalResult=81 ms -> 'cuál es mi color favorito'
libre     Me llamo Mauricio.           audio=2.56s RTF=0.38 FinalResult=55 ms -> 'me llamo mauricio'
libre     ¿Cómo me llamo?              audio=2.20s RTF=0.44 FinalResult=158 ms -> 'tuvo media hago'
gramatica ¿Cuál es mi color favorito?  audio=2.85s RTF=0.09 FinalResult=32 ms -> 'cuál es mi color favorito'
gramatica Me llamo Mauricio.           audio=2.43s RTF=0.12 FinalResult=49 ms -> 'me llamo mauricio'
gramatica ¿Cómo me llamo?              audio=2.16s RTF=0.09 FinalResult=21 ms -> 'cómo me llamo'
```
Trampa comprobada: con `json.dumps(gramatica)` sin `ensure_ascii=False`, Vosk avisa
`Ignoring word missing in vocabulary: 'cuál'` y descarta «cuál»/«cómo».

## Captura + fin de habla + decodificación por el aire (código de producto v1) — `probe_orden.py`
«fin_persona_a_retorno_ms» = desde el último sonido de la persona hasta que `escuchar_orden` devuelve el texto.
```
hang=300 ¿Cuál es mi color favorito? -> 'cuál es'            (corte prematuro, 2/2)
hang=300 Me llamo Mauricio.          -> 'me llamo por eso'   706 / 1739 ms
hang=300 ¿Cómo me llamo?             -> 'me hago'            1398 / 1281 ms
hang=450 ¿Cuál es mi color favorito? -> 'cuál es el color favorito' 772 ms; 'cuál es mi color favorito' 1317 ms
hang=450 Me llamo Mauricio.          -> 'me llamo por eso' 687 ms; 'me llamo eso' 2160 ms
hang=450 ¿Cómo me llamo?             -> 'me hago' 943 ms; 'okay hago' 1078 ms
```

## Ruido ambiente al final de la sesión (5 s, solo RMS)
```
RMS ambiente 5 s: p10=932 p50=1882 p90=4496 max=8188  | tramas >1000: 86%
referencia en los turnos buenos del arnés: ruido ~390-455
```
Por eso `e2e_v2_favorable2.json` se declara **contaminado** y no se usa para el veredicto.
