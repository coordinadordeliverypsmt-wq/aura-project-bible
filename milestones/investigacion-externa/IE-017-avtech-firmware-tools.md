---
id: IE-017
titulo: BigNerd95/Avtech-Firmware-Tools — formato de firmware Avtech
fuente: https://github.com/BigNerd95/Avtech-Firmware-Tools
rama-revision: master @ último push 2022-09-16 (SHA no capturado)
fecha-revision: 2026-10-22
licencia: GPL-3.0 (SPDX, API de GitHub) — copyleft: no copiar código a AURA
area: firmware
estado: descartado
cobertura: LEÍDO (remoto, resumido): metadatos, árbol, README.md. NO LEÍDO: avfwtools.py, fw/README.md, los binarios fw/*.rar|zip (no se descargaron).
relacionadas: [IE-016, IE-018]
---
## Qué se examinó (rutas y símbolos)
`README.md` y árbol: `avfwtools.py` (órdenes `sign`, `unsign`, `info`), `fw/` con dos paquetes de firmware de un modelo Avtech.

## Patrones relevantes
- Cabecera de 200 bytes [README]: marcador (el propio tamaño de cabecera hace de magic), nombre de producto (64 B, p. ej. familia
  H264DVRAV76T), descripción (64 B), versión (64 B) y suma de comprobación de 4 bytes sobre el cuerpo.
- Checksum [README]: suma simple de todos los bytes (no criptográfica; no es firma ni autenticación).
- No documenta clave ni firma asimétrica [README]; «sign» es solo reempaquetar con cabecera y suma.
- El README no menciona Xiongmai [README].

## Límites, riesgos y dependencias
- Es herramienta para modificar y reempaquetar firmware: ofensivo/modificación, fuera del alcance defensivo. No se hace nada con ella.
- Solo Avtech; mantenimiento parado desde 2022.

## Comparación con AURA
Sin equivalente ni necesidad. AURA no analiza ni flashea firmware. Un identificador de producto/versión en la cabecera sería, a lo sumo,
una forma de que el **propietario** compare lo que muestra su pantalla con un nombre de modelo (no aplica a Xiongmai).

## Decisión
**DESCARTAR** (para H2 aporta solo una señal débil: ver abajo).
¿Aplica a Xiongmai? **[INFER] casi seguro no**: (1) la ficha de IE-018 describe otro paquete (varias imágenes de sistema de ficheros
comprimidas + descriptor de instalación), no una cabecera plana de 200 B con suma de bytes; (2) este formato está acotado por el
nombre de producto Avtech; (3) la plataforma observada en el DVR (`uc-httpd`, «NETSurveillance WEB», DVRIP 34567) es Xiongmai/XMeye.
No se midió ningún firmware Xiongmai: es inferencia, no verificación.
Indicio que SÍ podría favorecer H2: ninguno hoy. La interfaz web de Avtech suele ser otra (no se verificó); si el propietario
leyera una pantalla con «Avtech», la hipótesis cambia.

## Validación mínima
Ninguna sobre firmware. Si el propietario facilita marca/modelo/versión de su pantalla, basta compararlos con esta cabecera de forma documental.

## Licencia y precauciones
GPL-3.0: no incorporar código. Los binarios de `fw/` son terceros no confiables: no descargar ni abrir.
