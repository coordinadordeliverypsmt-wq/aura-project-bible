---
documento: "PROMPT 02 — Inventario de verificadores sin raíz (Fase A) y matriz de confinamiento Landlock por contrato (Fase B)"
fecha: 2026-10-23
evidencia: "[EJEC] búsqueda AST de todo el repo; experimentos Landlock en directorios temporales (nunca sobre el repo)"
relacionado: "DP-CANDIDATO-AISLADO-AUTOCONSTRUCCION.md §11"
---

# Inventario de verificadores sin raíz y matriz Landlock

## A. Verificadores que llegan a `autoconstruccion.ejecutar` sin aceptar la raíz

**Método:** AST sobre todos los `*.py` del repo. Se buscaron llamadas a `ejecutar`, `ciclo`, `ejecutar_bajo_review`,
`trabajar` y `ciclo_autonomo` con `verificacion=` o con argumento posicional, resolviendo por AST las funciones con
nombre. Resultado: 183 llamadas con `verificacion=`, de las que 38 ya reciben la raíz. Los `ejecutar(` de
walking-skeleton son otro método (`motor.ejecutar`).

| Fichero (`entorno/control-plane/`) | Sin raíz | En alcance autorizado |
|---|---:|---|
| test_red_motor_autonomia.py | 16 | no |
| test_red_ciclo_autonomo.py | 13 | no |
| test_red_autoconstruccion.py | 7 | no |
| test_red_blindaje_del_anillo.py | 7 | no |
| test_red_segunda_barrera.py | 6 | no |
| test_red_blindaje_del_mecanismo.py | 4 | no |
| test_red_presupuesto_de_tarea.py | 4 | no |
| test_red_review_enchufado.py | 4 | no |
| test_red_aislamiento_del_sandbox.py | 3 | no |
| test_red_codigo_muerto_completo.py | 2 | no |
| test_red_review.py | 2 | no |
| test_red_vocabulario_constructivo.py | 2 | no |
| test_red_ejecucion_completa.py | 1 (helper `_ejecutar`) | no |
| test_red_tarea_atada_a_su_contrato.py | 1 (helper `_ejecutar`) | no |
| **Subtotal a migrar** | **72** | 14 ficheros fuera de alcance |
| test_red_candidato_aislado.py | 3 | sí: **controles deliberados**, no se migran |
| `milestones/m3-entry/evidencia-candidato-aislado-2026-10-22/exp_candidato_en_arbol_vivo.py` | 2 | evidencia histórica, no se migra |

- Los 72 son constantes (`lambda: True/False`) o funciones sin lectura del árbol: `revienta` lanza,
  `con_intervencion` actúa sobre `tmp_path` y `_agotar` devuelve False.
- La migración a `lambda raiz: …` es **mecánica**.
- **Ningún verificador de producción llega sin raíz:** `aura.py:76` pasa `None`, y `review.py` construye el suyo con
  la raíz.
- Convertir el uso sin raíz en error explícito exige migrar antes los 72. Eso requiere **ampliar la autorización** a
  esos 14 ficheros de prueba.

## A.2 Defecto descubierto en la vía de producción (alto)

- Los dos contratos reales (`milestones/m3-entry/capacidades/sexta-fuente-estancamiento.toml` L48 y
  `etiqueta-observatorio-efecto.toml` L84-86) declaran `pruebas_minimas` con **rutas absolutas al árbol vivo**.
- Con `raiz=copia`, pytest recoge el test del vivo y **carga los módulos del vivo**. Medido `[EJEC]`:
  `MODULO_CARGADO …/vivo/estancamiento.py`.
- La vía de producción declaraba `verificacion_aislada=True` mientras verificaba el original.
- Se corrige en la Fase A remapeando las pruebas a la copia en `review.py`, que está dentro del alcance.

## B. Matriz de confinamiento Landlock (evaluación `[EJEC]` en un directorio temporal)

- `aislamiento.abi_disponible()` = **6**; `descripcion()` = `landlock:abi6+rlimits`.
- Se puede confinar **sin modificar** `verificador.py` ni `aislamiento.py`:
  `vf.ejecutar_pruebas(pruebas, raiz, confinar=ais.preparar(raiz))`.

| Prueba | Resultado |
|---|---|
| Escribir un señuelo fuera de la copia | `PermissionError`; sha del señuelo igual antes y después (`9ecf645a1f49`) |
| Hijo y **nieto** (subprocess desde el confinado) escriben el señuelo | `PermissionError`; sha igual: **el confinamiento se hereda** |
| Leer fuera (`~/.aura`, `~/.cache`, `walking-skeleton`, un secreto) | `PermissionError` (la lectura queda confinada a la copia + `rutas_del_interprete()`) |
| `etiqueta-observatorio-efecto`, confinado sobre la copia | 59 ejecutadas, sano |
| `sexta-fuente-estancamiento`, confinado sobre la copia | sano **solo si `eventos.jsonl` está en la copia**; sin él falla igual sin Landlock (falso rechazo previo) |
| Landlock no disponible (ABI 0 forzado) | `preparar` **no falla cerrado**: solo aplica rlimits y la escritura externa ocurre. Hay que exigir `abi > 0` para declarar `ejecucion_confinada: True` y rechazar si no |
| Fallo real al aplicar reglas | excepción en `preexec_fn` → `SubprocessError` → `arbol_sano` False (cierra) |

**Riesgos:**
- rutas absolutas en los contratos (resuelto en la Fase A);
- `eventos.jsonl` ausente de la copia;
- `/tmp` no escribible hace que `pytest` cree `pytest-of-<user>/` dentro de la copia (inocuo);
- `crontab` sin ejercitar.

La matriz se acredita con solo dos contratos.

## C. Estado final (2026-10-25)

- A: 72/72 migrados; la vía sin raíz es un error explícito; residuos por AST = 3 controles deliberados + 2 líneas de
  evidencia histórica.
- B: el modo estricto deniega la lectura fuera de la allowlist mínima, la escritura fuera de la copia, **toda** la red
  (seccomp `socket()`), IPC, keyring, metadatos, xattr, inotify, prlimit/sched sobre otros procesos y señales externas.
  Se hereda a hijos y nietos. Seguridad APTO. La medición original de esta matriz (§B) queda como historia; los
  límites vigentes están en el docstring de `aislamiento.py`.
- Verificación posterior (2026-10-25, AST): 70 lambdas con raíz + 2 funciones con raíz = 72; 0 sin raíz en los 14
  ficheros.
