---
numero: ADR-0020
titulo: "Memoria por niveles de capacidad del hardware (evolucion por capacidades, no preferencia de motor)"
estado: accepted
fecha: 2026-07-22
fecha-resolucion: 2026-07-22
decisor: "Mauricio (CEO)"
proponente: "CTO"
impacta: ["ADR-0011", "ADR-0007", "ADR-0016", "Bible 4.1", "A1 (analisis de memoria)"]
origen: "A1 (analisis comparativo de memoria) + directriz del CEO 2026-07-22: evolucion por capacidades del hardware"
reabre: "—"
supersede: "—"
superseded-por: "—"
motivo-rechazo: "—"
---

# ADR-0020 — Memoria por niveles de capacidad del hardware

## Contexto

El analisis A1 concluyo, con evidencia, que:
- La recuperacion **semantica** es necesaria (el interino lexico de MA.2a no cumple RF-1 ni el recall
  ≥90% de 2.5 §5.2, y es precondicion de M3.3).
- El **cuello de botella real es el modelo de embeddings** (texto→vector), no el almacen vectorial.
- El **almacen es secundario a escala E1**: una busqueda por fuerza bruta sobre ~100.000 vectores midio
  **242 ms** en hardware modesto (bajo el presupuesto R1 de 1200 ms), y ~45-90 ms a escala cercana.

ADR-0011 eligio **Qdrant** (primario) y registro **pgvector** como alternativa ligera, con la clausula
*"el walking skeleton en hardware objetivo puede comparar ambos; el contrato de memoria (4.1) es
identico para los dos"*. A1 aporto un matiz: en E1 el stack **no despliega PostgreSQL**, luego pgvector
**anadiria** un motor; y un almacen dedicado (Qdrant) esta **sobredimensionado** a escala E1 (regla 13,
D26).

**Directriz del CEO (2026-07-22) — evolucion por capacidades del hardware.** AURA no se acopla a una
sola implementacion de memoria: **evoluciona segun los recursos del equipo donde se instale**. Un solo
proyecto, una sola arquitectura, adaptacion automatica al entorno; mas hardware = mas capacidad,
autonomia y rendimiento, **sin bifurcar el codigo**. Este ADR materializa esa directriz para la memoria.

## Alternativas consideradas

### A. Fijar un unico motor (Qdrant, o pgvector, o minimo) para todos los despliegues
Contras: o sobredimensiona el hardware modesto (Qdrant en E1), o limita el potente (minimo en un
servidor). Acopla la capacidad de AURA a una eleccion tecnologica fija. **Descartada.**

### B. Memoria por niveles de capacidad, contrato unico (elegida)
Materializa la directriz del CEO. Por ser formalizacion de una decision ya tomada, se omiten los 4 niveles (D3).

## Decision

La memoria (4.1) se implementa en **niveles de capacidad**, todos **detras del mismo contrato
funcional** (4.1: RAG semantico, recall ≥90%, procedencia y no-fabricacion, aislamiento por `user_id`).
**Lo unico que cambia entre niveles es la implementacion interna del almacen**, elegida
**automaticamente** durante la instalacion o reconfiguracion segun el **hardware detectado**.

Los niveles son **perfiles de ejecucion de una unica arquitectura, NO versiones de AURA**. Hay **un
solo proyecto, un solo codigo, un solo contrato funcional, un solo formato de memoria y una sola
arquitectura**; el usuario **nunca elige "que version instalar"**. AURA no se bifurca: se adapta.

| Nivel | Hardware | Implementacion del almacen |
|---|---|---|
| **N1** | Modesto / presupuesto cero | Embeddings locales + **almacen minimo** (fuerza bruta o indice embebido ligero). **Sin servicios adicionales.** |
| **N2** | Intermedio | **Indice vectorial embebido** (p. ej. HNSW en proceso) **cuando aporte un beneficio real** (volumen/latencia). |
| **N3** | Alto rendimiento | **Qdrant** u otro motor especializado cuando el **volumen o la carga** lo justifiquen. |

Reglas:
1. **El contrato de 4.1 es identico en los tres niveles.** La diferencia es solo la implementacion; los
   consumidores no la conocen (P-ARQ-4).
2. **El modelo de embeddings es comun a todos los niveles** (es el requisito semantico); su tamano/latencia
   puede tambien escalar por nivel. Debe ser **local y open-source** (D24/ADR-0001) en todos los niveles.
3. **Seleccion automatica, reversible y transparente, por capacidad EFECTIVA.** El perfil se elige
   **automaticamente** en instalacion/reconfiguracion sobre **hardware VERIFICADO en el momento** (D27),
   nunca supuesto. No basta con las specs (RAM/CPU/GPU): el perfil se determina por **capacidad efectiva
   verificada con pruebas reales** —latencia, memoria disponible, velocidad de inferencia— combinadas con
   las specs y los **requisitos minimos de cada capacidad** (**D44**); el hardware declara lo potencial,
   las pruebas determinan lo efectivo (evita clasificar como N3 un equipo con GPU que no cumple en la
   practica). Se **recalcula** ante cambios de hardware, sistema operativo, modelos o una version de AURA
   mas eficiente. La evolucion es **bidireccional y transparente**: mas capacidad → promueve; menos →
   **degrada sin perder memoria, configuracion ni compatibilidad**. Ejemplos: un portatil modesto usa el
   perfil ligero; trasladado a un equipo con mas RAM/GPU (y que **pasa las pruebas**), habilita
   implementaciones mas avanzadas; de vuelta a un equipo menos potente, degrada conservando el historial.
   El usuario **no interviene**.
4. **Independencia tecnologica.** Los perfiles se definen por **capacidades**, no por el nombre de una
   tecnologia. Hoy pueden ser almacen minimo / HNSW embebido / Qdrant; si en cinco anos aparece un motor
   mejor, ocupa el perfil que corresponda **sin cambiar la arquitectura**. Ningun motor es "el elegido":
   cada uno es el adecuado a un nivel de recursos. **Es evolucion por capacidades, no preferencia de motor.**

**Relacion con ADR-0011:** lo refina, no lo revoca. Qdrant (ADR-0011 primario) pasa a ser el motor de
**N3**; pgvector, una opcion de N2/N3 donde PostgreSQL ya exista. Se anade **N1** (minimo) como la base
para hardware modesto, que ADR-0011 no contemplaba por asumir PostgreSQL desplegado.

## Consecuencias

**Positivas:** AURA aprovecha el hardware disponible sin ramas de codigo; en un equipo modesto funciona
sin servicios; en uno potente escala. Coherente con la neutralidad tecnologica (ADR-0016/D33: la utilidad
puede escalar con el hardware, la seguridad nunca cambia). **Negativas:** hay que mantener y probar la
seleccion automatica y **≥2 implementaciones** del almacen tras el contrato; el conjunto de evaluacion de
recall (≥90%) debe pasar **en cada nivel**. **Riesgos aceptados:** la latencia real del embedder es la
incognita hardware-sensible, a medir en implementacion; migrar el historial entre niveles debe preservar
la evidencia (mismo contrato/formato).

## Impacto (acta D11 — obligatorio)

| Dimensión | Impacto |
|---|---|
| Seguridad | Neutro: todos los niveles son locales (ADR-0001); la seleccion no cambia garantias (ADR-0016). |
| Privacidad | Neutro/positivo: embeddings y almacen locales en todos los niveles; sin claves de terceros (D24). |
| Modularidad | Positivo: un solo contrato (4.1), implementaciones sustituibles (P-ARQ-4); sin bifurcar el codigo. |
| Costo | Positivo: N1 no paga servicios; se escala solo cuando el hardware lo justifica (D26, regla 13). |
| Experiencia de usuario | Positivo: la instalacion se adapta sola; mas hardware = mas capacidad, sin intervencion. |
| Mantenimiento futuro | Requiere mantener/probar la seleccion y ≥2 almacenes; el recall se valida por nivel. |

## Trazabilidad

Refina **ADR-0011** (motores vectoriales) y matiza **ADR-0007**; se apoya en **ADR-0016/D33** (neutralidad),
**P-ARQ-4** (sustituibilidad), **D24/ADR-0001** (local, open-source), **D27** (deteccion de hardware
verificada) y **D36** (escenarios). **Requiere actualizar Bible 4.1** —cuya formulacion actual fija el
motor ("RAG hibrido sobre Qdrant") y afirma "cumple los umbrales"— para (a) describir la memoria "sobre el
motor del nivel de capacidad" y (b) tratar el recall ≥90% como **objetivo a realizar por nivel**, no como
estado actual. Ese cambio de la Bible es **materia reservada al CEO**. Módulos de código: **ninguno en
esta fase** (solo diseno; la implementacion es una fase posterior).

## Principio permanente asociado — D43 (registrado en el acta, 2026-07-22)

> **D43 — Evolucion por capacidades del hardware.** AURA es un solo proyecto, un solo codigo y una sola
> arquitectura que **se adapta automaticamente al hardware detectado**: el contrato funcional de una
> capacidad permanece identico y solo cambia su implementacion interna, elegida —de forma automatica,
> reversible y transparente— en instalacion/reconfiguracion. Mas hardware = mas capacidad, autonomia y
> rendimiento, **sin bifurcar el codigo**; los perfiles se definen por capacidades, no por tecnologias
> concretas. Complementa ADR-0016/D33 (la seguridad nunca cambia con el hardware; la utilidad puede
> escalar). Se aplica primero a la memoria (ADR-0020) y rige cualquier componente futuro con
> implementaciones dependientes de recursos.

## Principios permanentes de la memoria (consolidacion A1 — CEO, 2026-07-22)

Guian **cualquier implementacion futura de memoria**; reafirman y hacen explicitas las garantias de este ADR:

1. **La memoria es un activo permanente.** Es **independiente del motor** que la gestione. Cambiar de N1 a
   N2/N3, o sustituir el motor vectorial por otro en el futuro, **nunca** implica perdida de informacion ni
   migraciones manuales del usuario.
2. **La evolucion es automatica.** Ante una mejora o reduccion de capacidades del equipo, AURA se adapta
   sola al perfil mas adecuado; el usuario **no decide el backend**. La adaptacion es **transparente,
   reversible y verificable**.
3. **La implementacion siempre es sustituible.** ADR-0020 **no** es una decision a favor de un motor
   concreto: Qdrant, pgvector o cualquier alternativa futura son **reemplazables**. Lo permanente es el
   **contrato funcional** y la **compatibilidad** de la memoria.
