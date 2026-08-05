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
| 002 | **Sobrevivir al reinicio y reanudar** | 3 procesos consecutivos reanudan el ciclo desde el historial, sin contexto externo — **los procesos los lanzó una sesión externa** | Claude Code |
| 003 | **Verificarse a sí misma** | ejecuta pruebas y Quality Gate como capacidad del ciclo | Claude Code |
| 004 | **Auditar sus propias garantías** | detectó 4 garantías rotas de 104 en su primera ejecución | Claude Code |
| 005 | **Generar trabajo desde evidencia** | un bloqueo produce su tarea de corrección; converge por construcción | Claude Code |
| 006 | **Reaccionar al veredicto, no solo a la ejecución** | un resultado negativo bloquea la tarea en vez de cerrarla | Claude Code |
| 007 | **Clasificar sus propios bloqueos** | 6 motivos reales clasificados sin cambiar el contrato | Claude Code |
| 008 | **Negarse a avanzar sobre una plataforma rota** | bloqueó un objetivo entero al detectar 2 garantías caídas | — *(emergente)* |

**008 no la enseñó nadie.** Emergió de combinar 004 y 006: al auditar detectó garantías rotas, el
veredicto negativo bloqueó la tarea, y el objetivo se detuvo solo. Es el primer comportamiento del
sistema que no fue diseñado explícitamente.

**Corrección (2026-08-04).** Esta tabla incluía una capacidad 009, «explicar su estado sin
intervención», acreditada al Centro de Gobierno. **Era falsa** y la publicó APUS-5: el módulo se
autodescribe como «la interfaz oficial entre el CEO y AURORA», pero su único importador en todo el
repositorio es su propia prueba (`tests/integration/test_centro_gobierno.py:11`). La función existe;
**la ruta que la entrega al CEO no**. Retirada de ✅ y reabierta como 🔴 018. Es el patrón
«declarado ≠ real» número 9 del proyecto, y el primero cuyo autor fue la asistencia externa.
La capacidad 002 se ha matizado por el mismo motivo: la persistencia es real y está medida, pero
los procesos que la demostraron los lanzó una sesión externa.

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
| 018 | **Hablar con el CEO sin sesión externa** | **parcial — no confirmada** | Ver nota abajo |

**014, 015 y 016 son la misma limitación vista desde tres ángulos.** Todos los análisis independientes
de dependencia externa han convergido en ella.

**018 — estado real (2026-08-04).** No la bloquea el hardware: nunca se cableó. Aprobado su
[Decision Package](milestones/m3-entry/DP-CANAL-PERMANENTE-CEO-AURORA.md) y entregadas dos de sus
tres piezas en `3e716d4`:

- ✅ **AURORA tiene proceso propio** (`--servir`) y **muestra su estado sin sesión externa**
  (`--gobierno`). Demostrado por ejecución: servicio vivo 75 s, panel consultado desde otra terminal,
  kill switch deteniéndolo fuera de banda. Quality Gate PASS · 21 mutantes, 0 supervivientes.
- ⛔ **Falta la Pieza 2**: desatendida, AURORA sigue autodenegándose toda acción de lista roja
  (`hitl_consola.py:35-38`). **Todavía no puede pedirte permiso: te lo deniega a sí misma.**

**Por eso 018 NO se declara aprendida**, pese a funcionar. Dos razones, ambas del criterio del CEO:
las **auditorías independientes cayeron por límite de cuota** y quedan pendientes, y la ruta
«qué decisiones esperan mi aprobación» **aún no existe**. Se declara aprendida cuando ambas cosas
se cierren — no antes. La evidencia de que funciona no sustituye a la verificación de que es
correcta.

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
