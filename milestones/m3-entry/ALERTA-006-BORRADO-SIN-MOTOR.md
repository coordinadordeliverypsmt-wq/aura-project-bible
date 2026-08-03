# ALERTA-006 — Una ruta borra información del usuario sin pasar por el motor único

**Detectada:** 2026-08-03, durante el inventario de clasificadores de intención para el DP de D-M-7.
**Estado:** registrada, **pendiente de decisión del CEO**. No se ha modificado código.
**Clasificación:** compromete la **arquitectura** (ALERTA-005) y puede producir **pérdida de
información del usuario**. Cumple con holgura el umbral de deuda del CEO.

---

## El hecho

`orchestrator.py:338-342` — la cascada de soberanía del modelo de usuario se evalúa **la primera de
todas** y hace `return` inmediato. Dentro de ella, `_atender_modelo_usuario` (`orchestrator.py:417-421`)
llama directamente a `modelo_usuario.borrar(...)`.

`motor.ejecutar(...)` está en `orchestrator.py:392`, en la **ruta 6**. La rama de soberanía retorna
mucho antes: **nunca llega**.

Resultado: existe una ruta que **elimina información persistida del usuario** sin pasar por
`PermissionManager`, sin dry-run y sin confirmación humana.

`permissions.py:67` clasifica `eliminar_informacion` como **lista ROJA**, efecto *«destruye»*, bajo el
criterio declarado en la cabecera del propio fichero: *«Lista roja = confirmación humana SIEMPRE,
tolerancia cero a falsos negativos»*.

## Por qué el efecto no es teórico: se borra el dato equivocado

El disparador es la subcadena `"olvida"` (`_PAT_MODELO_OLVIDA`, 2 patrones). Qué se borra lo decide
`_foco` (`orchestrator.py:437-444`), que busca palabras de más de 4 letras de cada entrada dentro del
texto y, **si no encuentra ninguna, cae a `vivas[0]`** — la primera entrada viva, sin relación con lo
pedido.

**Reproducido `[EJEC]`:**

```
modelo ANTES  : ['Prefiero el cafe sin azucar', 'Suelo trabajar por las noches']
petición      : «Olvida que a mi hermana le gusta el cafe verde»   ← habla de un TERCERO
_foco elige   : 'Prefiero el cafe sin azucar'                      ← nada que ver
borradas      : 1
modelo DESPUES: ['Suelo trabajar por las noches']
respuesta     : «Hecho. Ya no lo consideraré parte de lo que sé de ti.»
```

El usuario pide olvidar un dato **de su hermana** y AURA borra **una preferencia propia**, confirmando
que lo ha hecho. El capturador de señales sí detecta que la frase habla de un tercero
(`_habla_de_tercero`) y descarta la captura — pero **esa guarda no protege el borrado**, que ocurre en
otra ruta.

## Matiz honesto sobre el alcance

El usuario **sí pidió olvidar algo**: la intención es legítima y borrar a petición es soberanía
(ADR-0017). Lo que falla no es que se borre, sino **qué** se borra: la resolución del referente («eso»)
es una heurística que, al no acertar, degrada a «borra el primero» en vez de a «pregunta cuál».

Por eso el problema es doble y conviene no confundirlo:

1. **Arquitectónico:** una destrucción de datos no atraviesa el motor único (ALERTA-005) ni el control
   de lista roja (ADR-0003). Esto es cierto aunque el referente se resolviera bien.
2. **De comportamiento:** el fallback `vivas[0]` convierte una duda en una destrucción silenciosa.
   Contradice el principio del propio proyecto: *«ante la duda, roja»*.

## Rutas afectadas

Las tres primeras ramas de `on_turn` mutan estado persistente sin pasar por el motor `[EJEC]`:

| Ruta | Línea | Qué muta | ¿Motor? | ¿HITL? |
|---|---|---|---|---|
| Soberanía → `borrar` | 417-421 | **elimina** del modelo del usuario | No | No |
| Soberanía → `refutar` | 424-428 | marca `refutada` | No | No |
| Automatizaciones → crear | 354-355 | escribe regla persistente | No | No |
| Automatizaciones → cancelar | 360-361 | desactiva regla | No | No |

`refutar` y la gestión de reglas son reversibles (append-only); **`borrar` no lo es**.

## Qué NO se ha determinado

- Si el CEO considera que la soberanía del usuario **debe** exenta del motor por diseño (un «olvida
  esto» que pidiera confirmación podría ser hostil). Es una decisión de producto, no técnica.
- Si `refutar` sobre el foco equivocado tiene el mismo problema de referente. `[HIPO]` — el mecanismo
  `_foco` es el mismo, así que probablemente sí, pero no lo he ejecutado.

## Opciones esbozadas (sin analizar — no es este el DP)

1. Que el fallback de `_foco` **no borre**: ante duda, pedir desambiguación en vez de elegir el primero.
2. Enrutar el borrado por el motor único como `eliminar_informacion` (lista roja → HITL).
3. Hacer el borrado reversible (marca de baja en vez de eliminación), preservando append-only.

**Recomiendo la 1 como mínimo inmediato** —convierte una destrucción silenciosa en una pregunta— y
decidir 2 y 3 con su propio Decision Package.
