---
id: IE-005
titulo: "FunkeyFlo/ps5-mqtt — PS5 a Home Assistant por MQTT Discovery (envuelve playactor)"
fuente: https://github.com/FunkeyFlo/ps5-mqtt
rama-revision: main @ cce5651 (2026-10-16)
fecha-revision: 2026-10-22
licencia: MIT
area: hogar
estado: adoptado (concepto: observación despierta/reposo; 2026-10-22)
cobertura: "Leídos (vía WebFetch resumido): README.md, ps5-mqtt/server/src/{device.ts, services.ts, psn-auth-store.ts, psn-account.ts}, playactor/{discovery.ts, client.ts}, redux/sagas/{update-ha.ts, check-devices-state.ts, turn-on-device.ts, register-device.ts}. NO leídos: turn-off-device.ts, poll-*.ts, delay-for-transition.ts, web-server.ts, config.ts, pruebas (__tests__), la librería playactor (dependencia externa: protocolo Remote Play NO revisado)."
relacionadas: [IE-001]
---
## Qué se examinó (rutas y símbolos)
`playactor/discovery.ts` (`discoverDevices`, broadcast), `playactor/client.ts` (wake/standby/check vía CLI), `redux/sagas/check-devices-state.ts`, `turn-on-device.ts`, `register-device.ts`, `update-ha.ts`, `psn-auth-store.ts`, `psn-account.ts`.

## Patrones relevantes
- [CÓDIGO] Descubrimiento: broadcast UDP a `255.255.255.255` y a cada subred local (o una dirección configurada); resultados deduplicados por `device.id`; PS4 filtrada salvo `allowPs4Devices`.
- [CÓDIGO] Estado: `AWAKE`/`STANDBY`; si `check` falla ⇒ `status:"UNKNOWN"`, `available:false` (nunca se inventa un estado). Mensaje JSON retenido en `ps5-mqtt/<id>` con `power`, `device_status` (online/offline) y `activity`.
- [CÓDIGO] MQTT Discovery (`register-device.ts`): `switch` de energía (`payload_on` AWAKE, `payload_off` STANDBY, **`optimistic:false`**) y `sensor` de actividad; `availability` por plantilla; `unique_id` estable; QoS 1 + retain.
- [CÓDIGO] Credenciales PSN en `psn-auth.json` (dir 0700, fichero 0600, escritura atómica por rename, NPSSO guardado como hash SHA-256).
- [README] Solo hay control de energía: despertar y reposo.

## Límites, riesgos y dependencias
- [README] Solo desde/hacia modo reposo: el protocolo Remote Play de Sony no permite encender del todo/apagar; no inicia juegos. PS4 solo Awake/Standby.
- [CÓDIGO] Necesita credenciales de cuenta PSN (NPSSO + OAuth) y consulta presencia en `m.np.playstation.com`: NUBE de Sony. Esa parte es opcional para el control de energía [INFER, no confirmado: el control de energía usa playactor con credenciales almacenadas, cuyo registro inicial pasa por PSN]. Choca con D24 y con la exclusión vigente de PS5/PSN en la nube sin acta.
- [CÓDIGO] `turn-on-device.ts` actualiza el estado a AWAKE de forma OPTIMISTA tras `wake` resolver, sin releer; `transitioning` puede quedar activo ante fallo. En `check-devices-state.ts` un `break` salta los demás dispositivos de la pasada.
- [CÓDIGO] `client.ts` construye comandos de shell por interpolación (`sh.exec`) de IP, ruta y código: riesgo de inyección si vienen de configuración editable. `readStore()` vuelve a vacío ante error y un `save` posterior puede perder cuentas.
- Dependencia en Home Assistant OS/Supervised + broker MQTT + `playactor` (proyecto de terceros).

## Comparación con AURA
- `adapters/red_local.py` ya ve la PS5 por DDP (puertos 9302/987, `observacion_ddp` L382, `_buscar_ddp` L405), pasivo/dirigido. El descubrimiento ya está cubierto.
- AURA no tiene MQTT ni ejecutor para la PS5; `core/hogar.py` define encendida/apagada para `media_player` de HA, y `unavailable/unknown ⇒ no se envía`, que coincide con el `UNKNOWN`/`available:false` de este repo (ya cubierto).
- Brecha real: AURA mezcla en «apagada» los estados `off` y `standby`; para una PS5 `standby` (reposo) ≠ apagada y ningún mando puede pasar de apagada a encendida. [PROPUESTA] decirlo en la respuesta.

## Decisión
**Adaptar el patrón** (estado `UNKNOWN`/no disponible explícito y `optimistic:false`; reposo ≠ apagado). **No integrar** el ejecutor: requiere PSN en la nube y un ejecutor ajeno al Motor Único. Mantener sin acta cualquier uso de PSN. No hay MQTT que adoptar hoy.

## Validación mínima
Test sobre `core/hogar.py`/`home_assistant_real.py` con doble de HA: entidad PS5 en `standby` ⇒ AURA dice «en reposo» (no «apagada») y, ante `unavailable`, «no puedo saber su estado» sin enviar nada. Control: `off` ⇒ «apagada».

## Licencia y precauciones
MIT. No instalar ni ejecutar `playactor`; no contactar la consola ni PSN. No introducir NPSSO ni credenciales PSN en AURA. Revisión parcial (ver cobertura); el protocolo Remote Play queda sin revisar.

## Implementación en AURA (2026-10-22): observación despierta/reposo

Orden del CEO «Implementación D23 / IE-005». Se adoptó el **concepto**, no el código: el estado que declara la propia
consola por DDP.

- `adapters/red_local.observacion_ddp`: `HTTP/1.1 200 Ok` → `despierta`, `HTTP/1.1 620 Server Standby` → `en_reposo`.
  Cualquier otra respuesta → sin observación.
- `core/entorno`: guarda `estado_operativo` y `estado_visto` (la hora de lectura).
  - Una ronda sin respuesta conserva el último estado con su hora; nunca lo convierte en reposo.
  - Estados contradictorios en la misma ronda, o un conflicto de identidad, no se adoptan.
  - `describir` lo dice con su antigüedad: «último estado conocido» si tiene más de 15 min o la consola está ausente.
    Siempre añade «(lectura, no verificación física)».
- **No existe «apagada»:** que la consola no responda no la demuestra.
- Sin órdenes: la sonda sigue siendo solo `SRCH`; hay una prueba con socket simulado.
- Mutación: `mutaciones/estado-operativo-ps5.toml`, 16/16.
- Evidencia:
  - `despierta`: real (200 Ok el 2026-10-22, `../m3-entry/evidencia-tv-real-2026-10-22/RESULTADO.md`);
  - `en_reposo`: **solo simulado**, nunca observado en real.
- **Sigue pendiente de decisión del CEO:** cambiar `hogar.ESTADOS_APAGADA` (reposo ≠ apagada para acciones). No se tocó.
