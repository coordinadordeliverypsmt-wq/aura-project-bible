---
documento: "Decision Package — Cognición Local + Rendimiento del Razonador"
tipo: "Decision Package (perímetro de la siguiente inversión)"
estado: "perímetro APROBADO (CEO, 2026-09-09). Construcción NO iniciada."
fecha: 2026-09-09
mantenido-por: "APUS-5 (CTO)"
decide: "CEO (Mauricio) — acta: decisiones/2026-09-09-acta-cuatro-decisiones-ceo.md §D-3 y §D-4"
checkpoint: "3708e11d38ab9a4bbcbfb814fbc1c1ccbb293b8b"
---

# Cognición Local + Rendimiento del Razonador

**Este documento NO es la inversión: es su perímetro.** Existe para que la misión que la ejecute pueda
empezar sin volver a descubrir la arquitectura. **No se ha construido nada de lo que aquí se describe.**

**Clasificación de evidencia** (D47): `[EJEC]` medido ejecutando · `[INFER]` deducido · `[HIPO]` no verificado.

---

## 1 · Objetivo medible

Que AURA sostenga **conversación, conocimiento general, razonamiento e hipótesis** con el razonador
**local**, en `HC-1`, **sin que el LLM adquiera autoridad** sobre memoria personal, permisos, acciones,
reglas, señales, hechos del usuario ni gobernanza.

Medible significa esto y no una sensación:

> **Reducir la latencia de un turno cognitivo en `HC-1` sin perder ninguna de las garantías vigentes.**

El objetivo **no** es «que AURA razone mejor»: es que el tiempo del turno baje de forma medida mientras
`24/24`, `G-1` y los invariantes siguen en verde. Si la latencia baja y una garantía cae, la inversión
ha fracasado.

## 2 · Baseline actual `[EJEC]`

**Medido en `HC-1` y registrado en el repositorio** (`DP-COMPARACION-RAZONADORES.md` §7):

| | `qwen2.5:0.5b` (el de producción) |
|---|---|
| Ingesta de prompt | **3,52 – 3,83 tok/s** en reposo · **≈1,9 tok/s con carga** |
| Generación | **1,85 – 2,23 tok/s** |
| Turno de 727 tokens | **231 – 253 s** |

**Medido durante la sesión del 2026-09-09 y registrado aquí por primera vez** —no estaba en ningún
artefacto del repositorio, vivía solo en informes de sesión, y eso es precisamente lo que este DP viene
a corregir:

| Hecho | Cifra |
|---|---|
| Turno cognitivo **antes** de separar los prompts | **441,2 s** `[EJEC]` |
| Turno cognitivo **después** de separarlos | **237,0 s** `[EJEC]` |
| Tokens de ingesta: antes → después | **630 → 166** `[EJEC]` |
| Atribución del coste | **≈71 % del tiempo era ingestión del catálogo de 36 acciones** `[EJEC]` |
| Clasificador LLM como juez de intención | **8/12 aciertos**, 10–58 s por llamada `[EJEC]` — descartado |

> **El cuello de botella medido es la INGESTIÓN DE PROMPT, no la generación.** Por eso la primera
> palanca de esta inversión es *qué entra en el prompt*, y no *qué modelo lo procesa*. La mejora de
> 441,2 s → 237,0 s se obtuvo **sin tocar el modelo**: solo dejando de enviar el catálogo de acciones
> cuando el turno no pide ninguna acción.

**Lo que ya está construido y NO hay que rehacer:**

- `_SYSTEM_COGNITIVO` reducido, separado del prompt de acción;
- `providers_real.infer(prompt, modo="accion"|"cognitivo")`;
- `router.route(prompt, trace_id, modo)`;
- `orchestrator`: `modo = "accion" if _pide_accion(text) else "cognitivo"`;
- `24/24` de protección anti-fabricación sobre `tests/datos/bateria_memoria.json`;
- M-1: clasificación de intención de dos ejes (`core/intencion.py`, `DP-D-M-7` Opción A);
- histórico no recuperable (`contracts.HISTORICO`);
- Core como única autoridad sobre memoria personal (`ADR-0014`).

## 3 · Métricas

Toda medición **en `HC-1`**, en serie y sin nada más corriendo —el arnés de mutación ya enseñó lo que
cuesta medir en paralelo—:

1. **Latencia total del turno cognitivo** (s) — la métrica principal.
2. **Tokens de ingesta por turno** y **tok/s de ingesta**.
3. **Tokens generados** y **tok/s de generación**.
4. **Reparto ingesta / generación** en % del turno. Es lo que dice dónde atacar.
5. **Latencia del turno de acción**, para que la mejora cognitiva no se pague con la de acción.
6. **Huella de memoria** durante la inferencia: en 3,6 GiB, un swap imprevisto falsea cualquier cifra.
7. **Garantías**: `24/24`, `G-1` (`R-A`/`R-B`), garantías vigentes, supervivientes de mutación.

**Regla de evidencia:** una cifra no medida en `HC-1` **no cuenta**. Y ninguna comparación vale sin su
línea base tomada en la misma sesión: este hardware varía con la carga (3,83 → 1,9 tok/s medido).

## 4 · Pruebas que deben permanecer verdes

```
tests/unit/test_frontera_cognitiva.py          ← 24/24 anti-fabricación
tests/unit/test_m1_clasificacion_intencion.py  ← los dos ejes de M-1
tests/unit/test_historico_no_recuperable.py    ← memoria recuperable vs histórico
tests/unit/test_parada_escritura_pasiva.py     ← ADR-0024
tests/unit/test_grounding_core.py              ← el proveedor registra CERO llamadas
tests/unit/test_g1_ruta_unica.py               ← R-A 0 · R-B 0  (salvo R-B, ver §8)
tests/integration/test_hechos_declarados.py    ← candados A y B
tests/integration/test_bateria_memoria.py
tests/integration/test_correcciones_producto.py
tests/e2e/test_capacidad_m1.py
entorno/control-plane/  (suite completa)
```

Más: **ruff PASS** en ambos planos y **0 supervivientes** en los catálogos de mutación afectados.

## 5 · Invariantes

La separación **no cambia**, y es la razón de ser de la inversión:

```
CORE   = autoridad sobre hechos y memoria personal     ADR-0014
LLM    = razonador y conversador, SIN autoridad
MOTOR  = único ejecutor autorizado                     ALERTA-005
PARADA = mecanismo de seguridad, fuera de banda        Bible 5.3 §5 · ADR-0024
```

Y además: `_INTOCABLES` · `_MATERIA_RESERVADA` · `TODO_LO_DELEGABLE` · `REVIEW_HABILITADO = False` ·
HITL en lista roja (`ADR-0003`) · local-first sin claves de terceros (`D24` / `ADR-0001`) ·
`InProcessEventBus` sin sustituir por NATS · `main` intacta.

## 6 · Límites de autoridad

**El LLM no decide nada.** No decide qué memoria personal existe, ni qué se almacena, ni qué se ejecuta,
ni qué permisos hay, ni clasifica intención para activar una garantía (`ADR-0014` §2). Puede razonar,
conversar, responder conocimiento general y formular hipótesis. **Nada más.**

Ya está medido lo que ocurre si se le da el papel de juez: **8/12**, y los dos fallos peligrosos fueron
exactamente dos de los casos que el determinismo no cubre. No es una opinión: está en §2.

## 7 · Criterios de entrada

1. `HEAD` en el checkpoint publicado y `main` intacta.
2. `preflight-check.sh` en **ESTADO: APTO** — saltárselo ya produjo una conclusión falsa (`CHECKLIST` §4.1).
3. Baseline de latencia **tomado en la misma sesión**, no heredado de este documento.
4. `PARADA` **ARMADA** salvo ventana de ejecución explícitamente autorizada.
5. Las pruebas del §4 en verde antes de tocar nada.

## 8 · Criterios de salida

1. **Latencia del turno cognitivo reducida de forma medida en `HC-1`**, con antes y después de la misma sesión.
2. **`24/24` intacto.** No se acepta una regresión de la garantía anti-fabricación a cambio de velocidad.
3. **`G-1`: `R-A = 0`.** `R-B` debe seguir en `0` **o** cualquier escritura nueva debe quedar declarada
   con motivo y fecha, por operación, nunca por módulo.
4. **Garantías vigentes ≥ 970 de 983.** Las **13 deudas ajenas** están documentadas y quedan fuera de
   alcance; lo que no se admite es añadir una nueva.
5. **0 supervivientes** de mutación en lo tocado.
6. **ruff PASS** · **control-plane sin regresiones** (966 passed al cierre de esta misión).
7. **Ninguna ampliación de autoridad**, ningún permiso nuevo, ninguna capacidad nueva.
8. Comportamiento **demostrado ejecutando**, no descrito. El proyecto ha pagado ocho veces el patrón
   «declarado ≠ real».

## 9 · Qué está permitido tocar

- `walking-skeleton/aura_skeleton/modules/providers_real.py` — ingestión, prompt, parámetros de inferencia.
- `walking-skeleton/aura_skeleton/modules/router.py` — enrutado por modo.
- `walking-skeleton/aura_skeleton/core/orchestrator.py` — **solo** la construcción del prompt y la
  selección de modo. **No** la cascada de superficies, **no** la puerta de `ADR-0014`, **no** la guarda
  de `PARADA`.
- Pruebas y catálogos de mutación **propios de la inversión**.
- `milestones/m3-entry/` — mediciones y registro de evidencia.

## 10 · Qué permanece INTOCABLE

- `core/intencion.py` — la clasificación de M-1 y su whitelist del eje 2.
- `_es_consulta_de_memoria` y `es_interrogativa` — sostienen el `24/24`.
- `contracts.py` — `MemoryStore`, `HISTORICO`, `KINDS_PASIVOS`, `es_recuperable`, `es_escritura_pasiva`.
- `core/permissions.py` · `core/automatizacion.py` (motor) · `core/kill_switch.py`.
- `orquestador.py` · `politica-orquestador.toml` · `control_plane.py` · `conftest.py` (`_INTOCABLES`).
- `architecture_manifest.toml` — salvo una declaración nueva con motivo y fecha, por operación.
- Bible · ADR · `CLAUDE.md` · roadmap · `decisiones/`.
- El modelo: **`qwen2.5:0.5b` no se cambia ni se agranda** sin decisión posterior específica.
- **Ninguna API externa, ninguna credencial, ningún servicio cloud.**

---

## Palancas candidatas — **hipótesis, no plan** `[HIPO]`

Se anotan para que la misión no empiece en blanco. **Ninguna está aprobada ni medida**, y la que se
elija debe medirse antes y después:

1. **Reducir más la ingesta.** Es donde está el 71 % del coste medido. El catálogo ya no viaja en modo
   cognitivo; queda por ver qué más viaja y no hace falta —contexto de memoria, buffer de diálogo—.
2. **Reutilización de contexto entre turnos** (`keep_alive`, caché de prompt de Ollama), si existe y es
   local.
3. **Parámetros de inferencia**: ventana de contexto, `num_predict`, hilos. Todo local, sin cambiar modelo.
4. **Recortar la respuesta pedida**: menos tokens generados es menos tiempo, a 1,85–2,23 tok/s.
5. **Responder sin modelo cuando el Core puede**: es lo que ya hacen la aritmética y las nueve
   superficies deterministas. La palanca más barata es la llamada que no se hace.

**No se recomienda ninguna todavía.** Elegir exige medir primero, y medir es la primera fase de la
inversión, no un paso previo a saltarse.
