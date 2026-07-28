---
documento: "B1 — Analisis del defecto: el fallo del detector de hardware aborta el arranque"
fecha: 2026-07-27
autor: "CTO"
encargo: "CEO — analizar B1 antes de autorizar cualquier cambio en codigo (analisis del defecto, evidencia, causa raiz, alcance, estrategia, pruebas RED, validacion de mutacion, riesgos de regresion)"
estado: "EJECUTADO Y CERRADO. Autorizado por el CEO el 2026-07-27 con Gate A-0 previo. Quality Gate PASS (380 passed / 3 skipped)."
base: "main @ 395da8e (origin/main sincronizada) — Quality Gate PASS (366 passed / 3 skipped)"
clasificacion: "DEFECTO FUNCIONAL (incumplimiento de INV-4). No es deuda de diseno: la norma es correcta, el codigo no la implementa."
---

# B1 — El fallo del detector de hardware aborta el arranque

## 1. Analisis del defecto

**INV-4 (congelado)** exige del `ActivationContextBuilder`:

> *"Aisla el fallo de **un detector** y **registra** el incidente."*

El enunciado no distingue familias de detector. El codigo si: en
`walking-skeleton/aura_skeleton/core/activation_context_builder.py`, el `try/except` protege
**unicamente** el bucle de detectores de entorno; la llamada `self._hardware.detectar()` vive **fuera**
del bloque protegido, dentro de la expresion de retorno (linea 47).

Consecuencia observable, **asimetrica e invertida respecto a la gravedad real**:

| Detector que falla | Comportamiento actual | Conforme a INV-4 |
|---|---|---|
| Un detector de **entorno** | No contribuye · los demas siguen · incidente registrado · el contexto se construye | **Si** |
| El detector de **hardware** | La excepcion **se propaga**: no hay contexto, no hay plan, no hay sistema · **ningun** incidente registrado · se **pierde** el trabajo ya hecho por los detectores de entorno | **No** |

### Alcance del dano cuando se manifieste

La excepcion no encuentra ningun manejador en toda la cadena de arranque:

```
DetectorHardware.detectar()  ->  ActivationContextBuilder.construir()  ->  componer()  ->  main()
```

`componer()` no la captura (`composicion.py:192`) y `__main__.main()` tampoco (`__main__.py:65`,
sin `try`). El proceso termina con traza. **AURA no arranca.**

### Por que hoy no se observa (y por que eso no lo hace menos grave)

El unico `DetectorHardware` que existe es `_PerfilInyectado` (`composicion.py:50`), cableado de arranque
que devuelve un valor ya calculado: **no hace E/S y no puede fallar**. El defecto es por tanto **latente**:
esta inactivo hasta que exista el detector real de D44 —el que **mide** capacidad efectiva con pruebas
reales, con E/S, dependencias del sistema y hardware que puede no responder—, que es exactamente el
componente que **si** puede fallar.

Dicho de otro modo: el defecto esta programado para manifestarse **el primer dia que AURA mida hardware
de verdad**, y su efecto en ese momento es el maximo posible (no arrancar).

### Contradiccion con el principio permanente del proyecto

El principio de **capacidad latente** (CEO) sostiene que AURA debe permanecer funcional dentro de las
capacidades del equipo disponible, y que la evolucion por hardware es automatica y sin perdida.
Un sistema que **no arranca porque no consigue medirse a si mismo** invierte ese principio: convierte una
condicion del entorno —degradable— en una parada total. INV-11 (reversibilidad sin perdida) e INV-9
(una prevista no se enciende) describen un sistema que **siempre opera al nivel que puede**; el codigo
actual admite un estado que ninguno de los once invariantes contempla: **no operar en absoluto**.

---

## 2. Evidencia

Toda la evidencia siguiente es **ejecucion real** sobre `main @ 395da8e`, no razonamiento.

### E1 — Reproduccion del defecto (dos detectores, mismo fallo, resultados opuestos)

```
=== CASO 1: falla un detector de ENTORNO (comportamiento esperado) ===
  [WARN ] capability-builder detector de entorno sin respuesta: sonda de entorno no disponible
  -> contexto CONSTRUIDO: frozenset({'hogar'}) {'ram_mb': 16000}
  -> incidente registrado: True

=== CASO 2: falla el detector de HARDWARE (defecto B1) ===
  -> EXCEPCION PROPAGADA: RuntimeError : sonda de hardware no disponible
  -> incidente de hardware registrado: False
  -> los detectores de entorno SI se ejecutaron y su resultado se PIERDE (nunca llega al contexto)
```

Tres hechos verificados, no inferidos:
- **E1.a** — la excepcion **se propaga** fuera de `construir()`;
- **E1.b** — **no** queda registro del incidente (descarte silencioso, ademas de fatal);
- **E1.c** — los detectores de entorno **ya se habian ejecutado**: su resultado se calcula y se tira.

### E2 — No existe manejador en la cadena de arranque

`grep` sobre el arbol: la unica llamada a `.detectar()` en todo el repositorio es la del Builder
(`activation_context_builder.py:47`). `componer()` la invoca sin proteccion y `main()` invoca `componer()`
sin proteccion. **La excepcion llega al interprete.**

### E3 — El fallback correcto ya produce degradacion limpia (el modelo aguanta)

Plan real del `CapabilityManager` con el catalogo actual:

```
perfil VACIO (fallo de deteccion)      -> degradada | criterio de degradacion cumplido: opera en modo reducido
perfil modesto ram=2000                -> degradada | criterio de degradacion cumplido: opera en modo reducido
perfil amplio ram=16000                -> activa    | criterio de promocion cumplido
```

Un `PerfilHardware` vacio **no rompe nada**: ninguna metrica alcanza un umbral de promocion, y memoria cae
a su **piso** (campo 6 = N1 viable en cualquier equipo, ADR-0021 v1.1.0). Es decir: **el modelo declarativo
ya sabe comportarse ante la ausencia de metricas**; lo unico que falta es dejar que esa ausencia llegue al
Manager en lugar de matar el proceso antes.

### E4 — La documentacion ya afirma lo que el codigo no cumple

El docstring del propio Builder (lineas 19-21) declara: *"Un detector que falla no contribuye, **no
interrumpe a los demas** y **no aborta el arranque**"*. El documento de cierre del modelo describe la
Etapa 3 como *"con aislamiento de fallos y registro"*. **Ambas afirmaciones son falsas para el detector de
hardware.** No hay que cambiar la norma: hay que hacer que el codigo la cumpla.

---

## 3. Causa raiz

**Causa raiz tecnica.** La deteccion de hardware **no esta dentro del bloque protegido** porque se escribio
como argumento de la expresion de construccion del contexto:

```python
        for detector in self._entorno:
            try:                                   # <- proteccion aplicada al BUCLE
                soportadas |= set(detector.capacidades_soportadas())
            except Exception as e:
                obs.log("WARN", "capability-builder", f"detector de entorno sin respuesta: {e}", "-")
        return ActivationContext(
            hardware=self._hardware.detectar(),     # <- FUERA de toda proteccion
            capacidades_soportadas=frozenset(soportadas),
        )
```

**Causa raiz del proceso (la importante).** El requisito de aislamiento se implemento **donde la mecanica lo
sugeria** —el bucle, donde varios detectores compiten— y no **donde la norma lo exigia** —cada detector, sea
de la familia que sea—. El docstring generalizo a *"un detector"* mientras el codigo cubria solo una familia.

Lo que permitio que sobreviviera: **ninguna prueba ejercita el camino de fallo del detector de hardware**.
En `tests/unit/test_activation_context_builder.py` el doble de fallo es `_EntornoDoble(..., falla=True)`;
`_HardwareDoble` **no tiene modo de fallo**. La propiedad estaba documentada y nunca ejercitada.

**Trazabilidad.** Introducido en `23c7164` *(Etapa 3: ActivationContextBuilder + Protocols de detector)*, el
unico commit que ha tocado el fichero. No es una regresion posterior: nacio asi.

**Conclusion:** B1 no revela un error del modelo. INV-4 es correcto, suficiente y no ambiguo. B1 es un
**incumplimiento de implementacion** — el caso mas limpio posible: **no requiere modificar ninguna norma**.

---

## 4. Alcance exacto

### Se modifica

| Fichero | Cambio | Naturaleza |
|---|---|---|
| `core/activation_context_builder.py` | Extender el aislamiento al detector de hardware (~5 lineas) + 1 linea de docstring | Correccion de defecto |
| `tests/unit/test_activation_context_builder.py` | 4 pruebas nuevas + modo de fallo en `_HardwareDoble` | Prueba |
| `tests/integration/test_arranque_sin_metricas.py` *(nuevo)* | 1 prueba de cadena Builder -> Manager | Prueba |

### NO se toca (frontera dura de este trabajo)

- `capability_manager.py`, `capability_registry.py`, `catalogo_capacidades.py` — **ninguna linea**.
- `capacidades.py` — `ActivationContext` y `PerfilHardware` conservan tipo, campos y contrato.
- `detectores.py` — los Protocols no cambian: un detector **no** adquiere obligacion de no fallar.
- `composicion.py` — **ninguna linea**. El camino de arranque real es identico.
- ADR-0021, INV-1..INV-11, CV-1..CV-3, Bible — **sin cambios normativos**.
- Deudas D-1, D-4, B3, D-2 — **fuera de alcance**, permanecen registradas.

### Invariantes de comportamiento del cambio

1. **API publica sin cambios**: misma firma, mismo tipo de retorno, mismos tipos de argumento.
2. **Comportamiento observable actual sin cambios**: el unico detector real (`_PerfilInyectado`) no falla,
   luego el arranque produce exactamente el mismo plan y el mismo nivel de memoria.
3. **Ningun cambio requiere hardware para validarse** — enteramente verificable hoy, coherente con la
   doctrina de congelacion selectiva.

---

## 5. Estrategia de correccion

### Alternativas evaluadas

| # | Opcion | Veredicto |
|---|---|---|
| **A** | **Aislamiento simetrico**: si el detector de hardware falla, se registra el incidente y se construye el contexto con un `PerfilHardware` **vacio** (elemento neutro: ausencia de metricas). | **ADOPTADA** |
| B | Abortar deliberadamente el arranque y documentarlo como decision. | **Rechazada.** Exigiria modificar INV-4 —congelado— sin evidencia objetiva que lo justifique, y contradice el principio de capacidad latente. |
| C | Hacer opcional el hardware (`PerfilHardware \| None` en el contexto). | **Rechazada.** Altera un contrato congelado (INV-2), obliga al Manager a interpretar la ausencia —nueva rama de decision, mas superficie de riesgo— y traslada aguas abajo un problema que se resuelve en su origen. |
| D | Capturar en `componer()` en lugar de en el Builder. | **Rechazada.** INV-4 asigna el aislamiento **al Builder**. Capturar en la composicion la convertiria en decisora (viola INV-7 y D40: la composicion ensambla, no decide). |

### Por que A no convierte al Builder en decisor

Objecion legitima: *"elegir un perfil vacio, ¿no es decidir?"*. No, y el criterio es el que ya rige la
familia de entorno: un detector de entorno que falla **contribuye el conjunto vacio**; un detector de
hardware que falla **contribuye el conjunto vacio de metricas**. Es el **elemento neutro** de la
normalizacion, exactamente la operacion que INV-4 le atribuye ("normaliza estructuralmente").

El Builder **no** aplica umbrales, **no** compara, **no** inventa valores y **no** clasifica estados: entrega
"no hay metricas" y **el Manager decide** (E3: memoria cae a su piso declarado). Se preserva literalmente lo
que el propio docstring ya prometia: *"la ausencia de esa informacion la resuelve despues el Manager por sus
reglas, no el Builder"*.

### Forma propuesta del cambio (propuesta, no aplicada)

```python
    def construir(self) -> ActivationContext:
        soportadas: set[str] = set()
        for detector in self._entorno:
            try:
                soportadas |= set(detector.capacidades_soportadas())
            except Exception as e:
                obs.log("WARN", "capability-builder", f"detector de entorno sin respuesta: {e}", "-")
        try:
            hardware = self._hardware.detectar()
        except Exception as e:   # mismo aislamiento que el entorno (INV-4): AURA arranca sin metricas
            obs.log("WARN", "capability-builder",
                    f"detector de hardware sin respuesta: {e}; se continua SIN metricas verificadas", "-")
            hardware = PerfilHardware()
        return ActivationContext(hardware=hardware, capacidades_soportadas=frozenset(soportadas))
```

Cuatro precisiones deliberadas:

1. **`except Exception`, nunca `BaseException`**: `KeyboardInterrupt` y `SystemExit` deben seguir
   terminando el proceso. Un fallo del entorno se aisla; una orden del usuario no.
2. **El perfil vacio es literalmente vacio**: no se inventan valores por defecto (nada de `ram_mb=4000`).
   Inventar una metrica **si** seria decidir, y ademas mentir al Manager.
3. **El registro nombra el ambito y la consecuencia** (`"se continua SIN metricas verificadas"`): el
   incidente no puede leerse como un aviso rutinario.
4. **El orden importa**: la deteccion de hardware va **despues** del bucle, de modo que un fallo tardio no
   pueda descartar hechos ya reunidos (E1.c).

### Decision menor que requiere criterio del CEO

**Nivel del registro: `WARN` o `ERROR`.** Recomiendo **`WARN`**, por simetria con el caso de entorno ya
existente y porque no es un error de AURA sino una condicion del entorno que AURA maneja **por diseno**.
Contraargumento honesto: su consecuencia es sistemica —todas las capacidades deciden sin metricas—, lo que
justificaria `ERROR`. Es reversible en una linea y no afecta a ninguna prueba de comportamiento.

---

## 6. Pruebas RED (se escriben antes que el codigo; **todas fallan hoy**)

| # | Prueba | Propiedad observable | Invariante |
|---|---|---|---|
| **T1** | `test_el_fallo_del_detector_de_hardware_no_aborta_el_arranque` | Con un detector de hardware que lanza, `construir()` **retorna** un `ActivationContext` en lugar de propagar. Se usa una **excepcion propia** (no `RuntimeError`) para probar que la captura es amplia. | INV-4 |
| **T2** | `test_el_fallo_del_hardware_no_descarta_los_hechos_de_entorno` | Hardware que falla + dos detectores de entorno correctos -> `capacidades_soportadas` conserva **todo** (`{voz, hogar}`). Cierra E1.c. | INV-4 |
| **T3** | `test_el_fallo_del_detector_de_hardware_queda_registrado` | Queda un registro que identifica el **ambito de hardware**. Prohibe el descarte silencioso. | INV-4 |
| **T4** | `test_sin_metricas_el_perfil_es_vacio_no_inventado` | `ctx.hardware.recursos == {}` y `ctx.hardware.pruebas == {}`. El Builder **no fabrica** metricas. | INV-1 / INV-4 |
| **T5** | `test_sin_metricas_el_sistema_degrada_pero_opera` *(integracion Builder -> Manager)* | Con hardware que falla, el Manager **produce plan** y memoria queda **DEGRADADA** (piso N1), no latente ni ausente. Prueba la degradacion limpia de extremo a extremo. | INV-11 |

Ninguna prueba existente cambia de significado: T1..T5 son **aditivas**. Las 366 actuales deben seguir
pasando sin edicion.

**Nota sobre KeyboardInterrupt.** No se anade prueba: `except Exception` excluye `BaseException` por
semantica del lenguaje, y una prueba sobre eso verificaria Python, no AURA. Queda como precision de diseno
(§5.1), no como comportamiento a fijar.

---

## 7. Validacion de mutacion

Cada degradacion se aplica **sobre la implementacion ya en verde**; si alguna sobrevive, la prueba
correspondiente no vale y hay que rehacerla antes de continuar.

| # | Degradacion aplicada al Builder | Debe fallar |
|---|---|---|
| **M1** | Eliminar el `try/except` del hardware (volver al estado actual) | T1, T2, T3, T4, T5 |
| **M2** | Capturar pero **no registrar** (`except Exception: hardware = PerfilHardware()`) | **T3** |
| **M3** | Al fallar, retornar de inmediato descartando `soportadas` | **T2** |
| **M4** | Al fallar, inventar un perfil por defecto (`PerfilHardware(recursos={"ram_mb": 4000.0})`) | **T4** |
| **M5** | Capturar solo `RuntimeError` en vez de `Exception` | **T1** (usa una excepcion propia) |
| **M6** | Mover la deteccion de hardware **antes** del bucle de entorno y propagar | T1, T2 |
| **M7** | Al fallar, devolver el perfil vacio **pero** clasificar memoria como latente (decision en el Builder) | **T5** + `test_frontera_builder` (AST) |

**M7 documenta la frontera**: cualquier intento de decidir dentro del Builder queda bloqueado por la prueba
de AST ya existente, sin necesidad de anadir nada.

---

## 8. Riesgos de regresion

| # | Riesgo | Probabilidad | Mitigacion / verificacion |
|---|---|---|---|
| **R1** | La prueba de frontera por AST rechaza el cambio | **Nula** | `PerfilHardware` **no** figura en `PROHIBIDOS` ni `capacidades` en `MODULOS_PROHIBIDOS` (verificado en `test_frontera_builder.py`). El modulo ya importa de `capacidades`. |
| **R2** | Cambia el comportamiento de arranque real | **Nula** | `_PerfilInyectado` no puede fallar: la rama nueva no se ejecuta en produccion. Lo confirman las pruebas de integracion existentes de memoria por perfil, que deben pasar **sin edicion**. |
| **R3** | `except Exception` amplio enmascara un error de programacion del detector real (p. ej. `AttributeError`), degradando en silencio | **Media** (el unico riesgo real) | Es el precio que **INV-4 ya decidio pagar**: el aislamiento es la norma. Lo que impide que sea silencioso es T3 (registro obligatorio) y la redaccion del mensaje, que nombra la consecuencia. |
| **R4** | Se rompe la inmutabilidad o el lenguaje de dominio del contexto (INV-2) | **Nula** | El perfil vacio es un valor legitimo del **mismo tipo**; ni el contrato ni los campos cambian. |
| **R5** | El cambio se cuela con alcance mayor del autorizado | **Baja** | Un unico commit, diff acotado a 1 fichero de implementacion + 2 de prueba, revisable linea a linea. |
| **R6** | mypy / ruff | **Nula** | Sin tipos nuevos; `PerfilHardware()` es construible sin argumentos. Se verifica en el Quality Gate completo antes de proponer integracion. |
| **R7** | El detector real de D44, cuando exista, **asume** que puede fallar impunemente | **Baja** | El Protocol no cambia: el aislamiento es una garantia del Builder, no un permiso para el detector. Se deja constancia en el docstring. |

**Riesgo de NO corregir:** el defecto permanece armado hasta el dia en que se implemente el detector real de
hardware —es decir, hasta el primer dia con hardware nuevo—, que es precisamente el escenario que el
principio de capacidad latente promete resolver **sin intervencion**.

---

## 9. Observacion registrada, fuera de alcance

Con la correccion aplicada, un fallo de deteccion produce un arranque **degradado y registrado**, pero el
plan resultante es indistinguible del de un equipo modesto legitimo: el `motivo` de la decision dira
*"criterio de degradacion cumplido"* en ambos casos. **Distinguir "degradado porque el equipo es modesto" de
"degradado porque no pude medir el equipo"** es una cuestion de observabilidad que **no forma parte de B1**
y que exigiria tocar el contrato del plan.

No la incluyo, no la implemento y no propongo decision sobre ella: queda **anotada** por si el CEO desea
registrarla como deuda nueva.

---

## 10. Estado de preparacion (al cerrar el analisis)

- **Analisis:** completo, con reproduccion empirica y causa raiz aislada.
- **Norma a modificar:** **ninguna**. INV-4 es correcto; el codigo no lo cumple.
- **Bloqueos:** ninguno. No requiere hardware, ni dependencias nuevas, ni decisiones de diseno abiertas.

---

# EJECUCION (autorizada por el CEO, 2026-07-27)

Autorizacion con dos precisiones: **Gate A-0 previo** —demostrar que la correccion elimina una **clase
completa** de defectos, no un caso particular— y **nivel de registro `WARN`**, con el criterio del CEO:
*"el sistema consigue recuperarse; existe un comportamiento degradado definido; el incidente queda
registrado. ERROR se reserva para cuando el sistema no pueda cumplir el contrato minimo de arranque o deba
abortar la inicializacion."* Ese criterio queda incorporado como **regla de severidad del proyecto**.

## 11. Gate A-0 — Verificacion de simetria del aislamiento

### Criterio (uniforme, derivado de los contratos)

No se comprueba "el hardware esta protegido". Se comprueba una propiedad que **no nombra ninguna familia**:

> **familia de detector** := `Protocol` declarado en `core/detectores.py`.
> Toda invocacion de un metodo de familia dentro del Builder debe ejecutarse en el cuerpo de un `try` cuyo
> manejador (a) capture `Exception` —ni desnudo, ni `BaseException`, ni un tipo mas estrecho—,
> (b) **registre** el incidente y (c) **no relance**.

(a) y (c) son *"aisla"*; (b) es *"registra"*. Es INV-4 leido literalmente.

### Evidencia — antes

```
=== 1. Familias de detector descubiertas en core/detectores.py ===
  DetectorHardware     -> metodos: ['detectar']
  DetectorEntorno      -> metodos: ['capacidades_soportadas']
=== 2. Invocaciones de detectores dentro del ActivationContextBuilder ===
   linea  metodo                   familia            aislada   manejador
      43  capacidades_soportadas   DetectorEntorno    SI        OK
      47  detectar                 DetectorHardware   NO        -- NINGUNO --
=== 3. Veredicto ===  invocaciones: 2 | aisladas: 1 | DESPROTEGIDAS: 1
  RESULTADO: SIMETRIA ROTA (el diagnostico B1 queda CONFIRMADO)
```

### Evidencia — despues

```
   linea  metodo                   familia            aislada   manejador
      53  capacidades_soportadas   DetectorEntorno    SI        OK
      60  detectar                 DetectorHardware   SI        OK
=== 3. Veredicto ===  invocaciones: 2 | aisladas: 2 | DESPROTEGIDAS: 0
  RESULTADO: SIMETRIA COMPLETA
```

### Lo que cierra la CLASE, no el caso

El `try/except` corrige **una** invocacion. Lo que elimina la clase completa es que el criterio quede
**fijado como prueba permanente** en `tests/unit/test_aislamiento_detectores.py`, y que **descubra las
familias de los `Protocol`** en lugar de consultar una lista escrita a mano. Consecuencia verificada:
anadir manana una familia `DetectorRed` con `enlace_disponible()` y olvidarse de aislarla **rompe el
Quality Gate sin editar una sola linea de prueba**. Lo demuestra
`test_el_criterio_cubre_una_familia_de_detectores_FUTURA`, sobre fuentes sinteticos con esa familia
inexistente.

Cinco pruebas mas verifican **el criterio contra si mismo** (no registra / relanza / `except` desnudo /
`BaseException` / captura estrecha) y una sexta comprueba que **acepta** un aislamiento correcto: sin ella,
un criterio que rechazase todo tambien pasaria las anteriores.

**Ampliacion de alcance declarada.** Este fichero de prueba **no estaba** en el alcance de §4: se anade por
mandato explicito del Gate A-0. Es la unica diferencia respecto al alcance aprobado, y no toca ningun
componente ni ninguna otra deuda.

## 12. Ejecucion: RED -> GREEN -> Mutacion -> Quality Gate

**RED (contra `395da8e`):** 6 fallos, exactamente los previstos —T1..T5 y el criterio general—. Las seis
pruebas de auto-verificacion del criterio y la contraprueba de equipo amplio ya pasaban: solo debe estar en
rojo lo que el defecto rompe.

**GREEN:** aislamiento simetrico con `PerfilHardware()` como elemento neutro, registro `WARN` que nombra la
consecuencia (*"se continua SIN metricas verificadas"*), deteccion **despues** del bucle y `Exception` en
lugar de `BaseException`.

**Mutacion — los 7 mutantes detectados:**

| # | Degradacion | Detectada por |
|---|---|---|
| M1 | Eliminar el aislamiento (estado previo a B1) | 6 pruebas |
| M2 | Capturar pero no registrar | T3 + criterio AST |
| M3 | Al fallar, retornar descartando lo ya reunido | T2 |
| M4 | Al fallar, inventar un perfil por defecto | T4 |
| M5 | Capturar solo `RuntimeError` | 5 pruebas + criterio AST *(tras el refuerzo, ver abajo)* |
| M6 | Detectar antes del bucle y sin proteccion | 6 pruebas |
| M7 | Decidir dentro del Builder | `test_frontera_builder` (AST) |

**Quality Gate: PASS — 380 passed / 3 skipped** (base: 366 / 3). Las 366 anteriores pasan **sin editar**.

## 13. Correcciones sobre lo previsto en el analisis (trazabilidad honesta)

1. **Hueco del criterio, hallado por la mutacion.** M5 (`except RuntimeError`) fue detectado al principio
   **solo** por las pruebas de comportamiento del hardware; el criterio estructural lo aceptaba. En una
   familia futura sin pruebas de comportamiento propias habria pasado inadvertido —es decir, la clase
   **seguia parcialmente abierta**—. Se reforzo el criterio para exigir amplitud (`Exception`), y M5 pasa a
   caer tambien por AST. **La mutacion cumplio su funcion: encontro un fallo en las pruebas, no en el codigo.**
2. **Arnes de mutacion defectuoso.** La primera ejecucion declaro "7 mutantes sobreviven". Era falso: el
   arnes filtraba la salida de pytest por `startswith("FAILED")` ignorando los codigos de color y sin mirar
   el codigo de retorno. Corregido y repetido. Se deja constancia porque un arnes que no falla nunca es
   indistinguible de una suite perfecta.
3. **M6 es redundante con M1** (misma clase de fallo con otro orden), no un invariante independiente.
4. **M7 no involucra a T5**, como anticipaba §7: lo detecta la prueba de frontera por AST ya existente.

## 14. Cierre — evidencia de que INV-4 queda satisfecho para TODA la familia de detectores

| Exigencia de INV-4 | Familia entorno | Familia hardware | Familia futura |
|---|---|---|---|
| No aborta el arranque | Ya cumplia | **Corregido** (T1, T5) | Exigido por el criterio |
| No interrumpe a los demas | Ya cumplia | **Corregido** (T2) | Exigido por el criterio |
| Registra el incidente | Ya cumplia | **Corregido** (T3) | Exigido por el criterio |
| No inventa informacion | Ya cumplia | **Corregido** (T4) | — |
| Verificado estructuralmente | **Si** | **Si** | **Si, automaticamente** |

El Gate A-0 pasa de **1 invocacion desprotegida de 2** a **0 de 2**, y la propiedad deja de depender de que
alguien recuerde aplicarla: la sostiene una prueba que se ejecuta en cada Quality Gate y que se entera sola
de las familias nuevas.

**Alcance respetado:** ninguna deuda ajena tocada —D-1, D-4, B3 y D-2 permanecen intactas y registradas—;
ninguna norma modificada; `composicion.py`, Manager, Registry y catalogo **sin una sola linea de cambio**;
el arranque real produce el mismo plan que antes.
