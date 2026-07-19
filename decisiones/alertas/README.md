# Alertas de Arquitectura

Mecanismo del acta D15 (constitución 1.1 §4): riesgos a 5-10 años detectados por el CTO. Cada alerta suspende el trabajo afectado y convoca gate extraordinario del CEO. Estructura obligatoria: [plantilla-alerta.md](plantilla-alerta.md) (10 secciones, acta D16).

| Alerta | Riesgo | Estado |
|---|---|---|
| [ALERTA-001](2026-07-17-alerta-001-bus-vs-streaming.md) | Bus de eventos vs streams de voz/avatar (latencia M1) | **RESUELTA** — Opción A (2026-07-17) |
| [ALERTA-002](2026-07-18-alerta-002-captura-terceros.md) | Captura de conversaciones con terceros vs guardrail de no-vigilancia y ley de consentimiento (KCM, D23) | **RESUELTA** — Alternativa A + alcance de sesión (2026-07-18) |
| [ALERTA-003](2026-07-19-alerta-003-gemini-en-router.md) | Cablear Gemini (API comercial + clave) como proveedor principal en router.py vs D24/D1/ADR-0001/ADR-0010/P-ARQ-4 | **Activa** — pendiente de gate extraordinario |
