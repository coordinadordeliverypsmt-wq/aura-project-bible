# DP-ALERTA-005 · Contrato de correspondencia verificable del motor autónomo

**Estado:** aprobado por el CEO el 2026-11-08 (Alternativa B del Decision Package ALERTA-005).
**Rama:** `integracion/m3-entry`. **Alcance:** aditivo — formaliza y verifica lo que ya es cierto; **no**
reescribe el motor operativo ni conecta el ciclo real a `validar_transicion`/`WAITING_FOR_HUMAN`.
**Prueba que lo hace cumplir:** `entorno/control-plane/test_red_correspondencia_alerta005.py`.
**Mutación:** `entorno/control-plane/mutaciones/correspondencia-alerta005.toml`.

---

## 1 · Una sola fuente de verdad de hechos

El log `eventos.jsonl` (append-only, `seq` monótono, `hash_anterior` encadenado, ancla externa) es la
**única fuente de verdad de hechos**. Toda vista del sistema es una **proyección** de ese log. No existe
—ni debe introducirse— un segundo registro de hechos con autoridad propia.

## 2 · Tres categorías distintas que no deben confundirse

| Categoría | Qué es | Cómo se escribe | Ejemplos |
|---|---|---|---|
| **Estado de tarea** (Máquina A) | valor del ciclo de vida de una *tarea* en `TRANSICIONES` | **solo** `transicion()`/`reconciliar_tras_caida()` vía `validar_transicion` | `WORKING`, `WAITING_FOR_HUMAN`, `DECISION_REQUIRED`, `COMPLETED`, `FAILED` |
| **Evento gobernado** | hecho que **produce estado o concede autoridad**; no puede escribirse en crudo | su **puerta** declarada en `_PUERTA_DE` | `estado_de_tarea`, `propuesta_autorizada`, `review_habilitado`, `criterio_fijado`, `criterio_verificado`, `cuota_observada` |
| **Evento informativo** | hecho que **narra** sin conceder estado ni autoridad | `registrar_evento`/`registrar_evento_si` (crudo permitido) | `propuesta_registrada`, `cambio_aplicado`, `decision_requerida`, `ciclo_detenido`, `veredicto_emitido`, … |

**Invariante de gobierno (INV-G):** `EVENTOS_GOBERNADOS == set(_PUERTA_DE)` y
`_EVENTOS_DE_ESTA_PUERTA == EVENTOS_GOBERNADOS − {estado_de_tarea}` (el estado de tarea tiene su propia
puerta, `transicion`, no la puerta gobernada común). Ningún evento gobernado puede escribirse por
`registrar_evento` crudo; todo evento informativo sí. **La protección es la lista, no el guion bajo.**

## 3 · Matriz de correspondencia aprobada (proyección del ciclo real ↔ Máquina A)

| Evento del ciclo real (Máquina B) | Categoría | Correspondencia con estado de tarea (Máquina A) |
|---|---|---|
| `tarea_planificada` y `propuesta_registrada` (dos eventos distintos) | informativo | `WORKING` (equivalente funcional; el motor no lo materializa como estado de tarea) |
| `revision_sin_revisor_capaz` | informativo | `WAITING_FOR_REVIEW` (`ESTADO_REVISION`, estado compartido) |
| `propuesta_autorizada` | **gobernado (gate de autoridad)** | precondición de ejecución; autoridad humana o `REVIEW:` con acta humana previa |
| `review_habilitado` | **gobernado (gate de autoridad)** | elevación de nivel; solo acto humano con acta |
| `cambio_aplicado` (promovido) | informativo | `COMPLETED` (equivalente funcional) |
| `cambio_aplicado` (revertido) / `cambio_revertido_por_error` | informativo | `FAILED` (equivalente funcional) |
| `decision_requerida` | informativo | **sin correspondencia de estado** — ver §4 |

## 4 · Estados sin correspondencia directa (huérfanos declarados)

- **`WAITING_FOR_HUMAN` (Máquina A) no pertenece al ciclo de autoconstrucción.** El ciclo real nunca
  pone una tarea en ese estado: cuando necesita un humano, **se detiene** (`_detener`) y emite el evento
  informativo `decision_requerida`; el siguiente despertar reintenta. Su modelo es *detener+reintentar*,
  no *transicionar+esperar*. `WAITING_FOR_HUMAN` es el contrato del **camino de delegación multiagente**
  (`agentes.py`/`revisores.py`), que hoy no tiene llamante de producción (ver §6). D-ORCH-6 lo dejó
  correcto y simétrico para ese camino; su valor es futuro, no presente.
- **`decision_requerida` (evento) ≠ `DECISION_REQUIRED` (estado).** El primero es un evento informativo
  que narra "hace falta un humano" y **no concede estado ni autoridad**; el segundo es un estado de
  `ESTADOS_SOLO_HUMANO` cuya salida exige autoridad humana registrada vía `validar_transicion`. Colapsar
  ambos sería el patrón "declarado ≠ real".

## 5 · Los dos gates de autoridad (ambos fail-closed, ambos sobre el mismo log)

1. **Máquina A** — `validar_transicion`: gobierna las transiciones de estado de tarea; salir de
   `ESTADOS_SOLO_HUMANO` (`DECISION_REQUIRED`, `WAITING_FOR_HUMAN`) exige `AUTORIDADES_HUMANAS`.
2. **Máquina B** — `EVENTOS_GOBERNADOS` + `registrar_propuesta_autorizada`/`registrar_review_habilitado`:
   la única puerta de escritura real (`autoconstruccion.ejecutar`) exige `esta_autorizada()`, que solo es
   cierta si consta `propuesta_autorizada` escrita por autoridad humana o `REVIEW:` con acta humana previa.

Ambos comparten la constante `AUTORIDADES_HUMANAS` y el mismo log. **La autoridad humana no es
sustituible por el propio agente** en ninguno de los dos (verificado por sonda, 6/6 fail-closed).

## 6 · Garantías del motor que se conservan (no se tocan)

PARADA consultada en cada vuelta y antes de cada escritura; recuperación por diario antes de planificar;
reversión transaccional por fichero (`cambio_revertido_por_error`); materia reservada/zona (D22); revisor
independiente; confinamiento Landlock; monotonicidad del alcance de REVIEW. **Ninguna es representable en
`TRANSICIONES`; por eso no se conecta el ciclo a la Máquina A.**

## 7 · `estado.json` es caché, no fuente

`estado.json` es una proyección cacheada para consulta humana (CLI `estado`/`handoff`). El ciclo real no
lo consulta: proyecta en vivo desde el log. Puede quedar obsoleto sin afectar la ejecución. **Prohibido
interpretar una proyección (cacheada o en vivo) como una segunda fuente de hechos.** F1/F2/F3 lo
reconcilian cuando se invocan.

## 8 · Protección de la API legada `autoconstruccion.ciclo()`

`ciclo()` llama a `ejecutar()` por su cuenta, sin pasar por la 5ª puerta
`review._exigir_correspondencia_con_el_contrato`. Hoy **no tiene llamante de producción**, así que las dos
vías reales están cubiertas. Deuda condicionada (el propio código la documenta): **si algún día ganara un
llamante de producción**, sería la geometría de ALERTA-005 otra vez. La protección aprobada es **detectar
ese llamante por prueba** (barrido AST recursivo de los módulos de producción; lista blanca explícita, hoy
solo el módulo que define `ciclo()`). Añadir un llamante obliga a actualizar conscientemente la lista
blanca (el control lo hace fallar si crece sin edición explícita) y a dotar a `ciclo()` de su propia
comprobación de correspondencia. No se modifica el runtime del motor activo.

**Alcance y riesgo residual del barrido** (auditoría de seguridad F5, hallazgo ALTO atendido): el barrido
captura toda **referencia estática** a `autoconstruccion.ciclo`/`ciclo` importado —llamada directa, alias
de import (`from autoconstruccion import ciclo as X`), asignación a variable (`fn = ac.ciclo`) y paso como
argumento— que son los descuidos plausibles de un desarrollador. **Declarado explícitamente como riesgo
residual aceptado:** la indirección **dinámica** (`getattr(ac, "ciclo")`, `importlib.import_module(...)`)
**no** es detectable por análisis estático y queda fuera del alcance; requiere intención deliberada, no un
descuido, y aun así no abriría un gate de autoridad nuevo (la 5ª puerta de `ejecutar_bajo_review` sigue
cubriendo las dos vías reales). La protección no promete blindaje frente a un adversario determinado: detecta
la introducción **inadvertida** de un llamante por las formas de código habituales.

## 9 · Qué cierra este contrato

ALERTA-005 queda **conciliada por correspondencia verificable**, no por fusión: una fuente de hechos, dos
proyecciones documentadas, dos gates de autoridad fail-closed, cero caminos de elusión, y una prueba que
falla ante desviaciones reales (no ante cambios de texto). No se creó una tercera máquina de estados.
