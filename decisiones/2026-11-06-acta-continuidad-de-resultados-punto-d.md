---
documento: "Acta — Continuidad de resultados y privacidad de la información retenida (punto D)"
fecha: 2026-11-06
decide: "CEO Operativo de AURA"
redacta: "Director Técnico (Claude Code)"
base: "milestones/m3-entry/DECISION-REQUERIDA-CONTINUIDAD-DE-RESULTADOS.md §7 v2 (dictámenes arquitecto-evaluador: CABE CON CONDICIONES; security-reviewer: APROBADO CON CONDICIONES)"
rama: "integracion/m3-entry"
---

# Acta · Punto D — continuidad de resultados y privacidad

El CEO Operativo de AURA **aprueba las ocho decisiones de la §7.7** y autoriza implementar el punto D sobre la versión 2
de la §7, en la rama `integracion/m3-entry`.

## Decisiones ratificadas

1. **Privacidad de la ventana.** El contenido de las capacidades marcadas `devuelve_contenido_usuario` (hoy
   `leer_archivo`) no vuelve a entrar en el prompt de turnos posteriores; puede recuperarse a petición expresa dentro de
   la misma conversación.
2. **Persistencia.** Solo metadatos validados en el registro `resultado_accion` de `memoria.json` (lista blanca de
   campos y valores, al escribir y al leer; nunca el `say` ni el payload; episódico de acción; alcance usuario).
3. **Retención** sin caducidad temporal. El olvido se hace por el catálogo de operaciones; nueva fila **T19** del
   contrato de olvido.
4. **PARADA:** con PARADA armada no se persiste ningún resultado (guarda con `es_escritura_pasiva`).
5. **Privacidad de metadatos:** hora redondeada al minuto; cerraduras, alarmas y cámaras excluidas. **Sin firma
   criptográfica en este alcance**: limitación documentada (un proceso del mismo usuario podría anexar un registro
   falso; se mitiga con validación al leer, presentación como «registro local» y permisos 0600 en `memoria.json`, su `.tmp`, las copias y el manifiesto; **los directorios no se modifican**: límite declarado).
6. **Ver y exportar** incluyen `resultado_accion` con lista blanca, ámbito del usuario y redacción de campos. **No**
   autoriza su incorporación al prompt ni a `recall`.
7. **Fronteras:** se sustituyen `test_frontera_continuidad.py:74` y `:95`, y la rama del prompt de la prueba de
   contenido.
8. **Habilitación de integración** (las capacidades de ejecución y memoria colaboran) limitada a este alcance.

## Reconocimiento expreso del residual de ADR-0024

ADR-0024 / acta D-A006 (2026-09-09) aceptaron `memory.write` fuera del Motor Único como residual **acotado a lo
conversacional**. Este incremento añade una escritura de memoria **no conversacional** (metadatos derivados de acciones),
también fuera del Motor Único. El CEO Operativo **reconoce y acepta esa ampliación** del residual, limitada a
`resultado_accion` con esquema cerrado, sin crear autoridad nueva ni permitir escritura con PARADA armada. Sigue
«delimitado, no resuelto».

## Fuera de alcance

Versión de identidad (§5), re-ejecución o idempotencia de acciones tras reinicio, E2E físico, M3.2b, CM4, M4, cambios
generales de arquitectura, producción, `~/.aura`, `estado.json`, `eventos.jsonl`, cron, CM2 y nodos.
