# Informe de Administración de Almacenamiento — 2026-07-19

> Verificación ejecutada **en el momento de generar este informe** (D-Entorno: prohibido reportar estados históricos).
> Estado: **MIGRACIÓN INCOMPLETA — BLOQUEADA POR FALTA DE PRIVILEGIOS ROOT.**

## 1. Hallazgo principal (causa raíz del disco lleno)

El disco interno se llenó por una **suposición silenciosa**: Ollama fue configurado con
`OLLAMA_MODELS=/media/majo1230/AURORA_EXT/ollama_models`, pero **el USB nunca estaba montado**
en esa ruta. Linux no falla en ese caso: escribe en el directorio local. Los **1,8 GB** de modelos
quedaron en el **disco interno**, no en el USB.

Existe además una **segunda copia de 1,8 GB** en `/usr/share/ollama` (instalación systemd previa,
servicio `inactive`). En total ~3,6 GB de modelos duplicados en almacenamiento interno.

## 2. Rutas reales verificadas

| Recurso | Ruta real | Disco | Estado |
|---|---|---|---|
| Binario Ollama | `/usr/local/bin/ollama` | Interno | root:root |
| Modelos Ollama (activos) | `/media/majo1230/AURORA_EXT/ollama_models` (1,8 G) | **Interno** | mal ubicado |
| Modelos Ollama (obsoletos) | `/usr/share/ollama` (1,8 G) | Interno | duplicado, root:root |
| Proceso Ollama | PID usuario `majo1230`, no systemd | — | operativo :11434 |
| Faster-Whisper | — | — | Traceback (most recent call last):
  File "<string>", line 1, in <module>
ModuleNotFoundError: No module named 'faster_whisper'
NO instalado |
| Piper | — | — | NO instalado |
| nats-server | — | — | NO instalado |
| Swap **activo** | `/swapfile` 4G (1,8G en uso) | **Interno** | activo |
| Swap USB | `swapfile_aurora` 4 GB | USB | **existe pero NO activo** |

## 3. Espacio

- **Interno** (`/dev/mmcblk1p2`): `/dev/mmcblk1p2    57G    50G  3,8G  93% /` — antes de la limpieza: **889 MB libres (99%)**.
- **USB** (`/dev/sda1`, ext4, label `AURORA_EXT`): `/dev/sda1        7,3G   4,1G  2,9G  59% /media/majo1230/AURORA_EXT1` — 4,1 G ocupados por el swapfile.

## 4. Acciones ejecutadas (sin root)

- USB montado vía polkit en `/media/majo1230/AURORA_EXT1` (udisks añadió el sufijo `1` porque
  `AURORA_EXT` ya existía como directorio ocupado en el disco interno).
- Eliminados **solo regenerables**: `__pycache__`, `.mypy_cache`, `.pytest_cache`, `.ruff_cache`,
  caché de pip, `~/.npm/_npx` y `_cacache`, cachés de Chrome/Mozilla/node-gyp/mintinstall/mesa/typescript.
- **Espacio recuperado: ~2,9 GB.** Ollama verificado operativo tras la limpieza.
- **No se tocó**: código, git, documentación, bases de datos, `~/.config`, credenciales.

## 5. Bloqueo (por qué la migración no pudo completarse)

`sudo -n true` falla: **no hay sudo sin contraseña** en esta sesión no interactiva. Y el USB,
aunque montado, tiene su **directorio raíz propiedad de `root`** (`drwxr-xr-x root root`) — en ext4
la propiedad se almacena en disco, ninguna opción de montaje lo cambia. Por tanto mi usuario
**no puede escribir en el USB**.

Requieren root, sin excepción: escribir en el USB, mover `/usr/share/ollama`, editar `/etc/fstab`,
activar el swapfile del USB y reconfigurar el servicio systemd.

## 6. Comandos para el CEO (ejecutar en terminal interactiva)

```bash
# 1. Dar la propiedad del USB al usuario (habilita todo lo demás sin root en el futuro)
sudo chown majo1230:majo1230 /media/majo1230/AURORA_EXT1

# 2. Mover los modelos del disco interno al USB
mv /media/majo1230/AURORA_EXT/ollama_models /media/majo1230/AURORA_EXT1/

# 3. Eliminar el directorio-trampa interno y montar el USB en la ruta correcta
sudo umount /media/majo1230/AURORA_EXT1
rmdir /media/majo1230/AURORA_EXT
sudo mkdir -p /media/majo1230/AURORA_EXT

# 4. Persistencia real tras reinicio (elimina la causa raíz para siempre)
echo 'LABEL=AURORA_EXT /media/majo1230/AURORA_EXT ext4 defaults,nofail,x-systemd.device-timeout=10 0 2' | sudo tee -a /etc/fstab
sudo mount -a
sudo chown majo1230:majo1230 /media/majo1230/AURORA_EXT

# 5. Eliminar la instalación duplicada obsoleta (libera 1,8 GB) y desactivar el servicio systemd
sudo systemctl disable --now ollama
sudo rm -rf /usr/share/ollama

# 6. (Opcional) Trasladar el swap al USB y liberar 4 GB internos
sudo swapoff /swapfile && sudo rm /swapfile
sudo chmod 600 /media/majo1230/AURORA_EXT/swapfile_aurora
sudo swapon /media/majo1230/AURORA_EXT/swapfile_aurora
```

**Guardarraíl imprescindible:** el paso 4 (`fstab` con `nofail`) es lo que impide que el problema
se repita. Sin montaje persistente, cualquier ruta `/media/.../AURORA_EXT` vuelve a escribir en el
disco interno de forma silenciosa. Recomiendo además verificar `mountpoint -q /media/majo1230/AURORA_EXT`
antes de cualquier descarga de modelos.

## 7. Impacto en M1 / HC-1

Ninguno de estos bloqueos altera la conclusión medida: una inferencia real superó **120.000 ms**
frente al objetivo HC-1 de **1.200 ms**, con 2 CPU / 3,6 GB RAM y swap activo. HC-1 permanece
**Pendiente de validación en entorno objetivo** (D24). Liberar disco mejora la estabilidad, no la latencia.
