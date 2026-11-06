---
documento: "El chat con el proveedor real: quién responde cada turno"
tipo: "Evidencia técnica operacional"
fecha: 2026-09-15
mantenido-por: "APUS-5 (CTO)"
estado: "Proveedor real verificado. Un defecto de arranque corregido y protegido por mutación."
---

# Ocho preguntas, una sola llamada al modelo

**Clasificación de evidencia** (D47): `[EJEC]` medido ejecutando · `[LECT]` leído.
Datos crudos: [`datos/chat-real-8-casos.json`](datos/chat-real-8-casos.json) · arnés: `datos/chat_real.py`.

---

## 1 · «stack=mock» no significaba que faltara Ollama `[EJEC]`

La cadena es: `composicion` → `ModelProvider` → `ModelRouter` → `OllamaProvider` | `MockProvider` → Ollama.

La selección la hace **una sola línea**: `Configuracion.usar_stack_real`, que sale de
`os.environ.get("AURA_STACK_REAL") == "1"`. Sin esa variable, AURA arranca con `MockProvider`; con ella,
con `OllamaProvider`. **El camino a Ollama ya estaba implementado y funciona**: no hubo que construir
nada, solo usar la configuración que ya existía (misión §14), y así está documentado en
`CHECKLIST-CONTINUIDAD.md:170`.

## 2 · El defecto que sí existía: el arranque no sabía qué modelo tenía `[EJEC]`

El valor por defecto de `Configuracion.modelo` es **`qwen2.5:3b`**. El único modelo instalado en HC-1 es
**`qwen2.5:0.5b`** (397 MB). Arrancando con `AURA_STACK_REAL=1` y sin `AURA_LLM_MODEL`:

```
[BOOT] proveedor LLM: stack=real timeout=900s …
[BOOT] AURA lista: 21 capacidades, 3 fuentes de contexto, stack=real
[WARN] router: fallback: ollama fallo (HTTPError: HTTP Error 404: Not Found); circuito -> ABIERTO
AURA> Mi modelo local no está disponible ahora mismo; inténtalo de nuevo en unos minutos.
```

Esa respuesta es **falsa dos veces**: el modelo local sí estaba disponible —otro—, y no es un problema
transitorio que se resuelva «en unos minutos», sino una configuración que no se arregla sola. Y el
circuito quedaba **ABIERTO**, así que los turnos siguientes fallaban sin intentarlo siquiera.

Es el patrón «declarado ≠ real» (INV-9), el mismo que la MISIÓN VOZ corrigió para el sintetizador.

### La corrección: decir la verdad, no cambiar el modelo

`OllamaProvider.comprobar()` lee el catálogo local (`GET /api/tags`, tope de 3 s) y el arranque lo
declara. **No descarga, no instala y no cambia el modelo**: cambiarlo por cuenta propia sería
reinterpretar la configuración del entorno (INV-7, y la misión lo prohíbe expresamente). Medido en los
tres casos reales contra el Ollama de la máquina:

| Caso | Lo que declara ahora el arranque |
|---|---|
| Defecto del código | `modelo=qwen2.5:3b [NO INSTALADO en ollama; instalados: qwen2.5:0.5b]` |
| Modelo instalado | `modelo=qwen2.5:0.5b (instalado)` |
| Ollama caído | `modelo=qwen2.5:0.5b [catalogo sin comprobar: Ollama no responde (URLError)]` |

No saber **no impide arrancar**: si Ollama no responde, se dice y se sigue (la misma degradación honesta
que la voz). En modo mock no se consulta nada, porque no habría proveedor real al que preguntar.

## 3 · Las ocho pruebas del chat `[EJEC]`

Con `AURA_STACK_REAL=1`, `AURA_LLM_MODEL=qwen2.5:0.5b` y **la voz activa** — las latencias incluyen la
síntesis real, por eso los turnos del Core no bajan de 8 s.

| Caso | Quién responde | Dominio | Llamadas LLM | Estatus | Latencia | Respuesta |
|---|---|---|---|---|---|---|
| Conversación | **CORE** | `conversacion_general` | **0** | hecho | 8,8 s | «Hola. ¿En qué puedo ayudarte hoy?» |
| Declaración propia | **CORE** | `declaracion` | **0** | hecho | 8,2 s | «Entendido.» |
| Consulta de memoria | **CORE** | `modelo_usuario` | **0** | hecho | 14,8 s | «Te llamas Mauricio.» |
| Memoria inexistente | **CORE** | `memoria` | **0** | ausencia | 15,8 s | «No tengo ningun recuerdo registrado sobre eso.» |
| Matemática | **CORE** | `aritmetica` | **0** | hecho | 8,7 s | «Te quedan 3 manzanas.» |
| Conocimiento general | MODELO (`ollama`) | `llm` | **1** | propuesta | 247,4 s | «Esto lo genera mi modelo local y no está verificado: El cielo está oscuro.» |
| Tema sensible | **CORE** | `sensible` | **0** | abstención | 13,2 s | «Sobre religión no te doy respuestas generadas por mi modelo local…» |
| Persona real | **CORE** | `sensible` | **0** | abstención | 29,6 s | «Sobre personas reales no te doy respuestas generadas por mi modelo local…» |

**Una sola llamada al modelo en ocho turnos.** Siete los resolvió el Core de forma determinista.

## 4 · La autoridad, comprobada donde importa

- **El único turno que llegó al modelo salió marcado como PROPUESTA**, con la marca del Core delante. Y
  la respuesta fue **pobre** —«El cielo está oscuro»—: es exactamente el caso que justifica la marca. El
  sistema **no la convirtió en un hecho**, no la guardó y no la repitió después.
- **La memoria final contiene un único hecho**, el que el usuario declaró, con sus cuatro campos de
  versionado (D-AMP-1):
  `{"contenido": "me llamo Mauricio", "origen": "declarada", "clase": "hecho_declarado", "refutada": false, "version": null, "supersedes": null, "valid_from": null, "valid_until": null}`
  Nada de lo que dijo el modelo entró en memoria (D-FC-8 = B).
- Los dominios sensibles se abstuvieron **sin llamar al modelo**: la decisión es previa a la llamada, así
  que no hay nada que filtrar después.
- **Voz y texto recorren el mismo camino.** En esta batería la voz estaba activa y sintetizó en los ocho
  turnos; no existe una ruta paralela para voz. La cadena completa `audio → STT → Core → say → TTS` está
  medida en [`CIERRE-VOZ-2026-09-15.md`](CIERRE-VOZ-2026-09-15.md).

## 5 · Lo que NO se hizo

No se instaló Ollama, no se descargaron modelos, no se cambió de modelo, no se tocó `num_ctx` ni ningún
parámetro de generación, y no se movió ni copió ningún artefacto. El defecto `qwen2.5:3b` **sigue siendo
el valor por defecto del código**: la misión prohíbe cambiarlo, y ahora al menos AURA avisa de que no lo
tiene en vez de morirse en el primer turno.
