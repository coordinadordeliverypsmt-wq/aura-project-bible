---
id: IE-018
titulo: zzHAMZAzz/Custom-Firmware-For-Chinese-CCTV-DVR — guía anecdótica (Floureon)
fuente: https://github.com/zzHAMZAzz/Custom-Firmware-For-Chinese-CCTV-DVR
rama-revision: master @ último push 2018-10-25 (SHA no capturado)
fecha-revision: 2026-10-22
licencia: sin licencia declarada (SPDX null) — derechos reservados; no copiar
area: firmware
estado: investigado
cobertura: LEÍDO (remoto, resumido): metadatos, árbol (solo README.md), README.md. NO LEÍDO: nada más existe en el repo. No se descargó ningún firmware.
relacionadas: [IE-016, IE-017]
---
## Qué se examinó (rutas y símbolos)
Único fichero `README.md`: relato de un usuario que modifica el firmware de un DVR vendido como «Floureon».

## Patrones relevantes
- Plataforma [README]: sistema Linux; objetivo ARM; **no nombra** SoC, HiSilicon, Xiongmai ni OEM. «Muchas marcas, mismo SO y GUI».
- Identificación de modelo/firmware [README]: el autor lee un número de 8 dígitos en la pantalla del equipo (menú de información →
  versión, tras el prefijo «R11»; ejemplo del texto: 00000117) y lo usa para buscar el paquete en una web de terceros.
- Compatibilidad con XMEye [README]: afirma ver remotamente por XMEye; algunas unidades traen SSH habilitado, la suya no.
- Estructura del paquete [README]: varias imágenes de sistema de ficheros comprimidas + un descriptor de instalación que decide qué se actualiza.
  Las instrucciones de modificación y reempaquetado se omiten deliberadamente; **no se analizan ni se recomiendan**.
- Fiabilidad: relato de un solo usuario, firmware de sitios no oficiales, integridad sin verificar [INFER].

## Límites, riesgos y dependencias
Origen no oficial; 2018; sin licencia. Cualquier flasheo puede inutilizar el equipo y anular la garantía: fuera de alcance (solo análisis).

## Comparación con AURA
El dato aprovechable es **el método de identificación**: la pantalla de información del DVR muestra versión y, normalmente, modelo/ID/MAC.
AURA no tiene hoy ese dato (el propietario solo dice «Amtech»). Sin brecha de código; brecha de conocimiento: marca/modelo/versión reales.
Fuerza H3 solo en cuanto a «formato de número de versión»; no prueba que sea la misma plataforma que el DVR de .80.

## Decisión
**SOLO REFERENCIA**. Útil para saber qué leer en pantalla; nada de firmware.

## Validación mínima
Pedir al propietario que lea y transcriba la pantalla de información (ver sección de datos mínimos en el informe del encargo). Si el número de
versión sigue un patrón similar (prefijo de versión + dígitos), anotar «compatible con H3», no más.

## Licencia y precauciones
Sin licencia: no reproducir texto ni procedimientos. No descargar paquetes de firmware de terceros. Nada se flashea.
