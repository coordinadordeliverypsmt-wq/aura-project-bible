---
documento: "Revisión estratégica del roadmap — Architectural Review"
fecha: 2026-08-02
autor: "CTO / Comité de arquitectura"
encargo: "CEO — evaluar estado real del producto, arquitectura, deuda, restricciones y alternativas de inversión"
proposito: "Producir evidencia para la decisión del CEO. NO decidir. NO proponer incremento."
base: "main = origin/main = b806c82 · Quality Gate PASS 427/3"
metodo: "D47 — evidencia clasificada [EJEC]/[LECT]/[INFER]/[HIPO]"
---

# Architectural Review — Revisión estratégica del roadmap

**Alcance.** Evaluar el estado real del producto, la arquitectura, la deuda, las restricciones y las
alternativas de inversión. **El objetivo no es decidir**, sino producir la mejor evidencia posible para
que el CEO decida. **No se propone ningún incremento.** El repositorio no se modificó durante la
revisión; toda ejecución instrumentada corrió fuera de él.

**Clasificación de evidencia (D47):** `[EJEC]` medido ejecutando · `[LECT]` leído de artefactos ·
`[INFER]` deducido · `[HIPO]` no verificado.

> **Corrección incorporada tras la primera entrega.** La versión presentada al CEO afirmaba que *"Ollama
> no tiene modelos descargados"*, mirando `~/.ollama`. **Era falso.** El store del servicio está enlazado
> al USB `AURORA_EXT` y contiene **dos modelos íntegros**. La causa del error fue **no ejecutar el
> preflight check obligatorio (D27/D31)** al comenzar la revisión, que lo declara en su segunda línea.
> El §1.2 recoge la medición correcta —que **refuerza** la conclusión estratégica en lugar de
> debilitarla— y la lección quedó registrada en `CHECKLIST-CONTINUIDAD.md` §4.1.

---

## 1 · Estado real del producto

### 1.1 Qué hace AURA hoy

`[EJEC]` Arranca con un comando (`python3 -m aura_skeleton`) y anuncia **12 capacidades activas**:

| Naturaleza | Nº | Efecto real |
|---|---|---|
| Archivos y sistema | 10 | **Sí** — verificado en disco |
| Hogar (`encender`/`apagar_dispositivo`) | 2 | **No** — adaptador mock; solo escribe un log |

`[EJEC]` Responde además **4 conversaciones deterministas** sin consultar al LLM, dentro del presupuesto
HC-1 (≤1200 ms):

| Superficie | Latencia mediana |
|---|---|
| Automatizaciones | **1,9 ms** |
| Modelo de usuario | **2,1 ms** |
| Notificaciones | **6,0 ms** |

### 1.2 El motor de inferencia existe y no es viable

`[EJEC]` Ollama está instalado, **apagado**, con **dos modelos íntegros** en `AURORA_EXT`:
`qwen2.5:3b` (1,9 GB) y `qwen2.5:0.5b` (397 MB); todas las capas verificadas contra el manifiesto.

Medición con el modelo **más pequeño disponible**:

| Caso | Resultado | Frente a HC-1 (1200 ms) |
|---|---|---|
| Prompt «Hola», 8 tokens de salida | **25,8 s** (carga 0,9 s · eval 8,0 s) | **21× por encima** |
| Prompt real de AURA (543 tokens) | **no completa** — error 500 tras 3 min | inviable |

**La restricción no es el modelo, es la máquina.** No se trata de "falta descargar algo más pequeño":
lo más pequeño ya está descargado y tampoco sirve.

`[EJEC]` En consecuencia, por defecto (`AURA_STACK_REAL` no definida) AURA arranca con `MockProvider`:
**un clasificador de 5 reglas de palabras clave**.

### 1.3 Nadie ha usado AURA

`[EJEC]` El audit log de producción contiene **8 entradas, todas de arranque**. No hay memoria
persistida, ni reglas, ni backups. `[INFER]` Ninguna decisión de producto puede apoyarse hoy en
telemetría de uso real, y la capacidad 8 (aprendizaje) carece de materia prima.

---

## 2 · Product Readiness reevaluado

Se reutiliza el marco de 8 dimensiones ya aprobado (`ARCHITECTURE-REVIEW-M2-ENTRY.md` §8).
`[LECT]` M1 = 32% → M2 = 41%.

| Dimensión | Peso | M2 | **Hoy** | Evidencia |
|---|---|---|---|---|
| Entiende y responde con sentido | 15% | 10% | **4%** | `[EJEC]` el modelo existe pero es inalcanzable en la práctica (§1.2); en uso real gobierna el mock |
| **Responde a tiempo** | **25%** | 0% | **6%** | `[EJEC]` 1,9–6,0 ms en las 4 superficies deterministas; el camino general no completa |
| Entrada y salida por voz | 15% | 5% | 5% | `[EJEC]` piper y faster-whisper instalados; sin captura de micrófono |
| Conversación natural (barge-in) | 10% | 0% | 0% | `[LECT]` sin cambios |
| Recuerda entre sesiones | 10% | 9% | **10%** | `[EJEC]` N1 persiste; modelo de usuario inspeccionable, corregible y olvidable tras reinicio |
| **Hace cosas útiles** | **15%** | 12% | **13%** | `[EJEC]` 10 operaciones reales + automatización persistente; hogar simulado |
| Disponible sin fricción | 5% | 0% | **2%** | `[EJEC]` ejecutable único que arranca y reporta estado; sigue siendo consola manual |
| Seguro y gobernable | 5% | 5% | 5% | `[EJEC]` HITL, kill switch, dry-run, TOCTOU, permisos de fuente única |
| | | **41%** | **≈45%** | |

### El dato central

**Cuatro capacidades entregadas movieron el Product Readiness +4 puntos.**

No es un fallo de ejecución. Las tres dimensiones de mayor peso —responde a tiempo (25%), entiende
(15%), voz (15%) = **55% de la métrica**— dependen del hardware, no del software que se escriba.
`[INFER]` Con el hardware actual, el techo del camino "construir más capacidades" ronda el 50%.

---

## 3 · Estado de la arquitectura

### 3.1 Verificablemente sano

- `[EJEC]` **Camino único de ejecución.** Un segundo origen (`origen="regla:<id>"`) entró por el mismo
  gate **sin una línea nueva de permisos**.
- `[EJEC]` **Fuente única de verdad en permisos.** 28 acciones clasificadas; **ninguna capacidad con
  adaptador queda fuera del catálogo**.
- `[EJEC]` **Sustituibilidad por contrato.** `ram_mb=3600` → N1; `ram_mb=16000` → N2, sin que ningún
  consumidor lo note.
- `[LECT]` **Cinco alertas de arquitectura, las cinco resueltas.** Ninguna abierta.

### 3.2 Tensión 1 — el front-end conversacional crece por acumulación

`[EJEC]` **47 patrones literales en 8 grupos**, en cascada con precedencia fija; el árbitro es el orden
en que se escribió el código. Interferencia ya medible de extremo a extremo:

| El usuario dice | AURA responde | Diagnóstico |
|---|---|---|
| «Mis reglas de casa son otras» | lista las automatizaciones | falso positivo |
| «Olvida lo que ha pasado» | «No he encontrado eso para olvidarlo» | superficie equivocada |
| «Olvida esa automatización» | «No he encontrado eso para olvidarlo» | superficie equivocada; la regla sigue activa |
| «Elimina la automatización de copias» | pasa al LLM, sin efecto | hueco sin cubrir |

`[INFER]` El coste es cuadrático: cada superficie nueva puede colisionar con todas las anteriores.

### 3.3 Tensión 2 — la interfaz no siempre es fiel al estado interno

`[EJEC]` Con Home Assistant ausente, AURA responde *«Enciendo la lámpara. [accion
encender_dispositivo ejecutada]»* sin que se encienda nada. La garantía de ALERTA-005 verifica que **el
adaptador respondió**, no que **el mundo cambió**. Cuarto caso del patrón *declarado ≠ real*.

### 3.4 Tensión 3 — capacidades cerradas que no se materializan

`[EJEC]` Arranque real: `plan de capacidades: activas=[] degradadas=['memoria']; memoria -> N1`.

**N2 nunca se materializa**, por dos razones independientes: el detector de hardware real **no existe**
(solo Protocolos), y esta máquina tiene **3,6 GB** frente al umbral de **8 GB**.

`[EJEC]` **~430 LOC** de producción (N2, ModelResolver, NATS, Ollama, voz real) nunca se ejecutan en una
sesión real — código correspondiente a **6 ADRs aceptados**.

---

## 4 · Deuda técnica

### 4.1 Registrada `[LECT]`

`DEUDA-N2-MEMORIA-SEMANTICA.md` (acoplamiento a `_items`; re-embebido a **305 ms/recuerdo**; fragilidad
ante `restore()`; olvido no persistente sobre N2) · `DEUDA-AUTOMATIZACION.md` (8 partidas) ·
`DEUDA-CAPTURA-DE-SENALES.md`.

### 4.2 Riesgo activo descubierto en esta revisión

`[EJEC]` El artefacto que sostiene N2 (470 MB + 17 MB) son **enlaces simbólicos al directorio temporal
de un job de Claude Code**. Si se borra el job, la composición **degrada a N1 en silencio**.

Contradice el principio del CEO —*"la IA es una herramienta de construcción, no una fuente de verdad del
proyecto"*— y la regla D31, que exige que los modelos vivan en `AURORA_EXT`. Mitigación de un minuto,
**pendiente de autorización**.

### 4.3 Señales sin consumidor

`[EJEC]` La captura funciona (2 señales de 3 turnos). `[EJEC]` Pero un hábito como «Siempre reviso el
correo a las 9» **no se captura** — mismo límite de listas literales que §3.2 — y `[INFER]` ningún
componente consume lo capturado.

---

## 5 · Restricciones vigentes, medidas

| Restricción | Estado `[EJEC]` | Consecuencia |
|---|---|---|
| CPU / RAM | 2 núcleos · **3,6 GB** (≈1,2 disponibles) | Bajo el mínimo documentado (≥4 CPU, ≥12 GB) y bajo el umbral de N2 (8 GB) |
| GPU | ausente | Sin aceleración |
| Disco interno | **8,5 GB libres** (85% usado) | Margen escaso |
| **USB `AURORA_EXT`** | montado · **391 MB libres (95% usado)** | Sin espacio para artefactos nuevos |
| Ollama | instalado, apagado, 2 modelos íntegros | **Inviable por latencia** (§1.2) |
| Home Assistant · NATS · Qdrant | ausentes | 2 capacidades simuladas; bus NATS inactivo; sin índice vectorial |
| Presupuesto hardware | **cero** `[LECT]` (D34) | Prohibido fabricar entornos para aprobar hitos |
| Swap | activo en **disco interno** `[EJEC]` | El preflight lo marca como riesgo abierto |

`[LECT]` **P1 (escenario de despliegue) sigue sin decidir desde el 2026-07-21**, y de él dependen 3 de
las 5 fases de M3.

---

## 6 · Alternativas de inversión

Derivadas de la evidencia. **Sin recomendación.**

| | Alternativa | Desbloquea | Contrapartida | Evidencia |
|---|---|---|---|---|
| **A** | **Hardware / entorno de inferencia** | **55% del peso** de la métrica | Dinero; presupuesto hoy cero | §1.2, §2, §5 |
| **B** | **Fase de integración** | Repara interferencia **ya contraída** | No mueve las dimensiones pesadas | §3.2 |
| **C** | **Ampliar el núcleo determinista** | Único camino que **hoy** cumple HC-1 (1,9–6,0 ms) | Construye un sistema de reglas, no una IA; agrava §3.2 | §1.1, §3.2 |
| **D** | ~~Modelo dimensionado al hardware~~ | — | **DESCARTADA POR EVIDENCIA**: el 0.5b ya está descargado y tampoco completa un turno | §1.2 |
| **E** | **Consolidación** (cerrar deuda) | Elimina el riesgo del artefacto temporal, las colisiones y el hogar que miente | Cero valor nuevo visible | §3.2, §3.3, §4.2 |
| **F** | **Uso real sostenido** | Única vía de generar materia prima para la capacidad 8 | Usar AURA hoy es penoso: consola, sin voz, sin LLM viable | §1.3 |

`[INFER]` **A y F están acopladas:** no habrá uso real sostenido mientras el turno no sea usable, y no
lo será sin resolver A. Ninguna de las otras rompe ese lazo.

---

## 7 · Preguntas que solo el CEO puede responder

1. **¿Sigue vigente el presupuesto de hardware cero (D34)?** Determina si A es considerable, y con ella
   el techo de ~50% en Product Readiness.
2. **¿Cuál es el escenario de despliegue (P1)?** Pendiente desde el 2026-07-21; bloquea 3 de 5 fases de M3.
3. **¿Es aceptable que AURA sea útil sin LLM** (camino C), o contradice la visión PIOS de forma inadmisible?
4. **¿Se corrige ya el artefacto de N2 alojado en directorio temporal?** (§4.2)

---

## 8 · Límites de esta revisión

- **No se midió calidad de comprensión**, solo latencia: con turnos que no completan, la calidad no es
  medible en este entorno.
- **No se evaluó seguridad ofensiva**: fuera del encargo.
- Las colisiones de §3.2 son **las encontradas con 14 frases**; `[HIPO]` no se afirma que sean todas.
- **Errores propios corregidos durante la revisión**, declarados para que la evidencia se pondere:
  (a) se contó `detectores.py` como código muerto — son Protocolos, no implementación;
  (b) se concluyó que la captura de señales no producía nada — la consulta las ocultaba por el filtro
  léxico del `recall`; sí funciona;
  (c) se afirmó que Ollama no tenía modelos — se miró el store equivocado por no ejecutar el preflight.
- El Product Readiness es una métrica **con juicio**: los pesos son los aprobados, pero las puntuaciones
  de "entiende" (4%) y "responde a tiempo" (6%) son estimaciones defendibles con la evidencia citada,
  no valores derivados de una fórmula.
