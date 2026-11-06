---
documento: "Decision Package — Frontera voz→acción (último eslabón del umbral de integración)"
tipo: "DECISION PACKAGE — BORRADOR. NO APROBADO. Prepara la decisión; no la toma."
fecha: 2026-10-04
autor: "APUS-5 (CTO)"
estado: "APROBADO — OPCIÓN C (CEO, 2026-10-04). EN EJECUCIÓN."
origen: "CHECKPOINT 2026-09-28 «Cierre del umbral de integración — hasta la frontera voz→acción» · mapa maestro §14 (Umbral: «pendiente de decisión voz→orden») y §18-19 («Voz → acción reversible sin modelo — ¿ampliar ordenes.py a lista verde reversible?»)"
---

# DP — Frontera voz→acción

## 1. Por qué es el siguiente punto REAL de la línea evolutiva

Reconstrucción hecha desde las fuentes el 2026-10-04, no desde la última tarea escrita:

- **Antes de la pausa** (CHECKPOINT 2026-09-28):
  - El umbral PERSONA → OYE → ESCUCHA → RECUERDA → ENTIENDE → RESPONDE quedó **integrado y verde**.
  - La cadena por TEXTO orden → Motor Único → HA → efecto verificado (TV real on↔off releída) → memoria del resultado
    también quedó **integrada y verde**.
  - **Solo falta unir VOZ→ACCIÓN física**, que se marcó DECISION_REQUIRED.
- **La pausa** (2026-09-29) se debió a CM1: ≤ 800 ms es inalcanzable en HC-1, y se pidió hardware con aceleración o AVX2.
- **NODO-01** (2026-10-04) **no** es ese hardware. El Atom N450 queda por debajo de HC-1 en todas las métricas de cómputo
  [EJEC, `--nodos`]:

  | Métrica | N450 | HC-1 |
  |---|---|---|
  | ram_mb | 986 | 3719 |
  | nucleos_fisicos | 1 | 2 |
  | isa_sse4_2 | 0 | 1 |
  | proceso_bits | 32 | 64 |

  Amplía la presencia distribuida, los periféricos y el disco. **No desbloquea** STT, TTS, un modelo mayor ni la
  memoria N2 (el umbral de N2 es ram_mb ≥ 8000). CM1 sigue igual.
- **Conclusión:** el eslabón pendiente de la línea original no depende del hardware. Es esta frontera, y es de gobierno.

## 2. Qué existe ya (no se construye desde cero)

`core/orchestrator.py`:
- **Propuesta.** Una orden de hogar dicha se convierte en una **propuesta** (`_propuestas_de_hogar`, que vive **un** turno).
- **Confirmación.** «Sí» o «no» se interpreta con `hogar.confirmacion`.
- **Llave.** Con `voz_actua_en_hogar = False` (`orchestrator.py:1511`), un «sí» se audita («confirmado y DETENIDO:
  pendiente de decision del CEO») y responde ABSTENCIÓN. A propósito, **ninguna variable de entorno la enciende**.
- **Ejecución.** Con la llave abierta, ejecuta por `_despachar_orden`, que pasa por el Motor Único, los permisos y el efecto
  verificado (ya probado por texto con la TV real).

## 3. El riesgo que motivó cerrar la llave

El STT (faster-whisper) **puede fabricar texto que nadie dijo**: alucina con audio corto o ruidoso
(`DP-PERCEPCION-MULTIMODAL-CONSOLIDADO.md` §107). Para que la casa actúe sin que nadie lo haya pedido, el STT tendría
que fabricar **dos** cosas en turnos consecutivos: una orden reconocible y una confirmación.

## 4. Opciones

| Opción | Qué cambia | Salvaguardas | Riesgo residual |
|---|---|---|---|
| **A · Mantener cerrada** | Nada | — | El umbral nunca se cierra por voz |
| **B · Abrir solo la lista verde reversible** (TV on/off y similares de D4), con salvaguardas técnicas | La llave se abre por composición explícita, no por configuración | (1) La propuesta repite en voz alta dispositivo y acción. (2) El «sí» solo vale en el turno inmediato (ya es así). (3) Se descartan transcripciones por debajo de un umbral de confianza o de un mínimo de duración (`no_speech_prob`/`avg_logprob` de whisper), **medido antes** de abrir. (4) La acción roja sigue exigiendo HITL siempre (ADR-0003) | Bajo: acción reversible, confirmada y verificada |
| **C · Abrir B en modo «solo con presencia confirmada»** | Igual que B, y además exige la palabra de activación en el turno de la orden | B + wake word | Muy bajo; más fricción |

**Recomendación técnica:** B, empezando por **un solo dispositivo** (la TV de la sala, ya integrada y verificada). Antes,
la medición de §5.

## 5. Precondición técnica medible (sin abrir nada)

Si se aprueba B o C, el primer paso es **medir** la tasa de órdenes fabricadas por el STT con ruido real de la casa: en
memoria, sin guardar audio. Con esa cifra se fija el umbral de confianza de la salvaguarda (3).

Pruebas exigidas: RED de cada salvaguarda, mutación de la llave y de cada salvaguarda, y E2E por el aire con la TV real
(voz → propuesta → «sí» → efecto releído en HA → «¿qué hiciste?»).

## 6. Qué NO cambia

- CM1 no se toca.
- PARADA se respeta: una escritura no pasiva sigue bloqueada.
- La lista roja sigue exigiendo HITL (ADR-0003), y la ejecución pasa siempre por el Motor Único (ALERTA-005).
- El LLM no decide.
- La TV .20 (`media_player.samsung_6_series_55_un55ku6000`) NO entra en el alcance. Corrección: no está «congelada»; se integró en HA el 2026-09-28 (CHECKPOINT L6662). Por eso la allowlist por ENTIDAD de §8 es necesaria.

## 7. Decisión requerida (CEO)

1. ¿A (mantener cerrada), B (abrir la lista verde reversible con salvaguardas) o C (B + wake word en el turno de la
   orden)?
2. Si es B o C: ¿se autoriza empezar **solo** con la TV de la sala y la medición previa de §5?

## 8. Decisión del CEO (2026-10-04): OPCIÓN C — contrato técnico

El alcance de la autorización es exactamente este:
- **dispositivo:** la TV de la sala (`media_player.tv_sala_fmilia_medina_un43ru7100fxza`);
- **acciones:** solo `encender_dispositivo` y `apagar_dispositivo` (lista verde reversible, `permissions.py`);
- **condición de voz:** la palabra de activación tiene que estar en el turno de la orden.

**Fuera de este alcance:** cualquier otra entidad (incluida la TV .20), cualquier acción no verde y cualquier ruta que no
pase por el Motor Único.

**C1 · Activación como hecho del turno.**
- `handle_utterance(user_id, audio, trace_id, activado: bool = False)` publica `activado` en el payload de
  `perception.turn_end`.
- Solo la escucha continua (`_escuchar_continuo`, tras `esperar_llamada()` verdadera) pasa `activado=True`.
- Pulsar-para-hablar y el teclado pasan `False`.
- Una orden de hogar **hablada** sin `activado` no propone ni ejecuta: AURA responde que la llamen por su nombre.
- Un «sí» hablado sin `activado` tampoco ejecuta.

**C2 · Llave por ENTIDAD, abierta por composición.**
- `voz_actua_en_hogar: bool` pasa a ser `voz_actua_en: frozenset[str]` (vacío por defecto en el orquestador).
- `composicion.componer()` la fija a la constante `VOZ_ACTUA_EN = frozenset({"media_player.tv_sala_fmilia_medina_un43ru7100fxza"})`,
  con un comentario que cita esta decisión.
- No la cambia ninguna variable de entorno.
- La ejecución por voz exige que la entidad resuelta pertenezca a `voz_actua_en`. Si no pertenece: ABSTENCIÓN auditada,
  igual que hoy con la llave cerrada.

**C3 · Resolución explícita.**
- En voz, «la tele / la televisión» sin nombre resuelve **solo** dentro de `voz_actua_en` (hoy, la TV de la sala).
- La propuesta **nombra** el dispositivo y la acción («¿Apago la TV de la sala?»).

**C4 · Confianza del STT.**
- `VoiceAdapter` expone `ultima_confianza: dict | None` con `no_speech_prob` (máximo por segmento) y `avg_logprob`
  (mínimo por segmento), tomados de faster-whisper.
- Un turno hablado por debajo del umbral **no** propone ni confirma: AURA pide repetirlo.
- Los umbrales salen de la **medición** previa (sin guardar audio), no de una cifra inventada.

**C5 · Sin cambios:**
- el Motor Único (`_despachar_orden`) y los permisos;
- PARADA;
- el efecto verificado por relectura en HA;
- M8 (`¿qué hiciste?` recupera sin reejecutar);
- la propuesta, que vive un solo turno.
