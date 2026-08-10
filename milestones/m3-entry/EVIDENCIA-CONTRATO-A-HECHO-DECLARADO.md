# Evidencia de contrato — `HECHO_DECLARADO` (fase previa a implementación)

**Fecha:** 2026-08-09 · **Estado:** propuesto, **pendiente de aprobación explícita del CEO**
**Regla que lo obliga:** regla 6 del acta del CEO — *la ampliación debe quedar documentada
formalmente en Bible 4.4 §1 y en los contratos afectados*.

**NO se ha modificado ningún componente funcional.** Ni `_clasificar`, ni `senales.py`, ni
`ModeloUsuario`, ni ningún otro. Este documento es sólo la propuesta de contrato.

---

## 1 · Texto propuesto para Bible 4.4 §1

**Fichero:** `docs/libro-04-cognicion/4.4-aprendizaje-continuo-personalizacion.md`

**Hoy dice (líneas 32-35, literal):**

```markdown
## 1. Señales de aprendizaje

- **Explícitas:** correcciones, preferencias declaradas, feedback directo ("no me gusta que…").
- **Implícitas:** patrones de uso, temas recurrentes, aceptación o rechazo de sugerencias — observados en **datos del propio usuario** (ADR-0001), nunca de terceros (2.4 §5/§6).
```

**Texto propuesto** (el cambio es la tercera línea; el resto se conserva palabra por palabra):

```markdown
## 1. Señales de aprendizaje

- **Explícitas:** correcciones, preferencias declaradas, feedback directo ("no me gusta que…"), **hechos declarados sobre uno mismo** ("me llamo Mauricio", "trabajo en logística").
- **Implícitas:** patrones de uso, temas recurrentes, aceptación o rechazo de sugerencias — observados en **datos del propio usuario** (ADR-0001), nunca de terceros (2.4 §5/§6).

**Por qué un hecho declarado no es una preferencia** (CEO, 2026-08-09). Un nombre o una ocupación no
expresan *gusto* sino *identidad o circunstancia*: son verdaderos o falsos, no preferidos. Registrarlos
bajo `preferencia declarada` etiquetaría mal el dato **de forma permanente**, y §2 exige que la
procedencia viaje con él desde el primer registro — corregirlo después obligaría a migrar historial
real del usuario. La distinción no añade capacidad: **añade veracidad al registro**.

**Sigue sin haber inferencia.** Un hecho declarado se captura porque el usuario lo dijo, no porque el
sistema lo deduzca. Deducir sigue siendo M3.2.
```

**Lo que este cambio NO hace:** no toca las implícitas, no toca §2 (modelo del usuario), no toca §3
(personalización sin reentrenamiento), no habilita inferencia, no admite datos de terceros.

---

## 2 · Contratos afectados — inventario verificado `[LECT]`

| # | Artefacto | Qué cambia | Riesgo |
|---|---|---|---|
| C1 | `core/senales.py` · `ClaseSenal` | **+1 valor**: `HECHO_DECLARADO = "hecho_declarado"` | Enum abierto; ninguna prueba fija su tamaño |
| C2 | `core/senales.py` · `_EXPLICITAS` | **+1 miembro**. Hace que `Senal.declarada` sea `True` | **Regla 4 del CEO**: la procedencia queda `declarada` desde el primer registro |
| C3 | `core/almacen_senales.py` · `_PROCEDIMENTALES` | **NO cambia** | Al no estar, `tipo_de_memoria()` devuelve `"semantica"`: exactamente donde debe ir |
| C4 | `core/modelo_usuario.py` · `_TIPOS` | **NO cambia** | Ya es `("semantica","procedimental")` |
| C5 | `conectores/conversacion.py` · `_clasificar` | **+1 rama** y su tabla de patrones | Es el único punto donde se decide promover |
| C6 | `core/orchestrator.py` | **+1 superficie** de recuperación por intención | Va **antes** de la puerta de memoria, **sin tocarla** |
| C7 | **Bible 4.4 §1** | §1 arriba | **Requiere el acta del CEO, ya concedida** |

**El hallazgo que importa (C1):** ninguna prueba del repositorio fija hoy el número ni la lista de
clases de señal. Verificado: no existe `len(ClaseSenal)` ni equivalente. Es decir, **hoy el enum
podría divergir de la Bible sin que nada lo detecte** — el patrón «declarado ≠ real» que este
proyecto ha pagado nueve veces, listo para repetirse.

**Por eso la ampliación debe traer su propio contrato ejecutable (P1 abajo).** Sin él, cumpliríamos
la regla 6 escribiendo un documento que nada obliga a respetar.

---

## 3 · Compatibilidad con procedencia, refutación y borrado — regla 5 `[LECT]`

**Es automática, y conviene entender por qué**: `ModeloUsuario.ver`, `.borrar` y `.refutar` filtran
por `i["kind"] in _TIPOS`, **nunca por clase de señal**. Un hecho declarado se escribe como memoria
`semantica` (C3), luego las tres operaciones lo alcanzan sin modificar una línea de
`modelo_usuario.py`.

La procedencia también: `AlmacenSenales` escribe `origen` a partir de `Senal.declarada`, que será
`True` gracias a C2.

**Esto no se da por bueno por lectura**: P5 y P6 lo verifican ejecutando.

---

## 4 · Matriz de pruebas prevista

**Ninguna existe todavía.** Todas deben fallar antes de la implementación (RED) y pasar después.

| # | Qué demuestra | Regla del CEO | Falla hoy porque |
|---|---|---|---|
| **P1** | **El enum coincide con Bible 4.4 §1**: las 4 explícitas y las 3 implícitas declaradas, congeladas | 6 | `HECHO_DECLARADO` no existe |
| P2 | `Mi nombre es Mauricio` → señal `HECHO_DECLARADO`, no `PREFERENCIA_DECLARADA` | 1, 2 | `_clasificar` devuelve `None` |
| P3 | La señal recorre la cadena y aterriza en memoria **`semantica`** | 3 | no hay señal |
| P4 | `Senal.declarada is True` y la entrada queda con `origen == "declarada"` | 4 | ídem |
| P5 | Un hecho declarado se **refuta** por la ruta existente | 5 | ídem |
| P6 | Un hecho declarado se **borra** por la ruta existente | 5 | ídem |
| P7 | Cuatro cadenas completas: nombre · ocupación · proyecto · preferencia | 7, 8 | ídem |
| P8 | **Persistencia entre procesos**: proceso nuevo, misma `AURA_DATOS`, el hecho sigue | 8 | ídem |
| **P9** | **La respuesta NO puede venir del recall episódico** (§5) | 9 | — |
| P10 | `Hoy estoy cansado` **no** se promueve; queda episódica | — | — |
| P11 | Usuario nuevo: `¿Cómo me llamo?` declara que no lo sabe, **no inventa** (INV-9) | — | — |
| P12 | `mi hermana se llama Ana` **no** se captura (ALERTA-002) | — | — |
| P13 | Las **24 negativas** de ADR-0014 siguen `core` con **0** llamadas al LLM | 10 | — |

**Mutantes previstos** (regla 10): el detector no reconoce · se promueve cualquier frase · se captura
a un tercero · **la recuperación responde desde el recall episódico** (el irrenunciable) · el hecho no
sobrevive al reinicio · la clase se registra como `PREFERENCIA_DECLARADA` · `HECHO_DECLARADO` cae en
`_PROCEDIMENTALES` y deja de ser alcanzable por `ModeloUsuario`.

---

## 5 · Cómo se impide que el criterio pase por coincidencia léxica — regla 9

**El problema, medido `[EJEC]`:** hoy, **sin ningún incremento**, `¿Qué recuerdas de mi trabajo?`
responde *«Según lo que recuerdo: usuario dijo: Trabajo en logística»*. Lo hace por solape léxico
entre `mi trabajo` y `Trabajo en logística`. **Una prueba que sólo compruebe que la respuesta
contiene «logística» PASARÍA HOY** y no demostraría nada.

Tres candados, y hacen falta los tres:

**(a) Aserción sobre el ORIGEN, no sobre el contenido.** La respuesta debe venir con
`provider == "core"` y coincidir con el texto exacto que produce la superficie del Modelo de Usuario.
El recall episódico devuelve `provider == "mock"`/LLM y el prefijo `«Según lo que recuerdo: usuario
dijo:»`. **Son distinguibles sin ambigüedad.**

**(b) Prueba con la memoria episódica NEUTRALIZADA.** Se declara el hecho, se **borran las entradas
episódicas** del almacén, y se consulta. Si la respuesta sigue apareciendo, procede del Modelo de
Usuario por construcción. Es la prueba que mata la trampa de raíz.

**(c) Consulta con CERO solape léxico.** `¿Cómo me llamo?` no comparte ni un término con
`Mi nombre es Mauricio` — está medido: por eso hoy falla. Es el caso que ninguna coincidencia puede
resolver, y por eso es el criterio principal, no `mi trabajo`.

**Control negativo obligatorio:** una consulta cuyo hecho NO se ha declarado debe seguir declarando
la ausencia. Sin él, (a)-(c) se cumplirían con una superficie que responde siempre.

---

## 6 · Riesgos e impacto arquitectónico

| Riesgo | Mitigación |
|---|---|
| **Promoción indiscriminada**: una frase mundana se vuelve conocimiento permanente | Regla de tres condiciones (marcador **Y** sujeto **Y** atributo estable). P10 y su mutante |
| **Contaminar datos reales del CEO** | El alcance son 4 categorías (regla 7). Toda prueba con `AURA_DATOS` aislado — ya se contaminó una vez |
| **Robar frases a superficies existentes** | La superficie nueva casa por segmento completo, como Conversación General v1. P13 vigila ADR-0014 |
| **Divergencia Bible ↔ código** | P1, el contrato ejecutable que hoy no existe |
| **Etiquetado permanente erróneo** | Es la razón misma de la ampliación (§1) |
| **Ampliar el alcance por el camino** | Regla 7: nombre, ocupación, proyecto, preferencia. Nada más |

**Impacto arquitectónico real: bajo.** Un valor de enum, un miembro de conjunto, una rama de
clasificación y una superficie de lectura. **Cero componentes nuevos, cero rutas de persistencia
nuevas** (regla 3), y `ModeloUsuario` intacto.

---

## 7 · Qué se pide aprobar antes de escribir código

1. **El texto de Bible 4.4 §1** del §1, palabra por palabra.
2. **El inventario de contratos** del §2, y en particular **P1 como contrato ejecutable nuevo**.
3. **La matriz de pruebas** del §4 y los mutantes.
4. **Los tres candados** del §5 contra el paso por coincidencia léxica.
