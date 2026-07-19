# Fase 2 — Migración definitiva de Ollama al USB

Fecha: 2026-07-19. Verificación en vivo (D27).

## Estado final de la migración

`/usr/share/ollama/.ollama/models` es un **enlace simbólico** a
`/media/majo1230/AURORA_EXT/ollama_models` (creado 15:52). Los modelos residen en una
**única copia física en el USB** (`/dev/sda1`). No hay duplicados en el disco interno.

| Elemento | Ruta | Dispositivo real |
|---|---|---|
| Modelos (única copia) | `/media/majo1230/AURORA_EXT/ollama_models` | `/dev/sda1` (USB) |
| Store interno | `/usr/share/ollama/.ollama/models` → symlink | `/dev/sda1` (USB) |
| `OLLAMA_MODELS` del proceso | `/media/majo1230/AURORA_EXT/ollama_models` | `/dev/sda1` (USB) |
| Store por defecto del usuario | `~/.ollama` (20 K, vacío) | interno |

Modelo disponible: `qwen2.5:3b` (1.929.912.432 bytes, Q4_K_M, 3.1B, ctx 32768).

## Acciones ejecutadas

- Eliminados **17 archivos `-partial`** de un `ollama pull` interrumpido (15:39–15:48).
  Artefactos regenerables; el blob completo y el manifest quedaron intactos y Ollama
  lista el modelo correctamente tras la limpieza. USB: 375 M → 1,1 G libres.
- Revertido el montaje duplicado de `/dev/sda1` que había introducido (`AURORA_EXT1`).
- Ollama reiniciado **a través del guardarraíl** `entorno/scripts/ollama-usb.sh`, que
  validó por dispositivo antes de arrancar: `Guardarrail OK: modelos en /dev/sda1`.

## Corrección al registro

En un informe previo declaré "integridad COMPLETA" tras comparar tamaños entre
`/usr/share/ollama/.ollama/models` y el USB. **Esa comparación no era válida**: al ser el
origen un symlink al destino, se compararon los archivos consigo mismos. La verificación
con valor real es la **funcional** (carga del modelo desde el USB e inferencia), no aquella.

## Espacio

- Interno: **5,6 G libres** (desde 889 M al inicio de la jornada).
- USB: 1,1 G libres — 4,1 G corresponden a `swapfile_aurora`, 2,5 G a los modelos.

## Consumo principal de almacenamiento (D29)

`/timeshift` ocupa **26 G** en el disco interno (5 snapshots: 2026-07-10, 07-11, 07-16,
07-17, 07-18). Es el mayor consumidor con diferencia. **No se toca**: son respaldos del
sistema, no artefactos regenerables. Se documenta como riesgo/decisión abierta del CEO.

## Pendiente (requiere root)

- `sudo systemctl disable ollama` — el servicio systemd sigue **enabled** (aunque inactive).
  Con el symlink en su sitio usaría igualmente el USB, por lo que **no es un riesgo de
  escritura en interno**; es higiene de instalación obsoleta.

## Prueba funcional (evidencia decisiva)

Inferencia real ejecutada con el modelo servido desde el USB:

| Métrica | Valor |
|---|---|
| Respuesta | `OPERATIVO` (correcta) |
| `total_duration` | **250.475 ms** |
| `load_duration` (carga del modelo desde USB) | **150.466 ms** |
| `eval_duration` (4 tokens) | **34.952 ms** → **8.738 ms/token** |
| Objetivo HC-1 | 1.200 ms |

**Lectura arquitectónica:** la migración es correcta por política, pero **no podía mejorar la
latencia y de hecho empeora la carga**. `load_duration` es lectura de 1,9 GB desde un USB, más
lento que el eMMC interno. Y `eval_duration` (8,7 s por token) es cómputo puro: depende de CPU/RAM,
**no de dónde residan los archivos**. Con 2 núcleos, 3,6 GB de RAM y sin GPU, un modelo de 3.1B
parámetros no puede acercarse a HC-1 en esta máquina.

**Veredicto Fase 2: PASS.**

## Corrección de un fallo del propio Preflight

La versión inicial marcaba `/usr/share/ollama` como "instalación obsoleta" por su mera existencia,
y proponía `sudo rm -rf`. Tras la migración ese directorio contiene el **symlink al USB**: ejecutar
ese remedio **habría destruido la configuración correcta**. Corregido para comprobar el
**dispositivo** que respalda el store y reconocer el symlink como estado válido.
