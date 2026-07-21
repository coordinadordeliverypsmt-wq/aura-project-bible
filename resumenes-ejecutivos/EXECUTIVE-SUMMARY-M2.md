---
documento: "Executive Summary — Cierre de M2"
milestone: "M2 — Manos Digitales"
fecha: 2026-07-21
autor: "CTO"
destinatario: "CEO — AURA Labs"
---

# Executive Summary — M2 (Manos Digitales)

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

## Decisión que solicito

**Cierre formal de M2.** Lo presento como 8/9 en la demo, no como 9/9.

## Recomendación sobre M3

Sugiero que **M3 no sea otra capa de capacidades**. El cierre deja dos hechos incómodos juntos: el
sistema no responde a tiempo y el modelo local elige regular. Más funciones encima no mejoran
ninguno de los dos, y ambos dependen de la misma decisión pendiente: **el hardware objetivo**, que
determina qué modelo puede correr y con ello la calidad de sus decisiones.

La prioridad es tuya; mi obligación es señalar que la palanca de producto hoy no está en el código.
