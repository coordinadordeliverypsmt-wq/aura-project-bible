---
documento: "Architecture Review — Modelo de activacion de capacidades (¿basta PerfilEfectivo?)"
fecha: 2026-07-27
autor: "CTO"
encargo: "CEO — decidir el modelo correcto de activacion ANTES de declarar nuevas capacidades. No presuponer que se amplia PerfilEfectivo: comparar alternativas y justificar la elegida."
estado: "CERRADA (CEO, 2026-07-27) tras el refinamiento completo. El modelo de activacion queda definido y sus fronteras registradas como Invariantes Arquitectonicos (§ final), restricciones permanentes de la arquitectura. Guia la implementacion; NO declara capacidades nuevas. El diseno no se reabre salvo evidencia nueva que contradiga los invariantes."
base: "main @ b2ca158 (Memoria validada e2e; PerfilEfectivo = recursos + pruebas)"
---

# Architecture Review — Modelo de activacion de capacidades

> **Estado: CERRADA (CEO, 2026-07-27).** Los §§1-7 son el **analisis** (evidencia, alternativas A/B/C,
> matriz de validacion, dos niveles, interfaz de dominio) que condujo al **modelo resuelto** y a los
> **Invariantes Arquitectonicos**, ambos al final del documento. Esos invariantes son **restricciones
> permanentes**: a partir de aqui la discusion es de **implementacion**; el diseno no se reabre salvo
> evidencia nueva que los contradiga.
>
> **Trazabilidad.** Un commit anterior (`8ec488f`, merge `8423462`) registro por error "opcion C + patron D
> adoptada" **antes** de completar el refinamiento; fue **retractado** (`0645016`/`4f309e6`). El cierre actual
> lo autoriza el CEO **tras** el refinamiento completo (interfaz de dominio, semantica "soportada", ambitos de
> detector, flujo con agregador y frontera anti-God-Object). El modelo resuelto se describe por sus
> **propiedades**, no por una etiqueta A/B/C.

## Objetivo

Responder, **sin premisa previa**, cuál es el modelo correcto para que el `CapabilityManager` decida el
estado de una capacidad: **(a)** el `PerfilEfectivo` actual basta, **(b)** debe ampliarse, o **(c)** conviene
**separar** recursos fisicos y estado del entorno en modelos distintos. Se comparan y se justifica una.

## 1. Evidencia — dos naturalezas de condicion de activacion

`PerfilEfectivo` hoy contiene **solo hardware**: `recursos` (p. ej. `ram_mb`) y `pruebas` (p. ej. `embed_ms`);
las condiciones declarativas tienen `Fuente ∈ {RECURSO, PRUEBA}`. Memoria (ADR-0020) encaja perfecto: su
estado **escala** con la capacidad efectiva del hardware (promueve/degrada de forma continua).

Pero las capacidades cercanas activan por otra cosa (verificado en el codigo):

| Capacidad | ¿De qué depende su activacion? | Naturaleza |
|---|---|---|
| memoria | RAM / latencia de recuperacion (D44) | **Capacidad continua** (escala) |
| inferencia local, voz | Ollama/Whisper **instalados** + hardware | Presencia + capacidad |
| home_assistant | **Servicio** HA/MQTT alcanzable + dispositivos | **Presencia discreta** (gate) |
| automatizaciones | **Adaptadores/capacidades** registrados | Presencia (dependencia) |
| conectores de contexto | **Opt-in** del usuario (config) | **Configuracion** del entorno |

**Hallazgo central.** Hay **dos tipos de condicion**, con semantica distinta:
- **Capacidad continua** (hardware): un numero que se compara con un umbral; promueve o **degrada** de forma
  gradual (N1/N2/N3). Se mide con pruebas reales (D44).
- **Presencia discreta** (entorno): un hecho booleano —un servicio esta o no disponible, una dependencia
  esta o no instalada, un dispositivo esta o no conectado, una opcion esta o no habilitada—. **No escala:
  actua como puerta** (disponible/ausente). No se "mide" con pruebas de rendimiento; se **comprueba**.

Forzar la presencia discreta dentro de las metricas de hardware (p. ej. `recursos["ha"] = 1.0`) es un
**booleano disfrazado de metrica**: funciona, pero mezcla dos semanticas y dos responsabilidades de deteccion.

## 2. Alternativas

### A. `PerfilEfectivo` actual es suficiente (todo como metricas)
Codificar la presencia como metrica (`>= 1.0`). **Pros:** cero cambios; las reglas ya soportan `>=`.
**Contras:** sobrecarga semantica de `recursos`/`pruebas` (RAM y "microfono presente" en la misma tabla);
un servicio disponible no es una metrica de rendimiento; el `DetectorPerfil` tendria que medir hardware y
**comprobar** entorno en un mismo tipo (dos responsabilidades). Choca con la definicion de D44
("capacidad efectiva verificada por **pruebas**"): la presencia no es capacidad ni se verifica por prueba.
**Riesgo:** el modelo miente sobre lo que representa.

### B. Ampliar `PerfilEfectivo` con campos de entorno
Anadir `servicios`, `dispositivos`, `dependencias`, `config` al mismo objeto, y `Fuente` gana valores nuevos.
**Pros:** un solo objeto de entrada; el entorno pasa a ser de primera clase (no floats). **Contras:**
`PerfilEfectivo` (perfil de **capacidad**) se convierte en un **god-object** que tambien lleva "que servicios
estan arriba"; el nombre deja de ajustar; **dos responsabilidades de deteccion** en un tipo. Menos codigo que
C, pero **mezcla concerns** que evolucionaran por separado.

### C. Separar en dos modelos, agregados en un contexto de activacion (recomendada — a tu decision)
- `PerfilHardware` = lo que hoy es `PerfilEfectivo` (recursos + pruebas, D44).
- `EstadoEntorno` = presencia discreta: `servicios`, `dispositivos`, `dependencias`, `config` (frozensets/dict).
- El Manager recibe un `ContextoActivacion { hardware, entorno }` (sigue **agnostico**: solo metricas y
  hechos de presencia; nunca marcas/modelos/OS).
- Las condiciones declarativas amplian `Fuente` a `{RECURSO, PRUEBA, SERVICIO, DISPOSITIVO, DEPENDENCIA,
  CONFIG}` con operadores de presencia (`PRESENTE`/`AUSENTE`); **siguen siendo datos serializables**.
- Deteccion en **dos responsabilidades**: `DetectorHardware` (mide capacidad, D44) y `DetectorEntorno`
  (comprueba presencia). Ambos latente-prevista (su implementacion real requiere hardware/entorno).

**Pros:** separacion de concerns honesta (capacidad continua vs presencia discreta); cada dimension evoluciona
sin tocar la otra; el Manager y la declaracion **pasiva/serializable** se preservan; extensible (anadir una
dimension de entorno no toca el modelo de hardware). **Contras:** mas tipos por adelantado; el Manager cambia
de firma (recibe el contexto, no el perfil suelto).

### D. Patron ortogonal (combinable con A/B/C): recursos de entorno como capacidades-hoja
Modelar "servicio HA disponible" o "Ollama instalado" como **capacidades** del propio Registry, y que otras
dependan de ellas (campo 8, mecanismo I4 ya existente). **Util** para expresar cadenas de dependencia sin
logica nueva. **No sustituye** a A/B/C: la capacidad-hoja **sigue necesitando** un hecho de presencia como
entrada (de donde C/B lo toman). Se menciona porque reduce reglas ad-hoc una vez elegido el modelo base.

## 3. Coherencia con las decisiones vigentes

| Criterio | A | B | C |
|---|---|---|---|
| D44 (capacidad efectiva por pruebas = hardware) | ✗ mezcla presencia con "capacidad" | ~ la diluye | ✓ la respeta (hardware aparte) |
| ADR-0021 · Manager **agnostico** | ✓ | ✓ | ✓ (recibe hechos, no identidades) |
| Declaracion **pasiva/serializable** (independencia del catalogo) | ✓ | ✓ (si las condiciones siguen siendo datos) | ✓ |
| D46 · arquitectura completa sin hipotesis | ~ (presencia como float es hipotesis de modelado) | ✓ | ✓ |
| Separacion de responsabilidades (Registry/Manager/Detector) | ✗ un detector para dos cosas | ~ | ✓ dos detectores |
| Regla 13 · no sobre-ingenieria | ✓ (nada nuevo) | ✓ | ~ (mas tipos; justificado por necesidad real e inminente) |

## 4. Lo que NINGUNA alternativa pone en riesgo (retrabajo cero)

Sea cual sea la elegida, **lo construido no se rehace**: bajo C, el actual `PerfilEfectivo` **es**
`PerfilHardware` (mismo contenido); las reglas de memoria (sobre `recursos`) siguen validas y verdes; el
Manager gana la dimension de entorno de forma **aditiva**. No hay regresion ni migracion del trabajo de C1/C2.

## 5. Recomendacion del CTO (para tu decision, no ejecutada)

**Opcion C**, complementada con el patron **D** donde una dependencia sea, en si, una capacidad. Razon: las
dos naturalezas (capacidad continua vs presencia discreta) son **objetivamente distintas** —distinta
semantica, distinta deteccion, distinto rol (degradar vs abrir/cerrar)—; separarlas mantiene el modelo
**honesto y extensible** y evita el god-object de B y el booleano-disfrazado de A. La necesidad es **real e
inminente** (automatizaciones/conectores/HA no se pueden declarar sin ella), por lo que **no** es
sobre-ingenieria (regla 13): es construir justo lo que el siguiente paso exige.

**Si prefieres minimalismo**, B es un punto intermedio aceptable (un solo objeto, menos tipos) a costa de
mezclar concerns; A la descarto porque hace que el modelo represente algo que no es.

## 6. Impacto si se aprueba C (resumen, no implementacion)

- Nuevos tipos: `EstadoEntorno`, `ContextoActivacion`; `PerfilEfectivo` → `PerfilHardware` (alias/rename).
- `Fuente` + operadores de presencia; `_cumple` interpreta ambas fuentes. Todo declarativo/serializable.
- `DetectorEntorno` (Protocol; real diferido). `composicion` pasa el contexto (hardware por defecto + entorno
  por defecto vacio). Memoria intacta.
- Todo bajo TDD + mutacion + Quality Gate, en su propia fase, **solo tras tu aprobacion del modelo**.

## 7. Decision requerida

1. ¿Qué modelo adoptamos: **A**, **B** o **C** (mi recomendacion), y con o sin el patron **D**?
2. Con tu eleccion, preparo la fase de implementacion (contratos + TDD) **antes** de declarar cualquier
   capacidad nueva. Hasta entonces, el Registry permanece con **solo memoria**.

> **Resuelto (2026-07-27).** El §7 refleja la fase de decision; su resultado —tras el refinamiento— esta en
> los §§8-9 (modelo resuelto e Invariantes Arquitectonicos).

## 8. Modelo de activacion resuelto (cierre conceptual, CEO 2026-07-27)

El modelo queda definido por sus **componentes y su flujo**, no por una etiqueta A/B/C:

**Flujo:** `Detectores → ActivationContextBuilder → ActivationContext → Capability Manager → PlanActivacion → Composicion`.

- **Detectores** (por ambito, sin invasion): el **detector de hardware** produce `metricas_verificadas` (D44);
  los **detectores especializados** reducen cualquier combinacion concreta (servicios, dependencias,
  dispositivos, config, datos) a **hechos de dominio de soporte**: *"capacidad X soportada por el entorno"*.
  Toda la tecnologia concreta (MQTT, Ollama, Whisper, credenciales) queda **encapsulada aqui**.
- **ActivationContextBuilder** (agregador): ejecuta los detectores, **normaliza** sus salidas (estructural:
  nombres canonicos, unidades, union de conjuntos, descarte defensivo con log) y **construye** el
  `ActivationContext`. **No aplica reglas ni decide** (frontera demostrada; §9).
- **ActivationContext**: el **unico contrato de entrada** del Manager. Agrega `metricas_verificadas` +
  `capacidades_soportadas`, en **lenguaje de dominio** (nombres de capacidad y metricas), sin tecnologia.
- **Capability Manager**: funcion **pura** que decide `activa/degradada/latente` y la autonomia a partir del
  `ActivationContext` + las **reglas declaradas** del Registry (dependencias I4, seguridad, autonomia). Es el
  **unico** que decide estados. Nunca conoce tecnologia ni la maquinaria de deteccion.
- **Registry**: declaraciones **pasivas y serializables** (datos, no logica); fuente unica de la
  clasificacion (D41); un Loader externo puede producirlas desde cualquier formato (independencia del catalogo).
- **Patron D**: un requisito de entorno se modela como **capacidad-hoja** cuyo "soportada" fija su detector;
  las demas dependen de ella (I4). Sin campos de tecnologia.

Nota semantica: se descarta "disponible"; los detectores informan **"soportada"** (el entorno puede
sostenerla); la decision de estado es exclusiva del Manager.

## 9. Invariantes Arquitectonicos (restricciones permanentes)

Fronteras de responsabilidad **demostradas** en esta revision. Son **restricciones permanentes** de la
arquitectura, no conclusiones de un analisis puntual. Toda implementacion y toda evolucion futura debe
respetarlas.

- **I-A1 · Manager puro.** El Capability Manager es una funcion pura de decision:
  `planificar(ActivationContext) → PlanActivacion` con las reglas del Registry. **No** ejecuta deteccion,
  **no** conoce tecnologia ni implementacion, **no** tiene efectos. Determinista.
- **I-A2 · Detectores especializados y en su ambito.** El detector de hardware produce **solo** metricas
  verificadas (D44); los especializados producen **solo** hechos de dominio de soporte. **Ningun detector
  invade el ambito de otro**; toda la tecnologia concreta se encapsula aqui.
- **I-A3 · Builder sin reglas de negocio.** El ActivationContextBuilder **solo** ejecuta detectores,
  normaliza (estructural) y construye el `ActivationContext`. **No** aplica reglas, umbrales ni decisiones;
  **no** referencia `Registry`/`Manager`/`Estado`/reglas. Protegido por **prueba anti-regresion** (precedente
  D41/MA.5-a, por AST) en el Quality Gate.
- **I-A4 · ActivationContext, unico contrato de entrada.** El Manager recibe **exclusivamente** un
  `ActivationContext` (metricas verificadas + capacidades soportadas, en lenguaje de dominio). **No** recibe
  detectores ni fuentes concretas. Es el unico punto de entrada de informacion de activacion.
- **I-A5 · Registry declarativo.** Las capacidades son **declaraciones pasivas y serializables** (datos, no
  logica); el Registry es la **fuente unica** de la clasificacion (D41), reemplazable por cualquier Loader
  (independencia del catalogo). **Toda la inteligencia de decision vive en el Manager, nunca en la declaracion.**

**Gobierno.** Con estos invariantes, la Architecture Review queda **cerrada**. La discusion posterior es de
**implementacion** (contratos + TDD + mutacion + Quality Gate). El diseno **no se reabre** salvo evidencia
nueva que contradiga alguno de I-A1…I-A5.
