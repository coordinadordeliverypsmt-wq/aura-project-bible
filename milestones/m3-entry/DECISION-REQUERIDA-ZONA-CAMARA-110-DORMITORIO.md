# DECISION_REQUIRED — La cámara .110 es un dormitorio: ¿qué autoriza la superficie «interior»?

**Fecha:** 2026-10-22 · **Origen:** captura de pantalla del propietario (app de la cámara: nombre **«habitacion»**,
MAC 88:E6:28:BB:69:C1, firmware 3.5.1.1108) contrastada con el código y con las decisiones vigentes.
**Estado:** RESUELTA por el CEO el 2026-10-22: `decisiones/2026-10-22-acta-camaras-zona-como-metadato.md`. La zona es un metadato y nunca deniega; la .110 es elegible. Las secciones siguientes se conservan como registro.

## 1. Hechos verificados

- `[LECT]` `decisiones/2026-09-28-DP-FRAME-A-OBSERVACION-APROBADO.md:33`: «.110 autorizada por el CEO»;
  `DP-PERCEPCION-MULTIMODAL-CONSOLIDADO.md:140`: «superficie interior autorizada». **Esa autorización se dio sin que
  constara que la .110 está en un dormitorio.**
- `[LECT]` `walking-skeleton/aura_skeleton/core/politica_superficie.py:1-5`: «un canal privado (dormitorio) queda
  restringido»; deny-by-default; las zonas válidas son `exterior | acceso | garaje | privada | desconocida`. La zona NO se
  evalúa en ninguna regla: solo cuentan `autorizado` y los permisos.
- `[LECT]` `walking-skeleton/aura_skeleton/composicion.py:700-716`: si existe `AURA_CAMARA_RTSP`, la composición registra
  la cámara de red con `zona="interior"` (valor **fuera** de esa lista) y `autorizado=True`. La zona la pone el código, no
  el propietario. `capacidades.json` («Política por superficie») ya decía que hace falta que el propietario declare la zona
  de cada canal.
- `[EJEC]` `AURA_CAMARA_RTSP` no está definida en ningún lanzador ni servicio: **hoy AURA no puede mirar la .110**. El
  riesgo no está activo.
- `[LECT]` seis pruebas fijan `zona="interior"` en dobles (percepción auditiva, visual, movimiento, multimodal, observación
  y cámara sin nombre).

## 2. Pregunta

¿Qué debe hacer AURA con una cámara de **dormitorio** que ya tiene una autorización vigente dada como «interior»?

## 3. Opciones

| Opción | Qué significa | Consecuencias |
|---|---|---|
| **A · Privada = bloqueada siempre** | La zona la declara el propietario por canal (`AURA_CAMARA_ZONA`, con el enum). «privada» registra la superficie sin vídeo ni audio. «interior» desaparece. Se revoca la autorización del 28-09 para la .110 | Lo más seguro. La .110 deja de poder mirarse hasta que se mueva o se decida otra cosa. Se actualizan 6 pruebas. Coste: ~2-3 h con mutación |
| **B · Privada = solo con autorización expresa por canal** | Como A, pero una zona «privada» admite vídeo si el CEO lo autoriza por escrito para ESE canal, con su propósito (p. ej. «solo cuando yo lo pida, ambiental, sin persona»). La autorización del 28-09 se rehace sabiendo que es un dormitorio | La capacidad de la .110 se conserva con consentimiento informado. Requiere un acta nueva por canal. Coste similar a A |
| **C · Mantener «interior»** | Sin cambios | La zona sigue siendo inventada por el código («declarado ≠ real», tensión con INV-9); una cámara de dormitorio se trata como cualquier otra |

**Recomendación del ejecutor: A como comportamiento por defecto, con B disponible.** La zona la declara el propietario;
«privada» bloquea salvo un acta expresa para ese canal. Además, en un dormitorio suele haber terceros (ALERTA-002), que
la autorización del propietario no cubre.

## 4. Mientras se decide

- No se activa `AURA_CAMARA_RTSP` para la .110. El procedimiento de captura de `MAPA-ECOSISTEMA-FISICO.md` §6.2 queda
  RETIRADO.
- No se cambia la composición: hacerlo, aunque sea más restrictivo, modificaría una autorización aprobada.
- La identificación de la .110 (ONVIF, MAC) y la cámara local no se ven afectadas.
