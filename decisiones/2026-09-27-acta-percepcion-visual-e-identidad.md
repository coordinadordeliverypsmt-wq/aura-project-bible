---
documento: "Acta del CEO — Percepción visual e identidad"
tipo: "ACTA — DECISIÓN DE GOBIERNO RATIFICADA"
fecha: 2026-09-27
decide: "CEO / propietario del entorno doméstico (Mauricio)"
resuelve: "milestones/m3-entry/DECISION-REQUERIDA-PERCEPCION-VISUAL-E-IDENTIDAD.md"
---

# Acta · Percepción visual e identidad dentro del entorno doméstico

## Decisión

**APROBADO.** El CEO autoriza a AURA a desarrollar, integrar y probar capacidades de percepción visual
e identidad dentro del entorno doméstico bajo su control, **usando únicamente vías técnicas legítimas** y
respetando privacidad, seguridad y gobernanza. Esto ratifica la Decisión A del documento
`milestones/m3-entry/DECISION-REQUERIDA-PERCEPCION-VISUAL-E-IDENTIDAD.md` (antes «PROPUESTA — no
ratificada») y mueve la capacidad de percepción visual desde Release 4 hacia el desarrollo actual (D23:
el alcance del MVP lo abre el CEO por acta).

## Alcance autorizado

- Cámaras del hogar, DVR y sus cámaras, cámaras integradas por Home Assistant, y la **cámara local de la
  plataforma AURA**.
- Cadena, cada grada demostrada por separado y con evidencia:
  cámara → conexión → stream → **frame** → percepción → detección → contexto → identidad.

## Fronteras que el acta NO elimina (se respetan siempre)

- `DETECTADO ≠ CONECTADO`; `CÁMARA ≠ AURA VE`; `STREAM ≠ FRAME`; `FRAME ≠ VISIÓN`;
  `PERSONA DETECTADA ≠ PERSONA IDENTIFICADA`; `ORDEN ≠ EFECTO VERIFICADO`.
- **Nunca `CÁMARA → ACCIÓN`.** Toda acción pasa por: percepción → interpretación → contexto →
  autorización → **Motor Único**.
- **Procesamiento local** (§6). No se envía vídeo ni imágenes a servicios externos; sacar datos visuales
  del entorno exige una decisión posterior específica.
- **Sin captura ni almacenamiento indiscriminado** (§9, §10). La retención es selectiva y gobernada;
  cualquier cambio de retención se documenta **antes** de implementarse.
- **Solo vías legítimas** (§7): ONVIF, RTSP, APIs locales, Home Assistant, HTTP/S, WebSocket, pairing
  normal, credenciales del propietario. **NO** bypass, cracking, fuerza bruta, evasión de pairing,
  robo de credenciales ni cuentas de terceros. La falta de credencial se clasifica
  `REQUIERE CREDENCIAL DEL PROPIETARIO`, no «AURA no puede».
- **Identidad con evidencia** (§4): `IDENTIDAD CONFIRMADA` / `IDENTIDAD NO CONFIRMADA` /
  `PERSONA DESCONOCIDA`; nunca inventada; nunca inferida solo de IP/MAC/hostname/teléfono/presencia.

## Naturaleza (§15)

El acta autoriza la **capacidad**, no cada detalle técnico. Claude Code + ECC diseñan, implementan,
prueban, auditan, miden y documentan. **Si durante la implementación aparece una nueva decisión
estratégica, se detiene en esa frontera y se eleva.**

## Frontera elevada de inmediato (hallazgo de implementación, 2026-09-27)

La percepción de **personas** (detección e identidad) colisiona con **ALERTA-002** y `senales.py` §3
(«sin perfiles de terceros»): una persona vista por cámara suele ser un tercero, y su dato no es
capturable por el cauce de señales de aprendizaje del usuario. Cómo se representa y **retiene** una
persona percibida (detectada vs. identificada, visitas no persistidas, §2.4:116) es una **decisión de
diseño estratégica** que se documentará y elevará **antes** de implementar esa grada. Por eso el primer
incremento se limita a percepción **ambiental** (frame recibido y sus metadatos), sin persona ni
identidad.
