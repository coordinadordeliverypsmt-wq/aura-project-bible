---
numero: ADR-0003
titulo: "Listas de Autonomía (verde/roja) y Human-in-the-Loop"
estado: accepted
fecha: 2026-07-18
fecha-resolucion: 2026-07-18
decisor: "Mauricio (CEO)"
proponente: "Fable (CTO)"
impacta: ["5.3", "4.3", "6.4"]
origen: "Acta D4 (autonomía) y D9 (HITL); creado por mandato de la auditoría HI-1"
reabre: "—"
supersede: "—"
superseded-por: "—"
motivo-rechazo: "—"
---

# ADR-0003 — Listas de Autonomía (verde/roja) y Human-in-the-Loop

## Contexto

La auditoría (HI-1) detectó que el plan de formalización (1.2 §9) asignó un ADR a la política de autonomía (D4), nunca creado; el 5.3 la materializaba sin ADR. El CEO autorizó consolidar las Listas de Autonomía como **decisión arquitectónica permanente**.

*Formato de alternativas:* los 4 niveles del acta D3 no aplican — la decisión de fondo ya fue tomada por el CEO en las actas D4/D9; este ADR la formaliza (criterio de ADR-0001).

## Decisión

Se consolida la política de autonomía como decisión arquitectónica permanente:

**Lista verde (ejecución automática, acta D4, texto del CEO):** *"automatizaciones, encender/apagar dispositivos, consultas, recordatorios, monitoreo, organización."*

**Lista roja (confirmación humana SIEMPRE, acta D4, texto del CEO):** *"pagos, compras, transferencias, eliminación de información, apertura de cerraduras, mensajes enviados a terceros, acciones legales, acciones financieras."*

Reglas permanentes: toda acción pasa por el Gestor de Permisos (5.3) antes de tocar un adaptador; la lista roja exige confirmación con **tolerancia cero a falsos negativos** (2.5 §5.4); toda acción es auditable, explicable y reversible (D9, P-ARQ-1); los niveles superiores de autonomía solo se habilitan por política y decisión del usuario/CEO, nunca automáticamente.

## Consecuencias

**Positivas:** política de autonomía estable y trazable; ningún agente/plugin ejecuta sin pasar por Permisos. **Negativas:** confirmaciones para lista roja añaden fricción (deseada). **Riesgos aceptados:** ninguno nuevo; materializa decisiones vigentes.

## Impacto (acta D11 — obligatorio)

| Dimensión | Impacto |
|---|---|
| Seguridad | Positivo máximo: barrera obligatoria ante acciones de alto impacto |
| Privacidad | Positivo: mensajes a terceros y borrados requieren confirmación |
| Modularidad | Neutro: el Gestor de Permisos es un contenedor del núcleo (3.2) |
| Costo | Nulo |
| Experiencia de usuario | Mixto: fricción deseada en lista roja; fluidez en verde |
| Mantenimiento futuro | Positivo: política central única, no dispersa |

## Trazabilidad

Capítulos: 5.3 (materialización), 4.3 (agentes), 6.4 (acciones de sistema/hogar). Código futuro: Gestor de Permisos del walking skeleton.
