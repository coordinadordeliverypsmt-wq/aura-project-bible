---
numero: ADR-0004
titulo: "Principio de Evolución Permanente y arquitectura modular"
estado: accepted
fecha: 2026-07-17
fecha-resolucion: 2026-07-17
decisor: "Mauricio (CEO)"
proponente: "Fable (CTO), por mandato del CEO (acta D14)"
impacta: ["3.1", "3.3", "3.4", "3.6", "6.1"]
origen: "Actas D10 y D14"
reabre: "—"
supersede: "—"
superseded-por: "—"
motivo-rechazo: "—"
---

# ADR-0004 — Principio de Evolución Permanente y arquitectura modular

## Contexto

AURA debe vivir y crecer durante muchos años (D10: sistema vivo) integrando tecnologías que hoy no existen. El CEO mandató registrar como ADR independiente el principio de Evolución Permanente (D14). Sin reglas de contrato estables, cada integración nueva erosionaría el sistema hasta el rediseño — exactamente lo que el brief prohíbe.

*Formato de alternativas:* los 4 niveles del acta D3 **no aplican** — la decisión de fondo ya fue tomada por el CEO en actas (D10, D14); este ADR la formaliza (criterio establecido en ADR-0001).

## Alternativas consideradas

### A. Arquitectura pragmática iterativa (modular "cuando duela")
Pros: velocidad inicial. Contras: los límites artificiales se descubren tarde y el costo de reemplazo crece con cada release. **Descartada por el proponente:** contradice D10 y D14.

### B. Evolución Permanente por contrato (formaliza D10 + D14)
Pros: reemplazo y ampliación sin afectar el ecosistema; longevidad. Contras: costo inicial mayor; más contratos que mantener.

## Decisión

**Contenido de las actas D10 y D14 (texto del CEO):**

1. Ningún módulo podrá diseñarse con límites artificiales.
2. Todo componente deberá poder ser reemplazado o ampliado sin afectar el resto del ecosistema.
3. La arquitectura deberá soportar crecimiento durante muchos años; la compatibilidad hacia atrás es prioridad.
4. Ninguna integración será exclusiva de un proveedor.
5. Todo componente expondrá interfaces estables (API o contratos) para permitir reemplazos futuros.
6. La modularidad es obligatoria; no existirán componentes monolíticos; toda inteligencia será desacoplada.
7. Siempre que sea posible se privilegiará la modularidad sobre la simplicidad inmediata.

**Reglas operativas propuestas por el CTO** (no formaban parte de las actas; **aceptadas expresamente por el CEO en el gate del 2026-07-17**):

8. "Interfaz estable" significa: contrato versionado con SemVer; toda ruptura de compatibilidad exige ADR (1.2 §3.2) y un periodo de convivencia con la versión anterior.
9. "Límite artificial" significa: toda restricción no impuesta por una decisión del CEO, una ley física/técnica o un ADR — los supuestos de capacidad (nº de usuarios, dispositivos, proveedores) se declaran en el contrato, nunca se cablean en el código.
10. **Salvaguarda anti-sobre-ingeniería:** la modularidad prevalece "siempre que sea posible" (D14), pero cada módulo o capa nueva debe justificarse por necesidad presente o por una evolución prevista **documentada**; la modularidad especulativa sin caso de evolución identificado se rechaza en revisión. Un equipo de 1 humano no puede mantener módulos que no defienden su existencia.

## Consecuencias

**Positivas:** el sistema sobrevive al reemplazo de cualquier proveedor, protocolo o módulo; las 9 capacidades del MVP nacen sobre contratos que R2-R4 amplían sin romper.
**Negativas:** costo inicial mayor por contrato; disciplina de versionado permanente.
**Riesgos aceptados:** sobre-modularización (mitigada por la regla 10); latencia de contratos frente a prototipado rápido.

## Impacto (acta D11)

| Dimensión | Impacto |
|---|---|
| Seguridad | Positivo: módulos aislados limitan el radio de un compromiso; contratos auditables |
| Privacidad | Positivo: fronteras de datos explícitas por contrato (refuerza ADR-0001) |
| Modularidad | Positivo máximo: es el objeto del ADR |
| Costo | Negativo controlado: más diseño inicial; menos costo de reemplazo futuro |
| Experiencia de usuario | Neutro: invisible si los contratos cumplen; positivo a largo plazo (capacidades nuevas sin regresiones) |
| Mantenimiento futuro | Positivo máximo: reemplazo pieza a pieza durante años |

## Trazabilidad

Capítulos a actualizar: 3.1 (principios), 3.3 (contratos de eventos/API), 3.4 (contrato de plugins), 3.6 (criterios de stack), 6.1 (contrato de adaptador) — 3.1 en borrador nace conforme; el resto `No iniciado` (regla transitoria 1.2 §7).
Módulos de código afectados (futuro): —
