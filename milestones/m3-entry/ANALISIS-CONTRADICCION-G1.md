# CONTRADICCIÓN G1

> **2026-08-25.** Investigación forense. No modifica código, ni `aura_skeleton/`, ni las decisiones
> históricas. Evidencia D47: `[EJEC]` medido · `[LECT]` leído.

## 0 · Conclusión, por delante

**No hay contradicción. La contradicción la introduje yo en el informe anterior, y era un error de
lectura mío.** Leí el campo `nota` de las decisiones e ignoré su campo `estado`; y leí *«R-A: 0
entradas detectables»* como «0 violaciones» cuando significa «0 entradas de lista blanca».

**La causa del cambio de comportamiento es demostrable: `ESCENARIO C`.**

## 1 · Evidencia histórica

**`D-G1-2`** — *«Aprobar la lista blanca inicial de G-1»* · `bloquea: G1-GREEN`
> nota: *«R-A: 0 entradas detectables. R-B: 25 escrituras en 10 módulos. Solo 3 son inequívocos
> (memory.py, reglas.py, observability.py…). Los 7 restantes son DUDOSOS y NO los apruebo…»*
> **estado: `APROBADA DELIMITADA 2026-08-18 (A sí, B no, C excluido)`**

**`D-G1-3`** — *«G-1 es CIEGA a las 4 rutas de ALERTA-006 sin anotar tipos»* · `bloquea: G1-GREEN`
> nota: *«…G-1 detecta 0 de las 4 rutas que motivaron su existencia, porque `ModeloUsuario.__init__`
> y `Orchestrator.__init__` no anotan el tipo del almacén… Escribir el manifiesto la pondría en
> VERDE sobre un punto ciego…»*
> **estado: `APROBADA 2026-08-18 (solo dos anotaciones de tipo)`**

**El campo `nota` es el planteamiento del conflicto al CEO, no el estado del sistema.** Ambas
decisiones **fueron aprobadas** el 2026-08-18.

## 2 · Evidencia actual `[EJEC]`

R-A reporta **4 violaciones** con fichero y línea: `core/modelo_usuario.py:95 · olvidar`,
`:113 · marcar`, `core/orchestrator.py:1287 · crear`, `:1314 · desactivar`. R-B reporta **9**.

`violaciones_ra()` compara llamadas contra `operaciones_clasificadas_mutantes()`, que se deriva de
`architecture_manifest.toml` `[LECT]`. Ese fichero **está modificado respecto a HEAD** y contiene una
sección `[mutaciones]` nueva que declara el motor, `persistencia_autorizada` y la superficie mutante
de cada almacén: `memory.py → write, olvidar, marcar, restore`; `reglas.py → crear, desactivar`.

**Las 4 violaciones son exactamente esas operaciones llamadas desde fuera de su almacén.**

El propio manifiesto cita su autorización: *«Aprobación delimitada del CEO, D-G1-2, 2026-08-18. El
GRUPO B queda DELIBERADAMENTE FUERA… y su ausencia aquí es la razón de que R-B siga reportándolos.»*

## 3 · Diferencias

| Elemento | Histórico | Actual | Diferencia |
|---|---|---|---|
| Sección `[mutaciones]` del manifiesto | **no existía** | existe, con motor, lista blanca del Grupo A y superficies mutantes | **la causa** |
| Detección R-A | 0 rutas | **4**, con fichero y línea | consecuencia de lo anterior |
| Vía de detección | se suponía por tipo del receptor | **por nombre de operación clasificada** | no necesita anotar tipos |
| `ModeloUsuario.__init__` | sin anotar | **sigue sin anotar** `[LECT]`: `def __init__(self, memoria) -> None` | **sin cambios** |
| «0 entradas detectables» | entradas **de lista blanca** para R-A | — | **yo lo leí como «0 violaciones»** |
| Rojos de R-B | 25 escrituras, 3 aprobadas | 9 | el Grupo B quedó fuera **por decisión** |

## 4 · Causa

**`ESCENARIO C` — la implementación de G-1 cambió**, en su entrada de configuración: se escribió la
sección `[mutaciones]` del manifiesto, aplicando `D-G1-2`.

**El código de producción NO cambió**, y esto es lo que descarta los demás escenarios: la anotación
de tipo que `D-G1-3` aprobó **nunca se aplicó** — `ModeloUsuario.__init__` sigue sin anotar. R-A ve
las 4 rutas **sin** esas anotaciones, porque el manifiesto le dio los **nombres** de las operaciones
mutantes y no necesita resolver el tipo del receptor.

Descartados: **A** (el código no cambió) · **B** (la RED no cambió) · **D** (misma ruta) · **F**
(hay evidencia suficiente). **E** es cierto como efecto, pero `C` es la causa.

**Un matiz que merece registrarse:** `D-G1-3` temía que *«escribir el manifiesto la pondría en VERDE
sobre un punto ciego»*. **Ocurrió lo contrario:** el manifiesto la dejó en ROJO y detectando. El
riesgo que preocupaba al CEO no se materializó, y eso es evidencia a favor de la vía elegida.

## 5 · Impacto

- **`D-G1-2`** — aplicada. **Los 9 rojos de R-B no son deuda pendiente: son el resultado esperado de
  la decisión**, que dejó el Grupo B fuera a propósito. Cerrarlos exigiría revisar esa decisión.
- **`D-G1-3`** — **aprobada pero NO aplicada.** Las dos anotaciones autorizadas siguen sin escribirse.
  **Y ya no son necesarias para que R-A detecte**, lo cual cambia su naturaleza: eran el remedio a
  una ceguera que otra vía resolvió.
- **`G1-GREEN`** — no se desbloquea con este análisis. **Qué lo bloquea hoy exactamente:
  NO_DETERMINADO** — no lo he investigado y no lo infiero.
- **Autonomía** — sin cambio: `AUTO_EXECUTABLE` sigue en 0, `tareas_AUTO` en 6.
- **Línea A** — los 2 hallazgos de G-1 siguen `DECISION_REQUIRED` por zona vetada.

## 6 · Decisión requerida

**No hay que resolver ninguna contradicción: no existía.** Quedan dos preguntas reales, y ninguna la
respondo:

1. **¿Siguen siendo necesarias las dos anotaciones de tipo que `D-G1-3` aprobó?** R-A detecta sin
   ellas. Puede que aporten cobertura frente a llamadas que el nombre no revela, o puede que la
   decisión haya quedado sin objeto.
2. **¿Se revisa `D-G1-2` para incorporar el Grupo B?** Los 9 rojos de R-B persisten **por decisión
   suya**, no por trabajo sin hacer. Mientras no se revise, están correctamente rojos.

## 7 · D-M8

**`D-M8-1` intacta · `D-M8-2` intacta · `D-M8-3` intacta.** No se tocó ninguna, no se eligió entre
sus alternativas, y G-2/G-3/G-6/G-7 no se han vuelto a mirar.
