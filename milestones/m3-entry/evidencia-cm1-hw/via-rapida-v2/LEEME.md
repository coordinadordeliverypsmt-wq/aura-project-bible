# Vía rápida de STT (v1 y v2) — material de referencia, NO código activo

Rutas relativas a `walking-skeleton/`. Copia literal del estado previo a la retirada.

## Qué era
`OidoContinuo.escuchar_orden`: transcribir la orden con Vosk (reconocimiento libre en v1; en v2, además,
gramática cerrada de `ORDENES_DE_VOZ`) con un VAD de energía propio para decidir el fin de habla, activada
con `AURA_ORDEN_VOSK=1`. Buscaba cumplir CM1 (P50 <= 800 ms de fin de habla a inicio de respuesta).

## Por qué se retiró (evidencia [EJEC] 2026-09-29, AURA real por el aire)
- v1: 24 turnos, 8 válidos, P50 995 ms, 0/5 respuestas correctas.
- v2: 24 turnos, 7 válidos, P50 1070 ms, 0/8 correctas, 5/24 oídas bien.
- Caso más favorable (solo preguntas de la gramática): turnos válidos de 820 y 880 ms.
- Con la vía activada AURA GUARDÓ datos falsos en memoria («Tu color favorito es en.», «me llamo favorito»).
- CM1 no se alcanza, y dejar la opción disponible es una trampa: corrompe la memoria.

Se conservan en el código activo: `--latency-msec=20` (parecord), `--latency-msec=30` (paplay) y espeak como
motor de voz opcional.
