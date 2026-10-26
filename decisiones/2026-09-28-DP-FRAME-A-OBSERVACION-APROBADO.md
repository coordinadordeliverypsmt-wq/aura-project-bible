---
documento: "DP — Frontera FRAME → OBSERVACIÓN"
tipo: "DECISION PACKAGE — APROBADO por el CEO 2026-09-28 (Alt B · bajo demanda · imagen-cero) e IMPLEMENTADO"
fecha: 2026-09-28
decide: "CEO (Mauricio)"
base: "milestones/m3-entry/CUELLO-DE-BOTELLA-PERCEPCION.md · acta 2026-09-27 percepción visual · HEAD 6dad6af"
metodologia: "DEMOSTRAR → DECIDIR → IMPLEMENTAR (esta sesión: DECIDIR)"
---

# DP — Frontera FRAME → OBSERVACIÓN

> Convención de evidencia (D47): [HECHO]=medido · [ALT]=alternativa · [PROP]=propuesta · [HIPO]=no verificado.
> Este documento NO presupone aprobación; ninguna alternativa es la decisión hasta que el CEO la marque.

## 1. Problema
[HECHO] La percepción visual de AURA adquiere frames reales pero **no tiene consumidor de sistema**: el
resultado (`LecturaVisual`) termina en `obs.log` y se descarta. AURA (orchestrator, memoria, superficie
conversacional, `entorno.py`) nunca recibe lo percibido. Es capacidad de laboratorio, no de sistema.

## 2. Evidencia existente
- [HECHO] Frame real desde 2 fuentes: webcam .38 (640×480, V4L2) y YCC/.110 (1280×720, RTSP), mismo puerto
  `PercepcionVisual`. (`milestones/m3-entry/MAPA-ECOSISTEMA-FISICO.md`, addenda 2026-09-28.)
- [HECHO] `PercepcionVisual` no aparece en `composicion.py`/`orchestrator.py`; no publica al bus; no emite
  `Senal`; no escribe memoria; no alimenta `entorno.py`. Único efecto: `obs.log`. (grep, HEAD 6dad6af.)
- [HECHO] `PercepcionVisual` ya reduce el frame a metadatos (`LecturaVisual`: frame_recibido, fuente, ancho,
  alto; persona=None, identidad=None) y no guarda la imagen.
- [HECHO] Contratos reales disponibles: `bus.publish(Event)` (`contracts.py`/`bus.py`); memoria
  `memory.write(user_id, kind, content, provenance)`; recuperación M8 `DOMINIO_EJECUCION`; superficie de
  consulta de entorno `es_consulta_de_entorno` (patrón para «¿qué ves?»).

## 3. Estado actual
`fuente → frame → LecturaVisual → obs.log → (fin)`. Política por superficie (`politica_superficie.py`,
deny-by-default) ya gobierna si una superficie puede procesarse; se probó con .110 autorizada por el CEO.

## 4. Frontera arquitectónica actual
Termina en `PercepcionVisual.percibir()`. No hay tipo «Observación» ni consumidor.

## 5. Objetivo (a decidir)
[PROP] Introducir una **OBSERVACIÓN AMBIENTAL** mínima derivada de `LecturaVisual`, consumible por AURA,
gobernada por `politica_superficie`, reducida a metadatos, para que AURA pueda **responder** sobre lo que
percibió («recibí un frame de la cámara X, 1280×720; no interpreto su contenido»).

## 6. No objetivos (esta etapa)
persona · identidad · evento · movimiento · reconocimiento · clasificación semántica · audio ·
almacenamiento de imagen/vídeo/frame · vigilancia continua · acción. Se mantiene:
`observación ≠ evento ≠ persona ≠ identidad ≠ comprensión ≠ decisión`.

## 7. Contrato conceptual de Observación [PROP]
Campos mínimos: `fuente`, `superficie`, `tipo_de_fuente`, `ancho`, `alto`, `timestamp`, `trace_id`.
Prohibido en esta etapa: píxeles, recorte, hash de imagen, persona, identidad, etiqueta semántica.
Productor: `PercepcionVisual` (solo si la política autoriza la superficie). Consumidor: ver §8.

## 8. Alternativas (sin ganador)
- **A · solo audit** — Observación queda en `obs.log`. Resuelve trazabilidad; NO la hace consumible.
  Impacto arq/memoria/privacidad: nulo. Autonomía: no aumenta. Complejidad: mínima. Reversible: total.
  Riesgo vigilancia: nulo. Es prácticamente el estado actual.
- **B · audit + contexto efímero** — la Observación vive en la ventana de trabajo del turno (como DR-4),
  no persiste. AURA puede responder «¿qué ves?» en la conversación. Privacidad: alta (no persiste).
  Autonomía: habilita respuesta contextual. Complejidad: baja-media (tocar orchestrator). Reversible: alta.
  Riesgo vigilancia: bajo (bajo demanda).
- **C · audit + memoria** — la Observación se escribe con `memory.write` (kind propio, provenance visual).
  Habilita recordar «qué vi». Riesgo: retención acumulada; roza perfiles; choca con ALERTA-002 si la
  observación llevara personas (no en esta etapa, pero el canal quedaría abierto). Reversible: media.
- **D · Señal/evento del sistema** — publicar un `Event` al bus / emitir `Senal`. `Senal` es de aprendizaje
  del USUARIO y **prohíbe terceros (ALERTA-002)**: una observación visual NO debe ir por `Senal`. Un `Event`
  del bus sería posible pero introduce un flujo pasivo continuo. Riesgo vigilancia: mayor. Complejidad: media.
- **E · bajo demanda sin estado** — AURA percibe solo cuando se le pregunta/ordena; la Observación se
  produce, se responde y se descarta (ni memoria ni contexto persistente). Máxima privacidad; mínima
  autonomía proactiva. Reversible: total.

## 9. Comparación técnica (resumen)
| Alt | Consumible | Persiste | Privacidad | Autonomía | Complejidad | Riesgo vigilancia | Reversible |
|---|---|---|---|---|---|---|---|
| A | no | no | máx | nula | mínima | nulo | total |
| B | sí (turno) | no | alta | media | baja-media | bajo | alta |
| C | sí | sí | media | media-alta | media | medio | media |
| D | sí (pasivo) | según | media | media | media | mayor | media |
| E | sí (respuesta) | no | máx | baja | baja | mínimo | total |

## 10. Retención (obligatorio)
[PROP] «imagen cero por defecto»: imagen y frame NUNCA se persisten (ya es así); la Observación es solo
metadatos. Diferenciar: no-almacenar (imagen/frame) · efímero-en-turno (Alt B/E) · metadatos-en-memoria
(Alt C, requiere política de retención explícita). El audit log ya registra el hecho hoy.

## 11. Privacidad
Sin píxeles ni personas en esta etapa ⇒ riesgo bajo. La política por superficie sigue siendo el guardián
(deny-by-default; interior requiere autorización explícita del propietario). Alt C/D abren camino a
retención/pasividad y exigen cuidado extra.

## 12. Bajo demanda vs continuo
[PROP] **Bajo demanda** (reactiva) primero: HC-1 es limitado (Celeron N4020, ~3.6 GiB); continuo produce
ruido, coste y deriva a vigilancia sin utilidad demostrada. Continuo NO se propone en esta etapa.

## 13-16. Integración
- Orchestrator [PROP, Alt B/E]: una consulta tipo «¿qué ves en la cámara X?» (patrón `es_consulta_de_entorno`)
  dispara `percibir` bajo política y devuelve la Observación como respuesta del turno.
- Bus [ALT D]: posible, no propuesto en esta etapa (introduce flujo pasivo).
- Memoria [ALT C]: `memory.write` posible; requiere decisión de retención; no propuesto por defecto.
- Superficie conversacional: es el consumidor natural en Alt B/E (AURA responde; no actúa).

## 17. Impacto sobre autonomía
[HIPO] Conectar percepción **habilita** una cadena futura (percepción→comprensión→decisión→acción) que hoy
está cortada de raíz. Por sí sola, una Observación bajo demanda NO aumenta «trabajo sin intervención»; es
un **prerequisito**, no la autonomía en sí. Más frames/tests ≠ más autonomía.

## 18. Riesgos
Deriva a vigilancia (mitiga: bajo demanda + sin persistencia); confusión observación↔persona (mitiga:
contrato sin identidad); retención acumulada (mitiga: imagen-cero + Alt B/E); consumo en HC-1 (mitiga:
reactiva); acoplar producto a una fuente concreta (mitiga: usar el puerto `FuenteDeVision` ya agnóstico).

## 19. Seguridad
Política por superficie sigue gobernando; sin píxeles fuera de memoria; sin credenciales en artefactos;
la YCC/.110 emite sin contraseña en LAN (observación de seguridad del propietario, ajena a este DP).

## 20. Pruebas requeridas (si se aprueba)
RED: «percibir bajo demanda produce Observación consumible»; política sigue negando superficie no
autorizada; la Observación NO lleva persona/identidad/imagen. Mutación: no emitir sin frame; no persistir
imagen; observación no afirma persona. Regresión: cadena existente (.38/.110) intacta. Sin batería nueva
de producto hasta implementar.

## 21. Criterios de aceptación (si se aprueba)
AURA responde a «¿qué ves en la cámara X?» con una Observación real (fuente+dimensiones+timestamp),
gobernada por política, sin imagen almacenada, sin identidad; comportamiento demostrado, no «tests pasan».

## 22. Reversibilidad
Alt A/B/E: total o alta (aislado en orchestrator + puerto existente). Alt C/D: media (retención/flujo).

## 23. Decisión requerida
El CEO elige: **(i)** ¿se conecta la percepción? **(ii)** ¿qué alternativa (A–E)? **(iii)** ¿bajo demanda
o continuo? **(iv)** ¿retención (imagen-cero + efímero, o con memoria)? Recomendación de evidencia [PROP]:
**Alt B (audit + contexto efímero) + bajo demanda + imagen-cero** — mínima, reversible, sin vigilancia,
habilita respuesta contextual. No es decisión hasta que el CEO lo marque.

## 24. Próximo paso si se aprueba
RED→GREEN mínimo del consumidor (Observación efímera en el turno vía orchestrator), mutación, sin memoria
ni evento; después evaluar la grada siguiente (evento) con su propio DP.

## Contradicciones con gobierno
Ninguna detectada con Bible/ADR/CHECKPOINT. Coherente con el acta de percepción visual (2026-09-27) y su
§10 (retención documentada antes de implementar). ALERTA-002 excluye explícitamente la vía `Senal` (Alt D).
