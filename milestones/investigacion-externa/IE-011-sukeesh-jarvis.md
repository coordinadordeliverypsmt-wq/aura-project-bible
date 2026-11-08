---
id: IE-011
titulo: sukeesh/Jarvis — asistente por línea de comandos con plugins
fuente: https://github.com/sukeesh/Jarvis
rama-revision: master @ 2026-10-22 (commit no visible; 1.815 commits declarados)
fecha-revision: 2026-10-22
licencia: MIT
area: asistentes
estado: descartado
cobertura: README del repo y jarviscli/plugin.py (vía WebFetch, resumen). NO se leyó el cargador/descubrimiento de plugins, ni los plugins concretos, ni la configuración, ni tests.
relacionadas: [IE-010, IE-000]
---
## Qué se examinó (rutas y símbolos)
- `jarviscli/plugin.py`: `plugin(name)`, `require(network, platform, native)`, `complete`, `alias`, `PluginStorage`, `Plugin.init/run`, `_plugin_run_with_network_error`.
- README: carpeta `custom/`, `doc/PLUGINS.md`, instaladores.

## Patrones relevantes
- [CÓDIGO] Registro por decorador `@plugin("nombre")` que convierte función/clase en subclase `Plugin` con `_backend`; `@require` declara requisitos (red/plataforma/nativo) como metadatos; `@alias`/`@complete` para sinónimos y autocompletado.
- [CÓDIGO] Árbol de comandos: `PluginStorage` con subplugins; un plugin sin backend es solo padre y, si no reconoce subcomando, responde «no reconocí el comando; ¿quisiste decir…?» con la lista.
- [CÓDIGO] Un solo manejo de error explícito: `ConnectionError` -> `connection_error()` (docstring dice que se aplica con `require(network)`, el cableado no se vio).
- [README] Plugins = ficheros Python en `custom/` cargados dinámicamente; configuración mínima (sonido desactivado por defecto), sin fichero de configuración descrito.
- [INFER] Cualquier plugin es código arbitrario con acceso total al SO; no hay modelo de permisos, dry-run ni auditoría en lo leído.

## Límites, riesgos y dependencias
- Ejecución arbitraria por diseño (carga de código de usuario): DESCARTADA para AURA.
- Mantenimiento incierto: CI declarado en travis-ci.org, sin releases, 84 issues/43 PR abiertas [README; inferencia de abandono parcial no confirmada].
- Orientado a escritorio y teclado, no a hogar/voz continuo.

## Comparación con AURA
- `aura_skeleton/core/capability_registry.py` (Registro de Capacidades C1, ADR-0021 §2.4) y `core/capacidades.py` `Capacidad` (L155) ya registran capacidades nombradas por resultado, con `core/permissions.py` (listas verde/roja) y el Motor Único; es un superconjunto en control.
- Única idea aprovechable: requisitos declarados como metadatos (`require`) y la respuesta «¿quisiste decir…?» ante comando no reconocido, que ya encaja con la regla INV-9 (no fingir capacidad). Comprobar si AURA, ante una capacidad no registrada, sugiere las más cercanas en vez de solo negar [INFER, no verificado].

## Decisión
- Descartar. Opcionalmente adaptar la sugerencia de alternativas al rechazar un comando no registrado (solo texto, sin ejecución).

## Validación mínima
- Prueba: ante una orden desconocida el orquestador responde con alternativas del registro y NO ejecuta nada (auditoría sin `ejecuto`). Mutante: que una coincidencia aproximada ejecute -> debe fallar la prueba.

## Licencia y precauciones
- MIT. No instalar ni cargar plugins de terceros.
