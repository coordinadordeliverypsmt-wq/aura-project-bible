---
id: IE-009
titulo: OpenJarvis — primitivas de agentes locales, evaluación con coste como restricción, trazas
fuente: https://github.com/open-jarvis/OpenJarvis
rama-revision: main @ 2026-10-22 (commit no visible en la página; 1.291 commits declarados)
fecha-revision: 2026-10-22
licencia: Apache-2.0
area: asistentes
estado: investigado
cobertura: README de la página del repo (WebFetch) y README raw. NO se leyó código de src/openjarvis, ni docs/, ni tests/, ni el formato de trazas, ni el módulo de bench. Los mecanismos de medición de energía/FLOPs NO están documentados en lo leído.
relacionadas: [IE-010, IE-011, IE-000]
---
## Qué se examinó (rutas y símbolos)
- README del repo: lista de directorios (`src/openjarvis`, `configs/openjarvis`, `rust`, `frontend`, `desktop/src-tauri`, `docs`, `tests`), comandos `jarvis bench skills` y `jarvis optimize skills --policy dspy`.
- No se examinó código fuente.

## Patrones relevantes
- [README] Ocho agentes en tres modos (bajo demanda: `simple`, `orchestrator`, `native_react`, `native_openhands`, `deep_research`; programado: `morning_digest`; continuo: `operative`, `monitor_operative`).
- [README] «Skills» expuestas como herramientas descubribles desde un catálogo (estándar agentskills.io).
- [README] Evaluación que trata «energía, FLOPs, latencia y coste en dólares» como restricciones de primera clase junto a la precisión; `jarvis bench skills` con `--max-samples` y `--seeds`.
- [README] Bucle de aprendizaje a partir de trazas locales (`optimize --policy dspy`).
- [README] Local por defecto (instala Ollama + modelo inicial), nube solo si hace falta.
- [INFER] El valor aprovechable para AURA no es el framework sino la idea: medir cada turno con un registro uniforme (latencia, tokens, coste/energía estimada) y comparar contra una línea base con semillas fijas.
- [README] No documenta CPU-only, tamaño del modelo inicial ni formato de trazas: no se puede afirmar nada de ello.

## Límites, riesgos y dependencias
- Requiere Python >=3.10, Node 22+ para GUI, extensión Rust, Ollama; instalador que descarga modelos. [README]
- Sin requisitos de hardware publicados; presumiblemente inviable en NODO-01 (32 bits, 1 GB) [INFER].
- Proyecto activo (11,8k estrellas, 21 PR abiertas; solo como señal de actividad, no de calidad). Un «optimizador de skills» que se autoedita choca con INV-9/regla de capacidades registradas si se adoptara tal cual [INFER].

## Comparación con AURA
- Medición actual: `walking-skeleton/herramientas/benchmark_llm_ollama.py` (usa `time.perf_counter`, vuelca JSON `total_s` por modelo) y `milestones/m3-entry/BENCHMARK-COGNICION-LOCAL.md`, `evidencia-latencia-voz/RESULTADO-LATENCIA-Y-MODELO.md` (~110 s/turno cognitivo en HC-1; STT ≈ 5,5 s).
- Trazas/auditoría: `aura_skeleton/core/automatizacion.py` `MotorAutomatizacion.ejecutar` (L98) ya escribe `obs.log(..., audit=True)` con `trace_id` por acción.
- Brecha real: la medición es puntual por script; no hay un registro de latencia por etapa del turno (superficie determinista / STT / LLM / ejecución) reutilizable en cada nodo, ni comparación sistemática entre nodos. [INFER, sin ejecutar]
- Cómo medir AURA en NODO-01 (Atom N450, 1 núcleo, 1 GB, 32 bits) y HC-1 (x86_64, 2 núcleos, 3,7 GB) sin modelos grandes ni compras: [PROPUESTA] (a) medir SOLO el camino determinista y los componentes pequeños (STT, TTS, bus, Motor Único) con `perf_counter` por etapa y `trace_id`; (b) en NODO-01 registrar RSS pico y swap (`/proc/self/status`), no energía (sin vatímetro, declarar «no medido»); (c) reutilizar los 110 s de HC-1 como techo medido, no extrapolar a NODO-01 (regla CEO 2026-08-04: no publicar valores no derivables); (d) estadística con N repeticiones y mediana/p95, no media de una pasada.

## Decisión
- Adaptar el patrón de medición por etapa (no el framework). Investigar más solo si se necesita su formato de traza; descartar adopción de código, optimizador de skills y agentes autónomos.

## Validación mínima
- Prueba: RED que, con adaptadores simulados, exige que un turno completo emita un registro por etapa con `trace_id` común y duración >= 0, sumando <= total del turno; mutante: omitir la etapa del Motor debe hacer fallar la prueba. Ejecución real: mismo script en HC-1, comparando contra los 110 s ya medidos (debe coincidir en orden de magnitud).

## Licencia y precauciones
- Apache-2.0 (compatible). No instalar; no enrutar nada a su nube. Afirmaciones de leaderboard o «88,7 %» son de terceros y no verificadas.
