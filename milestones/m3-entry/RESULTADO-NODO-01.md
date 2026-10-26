---
documento: "RESULTADO — NODO-01: segundo PC como extensión física distribuida"
fecha: 2026-10-04
dp: "DP-NODO-01.md (misión del CEO del 2026-09-30)"
veredicto: "NODO-01 OPERATIVO y demostrado en hardware real, incluido el reinicio físico del nodo (p7). Queda sin demostrar el reinicio completo de HC-1."
---

# RESULTADO — NODO-01

Etiquetas de evidencia: [EJEC] medido ejecutando · [LECT] leído · [INFER] deducido. Las salidas en bruto
están en `evidencia-nodo-01/`.

## 1. Qué existe ahora

```
AURA (HC-1, Celeron N4020, 3,6 GB)                         NODO-01 (Atom N450, 986 MiB, antiX i686, runit)
  aura-nats.service  (nats-server, TLS, :4222)  ◄── latido nodo.latido.<id> cada 10 s ──  aura_skeleton.nodo_agente
  aura-receptor-nodos.service                                                          (runsvdir de usuario + @reboot)
  python3 -m aura_skeleton --nodos   →  envelope de HC-1 + envelope de cada nodo + decisión del CapabilityManager
```

`--nodos` en HC-1 [EJEC] (2026-10-04 05:03):

| | HC-1 | NODO-01 |
|---|---|---|
| ram_mb | 3719 | **986** |
| nucleos (hilos) / nucleos_fisicos | 2 / 2 | 2 / **1** |
| cpu_64bit / proceso_bits | 1 / 64 | 1 / **32** (CPU de 64 bits con sistema i686) |
| isa_sse4_2 / isa_ssse3 / isa_avx2 | 1 / 1 / 0 | **0** / 1 / 0 |
| gpu_render / video_dispositivos / audio_tarjetas / red_interfaces | 1 / 2 / 1 / 1 | 1 / 2 / 1 / 2 |
| disco_libre_mb | 7517 | 213800 |
| CapabilityManager | memoria = DEGRADADA | memoria = DEGRADADA |

Los dos sobres son **distintos y están medidos**, no asumidos. Las capacidades las decide el MISMO
`CapabilityManager` con el MISMO catálogo (INV-1). Las métricas de presencia —GPU, vídeo, audio y red— se muestran
con una nota explícita: hay HARDWARE/INTERFAZ PRESENTE, **no** capacidad habilitada ni demostrada (INV-9).

## 2. Pruebas físicas en el hardware real

| # | Escenario | Resultado | Evidencia |
|---|---|---|---|
| 1 | SIGKILL al agente | runit lo relanza en < 5 s. HC-1 registra `reinicios: 1` con la MISMA identidad | `p1-runit-recupera.txt` [EJEC] |
| 2 | El nodo deja de latir (`sv down`) | HC-1 lo pasa a **OFFLINE** a los 25 s (tolerancia 3×10 s). Al volver: ONLINE en 3 s | `p2-offline-y-vuelta.txt` [EJEC] |
| 3 | HC-1 sin bus (`nats-server` parado) | El nodo **sigue vivo** (mismo PID, `conectado=false`) y HC-1 dice **UNKNOWN** (no ONLINE). Al volver el bus: ONLINE en 6 s, **sin reiniciar el agente**, con la secuencia continua | `p3-hc1-sin-bus-y-reconexion.txt` [EJEC] |
| 3-v1 | La misma prueba ANTES del arreglo | **Defecto encontrado**: `Requires=` mataba el receptor al parar el bus | `p3-v1-defecto-requires.txt` [EJEC] |
| 4 | Reinicio de los servicios de AURA en HC-1 | El receptor reiniciado recarga el registro y **recibe latidos nuevos** (secuencia 20 > 19). Linger activo; unidades habilitadas | `p4-reinicio-servicios-hc1.txt` [EJEC] |
| 5 | Ataques desde el nodo con SU credencial | Ver lista debajo de la tabla | `p5-limites-seguridad.txt` + `p5-arnes-ataques.py` [EJEC] |
| 7 | **Reinicio FÍSICO del N450** | El equipo arrancó a las 07:49:13. El `@reboot` de cron lanzó `runsvdir` a las 07:49:42 y el agente conectó en unos 2 s. HC-1 lo ve ONLINE con el MISMO nodo_id; `reinicios` pasó de 2 a 3 | `p7-reinicio-fisico.txt` [EJEC] |
| 6 | Arranque sin sudo | `@reboot runsvdir` en la crontab del usuario y `runsvdir` vivo. Es la ruta que se usa al no haber sudo | `p6-arranque-sin-sudo.txt` [EJEC] |

Resultados de la prueba 5:
- **Suscribirse:** DENEGADO.
- **Publicar en el subject de otro nodo:** DENEGADO.
- **Suplantar a otro nodo desde el cuerpo del mensaje:** HC-1 lo rechaza y el nodo fantasma no se registra.
- **Conectar sin credencial o con una errónea:** falla.
- **Conectar sin la CA:** falla.
- **Puertos y secretos:** solo escucha el 4222, y la contraseña no aparece ni en `ps` ni en el log.

Consumo del agente en el N450: **26 MB de RSS** [EJEC `ps`]. El nodo conserva unos 730 MiB disponibles.

## 3. Defectos encontrados y corregidos

La auditoría independiente y el despliegue real encontraron estos defectos, ya corregidos:

| Defecto | Cómo se encontró | Corrección | Red |
|---|---|---|---|
| H-1 (HIGH): `Event.type` tomado del cuerpo, que permitía suplantar a otro nodo | Auditoría de seguridad | `type = msg.subject` en `bus_nats.py` | Prueba contra nats-server real + mutante H1 + física p5-A3 |
| M-1: un nodo podía alargar su ONLINE declarando `intervalo_s=3600` | Auditoría | Tolerancia = 3 × min(intervalo, 60 s) | Prueba + mutante M1 |
| M-2: el receptor latía aunque estuviera desconectado del bus | Auditoría | Solo late si `bus.conectado` | Prueba + mutante M2 + física p3 |
| CA sin `keyUsage`, rechazada por Python 3.13 (`VERIFY_X509_STRICT`) | **Solo en el nodo real**: HC-1 tiene Python 3.12 | CA y servidor con extensiones X.509 correctas, y STRICT explícito en el agente y el receptor para que HC-1 y el nodo verifiquen igual | Handshake estricto real + mutante D3 |
| La conexión inicial de nats-py era infinita: SIGTERM no funcionaba y no había estado local | **Solo en el nodo real** | `_conectar_acotado`: tope de 20 s e interrumpible por la parada; `error_cb` sin trazas | Pruebas + E2E sin servidor + mutantes D1 y D2 |
| `Requires=` dejaba muerto el receptor | Prueba física 3 | `Wants=` + `Restart=always` | Física p3 v2 |
| M-4 crontab, M-5 linger, L-2, L-3, L-4 (scripts) | Auditoría | Corregidos en `entorno/nodos/*.sh` y en `red_hc1.py` | `bash -n`; M-4, M-5 y L-3 ejecutados en real (p4, p6). **Sin pruebas automáticas** (reauditoría N-4) |

## 4. Verificación

- **Pruebas de la misión:** 291 en verde, incluidas las E2E contra nats-server real [EJEC].
- **Mutación:**
  - `nodo-01.toml`: **66/66** detectados, en tres pasadas sucesivas (60 + 3 + 3);
  - `detector-hardware.toml`: **32/32**.

  Todo [EJEC] y con los ficheros intactos tras cada pasada (`cmp`).
- **G-1:** las declaraciones R-B se aprobaron (CEO, 2026-10-04) y se hicieron por operación en
  `architecture_manifest.toml`; `test_g1_ruta_unica.py` da 24/24 [EJEC].
- **Quality Gate:** ver §7.

## 5. Qué NO está demostrado

1. ~~Reinicio físico del N450~~: **DEMOSTRADO** el 2026-10-04 (p7).
2. **Reinicio completo de HC-1.** Solo se reiniciaron los servicios (p4). Linger está activo, pero el arranque
   sin sesión no se ha observado.
   **DEMOSTRADO 2026-10-07 `[EJEC]`:** HC-1 arrancó a las 02:17 sin intervención de ninguna sesión; NATS, receptor y
   Home Assistant (nueva unidad `aura-hogar-ha.service`) volvieron solos por linger; verificador `PASS` con latido
   nuevo del nodo (evidencia `evidencia-nodo-01/p9-reinicio-completo-hc1.txt`).
3. **Firewall.** `ufw` está activo, pero el 4222 es alcanzable desde la LAN. Restringirlo a la IP del nodo exige
   sudo en HC-1 (`sudo ufw allow from <ip-nodo> to any port 4222 proto tcp` + deny). TLS y las credenciales por
   nodo protegen el puerto entre tanto.
   **Corrección 2026-10-07 `[EJEC]`:** ufw **no** está activo (`/etc/ufw/ufw.conf` → `ENABLED=no`; el servicio es un
   oneshot `active (exited)` sin reglas). Procedimiento con las reglas exactas, verificación y reversión:
   `entorno/nodos/PROCEDIMIENTO-FIREWALL-Y-REINICIO-HC1.md`.
4. **Rotación de la PKI con nodos ya desplegados.** `regenerar-pki` está probado de forma automática y se usó
   una vez antes del despliegue definitivo; la rotación del certificado (caduca el 2029-01-06) no tiene aviso.
5. **Scripts** sin pruebas ni mutantes (reauditoría N-4).
6. **El nodo no resuelve `.local`** (le falta nss-mdns): usa la IP de respaldo de `nodo.conf`. Si HC-1 cambia de
   IP por DHCP, hay que redesplegar la configuración o dar al nodo resolución mDNS. La identidad NO depende de esto.

## 6. Fronteras respetadas

- No se instaló ninguna capacidad cognitiva en el nodo: el paquete son 16 módulos de `aura_skeleton` más `nats`,
  y no incluye orchestrator, LLM, voz ni composicion.
- PARADA sigue vigente.
- CM1, R1, R2, R3, R4, D-3 y L4 no se han tocado.
- No se ha tocado `main`.
- No se ha tocado el DVR, ni las cámaras, ni el router.
- No hay secretos en el repositorio: la PKI y las credenciales están en `~/.aura-red` y `~/.aura-nodo`, en 0600/0700.
- No se ha añadido hardware.

## 7. Quality Gate

`./quality-gate.sh` del 2026-10-04 [EJEC]: **FAIL global**, por **deuda PREEXISTENTE**. El delta de esta misión es **0**.

| Bloque | Resultado | ¿Viene de NODO-01? |
|---|---|---|
| ruff check | PASS | — |
| formato | 31 ficheros sin formatear. Uno era `tests/unit/test_detector_hardware.py` (de la misión) y ya está formateado. Quedan **30, todos preexistentes** | 0 tras la corrección |
| mypy | 3 errores: `entorno.py:390`, `camara_rtsp.py:51` y `:53` | No: son los mismos de antes de la misión |
| pruebas | **2917 passed**, 2 failed, 1 skipped, 1 xfailed | No: los dos fallos son preexistentes |

Los dos fallos de pruebas:
- `test_cognicion_local`;
- `test_garantias_vigentes`: el gate encontró 31 garantías rotas. Una era `nodo-01.toml:R13`, cuya ancla dejó de existir con el arreglo de M-2. Se reancló al bucle nuevo, vuelve a detectarse (1/1) y protege también la llamada real en `ejecutar` (reauditoría N-3). Quedan **30/1429, ninguna de la misión**.

El gate NO es PASS. La deuda preexistente (formato de 30 ficheros, 3 errores mypy, `test_cognicion_local`, 30 garantías obsoletas) no es de esta misión y no se ha tocado.
