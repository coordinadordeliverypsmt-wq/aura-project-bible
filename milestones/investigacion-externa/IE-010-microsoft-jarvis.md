---
id: IE-010
titulo: microsoft/JARVIS (HuggingGPT, EasyTool, TaskWeaver) — planificación LLM, selección de modelos y dependencias entre tareas
fuente: https://github.com/microsoft/JARVIS
rama-revision: main @ 2026-10-22 (commit no visible; 112 commits declarados; última novedad datada en README: 2024-01-15)
fecha-revision: 2026-10-22
licencia: MIT
area: asistentes
estado: investigado
cobertura: README del repo y el fichero hugginggpt/server/awesome_chat.py (leído vía resumen de WebFetch, no línea a línea). NO se leyeron easytool/, taskbench ni TaskWeaver (el README leído no lo menciona; puede vivir en otro repo), ni los prompts completos, ni los modelos.
relacionadas: [IE-009, IE-011]
---
## Qué se examinó (rutas y símbolos)
- `hugginggpt/server/awesome_chat.py`: `parse_task`, `fix_dep`, `unfold`, `chat_huggingface` (bucle de planificación), `run_task`, `get_avaliable_models`, `record_case`, `send_request`.
- README: etapas y servicios externos.

## Patrones relevantes
- [README] Cuatro etapas: planificación de tareas -> selección de modelo -> ejecución -> generación de respuesta; el LLM es «controlador».
- [CÓDIGO] Plan como lista JSON de tareas con campo `dep` (ids previos, -1 = ninguna) y argumentos con marcadores `<GENERATED>-N` que se sustituyen por salidas previas.
- [CÓDIGO] `fix_dep` deriva `dep` de los marcadores; un `dep` >= id propio se reinicia a `[-1]` (guarda contra ciclos/referencias adelantadas, pero silenciosamente cambia el plan).
- [CÓDIGO] Ejecución: un hilo por tarea cuando sus dependencias están en el dict de resultados; bucle con `sleep(0.5)` y contador `retry` que nunca se reinicia (abandona tras ~80 s de inactividad).
- [CÓDIGO] Si el JSON del plan no parsea o es `[]`, cae a `chitchat`; tareas únicas de resumen/traducción/generación van directas a chitchat.
- [CÓDIGO] Selección de modelo: hasta 10 candidatos; si hay uno se elige; si hay varios, decide el LLM, y si responde JSON inválido se recupera con `find_json`/`get_id_reason`.
- [CÓDIGO] Fallos: `run_task` devuelve `False`, el error se guarda como resultado, se registra en `logs/log_fail.jsonl`; NO hay reintento de tarea fallida.
- [INFER, de lo leído] Defectos de orquestación observables: `tasks.remove(task)` mientras se itera (puede saltar tareas); el plan se reescribe tras generarse (`fix_dep`, `unfold`, reseteo de `dep`), es decir se «reinterpreta» en varios puntos.
- [README] EasyTool: instrucciones de herramienta concisas; código en `easytool/` (no leído).

## Límites, riesgos y dependencias
- Depende de OpenAI/Azure, token y endpoints de Hugging Face (modo `huggingface`/`hybrid`) y de servidor local de modelos pesados. [README/CÓDIGO]. Incompatible con D24 (sin claves de terceros) en su configuración principal.
- Mantenimiento: investigación original de 2023; el propio README anunció «reconstruir el proyecto» (2023-07-28) y lo último datado es 2024-01 [README]; 4,2k issues abiertas. Tratar como referencia académica, no como base viva. Parte de ello depende de servicios externos que pueden haber cambiado [INFER].
- Seguridad: el LLM decide qué modelo/endpoint invocar y rellena argumentos libres (incluye rutas locales con prefijo `public/`); sería el vector que AURA excluye.

## Comparación con AURA
- Motor Único: `aura_skeleton/core/automatizacion.py` `MotorAutomatizacion.ejecutar` (L98): «registro -> dry-run -> permisos -> adaptador -> auditoría», con auditoría también de intentos denegados (L174) y errores (L179). Planificación determinista: `core/planificacion.py`; superficies deterministas antes del modelo: `core/orchestrator.py` (ADR-0014, INV-7).
- Ya cubierto: dependencias explícitas, trazabilidad, fallo registrado, y permisos/dry-run que JARVIS no tiene.
- Contrastes útiles (cuestionario de contrato, [PROPUESTA]): (1) ¿qué hace el Motor ante dependencia a una acción que falló? JARVIS guarda el error y sigue; (2) ¿puede un plan referenciar una salida inexistente o adelantada? JARVIS lo silencia a `-1`; AURA debería rechazarlo explícitamente (no reescribir, INV-7); (3) ¿hay límite de espera por acción y está distinguido de «sin progreso»? JARVIS usa un contador global ambiguo; (4) ¿el marcador de salida previa pasa por permisos con su valor ya resuelto (`simular` sobre argumentos reales)?
- No verificado en AURA (no se leyó el plan multi-paso): se recomienda que el auditor lea `planificacion.py` con esas cuatro preguntas.

## Decisión
- Descartar adopción de código. Adaptar solo como lista de verificación de contrato (casos de fallo en dependencias). Selección de modelo por LLM: descartar (el Capability Manager es puro, INV-1).

## Validación mínima
- Pruebas RED sobre el Motor/planificador con adaptadores simulados: (a) plan con dependencia a acción fallida -> la dependiente NO se ejecuta y queda auditada; (b) referencia adelantada o a id inexistente -> rechazo explícito sin ejecutar nada. Mutante: ignorar el fallo previo debe dar prueba roja.

## Licencia y precauciones
- MIT. No clonar ni ejecutar; modelos HF con licencias propias, no evaluadas.
