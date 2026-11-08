---
documento: "Estudio de reutilización — Muse Gadget SDK (facebookincubator/muse-gadget-sdk)"
fecha: 2026-10-22
tipo: "Estudio técnico. No instala, no adopta, no compra hardware."
evidencia: "[LECT] lectura web del repositorio del SDK (sin clonar ni ejecutar); [EJEC] grep sobre AURA"
---

# Muse Gadget SDK — ¿qué se puede reutilizar en AURA?

**Veredicto: DESCARTAR como dependencia; nada que adoptar. Los patrones útiles ya existen en AURA.**

## 1. Qué es `[LECT]`

- Licencia Apache-2.0. Creado el 2026-10-02 y activo; su README lo declara hobbyista («proceed at your own risk»).
- SDK para conectar dispositivos a «Muse», un producto de Meta. Partes:
  - `esp32/`: C/C++, BLE, audio y vídeo.
  - `linux/`: Python, `cryptography` y `websockets`.
  - Android y un simulador.
- Emparejamiento con un token de gadgets.muse.ai y una conexión WebSocket permanente a la nube de Muse.

## 2. Clasificación

| Parte | Dependencia |
|---|---|
| `esp32/` (boards, `muse_ble`, cuenta, chat, vídeo) | ESP32, BLE y nube de Meta |
| Emparejamiento por BlueZ, token y host de Muse | BLE y nube de Meta |
| `linux/src/musegadget/executor.py`, framing JSON, `link.register/invoke/result`, Noise XX | sin hardware, pero atado al servicio Muse |

## 3. El ejecutor Linux expone ejecución arbitraria

`COMMAND_SPECS` ofrece `system.run`: `/bin/bash -c` con el comando que envía Muse. Ofrece también `file.read` y
`file.write` sin lista blanca de rutas.

Esto choca de frente con tres reglas de AURA:
- «solo CAPACIDADES registradas, gobernadas por el Motor Único» (CLAUDE.md §4);
- D24 (local-first, sin claves de terceros);
- ALERTA-005 (ninguna ruta alternativa de ejecución).

Además, el propio README reconoce que el emparejamiento no impide un MITM activo. NODO-01 (32 bits, 1 GB) tampoco es su
objetivo.

## 4. Patrones aprovechables frente a lo que AURA ya tiene `[EJEC]`

| Patrón del SDK | En AURA |
|---|---|
| Matar el grupo de procesos al vencer el timeout | **Ya existe:** `adapters/microfono.py:60` termina el grupo entero al interrumpir (medido el 2026-10-06) |
| Timeouts en subprocesos | **Ya existe:** `adapters/voice_real.py:338-348` (`subprocess.run` con `timeout`, `TimeoutExpired` tratado) |
| Ejecutor genérico de comandos | **No aplica, y no debe existir:** `adapters/computador.py` no lanza procesos; solo ofrece capacidades registradas (listar/leer) |
| Resultado `{ok, payload \| error}`, `duration_ms`, `timed_out`, `truncated` | El Motor Único ya devuelve estado, detalle y audit; añadir campos sin una necesidad observada viola la regla de no crear componentes sin evidencia |
| Handshake Noise XX entre dispositivos | Solo tendría sentido para cifrar HC-1 ↔ NODO-01. El enlace ya tiene PKI propia (`entorno/nodos/red_hc1.py`); no hay bloqueo observado que lo justifique |

## 5. Conclusión

No hay ninguna primitiva que adoptar sin crear una segunda arquitectura de control. La mejora local prioritaria no
sale de Muse. Sale del uso real del hogar: el «veredicto de hogar veraz» del 2026-10-22, que ya está implementado.
Si algún día AURA necesitara ejecutar procesos por capacidad, el patrón de `microfono.py` es el de referencia.
