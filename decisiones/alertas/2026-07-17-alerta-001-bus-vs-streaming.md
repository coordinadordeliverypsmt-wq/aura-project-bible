---
documento: "ALERTA DE ARQUITECTURA 001"
estado: "RESUELTA — Opción A aprobada por el CEO (2026-07-17)"
fecha: 2026-07-17
emisor: "Fable (CTO), conforme al acta D15 y la constitución 1.1 §4"
riesgo-horizonte: "MVP (hito M1) y 5-10 años"
trabajo-suspendido: "Diseño de los capítulos 3.3 (bus de eventos), 6.2 (voz) y 6.5 (avatar) — ninguno iniciado; suspensión preventiva"
---

# ALERTA-001 — El mandato "todo por el bus de eventos" es incompatible con la voz conversacional

## Riesgo

El capítulo 3.1 (Aprobado) declara que percepciones, decisiones y acciones viajan por el bus de eventos, y a la vez que "la conversación manda" (latencia sub-segundo, hito M1 — el de mayor riesgo del MVP según 2.2). Ambos mandatos no pueden cumplirse a la vez: el audio y el video son **streams continuos**, no eventos discretos; forzarlos a través de un bus con serialización y colas destruye el presupuesto de latencia de la voz. Tal como está, los capítulos 6.2 y 6.5 heredarían un mandato imposible — y el defecto quedaría cableado en la arquitectura durante años.

## Alternativas

- **A (recomendada por el CTO): bus = plano de control.** Los eventos discretos (decisiones, comandos, estados) viajan por el bus, versionados y trazables; los **streams de media** (voz, avatar) viajan por canales dedicados negociados fuera del bus, **correlacionados** con eventos de control (inicio/fin/decisiones) para preservar la auditabilidad D9 y la trazabilidad P-ARQ-7. El presupuesto de latencia conversacional se vuelve requisito explícito (cuantificado en 2.5, respetado por 3.3). Costo: dos mecanismos de transporte que documentar. Beneficio: cada mandato del CEO se cumple sin excepción oculta.
- **B: mantener todo-por-el-bus.** Simplicidad conceptual; latencia de voz comprometida → pone en riesgo M1 y el momento mágico (D2). **Desaconsejada.**
- **C: excepción puntual solo para voz.** Parche sin regla general; el problema reaparece con avatar, cámaras (R4) y cualquier stream futuro. **Desaconsejada.**

*Los 4 niveles del acta D3 no aplican: no es una compra/selección de tecnología sino una corrección estructural; las opciones son de diseño.*

## Resolución (CEO, 2026-07-17)

**Aprobada la Opción A.** Ratificado por el CEO:
- El **Event Bus será el plano de control** del sistema.
- Toda **acción discreta** (eventos, comandos, auditoría, memoria, decisiones, permisos y automatizaciones) viaja por el Event Bus.
- Los flujos de **voz, video, pantalla, sensores y demás transmisiones en tiempo real** usan **canales dedicados de baja latencia**.
- Ambos mundos permanecen correlacionados mediante **Correlation ID / Trace ID** para conservar la trazabilidad completa (D9, P-ARQ-7).

Aplicado en el 3.1 §2.1 (v1.1.0, paquete P-002); 3.3, 6.2 y 6.5 nacen con este alcance. Trabajo desbloqueado.
