# Architecture Decision Records

Instrumento definido en el [capítulo 1.2](../docs/libro-01-gobernanza-y-metodo/1.2-sistema-adrs-gestion-cambio.md). Plantilla oficial: [plantilla-adr.md](plantilla-adr.md). Índice mantenido por Haiku (artefacto operativo).

| Nº | Título | Estado | Origen | Impacta |
|---|---|---|---|---|
| [ADR-0001](0001-postura-local-first-estricta.md) | Postura local-first estricta | **accepted** (2026-07-17) | Acta D1 | 3.1, 3.2, 3.5, 4.1, 4.2, 5.5, 7.4 |
| [ADR-0004](0004-evolucion-permanente.md) | Principio de Evolución Permanente y arquitectura modular | **accepted** (2026-07-17) | Actas D10, D14 | 3.1, 3.3, 3.4, 3.6, 6.1 |
| [ADR-0002](0002-plataforma-documental-sitio.md) | Plataforma de generación del sitio documental (MkDocs Material) | **accepted** (2026-07-18) | Actas D8, D12 | 1.4 |
| [ADR-0005](0005-lenguaje-runtime-nucleo.md) | Lenguaje y runtime del núcleo | proposed | Acta D3, cap. 3.6 | 3.6, 7.1, 7.3 |

*Nota de numeración: ADR-0002 (plataforma documental, D8) y ADR-0003 (autonomía, D4) conservan sus números reservados por el plan del 1.2 §9 y se redactarán con los capítulos 1.4 y 5.3. El ADR-0004 se adelanta por mandato del acta D14; la numeración sigue siendo única e irrepetible.*

## Registro de verificaciones de consistencia ADR↔capítulos

| Fecha | Evento | Resultado |
|---|---|---|
| 2026-07-17 | Pre-gate 1.2 | ADR-0001: los 7 capítulos en `impacta` están `No iniciado` → pendientes de creación (regla transitoria 1.2 §7); ninguno desactualizado |
| 2026-07-17 | Aceptación ADR-0001 | Sin capítulos desactualizados; los 7 impactados nacerán conformes (sus esqueletos ya lo listan en "Decisiones aplicables") |
| 2026-07-17 | Aceptación ADR-0004 | 3.1 Aprobado nace conforme (P-ARQ-3, §2.1); 3.3, 3.4, 3.6 y 6.1 `No iniciado` → regla transitoria 1.2 §7 |
