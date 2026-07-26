---
documento: "Linea base — Congelacion controlada: trabajo verificable sin hardware agotado"
fecha: 2026-07-26
autor: "CTO"
encargo: "CEO — ratificacion de la opcion A: documentar formalmente que el trabajo verificable sin hardware queda agotado y declarar esta como la nueva linea base del proyecto"
base: "main @ b19e3fe (origin/main sincronizada) — Quality Gate PASS (310 passed / 3 skipped)"
estado: "Linea base vigente y REFERENCIA OFICIAL de reanudacion. El proyecto queda en congelacion controlada hasta un desencadenante autorizado (ver §5); desde este documento se retomara el desarrollo cuando exista nuevo hardware."
---

# Linea base — Congelacion controlada de AURA

Tras cerrar la linea MA (madurez de arquitectura), la iniciativa A1 (analisis de memoria → ADR-0020) y
la iniciativa A2 (realizacion del contrato de metricas P-ARQ-7), la revision del estado real del
repositorio concluye que **el trabajo de arquitectura verificable con el hardware actual queda
agotado**. Este documento formaliza esa conclusion y la declara **nueva linea base** del proyecto.

**Encuadre — esto es un hito de madurez, no una pausa por problemas tecnicos.** Toda la arquitectura
verificable con el hardware actual quedo **completada y validada** (Quality Gate PASS, 310 passed / 3
skipped). El proyecto no se detiene por un defecto, una limitacion de diseno ni una dificultad de
ingenieria: se detiene porque **lo que resta depende de capacidades fisicas** —hardware o dispositivos
reales— y de los datos que solo el uso real genera, **no de trabajo pendiente de arquitectura**. Alcanzar
este punto es un logro, no un tropiezo.

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

Lo que resta **no son funcionalidades "pendientes"**: son **capacidades latentes ya previstas por la
arquitectura** (D45, ADR-0021), cuya activacion depende unicamente de los recursos disponibles. No fueron
omitidas ni pasadas por alto; su realizacion se difiere **deliberadamente** por depender de recursos
fisicos o de datos reales, conforme a las decisiones permanentes del proyecto:

- **D34** — prohibe fabricar un entorno (mocks, datos sinteticos) para aprobar un milestone: la calidad
  de una capacidad probabilistica *es* su acierto sobre datos reales.
- **D39** — desarrollo continuo con restricciones de hardware: se madura lo que se puede con el equipo
  actual y se difiere explicitamente lo que exige el equipo objetivo.
- **D44** — la capacidad efectiva se determina por **pruebas reales**, no por specs: una capacidad
  dependiente del hardware no se declara cumplida hasta verificarse en el entorno que la ejecuta.

Cada una tiene su **lugar y su contrato en el Registro de Capacidades** (ADR-0021). Su grado de latencia
distingue —sin ambiguedad— lo que ya podria encenderse solo de lo que aun debe construirse+validarse:

| Capacidad latente | Grado (ADR-0021) | Depende de | Decision |
|---|---|---|---|
| M3.2b · Inferencia de preferencias | prevista | Datos de uso real | D34, D44 |
| M3.1 · Hogar real (Home Assistant) | prevista | Instalacion fisica real | D34 |
| M3.3 · Anticipacion (CM4) | prevista | M3.2b + datos + calidad de modelo | D34, D44 |
| M3.4 · Avatar | prevista | Plataforma de despliegue | D33 |
| HC-1 (latencia e2e) · CM1 (ventana de semanas) | (criterio de verificacion) | Uso real sostenido (hardware) | D39, D44 |

Diferir con criterio no es acumular deuda: **es gobierno honesto del alcance**. Una capacidad prevista,
con contrato y lugar reservados en el registro, es lo contrario de una omision silenciosa.

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
**habilitara automaticamente** capacidades conforme a **D45 / ADR-0021** (Registro de Capacidades),
**ADR-0020**, **D43** y **D44**.

- **D45 / ADR-0021** — **Registro de Capacidades + Capability Manager agnostico**: cada capacidad es un
  modulo autonomo, autocontenido y auditable que declara **diez campos** (contrato, prerequisitos minimos,
  mecanismo de deteccion, comportamiento degradado, criterio de promocion y de degradacion automaticas,
  grado de latencia, dependencias, garantias de seguridad y nivel de autonomia); el Manager recorre el
  registro y **promueve o degrada** segun la capacidad efectiva —**sin conocer ninguna capacidad
  concreta** y sin perdida de informacion—. AURA esta **siempre completa como arquitectura**; solo
  evoluciona el **conjunto de capacidades que ejerce**.
- **ADR-0020** — la memoria (una capacidad mas del registro) opera en **perfiles de capacidad** detras de
  un **contrato funcional unico**; el perfil se selecciona de forma automatica, reversible y transparente.
- **D43** — evolucion por capacidades del hardware: un solo proyecto, un solo codigo, una sola
  arquitectura que se adapta al hardware detectado, **sin bifurcar el codigo**.
- **D44** — capacidad efectiva verificada por pruebas: el hardware declara lo potencial, las pruebas
  determinan lo efectivo; el perfil se recalcula ante cambios de hardware, sistema operativo, modelos o
  una version mas eficiente de AURA.

La consecuencia practica: mas hardware = mas capacidad, autonomia y rendimiento, **sin migracion manual
del usuario, sin ediciones (Lite/Pro/Enterprise), sin un "AURA 2" y sin una nueva version del proyecto**.
Reanudar el desarrollo sera **registrar/habilitar capacidades** en su lugar ya previsto, **no** construir
una arquitectura nueva.

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

## Cierre ejecutivo

**Esta linea base es un hito de madurez del proyecto, no una pausa por problemas tecnicos.** Toda la
arquitectura que podia construirse y verificarse con el hardware actual esta **completada y validada**:
punto de entrada unico y composicion declarativa (D40), memoria escalable y por niveles de capacidad
(MA.2/ADR-0020), audit log forense con rotacion (MA.3), marco de conectores externos con transparencia
(MA.4/ADR-0019), convergencia validacion↔produccion (MA.5/D41), backups de memoria con restauracion
probada (7.4), soberania del modelo del usuario (M3.2a/ADR-0017) y metricas basicas cableadas
(A2/P-ARQ-7). Nada de esto es provisional: esta cubierto por pruebas y, donde aplica, validado por mutacion.

**Lo que resta no es trabajo de arquitectura pendiente, sino capacidades que dependen de recursos
fisicos** —hardware o dispositivos reales— y de datos de uso real. Diferirlas es la decision correcta
(D34/D39/D44), no una omision.

**Este documento es la referencia oficial desde la que se retomara el desarrollo** cuando exista nuevo
hardware. La reanudacion preservara integramente los principios de **D45 / ADR-0021** (Registro de
Capacidades), **ADR-0020**, **D43** y **D44**: cada capacidad futura (IA local, inferencia, voz, vision,
Home Assistant, automatizaciones, agentes, conectores externos, avatar) se **registrara** con sus **diez
campos** (contrato, prerequisitos, deteccion, comportamiento degradado, criterios de promocion/degradacion,
grado de latencia, dependencias, garantias de seguridad y nivel de autonomia), y el **Capability Manager**
la habilitara —y la degradara sin perdida— automaticamente cuando el entorno cambie. AURA **evolucionara por
capacidades**, habilitando lo que el nuevo equipo permita **sin bifurcar el proyecto** y **sin perder
memoria, configuracion, historial ni compatibilidad**. No habra un "AURA 2": habra el mismo AURA, en un
perfil de capacidad superior.

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

- **Registro de Capacidades (Capability Registry/Manager):** `adr/0021-registro-de-capacidades-y-activacion-por-perfil.md`
- Linea MA (cierre): `revisiones/2026-07-22-architecture-review-cierre-linea-MA.md`
- A1 (memoria por capacidades): `adr/0020-memoria-por-niveles-de-capacidad.md`
- A2 (metricas P-ARQ-7): `milestones/m3-entry/A2-metricas-basicas.md`
- Roadmap M3 reordenado (agotamiento anticipado, §4): `milestones/m3-entry/ROADMAP-M3-REORDENADO.md`
- Decisiones permanentes: `decisiones/2026-07-17-acta-decisiones-fundacionales.md` (D33, D34, D39, D42, D43, D44, **D45**)
