# Inventario de migración — Fase 1 — 2026-07-19

Generado por verificación en vivo. **Ningún archivo fue eliminado ni movido.**

## A. Store real de Ollama (ORIGEN de la migración)

Ruta: `/usr/share/ollama/.ollama/models` — dispositivo `/dev/mmcblk1p2` (INTERNO)
Modelo: `qwen2.5:3b` — total 1,8 G — propietario `ollama:ollama`

| Blob (nombre = sha256, verificable tras copiar) | Tamaño |
|---|---|
| `sha256-161ddde4c9cd07c9f1ccb4e0167c434bce72caeb3fc1844262fa66bc877b0426` | 4,0K |
| `sha256-5ee4f07cdb9beadbbb293e85803c569b01bd37ed059d2715faa7bb405f31caa6` | 1,8G |
| `sha256-66b9ea09bd5b7099cbb4fc820f31b575c0366fa439b08245566692c6784e281e` | 4,0K |
| `sha256-b5c0e5cf74cf51af1ecbc4af597cfcd13fd9925611838884a681070838a14a50` | 8,0K |
| `sha256-eb4402837c7829a690fa845de4d7f3fd842c2adee476d5341da8a46ea9255175` | 4,0K |

Manifests:
- `/usr/share/ollama/.ollama/models/manifests/registry.ollama.ai/library/qwen2.5/3b`

## B. Destino

Ruta: `/media/majo1230/AURORA_EXT/ollama_models` — dispositivo `/dev/sda1` (USB) — **vacío**, propietario `majo1230:majo1230`

Espacio USB: 2,9G libres — suficiente para 1,8 G.

## C. Copias adicionales detectadas (NO eliminar sin decisión expresa)

- `/timeshift/snapshots/2026-07-18_20-00-02/localhost/usr/share/ollama/.ollama/models/` — copia dentro de un **snapshot de Timeshift**. Es un respaldo del sistema: **no es un duplicado regenerable**, eliminarlo degrada la capacidad de restauración. Requiere decisión del CEO.
- Directorio **enmascarado** bajo el punto de montaje `/media/majo1230/AURORA_EXT`: contenía 1,8 G medidos a las 15:05. **No verificable sin root.**

## D. Estado del entorno al cierre de Fase 1

```
/dev/mmcblk1p2    57G    50G  3,8G  93% /
/dev/sda1        7,3G   4,1G  2,9G  59% /media/majo1230/AURORA_EXT
```

- Ollama: PID 19688, `OLLAMA_MODELS=/media/majo1230/AURORA_EXT/ollama_models` (ruta **sí** en el USB), responde `{"models":[]}`.
- USB montado una sola vez en la ruta oficial (revertido el montaje duplicado que introduje).

## E. Censo del disco interno (completado tras el cierre de Fase 1)

| Directorio | Tamaño |
|---|---|
| `/timeshift` (5 snapshots) | **26 G** |
| `/usr` | 13 G |
| `/home` | 4,4 G |
| `/var` | 861 M |
| `/opt` | 416 M |
| **Total `du`** | **48 G** |

Snapshots: 2026-07-10, 07-11, 07-16, 07-17, 07-18.

**Consecuencia para la planificación:** la migración completa de Ollama recupera ~3,6 G. Timeshift
ocupa **26 G**, siete veces más. La migración sigue siendo correcta por política (los modelos no
deben residir en interno), pero **no es la palanca principal de espacio**.

**Evidencia del directorio enmascarado:** `df` reporta 50 G usados; `du -x` suma 48 G. La diferencia
de ~2 G es coherente con ~1,8 G de archivos ocultos bajo el punto de montaje, que `df` contabiliza
y `du` no puede alcanzar. Es evidencia indirecta consistente, **no** una verificación directa.

**Blob principal:** `sha256-5ee4f07c…` = 1.929.903.008 bytes (`qwen2.5:3b`).

> Timeshift NO entra en ninguna política de borrado automático. Son respaldos del sistema:
> su eliminación es una decisión exclusiva del CEO.
