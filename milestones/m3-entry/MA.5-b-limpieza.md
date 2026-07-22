---
documento: "MA.5-b — Limpieza y convergencia: resultado (sin eliminacion)"
fecha: 2026-07-22
autor: "CTO"
estado: "Implementado — pendiente de gate de integracion del CEO."
origen: "Linea MA; condicion de MA.5-b (no eliminar sin prueba objetiva) y D42"
---

# MA.5-b — Limpieza y convergencia arquitectonica

MA.5 se dividio en dos: **MA.5-a** (convergencia de ejecutables → `composicion`, cerrada) y **MA.5-b**
(codigo muerto). Este documento registra el resultado de MA.5-b.

## Condicion fijada por el CEO

No se elimina nada solo porque "parezca muerto". Toda eliminacion debe demostrar con evidencia objetiva
**(1)** absorcion/sustitucion por otro mecanismo (convergencia), **o (2)** que nunca fue comportamiento
observable ni contrato vigente. Si no puede demostrarse una de las dos, se **conserva y se clasifica**.

## Investigacion — el subsistema de metricas

Unico objetivo documentado de "codigo muerto": `observability.py` — `metric_inc()` / `metrics()` /
`_metrics`.

| Prueba | Resultado |
|---|---|
| ¿Tiene llamadores? | **No.** Nadie incrementa ni lee metricas (write-only, sin cablear). |
| ¿Esta en `test_contracts.py`? | **No** (no es un contrato *probado*). |
| Condicion (1) absorbido/sustituido | ❌ No: los logs (`obs.log`) no sustituyen contadores; nada lo absorbe. |
| Condicion (2) nunca fue contrato | ❌ **No demostrable:** Bible **7.4** (operacion minima viable) exige *"metricas basicas (P-ARQ-7)"*. Es un **contrato documentado**. |

**Conclusion:** no es codigo muerto eliminable, sino la **implementacion sin cablear de un contrato
vigente** (7.4 / P-ARQ-7). Eliminarlo violaria la condicion de MA.5-b.

## Contradiccion registrada

- **Bible 7.4 / P-ARQ-7:** "metricas basicas" son parte de la operacion minima viable → el contrato existe.
- **Implementacion:** `metric_inc`/`metrics` existen pero **no estan cableadas** → el contrato **no esta realizado**.
- Esa brecha es **consciente y rastreable** (aqui, en el codigo y en D42).

## Resultado

- **Ninguna eliminacion.** El subsistema de metricas se **conserva**.
- **Clasificado** como implementacion pendiente del contrato P-ARQ-7: en el codigo
  (`observability.py`) y en el acta (**D42**).
- **D42** (regla permanente): un elemento pendiente de contrato no vuelve a considerarse "codigo
  muerto" mientras el contrato siga vigente; debe quedar identificado en la documentacion arquitectonica.

## Alcance (guardado)

MA.5-b **no** implementa metricas: cablear el contrato P-ARQ-7 seria una **capacidad funcional nueva**,
una iniciativa independiente a tratar cuando corresponda. El objetivo de MA.5-b era solo limpieza y
convergencia; MA.5-a cubrio la convergencia de ejecutables, y MA.5-b concluye que **no hay eliminacion
segura que hacer**.

**Linea MA:** MA.1 ✅ · MA.2 ✅ · MA.5-a ✅ · MA.3 ✅ · MA.4 ✅ · MA.5-b ✅ (sin eliminacion; clasificacion + D42).
