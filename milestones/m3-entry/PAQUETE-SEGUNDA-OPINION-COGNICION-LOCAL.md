---
documento: "Paquete de segunda opinión técnica — cognición local de AURA en HC-1"
tipo: "Paquete compacto para consulta externa (OpenAI)"
estado: "LISTO. El defecto de CONTRATO quedó resuelto localmente; lo que queda abierto es CAPACIDAD del modelo."
fecha: 2026-09-09
destinatario: "segunda opinión técnica — NO es el runtime cognitivo de AURA"
autor: "APUS-5 (CTO)"
---

# Segunda opinión: ¿puede un modelo de 0,5 B sostener conversación útil en HC-1?

**Qué NO se pregunta.** No se pregunta cómo obtener `say` de forma fiable: eso ya está resuelto y medido
(§6–§7). No se pregunta qué proveedor cloud usar: AURA es local-first (`D24` / `ADR-0001`) y esta consulta
es una opinión, no una dependencia.

## 1 · Problema exacto

Con `qwen2.5:0.5b` en `HC-1`, AURA **ya** obtiene una respuesta conversacional bien formada en el 100 %
de los turnos medidos. Lo que sigue sin resolverse es la **calidad cognitiva** de esa respuesta:

1. **Razonamiento**: ante «¿Por qué crees que me cuesta dormir si me acuesto tarde?» responde
   «Vamos a ver qué nos pasa. ¿Podríamos hablar ahora?» — fluido, vacío de inferencia.
2. **Conocimiento general**: o es impreciso, o declina («Lo siento, pero no puedo asistir a esa pregunta»).
3. **Latencia**: **90–102 s de media** por turno cognitivo, con varianza **25,5–180,2 s sobre el mismo
   prompt** según la carga del equipo.

La pregunta es si esto es un techo del tamaño del modelo o un problema de configuración que aún no vemos.

## 2 · Arquitectura actual relevante

```
usuario → orchestrator.on_turn
            ├─ 9 superficies deterministas            (Core = autoridad, ADR-0014)
            ├─ intencion.clasificar  (2 ejes, determinista, sin LLM)
            ├─ memory.recall                          (Core, nunca el LLM)
            └─ router.route(prompt, trace_id, modo)
                  modo = "accion"    → _SYSTEM (1876 car., catálogo de 36 acciones) → motor único
                  modo = "cognitivo" → _SYSTEM_COGNITIVO (404 car., sin catálogo)   → solo texto
```

Invariantes que la solución no puede tocar: el LLM **no** decide qué memoria existe, qué se almacena, qué
se ejecuta ni qué permisos hay; toda ejecución pasa por el motor único (`ALERTA-005`); la detección de
«el usuario pregunta por un recuerdo» es determinista (`ADR-0014` §2); 24 consultas negativas de
`tests/datos/bateria_memoria.json` deben quedar protegidas de fabricación (**24/24**, no negociable).

## 3 · Archivos relevantes

| Fichero | Papel |
|---|---|
| `walking-skeleton/aura_skeleton/modules/providers_real.py` | cliente Ollama, prompts por modo, **esquema de salida** |
| `walking-skeleton/aura_skeleton/modules/router.py` | enrutado por modo |
| `walking-skeleton/aura_skeleton/core/orchestrator.py` | selección de modo y cascada determinista |
| `walking-skeleton/aura_skeleton/core/intencion.py` | clasificación de intención (2 ejes, sin LLM) |
| `walking-skeleton/tests/unit/test_contrato_cognitivo.py` | el contrato de salida, como prueba |

## 4 · Comportamiento observado (antes de la reparación)

`format: "json"` produce JSON **válido** pero **no conforme**. Respuesta literal medida:

```json
{"intent":"consulta","action":"consultar","args":{"nombre":"Jesús","tipo":1}}
```

Sin `say` — el usuario recibía el texto de fallback— y con una **acción inventada** (`consultar` no está
en el catálogo) y **argumentos fabricados** a partir de un nombre del prompt.

## 5 · Métricas baseline `[EJEC]` · todas en HC-1

| Métrica | Valor |
|---|---|
| `say` presente con `format:"json"` | **1 de 4** |
| Acción inventada | **1 de 4** |
| Turno cognitivo antes de separar prompts | 441,2 s · 630 tokens de ingesta |
| Turno cognitivo después de separarlos | 237,0 s · 166 tokens de ingesta |
| Reparto del coste | ≈71 % era ingestión del catálogo |
| Generación | 1,85–2,23 tok/s · Ingesta 3,52–3,83 tok/s (≈1,9 con carga) |
| Varianza sobre el mismo prompt | **25,5 – 180,2 s** |
| RAM libre con la sesión activa | ≈365 MB de 3,6 GiB · `llama-server` residente 565 MB |

## 6 · Experimentos realizados

- **A — ¿qué hace `format`?** Mismo prompt, tres configuraciones, en serie.
- **B — esquema endurecido** (`required`, `minLength`, `enum`), 3 repeticiones.
- **C — a través del proveedor real** ya implementado, 3 repeticiones.
- **Descartado por medición previa:** LLM como juez de intención → **8/12**, 10–58 s por llamada.

## 7 · Resultados `[EJEC]`

| | `say` | acción inventada | latencia |
|---|---|---|---|
| A1 `format:"json"` | **no** | **sí** (`consultar`) | 120,2 s |
| A2 JSON Schema | **sí, con contenido** | no | 99,5 s |
| A3 sin `format` | texto plano, `say "..."` no parseable | no | 51,4 s |
| B esquema endurecido ×3 | **3/3** | **0/3** | media 90,0 s |
| C proveedor real ×3 | **3/3** | **0/3** | media 102,0 s |
| **Acumulado** | **7/7** | **0/7** | — |

## 8 · Hipótesis descartadas

- **El modelo es incapaz de emitir `say`** — falso: con esquema lo emite 7/7.
- **El formato JSON es inadecuado para conversación** — falso: A3 muestra que el modelo *intenta* el
  formato incluso sin pedirlo; lo que faltaba era la gramática.
- **El parser es demasiado estricto** — falso: el JSON era válido y *no contenía* la clave.
- **Hace falta otro modelo para obtener `say`** — falso, y era la conclusión camuflada más probable.

## 9 · Hipótesis que permanecen

1. **H-CAP**: 0,5 B es insuficiente para razonamiento causal de una frase, con cualquier prompt. `[HIPO]`
2. **H-PROM**: un prompt cognitivo distinto mejoraría la calidad. **No demostrable en HC-1**: la varianza
   medida (25,5–180,2 s, y `say` 0/3 → 1/3 sin cambiar nada) excede cualquier efecto observable con un
   número asequible de repeticiones. Es el motivo por el que se descartó aplicar un cambio de prompt.
3. **H-PARAM**: `num_ctx`, `num_predict`, `num_thread`, `keep_alive` podrían bajar la latencia sin tocar
   el modelo. No medido aún.
4. **H-HW**: la latencia está dominada por el hardware (Celeron N4020, 3,6 GiB) y no por el software.

## 10 · Restricciones

Local-first sin claves de terceros · sin servicios cloud en el runtime · el modelo **no se cambia ni se
agranda sin decisión del CEO** · no ampliar autoridad del LLM · 24/24 fuera de negociación · HC-1 es la
referencia de medición · presupuesto de tokens y de disco limitados.

## 11 · Código relevante (el cambio ya aplicado)

```python
_ESQUEMA_COGNITIVO = {
    "type": "object",
    "properties": {
        "say": {"type": "string", "minLength": 1},
        "intent": {"type": "string"},
        "action": {"type": "string", "enum": ["consulta"]},
        "args": {"type": "object"},
    },
    "required": ["say", "action"],
}
# en _infer_sync: el esquema SOLO en modo cognitivo; en modo acción la autoridad es el catálogo.
formato = _ESQUEMA_COGNITIVO if modo == "cognitivo" else "json"
# y una degradación de UNA sola vez a format:"json" si el runtime rechaza el esquema (Ollama < 0.5).
```

## 12 · Pregunta técnica exacta

> Con decodificado restringido por gramática ya resuelto, **¿existe alguna configuración local
> (parámetros de inferencia, cuantización, formato de prompt) que haga a un modelo de ~0,5 B dar
> respuestas causalmente correctas de una o dos frases en español, en un Celeron N4020 con 3,6 GiB de RAM
> y sin superar ~30 s por turno?** Y si no existe: **¿cuál es el modelo local más pequeño que sí lo
> consigue en ese hardware**, y qué evidencia lo respalda?

## 13 · Solución que recomiendo

**Aceptar el contrato por esquema como cierre del defecto de fiabilidad** —está implementado, probado y
con 7 mutantes muertos— y **separar la decisión de capacidad**: medir antes H-PARAM (coste bajo, reversible,
sin cambiar modelo) y solo después plantear al CEO un cambio de modelo con cifras de HC-1 en la mano.

## 14 · Por qué no pude validarla completamente

Porque la parte que queda **no es un defecto, es un techo**, y medirlo exige lo que HC-1 no da: en un
equipo cuya latencia varía 7× sobre el mismo prompt y con ≈365 MB libres, distinguir «este prompt razona
mejor» de «esta vez el equipo estaba más libre» requiere un número de repeticiones que no es asequible ni
en tiempo ni en presupuesto. Medir mal sería peor que no medir: el proyecto ya ha pagado ocho veces el
patrón «declarado ≠ real».
