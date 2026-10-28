# Cierre · Motor de autonomía — AURA descubre su propio trabajo

**Fecha:** 2026-08-31 · **Commits:** 0 · **Push:** 0 · **HEAD:** `790fafc`

---

## 1 · Qué cambió técnicamente

El ciclo autónomo existía y sabía encadenar tareas. Lo que no sabía era **de dónde salen**:

```python
ciclo_autonomo(directorio, ficheros, ...)   # <- la lista venía de fuera
```

Ese parámetro **era** el traspaso manual. Cuatro módulos nuevos cierran el tramo de arriba:

- **`descubrimiento.py`** — cinco fuentes mecánicas (código muerto por `ast`, invocables sin
  clasificar, eventos sin puerta, decisiones pendientes, bloqueos registrados). Cada oportunidad trae
  **ocho piezas** y una `fuente` que apunta a un `fichero:línea` o a un mecanismo nombrado.
- **`planificador.py`** — convierte **solo** las autorizadas en tareas. Id **derivado** de la
  oportunidad, así que el duplicado se reconoce solo.
- **`motor_autonomia.py`** — encadena y para. **No ejecuta**: eso sigue en
  `review.ejecutar_bajo_review`, con sus cuatro puertas. Una prueba lo comprueba leyendo el fuente
  por `ast` — mirando **código**, no prosa, porque la primera versión se encontró a sí misma en un
  docstring.
- **`aura.py`** — el punto de entrada, **acotado y que termina**.

## 2 · Las dos reglas que hacen esto seguro

**Descubrir trabajo no es concederse autoridad.** El descubridor mira todas las fuentes; quién
autoriza sigue siendo la política y el acta, con el mecanismo que ya existía. De ahí cuatro clases y
no dos: separar *«lo hay pero no puedo»* de *«no lo hay»* es lo que hace que una cola vacía sea una
afirmación con evidencia y no una rendición.

**Un descubridor que puede inventar trabajo es peor que no tener ninguno**: produce actividad que
parece progreso. Por eso la oportunidad sin procedencia se rechaza **en el constructor** — lo que no
se puede construir no hay que acordarse de filtrarlo.

## 3 · Por qué no es un demonio

El `§23` del DP aprobado: *«**Ningún daemon ni watcher permanente.** El Orchestrator se invoca y
termina»*. Un proceso que no muere es uno al que hay que ir a matar, y un sistema al que hay que ir a
matar no está gobernado. `aura.py` hace una vuelta acotada y sale; **quién lo despierta es asunto de
fuera**, y esa separación es justamente lo que hace que la autonomía resida en AURA.

## 4 · Evidencia

| Qué | Resultado |
|---|---|
| Encadenado real, efecto observable | 3 oportunidades **descubiertas**, 3 ejecutadas, funciones muertas borradas y vivas conservadas, **0 actos humanos** |
| Sobre el plano real | 7 descubiertas · 0 ejecutables · 6 bloqueadas · 1 elevada → **`COLA_AGOTADA`**, salida 0 |
| El cero, medido | 11 ficheros y 33 privadas examinadas, 0 muertas |
| Batería | **558 passed** (antes 527) |
| Mutación | **238 mutantes en 12 arneses, 0 supervivientes, 0 `NO_APLICADO`** |
| Quality Gate | **FAIL 5/1139/3 = baseline**, mismos 5 ids |

## 5 · Lo que encontró ejecutarlo, y no leerlo

El descubridor leía `decision_pendiente` del log y **no** las `decisiones_pendientes` de
`estado.json`: decía «0 decisiones» con `D-ORCH-6` registrada desde hacía días. Es la novena vez que
este proyecto comprueba lo mismo — **verifica con ejecución, no con lectura**.

## 6 · Deuda y observaciones

- **`NO_HAY_TRABAJO_AUTORIZADO`** hoy, y está medido. No se inventó ninguna tarea para llenar la cola.
- Seis oportunidades **bloqueadas** y una **decisión** esperan acta del CEO. Que sigan apareciendo en
  cada vuelta es a propósito: impide que un bloqueo se convierta en un olvido.
- El motor **no descompone** tareas grandes: hoy toda oportunidad autorizada es atómica
  (`eliminar_codigo_muerto`). El día que el acta habilite algo divisible, hará falta descomposición —
  se declara como observación, no como deuda, porque construirla hoy sería trabajo sin caso de uso.

## 7 · Retorno sobre Tokens

Este bloque **no ejecuta trabajo**: quita el paso que obligaba a que alguien lo entregara. Antes, cada
tarea costaba una sesión de asistencia externa para encontrarla, describirla y pasarla. Ahora cuesta
una invocación que termina en segundos y dice, con las cuentas delante, si hay algo que hacer.

Y deja escrito el criterio que faltaba: **una cola vacía es una medición, no una rendición.**
