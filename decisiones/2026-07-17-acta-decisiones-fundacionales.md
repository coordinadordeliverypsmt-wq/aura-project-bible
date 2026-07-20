---
documento: "Acta de Decisiones Fundacionales"
version: 1.12.0
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

## Autorización

El CEO autoriza el inicio de la **Fase D1**: redacción de los 5 capítulos P0 (1.1 → 1.2 → 2.1 → 2.2 → 3.1), cada uno con gate de aprobación del CEO.
