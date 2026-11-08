---
documento: "Verificación física real — TV de la sala (encendido) y PS5 (solo lectura)"
fecha: 2026-10-22
autorizacion: "Misión del CEO «Verificación física real de TVs y PS5» (2026-10-22): una prueba controlada de encendido/apagado de una TV; PS5 solo lectura"
evidencia: "[EJEC] salida-prueba.txt y audit-prueba.jsonl de esta carpeta (sin token: comprobado)"
---

# Verificación física real — 2026-10-22, 18:55-18:58 (UTC-5)

## 1. Identidad (solo lectura, 18:55:35)

| Entidad de HA | Integración | Fabricante / modelo | Estado | Desde |
|---|---|---|---|---|
| `media_player.tv_sala_fmilia_medina_un43ru7100fxza` | `samsungtv` (plantilla `integration_entities`) | Samsung, UN43RU7100 (.29 en el MAPA) | `off` | 18:52:44 |
| `media_player.samsung_6_series_55_un55ku6000` | `samsungtv` | Samsung, UN55KU6000 (.20 en el MAPA) | `on`; volumen 0,4; sin silencio | 18:50:38 |

En ambas, `device_class: tv`, `supported_features: 24509` y sin `assumed_state`. En HA no hay ninguna integración de
PlayStation (`ps4` y `playstation_network` vacías).

La TV de la sala es la única con nombre familiar en AURA: `composicion.NOMBRE_HUMANO_DE_VOZ` → «la TV de la sala».

## 2. Prueba controlada: una sola orden

**Por qué «encender» la TV de la sala:**
- El propietario dijo haber encendido las TVs, pero HA veía la de la sala `off`. Encenderla devuelve el estado que él
  quería y no deja la casa en un estado inesperado.
- Apagar la TV de 55", que estaba encendida, habría ido en contra de su intención.

**Comprobaciones previas:**
- Kill switch de producto (`~/.aura/KILL`): no existe.
- `entorno/control-plane/PARADA`: es la parada del motor autónomo, no del producto; no se tocó.

**Camino:** el de AURA en producción.
- `composicion.componer` con `AURA_HA_URL`/`AURA_HA_TOKEN` → adaptador **HomeAssistantReal** («hogar: REAL vía Home
  Assistant … API running»).
- Core determinista → permisos → Motor Único → adaptador.
- Proveedor del modelo sustituido por un espía: **0 consultas**.
- Datos en un directorio temporal: `~/.aura` no se tocó.

| Hora (UTC-5) | Hecho | Fuente |
|---|---|---|
| 18:56:54.593 | Estado previo `off` (desde 18:52:44) | lectura directa de HA |
| 18:56:54.835 | «enciende la tele de la sala» entra en AURA | script |
| 18:56:54.837 | `lista verde encender_dispositivo -> auto-ejecucion` | audit |
| 18:56:54.853 | **Orden enviada:** `EJECUTA turn_on sobre media_player.tv_sala_…` | audit |
| — | **Orden aceptada:** el POST no devolvió error HTTP (si no, `HogarOrdenRechazada`). AURA no la registra con hora propia | inferido del flujo `[INFER]` |
| 18:57:05.383 | HA registra `last_changed` → `on` | HA |
| 18:57:05.450 | **Estado observado por AURA** al releer: `off -> on (verificado=True)` | audit |
| 18:57:05.490 | AURA responde: «Listo: Home Assistant ve la TV de la sala encendida.» (10,7 s) | consola |
| 18:57:05.490 | `on`, sin `assumed_state` | lectura directa de HA |
| 18:57:15.492 | Sigue `on` (+10 s) | lectura directa de HA |
| 18:57:49 | Sala `on`; la de 55" sigue `on` desde 18:50:38: **no se tocó** | lectura directa de HA |

**Clasificación: PHYSICAL_EFFECT_VERIFIED, mediante el estado que reporta Home Assistant.**
- No hubo inspección visual independiente.
- Para `samsungtv`, `on` significa que la propia TV responde por red. Es una evidencia fuerte, pero no es una
  observación de la pantalla.
- Hubo una sola orden, sin reintentos ni orden opuesta.

**Lo que esto demuestra fuera de los dobles:**
- Resolución por nombre familiar.
- Lista verde y Motor Único.
- Relectura hasta el estado pedido dentro de `ESPERA_CONFIRMACION_S=15`: tardó 10,6 s.
- Respuesta que nombra a HA como fuente.

**Lo que NO se observó:** la TV real reportó `on`, no `playing`. Siguen sin observarse en real `playing`, `standby`,
`unavailable` y `assumed_state`, que solo están probados con dobles.

## 3. PS5: solo lectura, sin ninguna orden

Vía `red_local._buscar_ddp`, el productor DDP de AURA: un `SRCH` de estado sin órdenes, igual al del descubrimiento
aprobado.

| Hora | Respuesta | `host-type` | IP |
|---|---|---|---|
| 18:57:33 | `HTTP/1.1 200 Ok` (despierta) | — | .36 |
| 18:57:49 | `HTTP/1.1 200 Ok` (despierta) | PS5 | .36 |

En DDP, el reposo responde `620 Server Standby`, y apagada o sin red no responde.

**Lo que AURA sabe hoy:** que hay una PS5 en la `.36`. Lo que **no conserva**: `observacion_ddp`
(`adapters/red_local.py:382-402`) acepta 200 y 620, pero solo guarda la identidad. AURA no puede decir si está despierta
o en reposo aunque el protocolo lo da. Es una capacidad que falta, no un defecto: el docstring declara ese propósito.
Añadirla cambia el contrato de `Observacion`/`Dispositivo` y requiere decisión (D23; semántica de reposo pendiente en
IE-005).

Lo que AURA no puede hacer con lo que existe:
- encender la consola desde apagada;
- conocer el juego en curso (solo vía PSN, excluido por D24).

Tampoco lo intentó. No se registraron `host-id` ni el nombre de la consola.

## 4. Código

No hubo cambios: no apareció ningún defecto en la cadena probada.
