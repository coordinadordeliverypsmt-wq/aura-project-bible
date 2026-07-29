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

## Los cinco principios

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

**Formato de cierre para una decisión permanente:** basta indicar (a) el **artefacto** donde quedó
registrada, (b) el **commit** que la introdujo y (c) si aplica, el **ADR o backlog** relacionado.

## Trazabilidad de los tres incrementos cerrados

| # | Capacidad | Comportamiento nuevo | Artefactos verificables |
|---|---|---|---|
| 1 | N2 Memoria Semántica | Entiende recuerdos relacionados, no solo palabras iguales | commits `e4a502e`, `1c80185b`, `b0e9e37`; `DEUDA-N2-MEMORIA-SEMANTICA.md` |
| 2 | Centro de Notificaciones | Cuenta qué ocurrió mientras el usuario no estaba | commit `eea37cb` |
| 3 | Modelo de Usuario | El usuario gobierna lo que AURA sabe de él (olvido persistente) | commit `cdd2c6e`; deuda D-N2-4 en `DEUDA-N2-MEMORIA-SEMANTICA.md` (`13e67a7`) |
