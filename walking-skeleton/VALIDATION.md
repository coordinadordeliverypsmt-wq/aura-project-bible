# Walking Skeleton — Registro de Validacion

**Fecha:** 2026-07-18 · **Resultado:** ARQUITECTURA VALIDADA (exit 0). Primer codigo de AURA (Bible 7.3).

## Hallazgo del walking skeleton (valor del ejercicio)

En la primera ejecucion, el check de permisos (lista roja/HITL) fallo: la peticion "elimina el archivo" se clasifico como "encender luz" porque un recuerdo previo ("luz de la sala") se colo en el prompt y contamino la clasificacion de intencion.

Es exactamente para esto que existe el walking skeleton. El hallazgo es real: el contexto de memoria no debe alterar la intencion que el usuario expresa (conecta con la defensa de prompt injection, Bible 5.2). Correccion aplicada: la intencion se clasifica sobre la peticion del usuario y las intenciones de lista roja tienen prioridad de seguridad (P-ARQ-1). Re-ejecucion: 8/8 validaciones OK.

## Que quedo validado

Los 8 puntos exigidos por el CEO + idempotencia, de extremo a extremo (ver salida).

## Caveat honesto (para el CEO)

La latencia medida es estructural, no real: proveedores, STT/TTS y bus son mocks (sin NATS, Whisper ni LLMs de nube en este entorno). Lo validado es que la arquitectura y los contratos funcionan como fueron concebidos. La validacion de la latencia real (HC-1: R1 <=1200ms) requiere el stack real (ADR-0006/0008 + LLMs) y es el siguiente paso.

## Salida de la ejecucion

```
  [MEM  ] memory         trace=seed write [semantica] 'el usuario prefiere la luz de la sala te'
  [VOICE] voice-stt      trace=535a16d7 transcripcion: 'Enciende la luz de la sala'
  [EVENT] event-bus      trace=535a16d7 publish perception.turn_end event_id=8cca8d58c6b2
  [MEM  ] memory         trace=- recall 'Enciende la luz de la sala' -> 1 hit(s)
  [WARN ] router         trace=535a16d7 fallback: gemini-mock fallo (gemini-mock no disponible)
  [LLM  ] router         trace=535a16d7 enrutado a claude-mock
  [AUDIT] permissions    trace=535a16d7 lista verde encender_dispositivo -> auto-ejecucion audit=True
  [ACT  ] ha-adapter     trace=535a16d7 EJECUTA encender_dispositivo sobre 'luz sala' audit=True
  [MEM  ] memory         trace=535a16d7 write [episodica] 'usuario dijo: Enciende la luz de la sala'
  [VOICE] voice-tts      trace=535a16d7 AURA dice: "Listo, encendi la luz de la sala. [accion encender_dispositivo ejecutada: auto (lista verde)]"
  [LAT  ] orchestrator   trace=535a16d7 latencia total 203 ms (proveedor=claude-mock) audit=True
  [VOICE] voice-stt      trace=da5b0d7e transcripcion: 'Elimina el archivo de impuestos'
  [EVENT] event-bus      trace=da5b0d7e publish perception.turn_end event_id=b8e371d5769e
  [MEM  ] memory         trace=- recall 'Elimina el archivo de impuesto' -> 2 hit(s)
  [LLM  ] router         trace=da5b0d7e enrutado a claude-mock
  [HITL ] permissions    trace=da5b0d7e accion de LISTA ROJA requiere confirmacion: eliminar_informacion audit=True
  [AUDIT] permissions    trace=da5b0d7e lista roja eliminar_informacion -> DENEGADA audit=True
  [MEM  ] memory         trace=da5b0d7e write [episodica] 'usuario dijo: Elimina el archivo de impu'
  [VOICE] voice-tts      trace=da5b0d7e AURA dice: "No ejecute la accion. [accion eliminar_informacion denegada por el usuario]"
  [LAT  ] orchestrator   trace=da5b0d7e latencia total 111 ms (proveedor=claude-mock) audit=True
  [VOICE] voice-stt      trace=99356958 transcripcion: 'Que acordamos sobre la luz de la sala?'
  [EVENT] event-bus      trace=99356958 publish perception.turn_end event_id=fe1be2599d9d
  [MEM  ] memory         trace=- recall 'Que acordamos sobre la luz de ' -> 3 hit(s)
  [LLM  ] router         trace=99356958 enrutado a claude-mock
  [MEM  ] memory         trace=99356958 write [episodica] 'usuario dijo: Que acordamos sobre la luz'
  [VOICE] voice-tts      trace=99356958 AURA dice: "Segun lo que recuerdo: el usuario prefiere la luz de la sala tenue por la noche | usuario dijo: Enciende la luz de la sala | usuario dijo: Elimina el archivo de impuestos"
  [LAT  ] orchestrator   trace=99356958 latencia total 111 ms (proveedor=claude-mock) audit=True
  [ACT  ] ha-adapter     trace=dup-trac EJECUTA encender_dispositivo sobre 'luz sala' audit=True
  [ACT  ] ha-adapter     trace=dup-trac idempotente: encender_dispositivo ya ejecutado

=== ESCENARIO: Lista verde + fallback de proveedor ===
    Usuario (voz): "Enciende la luz de la sala"

=== ESCENARIO: Lista roja -> HITL (usuario deniega) ===
    Usuario (voz): "Elimina el archivo de impuestos"
    >>> HITL: AURA pide confirmar 'eliminar_informacion' {'target': 'archivo'} -> usuario responde: NO

=== ESCENARIO: Memoria (recuerdo previo) ===
    Usuario (voz): "Que acordamos sobre la luz de la sala?"

=== ESCENARIO: Idempotencia (comando repetido) ===

==================================================================
REPORTE DE VALIDACION DEL WALKING SKELETON
==================================================================
  Registros de auditoria (P-ARQ-7): 8
  [OK] 1. Arquitectura (nucleo minimo + modulos por contrato)
  [OK] 2. Flujo Event-Driven con trace_id
  [OK] 3. Orquestacion multi-modelo con fallback (gemini->claude)
  [OK] 4. Memoria fuera del nucleo con recall + no-fabricacion
  [OK] 5. Permisos: lista verde auto, lista roja con HITL
  [OK] 6. Latencia medida vs presupuesto R1 <=1200ms
  [OK] 7. Observabilidad (logs estructurados + audit log)
  [OK] 8. Integracion entre modulos (turno extremo a extremo)
  [OK] Idempotencia de efectos fisicos (3.3)
==================================================================
RESULTADO: ARQUITECTURA VALIDADA — el walking skeleton corre de extremo a extremo.
```
