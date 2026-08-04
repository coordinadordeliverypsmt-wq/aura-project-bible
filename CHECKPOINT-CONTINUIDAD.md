# CHECKPOINT DE CONTINUIDAD — AURA

**Protocolo PCC (CEO, 2026-08-03).** Este fichero se lee **antes que nada** al reanudar. No rehacer
análisis ya cerrado. No recorrer el repositorio salvo que aquí se indique. No reabrir decisiones
aprobadas.

**Fecha:** 2026-08-03 · **Motivo de la parada:** límite de contexto de la sesión.

**El Protocolo de Continuidad es PERMANENTE** (CEO, 2026-08-03) y vive en `CLAUDE.md` §0: parada automática por debajo del ~2 % de contexto, sin esperar a que el CEO lo pida.

---

## Identificación

| | |
|---|---|
| Milestone | `m3-entry` |
| Worktree | `.claude/worktrees/m3-entry` |
| Rama | `worktree-m3-entry` |
| Último commit de la rama | `315a7f9` (espec G-1) |
| `main` publicado | `ba73208` + merge de G-1 (ver §Último resultado válido) |

---

## Objetivo que se estaba ejecutando

Cerrar la cadena **ALERTA-006 → D-M-8 → G-1**, entregando diseño revisable **sin implementar código**,
según el orden fijado por el CEO.

## Completado (no repetir)

- **Contención de ALERTA-006 IMPLEMENTADA y publicada.** 3 medidas: guarda de dominio en el disparador
  de olvido · `_foco` no actúa ante ambigüedad (pide desambiguación) · `refutar` solo confirma con
  mutación efectiva. RED→GREEN→**mutación 5/5**→Quality Gate PASS. Publicada en `ba73208`.
- **DP D-M-1** (recuperador N1, `A′` prefijo+cota) — **aprobado como documento**. Implementación NO
  autorizada; supeditada a D-M-2.
- **DP D-M-2** (auto-eco) — **diagnóstico aprobado**. `Op-5` NO autorizada; supeditada a D-M-7.
- **DP D-M-7** (clasificación de intención) — **diagnóstico y modelo de 2 ejes aprobados**.
  Implementación NO autorizada. Batería de 172 casos en `milestones/m3-entry/bateria-intencion.json`.
- **DP D-M-8** (Motor Único de Mutaciones) — **diagnóstico y modelo aprobados**. Implementación
  condicionada a G-1.
- **ESPEC G-1** (Ruta Única de Mutación) — **APROBADA como documento de diseño** (CEO, 2026-08-03).

## Pendiente exacto

1. **Implementar D-M-8** siguiendo el plan de 7 fases del DP. **Requiere autorización explícita del
   CEO**, que aún no se ha dado.
2. **Corregir ALERTA-006 en lo estructural** mediante el nuevo Motor.
3. **D-M-7** sobre la nueva arquitectura → **D-M-2** con el clasificador definitivo → **D-M-1**.
4. **Revisión independiente de la contención de ALERTA-006** — no se pudo completar (el agente auditor
   terminó por límite de gasto de la cuenta). **La contención NO está cerrada definitivamente.**
5. **Decisión pendiente del CEO:** renombrar las operaciones mutantes a nombres inequívocos. Medido que
   es **condición de viabilidad de G-1** (resolución de receptor 40 % → 100 %). Toca superficie pública
   de los almacenes.

## Próximo primer paso al reanudar

> **1) Construir el ROADMAP, cuya FASE 1 es el ciclo cerrado de 7 pasos (ver seccion de cierre metodologico). Cada fase debe entregar CAPACIDAD REAL, no documentacion.**
> **1b) Inventario total previo antes de proponer nada nuevo.**
> **(referencia) ROADMAP del Sistema Operativo Interno** (ver seccion "ENCARGO EN COLA").
> **2) Dentro de el, pedir las dos autorizaciones pendientes: implementar D-M-8 y renombrar las operaciones mutantes.** Sin esas
> dos autorizaciones no puede avanzarse: el orden aprobado sitúa D-M-8 antes que todo lo demás, y G-1
> no es viable sin nombres inequívocos.

Antes de tocar nada: `bash entorno/scripts/preflight-check.sh` y `./quality-gate.sh` (§1 del Checklist).

## Último resultado válido

| Elemento | Estado |
|---|---|
| Quality Gate | **PASS** (última ejecución en la rama, tras la espec G-1) |
| Mutación | `mutaciones/contencion-alerta006.toml` → **5/5 detectados, 0 supervivientes** |
| Pruebas nuevas | `tests/unit/test_contencion_alerta006.py` (7 casos, 2 son controles) |
| Alerta abierta | **ALERTA-006** — contención hecha; **estructural ABIERTO** |
| DP aprobados como documento | D-M-1 · D-M-8 · ESPEC G-1 |
| DP con diagnóstico aprobado | D-M-2 · D-M-7 |

## Riesgos abiertos / qué falta verificar

- **ALERTA-006 sigue abierta en lo estructural:** la mutación **no pasa por el Motor Único** y **el kill
  switch armado NO la detiene**. La contención solo evitó la destrucción silenciosa.
- **La contención no tiene auditoría independiente.** La revisó quien la implementó, lo que incumple el
  estándar del proyecto.
- **G-1 no demuestra ausencia de rutas alternativas** (limitación del análisis estático, declarada en
  la especificación). Necesita la prueba dinámica complementaria G-2b.
- Deuda previa viva: `D-N2-5`, `D-A-11`, `D-M-1`…`D-M-7`, `ModeloUsuario.corregir` construido y **no
  cableado**, `CentroNotificaciones.cerrar_sesion` sin llamador.

---

## ENCARGO EN COLA — Roadmap del Sistema Operativo Interno de AURORA (CEO, 2026-08-03)

**No iniciado.** Recibido por debajo del umbral de parada del Protocolo de Continuidad; empezarlo
habria sido hacerlo "a la carrera". **Es el primer trabajo de la proxima sesion.**

### Cambio de objetivo principal
El objetivo deja de ser cerrar deuda tecnica: pasa a ser que **AURORA evolucione hacia una arquitectura
capaz de administrarse, verificarse y mejorarse a si misma en local**, sin depender de Claude para el
trabajo operativo. La pregunta rectora ya no es *"como implementamos esto"* sino
**"como hacemos que AURORA pueda implementarlo ella misma"**.

### Los 7 principios de trabajo (obligatorios)
1. Ningun cambio deja vacios arquitectonicos. Si aparece uno: documentarlo y proponer su cierre
   **antes** de continuar.
2. Toda implementacion responde a: *¿esto acerca a AURORA a ser mas autonoma y autosuficiente?*
3. **No hay modulos nuevos** sin integracion clara en el modelo general. Se prefiere una arquitectura
   pequeña, coherente y extensible.
4. El siguiente nivel es el **Sistema Operativo Interno**, con 10 roles bajo un **unico orquestador**:
   Director General · Arquitecto · Programador · QA y Mutacion · Seguridad · Documentacion ·
   Investigacion · Planificador · Memoria · Observabilidad.
5. **Ningun agente decide estrategia por su cuenta.** Arquitectura, Bible, ADR, protocolos y diseño
   pasan por Decision Package aprobado.
6. Transicion **incremental**, reutilizando lo existente. **No se rehace AURORA**: se convierten
   gradualmente los componentes actuales en un sistema capaz de mejorarse a si mismo.
7. **Reutilizar tiene prioridad sobre crear.** Antes de codigo nuevo: identificar que componentes
   actuales pueden convertirse en capacidades permanentes.

### Entregable pedido — roadmap tecnico, no funciones aisladas
Debe mostrar: **estado actual · estado objetivo · fases de transicion · dependencias · riesgos ·
que puede ejecutar AURORA por si misma en cada fase**.

### Punto de partida ya disponible (NO re-investigar)
- **Rol Orquestador:** existe `MotorAutomatizacion` como camino unico de ejecucion + `D-M-8` (Motor
  Unico de Mutaciones, modelo aprobado) + `ESPEC G-1` (verificador AST, aprobada).
- **Rol QA y Mutacion:** existe el arnes `herramientas/mutar.py` y el `quality-gate.sh` de 5 pasos.
- **Rol Seguridad:** existen `PermissionManager` (catalogo de 28 acciones, listas roja/verde),
  `KillSwitch` y HITL.
- **Rol Observabilidad:** existe `observability.py` con audit log append-only y sellado.
- **Rol Memoria:** existen `PersistentMemory`, `ModeloUsuario`, `AlmacenSenales`.
- **Rol Arquitecto:** existe `architecture_manifest.toml` (fuente unica de verdad, D41) + prueba AST.
- **Rol Documentacion:** existen `CLAUDE.md`, `CHECKLIST-CONTINUIDAD.md` y este checkpoint.
- **Definiciones de agentes:** `.claude/agents/` (4 roles ya versionados).
- **Vacios conocidos que el roadmap debe cubrir:** Director General, Programador, Investigacion y
  Planificador **no tienen contraparte** en el codigo actual.

### Directrices adicionales del CEO (2026-08-03, segundo mensaje)

**El roadmap es el PLAN MAESTRO DE EVOLUCION de AURORA, no una organizacion de tareas.**

**Paso previo obligatorio — INVENTARIO TOTAL antes de proponer nada nuevo.** Inventariar todo lo que
AURORA ya posee y decidir que se reutiliza, para no duplicar: motores · modulos · agentes · pruebas ·
herramientas · protocolos · ADR · Bible · infraestructura · automatizaciones · capacidades.
**El roadmap no puede crear un sistema paralelo:** debe transformar gradualmente el sistema actual en
una organizacion capaz de desarrollar AURORA desde dentro.

**Cada fase debe responder las 7 preguntas, explicitamente:**
1. ¿Que existe hoy?
2. ¿Que falta realmente?
3. ¿Que puede reutilizarse?
4. ¿Que debe evolucionar?
5. ¿Que debe desaparecer?
6. ¿Que nuevas capacidades obtiene AURORA al terminar la fase?
7. ¿Que PORCENTAJE del trabajo puede hacer sin intervencion de Claude?

**Reduccion de dependencia externa — es un objetivo explicito del roadmap.**
Definir como se reduce la dependencia de modelos externos **sin comprometer la calidad**. No se trata
de sustituir a Claude, sino de que **Claude pase de desarrollador principal a consultor especializado**,
invocado solo cuando AURORA detecte que alcanzo un limite tecnico o cuando el CEO pida revision
estrategica. **Ese descenso de dependencia es UNO DE LOS INDICADORES PRINCIPALES del proyecto y debe
medirse objetivamente en cada etapa.**

**Vacios arquitectonicos: priorizados por IMPACTO, no por facilidad de implementacion.**
**Regla de parada:** si durante el analisis aparece un vacio mas critico que los ya conocidos,
**detenerse, justificarlo con evidencia y presentarlo antes de continuar**.

**Criterio rector:** no se busca avanzar mas rapido, sino una arquitectura que sostenga el crecimiento
de AURORA **durante años**.

### Directriz final del CEO (2026-08-03, tercer mensaje) — el PROPOSITO y el IMA

**Correccion del proposito.** Reducir la dependencia de Claude es un **RESULTADO, no el proposito**.
El proposito es un ecosistema donde AURORA **comprenda** el estado del proyecto, **planifique** su
evolucion, **ejecute** trabajo, **valide** resultados, **aprenda** de ellos y **proponga mejoras** de
forma continua — siempre dentro de los limites de la arquitectura y **bajo supervision humana para las
decisiones estrategicas**.

**Indice de Madurez de Autoevolucion (IMA)** — a proponer en el roadmap como **indicador principal del
proyecto**. Nueve dimensiones minimas:

1. Comprension del proyecto
2. Capacidad de planificacion
3. Capacidad de implementacion
4. Capacidad de validacion
5. Capacidad de auditoria
6. Capacidad de recuperacion ante fallos
7. Capacidad de aprendizaje
8. Capacidad de coordinacion entre agentes
9. Dependencia de asistencia externa

**Cada indicador exige tres cosas:** (a) definicion objetiva · (b) forma de medicion · (c) criterio
claro de fase completada.

**Requisito duro:** el IMA debe **actualizarse automaticamente con evidencia obtenida del propio
sistema**, NO por valoracion subjetiva. Un indice que se rellena a mano es una opinion, no una metrica.

**Filtro obligatorio para TODA capacidad propuesta** — responder explicitamente:
1. ¿Esta capacidad hace mas inteligente a AURORA **como producto**?
2. ¿Esta capacidad hace mas capaz a AURORA de **desarrollar la siguiente version de si misma**?

Si ambas respuestas no son positivas, **probablemente no es prioridad de esta etapa**.

**Estatus:** con esto la vision estrategica queda definida. El roadmap pasa a ser **la guia de evolucion
del proyecto durante los proximos hitos**, y todas las decisiones futuras deben poder alinearse con el.

### Observacion tecnica ya detectada (no re-analizar, verificar al construir el roadmap)
El IMA —y en particular la dimension 9— **exige instrumentar el proceso de desarrollo, no el producto**.
Hoy **no existe ninguna instrumentacion para eso**: el audit log mide lo que AURORA hace como producto,
no lo que el equipo hace al construirla. Sin resolver esa brecha, los porcentajes de cada fase serian
estimaciones y no datos — el patron "declarado != real" otra vez. **Es lo primero que hay que examinar.**

### CIERRE DE LA DEFINICION METODOLOGICA + FASE 1 (CEO, 2026-08-03, cuarto mensaje)

**La fase de definicion metodologica queda CERRADA.** Se deja de diseñar como se trabaja y se empieza a
construir la capacidad de autoevolucion. El roadmap es el documento rector, **pero no puede ser un
ejercicio teorico**.

**REGLA PERMANENTE:** *cada fase debe terminar con una **capacidad REAL de AURORA**, utilizable de
inmediato — no solo documentacion ni decisiones de arquitectura.*

**Estructura obligatoria de cada fase del roadmap:**
Objetivo · **Capacidad nueva que AURORA obtiene** · **Evidencia objetiva de que funciona** ·
Impacto sobre el IMA · Dependencias · Riesgos · Criterios de finalizacion.

**FASE 1 — el primer ciclo cerrado.** Debe ser **lo minimo necesario para que AURORA coordine su
propio trabajo**. NO se busca autonomia completa: se busca **cerrar el ciclo**. Siete pasos:

1. Recibir un objetivo.
2. Descomponerlo en tareas.
3. Asignar esas tareas a sus agentes internos.
4. Consolidar los resultados.
5. Detectar conflictos.
6. Preparar un **Decision Package** cuando la decision sea estrategica.
7. Presentar un **informe ejecutivo al CEO**.

**Criterio del CEO:** si ese ciclo funciona, aunque sea de forma limitada, **se cruza un punto de no
retorno**. A partir de ahi se amplian capacidades, **no se rediseña el proceso**.

**Encargo concreto del roadmap:** identificar cual es esa Fase 1 y que **todo el trabajo posterior se
construya sobre ella**. Ese es el inicio real del Sistema Operativo Interno de AURORA.

### AUTORIZACION DE INICIO + NUCLEO VIVO (CEO, 2026-08-03, quinto mensaje)

**Etapa de planificacion CERRADA. Comienza la construccion del Sistema Operativo Interno.**
**El roadmap queda AUTORIZADO a iniciarse.**

**Disciplina permanente (aplica a todo el proyecto):**
- **No crear documentacion** si antes no existe una implementacion o validacion que la justifique.
- **Cada Decision Package termina convertido en capacidad funcional o queda explicitamente descartado.**
- **La documentacion es un artefacto del desarrollo, no el objetivo del desarrollo.**

**PRIORIDAD ADICIONAL — identificar el primer "NUCLEO VIVO":** el conjunto **minimo** de componentes
que permita a AURORA empezar a trabajar sobre si misma **de manera persistente**. No se busca todavia
una organizacion completa de agentes: se busca **el primer ciclo autonomo persistente**.

**El nucleo debe responder, como minimo:**
1. ¿Donde vive el estado del trabajo?
2. ¿Quien decide cual es la siguiente tarea?
3. ¿Quien verifica que la tarea termino correctamente?
4. ¿Quien actualiza el estado del proyecto?
5. ¿Como se reanuda automaticamente tras cualquier interrupcion?
6. ¿Como evita repetir trabajo ya realizado?

**Debe identificarse reutilizando todo lo existente antes de proponer componentes nuevos.**

**CRITERIO PRINCIPAL DE PROGRESO DEL PROYECTO:**
> *AURORA debe construir capacidades que **permanezcan despues de cada sesion**. Cada sesion debe dejar
> a AURORA **objetivamente mas capaz** que al comenzar.*

**Sigue vigente:** todo cambio de arquitectura, Bible, ADR o modelo de gobierno se presenta como
Decision Package **antes** de implementarse.

### Hipotesis de partida a VERIFICAR con el inventario (no dar por cierta)
De los 7 pasos del ciclo de Fase 1: los pasos **6 y 7** (Decision Package e informe ejecutivo) ya
existen como practica establecida; los pasos **3 y 4** (asignar a agentes, consolidar) tienen
precedente operativo en el despacho de exploradores y auditores. **Lo que no existe es la PERSISTENCIA
del ciclo:** hoy el objetivo, su descomposicion y el estado de cada tarea viven en el contexto del
modelo y se pierden al terminar la sesion. Las 6 preguntas del nucleo vivo apuntan todas a esa misma
carencia. **Probable nucleo real de la Fase 1 = estado del trabajo persistente + reanudacion
automatica.** Verificar con el inventario antes de proponerlo.

### PUNTO DE INFLEXION — PERSISTENCIA OPERATIVA (CEO, 2026-08-03, sexto mensaje)

El CEO eleva a **mayor vacio arquitectonico de AURORA** el hecho de que **hoy el ciclo de trabajo solo
sobrevive porque un humano y un modelo escriben un checkpoint a mano**.

**El roadmap NO empieza preguntandose como organizar agentes.** Empieza por:
> **¿Que necesita existir para que AURORA nunca vuelva a depender de la memoria de una sesion?**

**El inventario tiene como objetivo descubrir ese nucleo.** Si confirma la hipotesis, **la Fase 1 no es
"crear agentes": es construir la PERSISTENCIA OPERATIVA de AURORA.**

**Persistencia Operativa = que AURORA pueda, por si misma:**
1. Saber exactamente donde quedo su trabajo.
2. Saber cual era el objetivo activo.
3. Saber que tareas estaban abiertas.
4. Saber quien era responsable de cada una.
5. Saber que decisiones estaban pendientes.
6. Saber que evidencias ya existen.
7. Saber que falta por validar.
8. **Reanudar automaticamente sin depender del contexto de un modelo.**

**Instruccion:** investigar si esa capacidad puede construirse **reutilizando los componentes
actuales**. Si puede reutilizarse, **esa es la prioridad**. Si NO puede, entregar un **Decision Package**
que explique exactamente **que componente falta y por que**.

**PRINCIPIO PERMANENTE (registrado tambien en `CLAUDE.md` §4, reglas no negociables):**
> *Toda capacidad importante de AURORA debera sobrevivir al reinicio de una sesion. Si una capacidad
> desaparece cuando termina la conversacion, todavia no pertenece realmente a AURORA. Solo pertenece
> aquello que el propio sistema puede recuperar, comprender y continuar por si mismo.*

Es, en palabras del CEO, **la verdadera diferencia entre un asistente conversacional y un sistema
operativo de inteligencia**.

## Modo de trabajo vigente (CEO, 2026-08-03)

1. **No abrir nuevos Decision Packages ni alertas**, salvo bloqueo crítico para la implementación.
2. **Prioridad: cerrar deuda, no crear documentación.**
3. Detenerse al ~98 % de contexto y escribir este checkpoint.
4. Al reanudar: leer este fichero y continuar desde el paso pendiente.
