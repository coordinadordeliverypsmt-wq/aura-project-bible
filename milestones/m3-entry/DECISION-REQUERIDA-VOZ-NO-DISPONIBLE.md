---
documento: "DECISION_REQUIRED — qué debe hacer AURA cuando la voz no está disponible"
tipo: "Expediente de decisión (NO implementado, por orden expresa del CEO)"
fecha: 2026-09-10
estado: "ABIERTO. Requiere decisión del CEO. Nada corregido, nada instalado."
mantenido-por: "APUS-5 (CTO)"
---

# La voz ausente tumba el turno entero

**Clasificación de evidencia** (D47): `[EJEC]` medido · `[LECT]` leído · `[INFER]` deducido.

## 1 · Comportamiento actual `[EJEC]`

Con `AURA_STACK_REAL=1`, los tres turnos de una sesión real terminaron así:

```
piper --model '' --output_file /tmp/aura/resp_<trace>.wav
FileNotFoundError: [Errno 2] No such file or directory: '..json'
AURA> No pude completar el turno (CalledProcessError: ... returned non-zero exit status 1)
```

**Ningún turno se completó.** Y el arranque, en la misma ejecución, anunciaba:
`AURA lista: 21 capacidades, 3 fuentes de contexto, stack=real`.

## 2 · Causa `[LECT]`

Tres hechos encadenados, ninguno oculto:

1. `composicion.py:288` — `WhisperPiperVoice(piper_voice=os.environ.get("AURA_PIPER_VOICE", ""))`.
   **El valor por defecto es la cadena vacía.**
2. `adapters/voice_real.py:51-56` — `_tts_sync` invoca `subprocess.run([...], check=True)`. Con
   `--model ''`, Piper aborta y `check=True` convierte el fallo en `CalledProcessError`.
3. **No hay ninguna voz Piper instalada en `HC-1`** `[EJEC]`: no existe `~/.local/share/piper*` ni
   ningún `.onnx` de voz (los dos `.onnx` del equipo son modelos de *embeddings*, no de voz).

La excepción sube por `tts` → `on_turn` → y el bucle de conversación la reporta como turno fallido. El
`say` ya calculado —la parte cara, hasta 6 minutos de inferencia— **se descarta**.

## 3 · Impacto

- **Producto inusable en modo real** en cualquier equipo sin voz instalada, incluido `HC-1`.
- **Se paga el coste y se tira el resultado**: el fallo ocurre DESPUÉS de la inferencia.
- **`INV-9` en el límite**: el sistema declara `stack=real, 21 capacidades` mientras una de ellas no
  puede ejecutarse. Es el patrón «declarado ≠ real» que el proyecto ha pagado ocho veces.
- **No afecta a la seguridad**: ni a la autoridad del Core, ni a permisos, ni al `24/24`. Es
  disponibilidad, no integridad.

## 4 · Alternativas (ninguna elegida)

| | Qué hace | A favor | En contra |
|---|---|---|---|
| **A** | **Degradar a texto**: si el TTS falla, el turno se entrega igualmente y se registra el fallo de voz | El usuario recibe la respuesta que ya se pagó; el fallo queda auditado | Roza `INV-9` si se degrada en silencio: habría que anunciar «sin voz» de forma visible |
| **B** | **Abortar el turno** (comportamiento actual) | Honesto: no finge una capacidad que no tiene | AURA queda muda y el trabajo cognitivo se pierde |
| **C** | **Instalar una voz Piper** | Restaura la capacidad completa | Consume disco en un equipo con margen escaso; no arregla el defecto, lo esconde |
| **D** | **Política de voz explícita**: la voz se declara *latente* al arrancar si no hay modelo, y el Capability Manager la marca como no disponible | Coherente con `INV-1` y con el estado EFECTIVO de capacidades que ya existe | Es el más trabajo: toca composición y declaración de capacidades |

## 5 · Recomendación `[INFER]`

**D combinada con A**, en ese orden: que el arranque **declare** la voz como no disponible cuando no
haya modelo —el sistema ya distingue capacidades activas, degradadas y latentes, y `memoria` ya aparece
como `degradada`—, y que el turno se entregue en texto diciendo explícitamente que no hay voz. Así no
se finge nada (`INV-9` intacto) y no se tira una inferencia de cinco minutos.

**C es la peor opción como primera medida:** instalar una voz haría desaparecer el síntoma sin corregir
que un fallo de un adaptador periférico pueda tumbar un turno entero.

**Esta misión no lo implementa.** El CEO decide.
