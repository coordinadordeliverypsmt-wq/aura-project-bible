---
documento: "Decision Package — Candidato aislado en la autoconstrucción (verificar fuera del árbol vivo, promoción atómica, recuperación)"
tipo: "Decision Package. ALTERNATIVA A APROBADA por el usuario (CEO) el 2026-10-22 e IMPLEMENTADA el mismo día (ver §11)."
fecha: 2026-10-22
mantenido-por: "Dirección Técnica (sesión de asistencia)"
decide: "CEO (Mauricio)"
origen: "milestones/investigacion-externa/SINTESIS-2026-10-22-DVR-AGENTES-CAMARAS.md §3.2 (patrón IE-028; IE-023/IE-025)"
evidencia: "milestones/m3-entry/evidencia-candidato-aislado-2026-10-22/ (script reproducible + salida)"
---

# DP — Candidato aislado en `autoconstruccion.ejecutar`

## 1. Problema observado

### Flujo actual

Todo en `entorno/control-plane/autoconstruccion.py`, función `ejecutar` (L545-677) `[LECT]`.

1. Seis puertas, en este orden:
   1. zona (`zona_permitida`, L553);
   2. autorización humana (`esta_autorizada`, L557);
   3. `orquestador._INTOCABLES` (L588-595);
   4. **PARADA** (L596);
   5. vocabulario de operaciones (L607);
   6. segunda barrera (`es_sustituible`/`es_eliminable`, L615-631).
2. El candidato se genera **en memoria** (L622 / L631).
3. **Se escribe sobre el fichero vivo:** `ruta.write_text(nuevo)` (L632).
4. Se relee el fichero y se comprueba el efecto con el parser (L635-646).
5. Verificación: `sano = bool(verificacion()) if verificacion else None` (L658).
   - En uso real la crea `review.ejecutar_bajo_review` (review.py L534-542) a partir del contrato.
   - Es `verificador.arbol_sano` (L433-440), que lanza `pytest` con **`cwd=raiz`, el árbol vivo** (L368-371).
6. Rollback **desde memoria**:
   - si la verificación lanza una excepción, `except BaseException` (L659-667) y evento `cambio_revertido_por_error`;
   - si `not (efecto and sano)` (L669-671), sin evento propio.
7. Se registra `cambio_aplicado` (L676), **después** de verificar.

### Riesgos demostrados `[EJEC]`

Ejecutados sobre una copia, nunca sobre el repositorio:
`evidencia-candidato-aislado-2026-10-22/exp_candidato_en_arbol_vivo.py` y su `salida.txt`.

| # | Experimento | Resultado |
|---|---|---|
| R1 | Lectura del fichero objetivo **durante** la verificación | `'VALOR = 2\n'`: el árbol vivo ya contiene el candidato no aprobado. Cualquier gate, demo o proceso que lea en paralelo ve código sin verificar (la misma clase de fallo que «nada en paralelo con `herramientas.mutar`», CEO 2026-08-09) |
| R2 | `SIGKILL` del proceso durante la verificación | Código −9. El fichero **queda con el candidato**. En el directorio solo hay `.control-plane.lock`, `eventos.jsonl` y `s.py`: **sin respaldo**. Eventos: solo `propuesta_registrada` y `propuesta_autorizada`, **ningún rastro** de la escritura pendiente |

### Huecos de prueba `[EJEC grep]`

- La rama `except BaseException` (`cambio_revertido_por_error`) no tiene ninguna prueba.
- Ninguna prueba cubre una interrupción abrupta.
- Ninguna prueba exige que el árbol vivo esté sin candidato durante la verificación.
- No hay convención `xfail` en `entorno/control-plane`.

### Lo que ya está bien y no se toca

- Las seis puertas y su orden.
- PARADA comprobada antes de tocar disco.
- «No se midió» = revertir (L647-658).
- La tupla `_INTOCABLES` consultada y no copiada, con nombres resueltos.
- Ningún commit automático (`orquestador.RESTRICCIONES_PERMANENTES`).

## 2. Alternativas

Evaluadas por `arquitecto-evaluador`, solo lectura.

| | Mecanismo | ¿Cierra R1? | ¿Cierra R2? | Problema |
|---|---|---|---|---|
| **A** | Copia temporal fuera del árbol + verificación con `cwd`=copia + promoción atómica (`os.replace` desde un temporal **en el mismo directorio** que el destino) con precondición de hashes + diario de intención con el original en disco | **sí** | **sí** | Fidelidad de la copia (imports por ruta absoluta o `sys.path`, `conftest.py`); estado compartido (`estado.json`, `eventos.jsonl`); hace falta un manifiesto de hashes de todo lo copiado |
| B | `git worktree` | sí | parcial | Metadatos en `.git`, worktrees huérfanos tras un SIGKILL; parte de HEAD (ignora lo no confirmado); tensiona «no commit», la pila de stash compartida y ADR-0016 |
| C | `git archive HEAD` | aparente | no | **Verifica HEAD + candidato, no lo que se promueve** si hay cambios sin commit (hoy los hay): «declarado ≠ real». Vale para medir en paralelo (CLAUDE.md §2), no para certificar una promoción |
| D | Solo diario + instantánea en disco, sin copia | **no** | sí | Deja la exposición R1 abierta |

**Recomendación del ejecutor: A.** Es la única que cierra R1 y R2 y no depende del estado de git.

## 3. Flujo propuesto (A)

```
puertas 1-6 (sin cambios; NADA se escribe antes de PARADA)
 └─ L1  manifiesto: sha256 del objetivo + de cada fichero que se copiará
 └─ L2  copia controlada a mkdtemp() (fuera del repo); sin secretos, sin estado.json/eventos.jsonl reales,
        sin ~/.aura, sin PARADA; el entorno del subproceso de pruebas sin credenciales ni red
        (Landlock vía aislamiento.py cuando esté disponible; si no, se declara)
 └─ L3  candidato escrito SOLO en la copia; efecto releído en la copia
 └─ L4  verificación con cwd = copia, plazo y matar el árbol de procesos (verificador ya lo hace)
        «no se midió» (None/excepción/plazo) = RECHAZO → árbol vivo intacto (evento)
 └─ L5  [fase 2, ver §6] comparación con línea base
 └─ L6  revisión independiente + autorización humana (ya existen: REVIEW, esta_autorizada)
 └─ L7  promoción: PARADA otra vez → precondición (manifiesto == disco; si no, abortar: «la base cambió»)
        → diario de intención en disco (original + sha + id) → temporal en el MISMO directorio → fsync
        → os.replace → releer el vivo y comparar con el sha del candidato → evento cambio_aplicado
 └─ L8  fallo en la promoción → restaurar desde el diario → verificar sha del original → evento
        fallo al restaurar → error explícito + evento de alerta; jamás «PASS»
 └─ L9  arranque: diario huérfano ⇒ restaurar el original (ADR-0003: ante la duda, roja) + evento
        limpieza: solo el mkdtemp creado por esta ejecución (marcador propio dentro)
```

## 4. Invariantes de seguridad

1. Ninguna escritura (copia, diario ni temporal) antes de pasar las seis puertas. PARADA se comprueba otra vez antes
   de promover.
2. El árbol vivo es **byte a byte idéntico** si el candidato se rechaza, falla o se interrumpe antes de L7. Se
   comprueba con sha256.
3. La relectura del efecto se hace sobre la copia, y otra vez sobre el vivo tras promover.
4. «No se midió» = rechazar.
5. Precondición de hashes: si la base cambió entre la copia y la promoción, se aborta.
6. Cada eventualidad deja un evento: rechazo, abandono, promoción, restauración y recuperación al arranque. Se
   conserva el esquema de los cuatro eventos actuales.
7. El candidato no puede tocar el evaluador, los gates, PARADA, los permisos ni `_INTOCABLES`. La puerta 3 sigue
   siendo la misma; además, la copia no incluye los intocables como escribibles.
8. Sin commit, push ni deploy automáticos. La aprobación humana es un evento explícito (`propuesta_autorizada` con
   autoridad `ceo`/`humano`), nunca se infiere de un PASS.
9. Presupuesto: plazo de verificación (el que ya existe) y tope de cambios por ciclo (`ciclo(max_cambios)`, tope del
   motor). Sin bucles nuevos.

## 5. Matriz de fallos y recuperación

| Fallo | Estado del árbol vivo | Evento | Prueba |
|---|---|---|---|
| Las pruebas del candidato fallan | intacto | `cambio_rechazado` (nuevo) | T2 |
| Excepción o plazo agotado en la verificación | intacto | `cambio_revertido_por_error` (se conserva) | T3 |
| SIGKILL entre L2 y L6 | intacto (nunca se escribió) | ninguno; la copia huérfana se detecta por su marcador | T4 |
| La base cambia antes de L7 | intacto | `promocion_abortada_base_cambiada` | T5 |
| Sin autorización o denegada | intacto (ni copia) | rechazo actual | T6 |
| Falla `os.replace` | restaurado desde el diario y verificado | `promocion_revertida` | T7 |
| Falla la restauración | **alerta**; no se declara éxito | `restauracion_fallida` | T8 |
| SIGKILL durante L7 | el diario lo recupera al arranque | `recuperacion_al_arranque` | T4b |

## 6. Plan TDD (las pruebas RED se escriben al aprobarse el DP)

En `entorno/control-plane/test_red_candidato_aislado.py`. Comando oficial:
`cd entorno/control-plane && python3 -m pytest test_red_candidato_aislado.py -q`.

| T | Prueba | RED hoy |
|---|---|---|
| T1 | Candidato válido: durante la verificación el sha del fichero vivo == sha original; tras promover, == sha del candidato | **sí** (R1 demostrado) |
| T2 | Verificación `False` ⇒ sha del vivo == original, **y en ningún momento** contuvo el candidato (lector espía) | sí (hoy se escribe y luego se revierte) |
| T3 | Excepción o plazo agotado ⇒ vivo intacto + evento; el diagnóstico no contiene secretos | parcial (hoy revierte, pero expone) |
| T4 | SIGKILL en un subproceso durante la verificación ⇒ el vivo es el original | **sí** (R2 demostrado) |
| T4b | SIGKILL simulado entre el diario y `os.replace` ⇒ el arranque restaura y registra | sí (no hay diario) |
| T5 | Se modifica el fichero vivo entre la copia y la promoción ⇒ abortar sin escribir | sí |
| T6 | Sin autorización o denegada ⇒ no se crea ninguna copia ni se escribe nada | control (hoy pasa) |
| T7 | `os.replace` falla (monkeypatch) ⇒ el vivo es el original, verificado por sha | sí |
| T8 | Falla también la restauración ⇒ excepción explícita + evento; el resultado nunca es «sano» | sí |
| T9 | La copia no contiene `~/.aura`, PARADA, `.env` ni ficheros con secretos; el entorno del subproceso está saneado | sí |
| T10 | Un candidato sobre `review.py`, `orquestador.py` o PARADA se rechaza igual que hoy (puerta 3), sin copia | control |

Además:
- Mutación en `walking-skeleton/mutaciones/`, con un TOML propio. Mutantes: «verificar con cwd del vivo», «quitar la
  precondición de hashes», «no escribir el diario», «restaurar sin verificar el sha», «promover sin PARADA».
- La batería de `entorno/control-plane` completa sin regresiones; la línea base documentada es «1100 passed»
  (CHECKLIST, 2026-09-21), que se volverá a medir.

## 7. Superficies protegidas y no objetivos

**Requieren acta del CEO:**
- `autoconstruccion.py`: escribe el candidato.
- `review.py`, L534-542: ata el verificador a la raíz del vivo.
- Posiblemente `conftest.py`, si fija rutas absolutas. No está verificado.

Los tres están en `orquestador._INTOCABLES` (L84-85).

**Sin acta:**
- `verificador.py`, que puede alojar la maquinaria pura (copia, manifiesto, promoción y diario) y ya usa `mkdtemp`
  (L359-363).
- Las pruebas nuevas.

Construir solo esa maquinaria **no cierra la brecha**: el fichero vivo se sigue escribiendo en L632 hasta que el acta
autorice conectarla. Presentarla como corrección violaría INV-9.

**No objetivos:**
- evolución general del anillo;
- la cámara y el DVR;
- cambiar `_INTOCABLES`;
- la línea base y los fallos repetidos (§8);
- git worktree.

## 8. Observaciones confirmadas, fuera de este DP

- **Sin línea base** `[LECT + grep]`. Se acepta con `efecto and sano`, que es booleano, y nada compara métricas
  antes y después.
  - Propuesta posterior: un DP de «aceptación contra línea base con conjunto retenido» (IE-024/IE-021).
  - Métricas: éxito verificado, regresiones, falsos éxitos, flakiness, latencia, tasa de rollback y mutantes vivos.
- **Sin detector de fallos repetidos por clase.** `planificador.intentos_de` cuenta por tarea y `estancamiento`
  mide ausencia de progreso.
  - Es una observación, no deuda (CLAUDE.md §7): no hay un bloqueo observado que lo promueva.

## 9. Coste y migración

- **Esfuerzo:** ~1 incremento (RED → GREEN → mutación → gate), sin dependencias nuevas.
- **Reversibilidad:** alta; es un cambio local en dos o tres ficheros.
- **Migración:** ninguna. El diario y la copia son efímeros.
- **Coste en ejecución:** una copia de los ficheros necesarios por verificación, unos MB en `tmpfs` o en disco; el
  tiempo de pytest no cambia.

## 10. Decisiones requeridas al CEO

1. ¿Se aprueba la alternativa **A** y el **acta** para modificar `autoconstruccion.py` y `review.py` (y `conftest.py`
   si se demuestra necesario)?
2. ¿La recuperación al arranque restaura el original **aunque PARADA esté armada**? Toca ADR-0024. La recomendación
   es sí: restaurar el original es volver al estado aprobado, no actuar.
3. Diario huérfano tras una promoción a medias: ¿revertir (ADR-0003, recomendado) o completar?
4. ¿Componente nuevo, o extender `verificador.py`? Lo recomendado es extender: la regla de no crear un componente
   si existe un equivalente.
5. ¿Entra como corrección de seguridad del anillo, o exige evidencia de uso repetido (`PLAN-DE-FORMACION-AURORA.md`)?

**Mientras no se decida:**
- No se modifica nada.
- La brecha queda documentada.
- La regla operativa vigente sigue siendo: nada en paralelo con una ejecución del anillo.


## 11. Implementación (2026-10-22, autorizada)

**Alcance tocado:**
- `entorno/control-plane/autoconstruccion.py` (1301 líneas; por encima del techo blando de 800, ver límites);
- `entorno/control-plane/review.py`: el verificador recibe la raíz de la copia y el resultado propaga los flags;
- prueba nueva `test_red_candidato_aislado.py` (86);
- `mutaciones/candidato-aislado.toml` (38, nuevo);
- re-anclajes en `blindaje-del-anillo.toml` y `verificador.toml`, con la misma degradación.

No se tocó ningún otro fichero.

**Comportamiento implementado:**
- Puertas 1-6 intactas. `recuperar` corre después de PARADA y con PARADA armada no escribe.
- Copia `mkdtemp` sin secretos, symlinks, `.git`, `.venv`, `estado.json`, `eventos.jsonl` ni `PARADA`, con manifiesto
  sha256.
- Candidato y verificación **solo en la copia**.
- Promoción bajo `flock`:
  - PARADA comprobada otra vez;
  - comprobación de `BLOQUEADO` y de diarios ajenos;
  - precondición de manifiesto y del sha del original del que se derivó el candidato (H2);
  - diario 0600/0700 fuera del repo (`~/.local/state/aura/autoconstruccion/<clave>/`, o `AURA_AUTOCONSTRUCCION_ESTADO`);
  - temporal `O_EXCL|O_NOFOLLOW` en el mismo directorio, `os.replace` y relectura;
  - restauración verificada por sha, o `RestauracionFallida` + `BLOQUEADO`.
- `recuperar`:
  - idempotente;
  - valida cada diario antes de actuar: directorio, ruta resuelta dentro, `zona_permitida`, no intocable, `id`, `tmp`,
    sha del respaldo;
  - con un diario corrupto o forjado bloquea sin tocar nada;
  - barre solo las copias huérfanas propias (marca válida, pid muerto, más de 1 h).
- El estado vacío se retira bajo el cerrojo, con comprobación de inodo: la batería no deja residuos en `HOME`.

**Resultados:**
- `test_red_candidato_aislado.py`: 86 passed. RED observado en cuatro rondas: 19/26, 28/61, 8/70 y 4/79.
- Batería completa de `entorno/control-plane`: **1290 passed, 1 skipped**.
- Mutación: candidato-aislado 38/38; las 7 baterías existentes del anillo, 44/44.
- Brecha original [EJEC], con el mismo script: el vivo conserva `VALOR = 1` durante la verificación y tras SIGKILL
  (`evidencia-candidato-aislado-2026-10-22/salida-despues.txt`).

**Revisiones independientes:**
- Seguridad, ronda 1: NO APTO (H1 diario forjado, H2 actualización perdida, M1-M5).
- Seguridad, ronda 2: APTO CON RESERVAS (R1 `zona_permitida` en el diario, R2, reservas A y B). Todo corregido después.
- Código: WARNING (A1 verificador sin parámetros; A2 mutantes sin prueba). Corregido.

**Desviaciones y límites (declarados, no ocultos):**
1. **Verificador sin parámetros** (heredado): mide el árbol vivo y el resultado lo declara como
   `verificacion_aislada: False`. La ruta de producción (`review.py`) está aislada. Pasar a fail-closed exige migrar
   unas 30 `lambda: X` de otros ficheros de prueba, que no estaban en el alcance: **decisión del CEO pendiente**.
2. **Ejecución sin confinar:** `ejecucion_confinada: False`. Landlock existe
   (`aislamiento.preparar` + `verificador.ejecutar_pruebas(confinar=…)`), pero confinar la lectura a la copia produciría
   rechazos falsos sin medirlo contrato a contrato. **Pendiente.**
3. **Atomicidad por fichero**, no transacción multi-fichero: `ejecutar` cambia un único fichero.
4. **Ventana residual** entre la última lectura del original y `os.replace`: solo la explota un escritor externo que
   no use el cerrojo; POSIX no tiene un replace condicional.
5. **El rechazo se registra como `cambio_aplicado` con `revertido=True`** (compatibilidad), con `motivo`; no como
   `cambio_rechazado` (§5). `motor_autonomia` sigue contando cualquier `revertido` como «verificación fallida», y el
   comentario de `planificador.py:165` quedó desfasado. Ambos ficheros están fuera del alcance: **pendiente**.
6. **Fidelidad de la copia:** solo se copia `directorio`. Una prueba de contrato que lea fuera, por ejemplo con
   `parents[2]`, no lo verá. No se han visto fallos.
7. Un destino fuera de `directorio` o con nombre sensible da `CandidatoNoAislable` (fail-closed). Afecta a la vía del
   acta del 2026-09-07 (`milestones/m3-entry/medicion-razonador/heuristicas_deterministas.py`) si se usara con esa raíz.
8. Tamaño: `autoconstruccion.py` supera las 800 líneas. Extraer la maquinaria a `verificador.py` no estaba
   autorizado.

## 12. PROMPT 02 (2026-10-23): verificadores explícitos y Landlock

**Defecto alto corregido** `[EJEC]`:
- Los dos contratos reales declaran `pruebas_minimas` con rutas absolutas al árbol vivo. Con `raiz=copia`, pytest cargaba
  los módulos del **vivo**.
- La vía de producción (`review.py`) declaraba `verificacion_aislada=True` mientras verificaba el original.
- **El límite 1 de la §11 («la ruta de producción está aislada») era falso.**

**Fase A** (solo `autoconstruccion.py`, `review.py` y `test_red_candidato_aislado.py`):
- `ResultadoVerificacion` (`sano` | `fallo` | `error_infraestructura` | `no_aislable` | `sin_confinamiento`), del que se
  derivan `verificacion_aislada`, `ejecucion_confinada` y `motivo`.
- `review._verificador_de_review` remapea cada prueba a la copia con rutas resueltas. Si una prueba queda fuera,
  devuelve `no_aislable` sin ejecutar.
- La copia lleva `estado.json` y `eventos.jsonl` como solo lectura, fuera del manifiesto, y solo en la raíz.
- Los dos contratos reales se verifican en la copia: sanos con la copia intacta y en fallo con un candidato que rompe
  el módulo.
- **Los 72 verificadores `lambda: X` de 14 ficheros de prueba NO se migraron:** están fuera del alcance.
  Inventario completo en `INVENTARIO-VERIFICADORES-Y-MATRIZ-LANDLOCK.md`. Hace falta ampliar la autorización para
  migrarlos y después convertir la vía heredada en error.

**Fase B** (mismos ficheros):
- La verificación por contrato es **confinada obligatoriamente** con Landlock, usando
  `vf.ejecutar_pruebas(..., confinar=ais.preparar(raiz))`. `verificador.py` y `aislamiento.py` no se modificaron.
- Sin Landlock (ABI del kernel o del confinador ≤ 0) **no se ejecuta nada y se rechaza** (`confinamiento_no_disponible`).
- Un fallo al aplicar las reglas da `error_infraestructura`.
- `ejecucion_confinada=True` solo si corrió bajo Landlock.
- Medido con señuelos fuera de la copia (sha intacto):
  - la escritura queda bloqueada, también para hijos y nietos;
  - los dos contratos reales son sanos y confinados.

**Límites medidos** (revisión de seguridad: APTO CON RESERVAS, documentación corregida):
- **La lectura NO está aislada.** `aislamiento.rutas_del_interprete()` concede lectura a `sys.path`, que incluye el
  plano vivo, y a `/etc` y `/proc`.
- Landlock aquí no cubre ni la red ni las señales.

Restringirlo exige modificar `aislamiento.py`, que está **fuera del alcance**.

**Pruebas:**
- `test_red_candidato_aislado.py`: 118. RED: Fase A 16/102, Fase B 11/112, reservas 2.
- Batería del anillo: 1324 passed, 1 skipped.
- Mutación: candidato-aislado 57/57; las 21 baterías existentes, sin supervivientes (re-anclados CA-M1, CA-M26,
  CA-M37, BA-M3, VF-M1 y AC-M9).
- QG PASS 3811 (log `~/.claude/jobs/d6cb894c/tmp/qg-prompt02.log`).

## 13. PROMPT 03/04 (2026-10-23 → 25): cierre

- Fase A: la vía sin raíz se retiró (`VerificadorSinRaiz`) y los 72 consumidores se migraron.
- Fase B: verificación por contrato confinada en **modo estricto**. Detalle de controles y límites en el docstring de
  `aislamiento.py` y en el CHECKPOINT (p).
- Seguridad: **APTO** tras 5 rondas (vsock, SysV, metadatos, keyring, xattr, prlimit64/sched, inotify cerrados).
- Mutación: aislamiento-estricto 35/35, candidato-aislado 63/63.
- QG PASS 3811.
- El límite 2 de la §11 (ejecución sin confinar) queda resuelto. El límite 1 (verificador heredado) queda resuelto
  (retirado).
- **Cierre verificado (2026-10-25):** `auditor-consistencia` contrastó cifras y código con los logs persistentes, todo
  coincide. Pendientes: MEDIO-2 (motores, requiere autorización) y la carpeta `pytest-of-majo1230/` (intacta).
  CHECKPOINT (q).
