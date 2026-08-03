---
documento: "Deuda técnica registrada de N2 (memoria semántica)"
fecha: 2026-07-28
autor: "CTO / Director"
origen: "Auditoría post-implementación de N2 aprobada por el CEO (2026-07-28)"
estado: "REGISTRADA. No bloquea N2. Reevaluar ANTES de escalar la memoria semántica."
base: "main @ e4a502e (N2 integrada, Quality Gate PASS 386/3)"
---

# Deuda técnica de N2 — memoria semántica

Deuda **identificada por la auditoría post-implementación** de N2 y **autorizada a registrar** por el CEO
(2026-07-28). Ninguna de estas partidas **bloquea N2**: la capacidad cumple su objetivo (el `PlanActivacion`
gobierna una materialización real), respeta el contrato `MemoryStore` y no rompe a ningún consumidor
(verificado: todo el sistema usa solo `write`/`recall`). **Condición explícita del CEO: todas deben
reevaluarse antes de escalar la memoria semántica** (corpus grande, uso sostenido, o promoción de N2 a
implementación de producto).

D-N2-1 (docstring contradictorio sobre numpy) **NO figura aquí**: se corrigió antes del cierre de N2, como
exigió el CEO (la contradicción desapareció por completo).

## D-N2-2 · Acoplamiento a un atributo privado de N1

- **Qué es.** `SemanticMemory` accede a `self._store._items` —atributo **privado** de `PersistentMemory`—
  para recorrer el corpus.
- **Evidencia.** `walking-skeleton/aura_skeleton/modules/memory_semantic.py:63` (precomputo de vectores) y
  `:101` (recorrido en `recall`).
- **Riesgo.** Si N1 cambia su representación interna (`_items`), N2 se rompe silenciosamente. Es
  acoplamiento a implementación, no a contrato.
- **Reevaluar cuando.** Se toque la estructura interna de `PersistentMemory`, o se introduzca un tercer
  nivel/loader de memoria. **Corrección natural:** exponer en `MemoryStore` (o en N1) un iterador público
  de items, o que N2 mantenga su propio almacenamiento en lugar de leer el de N1.

## D-N2-3 · Reconstrucción completa de embeddings en cada arranque

- **Qué es.** El `__init__` de `SemanticMemory` **re-embebe todo el corpus** cargado de disco; los vectores
  **no se persisten** (viven solo en RAM).
- **Evidencia.** `memory_semantic.py:63`. Medición de ejecución (auditoría, 2026-07-28): **15.275 ms para
  50 recuerdos ≈ 305 ms/recuerdo** en el equipo actual (2 CPU, sin GPU). Es coste **lineal** en el número
  de recuerdos.
- **Riesgo.** Con una memoria personal real (cientos/miles de recuerdos), el **arranque de N2** pasaría de
  segundos a minutos. Aceptable hoy (N2 solo se materializa en perfil alto y el corpus es pequeño); no a
  escala.
- **Reevaluar cuando.** El corpus supere unos pocos cientos de recuerdos, o N2 sea la implementación por
  defecto. **Corrección natural:** persistir los embeddings junto a los items (o en un sidecar) e
  incrementalmente; a mayor escala, un índice ANN (hnswlib/faiss/Qdrant, ADR-0007/0011).

## D-N2-5 · `SemanticMemory` no implementa `olvidar` ni `marcar`: la soberanía se rompe con N2 activa

**Registrada el 2026-08-03 como deuda INDEPENDIENTE** por decisión del CEO, deliberadamente separada
del incremento que restaura la garantía de ADR-0014: son problemas distintos y no deben mezclarse.

- **Qué es.** `ModeloUsuario` invoca `olvidar`, `marcar` y `_items` sobre el objeto de memoria que le
  entrega la composición. `PersistentMemory` (N1) los define; **`SemanticMemory` (N2) no**.
- **Evidencia `[EJEC 2026-08-03]`.** Con N2 instanciada sobre el artefacto real:

  ```
  olvidar sobre N2 -> AttributeError: 'SemanticMemory' object has no attribute 'olvidar'
  ```

- **Por qué NO afecta al usuario hoy.** N2 **nunca se materializa** en este equipo (RAM 3,6 GB frente
  al umbral de 8 GB, y no existe detector de hardware real). La composición entrega siempre N1, que sí
  los implementa.
- **Por qué hay que registrarla igualmente.** Se activaría **el día exacto** en que se resuelva el
  hardware y N2 empiece a materializarse: justo cuando nadie esté mirando esta parte. La capacidad 3
  (Modelo de Usuario) se cerró demostrando el olvido persistente **sobre N1**; esa demostración no
  cubre N2. Es el patrón «declarado ≠ real» esperando a que cambien las condiciones.
- **Cumple el criterio de deuda** (CEO, 2026-08-02): compromete una **garantía de soberanía del
  usuario** —poder olvidar lo que AURA sabe de él— y produciría un fallo en ejecución, no una molestia.
- **Reevaluar cuando:** N2 pase a materializarse en algún entorno, o antes de promover N2 a
  implementación por defecto. **Corrección natural:** que `SemanticMemory` delegue `olvidar`/`marcar` en
  el `PersistentMemory` que ya envuelve, reindexando sus vectores en consecuencia.

  Relacionado con **D-N2-2** (acoplamiento a `_items`): ambas nacen de que la delegación de N2 sobre N1
  es parcial y no está fijada por contrato.

## Fragilidad latente ante `restore()`

- **Qué es.** `self._vectores` se mantiene alineado por índice con `self._store._items` **solo** vía
  `write`. `PersistentMemory.restore()` (y `_load` de un backup) reconstruyen `_items` **sin** actualizar
  `_vectores` → **desalineación**.
- **Evidencia (ejecución, auditoría 2026-07-28).** Tras `mem._store.restore(...)`: `items=1` frente a
  `vectores=2`. Con un restore que **añada** items, `recall` accedería a `self._vectores[i]` fuera de rango
  (`IndexError`) o puntuaría recuerdos con el vector equivocado.
- **Por qué NO es un bug activo.** `restore`/`backup`/`verify` **no son parte del contrato `MemoryStore`**,
  y **ningún componente del sistema los invoca sobre la memoria** (verificado: todo consumidor usa solo
  `write`/`recall`). La fragilidad solo se materializaría si un código futuro llamara `restore` sobre una
  instancia de N2 viva.
- **Reevaluar cuando.** Se conecte recuperación ante desastres (M1.1) a la memoria semántica, o N2 exponga
  el ciclo de backup/restore. **Corrección natural:** que N2 recompute (o invalide) `_vectores` al
  restaurar, o que herede/observe los cambios de `_items` de N1.

## D-N2-4 · El olvido persistente (soberanía) no está soportado sobre N2

- **Qué es.** El MVP del Modelo de Usuario (2026-07-28) introdujo `memoria.olvidar(predicado)` y
  `memoria.marcar(predicado, campos)` para que *"olvida esto"* / *"eso ya no es cierto"* **persistan** tras
  un reinicio. Ambos existen en **N1 (`PersistentMemory`)** y en `SimpleMemory`, pero **NO en N2
  (`SemanticMemory`)**.
- **Consecuencia (asimetría señalada por el CEO).** Con el perfil por defecto la memoria es N1 y el olvido
  persistente funciona (demostrado con reinicio). Con un perfil alto en el que el plan materialice **N2**,
  `ModeloUsuario.borrar`/`refutar` invocarían `olvidar`/`marcar` sobre `SemanticMemory`, que no los tiene
  → **`AttributeError`**: el usuario no podría gobernar (olvidar/corregir) lo que AURA sabe de él.
- **Por qué NO bloquea el MVP.** El comportamiento demostrado corresponde al perfil actual (N1). En esta
  máquina N2 no se materializa (`ram < 8 GB`).
- **Condición del CEO (2026-07-28).** *"Esta deuda debe resolverse antes de considerar la memoria
  semántica completamente gobernable."* No se considera N2 "gobernable" hasta que soporte el olvido y la
  refutación persistentes.
- **Corrección natural.** Añadir `olvidar`/`marcar` a `SemanticMemory` delegando en su `_store`
  (`PersistentMemory` interno) y **reconstruyendo `_vectores`** tras el cambio (relacionado con D-N2-2 y
  con la fragilidad de `restore`). Es simétrico al patrón ya usado por N2 para `write`.

## Regla de reevaluación (condición del CEO)

Estas partidas **no se tocan mientras N2 permanezca como validación arquitectónica con corpus
pequeño**. Antes de **escalar la memoria semántica** —más recuerdos, uso sostenido, o N2 como producto por
defecto— se **reabren y se resuelven** las que apliquen, bajo el método estándar (D47) y con gate del CEO.
