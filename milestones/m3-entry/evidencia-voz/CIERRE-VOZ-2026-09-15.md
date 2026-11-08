---
documento: "Cierre de voz end-to-end — evidencia de ejecución"
tipo: "Evidencia técnica operacional"
fecha: 2026-09-15
mantenido-por: "APUS-5 (CTO)"
estado: "La voz funciona end-to-end. Queda ABIERTA una decisión de persistencia (§8)."
---

# La voz de AURA funciona: STT → Core → TTS, medido

**Clasificación de evidencia** (D47): `[EJEC]` medido ejecutando · `[LECT]` leído · `[INFER]` deducido ·
`[HIPO]` no verificado.

Hardware: HC-1 (Lenovo 100e 2nd Gen, Celeron N4020, 3,6 GiB RAM, sin GPU).
Modelos: voz Piper `es_MX-ald-medium` y STT `faster-whisper base`, ambos en `AURORA_EXT`.
Datos crudos: [`datos/`](datos/). Arneses: `e2e_voz.py`, `fallo_voz.py`, `fase_reinicio.py`.

---

## 1 · Lo que ahora existe `[EJEC]`

Antes de esta sesión, **ningún turno con voz real se había completado nunca** en este proyecto: el
expediente del 2026-09-10 registró tres intentos y cero éxitos. Hoy el camino completo está demostrado.

| Etapa | Medido | Evidencia |
|---|---|---|
| TTS (Piper, frase corta) | **13,3 s**, WAV 22050 Hz mono 16-bit, 181 MB RSS | primera síntesis real del proyecto |
| STT (faster-whisper base) | **27,5 s** de transcripción + 10,1 s de carga | idioma `es` detectado con p = 0,99 |
| Turno completo con audio real | **29,4 s** (fase A) | `datos/reinicio-A-usb-montada.json` |
| Turno completo por la ruta del modelo | **374,7 s** → STT 58,7 s · LLM 285,9 s · TTS 30,0 s | `datos/e2e-voz-completa.json` |
| Arranque de la composición | 0,14 s | ídem |
| Memoria | RSS máx 359 MB; libre 1093 → 1004 MB | ídem |

### T2.a — la prueba del bucle cerrado, por fin ejecutada `[EJEC]`

`tests/e2e/test_real_stack.py::test_bucle_cerrado_tts_stt` existe desde M1 y **nunca se había podido
ejecutar**: exige una voz Piper que no estaba instalada. Ejecutada hoy con la voz de la USB, aplicando su
propio criterio (similitud por palabras ≥ 70 %):

```
original   : 'Hola, soy AURA, tu sistema operativo de inteligencia personal'
transcrito : 'Hola, soy ahora tu sistema operativo de inteligencia personal.'
similitud  : 89 %   →  PASA        (TTS 52,3 s · 200.748 B · STT 61,3 s)
```

Se ejecutó su cuerpo directamente porque el `pytestmark` del módulo exige además NATS en el 4222, que
esta prueba de voz no usa; el criterio y los asertos son los suyos, sin relajar.

---

## 2 · El defecto que se ha corregido `[EJEC]`

`_finalizar_turno` llamaba a `voice.tts(visible, tid)` **antes** de fijar `self._results[tid]` y de
`self._done[tid].set()`. Un fallo del sintetizador tumbaba el turno entero: la respuesta ya calculada
—hasta seis minutos de inferencia— se perdía, y la superficie esperaba un resultado que no iba a llegar.
Lo mismo ocurría con `voice.stt` en `handle_utterance`, que además ocurre antes de que el Core vea nada.

Ahora la voz es **periférica**: si falla, el turno se entrega en texto, el fallo se audita y queda
declarado en el resultado (clave `voz`), y el turno siguiente vuelve a intentarlo.

### Prueba de fallo real, con el adaptador real `[EJEC]`

`datos/fallo-tts-controlado.json` — la voz se apunta a un `.onnx` inexistente (lo que ocurre si la USB
se va) y después se restaura, **en el mismo proceso**:

| Comprobación | Resultado |
|---|---|
| respuesta conservada con la voz rota | ✅ `"Todavía no sé nada sobre ti."` |
| fallo observable | ✅ `voz = "no_disponible"` |
| turno completado | ✅ `provider = "core"`, 0,01 s |
| recuperación en el turno siguiente | ✅ `voz = "ok"` |
| mismo texto con voz y sin voz | ✅ la degradación no altera la respuesta |
| audio generado solo tras restaurar | ✅ un único WAV |

---

## 3 · STT — reconocimiento

- **Modelo:** `base` (145.217.532 B), resuelto por `HF_HOME` → `AURORA_EXT/hf_cache`. La copia canónica
  es `hf_cache/hub/`; la segunda copia en `hf_cache/` **no la usa** HuggingFace con `HF_HOME` `[EJEC]`.
- **Idioma: declarado, no detectado.** Medido con calentamiento previo y **orden alternado** para que no
  lo decidiera la caché: mediana **25,6 s** declarando `es` frente a **58,0 s** detectándolo (n = 3 pares;
  el declarado gana los 3). El texto transcrito fue **idéntico** en las seis pasadas: esto ahorra tiempo,
  **no mejora la exactitud** `[EJEC]`.
- **`initial_prompt` se probó y se descartó:** empeoró la transcripción («me llamo **un** Mauricio»).
- **Nunca descarga.** `local_files_only=True`. El defecto de la librería es `False`, así que un modelo
  ausente no fallaba: **se descargaba de HuggingFace**, una salida a la red que nadie decidió, en un
  sistema que declara local-first (D24, ADR-0001). Verificado bajo la condición real en §5.

### Limitación conocida, no escondida `[EJEC]`

El modelo `base` transcribe *«Hola AURA, me llamo Mauricio»* como **«Hola ahora me llamo Mauricio»**:
confunde el nombre propio del sistema. La consecuencia es **funcional, no cosmética**: el detector
reconoce la frase original (`es_declaracion_de_hecho_propio` → `True`) y **no** la transcrita (`False`),
así que el hecho no se registró y el turno siguiente respondió «Todavía no me has dicho cómo te llamas».

**Causa aislada por ejecución**, no por lectura: el detector funciona; lo que falla es el reconocimiento.
No se ha compensado en el Core —adaptar el Core a los errores del transcriptor sería moverle la autoridad
a un periférico— ni se ha subido de modelo, que la misión prohíbe hacer por iniciativa propia.

---

## 4 · TTS — síntesis

- **Binario:** `~/.local/bin/piper` (wrapper del paquete `piper-tts` del disco interno).
- **Modelo:** `AURORA_EXT/piper_voices/es_MX-ald-medium.onnx` (63.201.294 B) **más su `.onnx.json`**,
  que Piper exige junto al modelo.
- **Tope de espera:** `LIMITE_SINTESIS_S = 120`. No es una propiedad de la arquitectura (regla del CEO,
  2026-08-04): se deriva de los 13,3 s medidos y su trabajo es cortar un **cuelgue**, no disciplinar la
  latencia. Antes `subprocess.run(..., check=True)` no llevaba `timeout`: un Piper colgado colgaba el
  turno para siempre.
- **Falla antes de invocar:** con `piper_voice=""` el error era `FileNotFoundError: '..json'`, emitido por
  Piper sobre un fichero que el usuario nunca nombró. Ahora AURA comprueba el `.onnx` y su `.json` y dice
  cuál falta.

---

## 5 · Dependencia de la USB — explícita y demostrada `[EJEC]`

Cuatro arranques, **cada uno en un proceso nuevo** (`datos/reinicio-*.json`):

| Fase | Condición | Arranque declara | Turno de texto | Turno de audio |
|---|---|---|---|---|
| **A** | USB montada | `voz: DISPONIBLE (…es_MX-ald-medium.onnx)` | `voz=ok`, 10,1 s | `voz=ok`, 29,4 s |
| **B** | **USB desmontada de verdad** (`udisksctl unmount`) | `voz: NO DISPONIBLE …; los turnos se entregarán solo en texto` | responde en **0,03 s**, `voz=no_disponible` | *«No pude transcribir el audio, así que no voy a adivinar qué dijiste»* — `dominio=voz`, `estatus=abstencion` |
| **C** | USB remontada | `voz: DISPONIBLE` | `voz=ok`, 27,3 s | `voz=ok`, 75,0 s |
| **D** | USB montada, **shell limpio** (`env -i`) | `voz: NO DISPONIBLE (AURA_PIPER_VOICE está vacía)` | `voz=no_disponible`, 0,01 s | — |

Dos hechos que la fase B demuestra y que no se pueden obtener leyendo código:

1. **AURA sigue siendo usable sin la USB.** Responde en 0,03 s, conserva la respuesta y lo dice.
2. **La frontera local-first aguantó bajo la condición real.** Con el modelo fuera de alcance, AURA **no
   fue a buscarlo a internet**: falló y lo dijo. Sin `local_files_only=True` habría intentado descargarlo.

   El mensaje exacto está capturado en [`datos/frontera-local-first.json`](datos/frontera-local-first.json),
   reproducible con `HF_HOME` vacío y `HF_HUB_OFFLINE=1`:

   > `no hay modelo de transcripcion utilizable ('base'); no se descarga nada: Cannot find an appropriate
   > cached snapshot folder for the specified revision on the local disk and outgoing traffic has been
   > disabled.`

   *(La auditoría señaló con razón que esta frase se citaba en la prosa sin estar en ningún fichero de
   `datos/`. Se reprodujo y se guardó como artefacto: la cita ahora tiene respaldo.)*

La USB se remontó y quedó verificada (`/dev/sdb1` en `/media/majo1230/AURORA_EXT`, modelos legibles).

---

## 6 · Frontera de autoridad — intacta

- **STT** transforma audio en texto y no decide nada. Si falla, **el Core** cierra el turno por sí mismo,
  con `provider="core"`, **cero llamadas al modelo** y **sin escribir memoria**: sin transcripción no hay
  nada que el usuario haya dicho, y un adaptador periférico no puede ponerle palabras en la boca.
- **TTS** transforma texto en audio. Su fallo no altera el `say` (ADR-0017), no cambia el `estatus` y no
  se disfraza de «modelo no disponible».
- No se tocaron `permissions.py`, `kill_switch.py`, la PARADA, ni ningún perímetro de autoridad.
- El texto transcrito recorre **el mismo camino** que el texto tecleado: la voz no crea una segunda
  autoridad (`test_CONTROL_el_texto_transcrito_llega_al_Core_y_es_el_Core_quien_decide`).

---

## 7 · Verificación

| Comprobación | Resultado |
|---|---|
| Pruebas nuevas | 27 (15 integración + 12 unitarias), todas con caso de control |
| Mutación del comportamiento nuevo | `voz-degrada-con-honestidad.toml`: **14 detectados, 0 sobreviven** |
| Mutación de los catálogos reanclados | 38 mutantes más, 0 supervivientes |
| Garantías | **1121/1126 vigentes**; las 5 rotas son `VAL-M1..M5`, preexistentes y ajenas |
| Suites | `unit + integration + e2e + contracts` en verde salvo esa línea base |
| ruff · mypy · format | limpio · 0 incidencias en 68 ficheros · 42 (línea base exacta) |

Un mutante sobrevivió en la primera pasada (**VZ-M8**) y la causa era la prueba, no el código: al borrar
la comprobación del `.onnx` saltaba la del `.onnx.json`, cuyo mensaje **también** contiene la ruta, así
que el assert pasaba por la razón equivocada. La prueba ahora distingue *qué* falta.

### Auditoría independiente — tres hallazgos, los tres corregidos

Auditor distinto del implementador, según el estándar del proyecto. Reprodujo el defecto original en una
copia del árbol para comprobar que las pruebas nuevas **no son decorativas**: reintroducido el `tts`
desnudo, las 6 pruebas de TTS fallan; quitado el `try/except` del STT, fallan las 3 de STT.

| Sev. | Hallazgo | Corrección |
|---|---|---|
| **ALTO** | `LIMITE_TRANSCRIPCION_S` estaba **declarada y no se usaba en ninguna parte**. El comentario prometía una protección de cuelgue para STT que el código no daba: `model.transcribe()` corría sin tope. Es «declarado ≠ real» —cometido en el mismo cambio que viene a corregir ese patrón— | El tope es real: `asyncio.wait_for` sobre el executor, con `VozNoDisponible` al agotarse. Prueba + `VZ-M13`. Se documenta que libera **el turno**, no el hilo: Python no puede matar un hilo del executor |
| MEDIO | El documento citaba *«outgoing traffic has been disabled»* como `[EJEC]`, pero esa cadena **no estaba en ningún fichero de `datos/`** — solo en la prosa | Reproducido y guardado en `datos/frontera-local-first.json` |
| BAJO | El turno sin transcripción **sí entraba en el buffer de diálogo** (`self._dialogue`). No se persistía, pero reentraba al prompt como un «Usuario:» vacío en los turnos siguientes | `if text:` antes del `append`. Prueba + control + `VZ-M14` |

El auditor dejó constancia de lo que **no** pudo verificar: no ejecutó el arnés de mutación (RAM), y no
puede comprobar el origen físico de las mediciones. Ambas limitaciones son ciertas y se registran aquí en
lugar de presentarlas como verificadas.

---

## 7.bis · Observación técnica (no es deuda todavía)

El fallo de voz es observable en **dos** sitios: la clave `voz` del resultado del turno y un `WARN`
auditado (`audit=True`). La superficie de consola **no lo anuncia**: `__main__.py:183` imprime el `say` y
nada más. No se ha tocado, por tres razones: lo que §5 exige —que el fallo quede observable— ya se cumple;
en consola el usuario percibe por sí mismo que no ha sonado nada; y añadir líneas a la superficie pone en
riesgo las garantías de «UI limpia» a cambio de poco.

**Condición que lo convertiría en deuda:** que AURA se use en un canal donde el usuario **no pueda notar**
la ausencia de audio (por ejemplo, manos libres o un cliente que solo reproduzca voz). Ahí, callar que no
hubo voz sí sería fingir una capacidad.

---

## 8 · Lo que queda ABIERTO — `DECISION_REQUIRED`

**La capacidad de voz no sobrevive a una sesión nueva.** La fase D lo demuestra: con la USB montada y los
dos modelos presentes y legibles, un arranque sin `AURA_PIPER_VOICE` y sin `HF_HOME` **no tiene voz**.
Hoy esas variables no están en `~/.profile` ni en ningún script de arranque `[EJEC]`.

Esto choca con una regla permanente del CEO: *«Toda capacidad importante sobrevive al reinicio de sesión.
Si desaparece al terminar la conversación, no pertenece a AURA»*. **No se ha resuelto por decisión propia**
porque elegir dónde viven los modelos y quién declara su ubicación cambia una propiedad de persistencia
del sistema. Las alternativas están en el informe de cierre de la misión.

Existe un precedente **ya aprobado** que conviene mirar antes de decidir: `entorno/scripts/ollama-usb.sh`
(acta **D27**) resuelve exactamente este problema para los modelos de Ollama con un lanzador que se
**niega a arrancar** si la USB no está montada, y cuyo comentario dice: *«Una variable de entorno no es
una garantía: `/media/.../AURORA_EXT` existe igual con el USB desmontado»*. La fase B confirmó esa lección.

### Dos documentos que ya no dicen la verdad `[LECT]`

Se registran, **no se han modificado** (definen cómo se materializa el entorno, y eso es gobernanza):

- `entorno/scripts/install-linux.sh:33` — *«Modelos STT/TTS se descargan al primer uso»*. La voz Piper
  nunca se descargó (por eso no había voz), y ahora la descarga automática está **deliberadamente
  prohibida** por `local_files_only=True`.
- `entorno/scripts/requirements-stack.txt` — *«descarga el modelo al 1er uso»*, mismo caso.
