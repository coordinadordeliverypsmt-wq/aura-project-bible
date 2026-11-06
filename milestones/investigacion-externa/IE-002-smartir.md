---
id: IE-002
titulo: "smartHomeHub/SmartIR — climatización/TV/ventilador/luz por IR/RF en Home Assistant"
fuente: https://github.com/smartHomeHub/SmartIR
rama-revision: master @ e4df295 (2025-07-21)
fecha-revision: 2026-10-22
licencia: MIT
area: hogar
estado: adoptado (concepto; 2026-10-22)
cobertura: "Leídos (vía WebFetch resumido): custom_components/smartir/__init__.py, media_player.py, controller.py; árbol de ficheros (leído hasta codes/media_player, truncado: no se vio si hay tests/). NO leídos: climate.py, fan.py, light.py, services.yaml, manifest.json, README (404 en raw/README.md), ficheros codes/*.json individuales."
relacionadas: [IE-004]
---
## Qué se examinó (rutas y símbolos)
`custom_components/smartir/__init__.py` (`async_setup`, `_update`, `Helper.downloader`), `media_player.py` (`async_setup_platform`, `send_command`, `async_update`, `_support_flags`), `controller.py` (`get_controller`, 5 controladores). `codes/` = ~400 JSON por modelo (climate 357, fan 17, light 5, media_player 30+).

## Patrones relevantes
- [CÓDIGO] Un fichero JSON por modelo declara `commands` (`on`, `off`, `volumeUp`, `sources`…); `supported_features` se calcula SOLO de las claves presentes y no nulas (`media_player.py`, `_support_flags`). Patrón útil: capacidades derivadas de datos declarados, no supuestas.
- [CÓDIGO] «Estado asumido»: estado inicial `STATE_OFF`, `RestoreEntity` lo restaura tras reinicio, y se actualiza de forma optimista al enviar. Con `power_sensor` configurado ese sensor es la fuente de verdad (`async_update`). No define `assumed_state` explícito. [INFER] Esta es la distinción valiosa: estado asumido (sin sensor) vs observado (con sensor).
- [CÓDIGO] Un `asyncio.Lock` serializa los envíos (`send_command`). Mute es toggle ciego (ignora el argumento).
- [CÓDIGO] Controladores: Broadlink, Xiaomi, MQTT, LOOKin, ESPHome, con lista blanca de codificaciones por controlador.

## Límites, riesgos y dependencias
- **[CÓDIGO] RIESGO DE SEGURIDAD en actualización remota** (`__init__.py`): `update_component` descarga de `raw.githubusercontent.com` (rama `master`/`rc`) los ficheros que lista el `manifest.json` REMOTO (`updater.files`) y los escribe en `os.path.join(COMPONENT_ABS_DIR, file)` sin hash, firma ni validación de ruta: un `file` absoluto o con `..` escribe fuera del componente; escritura no atómica sobre el destino final; actualización parcial posible; servicios sin esquema. Es ejecución de código remoto sin integridad.
- [CÓDIGO] Descarga de códigos: si falta `<device_code>.json` lo baja de GitHub al arrancar (`async_setup_platform`); el nombre viene de la configuración del usuario. Los JSON son datos, pero un código IR mal formado se envía a un emisor físico.
- [CÓDIGO] Errores tragados: `controller.send` se captura con `_LOGGER.exception` y el llamador nunca ve el fallo; `KeyError` sin capturar con fuentes/dígitos inexistentes; sin timeouts (LOOKin `requests.get`); sin comprobar HTTP status.
- [CÓDIGO] Solo emisión: no lee estado real del equipo. Aprendizaje de códigos requiere dispositivo físico (no probado).

## Comparación con AURA
- `core/hogar.py` (ESTADOS_ENCENDIDA/ESTADOS_APAGADA, contrato por operación): AURA tampoco puede leer el estado de un aparato IR. Hoy `adapters/home_assistant_real.py:_actuar` (L377) verifica releyendo HA; para una entidad SmartIR (`media_player` optimista) HA devolvería el estado AUTOGENERADO por SmartIR y AURA diría «Home Assistant ve encendida» aunque el televisor no se haya movido. [INFER] Brecha real: AURA no distingue estado observado de estado asumido; la verificación sería circular.
- `core/entorno.py` no usa `supported_features` ni `assumed_state`; `_fusionar` (L183) y `dispositivos()` (L254) no los reciben.
- Tests: no confirmados (árbol truncado).

## Decisión
**Adaptar solo el concepto** «estado asumido vs observado» y «capacidades derivadas de claves declaradas»; **descartar** el mecanismo de actualización remota (prohibido por D24/Motor Único y por riesgo). No integrar SmartIR como ejecutor en AURA sin acta; no es solución de cámaras ni de descubrimiento IP.

## Validación mínima
Prueba sobre `home_assistant_real.py` con un doble de HA que devuelve `attributes.assumed_state: true`: AURA debe responder «HA lo da por encendido (estado asumido)» y NO marcar `verificado`. Control: sin `assumed_state`, el comportamiento actual no cambia.

## Licencia y precauciones
MIT: se puede reutilizar código, pero no hace falta. No instalar. No ejecutar `smartir.update_component`. Revisión parcial: `climate.py`, `fan.py`, `light.py`, README y tests NO leídos.

## Adopción (2026-10-22)

Se adoptó el **concepto**; no se copió código. Si tras una orden Home Assistant marca la entidad con
`attributes.assumed_state: true`, AURA ya no da la orden por verificada. Su respuesta: «Home Assistant la da por
encendida, pero es un estado asumido (no lee el aparato); no puedo confirmarlo». Lo mismo vale para volumen, silencio y
la consulta de estado.

- Código: `walking-skeleton/aura_skeleton/adapters/home_assistant_real.py` (`_actuar`, `_actuar_atributo`, evidencia
  `estado_asumido_por_ha`), `core/orchestrator.py` (`_sin_efecto_de_hogar`, `_redactar_efecto_de_volumen`) y
  `core/hogar.py` (`describir_estado`).
- Pruebas: `tests/unit/test_home_assistant_real.py` y `tests/unit/test_hogar_consulta.py`.
- Mutantes: `mutaciones/veredicto-hogar.toml` VH22–VH24, los tres detectados.
- Verificación física pendiente: si la integración `samsungtv` real publica `assumed_state` (hoy no consta).
