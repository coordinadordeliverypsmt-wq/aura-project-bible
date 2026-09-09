# ESPEC-F2-KILL-SWITCH-UNIVERSAL

> **2026-08-25 · ESPECIFICACIÓN, no implementación.** Ninguna línea de producción cambia con este
> documento. Evidencia D47: `[EJEC]` medido · `[LECT]` leído.
>
> **Estado: `WAITING_FOR_HUMAN_DECISION`** — contiene decisiones que el contrato no determina.

## 1 · Propósito

Especificar F2 —*«Kill switch universal · Paso 0 en el motor»* (`DP-D-M-8 §7`)— con el detalle
suficiente para que su implementación **no invente** nada, y **marcar explícitamente lo que las
fuentes no determinan** en vez de rellenarlo.

**Lo que este documento descubre y conviene leer antes que nada:** el Paso 0 **ya existe**. No hay
que crearlo. `PermissionManager.authorize` consulta el kill switch **como primerísima comprobación**,
antes incluso de la lista roja `[LECT]`. El defecto de G-2 no es que falte el control: es que **hay
rutas que no llegan a él**. Eso cambia la naturaleza de F2 —de *construir* a *hacer inevitable*— y
es justo donde aparece la decisión que el contrato no resuelve.

## 2 · Fuentes contractuales

| Fuente | Qué determina |
|---|---|
| `DP-D-M-8 §7` (aprobado CEO 2026-08-17) | F2 = *«Kill switch universal · Paso 0 en el motor»*; orden F2→F3→F4; *«el sistema esté protegido antes de ser refactorizado»* |
| `DP-D-M-8 §6` | forma de G-2: *«prueba parametrizada sobre **todas** las operaciones del catálogo, no solo las que pasan por `authorize`»* |
| `DP-D-M-8 §4.2` | la política se resuelve con el par `(operacion, sujeto)`; `RN-2`: **lo no catalogado se deniega** |
| `DP-D-M-8 §4.3` | *«pasar por el motor no es lo mismo que pedir confirmación»* |
| `ALERTA-005` (CLAUDE.md, no negociable) | toda ejecución pasa por el motor único, con permisos y dry-run. **Ninguna ruta alternativa** |
| `ALERTA-006` | el defecto vivo: con la parada armada, el dato se destruye igual |
| `D-M8-1` | alternativa **C** determinada; **A descartada** por crear segunda vía |
| `permissions.py:117-121` `[LECT]` | `authorize(action, args, trace_id) -> tuple[bool, str]`; el kill switch es la **primera** comprobación y devuelve `(False, "kill switch activo (5.3 §5)")` |
| `kill_switch.py` `[LECT]` | API: `engage(reason)` · `disengage()` · `is_engaged() -> bool` · `trigger_file` (por defecto `/tmp/aura/KILL`) |
| `automatizacion.py` `[LECT]` | `MotorAutomatizacion(adaptador_o_registro, permisos, altera)`; usa `adaptador.simular(accion, args, trace_id) -> plan`; `_detener` / `_error` devuelven `dict` |
| REDs G-2 ×3 y G-3 #4 `[EJEC]` | el comportamiento exigido, en rojo |

## 3 · Garantía

> **Con el kill switch ARMADO, ninguna mutación persistente ocurre — por ninguna ruta.**

Las dos mitades importan. *«Ninguna mutación»* es el efecto; *«por ninguna ruta»* es lo que hoy
falla y lo que F2 debe volver demostrable.

## 4 · Posición arquitectónica

F2 es el **Paso 0**: la comprobación que antecede a todo lo demás dentro del motor único. `§7` la
sitúa antes de F3 (ejecutor interno) y F4 (migración de rutas) porque *«cierra la violación más clara
de una garantía declarada»* sin depender del andamiaje posterior.

## 5 · Contrato de entrada

**DETERMINADO:** el Paso 0 necesita **la operación** y su **`trace_id`**, y recibe además los `args`.
Es la firma que `authorize` ya expone: `(action: str, args: dict, trace_id: str)`.

**NO_DETERMINADO:** si la entrada debe incluir **`sujeto`**. `§4.2` establece que la política se
resuelve con el par `(operacion, sujeto)`, pero **asigna esa dimensión a F3** (`§7`). Si F2 se
implementa antes que F3, su entrada no tiene `sujeto`. **Cuál de las dos cosas ocurre primero es
`DECISION_REQUIRED` (ver §17.2).**

## 6 · Contrato de salida

**DETERMINADO — el veredicto:** con el kill switch armado, el resultado es **negativo y motivado**.
Hoy: `(False, "kill switch activo (5.3 §5)")` `[LECT]`, y la RED de control de G-2 exige
literalmente que `"kill switch" in motivo`.

**NO_DETERMINADO — la forma:** `authorize` devuelve `tuple[bool, str]`; el motor devuelve `dict` vía
`_detener`/`_error`. **Si el Paso 0 se ubica en el motor, cuál de los dos vocabularios usa no está
determinado por ninguna fuente.** Depende de §17.1.

## 7 · Kill switch DESARMADO

**DETERMINADO:** el Paso 0 **no decide nada**. No autoriza: deja pasar al siguiente control
(lista roja, catálogo). `§4.3` es explícito en que atravesar el motor **no** implica pedir
confirmación.

## 8 · Kill switch ARMADO

**DETERMINADO:**
1. La operación **no se ejecuta**.
2. El resultado es negativo, con motivo que menciona el kill switch.
3. Queda **constancia en el audit** — hoy `obs.log("KILL", …, audit=True)` `[LECT]`.
4. **Ninguna mutación persistente ocurre**, que es literalmente G-2.

**No hay excepciones determinadas por ninguna fuente.** Si alguna operación debiera poder ejecutarse
con la parada armada, **ninguna fuente lo dice**, y esta ESPEC no la introduce.

## 9 · Dry-run

**DETERMINADO:** el dry-run existe y es parte del contrato del motor —`ALERTA-005` lo nombra— y
hoy se materializa como `adaptador.simular(accion, args, trace_id) -> plan` `[LECT]`.

**NO_DETERMINADO:** **qué hace `simular` con el kill switch ARMADO.** Ninguna fuente lo dice.
Caben dos lecturas y ambas son defendibles: simular no muta, luego podría permitirse; o la parada es
total, luego tampoco se simula. **`DECISION_REQUIRED` (§17.3).**

**Lo que sí queda fijado aquí, porque deriva de la garantía:** un dry-run **nunca** puede convertirse
en ejecución real. Eso no es una decisión nueva — es `ALERTA-005` aplicada.

## 10 · Orden de evaluación

**DETERMINADO — kill switch primero.** `permissions.py:118` lo comprueba **antes** que la lista roja
`[LECT]`, y la RED de control `test_g2_control_el_kill_switch_detiene_las_acciones_del_catalogo` lo
ejerce sobre las acciones del catálogo `[EJEC]`. El orden vigente es:

```
kill switch  →  autorización (lista roja / catálogo)  →  ejecutor
```

**Es el único orden compatible con fail-closed:** preguntar primero si el sistema está parado y
sólo después si la acción está permitida.

**NO_DETERMINADO:** dónde encaja el **ejecutor interno** de F3 en esa cadena.

## 11 · Prohibiciones

| Prohibición | Respaldo |
|---|---|
| Ninguna segunda vía de ejecución | **`ALERTA-005`** — respaldada |
| Ninguna consulta duplicada del kill switch en ramas individuales | **`D-M8-1`**, alternativa A descartada — respaldada |
| Ninguna mutación con el kill switch armado | **G-2** — respaldada |
| Fail-closed: lo no catalogado se deniega | **`RN-2` / §4.2** — respaldada |
| Un dry-run no se convierte en ejecución real | **`ALERTA-005`** — respaldada |
| Ninguna autoridad ni autenticación nueva | **regla de gobernanza del proyecto**, no del DP — respaldada fuera de F2 |
| Ninguna capacidad no declarada | **CEO 2026-08-03** (solo capacidades registradas) — respaldada |
| *«GitHub sigue siendo espejo»* | **NO APLICA a F2** — pertenece al Communication Plane (D-CP-5/G5). No lo declaro `NO_DETERMINADO`: es de otro plano |

## 12 · Invariantes demostrables

1. **I-F2-1** · armado ⇒ ninguna mutación persistente, **por ninguna ruta**.
2. **I-F2-2** · armado ⇒ el resultado menciona el kill switch.
3. **I-F2-3** · armado ⇒ queda registro en el audit.
4. **I-F2-4** · desarmado ⇒ el Paso 0 no altera el veredicto de los controles posteriores.
5. **I-F2-5** · el kill switch se evalúa **antes** que la autorización.
6. **I-F2-6** · **no existe ruta de mutación que no atraviese el Paso 0.** Es la que hoy falla.

## 13 · Evidencia requerida de la RED F2

- **Cobertura, no muestreo:** `§6` exige prueba parametrizada **sobre todas las operaciones del
  catálogo**. Una RED que pruebe tres operaciones no demuestra `I-F2-6`.
- **Efecto, no retorno:** que el dato **siga en disco**, como ya hacen las G-2 actuales — no basta
  con que una función devuelva `False`.
- **Caso de control obligatorio:** con el kill switch **desarmado**, la operación **sí** ocurre. Sin
  él, un sistema totalmente roto pasaría la RED.
- **Las rutas que hoy fallan:** `ModeloUsuario.borrar`, `ModeloUsuario.refutar`, `AlmacenReglas.crear`.

## 14 · Mutación (no se crea el TOML todavía)

Mutantes que **deben morir**: no consultar el kill switch · consultarlo **después** de la
autorización (rompe `I-F2-5`) · invertir `is_engaged()` · devolver `True` con motivo vacío ·
dejar **una** ruta sin pasar por el Paso 0 (ataca `I-F2-6`, el mutante central) · convertir el
dry-run en ejecución · omitir el registro de audit.

**El mutante que de verdad importa es el de la ruta huérfana:** si sobrevive, F2 está declarada y no
es real — el patrón que este proyecto ya ha pagado nueve veces.

## 15 · Dependencias F3/F4

- **F3** hereda `I-F2-5` y añade el `sujeto` a la entrada; **no puede** reintroducir una ruta que
  esquive el Paso 0.
- **F4** migra rutas en el orden ya fijado: **soberanía → reglas → señales**. Cada ruta migrada debe
  **conservar** `I-F2-1..6`; ninguna puede relajarlos «temporalmente».

## 16 · Dependencia de F0

- **DETERMINADO (contractual):** `§7` exige *«el sistema esté protegido antes de ser
  refactorizado»*. La red **existe**: F0 está `TECHNICALLY_COMPLETE` y `no_falta_construccion: true`.
- **NO_DETERMINADO:** **§7 no menciona auditoría en ninguna parte.** La exigencia de auditoría
  independiente no viene del DP, sino del protocolo del proyecto (*«el que implementa nunca audita
  su propio trabajo»*) y de `requisitos_F0.R4`. **No la invento como requisito de F2, ni la retiro.**
- **`DECISION_REQUIRED`:** si F2 espera a `AUDITORIA-DMOCHO-F0` (`WAITING_FOR_QUOTA`, la desbloquea
  la cuota, no el CEO) o se adelanta. **La ESPEC no lo decide** (§17.4).

## 17 · Decisiones pendientes

**17.1 · ¿Dónde vive el Paso 0? — la decisión principal.**
Hoy el kill switch se consulta en `permissions.py`, no en el motor; `§7` dice *«Paso 0 en el
motor»*. Caben tres lecturas y **el contrato no elige**: (a) **mover** la consulta al motor; (b)
**dejarla** en `authorize` y hacer que el motor garantice que toda mutación pase por él; (c)
**ambas**, que está **prohibido** —sería la consulta duplicada que `D-M8-1` descartó—.
**(c) queda descartada por contrato; entre (a) y (b) decide el CEO.**

**17.2 · ¿F2 antes que F3, o `sujeto` desde el principio?** `§7` ordena F2→F3, pero `§4.2` quiere el
par `(operacion, sujeto)`. Afecta al contrato de entrada (§5).

**17.3 · ¿`simular` con el kill switch armado?** Ninguna fuente lo determina (§9).

**17.4 · ¿F2 espera a la auditoría de F0?** (§16).

## 18 · Criterio de entrada a implementación

**No se escribe código hasta que:** 17.1 esté resuelta *(bloqueante — sin ella no se sabe dónde va el
Paso 0)* · 17.2 y 17.3 resueltas o declaradas fuera de alcance de F2 · 17.4 resuelta · y esta ESPEC
aprobada, como se hizo con `ESPEC-G-1`.

**Con 17.1 resuelta, el resto de esta ESPEC es suficiente para escribir la RED.**
