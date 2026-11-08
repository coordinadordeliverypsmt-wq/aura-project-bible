---
documento: "Decision Package — NODO-01: segundo PC como extensión física distribuida"
tipo: "DECISION PACKAGE — perímetro y contrato técnico"
fecha: 2026-09-30
autor: "APUS-5 (CTO)"
estado: "APROBADO POR MISIÓN CEO (2026-09-30). EJECUTADO y desplegado en el nodo real el 2026-10-04 — ver RESULTADO-NODO-01.md. Declaraciones G-1 R-B aprobadas por el CEO el 2026-10-04."
reutiliza: "ADR-0018 (NatsEventBus reservado a E2 distribuido) · ADR-0021 (PerfilHardware, DetectorHardware, CapabilityManager) · ADR-0020 · contracts.Event"
---

# DP — NODO-01

## 1. Qué se autoriza (acta: la misión del CEO del 2026-09-30)

El CEO autoriza convertir el segundo PC en **AURA-NODE-01**, un nodo de INFRAESTRUCTURA. Este DP solo concreta
el contrato técnico, sin ampliar el alcance de la misión. **No** cubre:

- capacidades cognitivas remotas: LLM, Whisper, Piper o visión;
- la cámara o el audio como producto;
- autoridad del nodo sobre otros nodos o sobre AURA;
- autoevolución, porque PARADA sigue vigente;
- desbloquear CM1, R1, R2, R3 o R4.

D-3 tampoco cambia.

Las capacidades de la primera versión son: identidad lógica, informe de hardware, capability envelope, latido,
estado ONLINE/DEGRADED/OFFLINE/UNKNOWN, registro en HC-1, reconexión, recuperación tras reinicio y supervisión
por runit.

## 2. Por qué estas piezas y no otras (reutilización demostrada)

El inventario se hizo sobre el repositorio el 2026-09-30 [LECT].

| Necesidad | Qué existe | Decisión |
|---|---|---|
| Transporte entre procesos y máquinas | `bus_nats.NatsEventBus` (contrato `EventBus`). El ADR-0018 lo reserva «para E2 (multi-proceso / hogar / distribuido)». `nats-server` y `nats-py` 2.15 ya están en HC-1 [EJEC] | **Reutilizar.** No se inventa ningún protocolo. SSH queda **solo** para administración y arranque |
| Sobre del mensaje | `contracts.Event` | **Reutilizar.** `type = "nodo.latido.<nodo_id>"` |
| Medición de hardware | `DetectorHardwareLocal`: solo stdlib, lee `/proc` y `/dev/dri` | **Reutilizar y ampliar** con métricas de presencia (§4) |
| Derivar capacidades | `CapabilityManager` + `catalogo()` (ADR-0021) | **Reutilizar.** HC-1 evalúa el perfil del nodo con el MISMO catálogo. Ni el nodo ni HC-1 tienen una taxonomía propia |
| Identidad del nodo | No existe. `core/entorno.py` identifica dispositivos AJENOS por IP o identidad declarada, no nodos de AURA | **Crear** (mínimo) |
| Registro de nodos, latido, estado | No existe. Nada escucha en la red [EJEC `ss -ltn`] | **Crear** (mínimo) |

## 3. Arquitectura

```
NODO-01 (antiX, runit)                               HC-1
 aura_skeleton.nodo_agente                            nats-server (TLS + usuario por nodo)
   ├─ identidad_nodo  (uuid persistente)                   ▲
   ├─ DetectorHardwareLocal ─► latido ─► NatsEventBus ─────┘  (subject nodo.latido.<id>)
   └─ reconexión infinita; sigue vivo sin HC-1        aura_skeleton --receptor-nodos
                                                        ├─ valida (esquema cerrado, id del subject = id del cuerpo)
                                                        ├─ RegistroNodos ─► AURA_RED/nodos/registro.json
                                                        └─ aura_skeleton --nodos: estado + envelope + Manager
```

## 4. Contrato técnico

### 4.1 Identidad (`adapters/identidad_nodo.py`)

- Fichero `<datos>/nodo/identidad.json` con `{"nodo_id": uuid4().hex, "creado": ISO-8601}`. El directorio
  tiene permisos 0700 y el fichero 0600. Se escribe de forma atómica (tmp + rename). Si la ruta es un enlace
  simbólico, se rechaza.
- **No depende** de la IP, la MAC, el hostname ni el usuario. Sobrevive a cambios de IP y a reinicios.
- Si el fichero existe pero está corrupto, salta `IdentidadCorrupta`. **Nunca se regenera en silencio**: eso
  crearía «otro nodo» (INV-9).

### 4.2 Latido (`core/nodos.py`, puro)

Esquema cerrado `"nodo.latido/1"`. Los campos son EXACTAMENTE estos:

| campo | tipo | regla |
|---|---|---|
| `esquema` | str | == `"nodo.latido/1"` |
| `nodo_id` | str | `^[0-9a-f]{32}$` |
| `nombre` | str | 1-64 caracteres imprimibles. Es una etiqueta humana, NO la identidad |
| `secuencia` | int | ≥ 0. Empieza en 0 en cada arranque |
| `arranque` | str | `^[0-9a-f]{32}$`: un uuid por cada arranque del agente. Cuando cambia, el agente reinició |
| `intervalo_s` | float | 1 ≤ x ≤ 3600 |
| `recursos` | dict[str, float] | ≤ 64 claves `^[a-z0-9_]{1,40}$`; valores finitos (no bool) |
| `omitidas` | list[str] | métricas que el detector no pudo medir. Mismas reglas de clave |
| `agente` | str | versión del agente, ≤ 32 caracteres |

Un campo de más, un campo de menos o un tipo inválido producen `LatidoInvalido`.

### 4.3 Estado (`core/nodos.estado_nodo`, puro)

Se evalúa con el reloj **de HC-1** (`recibido_en`), nunca con el del nodo: así no hay deriva de reloj.

| Condición (en orden) | Estado |
|---|---|
| el receptor de HC-1 no da señales de vida | **UNKNOWN**: «HC-1 no está escuchando» |
| no hay ningún latido registrado | **UNKNOWN** |
| `ahora - recibido_en > 3 × min(intervalo_s, 60 s)` (el intervalo lo declara el propio nodo: no puede alargar el plazo más allá de 180 s) | **OFFLINE**: una conexión antigua no prueba que siga vivo |
| hay métricas `omitidas`, o faltan `ram_mb` o `nucleos` | **DEGRADED** |
| en otro caso | **ONLINE** |

### 4.4 Capability envelope

- `recursos` contiene solo **métricas medidas**, nunca marcas ni modelos.
- El detector añade métricas de **presencia**: `cpu_64bit` (flag `lm`), `proceso_bits`, `nucleos_fisicos`,
  `isa_ssse3`, `video_dispositivos` (`/dev/video*`), `audio_tarjetas` (`/proc/asound/cards`) y
  `red_interfaces` (`/sys/class/net` sin `lo`).
- Están al nivel **HARDWARE / INTERFAZ PRESENTE** de la jerarquía de la misión: **no** son capacidades
  habilitadas ni demostradas. El informe lo dice tal cual.
- `gpu_render > 0` significa «hay un nodo DRM». **No** significa que haya aceleración de IA.
- Las capacidades las decide **solo** `CapabilityManager.planificar` sobre el `PerfilHardware` del nodo.

### 4.5 Seguridad

- **NATS en HC-1** con estas protecciones:
  - TLS, con una CA privada generada en HC-1. Vive en `AURA_RED` (por defecto `~/.aura-red`, plano de red separado de `AURA_DATOS`) y **nunca** en el repositorio. La CA cumple X.509 estricto (keyUsage y basicConstraints críticos): Python 3.13 lo exige.
  - Un usuario por nodo, con contraseña aleatoria guardada en un fichero 0600.
  - **Permisos**: el nodo solo puede **publicar** en `nodo.latido.<su_id>`, no puede suscribirse a nada y no
    tiene respuestas.
  - `max_payload` 64 KiB y sin puerto de monitorización.
- **El receptor rechaza** cualquier latido cuyo `nodo_id` no coincida con el subject. Así no puede haber
  suplantación aunque una credencial se filtre hacia otro subject.
- **Verificación TLS en el nodo**: se ancla a la CA privada (`CERT_REQUIRED`) **sin** comprobar el hostname,
  porque la IP de HC-1 cambia por DHCP. La confianza la da la CA, no el nombre.
- **Configuración del nodo**: una lista de URLs de servidor en un fichero. La IP es configuración, nunca
  identidad.
- **No se hace** ni escaneo, ni cambios en el router, ni nada sobre el DVR o las cámaras.

## 5. Despliegue

- **Instalación en el nodo, en espacio de usuario:**
  - el código del subconjunto `aura_skeleton` y `nats-py` 2.15 copiado en `~/.aura-nodo/app`, sin pip y sin red;
  - los datos en `~/.aura-nodo`.
- **Supervisión con runit**: con el servicio `/etc/sv/aura-nodo` si hay root; si no, con un `runsvdir` de
  usuario. **No** se usa systemd en el nodo, ni contenedores.
- **En HC-1**: `nats-server` y el receptor como unidades de usuario. Se retiran con un script.
- **Rollback**: `entorno/nodos/retirar-nodo.sh` y `retirar-hc1.sh`.

## 6. Criterio de cierre (§22 de la misión)

Demostrado **ejecutando**:
- registro, identidad, informe de capacidades, latido y estado;
- el caso OFFLINE al desconectar;
- la reconexión;
- runit recuperando un proceso matado;
- la identidad conservada tras reiniciar;
- HC-1 reiniciado y el nodo registrándose de nuevo;
- los límites de seguridad;
- regresión, mutación y Quality Gate.

Cualquier punto no demostrado se registra como NO DEMOSTRADO.
