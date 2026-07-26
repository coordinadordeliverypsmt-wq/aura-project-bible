---
documento: "Linea base — Congelacion controlada: trabajo verificable sin hardware agotado"
fecha: 2026-07-26
autor: "CTO"
encargo: "CEO — ratificacion de la opcion A: documentar formalmente que el trabajo verificable sin hardware queda agotado y declarar esta como la nueva linea base del proyecto"
base: "main @ b19e3fe (origin/main sincronizada) — Quality Gate PASS (310 passed / 3 skipped)"
estado: "Linea base vigente. El proyecto queda en congelacion controlada hasta un desencadenante autorizado (ver §5)."
---

# Linea base — Congelacion controlada de AURA

Tras cerrar la linea MA (madurez de arquitectura), la iniciativa A1 (analisis de memoria → ADR-0020) y
la iniciativa A2 (realizacion del contrato de metricas P-ARQ-7), la revision del estado real del
repositorio concluye que **el trabajo de arquitectura verificable con el hardware actual queda
agotado**. Este documento formaliza esa conclusion y la declara **nueva linea base** del proyecto.

Las cinco afirmaciones siguientes son el nucleo de la declaracion. Cada una es una condicion permanente
de esta linea base, no una observacion de coyuntura.

## 1. No existe un bloqueo arquitectonico

La detencion **no** obedece a un defecto, una contradiccion ni un limite del diseno. La arquitectura
esta **preparada para continuar**: los contratos, los puntos de extension y los mecanismos de
habilitacion ya existen y estan probados. El **unico factor limitante es la disponibilidad del
hardware** (y de los datos reales que solo el uso sostenido genera) necesario para **validar** las
capacidades restantes. Dicho con precision: no falta *construir* arquitectura, falta *poder verificar*
capacidades sobre un entorno fisico que todavia no existe.

Evidencia del marco ya dispuesto: mecanismo generico de conectores externos (ADR-0019, opt-in +
transparencia + degradacion, sin conector real construido), bus por escenario (ADR-0018: E1 oficial, E2
reservado), memoria por niveles de capacidad (ADR-0020), audit log forense con rotacion (MA.3),
metricas basicas cableadas (A2). Todo esto es **infraestructura lista para habilitar**, no obra pendiente.

## 2. No se considera deuda tecnica

Las funcionalidades pendientes **no fueron omitidas ni pasadas por alto**: fueron **diferidas
deliberadamente** por depender de recursos fisicos o de datos reales, conforme a las decisiones
permanentes del proyecto:

- **D34** — prohibe fabricar un entorno (mocks, datos sinteticos) para aprobar un milestone: la calidad
  de una capacidad probabilistica *es* su acierto sobre datos reales.
- **D39** — desarrollo continuo con restricciones de hardware: se madura lo que se puede con el equipo
  actual y se difiere explicitamente lo que exige el equipo objetivo.
- **D44** — la capacidad efectiva se determina por **pruebas reales**, no por specs: una capacidad
  dependiente del hardware no se declara cumplida hasta verificarse en el entorno que la ejecuta.

| Fase diferida | Depende de | Decision que la difiere |
|---|---|---|
| M3.2b · Inferencia de preferencias | Datos de uso real | D34, D44 |
| M3.1 · Hogar real (Home Assistant) | Instalacion fisica real | D34 |
| M3.3 · Anticipacion (CM4) | M3.2b + datos + calidad de modelo | D34, D44 |
| M3.4 · Avatar | Plataforma de despliegue | D33 |
| HC-1 (latencia e2e) · CM1 (ventana de semanas) | Uso real sostenido (hardware) | D39, D44 |

Diferir con criterio no es acumular deuda: **es gobierno honesto del alcance**. Un requisito
identificado, argumentado y pospuesto por dependencia fisica es lo contrario de una omision silenciosa.

## 3. El estado del proyecto queda congelado de forma controlada

Esta linea base representa un sistema **estable, verificable y listo para evolucionar** cuando cambien
las capacidades del hardware. "Controlada" significa que la congelacion es un estado **elegido y
documentado**, con un punto de reanudacion definido:

- **Estable y verificable ahora:** `main == origin/main @ b19e3fe`, arboles limpios, 0 commits sin
  publicar, **Quality Gate PASS (310 passed / 3 skipped)**. Todo lo construido esta cubierto por pruebas
  y, donde aplico, validado por mutacion.
- **Congelacion, no abandono:** no se retira ni degrada ninguna capacidad; el sistema sigue operativo en
  su perfil actual. Simplemente **no se abre trabajo nuevo** que no pueda validarse.
- **Reanudacion definida:** la salida de este estado esta gobernada por §5 (desencadenantes), no por la
  inercia del roadmap.

## 4. La evolucion futura seguira el principio de capacidades

Cuando exista un equipo con mayor capacidad, **AURA no cambiara de arquitectura ni de proyecto**:
**habilitara automaticamente** nuevas capacidades conforme a **ADR-0020**, **D43** y **D44**.

- **ADR-0020** — la memoria (y toda capacidad dependiente de recursos) opera en **perfiles de capacidad**
  detras de un **contrato funcional unico**; el perfil se selecciona de forma automatica, reversible y
  transparente.
- **D43** — evolucion por capacidades del hardware: un solo proyecto, un solo codigo, una sola
  arquitectura que se adapta al hardware detectado, **sin bifurcar el codigo**.
- **D44** — capacidad efectiva verificada por pruebas: el hardware declara lo potencial, las pruebas
  determinan lo efectivo; el perfil se recalcula ante cambios de hardware, sistema operativo, modelos o
  una version mas eficiente de AURA.

La consecuencia practica: mas hardware = mas capacidad, autonomia y rendimiento, **sin migracion manual
del usuario y sin una nueva version del proyecto**.

## 5. El siguiente trabajo no sera una continuacion artificial del roadmap

No se abrira un hito solo para "seguir avanzando". El proximo hito debera iniciarse **unicamente** cuando
exista alguno de estos **desencadenantes**:

1. **Nuevo hardware** — un equipo cuya capacidad efectiva (verificada por pruebas, D44) habilite
   capacidades hoy diferidas.
2. **Un nuevo requisito funcional aprobado** — una capacidad nueva decidida por el CEO, con su
   argumentacion y su Definition of Done.
3. **Una decision estrategica que modifique el alcance** — un cambio de rumbo del proyecto que redefina
   que se construye.

En ausencia de cualquiera de los tres, la respuesta correcta es **mantener la linea base**, no producir
infraestructura que nadie pueda validar (D34, y la advertencia ya anticipada en
`milestones/m3-entry/ROADMAP-M3-REORDENADO.md` §4).

---

## Nota de cierre — Presupuesto de hardware cero (registro expreso)

Queda registrado de forma expresa, por instruccion del CEO:

> **El presupuesto actual para hardware es cero.** Mientras esa condicion exista, **AURA debe seguir
> siendo completamente funcional dentro de las capacidades del equipo disponible**, **sin generar
> bifurcaciones del codigo ni versiones diferentes del proyecto**. La **evolucion sera automatica cuando
> el hardware cambie, sin perder memoria, configuracion, historial ni compatibilidad**.

Este principio es coherente con —y refuerza— ADR-0020, D43 y D44, y con los tres principios permanentes
de la memoria (activo permanente independiente del motor; evolucion automatica; implementacion siempre
sustituible). Un presupuesto de cero **no degrada** el compromiso del proyecto: AURA funciona hoy en su
perfil actual y crecera sola el dia que el hardware lo permita, sobre el mismo codigo y conservando todo.

## Referencias

- Linea MA (cierre): `revisiones/2026-07-22-architecture-review-cierre-linea-MA.md`
- A1 (memoria por capacidades): `adr/0020-memoria-por-niveles-de-capacidad.md`
- A2 (metricas P-ARQ-7): `milestones/m3-entry/A2-metricas-basicas.md`
- Roadmap M3 reordenado (agotamiento anticipado, §4): `milestones/m3-entry/ROADMAP-M3-REORDENADO.md`
- Decisiones permanentes: `decisiones/2026-07-17-acta-decisiones-fundacionales.md` (D33, D34, D39, D42, D43, D44)
