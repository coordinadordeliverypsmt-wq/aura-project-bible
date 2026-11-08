---
documento: "Propuesta — aislar los procesos de producción del worktree de desarrollo"
fecha: 2026-10-25
estado: "A IMPLEMENTADA EN EL ARNÉS (2026-10-25 (w)); B, C, D y E: PROPUESTA, NO ejecutada, requieren autorización expresa del CEO"
evidencia: "[EJEC] solo lectura (systemctl, journalctl, crontab, /proc, git status, sha256/mtime); mutación sobre copia"
relacionado: "CHECKPOINT (u) y (v); PROCEDIMIENTO-INICIO-CM2.md §7.6 y su ampliación (u)"
---

# Aislar los procesos de producción del worktree de desarrollo

## 1. Hechos medidos `[EJEC]`

| Proceso | Cómo arranca | Código que ejecuta |
|---|---|---|
| Medición CM2 | crontab de 21:30 a 23:40 → `~/.local/bin/aura-medir-cm2.sh` | `WS=…/worktrees/m3-entry/walking-skeleton`; `python3 -m aura_skeleton --medir-cm2` |
| Despertador de AURORA | crontab `*/30` → `entorno/scripts/despertar-aura.sh` (0775) | `exec python3 despertador.py`, que importa `aura`, `control_plane` y `orquestador` **antes** de comprobar PARADA y luego escribe en el `eventos.jsonl` real |
| `aura-receptor-nodos.service` | systemd de usuario, `Restart=always` (3 s) | `WorkingDirectory=…/m3-entry/walking-skeleton`; `python3 -m aura_skeleton --receptor-nodos`. Usa la **credencial y la PKI reales** |

- **El receptor** (PID 972) arrancó el 2026-10-25 a las 07:51:24, con el reinicio del equipo; `NRestarts=0`.
  - Carga **67** módulos de `aura_skeleton`: 10 sin seguimiento y 24 modificados respecto a HEAD.
  - Dos de ellos, `composicion.py` y `core/ejecutor_modelo_usuario.py`, **fueron mutados en el sitio hoy** por la
    batería `cm2-cableado-produccion` (mtime 13:38 y 13:43; contenido restaurado con el mismo sha).
  - Un reinicio durante esa ventana habría cargado código mutado. **No hubo reinicio.**
- **El despertador:** hay 32 mutantes, en 6 baterías del control-plane, sobre módulos que importa
  (`blindaje-del-mecanismo` 9, `eventos-de-autoridad` 8, `observar-git` 5, `kill-switch-cableado` 4,
  `presupuesto-y-perimetro` 3, `barreras-de-gobernanza` 3).
- **Sin daño observable:**
  - la cadena de hash de `eventos.jsonl` está íntegra (3684 eventos, verificada sobre una copia);
  - los 36 eventos de hoy son todos `despertar_rechazado`, con una única forma de `datos`, uno por franja.
- **Los datos del despertador viven JUNTO al código, por diseño** (`aura._base()` = `Path(__file__).parent`,
  `aura.py:64-68`: «la zona de escritura no es algo que deba decidir quien invoca»). `eventos.jsonl`, `estado.json` y
  **PARADA** están en `entorno/control-plane/` del worktree.
  - Ejecutarlo desde otra ruta **bifurcaría el historial** y **desconectaría PARADA**: el
    `touch …/m3-entry/entorno/control-plane/PARADA` documentado dejaría de pararlo.
  - CM2 y el receptor, en cambio, tienen los datos fuera del código: `~/.aura` y `AURA_RED=~/.aura-red`.
- **`git archive HEAD` no sirve tal cual:** `core/reloj_cm2.py` **no tiene seguimiento**, así que una copia de HEAD
  dejaría CM2 sin módulo, y el receptor ejecutaría código distinto del actual.
- **Si el worktree se mueve o se elimina:**
  - el servicio falla en bucle (`Restart=always`), sin fuga;
  - el despertador falla cada 30 minutos;
  - CM2 registra `error`, que cierra el día sin reintento. Tras 7 días, las sondas de día 28 quedan tardías.

## 2. Alternativas

| | Qué es | Protege de la mutación | Protege de las ediciones en curso | Requiere | Riesgo |
|---|---|---|---|---|---|
| **A. Mutar siempre sobre una copia** | Copiar el árbol a un tmp y ejecutar `python3 -m herramientas.mutar <toml> --raiz .` **dentro de la copia** | **Sí**, por completo | No | Cambiar la regla de `CLAUDE.md` §2 (gobierno) | Ninguno técnico. **Validado:** el mismo 4/4, y el árbol vivo conserva sha y mtime |
| **B. Instantánea del árbol revisado, SOLO para CM2 y el receptor** | Volcar por lista blanca (`aura_skeleton/`) a `~/.local/share/aura/runtime/<fecha>-<sha corto>/`, inmutable (`a-w`) y con manifiesto de sha; apuntar **CM2 y el receptor** a esa ruta concreta, sin enlace `actual`. **El despertador NO**: sus datos y PARADA van con el código | Sí | Sí | Cambiar `WS=`, el unit y `daemon-reload`; **reiniciar el receptor** | Sin procedencia git; el manifiesto la sustituye |
| **C. Commit y despliegue fijo** | Confirmar el trabajo y desplegar un commit revisado (`git worktree add --detach` o `git archive <commit>`) | Sí | Sí | Commit o merge de 408 entradas: decisión de integración | El mejor a largo plazo; es el paso de gobierno más grande |
| **E. Despertador: separar datos y código** | Que el plano de control acepte un directorio de datos fijo, distinto del código, con PARADA en él. Es lo único que permitiría congelar también el despertador | Sí | Sí | **Decisión de arquitectura**: contradice el diseño actual de `aura._base()` y toca el kill switch | Alto si se hace mal: PARADA es la barrera fuera de banda |
| **D. Cerrojo cooperativo** (OB-5) | El arnés publica un cerrojo; el despertador y el receptor no arrancan ni recargan mientras exista | Parcial | No | Cambiar código de producción (`despertador.py`, `__main__.py`) | No cubre las ediciones; añade acoplamiento |


**Condiciones de A** (revisión de seguridad (v)):

- **`--raiz` según el tipo de batería** (A1):
  - las de `walking-skeleton/mutaciones/` usan `--raiz <copia>/walking-skeleton`;
  - las de `entorno/control-plane/mutaciones/` usan `--raiz <copia>/entorno/control-plane`.
  Con la raíz equivocada el arnés devuelve base roja o `NO_APLICADO`; nunca muta el árbol vivo.
- **Dónde y qué copiar** (A2-A4):
  - la copia va en un `mktemp -d` **fuera** del worktree, con permisos 700;
  - incluye la raíz del repo, porque varias pruebas del control-plane la esperan;
  - **sin** `PARADA` ni `.mutar-en-curso.json`;
  - con la base verificada en verde. El arnés ya sale con 1 si no lo está.
- **Regla horaria** (O3): fuera de las 21:25 a 23:50. Los `python -m aura_skeleton` de las pruebas cuentan como
  «AURA viva» y consumen los intentos de CM2.

## 3. Recomendación

1. **Ya: A.** Es la única que no cambia nada en producción.
   - Requiere que el CEO apruebe incorporar a `CLAUDE.md` §2: «la mutación se ejecuta sobre una copia exportada con
     `--raiz`».
   - Hasta entonces, esta sesión la aplica a **sus propias** baterías.
2. **A continuación: B,** con autorización, solo para CM2 y el receptor, para cortar su dependencia del worktree sin
   forzar el commit.
   - El despertador **sigue en el worktree**: es el plano de desarrollo por diseño.
   - Su exposición a la mutación la elimina A.
   - Sacarlo del worktree exige E, que es una decisión de arquitectura.
3. **Al integrar `m3-entry`: C,** que sustituye a B.

## 4. Pasos de B (para cuando se autorice). Reversibles

Corregidos según la revisión de seguridad (v).

1. **Precondiciones:**
   - **No** entre las 21:25 y las 23:50, ni a :00 o :30 ±2 minutos.
   - **Tampoco** mientras corra una mutación, porque el script de CM2 la vería como «AURA viva».
   - Elegir una ventana sin nodos críticos: el reinicio interrumpe los latidos.
2. **Volcado por lista blanca, no el árbol** (B4):
   - Volcar solo `walking-skeleton/aura_skeleton/` y `walking-skeleton/pyproject.toml`, hacia
     `~/.local/share/aura/runtime/<fecha>-<sha corto>/`.
   - **Nunca** `entorno/control-plane` (sus datos y PARADA), `.git` ni `.claude`.
3. **Validar el propio volcado, no el árbol vivo** (B5):
   - generar un manifiesto `sha256sum`, sin `.pyc`;
   - pasar las pruebas de CM2 y de nodos **sobre el volcado**;
   - comprobar que el sha del volcado coincide con el medido.
4. **Inmutable** (B3): `chmod -R a-w` sobre el release, ficheros **y** directorios, y `PYTHONDONTWRITEBYTECODE=1` en
   el unit y en el script. `go-w` no basta: el propio usuario es quien muta, edita y autoconstruye.
5. **Ensayo en seco sin nada real** (B1):
   - `--nodos` y `--receptor-nodos` con `AURA_RED=<tmp>`, no vacío y distinto del real, **y** `AURA_RED_URL` hacia un
     puerto libre sin servicio, o hacia un `nats-server` propio en un puerto aleatorio. Sin esto, el receptor
     intentaría autenticarse contra el **bus real** de 127.0.0.1:4222.
   - **Nunca** copiar `receptor.credencial` ni `pki/` reales al tmp.
   - CM2 con los ganchos `AURA_CM2_PRUEBAS=1` y `AURA_DATOS` y `HOME` de tmp (§7.6, paso 4).
6. **Cambio, con copia de seguridad previa** (`crontab -l > …bak`, `cp -n` del unit y del script):
   - `WS=` del script de CM2 y `WorkingDirectory=` del unit apuntan a la **ruta concreta del release**, inmutable. Así
     no hay enlace `actual` y no hay carrera con `ln -sfn`, que no es atómico (B2).
   - El script se escribe de forma atómica (temporal y `mv -T`).
   - Después, `systemctl --user daemon-reload` y un reinicio del receptor.
   - Opcional (B7): endurecer el unit con `NoNewPrivileges`, `PrivateTmp` y `ReadOnlyPaths=<release>`.
7. **Verificación:**
   - el `cwd` del nuevo PID del receptor es el release, y el manifiesto se verifica en el arranque, por ejemplo con
     `ExecStartPre`;
   - `NRestarts` y el journal no muestran errores;
   - el despertador sigue sin cambios: con PARADA armada, en el siguiente :00 o :30 registra `despertar_rechazado`
     y la cadena sigue íntegra;
   - CM2 esa misma noche con §7.3. **Es el único paso que lee datos reales (`~/.aura`), y lo hace a propósito.**
8. **Reversión:** restaurar las copias de seguridad, `daemon-reload` y reiniciar el receptor.
   - El audit es append-only y la medición de CM2 es idempotente, así que solo se pierde, como mucho, un ciclo.
   - Un día que acabe en `error` no se recupera.
   - **No borrar un release mientras algún PID tenga su `cwd` en él** (B8): hay imports perezosos.

## 5. Autorizaciones exactas necesarias

- **A:** «añadir a `CLAUDE.md` §2 que la mutación se ejecuta sobre una copia con `--raiz`».
- **B:** «volcar el árbol revisado a `~/.local/share/aura/runtime/` y apuntar ahí `aura-medir-cm2.sh` y
  `aura-receptor-nodos.service`, incluido el reinicio del receptor». El crontab del despertador no se toca.
- **E:** la decisión de arquitectura sobre separar los datos y PARADA del código del plano de control.
- **C:** la decisión de integración de `m3-entry`, que es commit o merge y es del CEO.

## 6. Riesgos que añadió la revisión de seguridad (v)

- **O1, ALTO: hasta que se apruebe A, las baterías siguen mutando en el sitio** módulos que el despertador importa.
  - La barrera de hoy es de proceso, no de integridad: `mutacion_en_curso()` (`orquestador.py:383`, que barre
    `/proc`) se comprueba **después** de los imports (`despertador.py:65-67`).
  - Con un SIGKILL, el árbol queda mutado sin ningún arnés vivo. El siguiente :00 o :30 importaría código mutado.
  - **PARADA está armada desde el 8 de septiembre**: es lo que lo impide hoy, y por eso los 36 eventos de hoy son
    `despertar_rechazado: kill switch activado`.
  - Recomendación: mantener PARADA mientras se mute en el sitio, y que el despertador consulte también el diario
    `.mutar-en-curso.json`. Lo segundo cambia código de producción y requiere autorización.
- **O2, MEDIO:** la autoconstrucción de AURORA modifica código del mismo worktree. Hoy no ocurre porque PARADA está
  armada. B protege CM2 y el receptor de esto.
- **O5, BAJO:** la verificación de la cadena se hizo sobre una copia en un instante dado: 3684 eventos y sha
  `917394199ab33c8f`, ambos iguales al original en ese momento.

## 7. Estado de A: implementada en el propio arnés (2026-10-25 (w))

- **A no necesitaba cambiar `CLAUDE.md`.** Se implementó dentro de `walking-skeleton/herramientas/mutar.py` (regla 6),
  así que el comando de §2 sigue siendo el mismo. `ejecutar()` copia el repositorio a `/tmp/aura-mutar-*` (0700),
  ejecuta allí la base y los mutantes, y borra la copia al terminar.
  - Un `fichero` que saldría de la copia se rechaza con `AMBIGUO`.
  - Las copias huérfanas tras un SIGKILL se retiran al arrancar, solo si su dueño ha muerto.
  - Ya no se escribe diario.
- **Evidencia:** `milestones/m3-entry/evidencia-cm2-s3-2026-10-25/arnes-copia-aislada/`.
- **Condiciones A1-A3 de la revisión (v), ya resueltas por el propio arnés:**
  - se copia el repositorio entero, sin `.git`, así que `--raiz` funciona igual en las dos clases de batería;
  - la copia va fuera del proyecto, y se rechaza si no;
  - la base se verifica en la copia.
- **Siguen sin resolver: B, C, D, E y O1.** O1 deja de aplicar a las baterías que corren con este arnés. Persiste para
  otros mutadores en el sitio y para la autoconstrucción de AURORA.
