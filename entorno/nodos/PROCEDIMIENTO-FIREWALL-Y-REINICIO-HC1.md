---
documento: "Procedimiento — cortafuegos de HC-1 y reinicio verificado"
fecha: 2026-10-07
estado: "PREPARADO. Requiere una persona con sudo y presencia en HC-1. Nada de esto se ha ejecutado."
corrige: "RESULTADO-NODO-01.md §5.3 decía «ufw está activo»: es FALSO [EJEC 2026-10-07]"
---

# Cortafuegos de HC-1 y reinicio verificado

## 1. Estado real medido `[EJEC]` 2026-10-07

- **ufw NO está activo.** `/etc/ufw/ufw.conf` → `ENABLED=no`; el servicio `ufw` es un *oneshot* `active (exited)` que no
  carga reglas. `RESULTADO-NODO-01.md` §5.3 («ufw está activo, pero el 4222 es alcanzable desde la LAN») es inexacto en
  su primera mitad.
- **Expuesto a la LAN:** `*:4222` (NATS, `listen: "0.0.0.0:4222"`, TLS y una credencial por nodo). Home Assistant tiene
  dos escuchas TCP efímeras en `192.168.20.38` y usa UDP 1900 (SSDP) y 5353 (mDNS). Ollama (11434) y la interfaz de HA
  (8123) solo escuchan en `127.0.0.1`.
- **Dispositivos que hablan con HC-1:** NODO-01 `192.168.20.139` (NATS 4222, y mDNS para encontrar a HC-1); TV
  `192.168.20.20` y `192.168.20.29` (integración `samsungtv` de HA).

## 2. Cortafuegos (necesita sudo)

Reglas mínimas: el 4222 solo para el nodo; mDNS abierto en la LAN, porque el nodo encuentra a HC-1 por ahí; las TV pueden
volver a hablar con HA. Lo demás, denegado por defecto.

```bash
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow from 192.168.20.139 to any port 4222 proto tcp   # NATS solo desde NODO-01
sudo ufw allow from 192.168.20.0/24 to any port 5353 proto udp  # mDNS: NODO-01 resuelve HC-1 por nombre
sudo ufw allow from 192.168.20.20                                 # TV (callbacks de HA a puertos efímeros)
sudo ufw allow from 192.168.20.29                                 # TV
sudo ufw enable
```

**Verificación inmediata** (todo tiene que dar lo esperado; si algo falla, revertir):

```bash
sudo ufw status verbose                                   # reglas de arriba, "Status: active"
cd walking-skeleton && AURA_RED=~/.aura-red python3 -m aura_skeleton --nodos   # nodo-01 ONLINE, secuencia que crece
# Desde OTRO equipo de la LAN que NO sea .139 (no hay otro autorizado en este procedimiento):
#   nc -z -w3 192.168.20.38 4222   -> debe FALLAR
```

Y una orden de voz a la TV de la sala (`Oye Aurora` → `enciende la televisión` → `sí`), comprobando el efecto en HA.

**Reversión:** `sudo ufw disable` (vuelve al estado medido en §1).

**Riesgo conocido:** si una TV cambia de IP por DHCP, HA dejará de recibir sus eventos hasta añadir la nueva regla. Lo
mismo con NODO-01: el 4222 queda cerrado para él si cambia de IP. Conviene reservarles IP fija en el router.

## 3. Reinicio verificado de HC-1 (necesita presencia)

HC-1 es la máquina donde corren AURA y las sesiones de Claude Code: **no se reinicia a ciegas** desde una sesión.

1. Antes: anotar el arranque actual con `uptime -s`.
2. Comprobar que no hay nada crítico en curso (mutación, Quality Gate, conversación con AURA).
3. Reiniciar (`systemctl reboot`) y esperar al arranque. **No hace falta iniciar sesión**: linger está activo.
4. Después, desde una terminal:
   ```bash
   entorno/nodos/verificar-tras-reinicio-hc1.sh "<arranque anotado en el paso 1>"
   ```
   Tiene que terminar en `Resultado: PASS`. Comprueba:
   - que el arranque es posterior al anotado;
   - linger, `aura-nats` y `aura-receptor-nodos` activos y habilitados;
   - `aura-hogar-ha` activo y HA en el 8123;
   - NATS en el 4222 y el mDNS de HC-1, que debe coincidir con su IP real;
   - nodo-01 ONLINE con **latido nuevo** (la secuencia crece en 20 s);
   - PARADA (a) y kill switch (b) sin cambios.

**Validado el 2026-10-07 sin reiniciar:**
- El verificador da hoy FAIL en un único punto, `aura-hogar-ha.service: inactive`, porque HA corre a mano hasta el
  próximo arranque. Es lo correcto.
- La comprobación de «hubo reinicio» falla si el arranque no es posterior (caso de control ejecutado).

## 4. Qué se dejó preparado sin sudo `[EJEC]` 2026-10-07

- `entorno/nodos/servicio-ha-usuario.sh instalar`: unidad de usuario `aura-hogar-ha.service`, **habilitada** para el
  próximo arranque y **no arrancada** (la instancia manual sigue en el 8123). Se revierte con `servicio-ha-usuario.sh retirar`.
- `entorno/nodos/verificar-tras-reinicio-hc1.sh`: verificador de solo lectura.
