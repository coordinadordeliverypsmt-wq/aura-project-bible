---
documento: "Deuda registrada — borrar la cola del log de eventos no se detecta"
fecha: 2026-10-26
autor: "CTO"
origen: "Investigación externa IE-040 (HAL-040-2), confirmada ejecutando en AURA sobre una copia del log real"
estado: "REGISTRADA. Requiere Decision Package: toca control_plane.py, que figura en _INTOCABLES. Nada implementado"
implementacion: "Actualización 2026-10-27: corrección implementada en la rama local integracion/m3-entry (pista control-plane, merge 90545f4; ancla externa en control_plane.py). NO desplegada en producción (worktree-m3-entry): la deuda sigue abierta allí y adoptar_ancla no se ha ejecutado sobre el log real"
base: "worktree-m3-entry @ bf13a47"
---

# D-LOG-1 · `verificar_integridad_log` no detecta que se borren los últimos eventos completos

## Qué es

`[EJEC 2026-10-26]` Sobre una **copia** de `entorno/control-plane/eventos.jsonl` de 3729 líneas, en un temporal del job,
se borraron los **2 últimos eventos completos**. `control_plane.verificar_integridad_log` devolvió
`{'integro': True, 'eventos': 3727, 'cola_truncada': False}`. El original no cambió: sha `56a37569…` antes y después.

## Por qué ocurre

`[LECT]` La verificación (`control_plane.py:1957-1976`):

- comprueba la continuidad de `seq` desde 1, `hash_anterior` y el hash de cada evento;
- **no compara la cabeza** con ningún ancla externa;
- `estado.json` no guarda ni el último `seq` ni el hash de cabeza.

`cola_truncada` solo detecta una línea final **parcial**.

## Por qué es deuda (`CLAUDE.md` §7) y no una observación

Puede producir **pérdida de información** sin que nada lo diga: el historial (ADR-0023, fuente de verdad) perdería
hechos y seguiría verificándose como íntegro. Es el patrón «declarado ≠ real» aplicado al log.

## Qué pediría la corrección (cuando se autorice)

1. **Prueba RED:** borrar N eventos de cola y esperar `integro: False`.
2. **Caso de control:** el log intacto da `integro: True`.
3. **Mutante:** quitar la comparación con el ancla, y debe morir.
4. **Ancla fuera del log:** hash de cabeza y `seq`, escritos de forma atómica bajo el mismo `lock_estado`.
5. **Compatibilidad:** el primer anclaje adopta la cabeza actual.
6. **Auditor de garantías** antes de aplicar, mutación y QG.

## Fuentes

`milestones/investigacion-externa/IE-040-agent-governance-toolkit.md` (HAL-040-2 y su contraste).
