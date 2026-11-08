# Acta — Cámaras domésticas: la zona es un METADATO, no una denegación

**Fecha:** 2026-10-22 · **Origen:** orden del CEO «Rectificación de política e integración de todas las cámaras». Este
documento transcribe la orden; no añade autoridad propia del ejecutor.
**Resuelve:** `milestones/m3-entry/DECISION-REQUERIDA-ZONA-CAMARA-110-DORMITORIO.md`. La opción elegida no es A, B ni C:
es la que se describe a continuación.

## Decisión

1. **Todas las cámaras domésticas bajo el control del propietario son candidatas a integración**, sea cual sea su
   ubicación: habitación, dormitorio, recámara, sala, garaje, exterior u otra.
2. **La zona por sí sola NUNCA deniega el acceso.** Es metadato de organización y contexto: sirve para nombrar y elegir la
   cámara. Ninguna regla de permiso la consulta.
3. **La cámara .110** (EYEPLUS, firmware 3.5.1.1108, «habitacion») permanece en el inventario y es elegible para la
   integración.
4. Esta decisión **corrige la interpretación anterior**, que trataba el dormitorio como motivo suficiente para bloquear,
   incluido el docstring «un canal privado (dormitorio) queda restringido» de `politica_superficie.py`.

## Lo que esta acta NO cambia (sigue vigente)

- **Activación:** el mecanismo aprobado (el propietario define la URL de la cámara en el proceso) sigue siendo la puerta
  de entrada a cada cámara de red. No se convierte en un bloqueo por habitación.
- **Observación efímera:** sin guardar fotogramas ni contenido visual o sonoro en logs ni en memoria (DP de percepción).
- **Decisión B:** no identificar ni reconocer personas; sin biometría.
- **Nunca de la cámara a una acción:** toda acción pasa por el Motor Único, los permisos y PARADA.
- **Solo vías legítimas:** sin eludir autenticación ni probar credenciales; el DVR .80 sigue en «no tocar».
- **ALERTA-002:** sin perfiles de terceros ni persistencia de lo percibido.

## Constancias técnicas para el propietario (security-reviewer, 2026-10-22). No modifican la decisión

1. **Rastro de presencia.** Cada consulta de movimiento queda en el audit log persistente: superficie, si hubo movimiento,
   magnitud y hora. Una cámara de dormitorio deja así un rastro de presencia por zona, aunque la imagen sea efímera. No
   hay una retención definida para esos eventos; es una decisión pendiente si se quiere acotar.
2. **Terceros.** En un dormitorio puede haber visitas o menores que no han consentido. La política solo comprueba la
   autorización del propietario, no el consentimiento de quien aparece. Sigue vigente ALERTA-002: sin identificar, sin
   perfiles y sin guardar lo percibido.
3. **Riesgo del dispositivo, ajeno a AURA.** `[EJEC]` La .110 sirve su vídeo por RTSP SIN credencial: cualquier equipo de
   la red local puede verlo sin pasar por AURA. Se recomienda ponerle una contraseña desde su app. AURA usaría entonces
   la credencial del propietario por la vía legítima, nunca la forzaría.
