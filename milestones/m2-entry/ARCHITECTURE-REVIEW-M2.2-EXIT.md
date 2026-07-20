---
documento: "Architecture Review — M2.2 Exit"
version: 1.0.0
autor: "CTO"
fecha: "2026-07-20"
estado: "Pendiente de aprobación del CEO"
---

# Architecture Review — M2.2 Exit (Adaptador del computador principal)

**Quality Gate: PASS — 190 pruebas + 8 contratos** (al entrar en M2.2: 176 + 8).

## Condición 1 — El adaptador no puede eludir el perímetro

**Diseño:** una única puerta (`execute()`) con una única llamada a `validar()`. El adaptador **no
revalida por su cuenta**: una validación duplicada podría divergir de la del núcleo y crear un camino
con reglas distintas.

**Evidencia:** `test_ninguna_operacion_se_ejecuta_si_validar_falla`, parametrizada sobre las 6
operaciones con efecto. Se sustituye `validar` por una versión que **siempre lanza** y se comprueba
que el estado del directorio —listado y contenido— **no cambia en absoluto**. Si existiera cualquier
ruta alternativa dentro del adaptador, alguna operación dejaría rastro.

Complementada por `test_operacion_fuera_del_catalogo_no_llega_al_disco`: `ejecutar_comando` se rechaza
antes de tocar nada (RN-2).

## Condición 2 — Protección TOCTOU

**Diseño:** las operaciones destructivas nunca actúan sobre rutas de texto, sino sobre **descriptores
de directorio**.

| Mecanismo | Qué impide |
|---|---|
| `O_DIRECTORY \| O_NOFOLLOW` al abrir el padre | Que el propio directorio padre sea un enlace |
| Relectura de `/proc/self/fd/N` + reverificación de ámbito | Que el padre haya sido sustituido entre validar y actuar |
| `os.unlink/rename(base, dir_fd=fd)` | Que la ruta se reinterprete en el momento de actuar: el descriptor fija el inodo |
| `lstat` + rechazo de enlaces | Que el objetivo final se convierta en enlace |
| `O_NOFOLLOW` al escribir | Que el destino se convierta en enlace justo antes de abrirlo |

**Evidencia — la prueba se hizo determinista.** Se envuelve `validar` para que, **tras validar
correctamente**, sustituya el objetivo por un enlace a un archivo externo. Es exactamente la ventana
de la carrera, reproducida sin depender de temporización:

- `test_toctou_enlace_creado_justo_despues_de_validar` — el borrado se detiene y el archivo externo
  **sobrevive intacto**.
- `test_toctou_escritura_no_sigue_enlace` — la escritura se detiene y el externo conserva su contenido.

## Defensa en profundidad: dos capas, verificadas por separado

| Caso | Quién lo para |
|---|---|
| Enlace que apunta **fuera** del ámbito | `validar()` — comprobación de ámbito |
| Enlace que apunta **dentro** del ámbito | El adaptador — `_exigir_no_enlace` |

El segundo caso es el sutil: su destino es legítimo, así que la validación de ámbito lo aprueba. Sin la
comprobación del adaptador, borrar un enlace destruiría el archivo real al que apunta.

## Dos defectos encontrados por las pruebas

**D1 — `os.path.lexists(base)` miraba el directorio equivocado.** En `_escribir` y `_mover` se
comprobaba la existencia del destino con el nombre base, que se resuelve contra el **directorio de
trabajo del proceso**, no contra el descriptor. La protección frente a sobrescritura **no protegía
nada**. Corregido con `lstat(base, dir_fd=fd)`.

**D2 — `validar()` devolvía la ruta con los enlaces ya resueltos.** Si el usuario pedía borrar
`enlace.txt`, el adaptador recibía la ruta del **archivo de destino** y borraba ese otro archivo, del
que el usuario no había hablado.

Corregido distinguiendo dos rutas con papeles distintos:
- **literal** (normaliza `..` pero no resuelve enlaces) → es sobre la que se **opera**;
- **resuelta** → sirve solo para **comprobar el ámbito**.

Ambas deben estar en ámbito: la literal para que no apunte fuera, la resuelta para que ningún enlace
sirva de escape. Es un cambio de semántica, no cosmético: **AURA opera exactamente sobre el archivo
que el usuario nombró.**

Ninguno de los dos habría aparecido en una demostración: ambos exigían una prueba adversarial.

## Otras garantías

- **Idempotencia real.** Un evento reentregado no borra dos veces. La prueba recrea el archivo entre
  intentos y verifica que el reintento **no lo destruye**.
- **`mover` no sobrescribe.** Un destino existente detiene la operación (D32, máxima seguridad).
- **Auditoría selectiva.** Solo las operaciones destructivas se marcan `audit=True`: el registro
  forense no se diluye con ruido de lecturas.
- **D32 vigente:** `mover_archivo` y `renombrar_archivo` siguen en lista roja.

## Caso de control

`test_operaciones_legitimas_si_funcionan` ejercita leer, escribir, mover y borrar con rutas válidas.
Sin él, un adaptador que rechazara **todo** daría PASS en las pruebas de seguridad. Criterio de T1.

## Estado

| Condición del CEO | Estado |
|---|---|
| C1: sin rutas alternativas ni validación duplicada | ✅ PASS |
| C2: protección TOCTOU en destructivas | ✅ PASS |
| D32 vigente | ✅ |
| Sin regresión en M1/M2.0/M2.1 | ✅ Quality Gate PASS |

**M2.2 completada.** Siguiente: **M2.3 — motor de automatización con dry-run**, tras el cual procede la
reevaluación de D32.
