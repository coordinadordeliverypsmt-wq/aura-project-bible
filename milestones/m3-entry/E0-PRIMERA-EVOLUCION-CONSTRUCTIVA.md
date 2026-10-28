# E0 — Primera Evolución Constructiva Real de AURA

**Fecha:** 2026-09-08 · **Registro de un hecho, no una especificación.**

> AURA construyó una capacidad suya, sola, y la verificó. Este documento registra la evidencia; no
> define arquitectura, no altera decisiones históricas y no reescribe el historial.

---

## Qué se construyó

**Armar la sexta fuente — detección de estancamiento** (`DP-SELF-EVOLUTION-01`, Fase A). La fuente
estaba construida y cableada desde el 2026-09-04, pero **inerte**: su umbral no estaba fijado.

**Decisión humana:** acta `DR-D` del CEO, `K_ESTANCAMIENTO = 100`, registrada por el mecanismo real
(`review.habilitar`, autoridad `ceo`) en `eventos.jsonl` **`seq 1542`**.

**Transformación:** `sustituir_texto("K_ESTANCAMIENTO = None", "K_ESTANCAMIENTO = 100")` sobre
`entorno/control-plane/estancamiento.py`.

---

## Los dos intentos

| | `P-017` | `P-018` |
|---|---|---|
| `propuesta_registrada` | seq 1547 | seq 1575 |
| `propuesta_autorizada` | seq 1548 | seq 1576 |
| `cambio_aplicado` | seq 1549 | seq 1577 |
| `efecto_verificado` | **true** | **true** |
| `verificacion_sana` | **false** | **true** |
| `revertido` | **true** | **false** |

**Los dos aplicaron el cambio de verdad.** La diferencia estuvo en la batería: `P-017` la encontró en
rojo —una garantía exigía `K is None`, escrita cuando aún no existía acta— y **revirtió byte a byte**.
Corregida esa garantía para verificar que un `K` fijado tenga respaldo en un acta del historial,
`P-018` la encontró en verde y el cambio quedó.

Entre ambos hubo que corregir un defecto propio del planificador: **una tarea revertida quedaba
quemada para siempre**. `tarea_planificada` no es `tarea_completada`.

---

## Resultado

```
entorno/control-plane/estancamiento.py:54
K_ESTANCAMIENTO = 100

sha256  b03638a426daf240d2fdfe0f671dbe9a40fe371d2e3ffb77192d67d6472919e2
```

El módulo lo carga como `int`. **La sexta fuente ya no es inerte.**

En el historial de AURA, contado por ella misma:

```
#364  verificacion fallida    ejecutadas=0  efecto_real=0     ← P-017
#365  cola agotada            ejecutadas=0  efecto_real=0     ← tarea quemada
#366  limite de seguridad     ejecutadas=1  efecto_real=1     ← P-018
      actos_humanos=0
```

---

## Validación

**17/17** pruebas de estancamiento · **control-plane completo en verde** · **ruff PASS**. Ninguna
garantía se relajó para conseguirlo: la única reescrita —la de `K`— quedó **más fuerte** que antes,
porque ahora un número puesto a mano en el código sigue cayendo.

---

## Lo que esto significa, y lo que no

**Primera evolución constructiva real completada.** AURA descubrió la capacidad desde su propio
contrato, comprobó que estaba autorizada, la planificó, la construyó, corrió su batería, verificó el
efecto releyendo el fichero y lo registró — **con cero actos humanos durante el ciclo**.

**No significa** que AURA pueda construir cualquier cosa: el verbo sigue acotado por su acta, el
perímetro por el contrato, la operación por un vocabulario cerrado, y el ejecutor revierte ante
cualquier fallo. La capacidad quedó `COMPLETADA` y **no vuelve a proponerse**.
