# Procedimiento de inicio oficial del reloj de CM2

> **Actualizacion 2026-10-25:** el inicio **SE EJECUTO** el 2026-10-07T22:46:52Z (`cm2.inicio`, seq 1314), ratificado en
> `decisiones/2026-10-18-acta-ratificacion-inicio-cm2.md`; la medicion diaria la lanza el cron de usuario
> (`decisiones/2026-10-18-acta-reintentos-cron-cm2.md`). El estado original de abajo se conserva como historia.
> La observacion y evaluacion del gate S3 estan en el §7.

**Estado: NO ejecutado. Este documento no autoriza el inicio.** Lo autoriza solo el CEO con una orden explicita
(resolucion S3, §2.2 fase 3 y §3: «Inicio oficial (Q2a(iii))»). Mecanismo: `walking-skeleton/aura_skeleton/core/reloj_cm2.py`.

## 1. Precondiciones (todas verificables; si una falla, no se inicia)

| # | Precondicion | Como se verifica |
|---|---|---|
| 1 | Orden explicita del CEO de iniciar | Referencia en el acta/commit; sin ella, parar |
| 2 | Quality Gate en PASS sobre el commit a usar | `cd walking-skeleton && ./quality-gate.sh` termina en PASS |
| 3 | Mutacion del reloj verde | `cd walking-skeleton && python3 -m herramientas.mutar mutaciones/reloj-cm2.toml` sale con codigo 0. **Nada en paralelo** mientras corre (CLAUDE.md §2) |
| 4 | Preflight APTO | `bash entorno/scripts/preflight-check.sh` termina en `ESTADO: APTO` |
| 5 | PARADA / KILL | No hay PARADA (a) del control-plane vigente ni fichero `KILL` armado en `AURA_DATOS` que el CEO no haya decidido mantener. Ninguno **impide** iniciar (el reloj solo audita, no ejecuta acciones del Motor Unico), pero se registra el estado en el acta para no confundir un silencio posterior con un fallo |
| 6 | `AURA_DATOS` correcto | `echo "$AURA_DATOS"` (por defecto el directorio de datos real de AURA); debe existir y contener `memoria.json` (o `audit.jsonl`). `iniciar` rechaza un directorio inexistente o vacio sin crear nada |
| 7 | Aun no iniciado | `python -m aura_skeleton --medir-cm2` imprime `reloj de CM2: NO iniciado` (consultar no escribe nada) |

## 2. Comando exacto

Desde `walking-skeleton`, con `AURA_DATOS` apuntando al directorio real:

```bash
python -m aura_skeleton --iniciar-cm2 --confirmo-inicio
```

Salida esperada: `reloj de CM2: iniciado`. Sin `--confirmo-inicio` no emite nada. Repetirlo es idempotente
(`reloj de CM2: ya iniciado; no se modifica`). El inicio **no se puede deshacer**: el audit log es append-only.

## 3. Como verificar el evento

```bash
grep '"evento": "cm2.inicio"' "$AURA_DATOS/audit.jsonl"      # tambien en los segmentos rotados del mismo directorio
python -m aura_skeleton --medir-cm2
```

- El `grep` debe dar **una** linea con `ts` (epoch del inicio) y `seq`. Anotar ambos en el acta.
- `--medir-cm2` debe imprimir `reloj de CM2: iniciado` y una linea `inicio del reloj: <fecha ISO UTC> (seq N)` que
  coincida con el evento. Si la linea dice `inicio: no registrado`, el evento no esta en el historial: no hay calendario.

## 4. Que NO cuenta

**El tiempo anterior al inicio.** El origen de cada hecho es `max(valid_from, ts del primer cm2.inicio)`, y
`version_edad_dias` tampoco cuenta tiempo previo. Un hecho declarado 60 dias antes del inicio se sondea por primera
vez 7 dias **despues** del inicio, no «a 28 dias» el primer dia. Tampoco cuentan: ecos episodicos (sin `hecho_id`),
sondas tardias fuera de [28, 35] dias, ni versiones con menos de 28 dias.

## 5. Calendario esperado

Para un hecho declarado antes del inicio (instante I): sondas a I+7, I+14 e I+28 dias, ejecutadas por
`--medir-cm2` (que debe lanzarse en cada ventana; no hay proceso residente). Para un hecho declarado despues
(valid_from V): V+7, V+14, V+28. La tasa solo puede publicarse con sondas de dia 28, por tanto **no antes de 4
semanas naturales (28 dias) tras el inicio**, y solo si hay al menos el minimo provisional de sondas de dia 28
(`MINIMO_SONDAS_DIA28`); si no, el informe dice «sin datos suficientes». Las cuatro semanas no se simulan (§2.2 fase 4).
No se fijan fechas aqui: dependen del instante real del inicio.

## 6. Quien autoriza

El **CEO**. Este procedimiento, la resolucion S3 y quien lo redacta no autorizan ni ejecutan el inicio. La evaluacion
final de CM2 (fase 5) tambien es del CEO; el resultado es un **indicador preliminar** (Q3) y la fabricacion se informa
**no evidenciada** mientras no haya revision humana por muestreo.

## 7. Observacion y evaluacion del gate S3 (añadido 2026-10-25)

### 7.1 Criterio del gate — fuentes literales

- **Gate (D-CM2-1, literal):** «mantener abierto el gate de CM2 hasta disponer de al menos 20 sondas validas del dia 28
  y satisfacer todos los criterios vigentes». La poblacion son solo hechos **espontaneos** del uso real: ni sembrados,
  ni importados, ni reconstruidos.
- **Lectura operativa:**
  - El gate sigue **abierto** mientras el informe del cron diga `CM2: sin datos suficientes`.
  - Alcanza el minimo cuando dice `CM2 (indicador preliminar): X % (r/n)`, que exige n ≥ `MINIMO_SONDAS_DIA28`.
  - Ese minimo es **20**. Su naturaleza normativa esta en la tabla 7.1.1.
- **Evaluacion final de CM2:** es del **CEO (fase 5, §6 de este documento)** y el resultado es un indicador
  preliminar (Q3).
- **Fabricacion (regla de informe; ratificada por el CEO el 2026-11-09):** sin revision humana por muestreo se informa
  «fabricacion no evidenciada» (Resolucion S3 Q5 (b); DP-S3 §7, recomendacion (b), ~L589), y no puede afirmarse
  «cero fabricacion» sin evidencia humana (DP-S3 ~L586). La revision humana forma parte de la **evaluacion final del
  CEO (fase 5)**; **no es condicion literal del gate**. Las recuperaciones `valor_retirado` son la muestra a revisar;
  el tamaño, la frecuencia y el criterio de aceptacion de la muestra siguen **sin definir**.
- **CM1 (ratificado por el CEO el 2026-11-09):** CM1 (P50 ≤ 800 ms) es criterio de aceptacion de **R1**, **no**
  condicion del gate D-CM2-1 (DP-S3 §1, L21; mapa §13-§14). Su criterio y su bloqueo de hardware en HC-1 no cambian.
  Sigue **pendiente** la validez de los datos de CM2 si se sustituye HC-1 (DP-S3 L625-626).
- **Lo que NO esta escrito, y no se presume:**
  - Que la revision humana sea condicion del gate. Esta seccion corrigio asi la redaccion anterior del mapa maestro, y
    el CEO lo ratifico el 2026-11-09.
  - Un umbral porcentual para S3. El «≥ 90 %» es el criterio de Bible 2.5 §5.2 (DP-S3 L54, «propuesto» segun su nota †).
    Ningun documento leido lo fija como condicion del gate S3, y el DP solo exige que, sin datos, se diga
    «sin datos suficientes», nunca «90 %» (L360-361).

#### 7.1.1 Clasificacion normativa de cada parametro (revision 2026-10-25 (s))

| Elemento | Valor | Fuente | Naturaleza |
|---|---|---|---|
| Umbral del gate | ≥ 20 sondas validas de dia 28 | D-CM2-1 L23 (orden del CEO, literal) | **Normativo** (decision del CEO). En el codigo, `MINIMO_SONDAS_DIA28` lleva el comentario «provisional (Q5), revisable»: el CEO puede revisarlo, pero hoy rige 20 |
| Poblacion | Hechos tipados y espontaneos; ecos fuera | Resolucion S3 Q5 L43 + D-CM2-1 | **Normativo** («base provisional y revisable», aprobada por el CEO) |
| Exclusion de retiradas | Solo las del usuario (olvido, refutacion) | Resolucion S3 Q5 (a) | **Normativo**, base provisional |
| Revision humana | Sin ella, la fabricacion es «no evidenciada» | Resolucion S3 Q5 (b); ratificado por el CEO el 2026-11-09 | **Normativo como regla de informe** y parte de la evaluacion final del CEO (fase 5), **no** como condicion del gate |
| Version con ≥ 28 dias | Un valor cambiado el dia 27 no retiene a 28 | DP-S3 §5.2, adoptado como base por Q5 | Normativo, base provisional |
| Tolerancia de la ventana | `[28, 35]` dias (`TOLERANCIA_SONDA_DIAS = 7`) | Decision del CEO del 2026-11-09 (antes, solo el comentario del codigo «provisional (Q5), revisable») | **Normativo** (ratificado por el CEO el 2026-11-09): ventana de 28 a 35 dias, sin adelantos; la tolerancia solo retrasa, nunca adelanta. Hasta esa fecha fue parametro de implementacion sin decision explicita (§7.6) |
| Pausas de la ventana | No definidas | DP-S3 §5.2 «Pendiente» | **Indefinido**. No pueden usarse para extender ventanas automaticamente (CEO, 2026-11-09) |
| CM1 (P50 ≤ 800 ms) | Criterio de aceptacion de R1 | DP-S3 §1 L21; mapa §13-§14; decision del CEO del 2026-11-09 | **No es condicion del gate D-CM2-1**. Criterio y bloqueo de hardware sin cambios |
| Validez de los datos tras sustituir HC-1 | Sin decision | DP-S3 L625-626 | **Pendiente** (decision del CEO) |
| Umbral porcentual de S3 | Ninguno | — | **No existe**; no se presume |

**Sonda valida** = la que cuenta `tasa_dia28`. Es un evento `cm2.sonda` que cumple todo esto:

- tiene `hecho_id` y `dia == 28`;
- es la **primera** de ese hecho, por `seq`;
- `edad_dias` esta en `[28, 35]`;
- `version_edad_dias` es ≥ 28;
- no esta excluida por la politica por defecto, que solo excluye las retiradas iniciadas por el usuario
  (`olvido`, `refutacion`).

Solo `vigente` cuenta como recuperado; `nada`, `sin_consulta` y `valor_retirado` cuentan como **no** recuperados.

### 7.2 La fecha del gate NO es una fecha del reloj

**Regla vigente (ratificada por el CEO el 2026-11-09). No hay fecha fija: la cota se recalcula en cada observacion.**

- El dia 28 se cuenta **por hecho**. Su origen es `max(valid_from, inicio del reloj)`, tomando el `valid_from` de la
  **primera** declaracion espontanea del hecho (instante de la declaracion, `ejecutor_modelo_usuario.py` ~L316); una
  re-declaracion no reinicia el origen.
- **Ninguna sonda puede hacerse antes de `origen + 28 d`.** No hay adelantos.
- Una sonda solo cuenta si se hace dentro de la **ventana ratificada de 28 a 35 dias** y cumple el resto de la
  definicion de sonda valida (§7.1.1). La tolerancia solo puede retrasar, nunca adelantar. Las pausas siguen sin
  definir y no extienden ventanas automaticamente.
- El gate solo puede evaluarse cuando existan **al menos 20 sondas validas de dia 28**. Eso exige como minimo 20 hechos
  espontaneos, tipados y elegibles, y su primera fecha posible es el origen del vigesimo hecho elegible + 28 d, medida
  por el cron esa noche o la siguiente. Cerrar el gate no es aceptar CM2: eso es la evaluacion final del CEO (fase 5).

**Notas historicas fechadas.** Se conservan como registro; **no son fechas objetivo vigentes**:

- El 2026-11-04 (inicio + 28 d) es solo la fecha **teorica minima** para hechos que ya existieran en el inicio, y no
  habia ninguno.
- Ultima medicion antes de esta revision `[EJEC]`: el 2026-10-24, ciclo de 21:32:43 a 21:34:33 (-05:00); el audit se lee al principio del ciclo, con poblacion 0 y 0 sondas
  (`~/.local/state/aura-cm2.dia` y `aura-cm2.log`).
- *[Historico: calculado con la medicion del 2026-10-24; superado, no vigente.]* **Cota derivada del modelo, no proyeccion:** ninguna sonda de dia 28 puede existir antes del **2026-11-21 21:32 (-05:00)**, salvo que llegue una senal con `ts` anterior a esa lectura, cosa que no ocurre en el uso real. El gate
  necesita 20 hechos espontaneos con 28 dias cada uno, asi que su primera fecha posible es
  `valid_from del 20.º hecho + 28 d`, medida por el cron esa noche o la siguiente.
- *[Historico: escrito el 2026-10-25; fecha ya pasada, no vigente.]* **Lectura esperada el 2026-11-04:** `sondas de dia 28 contadas: 0` y `CM2: sin datos suficientes`. Cualquier otra
  lectura es una anomalia (§7.4).

### 7.3 Observacion (solo lectura; despues de las 23:45 hora local)

```bash
cat ~/.local/state/aura-cm2.dia               # FECHA ESTADO INTENTOS SONDAS_ACUMULADAS (debe ser la fecha de hoy)
grep -n 'inicio --medir-cm2' ~/.local/state/aura-cm2.log | tail -n1   # linea donde empieza el ultimo ciclo
sed -n "$(grep -n 'inicio --medir-cm2' ~/.local/state/aura-cm2.log | tail -n1 | cut -d: -f1),\$p" ~/.local/state/aura-cm2.log  # su informe completo
crontab -l | grep aura-medir-cm2              # 4 horarios: 21:30, 22:15, 23:00, 23:40
```

- **No** lanzar `--medir-cm2` a mano: escribe sondas en el audit real, y esa tarea es del cron.
- **No** leer `~/.aura` directamente.
- Correspondencia con el gate:
  - `sondas de dia 28 contadas: N` → N sondas validas;
  - `fuera de la tasa: k tardia(s)` → ventanas perdidas;
  - `k recuperacion(es) de valor retirado` → muestra pendiente de revision humana.

### 7.4 Datos ausentes, inconsistencias o errores

| Observacion | Significado | Accion |
|---|---|---|
| `.dia` no tiene la fecha de hoy despues de las 23:45 | El cron no corrio | Revisar `crontab -l` y que exista `WS` (el script fija la ruta del worktree `m3-entry`). Lanzarlo a mano escribe en `~/.aura`: **DECISION_REQUIRED** |
| Estado `error` | Ese dia ya no se reintenta | Leer la linea `error:` del log, diagnosticar y registrar |
| `aplazado` 4 veces | AURA principal vivo en las cuatro ventanas | Se reintenta al dia siguiente. Con mas de 7 dias seguidos, las sondas de esos hechos quedan **tardias** y fuera de la tasa: queda medido, no oculto |
| `reintentable` | Memoria en escritura | Lo reintenta el siguiente horario. Si era el ultimo (23:40), espera al dia siguiente |
| `no_iniciado` | El audit leido no contiene `cm2.inicio` | **P0:** el inicio existe desde el 2026-10-07 (seq 1314). Un `AURA_DATOS` distinto o un audit perdido: parar y elevar |
| `ANOMALÍA: sondas acumuladas bajan` | Audit perdido o estado manipulado | **P0 de integridad:** parar y elevar; no corregir datos |
| `tardia(s)` > 0 | Ventanas de dia 28 perdidas | Registrar las fechas; no recalcular a mano |
| `valor_retirado` > 0 | Candidatas a fabricacion | Elevar al CEO para revision humana (fase 5) |
| Crece la poblacion pero no aparecen sondas en `valid_from + 7/14/28` | Posible defecto del mecanismo | Validar en aislado (§7.5) antes de concluir nada |
| Se va a mover, fusionar o eliminar el worktree `m3-entry` | El cron se quedaria sin `WS` | Actualizar antes la ruta del script (instalacion: requiere autorizacion) |

### 7.5 Validacion reproducible del mecanismo (sin datos reales)

```bash
cd walking-skeleton
python3 -m pytest -q tests/unit/test_reloj_cm2.py tests/integration/test_reloj_cm2_integracion.py \
  tests/integration/test_declaracion_sin_llm.py
python3 -m herramientas.mutar mutaciones/cm2-cableado-produccion.toml   # NADA en paralelo mientras corre
```

Las pruebas `test_produccion_*` de `test_reloj_cm2_integracion.py` recorren toda la cadena de produccion. Estan en ese fichero porque es el unico que la guardia estatica `test_ninguna_prueba_del_repo_puede_iniciar_el_reloj_real` autoriza a iniciar relojes de tmp: `componer` → declaracion →
`cm2.hecho_registrado` → `medir` a +28 d → sonda `vigente`. Todo ocurre en `tmp_path`.

### 7.6 Decisiones abiertas y riesgo operativo (2026-10-25 (s)). NO ejecutado

**Tolerancia de 7 dias — RESUELTA (CEO, 2026-11-09).** Ventana ratificada: de 28 a 35 dias, sin adelantos. El codigo ya
la aplica (`TOLERANCIA_SONDA_DIAS = 7`) y no se cambia.

- Afecta a que sondas cuentan **solo** si el cron pierde mas de 7 dias seguidos de medicion.

**Pausas de la ventana — PENDIENTE.** Sin definir (DP-S3 §5.2). Mientras no se definan, **no pueden usarse para extender
ventanas automaticamente** (CEO, 2026-11-09).

**Dependencia del cron respecto del worktree (riesgo CONFIRMADO, `~/.local/bin/aura-medir-cm2.sh`):**

- `WS` esta fijado a `…/.claude/worktrees/m3-entry/walking-skeleton`. Si se mueve, se fusiona o se elimina el
  worktree, cada ciclo termina en `error: no existe el directorio de trabajo`.
- **Sin reintento:** el estado `error` cierra el dia.
- Despues de 7 dias sin medir, las sondas de dia 28 de esos hechos quedan tardias y fuera de la tasa.

**Propuesta de migracion. Requiere autorizacion expresa y no se ha ejecutado:**

1. Elegir el destino: el checkout de `main` despues del merge, o una ruta estable.
2. **Precondicion:** el destino contiene el mismo `aura_skeleton/core/reloj_cm2.py` (mismo sha) y pasa
   `pytest tests/unit/test_reloj_cm2.py tests/integration/test_reloj_cm2_integracion.py`.
3. **Fuera de las ventanas del cron** (no entre las 21:25 y las 23:50):
   - `cp -n` del script a `aura-medir-cm2.sh.bak-<fecha>`, con umask 077;
   - escribir la version nueva en un temporal **y** `mv -T` sobre el original, lo que crea un inodo nuevo (bash lee
     el script de forma incremental, y reescribirlo en sitio durante un ciclo corrompe la ejecucion);
   - cambiar **solo** la linea `WS=`.
   - **Mejora recomendada, en la misma autorizacion:** rechazar un `WS` que sea enlace, ajeno o escribible por
     grupo u otros, igual que el script ya hace con `ESTADO`. `WS` es el directorio desde el que el cron carga codigo.
4. **Validar sin tocar datos reales:**
   - exportar `AURA_DATOS=<tmp>/datos`, que debe existir y contener un `memoria.json` vacio, y `HOME=<tmp>/home`,
     **ademas de** `AURA_CM2_PRUEBAS=1 AURA_CM2_ESTADO_DIR=<tmp>/estado AURA_CM2_HOY=<fecha>`. El script **no**
     fija `AURA_DATOS`: sin ella, el ensayo haria una medicion **real**, irreversible en el audit append-only;
   - como guarda, anotar `stat -c '%s %Y' "$HOME_REAL/.aura/audit.jsonl"` antes y despues: debe coincidir;
   - resultado esperado: **`no_iniciado`** en `<tmp>/estado/aura-cm2.dia` (un tmp sin `cm2.inicio` no puede dar
     otro), o `aplazado` si hubiera un AURA principal vivo.
5. Observar el primer ciclo real **ese mismo dia**, despues de las 23:45, con el §7.3. Un `error` cierra el dia sin reintento.
6. **Reversion no destructiva:** restaurar el `.bak`. El audit es append-only y medir es idempotente, asi que un ciclo
   perdido solo retrasa sondas dentro de la tolerancia.
7. **Orden:** migrar **antes** de mover o eliminar el worktree; nunca despues.

> **Ampliación 2026-10-25 (u). No ejecutada.** El worktree `m3-entry` no lo usa solo el cron de CM2. Lo usan **tres**
> procesos de producción `[EJEC]`:
> 1. `~/.local/bin/aura-medir-cm2.sh`, en la línea `WS=`;
> 2. el despertador de AURORA (`crontab`, `*/30`, `entorno/scripts/despertar-aura.sh`);
> 3. el servicio `aura-receptor-nodos.service`, en su `WorkingDirectory=`. Este proceso tiene la credencial real del
>    receptor.
>
> Los tres ejecutan código del worktree, que tiene cambios sin confirmar, y ese código cambia en caliente con cada
> edición. También durante una batería de mutación, que muta en el sitio: un reinicio del servicio
> (`Restart=always`) en ese intervalo cargaría código mutado.
>
> Propuesta, que requiere autorización: instalar una copia congelada de un commit revisado (`git archive`) en una ruta
> propia y sin permisos de grupo, y apuntar ahí los tres procesos. El orden y la reversión son los del §7.6.
> **[CORREGIDO 2026-10-25 (v)]**
> - **No sirve para los tres procesos.** El despertador guarda `eventos.jsonl`, `estado.json` y **PARADA** junto a
>   su código (`aura._base()`); moverlo bifurcaría el historial y desconectaría PARADA.
> - **`git archive HEAD` no sirve tal cual:** `core/reloj_cm2.py` no tiene seguimiento.
> - La propuesta vigente, con sus alternativas, está en `milestones/m3-entry/PROPUESTA-AISLAMIENTO-PROCESOS-PRODUCCION.md`.
