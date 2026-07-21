---
documento: "Executive Summary FINAL — Cierre de M2"
milestone: "M2 — Manos Digitales"
fecha: 2026-07-21
autor: "CTO"
destinatario: "CEO — AURA Labs"
estado: "Cierre técnico aprobado por el CEO el 2026-07-21; pendiente el cierre oficial"
version: "final"
---

# Executive Summary — M2 (Manos Digitales)

> **Nota de versión.** Documento final de cierre. Incorpora el gate del CEO del 2026-07-21, que fijó
> como oficiales: el orden canónico del flujo (`dry-run → Permisos/HITL → adaptador → ejecución →
> auditoría`), el Product Readiness del **41%**, la demo como **8/9** capacidades y **HC-1 en estado
> Pendiente** por no existir medición de latencia válida.

## En una frase

**AURA ya actúa sobre el computador cuando se lo piden hablando, bajo confirmación informada y con
todos los frenos operativos** — y el cierre dejó al descubierto que la seguridad del sistema no
depende de que el modelo acierte, porque el modelo se equivocó y no pasó nada.

## Qué se entregó

Nueve operaciones reales sobre archivos —buscar, listar, leer, abrir, consultar estado, escribir,
mover, renombrar, borrar— alcanzables por conversación, más un motor de automatización por reglas y
un centro único de notificaciones.

Cada acción que altera el estado recorre el mismo camino, venga de donde venga: **previsualización →
confirmación humana → ejecución → auditoría**. El kill switch corta las dos vías.

## Lo que hay que saber

### 1. M2 estuvo a punto de cerrarse vacío

Al preparar la demo final descubrí que las tres piezas construidas en M2.2, M2.3 y M2.4 **estaban
desconectadas**: existían, tenían 218 pruebas en verde y ninguna petición del usuario podía
alcanzarlas. Peor, cuando el sistema autorizaba una acción que nadie podía ejecutar, **respondía
afirmando haberla hecho**.

Fue el mismo fallo que ALERTA-004 con un día de diferencia: declarado en el documento, ausente del
código, invisible porque cada prueba verificaba su pieza en aislamiento. Se abrió una fase no
planificada (M2.5) para corregirlo, y **una prueba permanente que hace fallar el Quality Gate si una
capacidad construida no es alcanzable**. Esa prueba está validada por mutación: reproduciendo el
fallo original, falla.

### 2. El modelo se equivocó y la arquitectura aguantó

En la demo real, ante *"recuérdame comprar pan"*, el modelo local eligió **abrir un archivo**. Una
decisión absurda.

No causó ningún daño: la acción era de solo lectura y el catálogo cerrado impedía cualquier otra
cosa. Es la mejor evidencia que ha dado este proyecto de que **la seguridad no descansa en el
criterio del modelo**, sino en controles del núcleo. Un modelo que falla produce una acción inútil,
no una destructiva.

Dicho esto, la contrapartida es real: **la calidad de decisión del modelo pequeño es mediocre** —una
elección claramente equivocada y otra aproximada de tres peticiones—. Está contenida, no resuelta.

### 3. La demo encontró un fallo que las pruebas no

La primera ejecución **derribó el turno completo**: una automatización que se disparaba dos veces
sobre el mismo archivo propagaba un error del sistema de archivos a través de todo el motor.
Corregido, con pruebas de regresión. Es la justificación de por qué exigimos una demo sobre stack
real y no solo pruebas verdes.

### 4. No hay medición de latencia utilizable

Con el modelo de 3 B la demo agotó 600 segundos por turno y abortó, con el equipo haciendo swap. La
corrida que completó lo hizo con carga 6,9 en dos núcleos. **Ambas condiciones invalidan la
medición**, y prefiero no darte un número contaminado que registrar como si fuera un dato.

**HC-1 sigue pendiente de validación en entorno objetivo.**

## Product Readiness: 32% → **41%**

| | M1 | M2 |
|---|---|---|
| Hace cosas útiles (acciones reales) | 1% | **12%** |
| Entiende y responde con sentido | 12% | **10%** |
| Responde a tiempo | 0% | 0% |
| Resto de dimensiones | sin cambios | sin cambios |
| **Total** | **32%** | **41%** |

El objetivo era ~45%. Se quedó en 41% por dos motivos: el arranque del sistema sigue exigiendo
lanzar procesos a mano (no se tocó en M2), y **bajé la puntuación de comprensión de 12% a 10%**
porque por primera vez hay evidencia de cómo elige acciones el modelo, y no es buena. El sistema no
empeoró; mejoró la información.

**A más de dos minutos por turno, AURA sigue sin ser usable durante una jornada**, tenga las manos
que tenga.

## Estado de calidad

| Indicador | Valor |
|---|---|
| Quality Gate | **PASS** |
| Pruebas | **234 pasan**, 3 omitidas, + 8 contratos |
| Demo con dobles | 9/9 capacidades |
| Demo con stack real | **8/9** — la novena verificada por prueba determinista |
| Errores no recuperados | **0** (tras corregir el hallado por la demo) |
| Alertas de arquitectura abiertas | **0** |

## Cierre documental ordenado en el gate

| Acción ordenada por el CEO | Resultado |
|---|---|
| Consistencia del orden del flujo en toda la documentación | **5.3 §3.1** pasa a ser la fuente única del orden canónico; actualizados ADR-0003, 3.2 (texto y diagrama de secuencia), 6.4 §2 y el Plan de Calidad |
| Registro formal del hallazgo sobre selección de acciones | `milestones/m2-exit/HALLAZGO-M2-SELECCION-DE-ACCIONES-DEL-MODELO.md` — clasificado explícitamente como limitación de capacidad, **no** fallo de seguridad |
| Executive Summary final | Este documento |
| Commits y estrategia de integración | §"Integración de la rama", más abajo |

**Los documentos históricos no se han reescrito.** Las actas y los Architecture Review ya firmados
(M1-Exit, M2.0 a M2.4) conservan su redacción original: registran lo que se sabía al firmarlos y
alterarlos falsearía el historial de decisiones. La consistencia se impone en los documentos
normativos vigentes, que son los que gobiernan la implementación.

## Integración de la rama `worktree-m2-exit`

Cinco commits, en orden:

| # | Commit | Contenido |
|---|---|---|
| 1 | `32217a3` | ALERTA-005 — hallazgo, verificación empírica y análisis de las tres alternativas |
| 2 | `7afe8a7` | M2.5 — integración del orquestador; registro de adaptadores; ejecutor único; prueba de alcanzabilidad |
| 3 | `82c8cfd` | Demo de capacidad M2 + corrección del error no recuperado que la demo encontró |
| 4 | `ad6adf8` | Architecture Review M2-Exit, Executive Summary, ALERTA-005 resuelta, evidencia archivada |
| 5 | *(este)* | Cierre documental: consistencia del flujo, hallazgo del modelo, resumen final |

**Estrategia recomendada: `merge --no-ff` a `main`.**

Un *squash* comprimiría los cinco en uno y perdería lo más instructivo del milestone: que la alerta
se emitió **antes** de la corrección, y que la corrección precedió a la demo que encontró un defecto
adicional. Esa secuencia es la trazabilidad que exige D25 y el mejor argumento disponible sobre por
qué el proceso funciona. Un *rebase* tampoco aporta: no hay commits paralelos en `main` con los que
entrelazar.

### Riesgo residual de la integración

| Riesgo | Valoración |
|---|---|
| **Conflictos con `main`** | **Ninguno esperado.** La rama parte de `744bab2`, que es la punta de `main`; nadie más ha commiteado |
| **Regresión funcional** | **Baja.** Quality Gate PASS en el estado final; las 218 pruebas previas siguen pasando |
| **Cambio de firma del `Orchestrator`** | **Real pero contenido.** Su sexto parámetro admite ahora un registro *o* un adaptador suelto, y acepta `motor` opcional. Las llamadas antiguas siguen funcionando; verificado por las pruebas heredadas de M1 |
| **Cambio de comportamiento observable** | **Deliberado.** Una acción autorizada sin adaptador capaz ya no responde con éxito, sino con error explícito. Es el punto 4 que aprobaste; cualquier script que dependiera de la respuesta anterior dependía de un fallo |
| **Prompt del sistema modificado** | **Bajo.** Pasa a derivarse del catálogo, ampliándose de ~200 a ~393 tokens. En hardware objetivo es irrelevante; en el actual añade coste de *prefill* a una latencia ya inasumible |
| **Sin remoto configurado** | El repositorio no tiene *remote*, de modo que no hay copia fuera de esta máquina. **Es el único riesgo que recomiendo atender**: cinco commits de trabajo dependen de un solo disco |

Comandos sugeridos:

```bash
git checkout main
git merge --no-ff worktree-m2-exit -m "M2 — Manos Digitales: cierre del milestone"
cd walking-skeleton && bash quality-gate.sh   # verificación tras el merge
```

## Decisión que solicito

**Cierre oficial de M2.** Lo presento como 8/9 en la demo, no como 9/9.

## Recomendación sobre M3

Sugiero que **M3 no sea otra capa de capacidades**. El cierre deja dos hechos incómodos juntos: el
sistema no responde a tiempo y el modelo local elige regular. Más funciones encima no mejoran
ninguno de los dos, y ambos dependen de la misma decisión pendiente: **el hardware objetivo**, que
determina qué modelo puede correr y con ello la calidad de sus decisiones.

La prioridad es tuya; mi obligación es señalar que la palanca de producto hoy no está en el código.
