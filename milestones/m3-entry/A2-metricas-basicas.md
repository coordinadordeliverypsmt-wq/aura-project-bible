---
documento: "A2 — Realizacion del contrato de metricas basicas (P-ARQ-7 / Bible 7.4)"
fecha: 2026-07-26
autor: "CTO"
estado: "Implementado — pendiente de gate de integracion del CEO."
origen: "Roadmap post-MA; autorizacion del CEO 2026-07-26 con alcance acotado"
---

# A2 — Metricas basicas de observabilidad (P-ARQ-7)

Cierra la brecha registrada en MA.5-b y D42: el subsistema de metricas existia sin llamadores
(implementacion **pendiente** del contrato, no codigo muerto). A2 lo **realiza** con el minimo
necesario, sin ampliar el alcance.

## 1. Contrato (que exige "metricas basicas")

Tres fuentes concordantes:

- **Bible 3.1 §P-ARQ-7** — observabilidad desde el nacimiento; logs, trazas y **telemetria** son
  dato del usuario, sujetos a ADR-0001 (residencia local, cifrado, minimizacion). Materializacion: 3.3, 7.4.
- **Bible 7.4** (operacion minima viable) — "logging estructurado y **metricas basicas (P-ARQ-7)**";
  "metricas locales (ADR-0001)".
- **Plan de Calidad §3** — materializacion operativa: *"contadores/sumas por nombre (`metric_inc`,
  `metrics()`) — p. ej. eventos publicados, acciones autorizadas/denegadas, latencia por etapa."*

## 2. Evidencia (estado previo)

- **Mecanismo presente**: `observability.py` (`metric_inc`, `metrics`), en memoria, stdlib pura.
- **Cableado ausente**: 0 llamadores en produccion y en pruebas.
- **Puntos de emision reales ya instrumentados con `log`**: `bus.publish` (eventos), `permissions.authorize`
  (autoriza/deniega), `Timer` (latencia por etapa).

## 3. Contradicciones — resultado: ninguna bloqueante

Verificado Bible ↔ ADR ↔ actas ↔ implementacion (D40–D44):

| Chequeo | Resultado |
|---|---|
| Bible 7.4 exige / mecanismo sin cablear (D42) | Realizar el contrato **cierra** la brecha; no la contradice. |
| ADR-0001 / D24 (local, sin telemetria remota) | Metricas en memoria (igual regimen que los logs); nunca salen. |
| ADR-0018 (bus por escenario) | Se instrumenta el bus **E1** oficial; NATS (E2) no se ejercita en el skeleton. |
| CEO "sin paneles de monitoreo" | Se realiza **solo el subsistema de contadores**; los dashboards (7.4) quedan fuera. |
| D40 (composicion ensambla, no decide) | El cableado es observabilidad en bus/permisos, no logica en la composicion. |
| D41 (fuente unica de verdad) | El nombre de cada contador tiene una sola fuente (helper `_metrica_resultado`). |

## 4. Diseno realizado (minimo aprobado)

Dos familias de contadores, cableadas en sus puntos reales reutilizando `metric_inc` (sin dependencias,
sin servicios, sin telemetria, todo en memoria/local):

1. `eventos.publicados` — en `bus.py:InProcessEventBus.publish`.
2. `acciones.autorizadas` / `acciones.denegadas` — en `permissions.py:authorize`, en los **cuatro
   caminos** de decision (kill switch, lista roja confirmada/denegada, lista verde, accion desconocida),
   via el helper `_metrica_resultado(ok)` (fuente unica del nombre, D41).

**Latencia**: se conserva en `Timer` + logs (decision del CEO 2026-07-26). Sin promedios ni
agregaciones hasta que exista necesidad demostrada.

**Naturaleza**: observabilidad **interna**, local, en memoria (ADR-0001/D24). **No** es API publica ni
contrato para consumidores externos — no figura en `contracts.py` ni en `test_contracts.py`.

**Evolucion aditiva**: los contadores son por nombre; incorporar una metrica nueva es una llamada nueva,
sin modificar las existentes (fijado por `test_evolucion_aditiva_por_nombre`).

## 5. Disciplina (TDD estricto)

- **RED**: `tests/unit/test_metricas_observabilidad.py` (7 pruebas de comportamiento observable, por
  DELTA sobre el estado global). Antes del cableado: 6 fallan por delta 0; 1 (aditividad del mecanismo) pasa.
- **GREEN**: cableado minimo → 7/7 verde.
- **Mutacion** (3 degradaciones, todas detectadas):
  (A) bus deja de contar → falla el conteo de eventos;
  (B) el helper no incrementa → fallan los conteos de permisos;
  (C) mapeo invertido (`ok → not ok`) → fallan porque el delta va al contador equivocado (las pruebas
  distinguen autorizada de denegada, no solo "algo cambio").
- **Quality Gate**: PASS (**310 passed / 3 skipped**), sin regresiones.

## 6. Reclasificacion (D42)

El rotulo "PENDIENTE de cableado" en `observability.py` pasa a **realizado en A2 (2026-07-26)**. La regla
**D42 no cambia**; solo transita el estado del elemento que fue su primer ejemplo. La nota equivalente en
el acta de decisiones fundacionales (D42) se propone al CEO por separado (materia de registro del acta).

## 7. Alcance NO tocado (frontera honesta)

- **Dashboards / paneles** de 7.4: fuera (decision CEO).
- **Latencia agregada** (promedios/percentiles): fuera; `Timer` + logs bastan en esta fase.
- **NatsEventBus (E2)**: no instrumentado; se realizara al activarse E2 (ADR-0018/D36).
- **Persistencia cifrada** de metricas: en produccion siguen el regimen local/cifrado de los logs
  (ADR-0001); en el walking-skeleton residen en memoria, como `_records`.
