---
documento: "Estándar de trabajo de AURA — Producto Demostrable"
fecha: 2026-07-28
autor: "CTO / Director"
estado: "VIGENTE. Consolidado y aprobado por el CEO (2026-07-28). Estándar de calidad para el resto del proyecto AURA."
relacionado: "D47 (método jerárquico de evidencia, decisiones/2026-07-28-D47-metodo-jerarquico-de-evidencia.md); ADR-0016 (neutralidad); ADR-0022 (artefactos de IA)"
---

# Estándar de trabajo de AURA — Producto Demostrable

Estándar de calidad **vigente para todos los incrementos** del proyecto AURA, consolidado por el CEO tras
cerrar los tres primeros incrementos con valor visible (N2 Memoria Semántica, Centro de Notificaciones,
Modelo de Usuario). Este documento es el **artefacto verificable** del estándar: sustituye a cualquier
referencia informal a "memoria".

> ## Principio rector (CEO, 2026-07-28)
>
> **La IA es una herramienta de construcción, no una fuente de verdad del proyecto. La única fuente de
> verdad es el repositorio y sus artefactos verificables.**
>
> Rige sobre todo lo demás: cualquier estado, decisión o regla que no esté en un artefacto verificable del
> repositorio **no existe a efectos del proyecto**. Un auditor debe poder reconstruir el estado completo
> clonando el repositorio, sin depender del agente que hizo el trabajo.

## Los seis principios

1. **Product Demo Preview antes de leer código.** Cada incremento empieza escribiendo la conversación
   nueva que el usuario podrá tener con AURA cuando termine. Si esa conversación no aporta una capacidad
   nueva perceptible, el incremento está demasiado centrado en infraestructura y se replantea antes de
   escribir una sola línea.

2. **Pensar siempre en el ecosistema de capacidades.** Ninguna capacidad se construye aislada. Cada
   incremento debe potenciar **al menos una capacidad existente**, y su Decision Package incluye la
   **matriz obligatoria** "Capacidad nueva → Potencia a". Si una capacidad solo aporta valor por sí sola,
   probablemente aún no está suficientemente integrada.

3. **Arquitectura mínima necesaria.** Se implementa la arquitectura mínima capaz de cumplir el
   comportamiento del producto. Antes de construir infraestructura se investiga, con evidencia, qué ya
   existe y puede reutilizarse; solo se construye lo imprescindible. Nueva infraestructura únicamente
   cuando la evidencia demuestra que es necesaria (concuerda con D47 y con la regla de beneficio medible
   de D24).

4. **Cierre basado en comportamiento observable para el usuario.** Un incremento se considera terminado
   cuando **el comportamiento demostrado** funciona de extremo a extremo, no cuando las pruebas están en
   verde. El cierre se entrega en **cinco bloques**: (1) qué cambió técnicamente; (2) qué gana AURA como
   producto; (3) demostración conversacional real (ejecutada, no descrita); (4) deuda pendiente; (5) qué
   capacidades existentes mejoran gracias al incremento.

5. **Toda decisión permanente debe quedar respaldada por un artefacto verificable.** No se distingue entre
   documentación, estado del repositorio y memoria:
   - un **cambio en el repositorio** queda demostrado por un **commit**;
   - una **decisión** queda demostrada por un **ADR o un documento de gobernanza** (como este);
   - una **regla permanente** queda demostrada cuando existe un **mecanismo real que la preserve**;
   - una **deuda** queda demostrada por una entrada en el **backlog** (p. ej. `milestones/*/DEUDA-*.md`).

   Al registrar algo permanente se indica **exactamente dónde** quedó (ADR, documento, backlog, commit),
   nunca "en memoria" como si eso fuese suficiente.

6. **Continuidad: ningún vacío queda oculto.** (CEO, 2026-08-02) Existe un artefacto permanente,
   [`CHECKLIST-CONTINUIDAD.md`](../CHECKLIST-CONTINUIDAD.md) en la raíz del repositorio, cuyo objetivo es
   que **cualquiera que retome el desarrollo —persona o agente, con o sin el contexto de las
   conversaciones anteriores— pueda continuar exactamente donde se quedó.**

   **Actualizarlo forma parte del cierre de cada incremento, igual que los cinco bloques. Un incremento
   no está cerrado si el checklist quedó desactualizado.** En cada cierre se revisan su estado (hash,
   Quality Gate, capacidades), sus decisiones pendientes, sus autorizaciones y —sobre todo— su sección
   **"lo que parece hecho y no lo está"**: se añade toda trampa nueva descubierta y se **borra** la que
   se haya corregido de verdad, citando el commit que lo demuestra.

   **Estatus elevado (CEO, 2026-08-02):** el checklist es la **fuente de verdad para retomar el trabajo y
   para registrar los vacíos** detectados durante un incremento. Un vacío, una deuda o un trabajo diferido
   se anotan **en el momento en que aparecen**, no al cerrar. No sustituye a la verificación por ejecución:
   el repositorio sigue siendo la fuente de verdad sobre los hechos.

   Por qué es un principio y no una tarea: el proyecto ya ha sufrido **cuatro veces** el mismo patrón
   —algo declarado en un documento y ausente en la realidad— (ALERTA-004, ALERTA-005, la captura de
   señales y los hallazgos de la revisión estratégica del 2026-08-02). Un checklist que solo dijera lo
   que está hecho repetiría ese patrón; el valor está en que diga **qué no es lo que aparenta**.

## Precisiones del CEO incorporadas (2026-07-28)

- **El comportamiento demostrado es el criterio de aceptación.** Ejemplo del cierre del Modelo de Usuario:
  terminado = el usuario puede preguntar qué sabe AURA de él, entender por qué, corregirlo, olvidarlo y
  comprobar **tras un reinicio** que realmente fue olvidado.
- **La interfaz debe ser fiel al estado interno.** AURA no comunica capacidades que todavía no posee. No se
  inventan grados de certeza ("creo", "inferí") sin un mecanismo real que los respalde. Cuando exista una
  capacidad de inferencia real (M3.2b), entonces aparecerá en la conversación, no antes.

## Tres planos y foco de los informes (CEO, 2026-07-28)

Se distinguen siempre tres planos, y **los informes finales se centran ÚNICAMENTE en el primero**:

1. **Proyecto (auditable):** documentos, ADR, backlog, código, pruebas, commits y Quality Gate. Es la
   única evidencia del proyecto.
2. **Proceso de ejecución:** cómo se organiza el trabajo para llegar al resultado. No es evidencia del
   proyecto; no aparece en los informes.
3. **Estado interno de la herramienta:** memoria, índices o cualquier mecanismo propio del agente. No es
   evidencia del proyecto; no aparece en los informes.

Los mecanismos internos pueden usarse para trabajar mejor, pero **no forman parte de la evidencia**. Un
auditor debe poder reconstruir la historia completa **solo con el plano 1**, sin depender del agente que
hizo el trabajo.

**Los informes, cierres y decisiones hablan exclusivamente del proyecto (plano 1).** El proceso (plano 2)
solo se menciona si el CEO lo pide expresamente. La herramienta (plano 3) **nunca** se presenta como
evidencia del proyecto.

**Frases prohibidas en un informe** (son estado interno de la herramienta, no evidencia): *"lo registré en
mi memoria"*, *"mi memoria interna recuerda…"*, *"quedó almacenado en memoria"*. En su lugar se indica
siempre el **artefacto verificable**: documento, ADR, backlog, commit o archivo concreto.

**Formato de cierre para una decisión permanente:** basta indicar (a) el **artefacto** donde quedó
registrada, (b) el **commit** que la introdujo y (c) si aplica, el **ADR o backlog** relacionado.

## Trazabilidad de los tres incrementos cerrados

| # | Capacidad | Comportamiento nuevo | Artefactos verificables |
|---|---|---|---|
| 1 | N2 Memoria Semántica | Entiende recuerdos relacionados, no solo palabras iguales | commits `e4a502e`, `1c80185b`, `b0e9e37`; `DEUDA-N2-MEMORIA-SEMANTICA.md` |
| 2 | Centro de Notificaciones | Cuenta qué ocurrió mientras el usuario no estaba | commit `eea37cb` |
| 3 | Modelo de Usuario | El usuario gobierna lo que AURA sabe de él (olvido persistente) | commit `cdd2c6e`; deuda D-N2-4 en `DEUDA-N2-MEMORIA-SEMANTICA.md` (`13e67a7`) |
