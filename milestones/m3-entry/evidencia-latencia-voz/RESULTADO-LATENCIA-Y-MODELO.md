# Latencia de voz y evaluación del modelo local — resultado (2026-10-04)

**Estado:** latencia implementada y verificada (TDD, mutación 8/8, Quality Gate PASS). **Modelo: NO se cambia**
(orden del CEO «NO CAMBIES EL MODELO TODAVÍA»; además la evidencia no lo justifica). E2E físico de latencia pendiente.

## 1 · Hardware medido — HC-1 `[EJEC]`

| Recurso | Valor |
|---|---|
| CPU | Intel Celeron N4020, 2 núcleos, 800–2800 MHz, **solo SSE4.2 (sin AVX/AVX2/FMA)** |
| RAM | 3719 MB (+ swap); **~2,2 GB disponibles** con Firefox cerrado, ~1,0 GB con Firefox abierto |
| GPU | UHD 600 (sin aceleración útil para el LLM; ver DP-CM1-HW-ACCEL) |
| Ollama | 0.32.1 |

## 2 · Perfil de latencia del turno de voz (antes) — del E2E físico `../evidencia-voz-accion/e2e-fisico-2026-10-04.jsonl` `[EJEC]`

«¿Sí?» → respuesta final ≈ **29 s**:

| Etapa | Coste | Causa |
|---|---|---|
| Grabación de la orden | ~9 s | duración fija de 5 s + síntesis del «¿Sí?» en cada turno (~2 s) + arranque de `paplay` |
| STT (Whisper base int8) | ~3 s | carga perezosa del modelo en el primer turno (~4,5 s adicionales) |
| Home Assistant (orden) | ~7 s | TV Samsung (red + TV), fuera del control de AURA |
| Verificación + TTS | ~10 s | relectura del efecto en HA + Piper |

**El LLM no está en la ruta voz→TV.** La orden, el «sí» y «¿qué hiciste?» los resuelve el Core
(`hogar.py`, ADR-0014). Por tanto **cambiar de modelo no acelera ese camino**.

## 3 · Cambios implementados

| Cambio | Ahorro | Garantía (mutante) |
|---|---|---|
| Captura con fin de habla (`Microfono.escuchar_hasta_silencio`): corta tras 700 ms de silencio una vez hay ≥250 ms de habla; sin voz espera 5 s (igual que antes); tope 6 s | hasta ~3–4 s por turno | VL-M1, M3, M4, M5, M6 |
| Solo en escucha continua (con «Oye Aurora»); pulsar-para-hablar conserva la duración fija | — | VL-M2 |
| «¿Sí?» sintetizado una vez y reutilizado (sin escritura extra en disco: G-1 R-B = 0) | ~2 s por activación | VL-M7 |
| Precarga de Whisper y Piper al arrancar (4,5–4,8 s antes de «AURA está atenta») | ~10 s en el primer turno | VL-M8 |
| `paplay --latency-msec=30` | arranque del audio | — |
| Trazas `[LAT]` de acuse, captura (con motivo de corte) y turno | medible en el E2E | — |
| Nombre humano en la propuesta y en la respuesta («la TV de la sala»); el `entity_id` sigue siendo el argumento del Motor Único | experiencia | pruebas de nombres |

## 4 · Benchmark del modelo — `herramientas/benchmark_llm_ollama.py`, en serie, sin presión de memoria `[EJEC]`

Prompt de sistema fijo, `temperature=0`, mismas 7 frases. Frío = tras descargar el modelo (`keep_alive=0`).

| Métrica | qwen2.5:0.5b (instalado) | qwen2.5:1.5b |
|---|---|---|
| Tamaño en disco / cuantización | 397 MB · Q4_K_M | 986 MB · Q4_K_M |
| Primera respuesta en frío | 37,4 s (carga 8,1 s) | 38,0 s (carga 8,3 s) |
| Respuesta en caliente | **6,1–15,7 s** | 7,9–23,9 s |
| Generación | **2,7–3,1 tok/s** | 1,9–2,3 tok/s |
| RAM usada del sistema (mín → máx) | 1433 → 1938 MB (**+~0,5 GB**) | 1460 → 2582 MB (**+~1,1 GB**) |
| Swap | sin crecimiento | sin crecimiento |
| «enciende la televisión» | «¡Por supuesto! Enciende la televisión…» | **«¡Listo! La televisión está encendida.»** (falso) |
| «¿qué hiciste?» | evasiva | «No hice nada específico.» |
| Pregunta general | correcta | correcta, algo más precisa |

**La primera medición de 0.5b (`benchmark-llm-qwen2.5-0.5b.json`) NO es comparable:** se tomó con ~1,0 GB
disponibles (Firefox abierto) y salió 2–4 veces más lenta. La comparable es `…-0.5b-sin-presion.json`.

**qwen2.5:3b no se midió de nuevo:** la medición previa en HC-1 colapsó en swap a los 600 s, y con ~2,2 GB
disponibles su peso (~1,9 GB) no deja margen para Whisper + Piper + HA. Descargarlo no aporta evidencia nueva.

## 5 · Decisión del modelo

1. **¿Subir de modelo?** No.
2. **¿A cuál?** A ninguno ahora. El único candidato viable es 1.5b.
3. **¿Por qué?** El 1.5b es ~30 % más lento, usa el doble de RAM y **fabrica acciones** («¡Listo! La televisión
   está encendida.»), que es justo lo que INV-9 prohíbe. Además el LLM no está en la ruta voz→TV.
4. **¿Qué ganaríamos?** Respuestas generales algo mejores y más concisas.
5. **¿Qué perderíamos?** ~0,6 GB de RAM de margen, ~1 tok/s y un riesgo mayor de afirmaciones falsas convincentes.
6. **¿Latencia?** Empeora en conversación general; no cambia en voz→TV.
7. **¿Margen de hardware?** Para 1.5b sí (sin swap). Para 3b no.
8. **¿Modelo pequeño para rutas rápidas?** Sí, pero la ruta rápida real es **sin modelo**: el Core determinista
   ya resuelve hogar, confirmación y «¿qué hiciste?», y el «¿Sí?» no consulta memoria ni LLM.
9. **¿Decisión familiar o arquitectónica?** Solo si se quisiera cambiar el modelo por defecto (`aura-voz.sh` /
   `composicion.py`, D-3). Hoy no se propone.

**Observación técnica (no deuda):** `composicion.py` declara `qwen2.5:3b` por defecto y HC-1 usa 0.5b vía
`aura-voz.sh`; la discrepancia ya se detecta al arrancar (`composicion.py:430`). Se promovería a deuda si algún
arranque sin `aura-voz.sh` llegara a usar el LLM en HC-1.

## 6 · Ficheros

- `benchmark-llm-qwen2.5-0.5b-sin-presion.json`, `benchmark-llm-qwen2.5-1.5b.json` — medición comparable.
- `memoria-benchmark-*.txt` (muestras `free -m` cada 10 s: usada / swap), `ollama-list.txt` (tamaños).
- `benchmark-llm-qwen2.5-0.5b.json` — medición con presión de memoria (histórica, no comparable).
- Mutación: `walking-skeleton/mutaciones/voz-latencia.toml` (VL-M1..M8, 8/8).
- Pruebas: `walking-skeleton/tests/unit/test_voz_latencia.py` (21).

---

## 7 · CIERRE DEL BLOQUE — 2026-10-06 `[EJEC]`

### 7.1 Baseline y estado optimizado

- **Baseline:** E2E del 2026-10-04 (`../evidencia-voz-accion/e2e-fisico-2026-10-04.jsonl`), turnos «apaga»:
  - orden: trace 65182787;
  - «sí»: trace ff914ce3.
- **Optimizado:** E2E del 2026-10-06 (`e2e-latencia-2026-10-06.jsonl`), con el mismo arnés, AURA real, HA real, la TV de la
  sala y voz humana por el aire:
  - orden: trace 93c52cc6;
  - «sí»: trace 5fe19100.

**Corrección del §2:** la cifra de «~3 s de STT» de la base se midió desde el aviso «sigo trabajando», que no es el fin de la
captura. El STT real es de ~5,5 s en ambas mediciones. La comparación válida es la de la tabla siguiente.

### 7.2 Medición por etapas — turno «sí» del 2026-10-06 (marcas del arnés, reloj de pared)

| Marca | Hora | Δ desde T1 |
|---|---|---|
| T0 inicio de la interacción («Oye Aurora») | no se registra por separado: Vosk la detecta y T1 es su primera marca | — |
| T1 activación («¿Sí?» impreso) | 09:18:15.500 | 0 |
| T2 inicio de captura / fin de captura (`corte=silencio`) | 09:18:16.061 / 09:18:19.100 | 0,56 s / 3,60 s |
| T3 STT («¿Sí?», no_habla=0,009) | 09:18:24.618 | 9,12 s (STT = 5,52 s) |
| T4 resolución de la intención (la propuesta pendiente se confirma) | 09:18:24.646 (sin marca propia; coincide con T5) | 9,15 s |
| T5 autorización (`lista verde … auto-ejecucion`) | 09:18:24.646 | 9,15 s (T3→T5 = 28 ms) |
| T6 llamada a HA (`EJECUTA turn_off`) | 09:18:26.276 | 10,78 s (T5→T6 = 1,63 s) |
| T7 efecto físico (HA leído por el arnés: `off`) | 09:18:26.658 | 11,16 s |
| T8 verificación (`on -> off (verificado=True)`) | 09:18:26.280 | 10,78 s (T6→T8 = 4 ms) |
| T9 respuesta generada (texto impreso tras Piper) | 09:18:27.765 | 12,27 s (TTS = 1,46 s) |
| T10 fin de la respuesta hablada (`respuesta ms=4174`) | 09:18:31.940 | **16,44 s** |

T7 y T8 casi coinciden porque el arnés sondea HA cada pocos cientos de ms. El efecto físico ocurre entre T6 y T7.

### 7.3 Delta frente al baseline (mismos turnos «apaga»)

| Etapa | Orden: base → hoy | «Sí»: base → hoy |
|---|---|---|
| «¿Sí?» → micrófono abierto | 1,12 → 0,53 s | 1,07 → 0,56 s |
| Captura + STT | 11,26 → 10,40 s (captura 4,68 + STT 5,72) | 11,65 → 8,56 s (captura 3,04 + STT 5,52) |
| Síntesis de la respuesta | 3,66 → 1,30 s | 5,16 → 1,49 s |
| **«¿Sí?» → respuesta (texto)** | **16,07 → 12,26 s (−3,8 s)** | **19,29 → 12,26 s (−7,0 s, −36 %)** |
| «¿Sí?» → fin de la respuesta hablada (T10) | no medido en la base | 15,85 s / 16,44 s |

La síntesis más corta se debe a que la respuesta ya no recita el `entity_id`
(«Listo: la TV de la sala está apagada; lo he comprobado.»).

### 7.4 Criterio de latencia (CM1, Bible: P50 ≤ 800 ms de fin de habla al inicio de la respuesta) — NO CUMPLE

- **Medición:** de corte de captura a respuesta, 7,05 / 8,66 / 7,02 / 7,28 s (4 turnos con `corte=silencio`), **P50 = 7,17
  s**.
- **Fin de habla:** por diseño el corte llega 0,7 s después del fin de habla (`_SILENCIO_FINAL_MS = 700`; el JSONL no registra el fin de habla), así que el P50 de fin de habla a respuesta es ≈ **7,9 s** `[INFER]`.
- **Veredicto:** **No cumple.** La mejora es real, pero mejorar no es cumplir. El criterio no se toca (CEO, 2026-09-28).
- **Cuello de botella:**
  - **STT, Whisper base int8:** ~5,5 s por turno sobre un Celeron N4020 sin AVX. Lo controla AURA, pero solo se reduce
    cambiando el modelo de STT (`tiny` ≈ 2,2× más rápido con menos precisión, medido el 2026-09-27) o el hardware. Ambas son
    decisiones ya registradas (D-3 / vía 3, `DP-CAPACIDADES-POR-HARDWARE.md` §7). No se tocan en este bloque.
  - **Hogar:** HA y la TV aportan 1,6 s en el apagado. El encendido es más lento porque depende del arranque de la TV.
  - **TTS:** ya no es significativo (~1,4 s).
  - **Hardware:** el bloqueo nº 1 del Master Map sigue igual.

### 7.5 Resultado físico

- **On→off por voz** («Oye Aurora» → «apaga la televisión» → «Oye Aurora» → «sí»): ejecutado por el Motor Único y releído en
  HA. La respuesta usa el nombre humano.
- **El ciclo de encendido no se completó:** la propuesta «Voy a encender la TV de la sala» quedó sin «sí».
  - La TV pasó a `on` a las 09:18:47 **sin orden de AURA**. La auditoría forense de AURA registra **una sola acción**
    (`turn_off`).
  - **Coincidencia temporal:** el cambio llegó 1,25 s después de que AURA propusiera «Voy a encender» (09:18:46.544, trace
    d50f8c63) y antes de cualquier «sí». La propuesta no ejecuta (0 `EJECUTA turn_on` en el JSONL).
  - El contexto de HA de ese cambio no tiene `user_id`: el cambio no llegó por la API autenticada que usa AURA. Se infiere el
    mando o la propia TV `[INFER]`.
- **Activación espuria:** a las 09:20:20 hubo una activación sin acción, probablemente el audio de la TV. AURA se cerró
  durante su STT. No ejecutó nada.
- **Estado final:** TV encendida, igual que al inicio. Arnés y AURA cerrados.
- **Encendido por voz completo:** ya demostrado el 2026-10-04 (21:35:53).

### 7.6 Robustez

Pruebas existentes de los 13 casos del bloque: 144/144 en verde, según la auditoría independiente.

La auditoría señaló 5 huecos en el camino hablado, que se cerraron con pruebas nuevas en
`tests/integration/test_voz_accion_opcion_c.py`:
- «sí» sin propuesta;
- TV de la llave inexistente en HA;
- TV `unavailable`;
- PARADA armada antes de la orden;
- turno vacío sin tocar HA.

Mutación `mutaciones/voz-robustez-cierre.toml`: **4/4**. El turno vacío lo protege VE-M5 (`voz-e2e-fisico.toml`), comprobado
aislado contra la prueba nueva el 2026-10-06: detectado.

**Identidad desconocida:** no existe identificación del hablante en este camino. Es la capacidad R3 «Identificación por voz»,
nivel 1, bloqueada por la DECISIÓN B. No es un hueco de pruebas ni de este bloque.

Sin regresiones: Quality Gate PASS.

### 7.7 Modelo

- **qwen2.5:1.5b:** evaluado (§4) y **no viable**: más lento, el doble de RAM, y fabrica acciones.
- **Referencias:** solo en esta evidencia y en el CHECKPOINT. Ninguna en código, configuración, scripts, servicios ni pruebas.
- **Eliminado** con `ollama rm qwen2.5:1.5b` el 2026-10-06. El almacén `~/.ollama/models` pasó de 1 383 872 032 a 397 822 176
  bytes: **986 049 856 bytes liberados**.
- **Modelo vigente:** `qwen2.5:0.5b`, verificado después de la eliminación (responde) y declarado en el arranque del E2E
  («modelo: qwen2.5:0.5b»).

### 7.8 Calidad

| Comprobación | Resultado |
|---|---|
| Quality Gate | **PASS**: 3046 passed, 1 skipped, 1 xfailed, 0 failed; ruff limpio; mypy sin errores en 89 ficheros; contratos 8/8 |
| Mutación `voz-latencia.toml` | **9/9**. Incluye VL-M9 (traza T10, añadida por TDD en este cierre) |
| Mutación `voz-robustez-cierre.toml` | **4/4** |
| Mutación `voz-e2e-fisico.toml` | 9/9 (2026-10-04; ficheros sin cambios desde entonces) |
| G-1 R-B | 0 violaciones |

### 7.9 Deudas y observaciones

- **IMPORTANTE (observación):** un SIGTERM a AURA en mitad de un turno deja el WAV de entrada en `/tmp/aura`.
  - Se observó al cerrar el arnés: `entrada_b5742dc49e66.wav`, borrado a mano.
  - La purga de arranque lo elimina en el siguiente inicio, y el comportamiento es anterior a este bloque.
  - Pasaría a deuda si AURA corriera como servicio que se detiene sin reiniciar, porque el audio quedaría en disco.
- **Observación:** con la TV encendida, el ruido de fondo puede impedir el corte por silencio. Se observó `corte=tope` a los
  6 s, que sigue siendo ≤ que la captura fija anterior.
- **Observación:** `milestones/mapa-maestro/` no está versionado en git (sin commits). Sus actualizaciones no dejan rastro
  auditable.
