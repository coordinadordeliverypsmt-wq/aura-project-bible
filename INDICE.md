# AURA Project Bible v1.0 — Índice Maestro (v0.2)

> Actualizado el 2026-07-17 tras las decisiones fundacionales del CEO ([acta](decisiones/2026-07-17-acta-decisiones-fundacionales.md)).

**Leyenda** — P0 fundacional · P1 necesario para el MVP · P2 importante · P3 futuro. ⊘ = stub (máx. 2 págs). Estado inicial: No iniciado.


## Libro I — Gobernanza y Método
*La constitución del proyecto: quién decide, cómo se documenta y cómo vive la Bible misma.*

- **1.1 Constitución del Proyecto, Roles y Autoridad** `[P0 · Fable · Aprobado]` — Definir la Bible como fuente única de verdad, los roles del equipo y el criterio de terminación de la propia v1.0.
- **1.2 Sistema de ADRs y Gestión del Cambio** `[P0 · Fable · Aprobado]` — Instituir el mecanismo formal para registrar y superseder toda decisión arquitectónica.
- **1.3 Proceso de Trabajo por Fases** `[P1 · Fable · No iniciado]` — Definir el método de fases cerradas con gates de aprobación del CEO.
- **1.4 Estándares Documentales, Plantillas y Ciclo de Vida de la Bible** `[P1 · Sonnet (mantiene Haiku) · No iniciado]` — Fijar la calidad mínima verificable de todo documento y cómo se versiona la Bible durante años.
- **1.5 Restricciones de Negocio: Presupuesto, Legal y Licencias** `[P1 · Fable (inventario: Haiku) · No iniciado]` — Hacer visibles las restricciones económicas y legales que condicionan decisiones P0/P1.

## Libro II — Visión y Producto
*Qué es AURA, para quién existe y qué límites éticos la gobiernan.*

- **2.1 Visión, Misión y Anti-Visión** `[P0 · Fable · No iniciado]` — Declarar la identidad de AURA como compañero cognitivo y lo que nunca será.
- **2.2 Alcance del MVP y Roadmap por Releases** `[P0 · Fable · No iniciado]` — Delimitar el MVP de 9 capacidades definido por el CEO y gobernar su riesgo de alcance.
- **2.3 Usuario y Escenarios Prioritarios** `[P1 · Fable · No iniciado]` — Aterrizar la visión en escenarios concretos de la vida del CEO ordenados por valor.
- **2.4 Personalidad, Ética y Límites del Compañero IA** `[P1 · Fable · No iniciado]` — Diseñar la identidad definida por el CEO y los límites éticos de una relación IA-humano de años.
- **2.5 Requisitos y Atributos de Calidad** `[P1 · Sonnet · No iniciado]` — Formalizar requisitos verificables que restringen y guían la arquitectura.

## Libro III — Arquitectura del Sistema
*El contrato técnico central: núcleo event-driven, plugins y datos.*

- **3.1 Principios Arquitectónicos y Decisiones Estructurales** `[P0 · Fable · No iniciado]` — Fijar los principios que toda decisión técnica futura debe respetar.
- **3.2 Arquitectura de Referencia (Vistas C4)** `[P1 · Fable · No iniciado]` — Establecer la vista maestra que todo capítulo técnico detalla y respeta.
- **3.3 Núcleo Event-Driven y Contratos Internos** `[P1 · Opus · No iniciado]` — Especificar el sistema nervioso de AURA y sus garantías cuando los eventos tienen efectos físicos.
- **3.4 Sistema de Plugins y Adaptadores** `[P1 · Opus · No iniciado]` — El contrato que materializa "agregar tecnologías sin rediseñar el sistema".
- **3.5 Modelo de Datos y Persistencia** `[P1 · Sonnet · No iniciado]` — Definir entidades, almacenes y la evolución de esquemas que protege el activo irremplazable (la memoria).
- **3.6 Selección de Stack Tecnológico** `[P1 · Fable · No iniciado]` — Documentar criterios y decisiones de lenguajes, frameworks e infraestructura vía ADRs.

## Libro IV — Cognición: Memoria, Orquestación y Agencia
*El corazón diferencial de AURA.*

- **4.1 Arquitectura de Memoria a Largo Plazo** `[P1 · Opus · No iniciado]` — Diseñar cómo AURA recuerda durante años sin degradarse ni violar la privacidad.
- **4.2 Orquestación Multi-Modelo y Model Router** `[P1 · Opus · No iniciado]` — La capa que enruta cada tarea al mejor modelo sin acoplarse a ningún proveedor.
- **4.3 Sistema de Agentes y Tool Use** `[P1 · Opus · No iniciado]` — Cómo AURA planifica, usa herramientas y ejecuta tareas de forma trazable.
- **4.4 Aprendizaje Continuo y Personalización** `[P1 · Fable · No iniciado]` — Cómo AURA mejora con el uso sin reentrenar modelos ni derivar en comportamiento (capacidad del MVP por decisión del CEO).

## Libro V — Seguridad y Confianza
*Que un sistema con acceso total a tu vida digital sea tu mayor protección, no tu mayor riesgo.*

- **5.1 Modelo de Amenazas** `[P1 · Fable · No iniciado]` — Identificar sistemáticamente qué puede salir mal con una IA que ve todo y puede actuar.
- **5.2 Seguridad de IA: Prompt Injection, Sandboxing y Memoria** `[P1 · Opus · No iniciado]` — Que contenido malicioso externo jamás escale a acciones reales sobre el hogar o los sistemas.
- **5.3 Autonomía Gobernada: Permisos, Human-in-the-Loop y Kill Switch** `[P1 · Fable · No iniciado]` — Materializar la política de autonomía decidida por el CEO.
- **5.4 Identidad, Secretos y Control de Acceso** `[P1 · Sonnet · No iniciado]` — Quién puede hablar con AURA y cómo se custodian decenas de credenciales sin un punto único de fuga.
- **5.5 Privacidad y Soberanía de Datos** `[P1 · Fable · No iniciado]` — Materializar la postura local-first estricta decidida por el CEO.
- **5.6 Seguridad Activa del Ecosistema** ⊘ `[P3 · Sonnet · No iniciado]` — AURA como guardián proactivo de la red y dispositivos del usuario (post-MVP).

## Libro VI — Interacción e Integraciones
*Cómo AURA percibe y actúa sobre el mundo.*

- **6.1 Contrato de Adaptador de Dominio** `[P1 · Fable · No iniciado]` — La abstracción común que normaliza cualquier dispositivo o servicio integrable.
- **6.2 Interacción por Voz** `[P1 · Sonnet · No iniciado]` — El pipeline de voz completo con latencia que haga la conversación natural (capacidad núcleo del MVP).
- **6.3 Integración de Referencia: Home Assistant + MQTT** `[P1 · Sonnet · No iniciado]` — Anclar el control básico del hogar (MVP) en la primera integración real.
- **6.4 Control de Sistemas, Automatización y Centro de Notificaciones** `[P1 · Sonnet · No iniciado]` — Las manos digitales del MVP: control básico del computador, motor de automatización y centro único de notificaciones.
- **6.5 Avatar Interactivo y Presencia** `[P1 · Sonnet · No iniciado]` — La representación visual interactiva de AURA (capacidad del MVP por decisión del CEO).

## Libro VII — Ingeniería, Operación y Evolución
*Los estándares con los que AURA se construye, se prueba y sobrevive años.*

- **7.1 Estándares de Desarrollo y Código** `[P1 · Sonnet · No iniciado]` — Fijar las reglas de calidad de código antes de la primera línea.
- **7.2 Estrategia de Pruebas y Evals de IA** `[P1 · Sonnet · No iniciado]` — Cómo se verifica software clásico + comportamiento no determinista de LLMs.
- **7.3 Walking Skeleton y Entrega Continua** `[P1 · Sonnet · No iniciado]` — El corte mínimo de código que valida la arquitectura al cerrar la Bible.
- **7.4 Operación Mínima Viable** ⊘ `[P2 · Sonnet · No iniciado]` — Lo operacional imprescindible, colapsado en un capítulo.
- **7.5 Visión Evolutiva: hacia el Sistema Operativo Cognitivo** ⊘ `[P3 · Fable · No iniciado]` — Horizontes post-MVP en máximo 2 páginas.

---
**Totales:** 36 capítulos · P0: 5 · P1: 28 · P2: 1 · P3: 2 · Stubs: 3 · Completos: 33

**Orden de redacción P0:** 1.1 → 1.2 → 2.1 → 2.2 → 3.1 (cada uno con gate del CEO).
