---
documento: "Auditoría técnica integral del proyecto AURA"
fecha: 2026-07-21
autor: "CTO"
encargo: "CEO — informe con evidencia obtenida del código, sin implementar nada"
base: "main @ 22c4e02 · tag v1.4.0-m3.0"
metodo: "Medición directa sobre el código: AST, trace de cobertura, grafo de imports, grep verificado"
---

# Auditoría técnica integral

Todas las cifras proceden de medición sobre el código en el estado `22c4e02`. Donde un hallazgo
resultó ser un falso positivo del método, se indica.

## 1. Tamaño real del proyecto

| Bloque | Líneas |
|---|---|
| Producción (`aura_skeleton/`) | **2.275** |
| Pruebas (`tests/`) | **2.338** |
| Scripts de demo y validación (raíz) | **1.352** |

Relación pruebas/producción ≈ **1,03**. Sana, pero engañosa por sí sola — ver §6.

Un dato que merece atención: **los scripts sueltos son el 37% del código no productivo** y nadie los
prueba. Son nueve ficheros que se han ido acumulando milestone a milestone.

## 2. Arquitectura actual

```
Entrada          Núcleo (garantías)              Salida
────────         ──────────────────              ──────
conversación ──> Orchestrator
                   ├─ ModelRouter ──> ModelProvider (Ollama)
                   ├─ MemoryStore
                   ├─ RegistroContexto ──> conectores/ (conversación, computador, hogar)
                   └─ MotorAutomatizacion  ← EJECUTOR ÚNICO
                        ├─ dry-run
                        ├─ PermissionManager + KillSwitch
                        ├─ RegistroAdaptadores ──> adapters/ (computador, HA)
                        └─ AuditLog
```

**Lo que la medición confirma que funciona:**

- **Un solo camino de ejecución.** Conversación, reglas y notificaciones convergen en
  `MotorAutomatizacion`. No hay rutas alternativas al sistema de archivos.
- **Acoplamiento al modelo confinado.** Ningún fichero de `core/`, `adapters/` o `conectores/`
  menciona un modelo o runtime concreto. El acoplamiento vive en `modules/providers_real.py`.
- **Núcleo agnóstico de fuentes.** `core/contexto.py` no tiene lista de fuentes admitidas.

## 3. Componentes implementados

| Componente | LOC | Estado |
|---|---|---|
| `adapters/computador.py` | 242 | Completo, con protección TOCTOU |
| `core/orchestrator.py` | 206 | Completo |
| `core/automatizacion.py` | 176 | Completo — ejecutor único |
| `core/notificaciones.py` | 132 | Completo |
| `modules/memory.py` | 129 | Funcional; recall lineal (§10) |
| `core/operaciones.py` | 117 | 9 operaciones tipadas |
| `core/permissions.py` | 110 | 27 acciones catalogadas |
| `core/modelo_usuario.py` | 99 | M3.2a — soberanía |
| `conectores/` (4 ficheros) | 168 | 3 fuentes instrumentadas |
| `core/senales.py` + `contexto.py` + `almacen_senales.py` | 213 | M3.0 |
| `adapters/voice_real.py` | 56 | Whisper/Piper — **28% de cobertura** |
| `bus_nats.py` | 66 | **0% de cobertura** |

## 4. Código muerto

Análisis AST cruzado con búsqueda de referencias en todo el proyecto.

| Símbolo | Fichero | Veredicto |
|---|---|---|
| `metric_inc()` | `observability.py` | **MUERTO.** Definido, nunca llamado |
| `metrics()` | `observability.py` | **MUERTO.** Nunca consultado |
| `_metrics` (dict) | `observability.py` | **MUERTO.** Nunca leído |
| `tipo_de_memoria()` | `almacen_senales.py` | Falso positivo — uso interno |
| `on_turn()` | `orchestrator.py` | Falso positivo — suscrito al bus |

**Hallazgo:** existe un subsistema de métricas completo que **nunca se incrementa ni se consulta**.
La Bible declara observabilidad como principio (**P-ARQ-7**), y la parte de logging y auditoría sí
está viva y probada; la de métricas es una fachada.

No es grave —son ~10 líneas inertes— pero es exactamente el patrón que ya costó ALERTA-004 y
ALERTA-005: **algo declarado en la arquitectura y ausente en la práctica.** Aquí el coste es sólo
código muerto porque nadie dependía de ello.

## 5. Código duplicado

**Siete scripts construyen el `Orchestrator` cada uno por su cuenta:**

```
demo_capacidad_m1.py   evals_m1.py        run_demo_nats.py   run_demo_real.py
demo_capacidad_m2.py   run_demo.py        validar_m1.py
```

Dos de ellos definen además su propio `_say()`, y uno su propio `_build()`.

**Por qué importa más de lo que parece.** Cada script cablea el sistema a mano, y **ALERTA-005 nació
justamente de un cableado incompleto**. Medido:

| Script | ¿Cablea el adaptador del computador? | ¿Cablea la captura de señales? |
|---|---|---|
| `demo_capacidad_m2.py` | **Sí** | **No** |
| Los otros seis | **No** | **No** |

**Ningún punto de entrada del proyecto activa la infraestructura de captura de M3.0.** Está
construida, probada por el camino conversacional… y ningún ejecutable la enciende.

### Aclaración importante: esto NO es ALERTA-006

A diferencia de ALERTA-005, aquí **no hay defecto de arquitectura**: el orquestador acepta el
registro de contexto y la prueba de alcanzabilidad lo verifica por el camino real del usuario. Lo que
falta es que un *punto de entrada* lo pase.

Pero conduce al hallazgo de §12, que sí es accionable.

## 6. Cobertura real frente a cobertura aparente

Medido con `trace` (stdlib) sobre las 258 pruebas. Cobertura global: **84%** (690/823 líneas
ejecutables).

**Esa cifra global es engañosa.** El desglose:

| Módulo | Cobertura | Qué es |
|---|---|---|
| `bus_nats.py` | **0%** | Bus NATS real |
| `modules/providers_real.py` | **0%** | **Proveedor de Ollama — el LLM real** |
| `adapters/voice_real.py` | **28%** | Whisper + Piper |
| Resto del núcleo | 80–100% | Lógica determinista |

> **Los tres módulos que hablan con el mundo real son los tres menos probados.**

El 84% mide sobre todo la lógica que ya era determinista y fácil de probar. **La integración real
—LLM, voz, bus distribuido— tiene cobertura automática cercana a cero** y se ha validado únicamente
con ejecuciones manuales (demos, `validar_m1.py`, `evals_m1.py`).

Eso es defendible —esos módulos requieren servicios externos— pero debe decirse con claridad: **la
red de seguridad automática no cubre la frontera con el mundo real**, que es justo donde aparecieron
los dos defectos más caros del proyecto (grounding y cableado).

## 7. Complejidad de módulos

Complejidad ciclomática aproximada (ramas + 1):

| Complejidad | Líneas | Función | Fichero |
|---|---|---|---|
| **14** | 67 | `ejecutar` | `core/automatizacion.py` |
| **10** | 34 | `infer` | `modules/router.py` |
| 9 | 25 | `_despachar` | `adapters/computador.py` |
| 8 | 38 | `_comprobar_destructiva` | `adapters/computador.py` |
| 8 | 28 | `_validar_ruta` | `core/operaciones.py` |
| 7 | 32 | `on_turn` | `core/orchestrator.py` |

**`ejecutar()` con complejidad 14 es el punto más denso del sistema** — y también el más crítico:
concentra dry-run, permisos, resolución de adaptador, ejecución y auditoría.

Valoración honesta: **su complejidad está justificada**. Es el precio de tener *un solo* camino de
ejecución en vez de varios simples que puedan divergir. Partirlo mejoraría la métrica y empeoraría la
garantía. **No recomiendo tocarlo.**

## 8. Acoplamientos

| Módulo | Depende de | Valoración |
|---|---|---|
| `core/orchestrator.py` | 5 módulos internos | Razonable: es el coordinador |
| `core/automatizacion.py` | 4 | Razonable: es el ejecutor |
| **`modules/providers_real.py`** | **`core.operaciones`, `core.permissions`** | ⚠ **Acoplamiento discutible** |

### El único acoplamiento que señalaría

`providers_real.py` —la capa del modelo— importa del **núcleo** para construir el prompt del sistema
a partir del catálogo. Se hizo así deliberadamente en M2.5, para evitar mantener a mano una copia del
catálogo que divergiera.

La dirección de la dependencia es la correcta (la periferia depende del núcleo, no al revés) y no
rompe ADR-0016. Pero conviene tenerlo presente: **es el punto por el que el modelo "sabe" qué puede
pedir**, y por tanto donde un cambio del catálogo altera silenciosamente el comportamiento del LLM.

## 9. Deuda técnica pendiente

| # | Deuda | Origen | Gravedad |
|---|---|---|---|
| D-1 | **Ningún punto de entrada de producción** | §5, §12 | **Alta** |
| D-2 | Integración real (LLM/voz/NATS) sin cobertura automática | §6 | **Alta** |
| D-3 | **Audit log sin política de rotación** — crece sin límite | Medido: sin `rotate`/`max_size` | **Media** |
| D-4 | Subsistema de métricas muerto | §4 | Baja |
| D-5 | Siete scripts duplicando el cableado | §5 | Media |
| D-6 | `recall` de memoria es lineal sobre todos los ítems | §10 | Media (futura) |
| D-7 | CM1 (memoria en semanas) nunca verificado | Cierre de M1 | **Alta** (bloquea R1) |
| D-8 | HC-1 sin medición válida | D24 | **Alta** (bloquea R1) |

**D-3 tiene una consecuencia que no es obvia:** el audit log es *también* la materia prima de las
señales implícitas de M3.0. Una rotación mal diseñada borraría el historial que la anticipación
necesita. Debe decidirse junto con la política de retención, no como tarea de limpieza.

## 10. Rendimiento — mejoras posibles

Medido sobre el código, no sobre ejecución (las mediciones de ejecución están contaminadas, D33).

| # | Hallazgo | Impacto hoy | Impacto a escala |
|---|---|---|---|
| R-1 | `MemoryStore.recall()` recorre **todos** los ítems y puntúa por solapamiento de palabras | Nulo (12 entradas) | **Alto**: O(n) por turno. Con meses de uso, degrada cada turno |
| R-2 | `PersistentMemory` reescribe el JSON completo en cada `write` | Nulo | **Alto**: O(n) por escritura |
| R-3 | Conector de auditoría hace `readlines()` del fichero entero y descarta lo ya leído | Bajo | **Medio**: crece con el audit log (ver D-3) |
| R-4 | Prompt del sistema incluye las 27 acciones del catálogo (~393 tokens) | **Medido**: coste de prefill en cada turno | Constante |

**R-1 y R-2 son la misma deuda:** la memoria es una lista en memoria persistida como JSON completo.
Funciona con 12 entradas; **con el uso diario de E1 y meses de historial, no**. La Bible ya prevé la
solución (ADR-0007/0011: Qdrant, RAG híbrido), pero no está implementada.

**Este es el trabajo de rendimiento que sí tiene sentido hacer antes del hardware nuevo**, porque no
depende de él y porque su ausencia se notará justo cuando empiece a acumularse el historial que M3
necesita.

## 11. Qué eliminaría hoy si empezara de cero

Con la ventaja de saber cómo terminó:

| # | Qué | Por qué |
|---|---|---|
| 1 | **Los siete scripts sueltos** | Sustituirlos por **un** punto de entrada con banderas. La duplicación de cableado es la causa raíz de ALERTA-005 |
| 2 | El subsistema de métricas | Nació muerto; observabilidad real = logs + audit log |
| 3 | `SimpleMemory` junto a `PersistentMemory` | Dos implementaciones cuando bastaba una con backend intercambiable |
| 4 | La distinción `run_demo` / `run_demo_real` / `run_demo_nats` | Es una bandera, no tres programas |

**Qué NO eliminaría, y conviene decirlo:** el catálogo de operaciones tipadas, el ejecutor único, el
audit log persistente y las pruebas de alcanzabilidad. Son las cuatro piezas que han detectado o
impedido defectos reales, y las cuatro parecían "sobreingeniería" al proponerlas.

## 12. Qué cambiaría ANTES de comprar el hardware nuevo

Esta es la pregunta más accionable, y la auditoría le da una respuesta concreta.

### Prioridad 1 — Un punto de entrada de producción (D-1)

**Hoy no existe nada que ejecutar para "usar AURA".** Hay nueve scripts de demo y validación; ninguno
es el programa que se dejaría corriendo.

Cuando llegue el hardware, el escenario E1 exige exactamente eso: **AURA encendida y en uso diario**.
Sin un punto de entrada único, lo que ocurrirá es que alguien adapte deprisa uno de los siete
cableados parciales — y el que menos capacidades enciende es el más probable, porque es el más
simple.

**Riesgo concreto y medido:** ninguno de los siete activa la captura de señales de M3.0. Se
empezaría a acumular uso real **sin registrar las señales que M3 necesita**, y el problema no se
notaría hasta semanas después, cuando el historial estuviera vacío.

Es la repetición exacta del patrón de ALERTA-004/005, y es evitable con trabajo que **no depende del
hardware**.

### Prioridad 2 — Memoria escalable (R-1, R-2)

Antes de que empiece a acumularse historial real, no después. Migrar una memoria con meses de datos
es mucho más caro que construirla bien con 12 entradas.

### Prioridad 3 — Política de rotación del audit log (D-3)

Decidirla **antes** de generar el historial que va a rotar, y coordinada con la retención de señales.

### Lo que NO haría antes del hardware

- Optimizar `ejecutar()` (§7): su complejidad es el precio de una garantía.
- Añadir cobertura a `providers_real.py` con dobles: sería probar el doble, no el sistema (D34).
- Cualquier trabajo sobre inferencia, anticipación o avatar: depende de datos o plataforma.

## 13. Riesgos vivos

| # | Riesgo | Probabilidad | Impacto |
|---|---|---|---|
| **A** | Al llegar el hardware se cablea un punto de entrada incompleto y se pierde captura de señales | **Alta** | **Alto** — retrasa M3 semanas sin avisar |
| **B** | El historial crece y la memoria lineal degrada cada turno | Alta a medio plazo | Medio |
| **C** | El audit log crece sin límite hasta llenar el disco | Media | **Alto** — ya ocurrió una vez con los modelos (D27/D31) |
| **D** | Un cambio de modelo degrada la calidad de decisión sin que la latencia lo delate | Media | Alto |
| **E** | Copia única del repositorio: sin remoto configurado | Media | **Muy alto** — pérdida total |

**El riesgo E sigue siendo el más grave y el más barato de cerrar.** Dos copias verificadas, ambas en
la misma habitación.

## 14. Conclusión

El proyecto está **arquitectónicamente sano**: un solo camino de ejecución, núcleo desacoplado de
modelo y hardware, garantías deterministas y verificadas. Las decisiones estructurales han resistido
tres milestones y varias correcciones.

La deuda real no está en el diseño, sino en **la frontera entre el sistema y su uso**: no hay
programa que ejecutar, la integración real no tiene red de seguridad automática, y la memoria no
escala más allá de la docena de entradas que hoy tiene.

Son exactamente las tres cosas que se volverán urgentes **el día que llegue el hardware**, y las tres
se pueden preparar sin él.
