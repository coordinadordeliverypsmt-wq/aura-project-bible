# Development Control Plane

Estado persistente **del trabajo sobre AURORA**, legible por máquina.

## Lo primero: esto no es AURORA

Es infraestructura de desarrollo. Sirve para que el trabajo continúe entre sesiones y entre
herramientas sin que un humano copie mensajes de una ventana a otra.

**No concede ninguna capacidad al producto.** No importa un solo módulo suyo —una prueba lo verifica
leyendo el texto del fuente— y vive fuera de su directorio. La métrica de gobierno sigue en **0/7** y
nada de esto la mueve.

Confundir «autonomía para desarrollar AURORA» con «autonomía de AURORA» sería el error más caro
posible aquí, y por eso hay dos pruebas dedicadas a impedirlo.

## Por qué no duplica el checkpoint

`CHECKPOINT-CONTINUIDAD.md` **ya es** estado persistente entre sesiones, y sigue siendo la fuente de
verdad: decisiones, alcance aprobado, prohibiciones, narrativa. Este módulo **no lo sustituye**.

| | `CHECKPOINT-CONTINUIDAD.md` | `estado.json` |
|---|---|---|
| Público | humano | máquina y agentes |
| Contenido | por qué, decisiones, prohibiciones | qué, dónde, en qué estado |
| Autoridad | **sí** | ninguna: refleja, no decide |
| Se escribe | redactando | observando |

El campo `checkpoint` apunta al documento. Si los dos discrepan, **manda el documento**.

## Uso

```bash
python3 entorno/control-plane/control_plane.py estado      # vuelca el estado
python3 entorno/control-plane/control_plane.py handoff     # bloque para el siguiente agente
python3 entorno/control-plane/control_plane.py cuota       # lo observable sobre cuota
python3 entorno/control-plane/control_plane.py refrescar   # reobserva git y cuota
```

## La cuota: lo que se puede saber y lo que no

Se investigó qué expone realmente Claude Code:

- `~/.claude/policy-limits.json` → **restricciones de política, no cuota**.
- `~/.claude/history.jsonl` → marcas temporales de actividad. Dice **cuándo** se trabajó, nunca
  **cuánto** se consumió. Y solo registra entradas interactivas del CLI: **una sesión en segundo
  plano no aparece**, así que la estimación de ventana puede decir «sin actividad» mientras se está
  trabajando.
- No existe fichero ni orden que publique consumo o cuota restante.
- La única evidencia real de agotamiento es **el error devuelto al fallar**. Se observó
  empíricamente: varios subagentes murieron con «You've hit your monthly spend limit». Es una
  observación *a posteriori*, no una predicción.

En consecuencia:

```
usage_known = false
rolling_window.estado = UNKNOWN
weekly.estado         = UNKNOWN
monthly_spend.estado  = UNKNOWN
```

**Este módulo nunca afirma cuánto queda.** Estimar un porcentaje sería el patrón «declarado ≠ real»
cometido dentro de la herramienta que vigila el trabajo — que es donde más daño hace. Una prueba
falla si aparece cualquier insinuación de porcentaje.

Las **tres** ventanas —móvil (~4 h 30 min), semanal y **límite mensual de gasto**— se modelan **por
separado**, porque se renuevan por separado. Cualquiera puede estar `PAUSED` con las otras en
`NORMAL` o en `UNKNOWN`.

| Nombre | Clave en el estado | Cómo se observa |
|---|---|---|
| `SHORT_4H30` | `rolling_window` | error al fallar; la duración es declarada, no medida |
| `WEEKLY` | `weekly` | error al fallar |
| `MONTHLY_SPEND_LIMIT` | `monthly_spend` | **observado el 2026-08-17**: `«You've hit your monthly spend limit»` |

**Y no son del mismo tipo.** Las dos primeras son **capacidad incluida** en el plan: agotarlas
detiene el trabajo. La tercera es **uso adicional de pago**: agotarla **no** detiene el trabajo que
cabe en lo incluido.

```python
CAPACIDAD_INCLUIDA = ("rolling_window", "weekly")
USO_ADICIONAL      = ("monthly_spend",)
```

Esta separación se añadió tras un **defecto real**: `puede_empezar()` devolvía `False` incluso para
`coste="bajo"` con la sesión y la semanal en `NORMAL`, solo porque `monthly_spend` estaba `PAUSED`.
Habría parado documentar y revisar, que era lo único todavía posible. Evidencia visual del CEO
(página oficial de uso, 2026-08-17): sesión 26 % usada DISPONIBLE · semanal 56 % usada DISPONIBLE ·
uso adicional USD 21,84 sobre un límite de USD 20,00 = 109 % PAUSADO.

`resumen_de_cuota(cuota)` devuelve la línea que evita esa confusión al leer un handoff:
`capacidad incluida: DISPONIBLE · uso adicional: BLOQUEADO`.

## Porcentajes: leídos, nunca estimados

`registrar_uso_observado(cuota, ventana, porcentaje_usado, fuente, observado_en, estado)` es la
**única** vía por la que entra un porcentaje. Exige `fuente` e `observado_en` —sin ellos, un dato
leído es indistinguible de uno inventado— y marca `caduca: True`, porque es una instantánea de un
contador que se mueve solo.

`observar_cuota()` sigue sin contener ningún porcentaje, y `usage_known` sigue en **`false`**: la
herramienta no publica el consumo. Que un humano lo lea en una web no lo hace consultable por el
agente.

El límite mensual se añadió porque se observó de verdad, no por simetría: un subagente auditor murió
con ese mensaje. Tratarlo como «la semanal» habría hecho deducir una renovación falsa —«ya es
lunes»— y volver a chocar con el mismo muro. `migrar_cuota()` completa esta ventana como `UNKNOWN`
en los estados escritos antes de que existiera; **nunca** como `NORMAL`, que afirmaría un margen que
nadie observó.

## Decidir si arrancar trabajo

`puede_empezar(cuota, coste)` aplica una regla deliberada: **desconocer la cuota no es tenerla.**

| Estado | Trabajo barato | Trabajo caro |
|---|---|---|
| Ambas `NORMAL` | sí | sí |
| Alguna `UNKNOWN` | sí | **no** |
| Alguna `WARNING` | sí | no |
| Alguna `PAUSED` / `CHECKPOINT_REQUIRED` | **no** | no |

Empezar algo grande sin margen conocido acaba en trabajo abandonado a mitad, que es peor que no
haberlo empezado.

## Estados

Vocabulario fijado por el CEO el 2026-08-17:

`WORKING` · `WAITING_FOR_QUOTA` · `WAITING_FOR_ENVIRONMENT` · `DECISION_REQUIRED` ·
`WAITING_FOR_HUMAN` · `COMPLETED` · `FAILED` · `WAITING_FOR_NEXT_TASK`

**`WAITING_FOR_QUOTA` exige evidencia observada de límite y `validar()` lo rechaza sin ella.** No es
un detalle: desconocer la cuota no es haberla agotado, y si se pudiera declarar por ignorancia el
trabajo se detendría esperando una renovación que quizá no desbloquea nada — dejando al siguiente
agente una parada inventada. Si el bloqueo es de memoria o disco, el estado es
`WAITING_FOR_ENVIRONMENT`; si simplemente no se sabe, es `WORKING`.

El octavo estado, `WAITING_FOR_NEXT_TASK`, se conserva porque «no hay tarea asignada» no es lo mismo
que «espero una decisión humana»: el primero se resuelve dando trabajo, el segundo solo lo resuelve
una persona.

## No repetir trabajo ya hecho

```python
cp.iniciar_tarea(estado, "T-1", "descripción")      # marca de inicio
cp.completar_tarea(estado, "T-1", "resultado", evidencia={...})   # + duración
cp.debe_ejecutar(estado, "T-1")                      # (False, "ya completada …")
```

Un agente que reanuda y repite una tarea completada la presenta como nueva. Es la forma más cara de
«declarado ≠ real» en un relevo, porque el siguiente lector cuenta dos veces el mismo avance.
`completar_tarea` es idempotente.

## Leer el checkpoint

```python
cp.leer_checkpoint(doc)              # existe · líneas · secciones · sha256
cp.checkpoint_sin_cambios(estado, doc)   # (False, "el checkpoint cambió …")
```

Observa, no interpreta ni reescribe. Si el documento cambió desde que se escribió el estado, el
estado describe otra realidad y lo dice: **la narrativa manda sobre el estado observado**.

## Estado por tarea — el global no oculta el individual

```python
cp.fijar_estado_tarea(estado, "EXP-REPRO", "WAITING_FOR_ENVIRONMENT", "RAM")
cp.fijar_estado_tarea(estado, "EXP-CAMPANA", "DECISION_REQUIRED", "D-N3")
cp.estado_de_tarea(estado, "EXP-REPRO")     # {'estado': 'WAITING_FOR_ENVIRONMENT', …}
```

Pueden coexistir `EXP-REPRO: WAITING_FOR_ENVIRONMENT` y `EXP-CAMPANA: DECISION_REQUIRED`.
**No es una contradicción.** El estado global describe la tarea que el agente intenta ejecutar; las
demás conservan el suyo. Colapsarlos haría que un agente esperase memoria por una decisión
pendiente, o pidiese una decisión por falta de memoria.

Una tarea sin estado propio devuelve `UNKNOWN`, **nunca hereda el global**: heredarlo haría creer
que una tarea nueva ya está bloqueada por un motivo que no le concierne.

## Bloqueo por cuota

```python
cp.registrar_bloqueo_de_cuota(estado, mensaje="…limit…", ventana="WEEKLY", tarea="EXP-REPRO")
```

Registra timestamp, ventana, mensaje observado, tarea pausada, último paso completado, siguiente
paso, archivos modificados y pruebas realizadas.

Registra además `tipo: QUOTA_LIMIT_OBSERVED`, `renovacion: UNKNOWN` —el producto no publica cuándo
se renueva ninguna ventana— y `estado_previo`, para no perder el estado que la cuota interrumpió:
`WAITING_FOR_QUOTA` describe la *acción*, no anula un `DECISION_REQUIRED` que sigue vigente.

**Ninguna ventana arrastra a otra, en ningún sentido.** Marcar `SHORT_4H30` deja las otras dos en
`UNKNOWN`; marcar `MONTHLY_SPEND_LIMIT` deja la móvil y la semanal en `UNKNOWN`. Deducir una
renovación haría reanudar trabajo que la otra ventana sigue bloqueando. Sin evidencia de cuál se
agotó, se registra `UNKNOWN` en lugar de suponerlo.

Y el bloqueo es **de la tarea, no del proyecto**: `AUDITORIA-DP-CP` en `WAITING_FOR_QUOTA` no impide
que una tarea local e independiente siga en `WORKING`. Si contagiara, el único trabajo que todavía
se puede hacer —documentar, revisar, ordenar— se pararía justo cuando es el único disponible.

La cuota es un **recurso externo** que bloquea temporalmente, no una decisión humana.

## Interrupciones — nunca un `COMPLETED` falso

```python
cp.interrumpir(estado, "EXP-REPRO", "primera_inferencia")   # → FAILED, no COMPLETED
```

Momentos cubiertos: espera ambiental, primera inferencia, segunda inferencia, escritura de
evidencia, agotamiento de cuota, cierre de Claude. Ninguno produce `COMPLETED`, y la tarea vuelve a
ser ejecutable.

Un `COMPLETED` falso hace que el siguiente agente dé por hecho un trabajo que nunca ocurrió — y
nadie vuelve a mirarlo.

## Reanudar

`estado_vigente(estado, commit_actual)` compara el commit registrado con el real. Si difieren, el
estado describe un pasado que ya no es el presente y **lo dice**, en vez de dejar que alguien
continúe sobre una foto vieja.

Que exista un fichero de estado no demuestra que el proceso anterior terminara bien.
