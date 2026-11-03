---
documento: "DECISION_REQUIRED — el modelo por defecto no es el modelo que se usa"
tipo: "Expediente de decisión (NO implementado)"
fecha: 2026-09-10
estado: "ABIERTO. Requiere decisión del CEO."
---

# `qwen2.5:3b` por defecto, `qwen2.5:0.5b` en producción

## 1 · Dónde se define `[LECT]`

`walking-skeleton/aura_skeleton/composicion.py:161`

```python
modelo: str = field(default_factory=lambda: os.environ.get("AURA_LLM_MODEL", "qwen2.5:3b"))
```

Es el único sitio donde se declara. `OllamaProvider("ollama", config.modelo)` lo recibe tal cual
(`composicion.py:287`).

## 2 · Por qué existe la diferencia `[INFER]`

El valor `qwen2.5:3b` es la herencia de la comparación de razonadores
(`DP-COMPARACION-RAZONADORES.md`), cuando `3b` era el candidato. La medición posterior en `HC-1`
—3,6 GiB de RAM, Celeron N4020— dejó `0.5b` como el modelo operable, y ese cambio se hizo **por
entorno**, no en el código. El default nunca se movió.

## 3 · Qué se usa realmente `[EJEC]`

- Instalado en el equipo: **solo `qwen2.5:0.5b`** (`ollama list` → un único modelo, 397 MB en disco,
  484 MB residentes al cargar, cuantización `Q4_K_M`).
- Toda medición de esta sesión y de la anterior se hizo con `AURA_LLM_MODEL=qwen2.5:0.5b` **pasado
  explícitamente**.

## 4 · Impacto

**Si alguien arranca AURA con `AURA_STACK_REAL=1` y sin `AURA_LLM_MODEL`, pide un modelo que no
existe.** Ollama responde con error a `/api/generate`, el router lo trata como proveedor caído y el
turno cae al fallback. El síntoma —«AURA no contesta»— es idéntico al de un fallo de cognición, y la
causa es un valor por defecto obsoleto.

Es además una **trampa de medición**: cualquier benchmark que olvide la variable mide otro sistema.

## 5 · Alternativas

| | Qué hace | En contra |
|---|---|---|
| **A** | Poner `qwen2.5:0.5b` como default | Fija en el código una decisión de hardware; en un equipo mayor sería el modelo equivocado |
| **B** | Sin default: exigir `AURA_LLM_MODEL` y fallar al arrancar si falta | Explícito y sin sorpresas, pero rompe cualquier arranque que hoy funcione por inercia |
| **C** | Verificar al arrancar que el modelo declarado existe en Ollama y decirlo | No decide qué modelo usar; convierte un fallo silencioso en un mensaje claro |

## 6 · Recomendación `[INFER]`

**C ahora, y A o B cuando se decida el modelo.** El problema urgente no es cuál sea el default: es que
**un modelo ausente se manifiesta como un fallo de cognición**. Comprobarlo al arranque cuesta una
llamada a `/api/tags` y elimina toda una clase de diagnósticos falsos — de los que este proyecto ya ha
pagado ocho.

**Esta misión no lo cambia.** El CEO decide.
