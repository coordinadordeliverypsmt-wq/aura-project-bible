---
documento: "DECISION_REQUIRED — construir D-M-1 A′ (recuperación exacta de memoria N1)"
tipo: "Propuesta de decisión para el CEO. NADA implementado."
fecha: 2026-10-12
mantenido-por: "Dirección Técnica (sesión de asistencia)"
decide: "CEO (Mauricio)"
remite: "milestones/m3-entry/DP-D-M-1-RECUPERACION-EXACTA.md (análisis completo, no se duplica aquí)"
---

# ¿Autorizar la construcción de D-M-1 A′?

**Estado:** RESUELTA por el CEO el 2026-10-12: `decisiones/2026-10-12-D-M-1-aprobacion-construccion.md` autoriza construir A′ (con sus límites). La afirmación de §1 «ninguna acta aprueba construirlo» era cierta al redactar este expediente y quedó superada ese mismo día. Nota añadida el 2026-10-22 al contrastarlo con el acta; el resto se conserva como registro.

Preparada porque el desarrollo de construcción autorizado se agotó (D-AMP-2 y M3.2a-exportar verificados)
y D-M-1 A′ es el único candidato técnico restante del barrido. **No se ejecuta: falta autorización.**

## 1 · Estado de autorización (verificado 2026-10-12)
- `DP-D-M-1-RECUPERACION-EXACTA.md:3-11`: **APROBADO COMO DOCUMENTO DE DECISIÓN** (CEO 2026-08-03), pero
  **«la implementación NO está autorizada todavía»**, **supeditada a resolver `D-M-2` ANTES**.
- `DEUDA-N1-RECUPERADOR.md`: lo registra como **«pendiente de aprobación del CEO»**.
- **Ninguna acta aprueba construirlo** (verificado en `decisiones/`).
- **Precondición D-M-2: RESUELTA (verificado 2026-10-12).** Aunque el DP de D-M-2 decía «Op-5 NO
  AUTORIZADA» (2026-08-03), el código HOY ya la impide: `core/intencion.py:548` `debe_almacenarse` hace
  `if es_interrogativa(texto): return False`, y `orchestrator.py:3253/3278/3288` no escribe el eco
  «usuario dijo: …» cuando `destino_de_memoria` es `None` (pregunta). La prueba
  `tests/integration/test_correcciones_producto.py:65-105`
  (`test_DM2_repetir_una_pregunta_NO_desactiva_ADR0014`) lo confirma en ejecución (repite la pregunta en 2
  turnos y verifica `recall == []`). **La precondición explícita de D-M-1 queda satisfecha.**

## 2 · Alcance (si se aprobara)
Sustituir la generación de candidatos de `PersistentMemory.recall` por **A′: filtro por prefijo con cota
de seguridad α=1** (si el prefijo visitaría > N posteos, barrido completo; si no, poda exacta por el
principio del palomar). **Cambia qué recuerdos se EXAMINAN, nunca el criterio de aceptación**
(`_COBERTURA_MINIMA`, tokenización, palabras vacías intactos). Impacto arquitectónico **nulo** (una
función). No toca ADR-0014 (lo refuerza), MA.2a (la respeta), ni el formato persistido.

## 3 · Defecto que cierra
Falsos negativos en **régimen ubicuo**: con >256 recuerdos que comparten un término **de contenido**,
un recuerdo cualificado nunca entra en candidatos → `recall` devuelve vacío → ADR-0014 hace que **AURA
afirme que no recuerda algo que sí tiene guardado**. Medido en corpus sintético: resultado erróneo en
**9,8 %** de consultas (36 de 39 fallos devolvían 3 resultados completos y equivocados). El dato no se
pierde del disco; falla el acceso.

## 4 · Evidencia de uso real: AUSENTE (dato decisivo)
El propio DP (§2.4, §7.2) `[HIPO]`: el régimen se alcanza hacia el **turno ~257 (~5 días de uso)** y
exige una palabra de contenido por encima de 256 recuerdos — **no se ha observado**; *«cero en uso real,
porque nadie ha usado AURA todavía»*. La regla del CEO (2026-08-04) es que **el desarrollo lo guía la
evidencia de uso real, no las ideas**. Construir D-M-1 ahora sería trabajo anticipado.

## 5 · Riesgos y pruebas
- **Riesgo:** A′ examina recuerdos que el defecto ocultaba → podrían aflorar **FP críticos** fuera de la
  batería (que no ejercita el régimen ubicuo). Regresión sobre la batería: **nula medible (0/77)**.
- **Pruebas exigidas (del DP §6/§7):** corrección contra **fuerza bruta** como oráculo (B), 18 000 corpus
  aleatorios, determinismo (SHA-256 entre semillas), mutación del incremento, QG. Criterio de aceptación:
  0 discrepancias vs. fuerza bruta + sin FP críticos nuevos + MA.2a respetada (cota activada ~0 %).

## 6 · Recomendación y consecuencias
**Recomiendo APLAZAR (opción B)** hasta que: (a) D-M-2 esté **resuelto y verificado** (precondición
explícita), y (b) haya **evidencia de uso real** del régimen (telemetría: consultas que activen el
defecto, o >256 recuerdos con término de contenido). Es coherente con la regla de 2026-08-04 y con el
propio DP.

| Opción | Consecuencia |
|---|---|
| **A · Aprobar construcción ahora** | La precondición D-M-2 ya está satisfecha (verificado), así que es viable; pero cierra un defecto real **aún no observado en uso real** y asume el riesgo de FP fuera de la batería. Construir sin evidencia de uso roza la regla de 2026-08-04. |
| **B · Aplazar (recomendada)** | El defecto queda **latente pero contenido**: falla hacia el silencio y ADR-0014 lo cubre (AURA dice «no recuerdo» en vez de fabricar). Coste nulo hasta que el uso real lo active. Se construye cuando haya evidencia. |
| **C · Otra vía** | p. ej. resolver/confirmar D-M-2 primero y re-evaluar D-M-1 con telemetría. |

**Esta propuesta no concede nada:** no autoriza obra, no toca código, no fabrica aprobación. Con tu voto
(A/B/C) se procede en consecuencia.
