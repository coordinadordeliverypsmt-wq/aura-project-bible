# Decision Package — D-M-8: Motor Único de Mutaciones

**Estado:** propuesta, **pendiente de aprobación del CEO**. **No se ha escrito código.**
**Encargo (CEO, 2026-08-03):** definir el contrato del Motor Único, el flujo obligatorio de toda
mutación persistente, su integración con Kill Switch / PermissionManager / HITL, la estrategia de
auditoría y reversibilidad, las garantías que protegerá el Quality Gate y el plan de migración.

**Peso de la decisión, en palabras del CEO:** *«de él dependerán todas las garantías futuras de
AURORA»*. Este documento se escribe con esa vida útil en mente, no para tapar ALERTA-006.

---

## 1 · El diagnóstico que hay que corregir, con precisión

**El motor ya existe y su contrato es correcto.** `MotorAutomatizacion.ejecutar`
(`core/automatizacion.py:98-143`) implementa `registro → dry-run → permisos → adaptador → auditoría`,
declara ser *«el único camino de ejecución de acciones del sistema»* y ya impone las tres restricciones
buenas: dry-run obligatorio, **toda** acción pasa por permisos (incluidas las verdes) y lista roja
exige confirmación **con previsualización**.

**El defecto no es la ausencia del motor: es su alcance.** El motor está acoplado a
`RegistroAdaptadores` — resuelve un *adaptador* para la acción. Las mutaciones del **estado propio de
AURA** (memoria, modelo del usuario, reglas) **no tienen adaptador**, así que quedaron fuera por
construcción, no por decisión.

De ahí que ALERTA-005 se declarara resuelta de buena fe: lo estaba **para efectos externos**. Nadie
comprobó la otra mitad.

> **La corrección conceptual de D-M-8 cabe en una frase: el Motor Único no es «el ejecutor de acciones
> sobre el mundo», es «el ejecutor de todo cambio irreversible o gobernado», tenga o no adaptador.**

---

## 2 · Contrato del Motor Único

### 2.1 · Qué entra: el concepto de *Mutación*

Toda modificación de estado persistente se expresa como una **Mutación**, con cinco campos
obligatorios:

| Campo | Significado |
|---|---|
| `operacion` | nombre canónico presente en el catálogo de `permissions.py`. **Lo no catalogado se deniega** (RN-2) |
| `args` | argumentos declarados; el ejecutor rechaza los no declarados |
| `origen` | `conversacion` · `regla` · `notificacion` · `sistema`. Nunca se infiere |
| `trace_id` | correlación con el turno |
| `sujeto` | **campo nuevo**: sobre qué recae (`usuario:<uid>`, `sistema`, `externo`) |

`sujeto` no existe hoy y es la pieza que faltaba: permite distinguir *«borrar un fichero del disco»* de
*«borrar un hecho que el usuario declaró sobre sí mismo»*, que hoy son indistinguibles para el catálogo.

### 2.2 · Qué las ejecuta: dos familias, un solo flujo

| Familia | Ejemplos | Ejecutor |
|---|---|---|
| **Efecto externo** | encender luz, borrar fichero | Adaptador (`RegistroAdaptadores`) — ya existe |
| **Estado propio** | olvidar, refutar, corregir, crear/desactivar regla, escribir memoria | **Ejecutor interno** — no existe hoy |

Ambas familias satisfacen el **mismo** contrato: `simular(op, args) → plan` y `aplicar(op, args) →
resultado`. El dry-run deja de ser privilegio de los adaptadores.

**Consecuencia deliberada, y es el corazón del DP:** el motor no necesita saber si algo toca el mundo o
la base de datos propia. Solo necesita saber que **cambia algo que importa**.

### 2.3 · Qué devuelve

Se conserva el contrato actual: estado en `{ejecutada, detenida, error}` y **nunca se informa éxito sin
resultado real del ejecutor** (ALERTA-005 punto 4). Esto corrige de paso `refutar`, que hoy narra éxito
con `n=0` porque el orquestador descarta el retorno `[EJEC]`.

---

## 3 · Flujo obligatorio de toda mutación persistente

```
0. KILL SWITCH ......... ¿parada de emergencia armada? → DETENIDA. Antes que nada.
1. CATÁLOGO ............ ¿operación clasificada?       → si no, DENEGADA (RN-2)
2. DRY-RUN ............. si altera estado: plan viable → si no, DETENIDA
3. PERMISOS ............ listas + política por sujeto
4. HITL ................ si lista roja: confirmación CON previsualización
5. EJECUTOR ............ adaptador o ejecutor interno
6. AUDITORÍA ........... registro forense reconstruible
7. RESULTADO ........... estado real; nunca éxito narrado sin efecto
```

**El paso 0 es el cambio estructural.** Hoy el kill switch vive **dentro** de `PermissionManager`
(`permissions.py:107`), de modo que solo alcanza a quien llama a `authorize`. Elevarlo a **precondición
del motor** hace que ninguna ruta pueda saltárselo sin saltarse el motor entero — que es exactamente lo
que el Quality Gate pasará a impedir (§6).

**Ningún paso es opcional ni configurable.** Un paso que se pueda desactivar deja de ser una garantía.

---

## 4 · Integración con Kill Switch, PermissionManager y HITL

### 4.1 · Kill Switch — de validación de ruta a garantía del sistema

El CEO ya lo aprobó como principio. En el diseño se traduce en dos cambios:

1. Se comprueba en el **paso 0 del motor**, no dentro de `authorize`.
2. `PermissionManager` **conserva** su comprobación. La redundancia es deliberada: defensa en
   profundidad, igual que ADR-0014 §3 mantiene el refuerzo del prompt aun teniendo la imposición
   determinista.

### 4.2 · PermissionManager — el catálogo necesita una dimensión nueva

Hoy el catálogo clasifica **por verbo** (`borrar_archivo`, `eliminar_informacion`…). El barrido mostró
dos huecos:

- **No existe entrada para *crear* información sobre la persona.** Hay `eliminar_informacion` (roja),
  pero la captura de señales escribe conocimiento sobre el usuario sin correspondencia alguna `[EJEC]`.
- **No se distingue el sujeto.** Borrar un fichero temporal y borrar un hecho clínico declarado por el
  usuario son ambos «borrar».

**Propuesta:** la política se resuelve con el par `(operacion, sujeto)`. Se añaden como mínimo
`registrar_informacion_usuario`, `olvidar_informacion_usuario`, `refutar_informacion_usuario`.

### 4.3 · HITL — y la tensión de producto, resuelta

El CEO planteó la tensión: un *«olvida esto»* que pidiera confirmación sería hostil, y ADR-0017 defiende
que el usuario mande sobre sus datos.

> **La tensión se disuelve al separar dos cosas que hoy están fundidas: pasar por el motor no es lo
> mismo que pedir confirmación.**

El motor aplica **la política**; la política puede eximir de HITL **sin eximir de nada más**. Propuesta
para la soberanía del usuario:

| Paso | ¿Aplica a «olvida esto»? |
|---|---|
| Kill switch | **Sí** |
| Catálogo | **Sí** |
| Dry-run | **Sí** — y aquí está el beneficio real: el plan dice *qué* se va a borrar |
| Permisos | **Sí** |
| **HITL** | **No** por defecto — el usuario lo está pidiendo ahora |
| Auditoría | **Sí** |
| Reversibilidad | **Sí** |

**Excepción que sí exige confirmación:** cuando el referente es **ambiguo**. Hoy `_foco` cae a
`vivas[0]` y destruye en silencio; con dry-run, el plan expone el objetivo y **la ambigüedad se
convierte en una pregunta**, no en una pérdida. Eso corrige M-01b sin volver hostil el flujo normal.

---

## 5 · Auditoría y reversibilidad

### 5.1 · Auditoría: reconstruible, no meramente existente

Hoy el borrado registra `olvidadas 1 entrada(s)` **sin `user_id`, sin contenido y con `trace_id="-"`**
`[EJEC]`: no permite reconstruir lo perdido. Toda mutación deberá registrar operación, sujeto,
`trace_id`, origen, resultado real y **identificación del objeto afectado**.

**Criterio de aceptación propuesto:** *a partir del audit log debe poder responderse «¿qué había antes
y qué hay ahora?»*. Si no se puede, la auditoría no cumple su función.

### 5.2 · Reversibilidad: append-only como invariante, no como costumbre

| Fichero | Hoy | Propuesta |
|---|---|---|
| `reglas.jsonl` | append-only también al desactivar ✔ | sin cambios — **es el modelo a imitar** |
| `audit.jsonl` | append + sellado ✔ | sin cambios |
| `memoria.json` · `write` | append ✔ | sin cambios |
| **`memoria.json` · `olvidar`** | **reescribe todo, destruye historia** | **lápida**: anexar baja lógica |
| **`memoria.json` · `marcar`** | **reescribe todo** | anexar marca |

`AlmacenReglas.desactivar` ya resuelve este problema correctamente anexando una línea `inactiva`
`[EJEC]`. **La memoria debe adoptar el patrón que las reglas ya usan**, no inventar otro.

**Matiz que el CEO debe pesar:** append-only en memoria implica que *«olvida esto»* **no borra
físicamente** del disco de inmediato. Es reversible y auditable, pero un usuario podría entender
«olvidar» como «destruir». Propuesta: baja lógica inmediata + **purga física diferida** explícita
(«olvidar del todo»), que sí sería lista roja. No lo decido aquí.

---

## 6 · Garantías que protegerá el Quality Gate

Sin esto, la clase entera de fallo reaparece: **hoy no existe ninguna prueba de ruta única**, y la e2e
de soberanía **consagra el bypass** `[EJEC]`.

| # | Garantía | Cómo se verifica |
|---|---|---|
| **G-1** | **Ninguna mutación persistente ocurre fuera del motor** | Análisis **AST** en la línea de `test_manifiesto_arquitectura.py`, que ya inspecciona quién construye `Orchestrator`: se prohíbe llamar a escritores de estado desde fuera del motor, salvo una **lista blanca explícita y revisada** |
| **G-2** | **El kill switch armado detiene TODA mutación** | Prueba parametrizada sobre **todas** las operaciones del catálogo, no solo las que pasan por `authorize` |
| **G-3** | **Ninguna operación no catalogada se ejecuta** (RN-2) | Operación inventada ⇒ denegada |
| **G-4** | **No se narra éxito sin efecto** (INV-9 / ALERTA-005 §4) | Ejecutor que devuelve 0 ⇒ el sistema **no** dice «hecho» |
| **G-5** | **Referente ambiguo no destruye** | Petición ambigua ⇒ desambiguación, nunca `vivas[0]` |
| **G-6** | **Toda mutación es reconstruible desde el audit log** | Reconstrucción del antes/después a partir del registro |
| **G-7** | **Append-only en los almacenes que lo declaran** | Tras un olvido, el fichero **no** pierde líneas |

**Mutantes obligatorios** (`mutaciones/motor-unico.toml`): quitar la comprobación de kill switch del
paso 0 · saltar el dry-run · devolver `ejecutada` sin llamar al ejecutor · hacer que `_foco` vuelva a
`vivas[0]` · reescribir el fichero en vez de anexar la lápida. **Cada uno debe morir.**

**G-1 es la garantía madre**: es la única que impide que en el futuro alguien añada una ruta nueva y
repita ALERTA-006 por décima vez.

---

## 7 · Plan de migración

Ordenado para que **el sistema esté protegido antes de ser refactorizado** — al revés se migra a ciegas.

| Fase | Contenido | Por qué en este orden |
|---|---|---|
| **F0 · Red** | Escribir G-1…G-7 **en rojo**, contra el código actual | Sin red, la migración no tiene cómo demostrarse. Documenta el estado real |
| **F1 · Contención** | Guarda de dominio en el disparador de olvido · `_foco` que no actúa ante duda · `refutar` comprueba `n` | Detiene la **destrucción silenciosa** ya. Barato y sin rediseño |
| **F2 · Kill switch universal** | Paso 0 en el motor | Cierra la violación más clara de una garantía declarada |
| **F3 · Ejecutor interno** | Contrato `simular`/`aplicar` para estado propio + catálogo con `sujeto` | El andamiaje del resto |
| **F4 · Migrar rutas** | Soberanía (borrar/refutar/**cablear `corregir`**) → reglas (crear/desactivar) → señales | De más peligrosa a menos |
| **F5 · Reversibilidad** | Lápidas en memoria; retirar la reescritura | Requiere F3 hecho |
| **F6 · Limpieza** | Corregir `test_modelo_usuario_flujo.py`, que hoy fija el bypass; retirar exenciones temporales | Cierra el círculo |

**F1 podría adelantarse** si el CEO quiere detener la destrucción de datos antes de aprobar el resto:
son tres cambios acotados y no comprometen el diseño. **Lo señalo porque el defecto está vivo.**

**Deuda que la migración debe absorber, no dejar atrás:** `ModeloUsuario.corregir` está construido y
**no cableado** `[EJEC]`, y `CentroNotificaciones.cerrar_sesion` —de la que depende ALERTA-002— tampoco
tiene llamador. Migrar sin cablearlas repetiría el patrón que originó todo esto.

---

## 8 · Retorno sobre Tokens

- **Menos intervención humana:** G-1 convierte en fallo de build lo que hoy exige que alguien sospeche y
  audite a mano. Esta sesión consumió tres investigaciones completas para encontrar lo que una prueba
  AST detectaría en cada push.
- **Menor consumo de contexto:** un punto único de mutación es un punto único que leer. Hoy responder
  «¿qué puede cambiar mi estado?» exige recorrer 4 ficheros y 15 rutas.
- **Reutilización:** el contrato `simular`/`aplicar` sirve para **cualquier** almacén futuro, incluido
  el que N2 necesite.
- **Para AURORA:** es la diferencia entre un sistema que se puede extender con seguridad y uno donde
  cada capacidad nueva puede abrir una ruta no gobernada. **Sin G-1, la autonomía de desarrollo es
  peligrosa**: un agente que añade una capacidad puede añadir un bypass sin que nada lo detecte.

---

## 9 · Qué tendría que demostrarse para cambiar esta decisión

1. **Que el dry-run no es expresable para el estado propio.** Es el supuesto técnico más fuerte del
   diseño. `[HIPO]` — creo que sí lo es (un plan de olvido es «voy a dar de baja estas N entradas»),
   pero no lo he prototipado.
2. **Que el coste por turno se vuelve inaceptable.** Cada mutación añadiría catálogo + dry-run +
   permisos. No medido `[HIPO]`.
3. **Que la soberanía exige exención total**, no solo de HITL. Cambiaría §4.3. Decisión de producto.
4. **Que G-1 no es verificable por AST** sin falsos positivos que bloqueen el desarrollo. Es el riesgo
   de implementación de la garantía madre; si se confirma, habría que buscar otro mecanismo —pero no
   renunciar a la garantía.

---

## 10 · Lo que este DP NO incluye

- **No implementa nada.** Ni motor, ni pruebas, ni la contención de F1.
- **No corrige ALERTA-006**: eso es el paso siguiente, ya ordenado por el CEO.
- **No decide D-M-7 ni D-M-2**, que se retomarán sobre esta arquitectura.
- **No propone** ampliar el alcance funcional del MVP (D23).
- **No resuelve** si «olvidar» debe purgar físicamente (§5.2): queda planteado para decisión.
