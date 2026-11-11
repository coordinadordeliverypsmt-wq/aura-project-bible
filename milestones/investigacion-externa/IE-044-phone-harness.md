---
id: IE-044
titulo: phone-harness/phone-harness — control multiplataforma de teléfonos para agentes
fuente: https://github.com/phone-harness/phone-harness
rama-revision: main @ 4bebff105af853215fb74c958c2c5e78bc275be2
fecha-revision: 2026-11-11
licencia: MIT
area: camaras-moviles
estado: investigado (README, SKILL, árbol, código focal y pruebas)
cobertura: README completo; SKILL.md; install.md; onboarding.md; setup Android/iOS/cloud; helpers.py; android.py; ios.py (lectura focal); remote.py; transport.py; telemetry.py; pyproject.toml; integración OpenClaw approval.ts, phone-exec.ts y classifier.py; pruebas backend contract, Android, iOS session y plugin. NO se leyó íntegramente todo el código restante, no se instaló, no se ejecutó y no se conectó un teléfono.
relacionadas: [IE-007, IE-008, IE-030, DP-DELEGACION-NODOS, ADR-0003, D24]
---

## Qué se examinó (rutas y símbolos)

- `README.md`, `SKILL.md`, `install.md`, `onboarding.md`, `setup/android.md`, `setup/ios.md`, `setup/cloud.md`.
- `src/phone_harness/helpers.py`: contrato de helpers multiplataforma, lectura de pantalla, OCR, accesibilidad, gestos, navegación, detección de interrupciones y sincronización.
- `src/phone_harness/android.py`: backend Android por ADB, selección de dispositivo, árbol UI y acciones.
- `src/phone_harness/ios.py`: backend de iPhone a través de la ventana de iPhone Mirroring en macOS.
- `src/phone_harness/remote.py` y `transport.py`: backend remoto HTTPS y abstracción de operaciones/capacidades.
- `src/phone_harness/telemetry.py`: telemetría local/cloud y opciones de exclusión.
- `integrations/openclaw/src/approval.ts`: compuerta de aprobación, propietario, scripts visibles completos, timeout y persistencia de aprobación por sesión.
- `integrations/openclaw/src/phone-exec.ts`: versión fijada, ejecución de scripts, entorno hijo con filtrado de credenciales, bloqueo de concurrencia, timeout, cancelación y limpieza de procesos.
- Pruebas focales: `tests/test_backend_contract.py`, `tests/test_android.py`, `tests/test_ios_session.py`, `tests/test_openclaw_plugin.py`.

Commit examinado: `4bebff105af853215fb74c958c2c5e78bc275be2`, último commit observado en `main) al revisar; firma GitHub verificada. Último cambio observado: corrección de inicialización de Apple Vision OCR y prueba macOS asociada.

## Patrones relevantes

- [README] Contrato común para teléfono personal iPhone, Android local, Android cloud e iPhone cloud. Los helpers intentan esconder las diferencias de cada backend.
- [CÓDIGO] `helpers.py` expone operaciones semánticas para leer, esperar y actuar: `screen`, `screenshot`, `find_text`, `tap_text`, `ui`, `tap_ui`, `tap`, `long_press`, `drag`, `scroll`, `swipe`, `open_app`, `home`, `back`, `wait_for_text`, `wait_for_app`, `wait_stable`.
- [README/CÓDIGO] Android usa ADB y el árbol de accesibilidad; iPhone personal usa captura de la ventana iPhone Mirroring, Vision OCR y eventos de entrada en macOS; iPhone cloud usa operaciones HTTPS. Son vías distintas, no un mecanismo universal de sistema operativo.
- [CÓDIGO] Abstracción de backend con operaciones soportadas y errores explícitos cuando una plataforma no puede realizar una operación.
- [SKILL] Método de ejecución: observar, ejecutar una acción, esperar una condición y verificar el cambio esperado; no interpretar que una llamada de tap o escritura equivale a éxito.
- [SKILL] Si una acción falla, aislar la acción, observar la pantalla y probar una hipótesis; no repetir en bloque una secuencia que pudo producir efectos parciales.
- [SKILL] El agente puede guardar helpers aprendidos en un workspace separado que no se sobreescribe durante actualizaciones.
- [CÓDIGO] La integración OpenClaw añade aprobación de propietario por script, muestra el script completo y no permite truncar un script demasiado largo para mostrarlo; timeout, cancelación, lock de teléfono y parada del proceso se implementan en el plugin.
- [CÓDIGO] La integración OpenClaw fija una versión del paquete Phone Harness (0.3.3 en el código leído), elimina del entorno hijo variables que parecen credenciales y serializa la ejecución concurrente del teléfono dentro del proceso.
- [CÓDIGO] Hay pruebas unitarias que simulan ADB y estados de sesión iPhone; el contrato común de backends se comprueba sin requerir un teléfono real.

## Límites, riesgos y dependencias

- [README] No es control literal de todas las funciones del móvil: no soporta multitáctil, cámara/Face ID flows y DRM video aparece negro; desbloqueo y PIN requieren intervención del usuario; OCR no detecta iconos por sí solo.
- [README] iPhone local requiere macOS 15+, iPhone Mirroring, iPhone con iOS 18+ y permisos Accessibility/Screen Recording de macOS.
- [README] Android local requiere ADB y USB debugging o Wireless debugging.
- [README] Las rutas cloud necesitan cuenta/servicio remoto; Android cloud usa ADB hacia el teléfono alojado, iPhone cloud usa HTTPS. No equivale a operación local-first.
- [CÓDIGO] La telemetría del proyecto es best-effort y opt-out, con opciones `DO_NOT_TRACK=1`, `PHONE_HARNESS_TELEMETRY=0` o configuración. La opción por defecto observada es habilitada salvo configuraciones específicas (por ejemplo la integración Hermes la deja opt-in); debe tratarse como dato sensible y verificarse en cada integración.
- [CÓDIGO] La integración de OpenClaw tiene un modo opcional de auto-ejecución basado en clasificador heurístico. El propio código indica que puede ser evadido; no adoptar esa vía como control de seguridad de AURA.
- [CÓDIGO] El helper `shell(cmd)` existe donde el backend lo soporta. No exponerlo como capacidad general a un modelo ni traducirlo a una capacidad AURA.
- [INFER] El script arbitrario como unidad de autorización ofrece una superficie mayor que una capacidad tipada por resultado; la integración OpenClaw mitiga con aprobación, pero AURA debe mantener su Motor Único, capacidades registradas y autorización granular.
- MIT permite estudiar/reutilizar código según términos de la licencia, pero no autoriza por sí solo su incorporación arquitectónica ni resuelve los requisitos de seguridad de AURA.

## Comparación con AURA

| AURA | Relación | Estado / brecha |
|---|---|---|
| IE-007 `android-remote-control-mcp` | Ya analiza controles Android, permisos, autenticación y exposición MCP | IE-044 aporta una abstracción multiplataforma y una skill diseñada para coding agents; actualiza la investigación móvil. |
| `core/politica_superficie.py` y `Superficie` | El teléfono debe seguir siendo un dispositivo/superficie; identidad del aparato no equivale a identidad de persona | No crear una nueva identidad de persona ni confiar en nombres visibles de dispositivo. |
| Motor Único / ALERTA-005 / ADR-0003 | Phone Harness opera acciones de UI y tiene una integración de aprobación para scripts | AURA debe traducir capacidades solicitadas a operaciones tipadas, registradas y autorizadas. Cada acción de lista roja requiere confirmación humana; no se hereda `allow always` como autorización global. |
| D24 / ADR-0001 local-first | El backend cloud depende de servicio externo | Priorizar Android local por ADB; evaluar iPhone Mirroring si el entorno de desarrollo es macOS. Cloud queda deshabilitado por defecto y exige decisión explícita. |
| DP-DELEGACION-NODOS | La ejecución móvil no es delegación de nodo | No mezclar los contratos del teléfono con NATS/DP-NODO-01. |
| IE-030 DeepCamera | Comparte la idea de helpers/contratos de operaciones entre backends | Reutilizar el principio de interfaz común, no persistir capturas ni introducir análisis biométrico. |

## Hallazgos

**HAL-044-1 · Contrato semántico multiplataforma para el teléfono.**
- Problema: automatizar móviles con comandos específicos de plataforma obliga al agente de programación a conocer muchos detalles de ADB, OCR y macOS.
- Mecanismo observado: una interfaz de helpers con backends específicos, detección de operaciones soportadas y error `Unsupported` cuando una acción no existe en la plataforma.
- Beneficio potencial: Claude Code puede aprender y probar un mismo vocabulario de tareas sobre Android e iPhone sin confundir las implementaciones.
- Límite: no todas las operaciones tienen paridad; la matriz de capacidades por backend debe formar parte del contrato.
- Criterio de validación futura: una prueba contractual con backends fake que demuestre que la misma capacidad semántica conserva resultado/error y que una operación no soportada falla explícitamente.
- Clase: PRIORIDAD ALTA como referencia técnica.

**HAL-044-2 · Bucle obligatorio observar → actuar → verificar.**
- Problema: los eventos de entrada táctil pueden no ejecutarse o ejecutarse en un estado distinto del esperado; una llamada sin excepción no prueba el resultado.
- Mecanismo: definir el cambio esperado antes de actuar, ejecutar una acción, esperar una condición observable y verificar una señal concreta en pantalla.
- Beneficio: reduce falsos positivos de automatización y repetición de operaciones con efectos externos.
- Criterio de validación futura: una prueba en dispositivo de ensayo con control positivo y una acción simulada como no-op; el sistema debe detectar que el resultado no cambió.
- Clase: PRIORIDAD ALTA como patrón.

**HAL-044-3 · Aprobación por llamada y script íntegro visible.**
- Problema: un agente puede ejecutar una secuencia arbitraria de UI y realizar operaciones sensibles.
- Mecanismo observado: plugin OpenClaw solicita aprobación del propietario, presenta el script completo, rechaza scripts que no caben completos en la descripción y tiene timeout/cancelación.
- Diferencia AURA: debe conservar autorización por capacidad/acción de lista roja, no convertir la aprobación de un script amplio en permiso general ni permitir auto-run heurístico.
- Criterio de validación futura: intento de ejecutar acciones sensibles sin aprobación, desde requester no propietario, con script truncado o tras expirar el permiso; todo debe denegarse.
- Clase: PRIORIDAD ALTA como patrón de defensa adicional, sujeto a evaluación.

**HAL-044-4 · Aislamiento del proceso de automatización y credenciales.**
- Problema: el script que controla el teléfono no debe heredar claves de proveedores y sesiones ajenas.
- Mecanismo observado: proceso hijo, entorno filtrado, límites de tiempo, lock de concurrencia y limpieza de procesos al cancelar.
- Diferencia AURA: la lista de variables eliminadas por regex no es garantía suficiente por sí sola; AURA debe preferir allowlist explícita de entorno, credenciales fuera del proceso ejecutor y límites del sandbox.
- Criterio de validación futura: pruebas con secretos plantados en entorno que demuestren que el proceso del dispositivo no los recibe ni los imprime; timeout y cancelación dejan cero procesos hijos.
- Clase: PRIORIDAD MEDIA.

**HAL-044-5 · El helper shell no equivale a una capacidad segura.**
- Problema: un único helper shell puede convertir el acceso al teléfono en ejecución arbitraria.
- Decisión: no exponer shell, ADB crudo ni comandos libres como herramientas del modelo AURA. Usar adaptadores internos acotados y operaciones declaradas en el catálogo del Motor Único.
- Clase: NO ADOPTAR como interfaz de agente.

## Decisión

**ADOPTAR COMO REFERENCIA TÉCNICA PRIORITARIA PARA LA FORMACIÓN DE CLAUDE CODE Y EL DISEÑO FUTURO DE UNA CAPACIDAD MÓVIL DE AURA. NO INSTALAR NI INTEGRAR AHORA.**

La primera plataforma objetivo de estudio/prototipo, cuando el roadmap y la autorización lo permitan, será Android local por ADB: portable a Linux/Windows/macOS y útil para desarrollar/pruebas automatizadas. iPhone Mirroring requiere macOS, por lo que su estudio de implementación y ejecución queda condicionado al hardware Mac disponible. No se adopta Phone Harness Cloud en la ruta local-first.

Esta ficha no abre un hito ni autoriza cambiar el contrato de `entorno`, introducir una app Android, habilitar accesibilidad, conceder permisos ADB, modificar teléfonos reales ni instalar extensiones permanentes en Claude Code.

## Validación mínima

Cuando exista un Decision Package aprobado:
1. Mapa de capacidades Android/iOS y matriz explícita de diferencias.
2. Backend fake y pruebas de contrato.
3. Prueba Android en dispositivo de laboratorio expresamente autorizado, comenzando solo por lectura de modelo/versión/pantalla.
4. Pruebas negativas de bloqueo, propietario, credenciales, timeouts y no-op.
5. Operaciones de lista roja con confirmación por llamada.
6. Verificación de que no hay captura, texto, notificación, portapapeles, PIN ni credencial persistidos en logs/memoria.
7. Quality Gate y auditoría independiente.

## Licencia y precauciones

MIT. Código externo no fue instalado ni ejecutado. Los hallazgos de la skill y README se clasifican como [README]; los detalles de los archivos fuente leídos, como [CÓDIGO]. La revisión no es una auditoría integral ni prueba de seguridad independiente.
