# Perfil de hardware de AURA — 2026-09-06

Documento **técnico y descriptivo**. No modifica arquitectura, gobernanza ni autoridad.
Todo lo que sigue está medido en este equipo, no estimado, salvo donde se marque `[INFER]`.

---

## 1 · CPU

| | |
|---|---|
| Modelo | Intel Celeron **N4020** @ 1,10 GHz (turbo 2,80) |
| Núcleos / hilos | **2 / 2** — sin SMT |
| Caché | L1d 48 KiB · L1i 64 KiB · **L2 4 MiB · sin L3** |
| SIMD | `mmx sse sse2 sse4_1 sse4_2` |
| SIMD **ausente** | **AVX · AVX2 · AVX-512 · FMA · F16C · VNNI · AMX** |

La ausencia de AVX2 es la restricción **dominante** del equipo, no un detalle de ficha. Se mide
directamente: en inferencia local, el *prefill* (3,3 tok/s) y la generación (2,68 tok/s) son casi
idénticos, cuando en hardware con AVX2 el primero es de 10 a 50 veces más rápido. No hay unidades
vectoriales que explotar, así que el cuello es **cómputo escalar**, no ancho de banda.

## 2 · RAM

| | |
|---|---|
| Física total | **3,6 GiB** (3.719 MB) |
| Disponible observado | **855 MB – 1,79 GB** según carga de escritorio |
| Consumidores habituales | Firefox ~950 MB · sesiones de Claude ~400-550 MB |
| Presión acumulada (PSI) | `some total = 111,7 s` · `full total = 72,3 s` |

`full` significa **todo el sistema detenido** esperando memoria: 72 segundos acumulados. En una sola
sesión de trabajo hubo **seis ejecuciones abortadas** por presión de memoria (suites de prueba e
inferencias), ninguna por el OOM killer del kernel.

## 3 · zRAM

**No existe. Preparada, no aplicada** — su activación exige `sudo`, que esta sesión no posee.

El módulo `zram.ko` **ya está en el kernel** de Linux Mint 22.3: no hay que instalar ningún paquete.
La unidad `entorno/hardware/zram-aura.service` deja configurados 1,5 GB con `lz4` y **prioridad 100**,
por delante del `/swapfile` (prioridad −2), que **no se toca ni se desactiva**.

Prioridad resultante prevista: **RAM física → zRAM → swap eMMC**.

## 4 · Swap

`/swapfile`, **4 GB en el eMMC**, prioridad −2, con **1,8 GB en uso** en reposo.

Su coste está medido, y es el argumento contra apoyarse en él: el eMMC lee a **220 MB/s en
secuencial** pero solo a **18,9 MB/s en aleatorio de 4 K**, que es el patrón real de la paginación.
Frente a los ~1,06 GB/s de ancho de banda efectivo en RAM, el swap es **56 veces más lento**.
Ampliarlo no compra rendimiento: compra la ilusión de que algo cabe.

## 5 · eMMC

`mmcblk0`, 58,2 GiB. Raíz `mmcblk0p2` ext4 con **5,8 GB libres (90 % ocupado)**.
Sin disco rotacional, pero **no es un SSD**: los tiempos de acceso aleatorio son los de arriba.

## 6 · USB — inventario y veredicto

| Disp. | Capacidad | FS | Etiqueta | Modelo | Estado |
|---|---|---|---|---|---|
| `sda` | 3,8 G | vfat | (ninguna) | Generic Flash-Disk | **DEFECTUOSA — corrompe datos** |
| `sdb` | 3,6 G | ext4 | `AURORA_BAK` | Generic Flash Disk | Respaldo del CEO — **no se toca** |
| `sdc` | 7,5 G | ext4 | `AURORA_EXT` | TDK LoR **TF10** | **DEFECTUOSA conocida (D31)** |

**`AURA_AUX` no se ha creado.** La única candidata libre (`sda`) **falló la prueba de integridad**:

```
10 MB   escrito db209500f530434c  releído 92b87b46e18abd88  FALLO
100 MB  escrito 6b805bf08aa6423c  releído bec898620b9617e8  FALLO
400 MB  escrito fd3425f47b3cfa99  releído 55ab413a4d2042fb  FALLO
```

El método está validado con dos controles, porque acusar a un medio es serio:
1. **eMMC con el mismo método → OK**, así que el procedimiento es correcto.
2. **Lectura sin `iflag=direct`, tras desmontar y remontar** (caché fría real) → **también falla**,
   así que no es un artefacto de `direct` sobre vfat.

Es **peor** que la TF10 de D31, que corrompía a partir de ~400 MB: esta falla ya a 10 MB. Velocidad
secuencial medida: 13,3 MB/s. **No se formateó, no se reparó, no se etiquetó, no se escribió más.**

## 7 · Limitaciones reales

1. **Sin AVX2**: toda carga vectorial —inferencia local, sobre todo— corre en el peor camino.
2. **Dos núcleos**: no hay paralelismo real; la suite de pruebas del producto no cabe en un proceso.
3. **3,6 GiB de RAM**: el margen operativo son ~1 GB, y compite con el escritorio.
4. **Almacenamiento aleatorio lento**: el swap es una red de seguridad cara, no una extensión.
5. **Disco al 90 %**: 5,8 GB libres limitan cualquier descarga o artefacto grande.
6. **Sin USB auxiliar fiable**: las tres memorias conectadas están descartadas o reservadas.

## 8 · Lo que este equipo sostiene razonablemente

El **plano de desarrollo de AURA al completo**: descubrimiento, planificación, revisión determinista,
ejecución de tareas técnicas reversibles, y su suite de 814 pruebas en un solo proceso (~36 s). El
ciclo autónomo cada 30 minutos con holgura. Git, y la publicación a GitHub. El archivo en Drive por
GVFS nativo. Inferencia local **de laboratorio**, medida y acotada, nunca en el ciclo.

## 9 · Lo que exige hardware superior

Un `RevisorLocal` por LLM en operación. La suite del producto en un único proceso. Cualquier modelo
por encima de ~1 B. Y trabajar con el navegador abierto mientras algo de eso ocurre.

El umbral mínimo, en **propiedades** y no en productos: **AVX2 como mínimo**, **16 GB de RAM** (8
como suelo absoluto) para que el modelo resida sin tocar swap jamás, **4 núcleos físicos**, **SSD**
en lugar de eMMC, y refrigeración capaz de sostener el turbo.

## 10 · La espiral, y sus fronteras

```
RAM física  →  zRAM  →  swap eMMC  →  [USB AUX: NO DISPONIBLE]  →  Cloud
   runtime      margen     último       ninguna memoria fiable      archivo
   crítico    comprimido   recurso                                  y versionado
```

Cuatro afirmaciones que este perfil deja explícitas:

- **USB ≠ RAM física.** Una memoria externa no amplía memoria: en el mejor caso amplía
  almacenamiento, y hoy **ninguna de las tres conectadas es fiable para eso**.
- **zRAM mejora el margen, no la RAM.** Comprime lo que ya está en memoria; no añade ni un byte
  físico. Ayuda a evitar el swap en eMMC, que es donde está el coste real.
- **AURA mantiene su runtime crítico en local.** `estado.json`, `eventos.jsonl` y el ciclo viven en
  el disco de la máquina y no se archivan ni se versionan.
- **Drive es archivo, GitHub es versionado.** Ninguno de los dos es runtime, y ninguno sustituye al
  disco local. Ollama y sus modelos permanecen locales.

---

**Medido el 2026-09-06.** Sin conectar Ollama, sin ejecutar ciclos autónomos, sin operaciones
destructivas y sin tocar gobernanza, arquitectura ni autoridad.
