# Alertas de Arquitectura

Mecanismo del acta D15 (constitución 1.1 §4): riesgos a 5-10 años detectados por el CTO. Cada alerta suspende el trabajo afectado y convoca gate extraordinario del CEO. Estructura obligatoria: [plantilla-alerta.md](plantilla-alerta.md) (10 secciones, acta D16).

| Alerta | Riesgo | Estado |
|---|---|---|
| [ALERTA-001](2026-07-17-alerta-001-bus-vs-streaming.md) | Bus de eventos vs streams de voz/avatar (latencia M1) | **RESUELTA** — Opción A (2026-07-17) |
| [ALERTA-002](2026-07-18-alerta-002-captura-terceros.md) | Captura de conversaciones con terceros vs guardrail de no-vigilancia y ley de consentimiento (KCM, D23) | **RESUELTA** — Alternativa A + alcance de sesión (2026-07-18) |
| [ALERTA-003](2026-07-19-alerta-003-gemini-en-router.md) | Cablear Gemini (API comercial + clave) como proveedor principal en router.py vs D24/D1/ADR-0001/ADR-0010/P-ARQ-4 | **RESUELTA** — Alternativa A (2026-07-19); parche rechazado definitivamente |
| [ALERTA-004](2026-07-19-alerta-004-grounding-no-garantizado.md) | La garantía de grounding / no-fabricación no estaba implementada en ninguna parte | **RESUELTA** — Alternativa A+B (2026-07-19), verificada con LLM real |
| [ALERTA-005](2026-07-20-alerta-005-manos-digitales-desconectadas.md) | Las manos digitales de M2 no estaban conectadas al cuerpo | **RESUELTA** — Alternativa A (2026-07-21), verificada con stack real |


> **Corregido el 2026-09-21 (CTO).** Este índice declaraba ALERTA-003 como *«Activa — pendiente de
> gate extraordinario»* cuando su propio expediente dice **«RESUELTA — Alternativa A (2026-07-19).
> Parche rechazado definitivamente»**, y omitía por completo ALERTA-004 y ALERTA-005, que existen
> como ficheros en este mismo directorio desde julio. No era un desfase inocuo: ALERTA-003 es el
> precedente que `DP-DEVELOPMENT-ORCHESTRATOR.md` §25.1 (`D-ORCH-1`) invoca sobre el alcance de D24,
> y quien lo consultara para decidir habría creído que existe un gate abierto sobre proveedores de
> nube. El desfase ya estaba detectado —el propio DP lo registra como hallazgo `[LECT]` n.º 5— y
> seguía sin corregirse. **Los expedientes son la fuente de verdad; este índice es proyección de
> ellos** (ADR-0023).
