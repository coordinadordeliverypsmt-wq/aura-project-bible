---
id: IE-015
titulo: Open-Smartwatch OS — organización de firmware, flags, config, consola y CI (patrones para NODO-01)
fuente: https://github.com/Open-Smartwatch/open-smartwatch-os
rama-revision: master (estable) y develop (beta) @ (último commit no visible; 1.997 commits)
fecha-revision: 2026-10-22
licencia: GPL-3.0
area: firmware
estado: investigado
cobertura: solo página principal y README (estructura de directorios, PlatformIO, configuración, consola serie, pruebas, workflows nombrados). No se leyó `platformio.ini`, `config.h.example`, código fuente ni el contenido de los workflows. No exige reloj ni firmware.
relacionadas: [IE-000]
---
## Qué se examinó (rutas y símbolos)
- Estructura: `src/` (firmware y apps), `include/config.h.example`, `lib/` (submódulos), `emulator/` (SDL2/CMake con pruebas unitarias y de interfaz), `scripts/`, `data/lua/`, `docs/`, `.github/`. [README]
- En AURA: `entorno/nodos/` (`empaquetar_nodo.py`, `desplegar-nodo.sh`), `aura_skeleton/nodo_agente.py`, `aura_skeleton/core/nodos.py` (Latido L68, `validar_latido`), `tests/unit/test_nodo_agente.py`. [CÓDIGO]

## Patrones relevantes
- Entornos de compilación nombrados (`pio run -e <env>`) y variantes («light edition»); funciones opcionales activadas por flags de compilación (p. ej. servidor de capturas). [README]
- Apps de ejemplo y no esenciales excluidas del build por defecto; se activan explícitamente. [README]
- Configuración por plantilla `config.h.example` → `config.h` local no versionado; se aplica una sola vez tras borrado o subida de «versión de configuración». [README]
- Consola serie con comandos mínimos (`help`, `configure`, `hostname`, `lock`, `reboot`, `time`, `wipe`) y monitor con trazas de excepción decodificadas. [README]
- Pruebas ejecutables sin hardware en un emulador de escritorio (unitarias + UI); workflows de CI separados por alcance (OS, emulador, feature) y de formato (`astyle`). [README]
- Rama estable vs. beta. [README]

## Límites, riesgos y dependencias
- Específico de ESP32/Arduino/PlatformIO y GPL-3.0; no reutilizable como código. [INFER]
- Consola serie con `wipe`/`configure` sin autenticación aparente: válido en dispositivo físico; en NODO-01 una consola equivalente debe ser de solo lectura por defecto. [INFER]
- Una versión de configuración que reaplica valores puede sobrescribir ajustes locales: requiere migración explícita. [INFER]

## Comparación con AURA
- Plantilla de config no versionada + valores locales: parcial; el agente lee `config.datos` (`nodo_agente.py`) y hay empaquetado en `empaquetar_nodo.py`. No se verificó si existe plantilla `.example` ni versión de esquema de configuración del nodo. Brecha posible, sin evidencia de uso real (CLAUDE.md §4: sin evidencia repetida no se desarrolla).
- Diagnóstico: el Latido y `validar_latido` (`core/nodos.py`) cubren el estado remoto; una orden local «diagnóstico» de solo lectura (versión, última conexión, expiración del certificado) no se ha comprobado. [INFER]
- Pruebas sin hardware: ya cubierto — `test_nodo_agente.py` prueba el agente con dobles (p. ej. TLS en L484) sin nodo físico. [CÓDIGO]
- CI por alcance: AURA usa un único `quality-gate.sh` (no CI remota); la mutación está aparte por decisión del CEO. Sin brecha.
- Flags de compilación/entornos: no aplican (Python, sin compilación); equivalente son variables `AURA_*` y capacidades registradas.

## Decisión
- **Adoptar como patrón (solo idea) y nada más:** (1) valores por defecto seguros: funciones opcionales fuera por defecto, activación explícita; (2) versión del esquema de configuración con migración declarada; (3) diagnóstico local de solo lectura. **Investigar más** (2) y (3) cuando exista un bloqueo observado en NODO-01. Descartar emulador, flags y consola con `wipe`.

## Validación mínima
- [PROPUESTA] Prueba unitaria: cargar una configuración de nodo con versión de esquema antigua/ausente y verificar que se rechaza o migra de forma explícita (caso de control: versión actual se acepta). Solo si se decide (2).

## Licencia y precauciones
- GPL-3.0: no copiar código, solo organización. No se necesita reloj, firmware ni PlatformIO. Nada se instala ni ejecuta.
