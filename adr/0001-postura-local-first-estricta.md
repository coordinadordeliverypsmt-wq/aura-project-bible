---
numero: ADR-0001
titulo: "Arquitectura local-first estricta"
estado: proposed
fecha: 2026-07-17
decisor: "Mauricio (CEO)"
proponente: "Fable (CTO)"
impacta: ["3.1", "3.2", "3.5", "4.1", "4.2", "5.5", "7.4"]
origen: "Acta 2026-07-17, D1"
supersede: "—"
superseded-por: "—"
---

# ADR-0001 — Arquitectura local-first estricta

## Contexto

AURA custodiará el activo más sensible imaginable: la memoria de años de la vida de su usuario, más credenciales, documentos, fotografías y control de dispositivos físicos. El CEO fijó la privacidad como pilar fundamental (acta D1). Una postura de datos ambigua contaminaría cada decisión posterior de memoria, orquestación y despliegue.

## Alternativas consideradas

### A. Nube-primero
Pros: operación simple, sin hardware propio. Contras: datos íntimos en infraestructura de terceros; contradice frontalmente D1. **Rechazada.**

### B. Híbrido permisivo (datos en nube salvo lo marcado sensible)
Pros: flexible. Contras: la clasificación por excepción falla hacia el lado inseguro; carga cognitiva permanente. **Rechazada.**

### C. Local-first estricto (elegida)
Pros: soberanía total por defecto; la excepción requiere autorización explícita. Contras: exige hardware local dimensionado y disciplina de sincronización.

## Decisión

AURA adopta **local-first estricto**:

1. Información personal, memoria, documentos, fotografías, credenciales, dispositivos, automatizaciones y datos privados residen **siempre** bajo control del usuario, en su hardware.
2. La nube solo puede usarse para: (a) consultar modelos de IA, (b) sincronizar información **previamente autorizada**, (c) respaldos **cifrados**, (d) servicios externos **explícitamente aprobados** por el CEO.
3. Toda comunicación va cifrada, sin excepción.
4. Todo dato enviado a un modelo de IA externo pasa antes por minimización (reglas en el capítulo 5.5).

## Consecuencias

**Positivas:** soberanía de datos; superficie de exfiltración mínima; cumplimiento de D1 verificable por diseño.
**Negativas:** inversión en hardware local (dimensionamiento en 3.2/7.4); complejidad de sincronización selectiva; los modelos frontier solo se usan vía API con minimización previa.
**Riesgos aceptados:** el hardware local es un punto de falla físico — se mitiga con la estrategia de respaldos cifrados (3.5, 7.4).

## Trazabilidad

Capítulos a actualizar: 3.1 (principio estructural), 3.2 (topología), 3.5 (residencia y cifrado), 4.1 (memoria local), 4.2 (política de enrutamiento por privacidad), 5.5 (fronteras y minimización), 7.4 (respaldos).
