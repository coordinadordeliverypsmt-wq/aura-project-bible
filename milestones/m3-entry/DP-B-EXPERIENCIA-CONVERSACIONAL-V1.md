# Decision Package B — Experiencia Conversacional v1

**Estado:** propuesto · **Fecha:** 2026-08-09 · **Decide:** CEO · **Propone:** APUS-5
**Alcance cerrado por el CEO:** sólo separación de experiencia. **No migrar logging.**

---

## 1 · Qué está YA resuelto (medido, no supuesto)

El encargo pedía revisar si STT, bus, memoria, router, orquestador y TTS usan `print()` directo.
**No lo hacen** `[EJEC]`: todos pasan por `observability.log`, que escribe a **`sys.stderr`**
(`observability.py:41`). La conversación va a `stdout` desde `__main__.py`.

**Los canales ya están separados.** Demostrado ejecutando la misma sesión con `2>/dev/null`: la
salida queda sin un solo `[VOICE]`, `[EVENT]`, `[MEM]`, `[LLM]` ni `[LAT]`.

Los únicos `print()` a stdout del paquete son los de `hitl_consola` —la confirmación de lista roja,
que **debe** ir ahí (ADR-0003)— y los del entrypoint.

**Conclusión: no hay nada que migrar.** `observability.py` no se toca, como ordenó el CEO.

---

## 2 · Qué falta realmente

Dos cosas, ambas en `__main__.py`:

1. **La telemetría se emite siempre.** Que vaya a `stderr` la separa por canal, pero el usuario ve
   ambos flujos en la misma terminal. Falta un **interruptor**.
2. **El bloque «AURA — arranque verificado»** se imprime a `stdout` en el modo normal. Es el
   criterio 3 que el propio CEO fijó: *la consola es un producto, no una herramienta de desarrollo*.

---

## 3 · Qué se decide

**Modo usuario por defecto · modo diagnóstico bajo bandera.**

| | Modo usuario (por defecto) | Modo diagnóstico (`--debug`) |
|---|---|---|
| Telemetría `[VOICE]/[EVENT]/[MEM]/[LLM]/[LAT]` | **silenciada** | íntegra, como hoy |
| Bloque de arranque técnico | oculto | íntegro |
| Conversación (`stdout`) | **idéntica** | idéntica |
| Confirmación de lista roja | **íntegra** (ADR-0003) | íntegra |
| Registro forense `audit.jsonl` | **íntegro** | íntegro |

**Dos límites que no se cruzan:**

- **ADR-0003.** La confirmación de una acción de lista roja **nunca** se silencia, y la
  previsualización va delante. Silenciarla convertiría el modo usuario en «confirmar a ciegas», que
  es justo lo que el CEO prohibió. **Mutante obligatorio.**
- **Auditabilidad.** Silenciar la consola **no** puede silenciar `audit.jsonl`. Lo que se apaga es la
  *presentación*, no el registro. **Mutante obligatorio:** con el modo usuario activo, el registro
  forense debe seguir escribiéndose completo.

---

## 4 · Cómo, sin tocar `observability.py`

`obs.log` ya centraliza toda la emisión. Basta un interruptor de módulo que consulte antes de
escribir —o que el entrypoint redirija su destino—, activado por `--debug` o por variable de entorno
para las sesiones no interactivas (`--servir`, `--gobierno`).

**Sin componente nuevo, sin ejecutable nuevo** (D40): vive en el entrypoint ya compuesto.

---

## 5 · Criterio de aceptación (el del CEO)

Las **tres cadenas completas del DP A** —nombre, trabajo y proyecto— repetidas **en modo usuario**,
mostrando únicamente la conversación. Ni una línea de telemetría.

Es decir: **B no se puede demostrar sin A**, porque el criterio son sus cadenas. **A va primero.**

Y una prueba de control que hoy nadie tiene: **con `--debug`, la telemetría sigue completa**. Sin
ella, «ocultar» se cumpliría trivialmente borrándola, que es exactamente lo que el CEO prohibió.

---

## 6 · Lo que este DP NO hace

- **No mejora la redacción** de ninguna respuesta. El volcado de los 17 identificadores en
  `snake_case` sigue igual: aparcado por el CEO.
- **No migra el logging.** Medido innecesario (§1).
- **No cambia** `stdout`/`stderr`.

---

## 7 · Retorno sobre Tokens

Una bandera frente a una migración de logging que se ha demostrado innecesaria: el encargo original
apuntaba a revisar seis componentes y ninguno lo necesitaba. **Medir antes de construir ahorró el
incremento entero.**

---

## 8 · Qué se pide aprobar

1. Modo usuario por defecto y `--debug` para el modo diagnóstico.
2. Ocultar el bloque de arranque en modo usuario.
3. Los dos límites del §3 con sus mutantes: ADR-0003 y el registro forense íntegros.
4. **Orden: A antes que B**, porque el criterio de aceptación de B son las cadenas de A.
