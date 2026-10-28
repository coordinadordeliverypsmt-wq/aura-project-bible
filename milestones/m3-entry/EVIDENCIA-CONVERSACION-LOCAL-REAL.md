---
documento: "Evidencia — por qué AURA no conversaba localmente, y qué lo cambió"
tipo: "Registro de medición (HC-1)"
fecha: 2026-09-09
estado: "Medido y validado. Sin commit: el CEO decide."
mantenido-por: "APUS-5 (CTO)"
---

# Por qué AURA no conversaba, medido en HC-1

**Clasificación de evidencia** (D47): `[EJEC]` medido ejecutando · `[INFER]` deducido · `[HIPO]` no verificado.

## 1 · El síntoma y los TRES defectos que lo producían

El síntoma era uno: AURA no conversa. Las causas eran tres, independientes y en serie — cada una
bastaba por sí sola para dejar el turno sin respuesta.

| # | Defecto | Dónde | Evidencia |
|---|---|---|---|
| **A** | `format: "json"` obliga a JSON **válido**, no **conforme**: el modelo omitía `say` e **inventaba** una acción | `providers_real.py` | `say` 1/4 · acción inventada `{"action":"consultar","args":{"nombre":"Jesús","tipo":1}}` `[EJEC]` |
| **B** | «crees» estaba en la lista de **ÓRDENES** (subjuntivo de *crear*), así que «¿Por qué **crees** que…?» se clasificaba `ORDEN` y nunca llegaba a ser `PREGUNTA` | `intencion.py` | `acto_de_habla` → `ORDEN` `[EJEC]` |
| **C** | Pedir **consejo** se confundía con interrogar un **registro**: «¿Qué me recomiendas para dormir mejor?» → `HECHO_USUARIO` → moría en la guarda de memoria vacía | `intencion.py` | 3 turnos reales, 3 veces «No tengo ningún recuerdo registrado sobre eso», 38–53 ms, `provider=core` `[EJEC]` |

> **Lo que hizo visible B y C fue ejecutar el producto, no leerlo.** Con `AURA_STACK_REAL=1`, los tres
> primeros turnos se resolvieron **sin llamar al modelo ni una vez**. El defecto A —el único que se
> había diagnosticado al principio— estaba aguas abajo de un muro que no dejaba pasar nada.

## 2 · La reparación

1. **Contrato de salida por esquema** (`_ESQUEMA_COGNITIVO`): JSON Schema en `format`, que restringe el
   decodificado por gramática. `say` con `minLength: 1`; `action` constreñida a `"consulta"`, que el
   catálogo declara **verde y sin efecto**. Solo en modo cognitivo: en modo acción la autoridad es el
   catálogo y duplicarla sería el error que `D-M-8` diagnostica. Degradación de **una sola vez** a
   `format:"json"` si el runtime local es anterior a Ollama 0.5.
2. **«crees» sale de `_ORDEN`.** Misma colisión verbo/sustantivo ya pagada con `baja`, `marca` y
   `lista` en `D-M-2`; `crea` (el imperativo real) se queda.
3. **Rama de petición de consejo** en `es_cognicion_general`, lista **positiva y cerrada**, con **dos
   frenos**: ningún posesivo propio (`mi`, `mis`, …) y ningún marcador de evocación.
4. **Marcadores de evocación ampliados** con AURA como sujeto (`me dijiste`, `me contaste`,
   `me comentaste`, `me recomendaste`, `dijiste que`). Lo destapó la mutación: «¿Cómo puedo recordar lo
   que me dijiste?» pedía consejo sobre un registro y se iba al modelo. Ampliarlos solo **estrecha** la
   cognición.

**Por qué es seguro ensanchar por aquí, y es toda la tesis:** las 24 consultas protegidas piden un
**dato** —un nombre, una hora, una combinación, una fecha, un número, un color, una marca—. **Ninguna
pide consejo.** La asimetría: un error en esta frontera deja un consejo sin contestar; no expone un
hecho personal.

## 3 · Antes y después, a través del producto completo `[EJEC]`

Mismo equipo, misma sesión, `AURA_STACK_REAL=1`, `qwen2.5:0.5b`, voz neutralizada en la instrumentación
(ver §5).

| Turno | Antes | Después |
|---|---|---|
| «¿Qué me recomiendas para dormir mejor?» | «No tengo ningún recuerdo…» · 38 ms · **sin LLM** | respuesta real sobre sueño · 364,5 s · `ollama` |
| «¿Por qué crees que dormir poco afecta al ánimo?» | ídem · 53 ms · **sin LLM** | respuesta real · 346,6 s · `ollama` |
| «¿Qué puedo hacer para concentrarme mejor?» | ídem | «Para concentrarte mejor, puedes considerar usar un monitor o una aplicación que te oriente…» · 220,6 s |
| «¿Crees que es buena idea hacer ejercicio de noche?» | ídem | respuesta real · 216,5 s |
| **«¿Cuál es el nombre de mi abuela?»** | protegido | **protegido · 0,1 s · `provider=core`, sin LLM** |

**Fiabilidad del contrato:** `say` presente y no vacío **4/4** en el producto, **7/7** en el proveedor
aislado → **11/11 acumulado**. Acciones inventadas: **0/11**. Baseline: 1/4 y 1/4.

**Latencia del turno cognitivo:** 216,5 · 220,6 · 346,6 · 364,5 s → **media 287,1 s** `[EJEC]`.
Baseline de la sesión anterior con `format:"json"`: 237,0 s. **No atribuyo la diferencia al esquema:**
con n=4 y una varianza medida de **25,5–180,2 s sobre el mismo prompt**, el dato no lo soporta. Queda
como coste observado, no como causa demostrada `[HIPO]`.

## 4 · Garantías, medidas después del cambio `[EJEC]`

| Garantía | Resultado |
|---|---|
| `24/24` anti-fabricación | **24/24**, y ninguna de las 24 es «cognición general» |
| Memoria ausente en producción | respondida por el **Core** en 0,1 s, sin LLM |
| `tests/unit` | **823 tests · 2 fallos**, ambos deuda ajena (garantías vigentes · huérfanos del arnés) |
| `tests/integration` + `e2e` | **653 tests · 1 fallo**, `test_limite_reintentos` (deuda ajena) |
| Mutación `contrato-cognitivo` | **7/7 detectados · 0 sobreviven** |
| Mutación `conversacion-natural` | **5/5 detectados · 0 sobreviven** (2 sobrevivieron en la primera pasada y se cerraron con pruebas nuevas) |
| Garantías vigentes | **983 de 996** · las 13 rotas son las deudas ajenas documentadas |

## 5 · Un hallazgo aparte: el stack real no puede hablar `[EJEC]`

Con `AURA_STACK_REAL=1` **ningún turno se completa**, y no por el modelo:

```
piper --model '' --output_file /tmp/aura/resp_*.wav
FileNotFoundError: [Errno 2] No such file or directory: '..json'
AURA> No pude completar el turno (CalledProcessError: ... exit status 1)
```

`AURA_PIPER_VOICE` vale `""` por defecto y **no hay ninguna voz Piper instalada en el equipo**. El
error de síntesis **aborta el turno entero**, incluida la parte cognitiva que ya estaba resuelta. El
arranque, sin embargo, anuncia `AURA lista: 21 capacidades … stack=real`: es el patrón
**«declarado ≠ real»** que el proyecto ya ha pagado ocho veces.

**No lo he corregido**, y el motivo es que la corrección exige una decisión que no es mía: ¿un fallo de
voz debe degradar el turno a texto, o debe seguir tumbándolo? Degradar en silencio roza `INV-9` (no
fingir capacidad); no degradar deja AURA muda en cualquier equipo sin voz instalada. Va al CEO.
