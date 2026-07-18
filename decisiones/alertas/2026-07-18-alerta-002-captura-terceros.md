---
documento: "ALERTA DE ARQUITECTURA 002"
estado: "Activa — pendiente de gate extraordinario del CEO"
fecha: 2026-07-18
emisor: "Fable (CTO), conforme al acta D15 y la constitución 1.1 §4"
trabajo-suspendido: "Diseño detallado del capítulo 4.5 (Módulo de Captura de Conocimiento), específicamente sus sub-capacidades que involucran a terceros (reuniones, llamadas, videollamadas). El resto del Libro IV/V/VI no está afectado."
---

# ALERTA-002 — La captura de conversaciones con terceros choca con el guardrail de no-vigilancia y con la ley de consentimiento

Estructura obligatoria de 10 secciones (acta D16). La capacidad (KCM, acta D23) **esta aprobada**; esta alerta no la rechaza: resuelve **como** construirla sin violar un guardrail etico ya aprobado ni la ley.

## 1. Problema detectado

El Modulo de Captura de Conocimiento (D23) debe transcribir reuniones/llamadas/videollamadas autorizadas e identificar participantes y responsables. Esas conversaciones incluyen a **personas distintas del usuario** (terceros). Sin embargo:

- El capitulo **2.4 sec.5 (Aprobado)** fija como guardrail etico que "AURA no construye perfiles persistentes ni historiales de conducta de personas distintas de su usuario", y la anti-vision 2.1 sec.3.6 declara que AURA "no es una herramienta de vigilancia de terceros".
- Identificar y almacenar quien dijo que, que se comprometio y que responsable tiene una tarea **es** construir un registro persistente de terceros.

La autorizacion que exige la D23 es la del **usuario**; no la de los terceros grabados.

## 2. Riesgos si se ignora

- **Incoherencia normativa interna:** una capacidad (D23) que viola un capitulo aprobado (2.4 sec.5).
- **Riesgo legal (alto):** grabar a terceros sin su consentimiento es ilegal en muchas jurisdicciones (consentimiento de todas las partes); 1.5 lo senalo como materia de asesoria profesional.
- **Riesgo reputacional/etico:** AURA como herramienta de vigilancia de terceros, traicionando su identidad (D18/2.1).
- **Riesgo a 10 anos (D20):** como futuro producto comercial (D19), perfilar terceros sin consentimiento es un pasivo legal y de marca de primer orden.

## 3. Tres alternativas posibles

### A. Conocimiento centrado en el usuario; terceros no perfilados (recomendada)
El KCM transcribe y resume para el usuario, pero **no construye perfiles persistentes de terceros**: los participantes se referencian por rol o etiqueta efimera ("Participante 2", "el cliente") salvo contactos que el usuario ya gestiona; las tareas/compromisos se guardan como **datos del usuario** (sus pendientes), no como historial de conducta de terceros. Reconcilia con 2.4 sec.5.
Pros: cumple el guardrail; menor superficie legal; sostenible. Contras: identificacion de participantes limitada por defecto.

### B. Captura completa con capa de gestion de consentimiento
Se construyen perfiles de participantes, exigiendo y registrando **consentimiento explicito de cada participante** antes de persistir sus datos.
Pros: maxima funcionalidad. Contras: tecnicamente pesado, socialmente incomodo, fragil legalmente; tensiona 2.4 sec.5 salvo excepcion aprobada.

### C. Diferir la captura de terceros; MVP-KCM solo sobre material propio del usuario
La v1 del KCM procesa solo notas de audio y grabaciones que el usuario ya posee legitimamente; reuniones/llamadas con terceros se posponen a un release posterior con revision legal previa.
Pros: cero riesgo inmediato; entrega valor pronto. Contras: no cumple todas las sub-capacidades de la D23 en v1.

## 4. Recomendacion del CTO

**Alternativa A como diseno base + una compuerta de atestacion de consentimiento (HITL) antes de toda grabacion + un item de revision legal (1.5) antes de habilitar llamadas/reuniones.** El usuario atesta que tiene derecho a grabar (HITL, D9); los terceros no se perfilan por defecto (cumple 2.4 sec.5); la extraccion se guarda como conocimiento y pendientes **del usuario**. Si el CEO desea identificacion plena de participantes (Alternativa B), eso exige **modificar el guardrail 2.4 sec.5** por enmienda explicita (materia reservada al CEO), no de facto.

## 5. Impacto en costo

Bajo/medio: A reutiliza voz local (ADR-0008), LLMs (4.2) y memoria (4.1) ya decididos; la compuerta de consentimiento es logica, no infraestructura. B anade una capa de gestion de consentimiento (costo alto). C es el mas barato.

## 6. Impacto en rendimiento

Neutro: transcripcion y resumen son asincronos por el bus (no en el camino conversacional de baja latencia); no afectan 2.5 sec.5.1.

## 7. Impacto en seguridad

A y C reducen al minimo los datos sensibles de terceros (refuerza 5.1 y ADR-0001). B la aumenta (mas datos de terceros que proteger).

## 8. Impacto en mantenibilidad

A es el mas sostenible por un equipo pequeno (regla 13 ADR-0004): menos datos, menos reglas de consentimiento. B es el mas complejo de auditar.

## 9. Impacto a 10 anos

A y C envejecen bien: respetar a los no-usuarios es defendible a escala comercial (D19). B es un pasivo creciente conforme aumenten usuarios y jurisdicciones.

## 10. Compatibilidad con versiones anteriores

Sin incompatibilidad: el KCM es un modulo nuevo (4.5), desacoplado (D23), implementado como plugin por contrato (3.4). La memoria (3.5/4.1) ya distingue titularidad por user_id, lo que soporta A de forma natural.

## Resolucion

Pendiente del gate extraordinario del CEO. El CTO recomienda la Alternativa A + compuerta de consentimiento + revision legal. La eleccion del CEO define como se redacta el capitulo 4.5 y si se modifica o no el guardrail 2.4 sec.5.
