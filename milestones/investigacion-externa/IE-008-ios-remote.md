---
id: IE-008
titulo: iOS-remote — control de iPhone por USB, WebDriverAgent y navegador
fuente: https://github.com/DimCyan/iOS-remote
rama-revision: main @ e4951f5 (2021-10-16, último push)
fecha-revision: 2026-10-22
licencia: GPL-3.0
area: camaras-moviles
estado: descartado
cobertura: LEÍDO (remoto) — README completo, `app.py` completo (vía raw), API de repo y último commit. NO leído — `static/`, `templates`, `device.json`, `requirements.txt` (no listado), guía upstream de WebDriverAgent. Nivel de inspección: README + código del servicio (medio). No se clonó ni ejecutó nada.
relacionadas: [IE-007]
---
## Qué se examinó (rutas y símbolos)
- `README.md`; `app.py` (rutas Flask `/remote`, `/click`, `/drag`, `/home`, `/backspace`, `/enter`, `/send`, `/lock`, `/screenshot`, `/rotation`, `/reboot`; funciones `_get_bundle_id`, `connect_device`).

## Patrones relevantes
- [README] Conexión por USB sin jailbreak; pantalla y control en navegador (multiplataforma). Requiere compilar e instalar WebDriverAgent-Runner en el dispositivo; usa `tidevice wdaproxy` (puerto 8100) y `tidevice relay 8200 9100`; servicio Flask en 5000.
- [README] «El soporte depende de la versión de WebDriverAgent»; probado hasta iOS 15; Xcode y Python sin fijar. Dependencia frágil de versiones.
- [README] No describe emparejamiento, confianza ni autorización más allá de instalar WDA; [INFER] el emparejamiento lo hace iOS por USB (diálogo «Confiar en este equipo») y la firma de WDA exige cuenta de desarrollador de Apple: no documentado aquí.
- [CÓDIGO] Sin autenticación en ninguna ruta; CORS abierto a cualquier origen (`origins: "*"`, y `support_crenditals` mal escrito); `app.run(debug=True)` (depurador Werkzeug); `/remote` pasa texto del usuario a `subprocess.Popen(..., shell=True)` (inyección de comandos); `/reboot` reiniciar dispositivo sin confirmación; JSON sin validar.
- [CÓDIGO] Enlaza a 127.0.0.1 por defecto (no fija host), pero cualquier página web abierta en el mismo navegador podría llamar a las rutas por el CORS abierto (INFER sobre el código).
- Proyecto parado desde 2021-10-16.

## Límites, riesgos y dependencias
- Hardware: iPhone por cable + Mac con Xcode para construir WDA [README]; `tidevice` y WDA de terceros.
- Seguridad: inyección de comandos, sin autenticación, depuración activada, CORS abierto: no aceptable.
- Mantenimiento abandonado; GPL-3.0.

## Comparación con AURA
| Fuente@rev | Evidencia | Problema | Relevancia | Estado AURA (ruta) | Brecha | Riesgo/coste | Licencia | Decisión | Validación |
|---|---|---|---|---|---|---|---|---|---|
| iOS-remote@e4951f5 | [CÓDIGO] `app.py` sin auth, `shell=True`, CORS `*`; [README] depende de versión de WDA | Control de iPhone por USB desde navegador | Baja: sirve como contraejemplo | `tests/unit/test_entorno.py:70` (teléfono = dispositivo); `milestones/mapa-maestro/capacidades.json` (móvil nivel bajo); `core/politica_superficie.py:Superficie` | Sin capacidad iOS, y no debe haberla sin acta (D23) | Alto | GPL-3.0 | Descartar. Solo aporta los controles 2, 3, 7 y 12 de IE-007 (emparejamiento explícito, sin shell, autenticación, vetar versiones) | N/A |

## Decisión
Descartar. Valor únicamente como contraejemplo de lo que AURA no debe hacer (shell con entrada del usuario, servicio sin autenticación, CORS abierto) y como aviso de dependencia de versiones (WDA/iOS/Xcode).

## Validación mínima
Ninguna. Si algún día se estudia iOS, la prueba previa sería comprobar que el emparejamiento exige acción humana en el dispositivo (diálogo de confianza) y que la capacidad falla de forma explícita con versiones no soportadas.

## Licencia y precauciones
GPL-3.0. No copiar. No ejecutar `app.py` ni `tidevice`; contiene inyección de comandos y depuración activada.
