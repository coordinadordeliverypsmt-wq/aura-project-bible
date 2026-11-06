# Acta — Ecosistema doméstico: descubrir, conocer y controlar los dispositivos de la red del hogar

**Fecha:** 2026-10-22 · **Origen:** directiva del CEO «Continuidad del propósito original, descubrimiento y control
integral del ecosistema doméstico» (sesión del 2026-10-21/22). **Este documento transcribe la orden del CEO**; no añade
autoridad propia del ejecutor.

## 1. Lo que el CEO autoriza (D23: apertura del alcance doméstico por acta)

Los dispositivos conectados a la red doméstica bajo el control del CEO quedan autorizados para formar parte del
ecosistema de AURA. Pueden **descubrirse, identificarse, consultarse, investigarse sus interfaces, integrarse sus
capacidades y controlarse** sus funciones técnicamente accesibles. Esto incluye televisores, sistemas de entretenimiento,
consolas (PS5), computadores, celulares, cámaras, audio, relojes, gadgets, domótica y dispositivos futuros. El alcance no
es una lista cerrada de marcas.

## 2. Límites que la propia directiva fija

- **Solo por la interfaz legítima, con la autenticación necesaria.** Quedan prohibidos el acceso a cuentas ajenas, romper
  cifrado, evadir autenticación, alterar firmware y vulnerar servicios externos. Si una función no está disponible así, se
  documenta como limitación.
- **El descubrimiento es controlado, proporcional y no destructivo.** No se hacen escaneos agresivos, no se modifica el
  router y no se cambia la configuración global. Se mantiene la garantía de diseño de `adapters/red_local.py`: descubrimiento
  pasivo o dirigido, sin sondear puertos ni probar credenciales.
- **No se registran secretos** en informes ni inventarios, solo referencias a dónde están.
- **Las decisiones vigentes de seguridad, privacidad, PARADA y gobierno se respetan.** No se eliminan unilateralmente.

## 3. Alcance documental de las decisiones vigentes frente a esta autorización (determinado por el ejecutor)

| Decisión | Estado tras esta acta |
|---|---|
| D23 (alcance MVP cerrado) | **Abierta** para el ecosistema doméstico, en los términos de §1-§2 |
| D4 / ADR-0003 (listas) | **Vigente.** Cada acción nueva se clasifica en `permissions.py`. Reversible = verde; ante la duda, roja |
| Motor Único, PARADA, permisos (ALERTA-005) | **Vigentes, sin excepción.** Toda acción pasa por `_despachar_orden` |
| Opción C de `DP-VOZ-ACCION.md` §8 (la voz solo enciende o apaga la TV de la sala) | **Vigente.** Esta acta autoriza el control, pero no modifica las salvaguardas específicas de la VOZ. Ampliar la voz a otras acciones o dispositivos es una decisión aparte (§5) |
| D24 (local-first, sin claves de terceros) | **Vigente.** Las integraciones solo en la nube (PSN, nubes de fabricantes) quedan como limitación documentada |
| Acta de percepción del 2026-09-27, decisión A | **Vigente y aprobada**: percepción visual por vías legítimas, procesamiento local, nunca de la cámara a una acción |
| Decisión B (identificar o reconocer a personas, biometría) | **No autorizada.** Describir presencia u ocupación observada SÍ; identificar a una persona NO |
| ALERTA-002 (terceros) | **Vigente** |
| M3.2b (patrones) | **Congelado** (sin cambios) |

## 4. Primer tramo vertical (contrato técnico; Decision Package abreviado aprobado por la directiva)

- **Dispositivo:** la TV de la sala (`media_player.tv_sala_fmilia_medina_un43ru7100fxza`, integración `samsungtv`;
  `supported_features` 24509 anuncia volumen por pasos, fijado y silencio).
- **Capacidades nuevas en la lista verde (reversibles):** `subir_volumen`, `bajar_volumen`, `silenciar`, `quitar_silencio`,
  por el camino de TEXTO (regla M1), por el Motor Único, con lectura del estado **antes y después**.
- **Verificación:** el efecto solo se da por hecho si el atributo releído cambia en el sentido esperado (`volume_level`
  sube o baja; `is_volume_muted` pasa al valor esperado). Si HA no expone el atributo, AURA dice que envió la orden pero no
  puede comprobarla. Una orden enviada no es un efecto.
- **Consulta de estado (solo lectura):** «¿qué está poniendo la tele?», a partir de los atributos que exponga HA. Lo que no
  esté expuesto se declara desconocido; no se infiere.

## 5. Decisiones que siguen pendientes del CEO

1. **Voz → volumen y silencio** (enmienda de la opción C §8): ¿la voz puede subir o bajar el volumen y silenciar la TV de la
   sala, con las mismas salvaguardas (activación, propuesta y «sí», confianza del STT)?
2. **Integraciones que necesitan la nube o una cuenta del fabricante** (PSN para el juego en curso de la PS5, apps de los
   relojes): D24 las excluye mientras no haya un acta específica.
