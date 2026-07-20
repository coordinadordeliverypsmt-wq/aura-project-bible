---
documento: "Architecture Review — M2.0 Exit"
version: 1.0.0
autor: "CTO"
fecha: "2026-07-20"
estado: "Pendiente de aprobación del CEO para autorizar M2.1"
---

# Architecture Review — M2.0 Exit

Alcance de M2.0: corregir los tres defectos preexistentes (H1, H2, H3) **antes** de construir
capacidad alguna. No se ha implementado ninguna capacidad de M2.1.

**Quality Gate: PASS — 151 pruebas + 8 contratos** (al entrar en M2.0: 49 + 6).

## H1 — Contrato `Adapter` corregido y verificado por firma

**Antes:** el Protocol declaraba `execute(command, args)`; el orquestador llamaba con cuatro
argumentos. `runtime_checkable` solo comprueba que el método exista, así que la prueba de contrato
pasaba con una declaración incorrecta.

**Después:**

```
contrato : ['command', 'args', 'trace_id', 'event_id']
real     : ['command', 'args', 'trace_id', 'event_id']
```

**Evidencia:** 2 pruebas nuevas en PASS.
- `test_contrato_adapter_firma` — compara con `inspect.signature`, no con `isinstance`.
- `test_contrato_adapter_refleja_la_llamada_real_del_orquestador` — fija los cuatro parámetros
  exactos, de modo que un cambio en el orquestador que no se refleje en el contrato rompa la prueba.

Se documentó en el Protocol por qué `event_id` es obligatorio: los adaptadores lo usan para
**idempotencia** (3.3 §3). En M1 era teórico; en M2, un evento reentregado sin idempotencia produce
**dos efectos reales sobre archivos**.

## H2 — Audit log persistente

**Antes:** `_records`, lista en memoria, perdida en cada reinicio.
**Después:** `AuditLog` en formato **JSONL append-only** con `fsync` tras cada anexión.

**Decisiones de diseño y su porqué:**

| Decisión | Motivo |
|---|---|
| JSONL append-only, no array JSON reescrito | Un corte durante la escritura solo puede dañar **la última línea**, no el historial completo |
| `fsync` tras cada anexión | Sobrevive a un **corte de energía**, no solo a un reinicio limpio. Más lento; es el compromiso correcto para un registro forense |
| Línea corrupta se descarta, no invalida el archivo | La pérdida se acota a un registro |

**Evidencia:** 3 pruebas en PASS.
- `test_audit_log_sobrevive_reinicio` — escribe con una instancia y lee con **otra distinta**: la
  segunda solo puede obtener los datos del disco.
- `test_linea_truncada_no_invalida_el_historial` — se corrompe deliberadamente la última línea y se
  comprueba que las anteriores sobreviven.
- `test_log_con_audit_persiste_automaticamente` — integración: solo los registros marcados
  `audit=True` llegan al disco; el ruido operativo no contamina el registro forense.

## H3 — Catálogo explícito de acciones

**Antes:** categorías abstractas (`organizacion`, `monitoreo`).
**Después:** **27 acciones** — 12 verdes, 15 rojas, conjuntos disjuntos.

**Criterio de clasificación declarado en el código: REVERSIBILIDAD.**
- **Verde:** no altera el estado del usuario (lectura, consulta) o es trivialmente reversible.
- **Roja:** altera o destruye estado, o produce efectos fuera del sistema.

Deliberadamente conservador: **ante la duda, roja.** Un falso positivo cuesta una confirmación; un
falso negativo puede destruir datos irrecuperables (RN-1).

`GREEN` y `RED` se **derivan** del catálogo — fuente única de verdad, sin listas paralelas que puedan
divergir.

**Evidencia:** 97 pruebas parametrizadas en PASS, sobre el catálogo **completo**, no una muestra.
- Toda acción roja exige confirmación (tolerancia cero a falsos negativos).
- Toda acción roja confirmada procede — el guardarraíl no es un bloqueo ciego.
- Toda acción verde se auto-ejecuta — si pidieran confirmación, el sistema sería inusable.
- Toda acción declara efecto y descripción (auditable).
- **`test_criterio_de_reversibilidad_es_coherente`** — regla estructural: nada con efecto
  `altera`, `destruye` o `externo` puede estar en verde. Impide que una **futura** ampliación cuele
  una acción destructiva en la lista verde por descuido. Verifica el criterio, no cada caso.

## Divergencia consciente respecto a la Bible — requiere ratificación

**6.4 §1 sitúa "organizar" en lista verde.** Al descomponer esa categoría en operaciones concretas,
`mover_archivo` y `renombrar_archivo` **alteran el estado del usuario** y pueden perder datos si el
destino colisiona.

Se han clasificado en **ROJA**, en contra de la letra de 6.4 §1. Es una decisión consciente, no un
descuido, y está anotada en el código. Consecuencia práctica: organizar una carpeta pedirá
confirmación.

**Alternativa si el CEO prefiere respetar 6.4 §1:** mantenerlas en verde **condicionadas a dry-run
previo obligatorio** — el usuario ve el plan de movimientos antes de que se ejecute, lo que preserva
la fluidez sin renunciar al control. Requiere que el dry-run (M2.3) exista antes que el adaptador
(M2.2), invirtiendo el orden previsto.

**Se solicita ratificación del CEO.** Hasta entonces rige la clasificación conservadora.

## Estado de contratos

| Contrato | Estado |
|---|---|
| `ModelProvider`, `MemoryStore`, `EventBus`, `VoiceAdapter` | **Invariantes** — sin tocar |
| `Adapter` | **Declaración corregida** para reflejar el uso real. Sin cambio de comportamiento |
| ADR-0014 | **Invariante y reforzado**: la clasificación verde/roja se resuelve en el Core, nunca en el LLM |

## Condición de salida de M2.0

| Criterio del CEO | Estado |
|---|---|
| H1: contrato corregido + prueba de **firma** | ✅ PASS |
| H2: audit log persistente + prueba de supervivencia a reinicio | ✅ PASS |
| H3: catálogo explícito + pruebas parametrizadas | ✅ PASS |
| Sin regresión en garantías de M1 | ✅ Quality Gate PASS |

**M2.0 cerrada. Se solicita autorización para iniciar M2.1**, junto con la ratificación sobre
`mover_archivo` / `renombrar_archivo`.
