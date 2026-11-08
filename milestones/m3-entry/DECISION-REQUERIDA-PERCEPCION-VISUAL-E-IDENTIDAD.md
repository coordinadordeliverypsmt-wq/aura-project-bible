---
documento: "Decisión requerida — percepción visual e identidad de personas"
tipo: "PROPUESTA — RATIFICADA el 2026-09-27 por decisiones/2026-09-27-acta-percepcion-visual-e-identidad.md (Decisión A: APROBADA)"
fecha: 2026-09-27
origen: "Campaña de presencia (mandato del CEO, 2026-09-26), bloques MIÉRCOLES (vídeo + identidad)"
decide: "CEO (Mauricio)"
---

# Decisión requerida · ¿adelanta AURA la visión y la identidad de personas?

**Estado:** RESUELTA por el CEO el 2026-09-27: `decisiones/2026-09-27-acta-percepcion-visual-e-identidad.md` (front-matter `resuelve:` este expediente). Nota añadida el 2026-10-22; el resto se conserva como registro.

El mandato del 2026-09-26 ordena construir vídeo e identidad esta semana. **La Bible los sitúa fuera
del MVP**, y el propio mandato establece que *«si la Bible/ADR/DP establece otra secuencia formal, la
fuente formal prevalece»*. Por eso no se integró nada en AURA: se midió la viabilidad, para que la
decisión tenga hechos debajo.

## Lo que dice la fuente formal

| Tema | Veredicto | Cita |
|---|---|---|
| Cámara y visión | **Release 4**, fuera del MVP | `docs/libro-02-vision-y-producto/2.2-alcance-mvp-roadmap-releases.md:112` y `:123` |
| Multiusuario / perfiles familiares | **Release 3** | `2.2:106` · `2.4-personalidad-etica-limites.md:117` |
| Captación de terceros (visitas) | **No se persiste como perfil** | `2.4:116` |
| Biometría | Futuro, sin mecanismo | `adr/0015-proveedores-de-contexto.md:29` |
| Punto de extensión | Ya existe, sin implementación | `walking-skeleton/aura_skeleton/core/contexto.py:1-20, 63` |

## Lo medido `[EJEC]` (2026-09-27), sin integrar nada

- Cámara integrada Chicony (`/dev/video0`): abre en **0,12 s**, entrega **640×480**.
- Detección de presencia (rostro, Haar de OpenCV, local): **226 ms** por fotograma a 640×480 y
  **85 ms** a 320×240, unos **12 fps** en el Celeron N4020. **Viable.**
- La imagen existió solo en memoria: **0 ficheros** en disco. Entorno de medición aislado en
  `~/aura-medicion/`, fuera de AURA.

## Decisión A · ¿Se adelanta la PERCEPCIÓN VISUAL (presencia, sin identidad) al MVP?

**Por qué no puede decidirlo el código:** mueve una capacidad de Release 4 a M3. Es un cambio de
roadmap (D23: el alcance del MVP está cerrado).

Opciones, sin recomendación:
1. **Mantener R4.** Nada cambia.
2. **Solo presencia**: «hay alguien / no hay nadie», sin guardar imagen ni rostro, como proveedor de
   contexto (`ProveedorContexto`, ADR-0015). Encendido de cámara bajo orden del usuario, con
   indicador visible.
3. **Presencia continua** con indicador y registro de auditoría de cada activación.

Consecuencia observable: con 2 o 3, AURA podría saludar al detectar a alguien o saber que la sala
está vacía. Infraestructura lista: medición hecha y punto de extensión existente.

## Decisión B · ¿Se autoriza RECONOCER a miembros de la familia?

**Por qué no puede decidirlo el código:** exige guardar huellas biométricas (embeddings de rostro o
de voz), y `2.4:116` prohíbe perfilar a quien no es usuario. No existe política de retención de
biometría.

Opciones, sin recomendación:
1. **No.** AURA solo distingue «persona presente» sin identificar.
2. **Enrolamiento explícito**: cada miembro se registra a sí mismo, con consentimiento; los
   desconocidos NUNCA se guardan; la huella se borra a petición.
3. **Identidad por voz** en vez de rostro, con el mismo enrolamiento.

Consecuencia: con 2 o 3, AURA distinguiría *conocido / desconocido / incierto*. Exige además una regla
de qué hacer ante un desconocido, y esa regla no existe.

## Lo que SÍ se construyó mientras tanto

Memoria corregida, voz real por micrófono y altavoz, y hogar real vía Home Assistant. Ver
`CHECKPOINT-CONTINUIDAD.md`, sección «Campaña de presencia».
