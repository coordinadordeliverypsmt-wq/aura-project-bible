---
numero: ADR-0021
titulo: "Registro de capacidades y activacion automatica por perfil de capacidad efectiva (Capability Registry / Manager)"
estado: accepted
version: 1.1.0
fecha: 2026-07-26
fecha-resolucion: 2026-07-26
fecha-revision: 2026-07-27
decisor: "Mauricio (CEO)"
proponente: "CTO"
revision: "v1.1.0 (2026-07-27) — Revision del modelo declarativo tras la auditoria de consistencia del Registry. Aprobada por el CEO campo a campo. Elimina los campos 2 y 3, fija la semantica del 6, corrige el 8 y el §4, y clasifica cada campo superviviente como OPERATIVO o DOCUMENTAL. Ver §0."
impacta: ["ADR-0020", "ADR-0018", "ADR-0019", "ADR-0004", "ADR-0016", "ADR-0003", "P-ARQ-1", "D33", "D34", "D38", "D43", "D44", "D45", "Bible 3.1", "Bible 3.2", "Bible 3.4", "Bible 5.3"]
origen: "Directriz del CEO 2026-07-26: arquitectura completa con capacidades latentes; generalizar ADR-0020 a todo el sistema mediante un Registro de Capacidades"
reabre: "—"
supersede: "—"
superseded-por: "—"
motivo-rechazo: "—"
---

# ADR-0021 — Registro de capacidades y activacion por perfil de capacidad efectiva

## 0. Revision v1.1.0 (2026-07-27) — modelo declarativo

Esta revision **no cambia la decision** (registro autodeclarativo + Manager agnostico + activacion por
perfil): corrige el **modelo declarativo** a la luz de los invariantes **INV-1…INV-11**, congelados
*despues* de redactarse este ADR. La auditoria de consistencia del Registry demostro que varios campos
atribuian al Registry o al Manager responsabilidades que los invariantes posteriores **reasignaron** a
otros componentes, dejandolos sin consumidor legitimo.

**Causa raiz:** ADR-0021 v1.0.0 se escribio antes de que existieran los invariantes. INV-3/INV-4 movieron
la deteccion a los detectores; INV-7 movio la autoridad sobre la ejecucion a permisos/HITL/kill switch;
INV-6 endurecio la frontera dominio↔realizacion.

**Cambios, aprobados por el CEO campo a campo (2026-07-27):**

| Campo | Cambio | Motivo |
|---|---|---|
| **2** `prerequisitos` | **ELIMINADO** | Sin diferenciacion estructural ni semantica frente al campo 5: mismo tipo, mismo contexto, mismo significado operativo. Su funcion de "piso" la ejerce el campo 6. |
| **3** `deteccion` | **ELIMINADO** | **Sin consumidor posible** bajo los invariantes: el Manager puede leer el Registry pero es puro y sin E/S (INV-1); el Builder ejecuta detectores pero no puede leer el Registry (INV-4); los detectores no conocen el Registry (INV-3). Ademas nombraba a `DetectorPerfil`, derogado. |
| **6** `degradacion` | **Semantica fijada: PISO** | El texto v1.0.0 ("condicion bajo la cual el Manager la **desactiva**") contradecia la implementacion y el uso real. Se alinea el ADR al comportamiento implementado. |
| **8** `dependencias` | Suprimido "o servicios" | **INV-6**: las dependencias relacionan capacidades entre si, **nunca** capacidades con implementaciones o servicios. |
| **9** `garantias_seguridad` | Pasa a **DOCUMENTAL**; §4 corregido | La promesa de v1.0.0 §4 (el Manager no activa si no puede mantenerlas) es **incompatible con INV-1 e INV-7**: el Manager es puro y sin E/S, y la verificacion en ejecucion pertenece a permisos/HITL/kill switch. |
| **4** `comportamiento_degradado` | Pasa a **DOCUMENTAL** | Texto libre: no puede gobernar materializacion. Su valor es descriptivo y auditable. |
| **10** `autonomia_maxima` | **Se conserva provisionalmente** | Sin consumidor definido hoy. Se mantiene por **asimetria de reversibilidad**: eliminarlo y reintroducirlo obligaria a redeclarar todas las capacidades. Se revisara cuando una capacidad real demuestre necesidad. |
| **1** `contrato` | Sin cambio de definicion | Su consumidor previsto es la **composicion**; su cableado pertenece a la linea de infraestructura, no a este ADR. |

**Numeracion:** los campos supervivientes **conservan su numero original** (1, 4, 5, 6, 7, 8, 9, 10). No
se renumera: toda la documentacion, el codigo y las pruebas citan estos numeros, y renumerar produciria
una migracion masiva sin beneficio.

**Criterio que gobierna esta revision:** el objetivo **no es reducir campos por estetica**, sino que
**cada campo tenga dueno, consumidor y proposito verificable**. El Registry es un **modelo declarativo de
capacidad**, no un punto adicional de gobierno de la ejecucion.

## Contexto

**ADR-0020** establecio que la **memoria** se implementa en perfiles de capacidad detras de un contrato
unico, con seleccion automatica por hardware verificado (D27) y capacidad efectiva por pruebas (D44).
**D43** ya declaraba que ese modo de evolucionar "rige cualquier componente futuro con implementaciones
dependientes de recursos". El proyecto, ademas, **ya construye puntos de habilitacion sin construir la
capacidad entera**: bus por escenario (**ADR-0018**, E1 activo / E2 reservado) y marco de conectores
externos (**ADR-0019 / MA.4**, opt-in + transparencia + degradacion, sin un solo conector real).

**Directriz del CEO (2026-07-26).** El objetivo final no es solo que existan capacidades latentes, sino
que AURA disponga de un **Registro de Capacidades (Capability Registry)**: cada capacidad es un **modulo
autonomo** que se **auto-declara**, y un **Capability Manager** —sin conocimiento especifico de ninguna
capacidad— recorre el registro y decide cuales activar segun la **capacidad efectiva** del entorno
(D44). Este ADR generaliza ADR-0020 de la memoria a **todo el sistema**.

## Alternativas consideradas

### A. Logica de activacion dispersa (cada capacidad, o la composicion, decide por si misma)
El orquestador/composicion tendria que conocer cada capacidad y su regla de habilitacion. Contras:
acoplamiento creciente, el nucleo "sabe" de cada capacidad, anadir una capacidad toca el nucleo.
Contradice P-ARQ-4 (sustituibilidad) y D40 (la composicion ensambla, no decide). **Descartada.**

### B. Registro de capacidades autodeclarativas + Manager agnostico (elegida)
Inversion de dependencias: la capacidad declara lo que necesita; el Manager solo evalua el registro
contra la capacidad efectiva. Materializa la directriz del CEO. Por ser formalizacion de una decision ya
tomada, se omiten los 4 niveles (D3).

## Decision

### 1. Capacidad = modulo autonomo autodeclarativo

Cada capacidad del sistema es un **modulo autonomo, autocontenido, verificable y auditable** que declara
en el **Registro de Capacidades** los **ocho campos** siguientes. Cada uno tiene **dueno, consumidor y
proposito verificable**; ninguno queda sin destinatario.

**Clasificacion (v1.1.0).** Todo campo pertenece a una de tres clases, y la clase determina que se espera
de el:

- **OPERATIVO** — dato que **gobierna una decision o una materializacion**. Debe tener consumidor.
- **DOCUMENTAL** — declaracion **auditable por humanos**, sin semantica operativa. **Ningun componente
  deriva comportamiento de el**, y declararlo asi es deliberado, no una carencia.
- **PROVISIONAL** — conservado sin consumidor definido, a la espera de evidencia. Su permanencia se
  revisa; no se le atribuye funcion.

| # | Campo | Clase | Consumidor |
|---|---|---|---|
| 1 | Contrato funcional | OPERATIVO | Composicion |
| 4 | Comportamiento degradado | **DOCUMENTAL** | — (auditoria humana) |
| 5 | Criterio de promocion | OPERATIVO | Manager |
| 6 | Criterio de viabilidad reducida | OPERATIVO | Manager |
| 7 | Grado de latencia | OPERATIVO | Manager |
| 8 | Dependencias | OPERATIVO | Manager |
| 9 | Garantias de seguridad | **DOCUMENTAL** | — (auditoria humana) |
| 10 | Nivel de autonomia permitido | **PROVISIONAL** | — (pendiente de evidencia) |

**Definiciones:**

1. **Contrato funcional** *(OPERATIVO)* — la interfaz estable que ofrece cuando esta activa (P-ARQ-4).
   Identifica **que** materializar; su consumidor previsto es la composicion.

4. **Comportamiento degradado** *(DOCUMENTAL)* — descripcion de que ofrece cuando no puede activarse
   plenamente. Su valor es **auditable, no ejecutable**: ningun componente deriva comportamiento de este
   texto. La materializacion del modo reducido la realiza la composicion, gobernada por el **estado** que
   emite el Manager, no por esta descripcion. La exigencia de **degradacion limpia, nunca fallo
   silencioso** (ADR-0019, checklist 3.1 §2.3.10) sigue vigente como requisito de diseno.

5. **Criterio de promocion** *(OPERATIVO)* — regla declarativa sobre el `ActivationContext` bajo la cual
   el Manager activa la capacidad en su **nivel pleno**.

6. **Criterio de viabilidad reducida** *(OPERATIVO)* — **PISO, no techo.** Regla declarativa que expresa
   la condicion **minima bajo la cual la capacidad puede operar en modo reducido**. Semantica exacta,
   fijada en v1.1.0 y alineada con la implementacion: si se cumple el campo 5 → **ACTIVA**; si no, y se
   cumple el campo 6 → **DEGRADADA**; si ninguno → **LATENTE**. *(El nombre historico "criterio de
   degradacion" indujo a leerlo como techo — "condicion para bajar de nivel" —; esa lectura queda
   derogada.)*

7. **Grado de latencia** *(OPERATIVO)* — **activable** (implementacion ya existente tras el contrato, se
   enciende/apaga sola por perfil) o **prevista** (la arquitectura reserva su contrato y su lugar; la
   implementacion se realizara y validara cuando el hardware/datos lo permitan, ADR-0004, sin rediseno).

8. **Dependencias** *(OPERATIVO)* — **otras capacidades** de las que depende. **Nunca servicios,
   implementaciones ni tecnologias** (INV-6). El Manager las resuelve exclusivamente contra nombres
   declarados en el Registry.

9. **Garantias de seguridad a mantener** *(DOCUMENTAL)* — las que deben preservarse mientras este activa
   (gate HITL, ADR-0001, minimizacion). Son **innegociables** y su declaracion es **auditable**, pero
   **el Manager no las verifica**: hacerlo exigiria E/S y comprobacion en ejecucion, incompatibles con
   INV-1 (Manager puro) e INV-7 (la ejecucion se gobierna por permisos, HITL y kill switch, no por el
   plan). Quien las hace cumplir es el gate de permisos, con independencia del Registry. Ver §4.

10. **Nivel de autonomia permitido** *(PROVISIONAL)* — valor declarado en escala creciente: (a) solo
    observacion, (b) recomendacion, (c) ejecucion con autorizacion (HITL), (d) ejecucion automatica
    controlada, (e) ejecucion autonoma limitada, (f) ejecucion autonoma completa.

    **Estado normativo: sin consumidor.** El campo **no gobierna nada**: ningun componente lo consume, ni
    normativa ni operativamente. La funcion que la v1.0.0 le atribuia —*"el Manager decide hasta donde
    puede actuar"*— **queda derogada**: **INV-7** asigno el gobierno de la ejecucion, de forma exclusiva,
    a permisos, HITL y kill switch. Declarar un valor en este campo **no autoriza ni restringe** ninguna
    accion; la autoridad es y sigue siendo el gate de permisos (§4).

    **Motivo de su conservacion (unico registrado):** eliminarlo y reintroducirlo obligaria a **redeclarar
    todas las capacidades**, un coste asimetrico frente al de mantenerlo inerte. Se conserva **a la espera
    de evidencia arquitectonica** que justifique darle un consumidor. Este ADR **no le atribuye ninguna
    funcion futura**; si tal evidencia apareciera, exigira su propia decision.

**Campos eliminados en v1.1.0:** *prerequisitos* (antiguo 2) y *mecanismo de deteccion* (antiguo 3). Ver §0.

### 2. Capability Manager agnostico
El **Capability Manager no conoce ninguna capacidad concreta**. Recibe el `ActivationContext` —unico
contrato de entrada (INV-2)— y, recorriendo el registro: (a) **activa** las capacidades cuyo criterio de
promocion (campo 5) se cumple; (b) las deja **operando en modo reducido** cuando no se cumple el 5 pero si
el criterio de viabilidad reducida (campo 6); (c) las deja **latentes** en cualquier otro caso, incluidas
las de grado *prevista* (campo 7) y aquellas cuyas dependencias (campo 8) no operan. Anadir una capacidad
nueva es **registrar un modulo**, no tocar el Manager ni el nucleo.

**Lo que el Manager NO hace** *(precision de v1.1.0)*: no ejecuta deteccion (INV-1, INV-3), no verifica
las garantias de seguridad del campo 9 —eso corresponde al gate de permisos, §4— y no gobierna la
ejecucion (INV-7).

### 3. Dos grados de latencia (ninguna capacidad es "pendiente")

| Grado | Significado | Al cambiar el hardware |
|---|---|---|
| **Latente-activable** | Implementacion ya existe tras el contrato; inactiva solo por perfil | **Activacion automatica literal** |
| **Latente-prevista** | La arquitectura reserva contrato y lugar; la implementacion se realiza+valida cuando el hardware/datos lo permiten (ADR-0004) | Se **habilita** = se construye+valida en su lugar previsto, **sin nueva arquitectura** |

Esta distincion respeta **regla 13 / D3 / D34 / D38** (no se construye ni se especula lo que no se
necesita ni puede validarse): "preparada para todas" significa que **todas tienen su lugar y su contrato
en el registro**, no que todas esten construidas y solo apagadas.

### 4. Invariante de seguridad (D33) — innegociable
Activar mas capacidades **nunca** relaja la seguridad. **La utilidad escala con el hardware; la seguridad,
jamas** (ADR-0016 / D33). Encender Home Assistant no salta el gate HITL; encender vision no elude
ADR-0001/minimizacion. Por mucha capacidad efectiva que tenga el hardware, una accion de lista roja
**siempre** requiere confirmacion humana (P-ARQ-1 / ADR-0003 / Bible 5.3).

**Quien hace cumplir esta garantia** *(correccion de v1.1.0)*. La version 1.0.0 afirmaba que *"el Manager
no activa una capacidad si sus garantias no pueden mantenerse"*. **Esa afirmacion queda derogada**: es
incompatible con **INV-1** (el Manager es una funcion pura, sin E/S, y no puede comprobar el estado del
sistema) y con **INV-7** (la ejecucion se gobierna **exclusivamente** por permisos, HITL y kill switch,
nunca por el plan).

La seguridad **no depende del Registry ni del plan, y esa independencia es deliberada**: el gate de
permisos actua sobre **toda** accion, con independencia de que la capacidad este activa, degradada o de
que exista siquiera en el registro. Un Registry mal declarado **no puede** relajar la seguridad, porque no
participa en ella. El campo 9 declara **que debe preservarse** —informacion auditable y exigible en
revision—, no un mecanismo de verificacion automatica.

El campo 10 **no participa en esta garantia**: carece de consumidor y no gobierna nada (§1). Con
independencia de lo que declare, la autonomia efectiva de cualquier accion la determina el gate de
permisos.

### 5. Alcance — todo el sistema
Aplica a **toda** capacidad, no solo a la memoria: **IA local, memoria, modelos de inferencia, voz,
vision, Home Assistant, automatizaciones, agentes, conectores externos, avatar y cualquier capacidad
futura**. La memoria (ADR-0020) pasa a ser **una capacidad mas del registro**; ADR-0018 y ADR-0019 son
**instancias** del patron.

### 6. Principio de evolucion (formaliza D45)
AURA **nunca cambia de arquitectura** al mejorar el hardware; **solo incrementa el numero de capacidades
que puede ejercer**. Por tanto: **nunca** ediciones Lite/Pro/Enterprise; **nunca** un "AURA 2"; **nunca**
migraciones manuales entre perfiles; el usuario **instala AURA una sola vez** y **jamas elige perfiles,
ediciones o versiones**. AURA detecta el entorno, determina el perfil efectivo (D44) y **se reorganiza
sola**, habilitando o deshabilitando capacidades de forma **transparente, reversible y sin perdida de
memoria, configuracion, historial ni compatibilidad**. **Objetivo final:** al conectar AURA a un equipo
mas potente, este simplemente **"despierta"** capacidades que la arquitectura **ya tenia previstas** —no
aparece un proyecto distinto ni una nueva version—.

### 7. Crecer y retroceder: evolucion simetrica sin perdida
La evolucion **no es solo "activar mas"**. Toda capacidad debe poder **crecer y tambien retroceder
automaticamente** —promocion (campo 5) y degradacion (campo 6)— **sin perdida de informacion ni de
coherencia del sistema**. Si el hardware disminuye o cambia el contexto, el Manager **degrada
elegantemente** (usando el comportamiento degradado del campo 4), conservando memoria, configuracion e
historial y preservando el contrato de datos (ADR-0020). La reversibilidad es una **propiedad de primera
clase**, no un caso excepcional: un portatil modesto → un equipo potente → de vuelta al modesto debe
recorrer ese camino sin que el usuario pierda nada ni intervenga.

### 8. Relacion con los invariantes INV-1…INV-11 *(v1.1.0)*

Los invariantes se congelaron **despues** de la v1.0.0 de este ADR y son la **referencia normativa
vigente** del modelo de activacion. Esta seccion fija como se relaciona cada uno con el modelo declarativo,
para que ninguna declaracion futura vuelva a atribuir a un campo una funcion que un invariante asigno a
otro componente.

| Invariante | Efecto sobre el modelo declarativo |
|---|---|
| **INV-1** Manager puro | El Manager **solo interpreta reglas declarativas** (campos 5, 6, 7, 8). No ejecuta sondas ni verifica garantias: por eso el antiguo campo 3 se elimina y el campo 9 es documental. |
| **INV-2** Contexto, unico contrato de entrada | Las reglas de los campos 5 y 6 **solo pueden consultar** metricas verificadas y nombres de capacidades soportadas. Ninguna puede referirse a tecnologia. |
| **INV-3** Detectores por ambito | La deteccion pertenece **integramente** a los detectores. El Registry no la describe ni la nombra (eliminacion del campo 3). |
| **INV-4** Builder ensambla, no decide | El Builder **no puede leer el Registry**: ningun campo puede estar destinado a ser consumido por el (razon estructural de la eliminacion del campo 3). |
| **INV-5** Registry declarativo, fuente unica | Todos los campos son **datos pasivos y serializables**. Ninguno contiene funciones ni logica; ninguno duplica informacion que ya posea otro artefacto. |
| **INV-6** Dominio ≠ realizacion | La capacidad **no enumera acciones ni implementaciones**; el campo 8 relaciona **capacidades entre si**, nunca servicios (correccion de v1.1.0). |
| **INV-7** Punto unico de interpretacion | La salida del Manager se consume **una sola vez**, en la composicion. Por eso el consumidor del campo 1 es la composicion, y por eso el campo 10 **no puede** gobernar la ejecucion. |
| **INV-8** La autonomia nunca escala | Ningun campo del Registry puede elevar la autonomia. El campo 10 es un **valor declarado sin consumidor** (§1); la autoridad es el gate HITL. |
| **INV-9** Una prevista no se enciende | El campo 7 tiene **precedencia sobre los campos 5 y 6**: una capacidad `prevista` permanece latente aunque su criterio de promocion se cumpla. |
| **INV-10** Dependencias en cascada | El campo 8 se resuelve hasta punto fijo: una capacidad no opera si alguna de sus dependencias no opera. |
| **INV-11** Reversibilidad sin perdida | La transicion entre los estados que producen los campos 5 y 6 es **reversible y sin perdida** de memoria, configuracion, historial ni compatibilidad. |

**Regla de precedencia ante conflicto:** si este ADR y los invariantes discrepasen, **prevalecen los
invariantes**; esta revision existe precisamente para eliminar las discrepancias detectadas.

## Consecuencias

**Positivas:** un solo proyecto/codigo/arquitectura para todo el rango de hardware; el nucleo no crece al
anadir capacidades (registro + Manager agnostico); la evolucion es aditiva y **simetrica** (crece y
retrocede sin perdida); la seguridad y la autonomia quedan **declaradas de forma auditable** en cada
capacidad, y su **cumplimiento** corresponde al gate de permisos, con independencia del Registry (§4).
**Negativas:** hay que mantener y probar el registro y el Manager, y cada capacidad debe declarar sus
**ocho campos** con rigor; los **criterios de promocion y de viabilidad reducida por capacidad** deben
definirse con pruebas reales (dependiente de hardware, fase posterior). **Riesgos aceptados:** la
calibracion de los umbrales D44 por capacidad es la incognita hardware-sensible, a medir al reanudar; el
registro debe ser la **fuente unica de la declaracion** de capacidades (D41); y el campo 10 permanece
**sin consumidor** hasta que una capacidad real demuestre su necesidad (§1).

## Impacto (acta D11 — obligatorio)

| Dimensión | Impacto |
|---|---|
| Seguridad | Neutro/invariante: la seguridad no escala con el hardware (D33). Cada capacidad **declara** sus garantias (campo 9, documental); **quien las hace cumplir es el gate de permisos**, con independencia del Registry y del plan (§4, INV-7). El campo 10 no gobierna nada (§1). |
| Privacidad | Neutro/positivo: capacidades locales (ADR-0001); activar mas no crea canales de fuga; conectores externos siguen ADR-0019. |
| Modularidad | Muy positivo: capacidades como modulos autonomos tras contrato (P-ARQ-4); Manager agnostico; nucleo estable (D40). |
| Costo | Positivo: un solo codigo, sin ramas/ediciones; se activa solo lo que el hardware justifica (D26, regla 13). |
| Experiencia de usuario | Positivo: instalar una vez; mas hardware = mas capacidad, sin intervencion ni migracion. |
| Mantenimiento futuro | Requiere mantener registro + Manager y probar activacion; a cambio, anadir capacidades no toca el nucleo. |

## Trazabilidad

**Generaliza ADR-0020** (memoria por perfiles) a todo el sistema y se convierte en **uno de los pilares
fundamentales de la arquitectura de AURA** (ya no es un ADR de memoria ni de hardware). Convierte
**ADR-0018** y **ADR-0019** en instancias del patron. Se apoya en **ADR-0004** (evolucion sin rediseno,
interfaces estables), **P-ARQ-4** (sustituibilidad), **ADR-0016 / D33** (seguridad invariante, utilidad
escalable), **P-ARQ-1 / ADR-0003 / Bible 5.3** (HITL: unica autoridad sobre la autonomia efectiva), **D27**
(hardware verificado), **D43** (evolucion por capacidades), **D44** (capacidad efectiva por pruebas),
**D41** (fuente unica: el registro) y **regla 13 / D3 / D34 / D38** (no construir/especular de mas: de
ahi los dos grados de latencia). Registra los principios permanentes **D45** y **D46**. La **Bible** quedo
actualizada (3.1 P-ARQ-9 y §2.4; ecos en 3.2/3.4). **Implementacion:** el mecanismo (Capability
Registry/Manager) es **determinista** y se **construyo sin hardware** en **C1** (TDD + mutacion + Quality
Gate). Lo que **si** depende de hardware —y por tanto permanece latente-prevista— es la **calibracion** de
los umbrales D44 por capacidad y la implementacion/validacion de capacidades **probabilisticas** o ligadas
a **dispositivos/datos reales** (D34/D44). Coherente con **D46**: ninguna limitacion de hardware justifica
dejar la **arquitectura** pendiente.
