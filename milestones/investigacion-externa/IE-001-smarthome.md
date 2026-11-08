---
id: IE-001
titulo: "hansb001/smarthome — kit Arduino + gateway Raspberry + MQTT + Node-RED"
fuente: https://github.com/hansb001/smarthome
rama-revision: main @ b34e7c7 (último push 2022-10-24; último commit 2021-03-01)
fecha-revision: 2026-10-22
licencia: "Ninguna declarada (API GitHub: license=null). Sin licencia = todos los derechos reservados: NO copiar código"
area: hogar
estado: investigado
cobertura: "Leídos (vía WebFetch resumido, no lectura íntegra): README.md, flows/Gateway_flow, code/ArduinoCodeSmartHome.ino. NO leídos: flows/Local_flow, flows/MQTT_flow, code/NodeMCU, imágenes. Repo de 16 entradas; no tiene pruebas."
relacionadas: [IE-005]
---
## Qué se examinó (rutas y símbolos)
- `README.md` (arquitectura), `flows/Gateway_flow` (Node-RED: serial/MQTT/Slack/cámara), `code/ArduinoCodeSmartHome.ino` (protocolo serie).
- Es un tutorial/code pattern de IBM: placa Arduino (kit Keyestudio) → USB serie → Raspberry «gateway» → Mosquitto en otra Raspberry → panel Node-RED.

## Patrones relevantes
- [README] Separación en cuatro capas: sensores/actuadores (Arduino, NodeMCU), gateway (serie↔MQTT), broker, panel. Temas `smart/home/message`, `smart/home/message/picture`, `smart/garden/message`.
- [CÓDIGO] El gateway traduce a un protocolo serie de una letra por orden (`a`..`w`, `t/u/v/w` + `<valor>#`) a 9600 baud en `/dev/ttyUSB0` (Gateway_flow, .ino).
- [CÓDIGO] Los eventos suben por salida de texto libre («take picture», «Soil=», «danger») y el gateway los reparte con nodos `switch` por subcadena.
- [INFER] Patrón transferible: gateway que es el ÚNICO traductor entre un bus de mensajes y el hardware, con topics por dominio. Es lo que AURA distribuida (HC-1 + NODO-01) necesita conceptualmente; la implementación no es transferible.

## Límites, riesgos y dependencias
- [CÓDIGO] Los actuadores NO devuelven acuse ni estado (`.ino`: ningún ack; «actuator state is not reported and cannot be queried»). Es exactamente el anti-patrón «orden enviada = efecto logrado».
- [CÓDIGO] Sin autenticación ni TLS en MQTT (IP fija, puerto 1883, sin usuario); webhooks de Slack en claro dentro del flujo exportado (valores no reproducidos aquí). Slack = nube: choca con D24.
- [CÓDIGO] Sin validación de rangos; órdenes bloqueantes (`delay`); la lógica automática sobrescribe órdenes manuales; sin nodos `catch`.
- [README] Hardware específico (Keyestudio, Sense HAT, USB cam). Sin licencia, último commit 2021: sin mantenimiento.

## Comparación con AURA (ruta:símbolo de AURA, estado actual, brecha real o «ya cubierto»)
- `aura_skeleton/bus_nats.py` ya es el bus entre nodos; AURA tiene motor único y permisos, que este repo no tiene. Ya cubierto con mayor rigor.
- `adapters/home_assistant_real.py:_releer/_actuar` (L360/L377) verifica releyendo estado; este repo es el contraejemplo (sin verificación). Nada que adoptar.
- Brecha real: ninguna aprovechable. Valor: confirma por contraste la regla de contrato «orden → estado esperado → relectura».

## Decisión
**Descartar** como fuente de código; conservar solo la nota de arquitectura (gateway único + topics por dominio) como confirmación de lo ya decidido en `bus_nats.py`.

## Validación mínima
Ninguna requerida. Si se quisiera, test de arquitectura: ningún nodo publica órdenes de hardware sin pasar por el Motor Único (ya es invariante ALERTA-005).

## Licencia y precauciones
Sin licencia: no copiar. No instalar ni ejecutar flujos Node-RED (contienen URLs de Slack). Revisión parcial: no se afirma haber revisado `Local_flow`, `MQTT_flow` ni `NodeMCU`.
