---
documento: "Acta de Decisiones Fundacionales"
version: 1.20.0
autor: "Mauricio (CEO) — registrada por Fable (CTO)"
fecha: 2026-07-17
estado: "Vinculante"
historial:
  - version: 1.0.0
    fecha: 2026-07-17
    cambio: "Registro de las 8 decisiones fundacionales + principio adicional y autorización de Fase D1"
  - version: 1.1.0
    fecha: 2026-07-17
    cambio: "D10 — Filosofía de Desarrollo (sistema vivo) agregada por el CEO al aprobar el capítulo 1.1"
  - version: 1.2.0
    fecha: 2026-07-17
    cambio: "D11 (matriz de impacto en ADRs), D12 (modo de trabajo documental) y D13 (estructura estándar de capítulo) agregadas por el CEO al aprobar el capítulo 1.2"
  - version: 1.3.0
    fecha: 2026-07-17
    cambio: "D14 (Evolución Permanente → ADR-0004) y D15 (deber de disenso y Alerta de Arquitectura del CTO) agregadas por el CEO al aprobar el capítulo 2.2"
  - version: 1.4.0
    fecha: 2026-07-17
    cambio: "D16 (estructura obligatoria de 10 secciones de la Alerta de Arquitectura) y D17 (CEO Executive Summary por fase) agregadas por el CEO en el gate de la Fase D2"
  - version: 1.5.0
    fecha: 2026-07-18
    cambio: "D18 (AURA = PIOS), D19 (naturaleza personal con arquitectura comercial-escalable), D20 (horizonte 10 años) y D21 (las cinco preguntas de largo plazo) agregadas por el CEO en el gate de la Ola 1 de la Fase D2"
  - version: 1.6.0
    fecha: 2026-07-18
    cambio: "D22 (fase de ejecución: mandato de ejecutar sin cambios de alcance + delegación de aprobación de capítulos de ejecución al CTO, con decisiones de tecnología/guardrails/rango 1 reservadas al CEO) agregada por el CEO en el gate del 3.2"
  - version: 1.7.0
    fecha: 2026-07-18
    cambio: "D23 (Módulo de Captura de Conocimiento como capacidad oficial + cierre del alcance funcional de la versión inicial). El CEO refina además la lista de materias reservadas a su aprobación (tecnología, alcance, guardrails éticos, Alertas, riesgos de largo plazo)"
  - version: 1.8.0
    fecha: 2026-07-18
    cambio: "D24 (stack local-first sin dependencia de proveedores para validación/baseline; HC-1 pendiente de validación en entorno objetivo; análisis comparativo open source por ADR antes de adoptar componentes; gestión proactiva de entorno)"
  - version: 1.9.0
    fecha: 2026-07-18
    cambio: "D25 (Architecture Review al cierre de cada milestone) y D26 (sin ADR/dependencia nueva sin reducir complejidad o beneficio medible) agregadas por el CEO al aprobar la Architecture Review M1 y autorizar el Milestone M1"
---

# Acta de Decisiones Fundacionales — 2026-07-17

El CEO ratificó el método de trabajo y el índice de la Bible (v0.1 → v0.2), y resolvió las 8 decisiones abiertas. Estas decisiones son **vinculantes**: prevalecen sobre cualquier capítulo y se formalizarán como ADRs una vez aprobado el capítulo 1.2.

## D1 — Postura de datos: local-first estricto

Toda la información personal, memoria, documentos, fotografías, credenciales, dispositivos, automatizaciones y datos privados permanecerán **siempre bajo control del usuario**. La nube solo podrá utilizarse para: (a) consultar modelos de IA, (b) sincronizar información previamente autorizada, (c) respaldos cifrados, (d) servicios externos explícitamente aprobados. Toda comunicación deberá estar cifrada. La privacidad es un pilar fundamental de AURA.
*Impacta: 3.1 (será ADR-0001), 5.5, 4.1, 4.2.*

## D2 — Alcance del MVP

El MVP debe demostrar que AURA es un compañero inteligente, no otro asistente. Capacidades mínimas (9):
memoria permanente · conversación natural por voz · avatar interactivo · control básico del computador · automatización de tareas · integración con ChatGPT, Claude y Gemini · control básico del hogar inteligente · aprendizaje continuo · centro único de notificaciones.

**Momento mágico:** mantener conversaciones naturales, recordar semanas después cualquier tema tratado, ejecutar acciones reales y anticiparse a las necesidades del usuario.

*Nota del CTO (aceptada la decisión):* es el MVP más ambicioso de los evaluados por el panel; para gobernar el riesgo de alcance se estructurará en hitos internos — **M1** núcleo conversacional (memoria + voz + 3 LLMs), **M2** manos digitales (computador + automatización + notificaciones), **M3** presencia (hogar + avatar + aprendizaje/anticipación) — detallados en el capítulo 2.2.
*Impacta: 2.2; sube a P1 completo los capítulos 4.4, 6.2, 6.3, 6.4 y 6.5.*

## D3 — Presupuesto

Sin límite presupuestal inicial. Toda decisión técnica prioriza **calidad y escalabilidad**. Cuando existan alternativas, se presentarán siempre en 4 niveles — **Económica · Balanceada · Profesional · Enterprise** — y el CEO decidirá cuál implementar.
*Impacta: 1.5, 3.6 y todo ADR con alternativas.*

## D4 — Nivel inicial de autonomía

AURA ejecuta automáticamente **solo acciones de bajo riesgo**: automatizaciones, encender/apagar dispositivos, consultas, recordatorios, monitoreo, organización.

Requiere autorización **siempre**: pagos, compras, transferencias, eliminación de información, apertura de cerraduras, mensajes enviados a terceros, acciones legales, acciones financieras.

Conforme aumente la confianza podrán habilitarse niveles superiores mediante políticas.
*Impacta: 5.3 (listas verde/roja), 4.3.*

## D5 — Multiusuario

La versión inicial es para un único usuario (**Mauricio**). La arquitectura se diseña desde el inicio preparada para múltiples usuarios: cada usuario tendrá identidad, memoria, permisos, automatizaciones y preferencias completamente independientes.
*Impacta: 3.1, 5.4, 4.1.*

## D6 — Identidad de AURA

Nombre: **AURA**. Naturaleza: compañero de Inteligencia Artificial. Personalidad: profesional, cercana, proactiva, honesta, crítica cuando sea necesario, **jamás aduladora**. Siempre dirá la verdad aunque contradiga las ideas del usuario; no intentará complacer si considera que existe una mejor alternativa. Un compañero de confianza, no un asistente sumiso.
*Impacta: 2.4 (system prompt maestro).*

## D7 — Criterio de cierre de la Bible v1.0

Ratificado. No comenzará una sola línea de código hasta que: P0 aprobado · P1 aprobado · arquitectura validada · riesgos identificados · roadmap aprobado · ADRs principales documentados.
*Impacta: 1.1 (sección "Criterio de cierre").*

## D8 — Plataforma documental

Aprobado **Git + Markdown**. Toda la documentación vive en el repositorio. Versionado con Semantic Versioning. Cada documento lleva: versión, autor, fecha, estado e historial de cambios. La documentación deberá poder convertirse automáticamente en sitio web con **MkDocs Material o Docusaurus** (elección pendiente — se resolverá vía ADR con las 4 opciones de nivel).
*Impacta: 1.4.*

## D9 (adicional) — Principio obligatorio: Human in the Loop

Principio arquitectónico obligatorio para todo el proyecto: **toda acción crítica deberá poder ser auditada, explicada y revertida. Nunca sacrificar seguridad por comodidad. Toda decisión tomada por AURA deberá ser explicable.**
*Impacta: 3.1 (Principio #1), 5.3, 4.3.*

## D10 — Filosofía de Desarrollo: sistema vivo (2026-07-17, segunda sesión)

AURA nunca será un producto terminado: será un **sistema vivo**. Cada módulo deberá diseñarse para evolucionar. Toda nueva capacidad deberá poder incorporarse **sin rediseñar el sistema**. AURA deberá aprender continuamente. Su arquitectura deberá permitir crecer durante muchos años. La **compatibilidad hacia atrás** será una prioridad. La **modularidad** será obligatoria. **No existirán componentes monolíticos. Toda inteligencia será desacoplada.**
*Impacta: 3.1 (principios), 2.1 (visión), 3.3/3.4 (contratos y plugins con compatibilidad hacia atrás), 4.4 (aprendizaje continuo).*

## D11 — Matriz de impacto obligatoria en ADRs (2026-07-17, tercer gate)

Todo ADR deberá indicar explícitamente su impacto en: **seguridad, privacidad, modularidad, costo, experiencia de usuario y mantenimiento futuro**.
*Impacta: 1.2 §5, plantilla de ADR, todos los ADRs futuros (y ADR-0001 por actualización autorizada).*

## D12 — Modo de trabajo documental (2026-07-17, tercer gate)

No se imprimirán documentos extensos en la terminal. Todo documento se guarda como archivo Markdown en el repositorio. La terminal muestra únicamente: resumen ejecutivo, cambios realizados, archivos modificados y preguntas que requieren aprobación. Cuando un documento quede **aprobado** se generan automáticamente su versión Markdown, PDF y HTML navegable, y se actualiza el índice de la Bible. Toda la documentación debe poder abrirse desde VS Code.
*Impacta: 1.4, flujo de trabajo del CTO y agentes, `herramientas/publicar.py`.*

## D13 — Estructura estándar de capítulo, legible por humanos e IA (2026-07-17, tercer gate)

Toda la documentación deberá ser legible tanto por humanos como por IA. Cada capítulo incluirá automáticamente: **Resumen ejecutivo · Objetivo · Decisiones tomadas · Riesgos · Dependencias · Próximos pasos · Referencias cruzadas**. Todo se mantiene sincronizado automáticamente.
*Impacta: 1.4 (plantillas), los 36 capítulos de la Bible.*

## D14 — Principio de Evolución Permanente (2026-07-17, cuarto gate)

Todo componente desarrollado para AURA deberá cumplir el principio de **Evolución Permanente**: ningún módulo podrá diseñarse con límites artificiales; todo deberá poder ser reemplazado o ampliado sin afectar el resto del ecosistema; la arquitectura deberá soportar crecimiento durante muchos años; ninguna integración será exclusiva de un proveedor; todo componente deberá exponer interfaces estables (API o contratos) para permitir reemplazos futuros; siempre que sea posible se privilegiará la modularidad sobre la simplicidad inmediata. **Se registra como ADR independiente** (ADR-0004).
*Impacta: 3.1, 3.3, 3.4, 6.1 y todo capítulo de arquitectura; ADR-0004.*

## D15 — Deber de disenso y Alerta de Arquitectura del CTO (2026-07-17, cuarto gate)

Además de redactar la Bible, el CTO actúa como tal: si detecta que una decisión — incluida una del CEO — puede comprometer el proyecto dentro de 5 o 10 años, debe **detener el proceso y levantar una ALERTA DE ARQUITECTURA**. No debe continuar simplemente porque el CEO no lo haya mencionado. Debe cuestionar las decisiones del CEO cuando exista una alternativa claramente superior. El CEO prefiere una discusión técnica hoy que una mala arquitectura mañana.
*Impacta: 1.1 (enmienda al rol del CTO), flujo de todos los gates.*

## D16 — Estructura obligatoria de la Alerta de Arquitectura (2026-07-17, gate D2)

Toda ALERTA DE ARQUITECTURA deberá incluir obligatoriamente, en este orden: **(1) Problema detectado · (2) Riesgos si se ignora · (3) Tres alternativas posibles · (4) Recomendación del CTO · (5) Impacto en costo · (6) Impacto en rendimiento · (7) Impacto en seguridad · (8) Impacto en mantenibilidad · (9) Impacto a 10 años · (10) Compatibilidad con versiones anteriores.** El CEO no quiere solo una recomendación: quiere entender el porqué técnico antes de aprobar.
*Impacta: 1.1 §4, plantilla `decisiones/alertas/plantilla-alerta.md`, toda alerta futura.*

## D17 — CEO Executive Summary por fase (2026-07-17, gate D2)

Al finalizar cada fase importante, el CTO generará un documento **CEO Executive Summary** que sintetice, en lenguaje ejecutivo, lo decidido, lo construido, los riesgos vivos y lo pendiente de la fase.
*Impacta: 1.3 (cierre de fase), `resumenes-ejecutivos/`.*

## D18 — AURA es un Sistema Operativo de Inteligencia Personal (PIOS) (2026-07-18, gate Ola 1 D2)

AURA **no** será definida como un asistente virtual. AURA será definida como un **Sistema Operativo de Inteligencia Personal (Personal Intelligence Operating System — PIOS)**. Toda decisión de arquitectura, documentación y desarrollo deberá alinearse con esta definición. El objetivo de AURA es convertirse en el **núcleo inteligente del ecosistema digital del usuario**, integrando modelos de IA, automatizaciones, dispositivos, memoria, conocimiento y servicios externos bajo una única arquitectura **modular, segura y evolutiva**.
*Impacta: 2.1 (definición primaria — enmienda a v2.0.0), README, y el encuadre de todo capítulo. El "compañero cognitivo" pasa a ser la cara experiencial del PIOS.*

## D19 — Naturaleza del proyecto: personal hoy, arquitectura comercial-escalable (2026-07-18)

AURA nace como proyecto **personal de largo plazo**, pero su arquitectura se diseña con **visión comercial y escalable**. Ninguna decisión técnica podrá limitar una futura evolución hacia producto comercial, empresarial u open source parcial. Toda la arquitectura debe permanecer **desacoplada** para permitir cualquiera de esos escenarios sin rediseños mayores. (Resuelve la pregunta abierta de 1.5 §5; el "default prudente" de licencias se vuelve permanente.)
*Impacta: 1.5 §5 (resuelta), 3.6 (stack sin lock-in), toda selección de licencias/dependencias.*

## D20 — Horizonte mínimo de 10 años en toda decisión de arquitectura (2026-07-18)

Toda decisión de arquitectura se evaluará pensando en un horizonte mínimo de **10 años**. No se aceptarán optimizaciones que comprometan la escalabilidad, la mantenibilidad o la independencia tecnológica del proyecto.
*Impacta: 3.1 §2 (criterio de evaluación), todo ADR.*

## D21 — Las cinco preguntas de largo plazo (2026-07-18)

Toda decisión deberá responder, antes de aprobarse: (1) ¿Escala durante los próximos 10 años? · (2) ¿Reduce la dependencia de un proveedor? · (3) ¿Permite sustituir tecnologías sin rediseñar el sistema? · (4) ¿Puede mantenerse por un equipo pequeño? · (5) ¿Contribuye a que AURA sea un sistema vivo y evolutivo? Si **alguna respuesta es negativa**, el CTO deberá generar una **ALERTA DE ARQUITECTURA** antes de continuar.
*Impacta: 3.1 §2.3 (checklist de evaluación), 1.2 (criterio de todo ADR), mecanismo de alertas D15/D16.*

## D22 — Fase de ejecución: mandato de ejecutar y delegación de aprobación al CTO (2026-07-18, gate 3.2)

A partir de la aprobación del 3.2, el objetivo principal es **ejecutar la arquitectura aprobada**. No se introducirán nuevas funcionalidades, cambios de alcance ni modificaciones conceptuales, **salvo mediante una Alerta de Arquitectura debidamente justificada y aprobada**. Para no ser el cuello de botella de la ejecución, el CEO **delega en el CTO la autoridad de aprobación de los capítulos de ejecución**, que el CTO ejerce con criterio ejecutivo: (1) que no cambie el alcance; (2) que respete todas las decisiones previas (actas, ADRs, principios); (3) las cinco preguntas de largo plazo (D21). El CTO aprueba o rechaza y avanza. **Se reservan al CEO** (no delegadas): las selecciones de tecnología con alternativas (D3, 4 niveles), toda modificación de un guardrail ético o de una decisión de rango 1, y toda Alerta de Arquitectura. Un capítulo que requiera cualquiera de esas se eleva al CEO; el resto lo aprueba el CTO.
*Impacta: 1.1 §4/§6 (enmienda: delegación de aprobación en fase de ejecución), flujo de todos los capítulos restantes.*

## D23 — Módulo de Captura de Conocimiento y cierre del alcance funcional (2026-07-18, gate stack)

Se incorpora como **capacidad oficial** de AURA un **Módulo de Captura de Conocimiento**: un módulo nativo, **desacoplado del núcleo**, capaz de capturar, procesar y organizar información de conversaciones **siempre con autorización expresa del usuario** y respetando privacidad, seguridad y Human-in-the-Loop. Debe permitir: transcribir reuniones presenciales autorizadas; transcribir llamadas y videollamadas autorizadas; procesar grabaciones y notas de audio; generar transcripciones precisas y resúmenes ejecutivos; identificar participantes, temas, decisiones y compromisos; extraer tareas, fechas y responsables; incorporar lo relevante a la memoria de AURA según las reglas; y permitir búsquedas posteriores. Se implementa como componente desacoplado (arquitectura modular aprobada), local-first y bajo las políticas de seguridad del proyecto. **Con esta decisión, el CEO declara CERRADO el alcance funcional de la versión inicial de AURA**: no se incorporarán nuevas funcionalidades ni cambios de visión salvo Alerta de Arquitectura o decisión estratégica excepcional aprobada por el CEO.
*Impacta: 2.2 (nueva capacidad, cierre de alcance), nuevo capítulo 4.5, y 2.4 §5 (guardrail de no-vigilancia — ver ALERTA-002).*

## D24 — Stack de validación y producción local-first, sin dependencia de proveedores; entorno proactivo (2026-07-18)

Para validar HC-1 y como baseline reproducible del proyecto **no se utilizarán APIs comerciales ni claves de terceros**. La arquitectura debe ser **independiente de proveedores, reproducible y basada preferentemente en tecnologías locales y de código abierto** (o la mejor alternativa técnicamente justificada). Los modelos de nube (D2: ChatGPT/Claude/Gemini) siguen siendo **recursos opcionales** detrás del router (4.2), pero el sistema **no depende** de ellos: el camino por defecto y de validación es local. **HC-1 se registra como "Pendiente de validación en entorno objetivo"**, no como fallido. **Antes de adoptar definitivamente** cualquier componente (Ollama, Faster-Whisper, Piper, Qdrant, etc.) se realiza un **análisis comparativo open source registrado en ADR** (criterios: rendimiento, mantenimiento, comunidad, portabilidad, facilidad de integración, proyección a largo plazo). **Gestión proactiva de entorno:** si se identifica una dependencia/herramienta/servicio necesario, el CTO lo informa con anticipación (por qué, en qué fase, cómo instalarlo, si es automatizable) y prepara scripts reproducibles, para evitar bloqueos por dependencias no previstas. No se solicitan claves de API ni soluciones propietarias salvo justificación arquitectónica documentada y aprobada.
*Impacta: ADR-0006..0013, entorno/ (scripts y stack de producción), validación de HC-1.*

## D25 — Architecture Review al cierre de cada milestone (2026-07-18)

Al finalizar **cada milestone** se ejecuta una **Architecture Review** con el mismo formato consolidado (estado de ADRs y decisiones, cumplimiento de requisitos, trazabilidad Bible↔ADR↔código↔pruebas, riesgos y recomendaciones), para que la evolución del proyecto siga siendo **controlada, trazable y alineada con la Bible y los ADR**. Ningún milestone se declara cerrado sin su Architecture Review aprobada por el CEO.
*Impacta: 1.3 (cierre de milestone), revisiones/.*

## D26 — Disciplina de incorporación: sin complejidad injustificada (2026-07-18)

**Ningún ADR nuevo ni ninguna dependencia nueva** se incorpora sin **demostrar** que reduce complejidad o aporta un **beneficio medible**. La justificación se documenta (en el ADR o en la nota de la dependencia) con la métrica o el criterio de beneficio. Refuerza la regla 13 del ADR-0004 (anti-sobre-ingeniería) y el acta D24 (entorno).
*Impacta: 1.2 (criterio de ADR), 3.6/entorno (dependencias), toda incorporación futura.*

## D27 — Verificación de Entorno obligatoria (Preflight Check) (2026-07-19)

Ningún Sprint, Milestone o sesión de desarrollo comienza sin un **Preflight Check** en estado **APTO**.

**Principio rector:** se verifica siempre el **estado real del sistema**, nunca se asume que una configuración sigue siendo válida porque exista una variable de entorno o un archivo de configuración. En particular, se comprueba el **dispositivo físico que respalda cada ruta** (`df --output=source`), no la ruta en sí: un directorio `/media/.../AURORA_EXT` existe igualmente con el USB desmontado, y en ese caso las escrituras van al disco interno **sin error visible**. Esta fue la causa raíz del incidente del 2026-07-19.

**Comprobaciones:** espacio libre interno y USB; USB realmente montado; punto de montaje = dispositivo esperado; existencia de rutas configuradas; Ollama usando de verdad el directorio del USB; ausencia de modelos duplicados en interno; swap activo esperado; margen suficiente para trabajar.

**Reparación automática:** se corrige sin intervención todo lo que no requiera privilegios; lo que requiera root se entrega como comandos exactos para el CEO. Tras cualquier intervención se **vuelve a verificar** antes de continuar.

**Prevención:** si se detecta que el proyecto va a escribir modelos, cachés o regenerables en el disco interno, se **detiene la operación**, se corrige, se reverifica y solo entonces se continúa.

**Almacenamiento:** interno = SO, código, git, documentación, datos permanentes. USB = modelos (Ollama, Faster-Whisper, voces Piper), cachés, temporales, artefactos regenerables.

**Entregable:** resumen con Estado (APTO/NO APTO), problemas encontrados, corregidos automáticamente, acciones manuales requeridas y riesgos abiertos. Sin estado APTO no se continúa, salvo autorización expresa del CEO.

*Implementado en `entorno/scripts/preflight-check.sh` y `entorno/scripts/ollama-usb.sh` (lanzador con guardarraíl). Impacta: todo inicio de sesión, sprint y milestone.*

## D28 — Riesgo aceptado: cierre de la verificación forense del directorio enmascarado (2026-07-19)

La verificación directa del directorio enmascarado por el punto de montaje se da por cerrada. La evidencia disponible (`df`, `du`, inventario, ubicación física de los modelos y censo del disco) es suficiente para decidir. No se requiere más investigación forense.
*Impacta: Fase 1 de la migración de almacenamiento.*

## D29 — Cambio de prioridad: Timeshift es el consumidor principal (2026-07-19)

El mayor consumidor de almacenamiento interno es Timeshift (26 GB), no los modelos de IA. La migración de Ollama al USB sigue siendo **obligatoria por política** (D31), pero deja de ser la palanca principal para liberar espacio.
*Impacta: planificación de mantenimiento; ejecutado con `liberar-recursos.sh` (5,4 GB → 13 GB libres).*

## D30 — Prohibición de bloqueos administrativos (2026-07-19)

No se detiene el desarrollo por verificaciones cuyo resultado ya no cambia una decisión de arquitectura. Si la evidencia es suficiente para decidir, se continúa automáticamente.

**Criterio obligatorio antes de declarar un FAIL bloqueante**, a responder internamente:
1. ¿La información adicional cambiaría realmente una decisión técnica?
2. ¿Existe un riesgo real para la integridad del proyecto?
3. ¿O simplemente se está buscando certeza absoluta?

Si la respuesta a la tercera es "sí": **registrar el riesgo, documentar la incertidumbre y continuar**.

**Principio:** *evidencia suficiente > certeza absoluta.* El proyecto debe avanzar.
*Impacta: todo gate, toda fase, todo Preflight Check. Complementa D27.*

## D31 — Almacenamiento distribuido: los USB son infraestructura permanente (2026-07-19)

Los dispositivos USB dejan de tratarse como unidades externas y pasan a ser **infraestructura permanente del proyecto AURA**. El disco interno del Lenovo 100e no volverá a saturarse por datos regenerables.

**Distribución permanente:**

| Almacenamiento | Contenido |
|---|---|
| **Interno** (eMMC 57 G) | Sistema operativo, código fuente, repositorio Git, configuración, bases de datos pequeñas, cachés indispensables, paquetes Python (`~/.local`) |
| **USB Principal** (`AURORA_EXT`, 7,3 G) | Modelos de Ollama, modelos Whisper, voces Piper, cachés regenerables, temporales grandes |
| **USB Secundario** (`AURORA_BAK`, 3,6 G) | Backups, snapshots del proyecto, logs históricos, exportaciones, artefactos de pruebas, resultados de benchmarks y validaciones |

**Reglas de operación:**

1. Antes de instalar cualquier componente nuevo se verifica **automáticamente** dónde debe almacenarse.
2. Si un componente se instala en el disco interno debiendo residir en USB, se **corrige automáticamente antes de continuar**.
3. Ninguna instalación futura consume espacio interno si puede ubicarse en almacenamiento externo.
4. Los montajes se declaran en `/etc/fstab` por **identificador estable** (UUID o LABEL), nunca por ruta `/dev/sdX`: el 2026-07-19 un reinicio renombró `sda1` → `sdb1` y una ruta fija habría apuntado al dispositivo equivocado. **Una sola entrada por punto de montaje**: dos entradas al mismo destino provocan montajes duplicados.

**Preflight Check obligatorio en cada ejecución** (extiende D27): ambos USB montados; Ollama usando realmente el USB; Whisper y Piper en almacenamiento externo; swap activo = el definido para AURORA; margen mínimo configurable en el disco interno; **nunca se escriben modelos de IA en el disco interno**. Si alguna verificación falla, el proyecto **se detiene** y explica exactamente qué debe corregirse.

**Excepción razonada (los paquetes Python permanecen en interno):** un entorno de ejecución alojado en una unidad extraíble deja de funcionar en cuanto la unidad no monta, y el fallo se manifiesta lejos de su causa. El criterio es que al USB van **datos y salidas**, no el software que debe estar disponible para arrancar.

**Discrepancia técnica registrada del CTO (D15, deber de disenso):** se recomienda **no** trasladar el swap al USB. La latencia de acceso es del orden de 100x peor que la del eMMC interno, el swapping desgasta la memoria flash hasta inutilizarla, y una desconexión del USB con swap activo derriba el sistema. Se recomienda además **eliminar `swapfile_aurora`** del USB principal: ocupa 4 GB (55% de la unidad) sin prestar servicio, ya que el swap activo es `/swapfile` en el disco interno. Pendiente de decisión del CEO.

*Implementado en `entorno/scripts/preflight-check.sh`, `ollama-usb.sh` y `liberar-recursos.sh`. Impacta: toda instalación futura, todo inicio de sesión, D27.*

## D32 — `mover_archivo` y `renombrar_archivo` en lista roja hasta que exista dry-run (2026-07-20)

Al descomponer la categoría "organizar" (6.4 §1, lista verde) en operaciones concretas, `mover_archivo` y `renombrar_archivo` **alteran el estado del usuario** y pueden perder datos si el destino colisiona. El CEO **ratifica la clasificación conservadora**: ambas permanecen en **lista roja**.

**La Bible NO se modifica todavía.** Rige el principio de máxima seguridad hasta que el **motor de dry-run** exista, esté implementado y validado con evidencia.

**Decisión pendiente registrada:** al cierre del motor de dry-run se reevaluará si estas acciones pueden pasar a lista verde **condicionadas a previsualización obligatoria**.

**Reevaluación ejecutada (2026-07-20, cierre de M2.3): SE MANTIENE SIN CAMBIOS.** Con el motor de dry-run implementado y validado, el CEO resuelve que ambas acciones **continúan en lista roja**. Razonamiento: *"una previsualización no elimina el impacto de una confirmación errónea"*. Se privilegia la seguridad sobre la fluidez.

**Nueva condición de revisión:** la posible reclasificación se examinará **con datos de uso reales y evidencia operacional**, no únicamente con argumentos de diseño. Queda por tanto abierta la divergencia con 6.4 §1 hasta esa fase, de forma consciente y documentada.

*Impacta: `permissions.py` (catálogo), M2.1, M2.3 (dry-run), 6.4 §1.*

## D33 — Neutralidad tecnológica: la plataforma objetivo se decide con el escenario de despliegue

**Fecha:** 2026-07-21. **Decide:** CEO.

Presentado el análisis técnico comparativo de plataformas y modelos para R1, el CEO **acepta las conclusiones técnicas** —el requisito relevante es la **latencia percibida** (primer token ≤500 ms y generación por encima del ritmo del habla), y el Core está verificadamente desacoplado del runtime del modelo— pero **no oficializa ninguna plataforma objetivo**.

**Apple Silicon queda como plataforma de referencia para pruebas de rendimiento**, no como plataforma del proyecto.

**La decisión definitiva se tomará al definir el escenario de despliegue:** uso personal, instalación doméstica, distribución a terceros o producto comercial. Son escenarios con requisitos incompatibles entre sí; comprometer hardware antes de conocer cuál aplica fijaría una restricción a 10 años (D20) sobre una incógnita.

**Principios permanentes de arquitectura** (registrados en **ADR-0016**):

1. Core independiente del modelo.
2. Core independiente del hardware.
3. Modelos, runtimes y aceleradores reemplazables mediante adaptadores.
4. Proveedores de contexto desacoplados mediante ADR-0015.

**Regla derivada:** *cambiar de hardware o de modelo puede cambiar lo útil que es AURA, nunca lo segura que es.*

**Consecuencia operativa:** toda medición de rendimiento debe registrarse junto a la plataforma en que se obtuvo. HC-1 se evalúa contra la plataforma de referencia vigente, y ese vínculo debe ser explícito en cada informe.

*Impacta: ADR-0016, `entorno/ANALISIS-PLATAFORMA-OBJETIVO-R1.md`, HC-1, M3.*

## D34 — No se construyen entornos artificiales para aprobar un milestone

**Fecha:** 2026-07-21. **Decide:** CEO.

Ante la ausencia de una instancia de Home Assistant en el entorno actual, el CEO **rechaza instalar una únicamente para satisfacer el milestone**:

> *"No se construyen entornos artificiales únicamente para aprobar un milestone."*

**Regla permanente:** una capacidad que actúa sobre el mundo físico **se valida contra el mundo físico**. Un laboratorio montado a propósito no demuestra que la capacidad funcione donde va a operar; demuestra que funciona en el laboratorio.

**Aplicación a M3.1:**

- El adaptador **puede diseñarse** con antelación.
- **No se declarará completado** hasta superar una validación *end-to-end* contra una instalación real de Home Assistant, con dispositivos reales (sensores, cámaras, luces).
- M3.1 queda **pendiente** hasta que exista el escenario de despliegue definitivo.

**Alcance general.** El principio no se limita a Home Assistant: rige para toda capacidad cuya corrección dependa de datos o dispositivos reales. Complementa el criterio heredado de T1 —*"si la prueba solo puede fallar por culpa del doble, no vale"*— y lo extiende: **un entorno fabricado para pasar la prueba es un doble con otro nombre.**

**Consecuencia asumida:** algunos milestones quedarán abiertos más tiempo. Se prefiere un milestone honestamente incompleto a uno cerrado contra un decorado.

*Impacta: M3.1, M3.2 (inferencia sobre datos reales), roadmap de M3, criterios de validación de 7.2.*

## D35 — M3 en espera de habilitadores externos; se abre la linea "Preparacion del Entorno Objetivo"

**Fecha:** 2026-07-21. **Decide:** CEO.

Entregadas M3.0 y M3.2a, el trabajo restante de M3 depende de datos de uso real y de un entorno domestico que todavia no existen. El CEO resuelve:

**1. Congelacion.** **M3.1** (hogar real) y **M3.2b** (inferencia de preferencias) quedan **congeladas** hasta disponer de entorno domestico y datos reales suficientes.

**2. Prohibicion de infraestructura no validable.** No se implementara mas infraestructura cuya validacion requiera datos o entornos inexistentes. Es la aplicacion directa de **D34**.

**3. Nueva linea de trabajo: "Preparacion del Entorno Objetivo"**, independiente del roadmap funcional. Produce **unicamente documentacion y analisis** sobre: hardware objetivo, modelo base, sistema operativo, estrategia de despliegue, arquitectura de conectores futuros, requisitos minimos y recomendados, y costes/consumo/mantenimiento.

**Precision del CEO — el estado de M3.** *"No considero M3 bloqueado, sino en espera de habilitadores externos."* La distincion es material: un milestone bloqueado señala un fallo del proyecto; uno en espera señala una dependencia externa identificada y gestionada. M3 se reanudara desde este punto cuando el entorno real exista.

**Restriccion sobre las metricas.** Esta linea **no modifica el Core** y **no incrementa el Product Readiness**. La cifra permanece en **41%** mientras no se entregue capacidad verificable al usuario. Documentar el entorno futuro no acerca a AURA a ser usable; solo prepara la decision que si lo hara.

*Impacta: roadmap de M3, `entorno-objetivo/`, Product Readiness, HC-1.*

## D36 — Escenario de despliegue oficializado: E1 inicial, E2 objetivo de la primera version estable

**Fecha:** 2026-07-21. **Decide:** CEO.

- **E1 — uso personal:** escenario **inicial oficial**.
- **E2 — hogar inteligente:** **objetivo de la primera version estable**.
- **E3 (distribucion a terceros) y E4 (producto comercial):** **fuera del alcance actual**. No deben condicionar decisiones de arquitectura mientras no exista un cambio explicito de alcance.

**Consecuencia inmediata:** queda resuelta la dependencia que mantenia en espera a tres fases de M3, a la elección de hardware, de modelo y de sistema operativo. Lo que sigue pendiente ya no es una decision, sino la **disponibilidad material** del entorno: equipo, Home Assistant, dispositivos y uso cotidiano.

**Consecuencia sobre el diseno:** al quedar E3/E4 fuera de alcance, no se disenara para multiusuario ajeno, soporte a terceros ni cumplimiento contractual. Las obligaciones legales que E3/E4 introducirian (RGPD como responsable del tratamiento, reparto de responsabilidad del HITL) **no se abordan**, y su aparicion futura requerira revision de arquitectura.

*Impacta: M3.1, M3.2b, D33 (plataforma), `entorno-objetivo/02-estrategia-de-despliegue.md`.*

## D37 — Precision del principio local-first: independencia funcional, no aislamiento

**Fecha:** 2026-07-21. **Decide:** CEO. **Corrige una formulacion imprecisa del CTO.**

El CTO habia documentado que los conectores hacia wearables (Garmin, Apple Watch, Oura, Fitbit) *"chocan con ADR-0001 (local-first)"*, por acceder a datos mediante APIs en la nube del fabricante. **El CEO corrige esa lectura**, y la correccion se acepta:

> *"No chocan con local-first. Lo que ocurre es que esos fabricantes no permiten acceder a todos los datos directamente desde el dispositivo. Ese matiz evita convertir el principio local-first en una limitacion innecesaria."*

**Formulacion vigente del principio** (precisa ADR-0001, no lo modifica):

1. **AURA funciona completamente sin Internet.** Ninguna capacidad basica depende de un servicio externo.
2. **Opcionalmente**, el usuario puede conectar servicios externos para **enriquecer** el contexto.
3. **Si un servicio deja de funcionar o el usuario revoca el acceso, AURA sigue operando**; simplemente pierde esa fuente.

**La distincion clave:** lo prohibido es la **dependencia funcional**, no la existencia de fuentes opcionales. *Local-first* no es *local-only*.

### Decision PENDIENTE de arquitectura — conectores hacia servicios de terceros

No se renuncia a integrarlos ni se modifica el principio. Queda registrado como pendiente, con estas condiciones ya fijadas por el CEO:

- **Habilitacion explicita del usuario.** Ningun conector externo se activa por defecto.
- **Transparencia sobre el recorrido del dato:** debe quedar claro **que datos permanecen locales y cuales pasan necesariamente por servicios del fabricante**.
- **Ningun proveedor externo sera requisito** para el funcionamiento basico de AURA.

Su implementacion requerira ADR propio. Hasta entonces, ningun conector de este tipo se construye.

*Impacta: ADR-0001 (precisado, no modificado), ADR-0015, D24, `entorno-objetivo/04-conectores-futuros.md`.*

## D38 — Cierre de la linea "Preparacion del Entorno Objetivo"

**Fecha:** 2026-07-21. **Decide:** CEO.

La linea abierta por D35 queda **concluida y aceptada**. No incrementa el Product Readiness, que permanece en **41%**.

**Regla operativa:** *"No continues generando documentacion preparatoria si no aporta nueva evidencia o desbloquea un milestone."*

El proyecto queda a la espera de **decisiones de arquitectura** o de la **disponibilidad del entorno real** (hardware, Home Assistant, dispositivos y uso cotidiano) para reanudar los milestones correspondientes.

*Impacta: `entorno-objetivo/`, ritmo de trabajo del CTO.*

## D39 — El proyecto NO esta congelado: desarrollo continuo con restricciones de hardware

**Fecha:** 2026-07-21. **Decide:** CEO. **Corrige una caracterizacion erronea del CTO.**

El CTO habia descrito el estado del proyecto como *"congelado"*. **El CEO corrige el concepto:**

> *"No quiero una pausa de desarrollo; quiero una adaptacion del roadmap a las limitaciones actuales."*

**Estado oficial: desarrollo continuo con restricciones de hardware.**

Lo aplazado son **unicamente** las capacidades cuya validacion depende del hardware objetivo o de un entorno fisico real: M3.1, M3.2b, y las partes de M3.3 y M3.4 que asi lo requieran. **Todo lo demas sigue avanzando.**

**Criterios de admision del trabajo.** Es valido todo aquel que cumpla alguno de estos ocho:

1. No depende del hardware objetivo.
2. Aporta valor arquitectonico real.
3. Reduce deuda tecnica.
4. Mejora la calidad del codigo.
5. Fortalece la seguridad.
6. Simplifica el despliegue.
7. Mejora el runtime de produccion.
8. Prepara la integracion futura de sensores, wearables y demas conectores aprobados.

**Objetivo declarado:** *"Cuando llegue el nuevo hardware, el objetivo es que AURA ya tenga toda la arquitectura madura y unicamente sea necesario habilitar las capacidades que requieren esa plataforma, no empezar a construirlas desde cero."*

**Relacion con D38.** D38 prohibia generar documentacion preparatoria que no desbloqueara un milestone; sigue vigente. D39 **no la contradice**: distingue entre documentar el futuro —restringido— y **construir arquitectura que estara lista cuando el futuro llegue** —autorizado—.

*Impacta: estado del proyecto, roadmap, `auditoria/2026-07-21-auditoria-tecnica-integral.md` (que aporta el inventario de trabajo admisible).*

## D40 — Principios permanentes del arranque y la composicion

**Fecha:** 2026-07-21. **Decide:** CEO, al aprobar MA.1.

**1. Observabilidad del arranque.** *"AURA debe indicar siempre que cree que esta activo antes de comenzar a operar."*

El informe de arranque —capacidades activas, fuentes de contexto, rutas de estado, kill switch— deja de ser una comodidad de MA.1 y pasa a ser **principio permanente**. Su valor es preciso: convierte un cableado incompleto en algo **visible el dia uno**, en lugar de un defecto que se descubre semanas despues. Es la contramedida directa al patron de ALERTA-004 y ALERTA-005.

**2. Punto de entrada unico.** `python -m aura_skeleton` es la **unica forma oficial** de iniciar AURA. Cualquier ejecutable nuevo **debe consumir `composicion.componer()`**, nunca reconstruir el sistema. Un cableado propio en otro fichero reabre exactamente el agujero que MA.1 cerro.

**3. La composicion debe permanecer declarativa.** Su responsabilidad es **ensamblar componentes, no contener logica de negocio**. Si empieza a tomar decisiones funcionales, **debe refactorizarse antes de continuar**.

**4. Precision del alcance (2026-07-22, con ADR-0018 y D41).** El punto 2 distingue **punto de entrada de produccion** de **arnes de validacion**: el unico ejecutable de produccion (`python -m aura_skeleton`) debe consumir `composicion`; los arneses de validacion pueden ensamblar variantes deliberadas de la arquitectura (otro bus, varios proveedores, un componente aislado) **solo si estan declarados en la fuente unica de clasificacion** (manifiesto, D41) y **nunca** como punto de entrada de produccion. Todo ejecutable que construya el sistema y no este clasificado en el manifiesto es una violacion de D40, verificada por prueba anti-regresion.

**5. Criterio de admision de un arnes (2026-07-22).** Un arnes solo puede quedar en el manifiesto si necesita una **variacion deliberada que no tendria sentido incorporar al cableado de produccion**. Si esa variacion pasa a tener valor para produccion, se revisa si debe **convertirse en una capacidad de `composicion()`**; de lo contrario, permanece como arnes autorizado. *(Primera aplicacion: `demo_capacidad_m2` queda como arnes porque su proveedor guionado es un doble de prueba determinista, no una capacidad que tenga sentido en produccion.)*

*Impacta: `composicion.py`, `__main__.py`, todo ejecutable futuro, MA.2 a MA.5.*

## D41 — Fuente unica de verdad para la clasificacion estructural del sistema

**Fecha:** 2026-07-22. **Decide:** CEO, al aprobar el plan de MA.5-a.

**Ninguna lista de excepciones arquitectonicas se mantiene duplicada** entre documentacion, codigo y pruebas. Toda clasificacion estructural del sistema —que ejecutables son de produccion, cuales son arneses autorizados, cuales no construyen el sistema, cuales son obsoletos— tiene **una unica fuente de verdad versionada** (`walking-skeleton/architecture_manifest.toml`), **consumida por las herramientas de validacion**: la prueba anti-regresion la lee; la documentacion la referencia, no la copia.

**Por que:** una allowlist codificada dentro de una prueba, y repetida en documentacion, se desincroniza en silencio. Un manifiesto unico hace que agregar o reclasificar un ejecutable sea un cambio en un solo sitio, revisable y auditado.

*Impacta: MA.5-a, la prueba anti-regresion, ADR-0018, todo documento que clasifique ejecutables.*

## D42 — Un elemento "pendiente de contrato" no es codigo muerto; se clasifica explicitamente

**Fecha:** 2026-07-22. **Decide:** CEO, durante MA.5-b.

**Regla permanente.** Todo elemento clasificado como **implementacion pendiente (o parcial) de un contrato** debera quedar **identificado de forma explicita en la documentacion arquitectonica**, y **no podra volver a ser considerado "codigo muerto" mientras el contrato que lo justifica permanezca vigente**. Antes de eliminar algo que "parezca muerto" (condicion fijada para MA.5-b) debe demostrarse con evidencia objetiva **(1)** que su funcionalidad esta completamente absorbida o sustituida por otra (convergencia arquitectonica), **o (2)** que nunca formo parte de un comportamiento observable ni de un contrato vigente. Si no puede demostrarse una de las dos, se **conserva y se clasifica**, no se elimina.

**Primer elemento clasificado (MA.5-b):** el subsistema de **metricas** (`observability.py`: `metric_inc`/`metrics`/`_metrics`). El contrato existe —Bible **7.4** (operacion minima viable) exige *"metricas basicas (P-ARQ-7)"*—; la implementacion **no esta cableada** (ningun componente incrementa ni lee metricas). Se **conserva** como implementacion pendiente del contrato P-ARQ-7, clasificada en el codigo (`observability.py`) y aqui. Cablearla seria una **iniciativa funcional independiente**, no limpieza (fuera del alcance de MA.5-b).

**Actualizacion de estado (A2, 2026-07-26):** ese ejemplo pasa de *pendiente* a **realizado**. La iniciativa independiente **A2** cableo el contrato en sus puntos de emision reales —`bus.publish` (`eventos.publicados`) y `permissions.authorize` (`acciones.autorizadas`/`acciones.denegadas`)— bajo TDD estricto (RED→GREEN→Quality Gate→mutacion), manteniendo `metric_inc`/`metrics` simples y locales (sin dependencias, sin persistencia, sin telemetria). **La regla D42 permanece intacta**: solo transita el estado del elemento que fue su primer ejemplo (ver `milestones/m3-entry/A2-metricas-basicas.md`).

*Impacta: MA.5-b, `observability.py`, Bible 7.4/P-ARQ-7, todo futuro juicio de "codigo muerto".*

## D43 — Evolucion por capacidades del hardware (perfiles, no versiones)

**Fecha:** 2026-07-22. **Decide:** CEO, al aprobar ADR-0020.

**Principio permanente.** AURA es **un solo proyecto, un solo codigo, un solo contrato funcional, un solo formato de datos y una sola arquitectura** que **se adapta automaticamente al hardware detectado**. Los distintos "niveles" son **perfiles de ejecucion de esa unica arquitectura, NO versiones de AURA**: el contrato funcional de una capacidad permanece identico y solo cambia su **implementacion interna**, elegida de forma **automatica, reversible y transparente** para el usuario en instalacion/reconfiguracion.

- **Mas hardware = mas capacidad, autonomia y rendimiento; menos hardware degrada sin perder memoria, configuracion ni compatibilidad.** El usuario nunca elige "que version instalar" ni interviene.
- **Independencia tecnologica:** los perfiles se definen por **capacidades**, no por el nombre de una tecnologia; un motor mejor en el futuro ocupa el perfil que corresponda sin cambiar la arquitectura.
- **La deteccion de hardware que gobierna el perfil se verifica en el momento** (D27), nunca se supone.

Complementa **ADR-0016/D33** (neutralidad tecnologica: la seguridad nunca cambia con el hardware, la utilidad puede escalar). Primera aplicacion: la memoria (**ADR-0020**, perfiles N1/N2/N3). Rige cualquier componente futuro con implementaciones dependientes de recursos.

*Impacta: ADR-0020, ADR-0011, ADR-0016, Bible 4.1, todo componente con implementaciones dependientes de recursos.*

## D44 — Capacidad EFECTIVA (verificada por pruebas), no capacidad declarada por specs

**Fecha:** 2026-07-22. **Decide:** CEO, al aprobar ADR-0020.

**Regla permanente (completa D43).** La deteccion del perfil de hardware **nunca depende solo de las especificaciones tecnicas** (RAM, CPU, GPU). Se basa en la **capacidad real verificada** del equipo, combinando tres fuentes:

1. **Caracteristicas del hardware detectado** (specs declaradas).
2. **Resultados de pruebas reales de rendimiento** —latencia, memoria disponible, velocidad de inferencia, etc.— ejecutadas en el propio equipo (D27: verificacion en el momento).
3. **Requisitos minimos definidos para cada capacidad.**

El hardware declara una **capacidad potencial**; las pruebas determinan la **capacidad efectiva**. Asi se evita clasificar un equipo como "alto rendimiento" solo porque tiene GPU cuando, en la practica, no cumple los objetivos.

**El perfil se recalcula automaticamente** cuando cambie el hardware, el sistema operativo, los modelos utilizados, o aparezca una version de AURA mas eficiente — manteniendo la evolucion automatica **sin reglas fijas**.

**Alcance:** aplica a **toda capacidad dependiente del hardware** (memoria, inferencia, voz, automatizaciones, vision, etc.), no solo a la memoria. Es la referencia de la nueva linea base para cualquier seleccion de perfil por hardware.

*Impacta: ADR-0020, D43, D27, toda capacidad futura con implementaciones dependientes de recursos; el mecanismo de instalacion/reconfiguracion.*

## D45 — Arquitectura completa; capacidades latentes en un Registro de Capacidades

**Fecha:** 2026-07-26. **Decide:** CEO. **Materializa:** ADR-0021. **Va un paso mas alla de** ADR-0020/D43/D44.

**Regla permanente.** AURA es **un solo proyecto** —un solo codigo, una sola arquitectura, un solo
contrato y un solo formato de memoria—. Las capacidades dependientes del hardware **no se documentan ni
se tratan como "pendientes"**: son **capacidades latentes ya previstas por la arquitectura**, cuya
activacion depende unicamente de los recursos disponibles. La arquitectura esta **siempre completa**; lo
unico que evoluciona es el **conjunto de capacidades que AURA puede ejercer** segun el hardware.

1. **Registro de Capacidades (Capability Registry).** Cada capacidad es un **modulo autonomo** que se
   auto-declara con, al menos: (1) contrato funcional, (2) grado de latencia —**activable** o
   **prevista**—, (3) requisitos minimos de activacion, (4) dependencias, (5) garantias de seguridad a
   mantener, (6) criterio objetivo D44 de habilitacion. El registro es la **fuente unica** de la
   clasificacion de capacidades (D41).
2. **Capability Manager agnostico.** No conoce ninguna capacidad concreta: recorre el registro y activa o
   desactiva segun la **capacidad efectiva** del entorno (D44). Anadir una capacidad es **registrar un
   modulo**, no tocar el nucleo (D40, P-ARQ-4).
3. **Dos grados de latencia.** *Activable* (implementacion existente, se enciende sola por perfil) y
   *prevista* (arquitectura reserva contrato y lugar; se construye+valida cuando el hardware/datos lo
   permiten, ADR-0004). Esto respeta **regla 13 / D3 / D34 / D38**: "preparada para todas" = todas tienen
   lugar y contrato en el registro, **no** que todas esten construidas y apagadas.
4. **La seguridad es invariante (D33).** Activar mas capacidades **nunca** relaja garantias; el Manager no
   activa una capacidad si no puede preservar las suyas. La **utilidad escala con el hardware; la
   seguridad, jamas**.
5. **Evolucion sin cambio de arquitectura.** Al mejorar el hardware AURA **solo incrementa** las
   capacidades que ejerce. **Nunca** ediciones Lite/Pro/Enterprise; **nunca** un "AURA 2"; **nunca**
   migraciones manuales; el usuario **instala una sola vez**. La activacion/desactivacion es
   **transparente, reversible y sin perdida** de memoria, configuracion, historial ni compatibilidad.

**Alcance:** todo el sistema —IA local, memoria, inferencia, voz, vision, Home Assistant,
automatizaciones, agentes, conectores externos, avatar y cualquier capacidad futura—. La memoria
(ADR-0020) es una capacidad mas del registro; ADR-0018 y ADR-0019 son instancias del patron.

*Impacta: ADR-0021, ADR-0020, ADR-0018, ADR-0019, ADR-0004, D33/ADR-0016, D43, D44, D41, Bible 3.1/3.2/3.4, la linea base 2026-07-26, todo componente y capacidad futura.*

## Autorización

El CEO autoriza el inicio de la **Fase D1**: redacción de los 5 capítulos P0 (1.1 → 1.2 → 2.1 → 2.2 → 3.1), cada uno con gate de aprobación del CEO.
