# Plan de Formación de AURORA

> El plan de estudios de AURORA. **No es un backlog técnico**: documenta su evolución intelectual —qué
> capacidades ha aprendido, cuáles están en observación y cuáles siguen bloqueadas— de forma trazable
> y respaldada por evidencia del uso real.
>
> **Regla de admisión:** ninguna capacidad entra aquí por parecer buena idea. Entra cuando el uso real
> produce evidencia repetida, y esa evidencia se cita.

**Fuente oficial de evidencia:** el Centro de Gobierno y el historial persistido (`~/.aura/`).

---

## Los cuatro ritmos del proyecto

| Actor | Ritmo | Responsabilidad |
|---|---|---|
| **AURORA** | **continuo** | Ejecuta su ciclo, acumula evidencia. **Su estado persiste**: es la única que trabaja todos los días |
| **Claude Code** | episódico | Consejo de Formación: analiza la evidencia acumulada cuando se le convoca |
| **APUS-5** | episódico | Guía el aprendizaje durante las sesiones. Enseña, no sustituye |
| **CEO** | — | Fija la visión, aporta necesidades reales, decide qué se incorpora |

**Por qué el trabajo continuo pertenece a AURORA y no a APUS-5:** el estado de AURORA sobrevive al
reinicio y su ciclo se reanuda solo; ninguna sesión de asistencia externa persiste. Esa asimetría no es
una limitación a corregir: es la razón por la que la operación es suya.

---

## ✅ Aprendidas

Capacidades que AURORA ejerce hoy sin intervención externa, demostradas por ejecución.

| # | Capacidad | Evidencia | Enseñada por |
|---|---|---|---|
| 001 | **Coordinar su propio backlog** | 14/16 secciones del Centro de Gobierno resueltas sola (18 vueltas) | Claude Code |
| 002 | **Sobrevivir al reinicio y reanudar** | 3 procesos consecutivos continúan el ciclo sin contexto externo | Claude Code |
| 003 | **Verificarse a sí misma** | ejecuta pruebas y Quality Gate como capacidad del ciclo | Claude Code |
| 004 | **Auditar sus propias garantías** | detectó 4 garantías rotas de 104 en su primera ejecución | Claude Code |
| 005 | **Generar trabajo desde evidencia** | un bloqueo produce su tarea de corrección; converge por construcción | Claude Code |
| 006 | **Reaccionar al veredicto, no solo a la ejecución** | un resultado negativo bloquea la tarea en vez de cerrarla | Claude Code |
| 007 | **Clasificar sus propios bloqueos** | 6 motivos reales clasificados sin cambiar el contrato | Claude Code |
| 008 | **Negarse a avanzar sobre una plataforma rota** | bloqueó un objetivo entero al detectar 2 garantías caídas | — *(emergente)* |
| 009 | **Explicar su estado sin intervención** | Centro de Gobierno con trazabilidad de origen | Claude Code |

**008 no la enseñó nadie.** Emergió de combinar 004 y 006: al auditar detectó garantías rotas, el
veredicto negativo bloqueó la tarea, y el objetivo se detuvo solo. Es el primer comportamiento del
sistema que no fue diseñado explícitamente.

---

## 🟡 En observación

Patrones detectados que **aún no tienen evidencia suficiente** para justificar una enseñanza.

| # | Candidata | Veces observada | Qué falta |
|---|---|---|---|
| 010 | **Asignar responsable a una necesidad** | **2** | Es determinista: AURORA conoce sus responsables. Esperar repetición |
| 011 | **Fijar prioridad de una tarea** | **2** | Derivable de la categoría del bloqueo |
| 012 | **Redactar la evidencia inicial** | **2** | Copiar la necesidad literal; trivial |
| 013 | **Revisar deuda documental** | **1** | Bloqueo `capacidad inexistente`. Una sola observación |

**010, 011 y 012 son los tres pasos deterministas del Traductor Operativo**, repetidos en las dos
necesidades reales traducidas hasta hoy. Si vuelven a aparecer, serán las primeras candidatas con datos
detrás — y su incorporación reduciría directamente la superficie del Traductor.

---

## 🔴 Bloqueadas

No se desarrollan. La evidencia demuestra que no dependen de más arquitectura.

| # | Capacidad | Motivo | Evidencia |
|---|---|---|---|
| 014 | **Formular cambios de código** | hardware | Ollama: 25,8 s para «Hola»; 98 % del trabajo de una sesión fue generativo |
| 015 | **Interpretar una necesidad en lenguaje** | formulación | Único paso del Traductor no determinista, en las 2 necesidades traducidas |
| 016 | **Proponer backlog y cambios sugeridos** | formulación | Las 2 únicas secciones del Centro de Gobierno que AURORA no pudo construir |
| 017 | **Usar su historial para decidir** | requiere juicio | `NO_MEDIBLE` en el IMA: registra `intentos` y nadie los lee para cambiar una decisión |

**014, 015 y 016 son la misma limitación vista desde tres ángulos.** Todos los análisis independientes
de dependencia externa han convergido en ella.

---

## Registro del Traductor Operativo

Andamiaje temporal. **El objetivo es que su superficie disminuya.**

| # | Necesidad real | Pasos | Deterministas | Formulación | Bloqueos |
|---|---|---|---|---|---|
| 1 | revisar la deuda técnica del recuperador | 5 | 3 | 2 | 1 nuevo |
| 2 | verificar el modelo de usuario y las señales | 5 | 3 | 2 | 0 |

Los tres pasos deterministas son los mismos en ambas. Los dos de formulación, también.

---

## Cómo se actualiza

En cada sesión del Consejo de Formación, y **solo con evidencia del Centro de Gobierno**:

1. ¿Qué patrones nuevos aparecieron desde la última revisión?
2. ¿Qué capacidades faltantes se repitieron lo suficiente para justificar una enseñanza?
3. ¿Qué puede aprenderse con reglas deterministas, sin modelo más potente?
4. ¿Qué sigue bloqueado por formulación?

El resultado es un **plan**, nunca una implementación. Ninguna capacidad se desarrolla
automáticamente.
