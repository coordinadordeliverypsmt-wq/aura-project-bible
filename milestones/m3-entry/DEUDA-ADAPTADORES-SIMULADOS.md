---
documento: "Deuda registrada — adaptadores simulados indistinguibles de los reales"
fecha: 2026-08-02
autor: "CTO"
origen: "Revisión estratégica del roadmap (2026-08-02); confirmado al cerrar la corrección D"
estado: "REGISTRADA. No bloquea. El CEO decidió no abrir un incremento: primero producto."
base: "main @ c31ac2a · Quality Gate PASS 432/3"
---

# D-ADP-1 · Un adaptador simulado responde igual que uno real

## Qué es

`[EJEC 2026-08-02]` Con Home Assistant ausente:

```
Usuario: Enciende la lámpara del salón
AURA:    Enciendo la lámpara. [accion encender_dispositivo ejecutada]
```

No se encendió nada. `HomeAssistantMock` escribe una línea de log y devuelve `{"status": "ok"}` —
exactamente lo mismo que devolvería un adaptador real. El arranque lista sus dos capacidades entre las
**12 operaciones disponibles**, sin distinguirlas de las 10 que sí tienen efecto sobre el disco.

## Por qué no lo cubre ninguna garantía existente

La garantía de M2.5 (ALERTA-005 punto 4) verifica que **el adaptador respondió**, no que **el mundo
cambió**. Es una garantía sobre el camino de ejecución, no sobre la realidad del efecto — y con un
adaptador simulado el camino se recorre entero y con éxito.

## Relación con la corrección D (2026-08-02)

Es **la misma clase de inconsistencia, una capa más abajo**:

| Capa | Inconsistencia | Estado |
|---|---|---|
| **Capacidades** (plan vs materialización) | El plan declaraba `ACTIVA` mientras corría N1 | ✅ **Corregida** — AURA declara el estado efectivo, auditado |
| **Adaptadores** (respuesta vs efecto) | Un mock responde `ok` como uno real | ⬜ **Esta deuda** |

Que la primera esté resuelta no resuelve la segunda: son mecanismos distintos. La corrección D actúa en
la composición sobre el `PlanActivacion`; aquí el problema vive en el contrato `Adapter`, que no
distingue **simular** de **hacer**.

## Riesgo real

- **Hoy, acotado:** afecta solo a las 2 capacidades de hogar, y no hay dispositivos que dañar.
- **Cuando llegue Home Assistant real:** desaparece para el hogar, pero **no** el mecanismo — cualquier
  adaptador futuro que se registre como mock reproducirá el problema.
- **El daño es de confianza, no de datos:** AURA afirma haber hecho algo que no hizo. Contradice
  directamente 2.4 §personalidad (*honesta, jamás aduladora; la verdad ante todo*) y el principio del CEO
  *"la interfaz debe ser fiel al estado interno"*.

## Corrección natural (no diseñada aún, no autorizada)

Que un adaptador **declare si sus efectos son reales o simulados**, y que esa declaración viaje hasta la
respuesta y hasta el arranque: AURA diría *"simulé encender la lámpara: no hay Home Assistant conectado"*.
Es una extensión del contrato `Adapter`, con impacto en `RegistroAdaptadores`, en el motor y en la
redacción de respuestas.

**Reevaluar cuando:** se conecte Home Assistant real, se registre cualquier adaptador simulado nuevo, o el
CEO priorice las inconsistencias de infraestructura frente a producto.

## Decisión del CEO (2026-08-02)

> *"No abras otro frente ahora. Regístralo como deuda, mantenlo en el checklist y continuamos. No vamos a
> convertir cada hallazgo en un nuevo incremento; primero avanzamos en producto y después abordaremos esas
> inconsistencias de infraestructura según prioridad."*
