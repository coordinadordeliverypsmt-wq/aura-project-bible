---
id: IE-004
titulo: "Nerwyn/universal-remote-card — mando universal Lovelace multiplataforma"
fuente: https://github.com/Nerwyn/universal-remote-card
rama-revision: main @ 4f432e1 (2026-10-22)
fecha-revision: 2026-10-22
licencia: Apache-2.0
area: hogar
estado: investigado
cobertura: "Leídos (vía WebFetch resumido): README.md, src/models/maps/platforms.ts, src/models/maps/roku/defaultKeys.ts, src/models/interfaces/IConfig.ts, src/utils/defaultActions.ts. Árbol src/ listado completo. NO leídos: demás mapas por plataforma (android_tv, apple_tv, webos, samsung_tv…), remote-button.ts, base-remote-element.ts, IElementConfig.ts, IActions.ts. Sin carpeta de pruebas."
relacionadas: [IE-002, IE-003]
---
## Qué se examinó (rutas y símbolos)
`src/models/maps/<plataforma>/{defaultKeys,defaultSources,index}.ts` (15 plataformas + Generic Remote), `src/utils/defaultActions.ts` (`getDefaultActions`, `autofillActionTargets`), `IConfig.ts`, `platforms.ts`.

## Patrones relevantes
- [CÓDIGO] Capacidades por plataforma = DATOS: un mapa de teclas y otro de fuentes por plataforma; cada tecla es `{name, icon, tap_action:{action:'key', key}}`. `getDefaultActions(platform)` hace `switch` y devuelve `[defaultKeys, defaultSources]`.
- [CÓDIGO] La acción `key` es un atajo que cada plataforma traduce a una llamada de HA distinta (`remote.send_command`, `webostv.button`…) [README]; las plataformas sin mapeo NO admiten `key`.
- [CÓDIGO] `autofillActionTargets` rellena el objetivo (entity_id, config_entry_id, mac) según el dominio de la acción con `??=` (no pisa lo explícito).
- [CÓDIGO] «Generic Remote» se construye como UNIÓN deduplicada por nombre de las demás plataformas.
- [README] Admite que «no todas las teclas existen en todas las plataformas»; volumen depende de `media_player.volume_set`; teclado/búsqueda varían por plataforma.

## Límites, riesgos y dependencias
- [CÓDIGO] No comprueba `supported_features` ni estado `unavailable`/`off` (`defaultActions.ts`); plataformas desconocidas caen a Android TV por defecto (suposición silenciosa). La disponibilidad se declara, no se verifica en ejecución.
- [README] Plantillas nunjucks en casi todos los campos y acción «Evaluate JS» con acceso a `hass`: superficie de ejecución arbitraria (el propio README la marca peligrosa). Elementos personalizados desde `www`.
- Es solo frontend: no ejecuta nada sin HA.

## Comparación con AURA
- AURA representa capacidades por dominio en `core/entorno.py` (CONTROLABLE por dominio) y operaciones por contrato en `core/hogar.py`; no tiene catálogo de teclas por mando ni consulta `supported_features`. Brecha real: AURA no puede decir «este mando no tiene la tecla X» ni «esta entidad no admite volumen» antes de llamar.
- Lección [INFER]: el modelo bueno es plataforma → conjunto de teclas declarado (dato, auditable) y el defecto malo es el fallback silencioso. En AURA, tecla no declarada ⇒ «no sé hacerlo», nunca un valor por defecto (INV-9).
- No incorporar ejecución por plantillas/JS: violaría Motor Único.

## Decisión
**Adaptar el patrón de datos** (capacidades como tabla declarada por plataforma/dispositivo, sin fallback). **Descartar** código, plantillas y «Evaluate JS».

## Validación mínima
Test: dado un `media_player` de HA con `supported_features` sin `VOLUME_SET` (bit 4), la orden «sube el volumen» responde «ese dispositivo no admite volumen» y NO llama al servicio. Control: con el bit activo, llama.

## Licencia y precauciones
Apache-2.0 (exige atribución y aviso de cambios si se copia; no se copia). No instalar. Revisión parcial (ver cobertura).
