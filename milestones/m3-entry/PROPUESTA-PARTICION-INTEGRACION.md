---
documento: "Propuesta de partición de commits para integrar worktree-m3-entry"
fecha: 2026-10-26
estado: "REVISIÓN 2 (2026-10-26, §8): la partición de §3 queda SUPERADA por la verificada en §8. NO ejecutada: ningún git add, commit, push ni merge. Requiere confirmación del CEO"
evidencia: "evidencia-cm2-s3-2026-10-25/reanudacion-tras-caida/inventario-integracion.txt (git status -uall, clasificado por zona)"
---

# Partición de commits para integrar el worktree

## 1. Estado medido `[EJEC]`

| Dato | Valor |
|---|---|
| Rama | `worktree-m3-entry` |
| HEAD | `6dad6af` |
| main y origin/main | `d933a08` |
| Staging | solo el rename preexistente `walking-skeleton/mutaciones/arnes-validador-comandos.toml → retiradas/`. **Superado por la §8.3:** se des-stagea antes del commit 1 y se rehace en el commit 3 con sus **dos** lados |
| Entradas | `git status` resumido: 413. Con `-uall`: 1831 |

**Las 1831 entradas, por zona:**

| Zona | Entradas | Qué contiene | Qué se hace |
|---|---|---|---|
| Z0 artefactos | 1187 | `graphify-out/`, `__pycache__/`, `kernel.errors.txt`, `.githooks/omisiones.log` | **Excluir** |
| Z0 datos vivos | 2 | `entorno/control-plane/eventos.jsonl` y `estado.json` | **Excluir siempre** |
| Z1 código usado por procesos vivos | 3 | `core/reloj_cm2.py` (lo usa CM2); `adapters/receptor_nodos.py` y `core/nodos.py` (los usa el servicio receptor) | Primero |
| Z2 código funcional y herramientas | 87 | Sobre todo `aura_skeleton/core` y `adapters` | Commits 2 a 4 |
| Z3 pruebas | 159 | 75 unitarias, 46 de integración, 3 e2e | Con su código |
| Z4 mutaciones | 103 | Baterías del arnés | Con su código |
| Z5 documentación y gobierno | 103 | DP, mapa maestro, `capacidades.json`, resultados | Commit 7 |
| Z6 evidencias y logs | 187 | Directorios `evidencia-*` | Commit 6 |

## 2. Reglas de la partición

- **No usar `git add -A`.** Arrastraría los registros reales de producción (`eventos.jsonl` y `estado.json`) y 1187
  artefactos. El protocolo de `CLAUDE.md` §3 usa `git add -A`, y en este árbol **no sirve**. Hay que hacer `git add` por
  rutas explícitas, sacadas del inventario.
- **Cada commit pasa el QG por sí mismo.** El código va siempre con sus pruebas y sus mutaciones. Nunca código sin su
  red.
- **Antes de cada commit:**
  - `git diff --cached --name-only | grep -E 'eventos.jsonl|estado.json|__pycache__|graphify-out'` tiene que salir
    **vacío**;
  - comprobar que no hay secretos.
- **Mensajes:** conventional commits, con los trailers de `CLAUDE.md` §3.

## 3. Partición propuesta

Cada commit es una unidad que se puede revisar y revertir.

| # | Commit | Contenido | Depende de |
|---|---|---|---|
| 1 | `feat(cm2,nodos): código que ya ejecutan los procesos vivos` | Z1, más las pruebas y mutaciones que los cubren (`test_reloj_cm2*`, `test_receptor_nodos*`, `test_nodos*`, `cm2-cableado-produccion.toml`) | — |
| 2 | `fix(red): _ruta_red v2 y aislamiento de pruebas de dispositivos reales` | `__main__.py`, `tests/conftest.py`, `test_ruta_red.py`, `test_sin_dispositivos_reales.py`, `ruta-red.toml`, `sin-dispositivos-reales.toml` | 1 |
| 3 | `feat(arnes): mutación en copia aislada (regla 6)` | `herramientas/mutar.py`, `test_arnes_*`, `arnes-*.toml`, `retiradas/` y el rename ya preparado | — |
| 4 | `feat(control-plane): candidato aislado, confinamiento estricto y resto del plano` | Los ficheros modificados de `entorno/control-plane/` **salvo** los registros y salvo los de la recuperación tras caídas, con sus pruebas y mutaciones | 3 |
| 5 | `feat(control-plane): recuperación tras caídas (DP-RECUPERACION-TRAS-CAIDAS)` | Los 7 ficheros del diff final (§4) | 4 |
| 6 | `docs(evidencia): evidencias de CM1, CM2/S3, voz, nodos y cognición local` | Z6 | — |
| 7 | `docs: DP, mapa maestro, capacidades, checkpoint y checklist` | Z5 | 1 a 6 |

**El resto de Z2 y Z3**, es decir los módulos de voz, cognición local y memoria declarativa, entra en commits por tema
**antes del 5**. Cada uno lleva su prueba y su mutación. El inventario permite asignarlos fichero a fichero; la
asignación exacta se hace al ejecutar, revisando cada `git diff --cached`.

## 4. La recuperación tras caídas (commit 5)

Ya está **aplicado** al worktree (11:52) y el QG pasa (3842, EXIT=0). El diff final lo ha validado la revisión independiente. Toca:

- `planificador.py`
- `control_plane.py`
- `motor_autonomia.py`
- `aura.py`
- `.gitignore`
- `test_red_reanudacion_tras_caida.py` (nuevo)
- `mutaciones/reanudacion-tras-caida.toml` (nuevo)

Entran también en el commit 5 los **2 toml del ajuste de garantías** (`walking-skeleton/mutaciones/motor-autonomia.toml` y `f1-orquestador.toml`). Después, en el árbol vivo, hay que ejecutar la suite del control-plane, que
**incluye los 2 tests de `test_red_capacidad_completada`**: solo pasan en la ruta real.

## 5. Rama de destino recomendada

- **Recomendación:** commits en `worktree-m3-entry`, después `git -C <main> merge --no-ff worktree-m3-entry`, QG en main
  dentro de un subshell y push. Es el flujo de `CLAUDE.md` §3, **cambiando `git add -A` por rutas explícitas**.
- **Alternativa:** abrir una PR desde una rama de revisión (`revision/m3-entry-2026-10-26`) en lugar de hacer merge
  directo.

**Decisión pendiente del CEO:** elegir rama y modo, y confirmar la partición.

## 6. Riesgos de la integración

- **Los procesos vivos usan este worktree:**
  - el cron de CM2, por `WS=`;
  - el despertador;
  - el receptor, por su `WorkingDirectory`.

  Un commit **no** cambia los ficheros del árbol, así que no les afecta. En cambio, `git merge --ff-only main` hecho
  desde el worktree sí podría hacerlo si main trae cambios distintos. Hay que comprobar con `git diff HEAD main` que
  el realineado no toca código en ejecución.
- **Aplicar la recuperación cambia código que ejecuta el despertador** (`motor_autonomia`, `planificador`) en el
  próximo despertar del cron. **Con PARADA armada el motor no llega a ejecutarlo**, porque el despertador para antes.
  Desarmar PARADA es una decisión aparte.

## 8. Revisión 2: partición VERIFICADA (2026-10-26, decisión del CEO «preparar, no ejecutar»)

**Una verificación reproducible refuta la §3** `[EJEC]`. Artefactos: `evidencia-cm2-s3-2026-10-25/particion-integracion/`.

- **El commit 1 de la §3 no es viable.** `aura_skeleton` es un bloque indivisible para los procesos vivos: el receptor y
  el cron de CM2 entran por `aura_skeleton.__main__`, cuyo cierre de imports es de 85 ficheros, con 44 rutas
  modificadas o nuevas de `aura_skeleton`. La partición literal (solo `reloj_cm2`, `receptor_nodos`, `nodos` y sus
  pruebas sobre HEAD) **hace fallar** `tests/unit/test_reloj_cm2.py::test_nombre_por_me_llamo_se_pregunta_como_nombre`
  (`etapa-literal1-pytest.log`). Control: la misma batería sobre la etapa 1 reasignada pasa (`control-etapa1-pytest.log`).
- **Ficheros compartidos en la §3:**
  - los commits 1 y 2 comparten `__main__.py` y `conftest.py`;
  - los commits 4 y 5 comparten 4 `.py` y `.gitignore`.
- **El despertador necesita además dos módulos nuevos:** `aislamiento.py` y `verificador.py`. Sin ellos no importa.
- **Import dinámico invisible al AST:** `adapters/estado_autonomo_cp.py` carga `observatorio` del control-plane con
  `importlib`.

### 8.1 Partición verificada

El estado del 2026-10-26 tiene 1872 entradas con `-uall`: **666 para commitear y 1206 excluidas**. Las rutas exactas
están en `commit-K.paths`, y `asignacion.tsv` recoge ruta, commit y motivo.

| # | Propósito | Rutas | Depende de | Validación tras el commit |
|---|---|---|---|---|
| 1 | Núcleo runtime completo: CM2, nodos, receptor, voz, cognición y memoria (`aura_skeleton/**`, manifiesto, pruebas del núcleo, sus mutaciones, `entorno/nodos/*`, scripts de voz) | 249 | — | Primero las pruebas de CM2, nodos y receptor; después el **QG** |
| 2 | Red de `_ruta_red` v2 y del aislamiento de dispositivos (2 pruebas y 2 toml; el código está en el 1) | 4 | 1 | Esas pruebas; puede plegarse al 1 |
| 3 | Arnés en copia aislada y el gate (`mutar.py`, `registro_gate.py`, `quality-gate.sh`, `test_arnes_*`, `retiradas/` y el **rename**) | 12 | — | **QG** (ya con el gate nuevo) |
| 4 | Control-plane **anterior** a la recuperación: 58 ficheros más 17 toml. Los 4 `.py` se indexan **desde** `previos-a-la-aplicacion/` | 68 | 3 | Suite del control-plane en copia, con 2 fallos esperados fuera de la ruta real |
| 5 | Recuperación tras caídas: los 7 ficheros del diff final y los 2 toml del ajuste de garantías | 9 | 4 | **QG** en vivo, incluidos los 2 tests de `test_red_capacidad_completada` |
| 6 | Evidencias, investigación externa y herramientas de medición sin pruebas | 240 | — | Ninguna; no toca código |
| 7 | Documentación, gobierno y panel (DP, mapa, `capacidades.json`, CHECKPOINT, CHECKLIST, `CLAUDE.md`, `.claude/{agents,rules}`, `panel_progreso` y su test, `publicado/`) | 84 | 1 a 6 | **QG** final y `preflight-check.sh` |

**Exclusiones verificadas:**

- datos vivos: `estado.json` y `eventos.jsonl`;
- artefactos: `__pycache__`, `graphify-out/`, `kernel.errors.txt`, `.githooks/omisiones.log`, cachés;
- cerrojos: `.control-plane.lock` y `.supervisor.lock`;
- `PARADA`, que está en `.gitignore`;
- ficheros efímeros: `.claude/ficha-evidencia.md` y `.claude/scheduled_tasks.lock`.

### 8.2 Verificación acumulativa

En cada etapa K se construye un árbol temporal con `git archive HEAD` más los commits 1 a K, y se comprueba que:

- **los imports se resuelven:** 0 sin resolver, por AST, incluidos los perezosos;
- **los tres procesos vivos importan:** `aura_skeleton.__main__` con `--receptor-nodos` y `--medir-cm2`, y `despertador`;
- **`pytest --collect-only` en walking-skeleton y en el control-plane** da 0 errores en las 7 etapas (de 3691 a 3862 y
  de 966 a 1435 recogidas).

La etapa 7 coincide con el worktree salvo en lo excluido (`diff-etapa7-vs-worktree.txt`).

**Límite:** esto valida las dependencias estáticas y de colección, **no el comportamiento** de cada etapa intermedia. El
comportamiento se valida con el QG en los commits 1, 3, 5 y 7 al ejecutar la partición.

### 8.3 Procedimiento (cuando el CEO lo autorice)

1. **Antes de empezar:**
   - regenerar `git status --porcelain=v1 -uall` y asignar toda ruta nueva al commit 7 o a excluidas;
   - des-stagear el rename para que no entre en el commit 1:
     `git reset -q -- walking-skeleton/mutaciones/arnes-validador-comandos.toml walking-skeleton/mutaciones/retiradas/arnes-validador-comandos.toml`.
2. **En cada commit:** `git add --pathspec-from-file=<…>/commit-K.paths`. Nunca `-A`.
3. **Commit 4:** indexar la versión previa **sin tocar el árbol**, para que los procesos vivos no vean nada:
   `git update-index --cacheinfo 100644,$(git hash-object -w <previos>/<f>.py),entorno/control-plane/<f>.py`. En el commit 5,
   `git add` de la versión viva.
4. **Antes de cada commit:** `git diff --cached --name-only | grep -E 'eventos.jsonl|estado.json|__pycache__|graphify-out|ficha-evidencia'`
   tiene que salir **vacío**.
5. **Si algo falla** (solo para commits propios, sin push y sin tocar el árbol):
   - antes de commitear: `git restore --staged --pathspec-from-file=…`;
   - ya commiteado: `git reset --soft HEAD~1` y después `restore --staged`;
   - **nunca** `git stash` a secas ni un reset `--hard`.
6. **Integración:** según la §5 (`merge --no-ff` en un subshell y QG en main), con `git diff HEAD main` antes de realinear
   para no tocar el código que ejecutan los procesos vivos.

**Riesgos que quedan:**

- El commit 1 es grande (249 rutas), porque no hay corte posible.
- 17 toml con mutantes no aplicables son **preexistentes en HEAD** y ajenos a esta partición. Se registran como
  observación técnica.
- El worktree cambia durante las sesiones: la asignación se hace **justo antes** de ejecutar.

### 8.4 Auditoría independiente (`auditor-consistencia`): CONSISTENTE CON RESERVAS, reservas resueltas

**Verificado correcto:**

- **Cobertura:** cada ruta en un solo commit o en las excluidas, sin rutas en dos commits.
- **Exclusiones:** ni datos vivos, ni cerrojos, ni PARADA, ni secretos.
- **Procesos vivos:** sus módulos están en commits menores o iguales a los que los necesitan.
- **Par 4→5:** aplicar el diff final sobre las versiones previas reproduce byte a byte las vivas, y `SHA256SUMS` da OK.

| Reserva | Resolución `[EJEC]` |
|---|---|
| **GRAVE:** al des-stagear el rename, la ruta **vieja** queda como borrado sin stagear y ninguna lista la incluía. El fichero viejo habría quedado en HEAD para siempre. La simulación no lo veía | Se añade a `commit-3.paths`. Comprobado en un repo desechable: `git add` de una ruta borrada registra el borrado (`D`) |
| **MENOR:** `test_red_tarea_lleva_su_contrato.py` (commit 4) lee `capacidades/etiqueta-observatorio-efecto.toml`, que estaba en el commit 7 | El contrato pasa al **commit 4** |
| **MENOR:** la propuesta se contradecía sobre el rename (§1 frente a §8.3) | Corregido en la §1 |
| **MENOR:** las etapas solo se validaron por colección, no por comportamiento | Declarado en la §8.2. El QG de los commits 1, 3, 5 y 7 es la validación de comportamiento al ejecutar |
| **Observación técnica**, preexistente y ajena a la partición: 23 toml con mutantes que no aplican, por ejemplo `fichero-ausente: communication_plane.py` | Es «declarado ≠ real» del repositorio. Pasa a deuda si algún incremento depende de esas garantías |

**Estado de las listas tras corregir:**

| Commit | 1 | 2 | 3 | 4 | 5 | 6 | 7 |
|---|---|---|---|---|---|---|---|
| Rutas | 249 | 4 | 13 | 69 | 9 | 272 | 83 |

En total, 699 rutas, sin duplicadas y **0 sin asignar** frente al `git status -uall` del 2026-10-26. El commit 6 incluye
los propios artefactos de la partición.

