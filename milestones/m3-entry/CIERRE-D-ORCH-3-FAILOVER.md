# Cierre · `D-ORCH-3` — catálogo `AUTO` + failover gobernado **Claude → OpenCode**

**2026-08-26** · rama `worktree-m3-entry` · **0 commits · 0 push**

## 1 · El catálogo `AUTO` — derivado, no inventado

`DP §10.2` fija el origen: **lista verde de ADR-0003**. El catálogo verde ya está aprobado en
`permissions.py`, así que se **filtra**, no se inventa. El filtro es el **efecto declarado**: solo
entran las verdes de efecto `lectura` del plano de desarrollo. Las verdes de efecto `interno` o
`reversible` (`automatizacion`, `encender_dispositivo`) son del **producto**, no del trabajo sobre él.

| Acción | Origen |
|---|---|
| `ejecutar_pruebas` | `permissions.py:47` verde/lectura + `DP §10.2` |
| `verificar_calidad` | `permissions.py:48` verde/lectura |
| `auditar_garantias` | `permissions.py:49` verde/lectura |
| `diagnosticar_estado` | `permissions.py:50` verde/lectura |

**Ninguna modifica nada** (`limites_de_modificacion = "ninguna"`). Cada entrada declara los once
campos exigidos. `REVIEW` sigue vacío: ese nivel **no existe** hasta `D-ORCH-2`.

## 2 · El failover NO es «si Claude falla, usa OpenCode»

| Clase | ¿Releva? | Por qué |
|---|---|---|
| `AGENTE_SIN_CUOTA` · `AGENTE_NO_DISPONIBLE` | **sí** | el agente no puede |
| `TAREA_FALLIDA` · `SIN_EFECTO` · `RESULTADO_INVALIDO` | **no** | relevar **oculta el fallo** rotando agentes |
| `TIMEOUT` | **no** | no distingue agente colgado de tarea infinita; ante la duda, no se gasta otro agente |

Cadena **finita y cerrada**: `claude → opencode → fin`. Codex excluido por decisión del CEO; Ollama
no participa. Los **nueve campos** de trazabilidad se registran en **todos** los intentos, no solo en
el que sale bien: si solo constara el último, el relevo sería invisible.

## 3 · El punto crítico — AURA no cree al agente

El agente **afirma**; AURA **verifica el efecto**. Una prueba recorre afirmaciones contradictorias
(«he fallado», «ERROR CATASTRÓFICO») sobre un efecto real y todas dan `VERIFIED`: **el texto no
participa en el veredicto**. Y al revés, un proceso que imprime «informe generado correctamente» sin
crear nada da `NO_VERIFICADO` y la tarea queda `FAILED`.

Una evidencia que no se sabe comprobar da `NO_VERIFICABLE`, nunca `VERIFIED`.

## 4 · E2E reales

**Failover con OpenCode real** — instalado bajo demanda, ejecutado, retirado:

```
1 INSTALAR opencode      exit=0
2 VERIFICAR presencia    /home/.../bin/opencode
3 EJECUTAR (real)        timeout
4 RETIRAR                exit=0
5 LIMPIAR residuos       ok
6 VERIFICAR AUSENCIA     opencode ausente
7 SIN RESIDUOS           ninguno
#1 claude   class=AGENTE_SIN_CUOTA  verified=False fallback=False dur=0.003s
#2 opencode class=TIMEOUT           verified=False fallback=True  dur=327.35s
resultado: NO_VERIFICADO · TASK: FAILED · log íntegro: True
```

**El sistema no fingió éxito**, que es lo que se estaba probando. El ciclo completo del agente
externo operó y la ausencia quedó verificada.

**Continuidad con relevo, en verde:**

```
cola: 3 AUTO + 1 HUMAN
RESULTADO: {'intentadas': 3, 'completadas': 3, 'fallback_usado': True, 'motivo': 'cola AUTO agotada'}
  AUTO-1  COMPLETED  efecto_real=True     AUTO-2  COMPLETED  efecto_real=True
  AUTO-3  COMPLETED  efecto_real=True     HUMANA-1  WAITING_FOR_NEXT_TASK  (intacta)
  6 intentos registrados (2 por tarea) · log íntegro: True
```

## 5 · BLOQUEO REAL — OpenCode no puede razonar sin violar D24

Medido `[EJEC]`, `opencode-ai@1.18.22`:

> **«Google Generative AI API key is missing.»**

El agente secundario **exige una clave de proveedor para razonar**, y **D24 prohíbe claves de
terceros**. No es un fallo del mecanismo de failover —que funciona y está probado—: es que el
ejecutor LLM externo no puede operar sin violar una decisión que no se toca. Queda fijado en
`agentes.BLOQUEO_CONOCIDO` para que nadie lo redescubra ni lo dé por resuelto sin acta.

**Lo que sí quedó probado de OpenCode:** instalación bajo demanda, verificación, retirada, limpieza y
**ausencia comprobada**. Lo que no: ejecutar trabajo LLM.

## 6 · Verificación

| | |
|---|---|
| Control Plane | **308 passed** (D-ORCH-3: 29 nuevas) |
| Communication Plane · agente-externo | **180/5 skipped** · **20** — sin cambios |
| `ruff` | PASS |
| **Mutación** | **F1 35 · F2-F3 18 · D-ORCH-3 19 = 72 mutantes, 0 supervivientes, 0 NO_APLICADO** |
| Quality Gate | **FAIL 5/1139/3** — baseline, sin relación con este bloque |
| `estado.json` real | **INTACTO** tras la batería completa **y** el Quality Gate `[EJEC]` |
| OpenCode · Codex · residuos · procesos · claves nuevas | **ausentes · 0 · 0 · 0** |
| D24 · Bible · ADR · roadmap | **0 cambios** |

## 7 · Qué puede ejecutar AURA automáticamente desde ahora

Las cuatro acciones `AUTO`, sobre tareas **ya registradas**, con relevo automático si el agente
principal se queda sin cuota, verificación externa del efecto y cierre solo con evidencia.
`continuidad()` encadena la cola sin intervención, **no inventa tareas**, es finita, y **se detiene
dejando el motivo escrito** si ningún agente puede seguir — vaciar la cola marcando `FAILED` cuando
el problema es el agente destruiría trabajo pendiente por un motivo ajeno a él.

**Lo que falta para que sea útil de verdad:** un ejecutor que pueda razonar. Claude Code lo es y está
instalado; OpenCode está bloqueado por D24.
