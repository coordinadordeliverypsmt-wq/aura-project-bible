---
documento: "Análisis técnico — Plataforma de referencia y modelo base para R1"
fecha: 2026-07-21
autor: "CTO"
estado: "Aprobado con precisión del CEO (2026-07-21). Ver aviso de alcance."
alcance: "Referencia permanente para decisiones de rendimiento y capacidades"
---

# Análisis técnico — Plataforma de referencia y modelo base (R1)

Documento de referencia encargado por el CEO antes de continuar con M3.1.

> ## ⚠ Aviso de alcance — precisión del CEO (2026-07-21)
>
> **Ninguna plataforma de este documento es la plataforma objetivo oficial del proyecto.**
>
> El CEO aprobó las conclusiones técnicas —el requisito de latencia percibida y el desacoplamiento
> del Core respecto al runtime— pero **no oficializó Apple Silicon** ni ninguna otra opción. Lo
> aprobado es su uso como **plataforma de referencia para pruebas de rendimiento**.
>
> **La decisión de plataforma definitiva se tomará cuando se defina el escenario de despliegue**: uso
> personal, instalación doméstica, distribución a terceros o producto comercial. Son escenarios con
> requisitos incompatibles entre sí, y elegir hardware antes de saber cuál aplica sería fijar una
> restricción de 10 años (D20) sobre una incógnita.
>
> Las recomendaciones de §1.5 deben leerse como **evaluación comparativa**, no como decisión. La
> neutralidad tecnológica queda registrada en **ADR-0016**.

## 0. Cómo leer las cifras de este documento

Se distinguen tres calidades de dato, y conviene no mezclarlas:

| Marca | Significado |
|---|---|
| **[medido]** | Medición propia sobre el equipo actual, con evidencia en el repositorio |
| **[terceros]** | Publicado por fuentes externas; orientativo, no verificado por nosotros |
| **[cálculo]** | Derivado por aritmética a partir de requisitos de la Bible |

Ninguna decisión de este documento debería tomarse sobre un dato **[terceros]** aislado sin
verificarlo en el equipo concreto antes de comprarlo.

## 1. ¿Cuál es el hardware objetivo de referencia para R1?

### 1.1 Punto de partida: por qué el equipo actual no es candidato

| Componente | Valor **[medido]** |
|---|---|
| CPU | Intel **Celeron N4020**, 2 núcleos / 2 hilos, 1.10 GHz (turbo 2.80) |
| RAM | **3,6 GB** totales |
| GPU | Intel UHD Graphics 600 — **Ollama la descarta**: `dropping integrated GPU` |
| Latencia por turno (`qwen2.5:0.5b`) | **145.984 / 147.739 / 467.858 ms** |
| Latencia por turno (`qwen2.5:3b`) | **Agota 600 s y aborta**, con el equipo en swap |

El objetivo HC-1 es **P50 ≤ 1.200 ms**. La medición más favorable está **121 veces por encima**, y ni
siquiera es válida: se tomó con carga 6,9 en dos núcleos. No es un problema de optimización de
código; es de dos órdenes de magnitud.

### 1.2 El requisito real, que no es "tokens por segundo"

Aquí conviene deshacer un malentendido frecuente, porque cambia qué hardware hace falta.

El presupuesto de 2.5 §5.1 reparte los 1.200 ms **por etapas, en streaming**:

```
captura+VAD ≤150ms · STT ≤250ms · primer token del LLM ≤500ms · primer audio TTS ≤300ms
```

Lo que debe caber en 1.200 ms es **el primer audio**, no la respuesta completa. De ahí se derivan dos
requisitos distintos **[cálculo]**:

| Requisito | Umbral | Qué lo determina |
|---|---|---|
| **Tiempo hasta el primer token** | **≤ 500 ms** | Velocidad de *prefill*: CPU/GPU y longitud del prompt |
| **Generación sostenida** | **≥ ~10 tok/s** | Ancho de banda de memoria |

El segundo umbral merece explicación: el habla ronda 150 palabras por minuto ≈ **4 tokens/s**. Basta
con generar más rápido de lo que AURA habla para que el TTS nunca se quede sin texto. Se propone
**10 tok/s** como umbral con margen (2,5×), no 40 ni 60.

**Consecuencia práctica: no necesitamos una máquina de inferencia de gama alta.** Necesitamos una que
sostenga ~10 tok/s con un modelo decente y responda rápido al primer token. Eso abre opciones
mucho más baratas y sobrias que las que sugeriría perseguir cifras de *benchmark*.

### 1.3 Criterio adicional: AURA está encendida todo el día

Un PIOS no es una estación de inferencia por lotes. Es un compañero **presente durante toda la
jornada** (criterio-marco de 2.1), lo que convierte el consumo en reposo en un criterio de primer
orden, no en una nota al pie. Una plataforma que consuma 80 W en reposo cuesta, encendida
permanentemente, más en electricidad al año que la diferencia de precio con una que consuma 8 W.

### 1.4 Alternativas evaluadas

| # | Plataforma | RAM/VRAM | Rendimiento esperado | Consumo reposo | Veredicto |
|---|---|---|---|---|---|
| **A** | Mantener el equipo actual | 3,6 GB | **[medido]** 146–468 s/turno | bajo | **Descartada.** Dos órdenes de magnitud del objetivo |
| **B** | Mini PC Intel N100/N150 | 16 GB | **[terceros]** 6–9 tok/s en 8B Q4; mejor en 3B | muy bajo | **Marginal.** CPU-only, RAM de un solo canal. Cumpliría con 3B, sin margen |
| **C** | PC con GPU dedicada (RTX 3060 12 GB) | 12 GB VRAM | **[terceros]** 42–45 tok/s en 7–8B | alto (~60–100 W) | **Viable.** Sobrado en rendimiento; penaliza el consumo 24/7 |
| **D** | Mac mini Apple Silicon (M4) | 16–24 GB unificada | **[terceros]** 60–80 tok/s en 7B Q4 | muy bajo (~5–10 W) | **Viable y equilibrada** |

Nota sobre **[terceros]**: Ollama 0.19 (marzo 2026) cambió su backend de Metal a MLX en Apple
Silicon, con saltos de rendimiento notables en los datos publicados. Es un cambio reciente y conviene
verificarlo antes de comprometer la decisión.

### 1.5 Evaluación comparativa

> **No es una decisión de plataforma.** Ver el aviso de alcance al inicio: el CEO no oficializó
> ninguna plataforma objetivo. Lo que sigue es la comparación técnica que sustenta el uso de una
> plataforma **de referencia para pruebas**.

**La opción D (Apple Silicon, 16 GB o más) es la mejor referencia de prueba disponible**, con la
**opción C como alternativa** si se prefiere hardware x86 abierto o ya se dispone de una GPU.

Razones, en orden de peso:

1. **Cumple el requisito real con margen** sin ser una máquina de gama alta.
2. **Consumo en reposo compatible con estar encendida siempre**, que es la condición de un PIOS.
3. **Memoria unificada**: el cuello de botella de un LLM local es el ancho de banda de memoria, y ahí
   Apple Silicon rinde muy por encima de un mini PC x86 de RAM de un solo canal.

Y una advertencia que corresponde a mi papel: **la opción C tiene una ventaja que la D no tiene** —
es hardware estándar, ampliable y reparable, con un horizonte de 10 años (D20) más predecible. Si el
CEO valora más la longevidad y la independencia de un fabricante que el consumo, **C es una elección
defendible y no la descartaría**.

**Ninguna de las dos viola D24 ni ADR-0001**: la restricción es que el *stack de software* sea local
y open source, no que el hardware lo sea.

## 2. ¿Qué modelos locales son realmente viables?

Regla previa **[cálculo]**: un modelo debe caber **entero** en memoria rápida junto al resto del
sistema. Cuando no cabe, el sistema entra en *swap* y el rendimiento no se degrada, se desploma — es
exactamente lo que **[medido]** ocurrió con `qwen2.5:3b` en el equipo actual.

| Modelo (Q4) | Tamaño aprox. | Equipo actual | Opción B (16 GB) | Opciones C/D |
|---|---|---|---|---|
| 0,5 B | ~0,4 GB | **[medido]** funciona, 146 s/turno | Sí, muy rápido | Sí, trivial |
| 3 B | ~2,0 GB | **[medido]** agota 600 s (swap) | Sí, con margen | Sí, holgado |
| 7–8 B | ~4,5–5 GB | No | Sí, pero **[terceros]** 6–9 tok/s | Sí, con buen margen |
| 13–14 B | ~8–9 GB | No | No | Sí en D con 24 GB; ajustado en C |

**Recomendación de modelo base: la clase 7–8 B como objetivo, con 3 B como respaldo.**

Las opciones C y D sostienen 7–8 B muy por encima del umbral de 10 tok/s. La opción B sólo lo
sostiene con 3 B.

### La razón por la que el tamaño del modelo importa más de lo que parece

No es una cuestión de fluidez. **[medido]** en la demo de M2, `qwen2.5:0.5b` eligió `abrir_archivo`
ante *"recuérdame comprar pan"* — una acción absurda, y una de tres peticiones claramente
equivocada.

La arquitectura contuvo el error sin daño, y esa es la buena noticia. Pero **el umbral de M3 es
≤ 20% de falsos positivos en anticipación** (2.5 §5.3), un problema más difícil que elegir con la
petición delante. Con la calidad de decisión observada, ese umbral no se alcanza. **La elección de
modelo base no es una decisión de rendimiento: es la que determina si CM4 es alcanzable.**

## 3. ¿Qué gana o pierde AURA con cada alternativa?

| Capacidad | A (actual) | B (N100) | C (GPU) | D (Apple Silicon) |
|---|---|---|---|---|
| Conversación fluida (HC-1) | **No** | Ajustado con 3 B | **Sí** | **Sí** |
| Uso diario real → historial para M3 | **Imposible** | Sí | Sí | Sí |
| Calidad de decisión (acciones, M2) | Mala **[medido]** | Media (3 B) | **Buena** (7–8 B) | **Buena** (7–8 B) |
| Anticipación con ≤20% falsos positivos (CM4) | No | Improbable | **Plausible** | **Plausible** |
| Avatar (M3.4) — recursos gráficos | No | Muy justo | **Sí** | **Sí** |
| Encendida todo el día | Sí | **Sí** | Penalizado | **Sí** |
| Ampliable y reparable a 10 años (D20) | — | Media | **Alta** | Baja |
| Barge-in y voz en streaming | No | Ajustado | **Sí** | **Sí** |

**Lectura corta:** la opción B desbloquea el uso diario pero deja M3 en el filo; C y D desbloquean
además la calidad de decisión, que es lo que M3 necesita de verdad.

## 4. ¿Qué arquitectura permite sustituir el modelo sin tocar el Core?

**Ya está construida y verificada**, desde M1 y reforzada en M2.5.

El contrato es de dos métodos:

```python
@runtime_checkable
class ModelProvider(Protocol):
    name: str
    async def infer(self, prompt: str) -> str: ...
```

Cualquier motor —Ollama, llama.cpp, MLX, vLLM o un servicio futuro— se incorpora implementando esa
interfaz. Por encima, el `ModelRouter` selecciona proveedor y aplica *fallback* con cortacircuitos,
de modo que **cambiar de modelo es cambiar de configuración, no de arquitectura**.

### Evidencia, no afirmación

Verificado sobre el código actual:

```
Ficheros que mencionan un modelo o runtime concreto (qwen/ollama/gpt/claude/mistral/llama):
  aura_skeleton/modules/providers_real.py     <- unico acoplamiento
  aura_skeleton/contracts.py                  <- solo el contrato, sin implementacion

En core/, adapters/ y conectores/: NINGUNA coincidencia.
```

**El acoplamiento al modelo vive en un solo fichero.** Sustituirlo no toca el núcleo, ni los
adaptadores, ni los conectores de contexto.

### Un matiz honesto

Hay un punto de acoplamiento **blando** que conviene tener presente: el *prompt del sistema*, que en
M2.5 pasó a derivarse del catálogo de acciones. No es código acoplado al modelo, pero **su eficacia
sí depende del modelo**: un modelo distinto puede necesitar otra formulación para elegir bien.

No rompe la sustituibilidad —no hay que tocar el Core—, pero **cambiar de modelo exigirá volver a
verificar la calidad de decisión**, no sólo la latencia. Conviene incluir esa verificación en el gate
del cambio de modelo, y no darlo por hecho.

## 5. Qué depende del modelo y qué debe permanecer independiente

| Componente | ¿Depende del modelo? | Regla permanente |
|---|---|---|
| `modules/providers_real.py` | **Sí, por diseño** | Es el punto de sustitución. Único fichero que puede nombrar un modelo |
| `modules/router.py` | Parcialmente | Conoce *proveedores*, no modelos concretos |
| Prompt del sistema | **Acoplamiento blando** | Derivado del catálogo; su eficacia se re-verifica al cambiar de modelo |
| `core/orchestrator.py` | **No** | Coordina; no sabe qué modelo responde |
| `core/permissions.py` | **No, y jamás** | La clasificación verde/roja es del Core (ADR-0014) |
| `core/operaciones.py` | **No, y jamás** | La validación de argumentos y ámbito es determinista |
| `core/automatizacion.py` | **No** | El orden dry-run → HITL → adaptador no depende del modelo |
| `core/senales.py`, `core/contexto.py` | **No** | La captura observa; no interpreta (ADR-0015) |
| `adapters/*` | **No** | Ejecutan operaciones tipadas |
| Audit log | **No** | Registro forense de hechos |

### La regla que se deriva, y que propongo fijar como permanente

> **Ninguna garantía del sistema puede depender del modelo.** Seguridad, permisos, validación,
> auditoría y captura son deterministas y verificables. El modelo aporta lenguaje y razonamiento;
> nunca autoridad.

Es ADR-0014 aplicado a la elección de plataforma, y tiene una consecuencia útil: **cambiar de modelo
no puede degradar la seguridad de AURA**, sólo su utilidad. Es exactamente lo que **[medido]**
demostró la demo de M2, cuando el modelo se equivocó y no pasó nada.

## 6. Fuentes de contexto futuras

Sección requerida por el CEO. **Nada de esto se implementa ahora.** Queda definida la arquitectura
para incorporarlo cuando corresponda, sin rediseñar el Core.

### 6.1 Fuentes previstas

| Fuente | Señales que aportaría | Estado |
|---|---|---|
| **Cámaras de seguridad** | Presencia, patrones de entrada/salida | **No implementada** |
| **Home Assistant (ampliado)** | Escenas, sensores, más dispositivos | Parcial (M3 usa el adaptador base) |
| **Wearables** (Garmin, Apple Watch, Fitbit, Oura, Polar…) | Actividad, sueño, rutinas | **No implementada** |
| **Sensores biométricos** | Constantes, estado fisiológico | **No implementada** |
| **Sensores ambientales** | Temperatura, luz, calidad del aire, ruido | **No implementada** |
| **Vehículos** | Desplazamientos, rutinas de trayecto | **No implementada** |
| **Dispositivos IoT futuros** | Por definir | **No implementada** |

### 6.2 Cómo se incorporan, según ADR-0015

Cada fuente será **un fichero nuevo en `conectores/`** que implemente el contrato:

```python
@runtime_checkable
class ProveedorContexto(Protocol):
    nombre: str
    async def recoger(self, trace_id: str) -> list[Senal]: ...
```

**No se modifica `core/`.** El núcleo no tiene ni tendrá una lista de fuentes admitidas, ni
condicionales por tipo de fuente, ni imports de conectores. Está verificado por una prueba que define
una cámara inexistente y comprueba que funciona sin que el núcleo la mencione.

### 6.3 Lo que estas fuentes NO cambian

Las tres restricciones permanentes aprobadas por el CEO se aplican **igual** a toda fuente futura:

- **Capturar no implica inferir.** Un wearable aporta observaciones, no conclusiones.
- **La captura es pasiva.** Ninguna fuente puede desencadenar acciones por sí misma.
- **Sin perfiles persistentes de terceros.** Una cámara que capta a otra persona **no genera señal
  sobre ella**. Esta restricción, hoy sencilla, será exigente con fuentes visuales y merece su propio
  diseño cuando llegue el momento.

### 6.4 Advertencia de arquitectura para cuando llegue el momento

Estas fuentes multiplican lo que AURA puede saber, y algunas —biométricas y de vídeo— son de
naturaleza distinta a las actuales: **no dependen de que el usuario diga o haga nada**. Capturan por
el mero hecho de que exista.

La arquitectura de proveedores hace que **incorporarlas sea técnicamente barato**, y eso es
precisamente lo que obliga a que cada incorporación sea una **decisión deliberada con su propio
gate**, no un efecto lateral de que la interfaz encaje. ADR-0015 autoriza que añadirlas no rompa el
núcleo; **no autoriza añadirlas**.

## 7. Decisión requerida del CEO

1. **P1 — Plataforma objetivo de R1:** ¿opción **D** (Apple Silicon, recomendada), **C** (x86 con
   GPU, más longeva y reparable) o **B** (mini PC, la más económica y la más justa)?
2. **P2 — Modelo base:** ¿se fija la clase **7–8 B** como objetivo, con 3 B de respaldo?
3. ¿Se acepta como regla permanente que **ninguna garantía del sistema pueda depender del modelo**
   (§5), y que cambiar de modelo exija **re-verificar la calidad de decisión**, no sólo la latencia?
4. ¿Se confirma que las fuentes de §6 quedan **documentadas pero no autorizadas**, requiriendo cada
   una su propio gate?

---

## Fuentes externas consultadas

Datos marcados **[terceros]**, no verificados por nosotros:

- [Best Mini PC for Ollama and Local LLMs in 2026](https://www.mayhemcode.com/2026/02/best-mini-pc-for-ollama-and-local-llms.html)
- [Running Ollama on Intel N100 & N150 Mini PC](https://bishalkshah.com.np/blog/ollama-n100-mini-pc-local-ai)
- [RTX 3060 12GB Local LLM (2026)](https://modelfit.io/gpu/rtx-3060/)
- [llama.cpp vs MLX vs Ollama vs vLLM: Apple Silicon 2026](https://contracollective.com/blog/llama-cpp-vs-mlx-ollama-vllm-apple-silicon-2026)
- [Apple Silicon LLM Benchmarks 2026 (M1–M5)](https://llmcheck.net/benchmarks)
- [Ollama VRAM Requirements 2026](https://localaimaster.com/blog/ollama-model-ram-vram-table)
