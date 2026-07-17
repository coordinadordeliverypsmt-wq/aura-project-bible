---
numero: ADR-0001
titulo: "Postura local-first estricta"
estado: accepted
fecha: 2026-07-17
fecha-resolucion: 2026-07-17
decisor: "Mauricio (CEO)"
proponente: "Fable (CTO)"
impacta: ["3.1", "3.2", "3.5", "4.1", "4.2", "5.5", "7.4"]
origen: "Acta 2026-07-17, D1"
reabre: "—"
supersede: "—"
superseded-por: "—"
motivo-rechazo: "—"
---

# ADR-0001 — Postura local-first estricta

## Contexto

AURA custodiará el activo más sensible imaginable: la memoria de años de la vida de su usuario, más credenciales, documentos, fotografías y control de dispositivos físicos. El CEO fijó la privacidad como pilar fundamental (acta D1). Una postura de datos ambigua contaminaría cada decisión posterior de memoria, orquestación y despliegue.

*Formato de alternativas:* los 4 niveles del acta D3 **no aplican** — la decisión de fondo ya fue tomada por el CEO en acta; este ADR solo la formaliza. (Criterio reutilizable por ADR-0003 y ADR-0004, en la misma situación.)

## Alternativas consideradas

### A. Nube-primero
Pros: operación simple, sin hardware propio. Contras: datos íntimos en infraestructura de terceros. **Descartada por el proponente:** contradice frontalmente la D1.

### B. Híbrido permisivo (datos en nube salvo lo marcado sensible)
Pros: flexible. Contras: la clasificación por excepción falla hacia el lado inseguro; carga cognitiva permanente. **Descartada por el proponente:** incompatible con la D1.

### C. Local-first estricto (formaliza la D1)
Pros: soberanía total por defecto; la excepción requiere autorización explícita. Contras: exige hardware local dimensionado y disciplina de sincronización.

## Decisión

**Contenido de la D1 (texto del CEO):**

1. La información personal, memoria, documentos, fotografías, credenciales, dispositivos, automatizaciones y datos privados permanecen **siempre bajo control del usuario**.
2. La nube solo puede usarse para: (a) consultar modelos de IA, (b) sincronizar información **previamente autorizada**, (c) respaldos **cifrados**, (d) servicios externos **explícitamente aprobados**.
3. Toda comunicación va cifrada, sin excepción.

**Reglas adicionales propuestas por el CTO** (no formaban parte de la D1; **aceptadas expresamente por el CEO en el gate del 2026-07-17**):

4. "Bajo control del usuario" se interpreta por defecto como hardware propio del usuario; el uso de infraestructura remota controlada por el usuario requiere aprobación explícita.
5. Todo dato enviado a un modelo de IA externo pasa antes por minimización (reglas de detalle en el capítulo 5.5).

## Consecuencias

**Positivas:** soberanía de datos; superficie de exfiltración mínima; cumplimiento de la D1 verificable por diseño.
**Negativas:** inversión en hardware local (dimensionamiento en 3.2/7.4); complejidad de sincronización selectiva; los modelos frontier se usan vía API — con minimización previa si se acepta la regla 5.
**Riesgos aceptados:** el hardware local es un punto de falla físico — se mitiga con la estrategia de respaldos cifrados (3.5, 7.4).

## Impacto (acta D11)

| Dimensión | Impacto |
|---|---|
| Seguridad | Positivo alto: superficie de exfiltración mínima; los secretos nunca salen del perímetro |
| Privacidad | Positivo máximo: materializa el pilar D1 por diseño |
| Modularidad | Neutro: exige que cada plugin declare su frontera local/nube (refuerza contratos, D10) |
| Costo | Negativo controlado: hardware local propio + APIs de inferencia; sin costos de almacenamiento en nube |
| Experiencia de usuario | Mixto: latencia local excelente; funciones frontier dependen de conectividad y minimización |
| Mantenimiento futuro | Negativo controlado: el usuario opera su propio hardware (respaldos y actualizaciones en 7.4) |

## Trazabilidad

Capítulos a actualizar: 3.1 (principio estructural), 3.2 (topología), 3.5 (residencia y cifrado), 4.1 (memoria local), 4.2 (enrutamiento por privacidad), 5.5 (fronteras y minimización), 7.4 (respaldos) — todos `No iniciado`: aplica la regla transitoria de 1.2 §7 (nacen conformes al ADR).
Módulos de código afectados (futuro): —
