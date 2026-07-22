---
numero: ADR-0018
titulo: "Bus de eventos por escenario: InProcessEventBus oficial en E1, NatsEventBus reservado a E2"
estado: accepted
fecha: 2026-07-22
fecha-resolucion: 2026-07-22
decisor: "Mauricio (CEO)"
proponente: "CTO"
impacta: ["composicion.py", "ADR-0006", "D40", "MA.5-a"]
origen: "MA.5-a — contradiccion arquitectura↔implementacion reportada 2026-07-22; el CEO aprobo la opcion (b)"
reabre: "—"
supersede: "—"
superseded-por: "—"
motivo-rechazo: "—"
---

# ADR-0018 — Bus de eventos por escenario: InProcessEventBus oficial en E1, NatsEventBus reservado a E2

## Contexto

Al iniciar MA.5-a (convergencia validacion↔produccion) se detecto una divergencia con evidencia:

- **`composicion.py:132`** —el punto de entrada unico de produccion (D40)— cablea **`InProcessEventBus`**
  de forma fija, sincrona, sin opcion de bus.
- **ADR-0006** (`accepted`) declara **NATS** como *"bus oficial de eventos"*, sin acotar por escenario.

Es decir: el punto de entrada de produccion no usa el bus que ADR-0006 declara oficial. Pero la
evidencia documental matiza que **no es una contradiccion con la Bible**, sino con la *seleccion
universal* de ADR-0006:

- **Bible 3.3 §2** define el bus por **contratos independientes del broker** y enumera **in-process**
  como una opcion de broker valida junto a NATS/MQTT/Redis: *"Los contratos aqui valen para cualquier
  broker que los cumpla (P-ARQ-4)"*. Cambiar de broker **no toca a los consumidores** (3.3, pregunta 3).
- **D36** oficializa **E1 (uso personal, un solo proceso)** como escenario inicial y **E2 (hogar
  inteligente, multi-proceso)** como objetivo de la primera version estable.
- **`run_demo_nats.py`** ya probo empiricamente la sustitucion in-process→NATS con los mismos
  consumidores sin cambios (P-ARQ-4 validado).

Para un despliegue E1 (un solo proceso, en la maquina del usuario) un bus in-process es funcional y
correcto; NATS aporta valor cuando hay multiples procesos (E2). Forzar NATS en E1 anadiria un servicio
que ese escenario no necesita, y volveria `composicion` asincrona (por `NatsEventBus.connect`) sin
beneficio para el producto real de hoy.

## Alternativas consideradas

### A. Cablear NATS en `composicion` para cumplir ADR-0006 al pie de la letra
Pros: `composicion` produciria el bus que ADR-0006 llama oficial. Contras: toca arquitectura de
produccion para satisfacer una decision documental que **hoy no representa el estado real del
producto** (E1); vuelve `componer()` asincrona; anade un servicio a un escenario que no lo requiere.
**Descartada por el CEO (2026-07-22):** *"No corresponde forzar la implementacion para que coincida
con una decision documental que hoy no representa el estado real del producto."*

### B. Precisar la seleccion por escenario (elegida)
Formaliza una decision ya tomada por el CEO (opcion b). Por ser una formalizacion, se omiten los 4
niveles (D3).

## Decision

1. **`InProcessEventBus` es el bus oficial de E1** (despliegue personal, un solo proceso). Es lo que
   `composicion.componer()` cablea, y queda **documentado como correcto**, no como interino sin decidir.
2. **`NatsEventBus` queda reservado explicitamente para E2** (multi-proceso / hogar / distribuido).
3. **La sustitucion entre ambos sigue siendo un requisito arquitectonico** (P-ARQ-4, Bible 3.3),
   verificado de forma viva por `run_demo_nats.py` — **pero no es una obligacion del despliegue E1.**
4. Este ADR **refina** ADR-0006 (no lo revoca): ADR-0006 eligio NATS como broker; ADR-0018 acota esa
   eleccion por escenario, de forma consistente con Bible 3.3 (broker sustituible) y D36 (E1/E2).

## Consecuencias

**Positivas:** `composicion` deja de ser una divergencia sin decision y pasa a ser *correcta para E1*;
los scripts que ejercitan NATS se reencuadran como **validacion de E2**, no como puntos de entrada de
produccion; la sustituibilidad, ya probada, no se pierde. **Negativas:** hay dos rutas de bus que
mantener; la sustituibilidad se puede pudrir si el arnes de E2 (`run_demo_nats`) deja de ejercitarse.
**Riesgos aceptados:** la validacion real de NATS/E2 depende de un entorno multi-proceso, hoy diferido;
mientras tanto `bus_nats.py` conserva 0 cobertura de prueba automatizada (solo el arnes lo ejercita).

## Impacto (acta D11 — obligatorio)

| Dimensión | Impacto |
|---|---|
| Seguridad | Neutro. Ambos buses son 100% locales (ADR-0001); in-process reduce la superficie (sin socket). |
| Privacidad | Neutro/positivo: E1 in-process no expone un puerto de broker. |
| Modularidad | Positivo: reafirma P-ARQ-4 (consumidores independientes del broker); la eleccion es config, no rediseño. |
| Costo | Positivo: E1 no paga el coste operativo de un servicio NATS que no necesita. |
| Experiencia de usuario | Neutro: el usuario de E1 no arranca ni administra un broker aparte. |
| Mantenimiento futuro | Requiere mantener vivo el arnes de sustituibilidad (E2) para que el salto a NATS no se degrade. |

## Trazabilidad

Capítulos a actualizar: **ADR-0006** (nota de refinamiento → ADR-0018); **acta D40** (precision del
alcance de "ejecutable", ver MA.5-a); **`entorno-objetivo/02-estrategia-de-despliegue.md`** (bus por
escenario). Bible **3.3** ya es consistente (broker sustituible) — se anota, no se modifica. Módulos de
código afectados: `composicion.py` **no cambia** (se documenta que InProcessEventBus es correcto para E1).
