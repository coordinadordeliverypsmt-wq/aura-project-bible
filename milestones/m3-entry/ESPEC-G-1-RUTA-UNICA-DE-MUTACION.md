# Especificación G-1 — Ruta Única de Mutación

**Estado:** diseño, **pendiente de aprobación del CEO**. **No se ha escrito código.**
**Encargo (CEO, 2026-08-03):** contrato formal de la garantía · diseño del verificador AST ·
**identificar todos los falsos positivos y negativos antes de implementar** · estrategia de migración
sin romper compatibilidad.

**Principio rector aprobado (CEO, 2026-08-03):** *toda mutación persistente del estado de AURORA,
afecte al mundo exterior o al estado interno, debe ejecutarse a través del Motor Único.*

---

## 1 · Se reutiliza un mecanismo que ya existe

El proyecto **ya tiene** una garantía de arquitectura verificada por AST y gobernada por un manifiesto:
`architecture_manifest.toml` (fuente única de verdad, D41) + `test_manifiesto_arquitectura.py`, que
**deriva** la lista del manifiesto en cada corrida en vez de duplicarla, y detecta por **AST real**
(una llamada, no un import ni un comentario).

**G-1 extiende ese mecanismo; no crea uno paralelo.** Crear un segundo verificador sería repetir
exactamente el error que D-M-8 diagnosticó: dos implementaciones del mismo control acaban divergiendo.

---

## 2 · Contrato formal de G-1

### 2.1 · Enunciado

> **G-1.** Para todo módulo `m` del paquete de producción `aura_skeleton/`, ninguna llamada a una
> **operación mutante persistente** aparece en `m` salvo que `m` figure como **autorizado** para esa
> operación en `architecture_manifest.toml`.

### 2.2 · Definiciones

**Operación mutante persistente:** toda operación cuyo efecto sobrevive al proceso. Tres familias:

| Familia | Ejemplos actuales |
|---|---|
| **F1 · Método de almacén catalogado** | `write`, `olvidar`, `marcar` (memoria); `crear`, `desactivar` (reglas) |
| **F2 · Escritura directa a disco** | `open(…, "w"/"a")`, `os.replace`, `Path.write_text`, `os.remove` |
| **F3 · Efecto externo observable** | `subprocess.run`, adaptadores, egress de red |

**Autorizado:** declarado en el manifiesto con **motivo y fecha**. La autorización es por
`(operación, módulo)`, no global.

**Motor Único:** el módulo que implementa el flujo de D-M-8. Es el único autorizado por defecto.

### 2.3 · Las tres reglas

| Regla | Qué prohíbe | Cubre |
|---|---|---|
| **R-A** | Llamar a una operación de F1 desde un módulo no autorizado | El caso de ALERTA-006 |
| **R-B** | Escritura directa a disco (F2) fuera de los módulos de persistencia declarados | Que alguien escriba a mano y esquive F1 |
| **R-C** | Que un módulo de persistencia declarado exponga un método **sin clasificar** como mutante o no-mutante | Que una operación **nueva** nazca fuera del control |

**R-C es la que da a G-1 vida útil.** Sin ella, G-1 solo protege contra las operaciones que hoy
conocemos, y un método nuevo escaparía en silencio — que es literalmente cómo nació ALERTA-006. Es el
mismo principio que el manifiesto ya aplica a los ejecutables: *«ningún ejecutable nuevo puede aparecer
sin clasificar»*.

### 2.4 · Criterio de fallo del Quality Gate

El gate falla si se viola **cualquiera** de R-A, R-B o R-C. Sin severidades ni avisos: una garantía con
grados deja de ser una garantía. El mensaje de fallo debe nombrar fichero, línea, operación y **qué
hacer** (enrutar por el Motor o solicitar autorización con motivo).

---

## 3 · Diseño del verificador AST

### 3.1 · Entrada

Sección nueva del manifiesto — **sin duplicar nada en código** (D41):

```toml
[mutaciones]
motor = "aura_skeleton/core/automatizacion.py"

# F1 — superficie mutante de cada almacén, declarada explícitamente.
[[mutaciones.almacen]]
modulo   = "aura_skeleton/modules/memory.py"
mutantes = ["write", "olvidar", "marcar"]
neutros  = ["recall", "backup", "_indexar", "_terminos_item"]   # R-C: todo def público, clasificado

# F2 — quién puede tocar el disco directamente.
persistencia_autorizada = [
  "aura_skeleton/modules/memory.py",
  "aura_skeleton/core/reglas.py",
  "aura_skeleton/observability.py",
]

# Lista blanca temporal: cada entrada con MOTIVO y FECHA. Solo puede ENCOGER (§5).
[[mutaciones.excepcion]]
modulo    = "aura_skeleton/core/orchestrator.py"
opera     = ["olvidar", "marcar"]
motivo    = "ALERTA-006 — soberanía aún no migrada al Motor Único"
desde     = "2026-08-03"
retirar_en = "D-M-8 fase F4"
```

### 3.2 · Algoritmo

```
1. Cargar manifiesto → operaciones F1, módulos de persistencia, excepciones.
2. Para cada .py de aura_skeleton/:
     árbol = ast.parse(fichero)
     R-A: por cada ast.Call con func = ast.Attribute y attr ∈ operaciones_F1:
            resolver el RECEPTOR (§3.3). Si es un almacén conocido y el módulo
            no está autorizado ni exceptuado → VIOLACIÓN.
     R-B: por cada llamada a open/os.replace/os.remove/Path.write_text con modo
            de escritura, si el módulo ∉ persistencia_autorizada → VIOLACIÓN.
3. R-C: para cada módulo de almacén declarado, listar sus `def` públicos y
     comprobar que cada uno esté en `mutantes` o en `neutros`.
     Un `def` nuevo sin clasificar → VIOLACIÓN.
4. Falla el gate si hay ≥1 violación.
```

### 3.3 · El problema central: resolver el receptor

`x.write(...)` es ambiguo: puede ser memoria, un fichero o un socket. **De esto depende que G-1 sea
utilizable o una fuente de ruido.** Estrategia por capas, de más fiable a menos:

1. **Tipado explícito** (`mem: PersistentMemory`) → resuelto con certeza. `mypy` ya corre en el gate,
   así que las anotaciones existen en gran parte del código.
2. **Construcción local visible** (`mem = PersistentMemory(...)` en el mismo ámbito) → resuelto.
3. **Atributo de instancia** (`self.memory.write(...)`) → resuelto si el `__init__` anota o construye.
4. **No resoluble** → **no se reporta como violación**; se acumula en un informe de *no resueltos*.

**Decisión de diseño explícita:** ante un receptor no resoluble, **el verificador calla**. Prefiere un
falso negativo declarado y contable a un falso positivo que bloquee el desarrollo. La cifra de no
resueltos se publica en cada corrida, y **si crece, es señal de que el código está perdiendo tipado**.

---

## 4 · Falsos positivos y falsos negativos

El CEO pidió identificarlos **antes** de implementar. Este es el apartado que decide si G-1 es viable.

### 4.1 · Falsos positivos (el verificador acusa sin motivo)

| # | Caso | Mitigación | Riesgo residual |
|---|---|---|---|
| FP-1 | **Homonimia de `write`**: `fichero.write()`, `socket.write()`, `stream.write()` | Resolución de receptor (§3.3); si no se resuelve, no se acusa | Bajo |
| FP-2 | El propio módulo de almacén llama a sus internos (`self._persist()`) | El módulo declarado es autorizado sobre sí mismo por definición | Nulo |
| FP-3 | **Tests** que construyen almacenes y llaman a `olvidar` | `tests/` excluido del ámbito, igual que ya hace el manifiesto | Nulo |
| FP-4 | Demos y arneses (`demo_*.py`, `validar_*.py`) | Ámbito = `aura_skeleton/`; los arneses se declaran como hoy | Bajo |
| FP-5 | Un wrapper legítimo que delega en el Motor | Se autoriza explícitamente con motivo | Bajo |
| FP-6 | Método homónimo en clase ajena (`Notificacion.marcar`) | Resolución de receptor por tipo | Medio — **es el FP más probable** |

**FP-6 era el riesgo principal, y está MEDIDO (§4.4): `write` hace caer la resolución al 40 %; sin él,
sube al 100 %.** Los 12 casos irresolubles son `f.write()` sobre ficheros, no llamadas a almacenes.

**Decisión que esto fuerza:** renombrar las operaciones mutantes del Motor a nombres inequívocos
(p. ej. `mutar_*`) **es condición de viabilidad**, no una mejora estética. Requiere aprobación del CEO
porque toca la superficie pública de los almacenes; sin ella, G-1 nace como fuente de ruido.

### 4.2 · Falsos negativos (el verificador calla ante una violación real)

Ordenados por peligrosidad. **Ninguno se puede eliminar por completo con análisis estático.**

| # | Caso | ¿Se mitiga? |
|---|---|---|
| **FN-1** | **Indirección dinámica**: `getattr(mem, "olvidar")()`, `op = mem.olvidar; op()` | **No** por AST. Mitigación: R-D — prohibir `getattr` con literal sobre almacenes, detectable por AST |
| **FN-2** | **Escritura por biblioteca no listada**: `shutil.move`, `json.dump(f)`, `pickle`, `sqlite3` | Parcial: la lista de F2 debe ampliarse. **Es una lista, y toda lista es incompleta** |
| FN-3 | **`subprocess`** que muta el sistema | Detectable si `subprocess` entra en F2/F3 |
| FN-4 | Un almacén **nuevo** que nadie declara en el manifiesto | R-C solo cubre los declarados. Mitigación: exigir que toda clase con `_persist`/`_anexar` esté declarada |
| FN-5 | Mutación a través de una **dependencia externa** | Fuera de alcance; el proyecto es local-first y sin claves de terceros (D24) |
| FN-6 | Receptor no resoluble (§3.3 capa 4) | **Declarado y contado**, no silencioso |

> **Declaración honesta de alcance: G-1 NO demuestra la ausencia de rutas alternativas.** Demuestra que
> **las rutas conocidas y los patrones catalogados** no aparecen fuera del Motor. Un análisis estático
> sobre un lenguaje dinámico no puede dar más. Presentarlo como prueba de imposibilidad sería
> exactamente el patrón «declarado ≠ real» que este proyecto lleva nueve repeticiones intentando cerrar.

**Lo que G-1 sí garantiza, y no es poco:** que la clase de defecto de ALERTA-006 —añadir una ruta que
muta estado esquivando el Motor, sin que nada lo note— **deja de ser silenciosa**. El coste de violarla
pasa de cero a un build roto.

### 4.4 · Viabilidad MEDIDA sobre el código actual `[EJEC]`

Prototipo del verificador ejecutado fuera del repositorio contra `aura_skeleton/`. Este apartado
convierte la principal hipótesis del diseño en un dato, y **decide una cuestión abierta**.

| Conjunto de operaciones F1 | Llamadas | Receptor resuelto | No resoluble |
|---|---|---|---|
| Con `write` incluido | 20 | 8 — **40,0 %** | 12 — **60,0 %** |
| **Solo inequívocas** (`olvidar`, `marcar`, `crear`, `desactivar`) | 4 | **4 — 100,0 %** | **0 — 0,0 %** |

**El 60 % de no resolución no venía de la técnica: venía del nombre.** Los 12 casos irresolubles son
`f.write()` sobre ficheros abiertos —`open(...) as f`—, es decir **homonimia pura** con
`PersistentMemory.write`. Ninguno es una llamada a un almacén.

> **Consecuencia de diseño, y decide FP-6:** renombrar las operaciones mutantes del Motor a nombres
> inequívocos **no es una mejora opcional, es condición de viabilidad de G-1**. Con nombres
> inequívocos la resolución de receptor es del 100 % sobre el código real; con `write` genérico, G-1
> sería ruido.

Otras cifras del mismo barrido, útiles para dimensionar R-B y FN-1:

- **32 escrituras directas a disco** (`open`, `os.replace`, `write_text`…) en el paquete → es la
  superficie que R-B debe gobernar, y confirma que R-B no es teórica.
- **3 usos de `getattr`** → superficie de FN-1 hoy: pequeña y auditable a mano, lo que hace **barata**
  la regla R-D propuesta.

### 4.3 · Garantía complementaria recomendada

Análisis estático y dinámico se cubren los huecos mutuamente. Propongo añadir a D-M-8:

> **G-2b · Prueba dinámica de kill switch universal:** con el switch armado, ejercitar **todas** las
> operaciones del catálogo y verificar que ninguna muta. Captura FN-1 y FN-2 —las indirecciones que el
> AST no ve— porque observa el **efecto**, no la sintaxis.

G-1 impide escribir la ruta; G-2b detecta que la ruta existe. Ninguna basta sola.

---

## 5 · Estrategia de migración sin romper compatibilidad

**Principio:** G-1 entra en verde **desde el primer día**, documentando el estado real como deuda
explícita. Nada se rompe; lo que hoy viola la garantía queda **declarado**, no oculto.

| Fase | Acción | Efecto |
|---|---|---|
| **M0** | Manifiesto con la lista blanca de **todas** las rutas actuales (≈15 del barrido), con motivo y fecha | G-1 verde. **La deuda pasa a ser un dato del repositorio**, no un hallazgo de auditoría |
| **M1** | Activar R-B y R-C | Impide que aparezcan rutas **nuevas**. Es el 80 % del valor, y llega antes que la migración |
| **M2** | Migrar soberanía (`olvidar`, `marcar`, cablear `corregir`) → retirar sus excepciones | La lista encoge |
| **M3** | Migrar reglas (`crear`, `desactivar`) → retirar excepciones | La lista encoge |
| **M4** | Migrar escritura episódica y señales | La lista encoge |
| **M5** | Lista blanca vacía o reducida a exenciones ratificadas por el CEO | G-1 plena |

### Regla de cierre — la que impide que la lista blanca se vuelva permanente

> **La lista blanca solo puede ENCOGER.** Añadir una entrada exige **acta del CEO**, igual que ampliar
> el alcance del MVP (D23). Una prueba comprueba que el número de excepciones **nunca crece** respecto
> al valor registrado en el manifiesto.

Sin esta regla, M0 se convertiría en el lugar donde se esconde la deuda para siempre. **Con ella, la
lista blanca es un contador de deuda que solo puede bajar** — y eso es medible en cada push.

---

## 6 · Qué tendría que demostrarse para cambiar este diseño

1. ~~**Que la resolución de receptor falla demasiado.**~~ **MEDIDO, ver §4.4** `[EJEC]`. Resuelto: no
   es un riesgo si se retira `write` del conjunto por nombre.
2. **Que R-C produce fricción insostenible**: clasificar cada método público nuevo podría resultar
   pesado. Si lo es, se acota a los módulos de almacén, no a todo el paquete.
3. **Que la homonimia obliga a renombrar** (FP-6). Si renombrar las operaciones del Motor resulta
   invasivo, habría que aceptar más no-resueltos.
4. **Que el coste en el gate es alto.** El AST sobre ~50 ficheros debería ser inmediato, pero no está
   medido `[HIPO]`.

---

## 7 · Lo que esta especificación NO incluye

- **No implementa** el verificador, el manifiesto ni la migración.
- **No corrige** ALERTA-006 en lo estructural: eso es D-M-8.
- **No decide** el renombrado de operaciones (FP-6), que se plantea para decisión.
- **No sustituye** a la revisión independiente de la contención, que sigue pendiente.
