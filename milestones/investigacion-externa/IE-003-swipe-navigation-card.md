---
id: IE-003
titulo: "Tjstock/swipe-navigation-card — tarjeta Lovelace de gestos y botones"
fuente: https://github.com/Tjstock/swipe-navigation-card
rama-revision: master @ d8b9440 (2026-02-11)
fecha-revision: 2026-10-22
licencia: MIT
area: hogar
estado: investigado
cobertura: "Leídos (vía WebFetch resumido): swipe-navigation-card.js (fichero único), README.md. NO leídos: .github/workflows/validate.yaml, hacs.json. No hay pruebas en el repo (árbol completo: 18 entradas)."
relacionadas: [IE-004]
---
## Qué se examinó (rutas y símbolos)
`swipe-navigation-card.js`: `set hass`, `initializeCard`, `buildAndAppendButton`, `touchStart/touchMove/touchEnd`, `buttonDown/buttonRelease`, `callHassAction`, `setConfig`.

## Patrones relevantes
- [CÓDIGO] Separación UI↔acción por EVENTO: la tarjeta no llama a servicios; emite un `CustomEvent('hass-action')` (burbujea, compuesto) con la configuración y es el frontend de HA quien ejecuta (`callHassAction`). La tarjeta es declarativa: mapea gesto → acción configurada.
- [CÓDIGO] Validación temprana de configuración (`setConfig` lanza si `hold_repeat_ms` fuera de 100–2000 o si hay varias fuentes de carátula).
- [CÓDIGO] Autorrepetición en pulsación larga (`hold_repeat_ms`) con temporizador cancelable.
- [CÓDIGO] No usa `innerHTML`/`eval`.

## Límites, riesgos y dependencias
- [CÓDIGO] Sin accesibilidad: sin ARIA, `tabindex` ni teclado; solo puntero/táctil.
- [CÓDIGO] UI y lógica de gestos mezcladas en el setter `hass` (el propio código tiene un `//TODO`); errores de reinicio (`xDown, yDown... = null` con operador coma); posible inyección CSS por URL sin escapar en `setBackgroundCoverArt`.
- No es motor de control: delega todo en HA y no conoce estados ni capacidades.

## Comparación con AURA
- AURA no tiene capa de UI de gestos; las superficies deterministas (ADR-0014) no consultan al LLM. El patrón «UI declara intención, otro ejecuta» ya está cubierto por el Motor Único (ALERTA-005). Brecha real: ninguna.
- La falta de accesibilidad es contraejemplo para cualquier futuro panel: [PROPUESTA] exigir operación por teclado/voz de toda acción en un panel AURA.

## Decisión
**Descartar** (sin valor adicional). Solo se conserva la lección de accesibilidad y de «gesto → intención nombrada → ejecutor único».

## Validación mínima
Ninguna requerida.

## Licencia y precauciones
MIT. No instalar. Revisión parcial (README + JS vía resumen; workflow y `hacs.json` sin leer).
