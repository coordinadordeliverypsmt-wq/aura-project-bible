# CONTRATO-DE-CAPACIDAD

**Estado:** propuesto · **Fecha:** 2026-09-07 · **Decide:** CEO · **Propone:** Claude Code
**Naturaleza:** especificación. No introduce código, no amplía autoridad, no delega verbos.

> El barrido de `010` demostró que el bloqueo no está en el motor —que funciona y lo ha demostrado
> 10 veces— sino en que **una capacidad declarada no trae consigo lo que hace falta para
> construirla**. Este documento define ese «lo que hace falta», y lo define de forma que **el propio
> motor pueda evaluarlo**, sin que nadie tenga que explicarle cada vez qué significa la capacidad.

---

## 0 · El contrato no se inventa: ya existe en embrión

Dos esquemas del repositorio ya hacen exactamente esto para objetos más pequeños. El contrato de
capacidad es su unión, no un vocabulario nuevo:

| Precedente | Qué contrata | Campos |
|---|---|---|
| `politica-orquestador.toml` | una **acción** del orquestador | `tipo` · `objetivo` · `autoridad` · `precondiciones` · `agentes_permitidos` · `evidencia_requerida` · `criterio_de_exito` · `ante_fallo` · `permite_fallback` · `limites_de_modificacion` · `origen` |
| `descubrimiento.PIEZAS_OBLIGATORIAS` | una **oportunidad** | `fuente` · `justificacion` · `alcance` · `accion` · `autoridad` · `criterio_de_finalizacion` · `evidencia_requerida` · `riesgo` · `estado` |

Ambos comparten la misma tesis, escrita en `descubrimiento.py:29`: *«un descubridor que puede
inventar trabajo produce actividad que parece progreso»*. Y ambos la hacen cumplir del mismo modo:
**campo obligatorio ausente ⇒ el objeto no se construye**. El contrato de capacidad hereda esa regla.

---

## A · Contrato propuesto

### Estados

```
DECLARADA → ESPECIFICADA → AUTORIZADA → IMPLEMENTABLE → EJECUTABLE → VERIFICABLE → COMPLETADA
                                    ↘  BLOQUEADA (DECISION_REQUIRED)  ↙
```

Cada flecha es una **puerta con condición objetiva**, no un juicio. Una capacidad nunca «avanza»:
cumple o no cumple. `BLOQUEADA` es alcanzable desde cualquier estado y es la única salida cuando
falta un campo obligatorio.

### Campos

**Los 1-4 son de identidad y no bloquean por sí solos. Los 5-11 son los que deciden.**

| # | Campo | Obligatorio | Qué es | Precedente |
|---|---|---|---|---|
| 1 | `id` | **sí** | identificador estable (`010`, `eliminar_codigo_muerto`) | `Oportunidad.id` |
| 2 | `nombre` | **sí** | el enunciado literal de la capacidad | plan de formación |
| 3 | `version` | **sí** | versión del contrato, no de la capacidad | `politica…toml:version` |
| 4 | `estado` | **sí** | uno de los siete de arriba | `Oportunidad.estado` |
| 5 | `intencion` | **sí** | qué problema resuelve, en una frase | `objetivo` |
| 6 | `entradas` | **sí** | lista de `{nombre, fuente, formato}`. **`fuente` debe ser verificable** | `fuente` + `fuente_verificable()` |
| 7 | `salidas` | **sí** | lista de `{resultado, destino}`. `destino` = dónde queda disponible | `evidencia_requerida` |
| 8 | `regla_de_transformacion` | **sí** | la relación **determinista** entradas→salida, o `REQUIERE_INFERENCIA` | *nuevo — es lo que `010` no tiene* |
| 9 | `fuentes_de_verdad` | **sí** | ficheros/módulos que son **autoridad**, separados de los de **referencia** | `origen` |
| 10 | `perimetro` | **sí** | `{modificables: [...], fuera_de_alcance: [...]}`. **Rutas exactas, nunca globs ni prefijos** | `_FICHEROS_AUTORIZADOS`, `_ZONA_PERMITIDA` |
| 11 | `autoridad` | **sí** | `{nivel, acta, parte_de_aura, parte_del_ceo}` | `Oportunidad.autoridad`, `review.habilitado()` |
| 12 | `ejecutor` | **sí** | el verbo requerido **y si existe ejecutor construido** | `review._EJECUTORES_CONSTRUIDOS` |
| 13 | `efectos` | **sí** | `{permitidos, prohibidos, reversible: bool}` | `limites_de_modificacion`, `tipo` |
| 14 | `verificacion` | **sí** | `{invariantes, pruebas_minimas, criterio_de_aceptacion, evidencia}` | `criterio_de_exito`, `criterio_de_finalizacion` |
| 15 | `trazabilidad` | **sí** | punteros: especificación · autorización · plan · ejecución · pruebas · evidencia | log encadenado |

**Opcionales:** `precondiciones`, `agentes_permitidos`, `ante_fallo`, `permite_fallback`, `riesgo`,
`notas`. Son los que `politica-orquestador.toml` ya usa y que **no cambian el veredicto** de
implementabilidad: afinan la ejecución, no la autorizan.

**Regla dura de los campos 6, 9 y 10:** toda ruta citada debe **existir**. Es la misma barrera que
`descubrimiento.fuente_verificable()` aplica hoy —*«una procedencia que no se puede ir a mirar es
indistinguible de una inventada»*— y por la misma razón vive en el constructor, no en un filtro.

---

## B · Regla objetiva de implementabilidad

```
IMPLEMENTABLE = TRUE   si y solo si TODAS:

 1. los 15 campos obligatorios están presentes y no vacíos;
 2. regla_de_transformacion != REQUIERE_INFERENCIA;
 3. toda entrada tiene fuente verificable       -> fuente_verificable(f) == True
 4. perimetro.modificables != []  y  para cada ruta r:
        r existe  AND  autoconstruccion.zona_permitida(r) == True
 5. autoridad.acta existe en el log            -> review.habilitado(dir) AND
                                                   review.en_alcance(dir, verbo)
 6. ejecutor.verbo in review._EJECUTORES_CONSTRUIDOS
 7. efectos.reversible == True
 8. verificacion.pruebas_minimas != []  y  cada prueba citada existe
 9. ninguna acción del contrato cae en review._MATERIA_RESERVADA
```

Las nueve son **comprobables por código, sin criterio**. Ninguna pregunta «¿está bien
especificada?»; todas preguntan «¿está *este* campo, y apunta a algo que existe?».

**Las cuatro que importan** —y que `010` no pasa— son la **2**, la **4**, la **6** y la **8**: sin
regla determinista no hay qué construir; sin perímetro en zona no hay dónde; sin ejecutor no hay
con qué; sin prueba no hay cómo saber si salió bien.

---

## C · Regla objetiva de bloqueo

```
BLOQUEADA / DECISION_REQUIRED   si CUALQUIERA:

 - falta un campo obligatorio                        -> falta especificación
 - regla_de_transformacion == REQUIERE_INFERENCIA    -> lo decide un humano, no una regla
 - una fuente o ruta citada NO existe                -> cita inventada
 - perimetro.modificables toca zona prohibida        -> zona_permitida() == False
 - autoridad.acta no consta en el log                -> no hay permiso, hay intención
 - ejecutor.verbo no tiene ejecutor construido       -> INV-9: no se finge capacidad
 - efectos.reversible == False                       -> ADR-0003: ante la duda, roja
 - la capacidad toca materia reservada               -> D22
```

**Fail-closed y sin excepciones.** No existe bandera, constante ni configuración que convierta un
bloqueo en un permiso: eso es un acta del CEO, igual que `REVIEW_HABILITADO` y `K_ESTANCAMIENTO`.

**Y una regla de precedencia:** el bloqueo se evalúa **antes** que la implementabilidad. Una
capacidad que cumpliera las nueve condiciones de B y a la vez tocara materia reservada queda
bloqueada. La gobernanza habla primero.

---

## D · Validación con `010` — resultado correcto: **BLOQUEADA**

`010 — Asignar responsable a una necesidad`, con su especificación literal completa:
una fila de tabla (`PLAN-DE-FORMACION-AURORA.md:65`) y una frase (`:70`).

| Campo | ¿Lo tiene? | Evidencia |
|---|---|---|
| `id`, `nombre`, `estado` | **sí** | `PLAN…:65` — `010`, «Asignar responsable a una necesidad», 🟡 |
| `version` | no | — |
| `intencion` | parcial | *«reduciría la superficie del Traductor»* (`:72`) |
| `entradas` | **NO** | «necesidad» no está definida en ninguna parte del repositorio |
| `salidas` | **NO** | sin destino declarado |
| `regla_de_transformacion` | **NO** | el plan dice *«es determinista»* pero **no dice cuál es la regla**. Las dos asignaciones reales son la constante literal `responsable="programador"` (`planificacion.py:135,177`) |
| `fuentes_de_verdad` | parcial | existe `composicion.py:215 _EJECUTORES` con 4 responsables — **pero en el plano de producto** |
| `perimetro` | **NO** | cero ocurrencias de `responsable` en `entorno/control-plane/`; todo el material está en `walking-skeleton/`, donde `zona_permitida()` devuelve `False` |
| `autoridad` | **sí, parcial** | el CEO autorizó `010` para construcción; **no existe acta con perímetro** |
| `ejecutor` | **NO** | `implementar_incremento_especificado` ∉ `_EJECUTORES_CONSTRUIDOS` |
| `efectos` | **NO** | sin declarar |
| `verificacion` | **NO** | ninguna prueba del repositorio verifica `010` |
| `trazabilidad` | **NO** | el Traductor Operativo consta **pendiente** (`CHECKPOINT…:324`), no construido |

**Dispara seis reglas de bloqueo de la sección C**, cualquiera de ellas suficiente: campos
obligatorios ausentes (6, 7, 8, 13, 14), perímetro fuera de zona, y ejecutor inexistente.

**No resuelvo ninguno.** No decido qué es «necesidad», ni si `_EJECUTORES` debe ser fuente de verdad
de AURA, ni la relación necesidad→responsable, ni el perímetro, ni si se abre `walking-skeleton/`.
El contrato hace aquí su trabajo: **detecta la insuficiencia y nombra exactamente cuál es.**

---

## E · Validación con una capacidad existente — `eliminar_codigo_muerto`: **COMPLETADA**

El control necesario: si el contrato bloqueara también lo que ya funciona, sería un filtro inútil.

| Campo | Valor | Evidencia `[EJEC]` |
|---|---|---|
| `id` / `nombre` | `eliminar_codigo_muerto` | `review.TODO_LO_DELEGABLE` |
| `intencion` | retirar código sin uso del plano de desarrollo | `DEC-ORCH-2` |
| `entradas` | fichero + símbolo + forma, de `descubrimiento._muertos_en()` | fuente verificable: `fichero:linea` |
| `salidas` | fichero sin el símbolo | releído del disco |
| `regla_de_transformacion` | **determinista y única**: `es_eliminable()` decide, `quitar_simbolo()` ejecuta | `autoconstruccion.py:277,371` |
| `fuentes_de_verdad` | `es_eliminable()` es *«la única fuente de verdad sobre lo eliminable»* | docstring, `:289` |
| `perimetro` | `entorno/control-plane/` + 1 fichero exacto por acta | `_ZONA_PERMITIDA`, `_FICHEROS_AUTORIZADOS` |
| `autoridad` | acta `DEC-ORCH-2`, **registrada en el log, `seq=1`** | `review_habilitado`, alcance `["eliminar_codigo_muerto"]` |
| `ejecutor` | **existe** | `_EJECUTORES_CONSTRUIDOS`, `autoconstruccion.ejecutar()` |
| `efectos` | escribe un símbolo; **reversible** — revierte si el efecto o la verificación fallan | `:465` |
| `verificacion` | efecto releyendo el AST + batería en verde + protección `@_regla` | `_existe_simbolo()` |
| `trazabilidad` | **10 `cambio_aplicado`** con `efecto_verificado: true` y `revertido: false` | log encadenado |

**Pasa las nueve condiciones de B y no dispara ninguna de C.** Es `COMPLETADA`: no solo declarada,
sino ejecutada 10 veces con efecto verificado y registrado.

**El contrato distingue los dos casos por la misma regla, no por excepción.** La diferencia
decisiva es el campo 8: `eliminar_codigo_muerto` tiene una regla determinista escrita en un sitio;
`010` tiene la palabra «determinista» y ninguna regla.

---

## F · Cambios necesarios para adoptar el contrato — **NO REALIZADOS**

Ordenados de menor a mayor autoridad. **Ninguno ejecutado en esta misión.**

| # | Cambio | Dónde | Quién decide |
|---|---|---|---|
| **F1** | Publicar este contrato como especificación vigente | este documento | **CEO** |
| **F2** | Un evaluador `contrato.evaluar(cap) -> (estado, campos_faltantes)` que aplique B y C. **Solo lectura, sin efectos.** Es aritmética sobre campos, no una capacidad nueva | `entorno/control-plane/` (en zona) | **CEO** — es código nuevo del plano de desarrollo |
| **F3** | Que `formacion.py` adjunte el veredicto a cada oportunidad que ya emite | `formacion.py` (en zona) | **CEO** |
| **F4** | Dónde vive el contrato de cada capacidad: fichero por capacidad, o campos nuevos en el plan | decisión de formato | **CEO — `DECISION_REQUIRED`** |
| **F5** | Que una capacidad con contrato completo pueda pasar a `OPORTUNIDAD_REAL` | techo de `formacion.py` | **CEO — `DECISION_REQUIRED`.** Hoy el techo es `DECISION_REQUIRED` porque el plan dice *«ninguna capacidad se desarrolla automáticamente»*. Levantarlo **contradice el plan**: exige acta que lo enmiende |
| **F6** | Construir un ejecutor para `implementar_incremento_especificado` | `review.py` | **CEO — `DECISION_REQUIRED`.** Solo tiene sentido una vez exista **una** capacidad que pase B |

**F5 es la decisión de fondo**, y la señalo sin resolverla: el contrato puede decir «esta capacidad
es implementable», pero el plan de formación prohíbe hoy que eso se convierta en trabajo automático.
Son dos reglas del CEO que apuntan en direcciones distintas. **No las reconcilio.**

---

## G · Observación registrada, no corregida

`descubrimiento.py:29` y `:54` dicen *«las ocho piezas»*; `PIEZAS_OBLIGATORIAS` tiene **nueve**
(`estado` es la novena). La prosa quedó atrás cuando la tupla creció. No lo toqué: no bloquea nada y
corregir prosa no estaba autorizado en esta misión.
