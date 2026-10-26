# Acta — Reintentos el mismo día de la automatización de CM2 (2026-10-18)

**Fuente:** orden ejecutiva del CEO «AURA — S3 / CM2: reparar el aplazamiento de la automatización», recibida en sesión el
2026-10-18. Este documento **transcribe** la orden; no añade alcance. Amplía la autorización de
`decisiones/2026-10-18-acta-ratificacion-inicio-cm2.md` §2 («un cron diario de usuario»).

**Autorizado (literal):** «corregir el riesgo detectado en el script `~/.local/bin/aura-medir-cm2.sh` y en el cron de
usuario asociado, para que una ejecución aplazada porque AURA está activo pueda volver a intentarse más tarde el mismo
día». Alcance: script de automatización y cron de usuario de CM2; ficheros auxiliares de estado y pruebas bajo
`~/.local/state` con permisos restrictivos; documentación de evidencia y continuidad afectada. Requisitos: mantener 21:30
como primera ejecución; reintentos en horas explícitas y acotadas antes de terminar el día local; no repetir una medición
ya hecha; flock; conservar el despertador; registrar omisiones solo con agregados.

**No autorizado (literal):** código de CM2 y su mecanismo de medición; `~/.aura`, `memoria.json` y el contenido de los
eventos; D-CM2-1, privacidad, PARADA y decisiones de gobernanza; configuración global, cron del sistema, sudo, despliegues
y cambios de arquitectura; commit, push, merge y limpieza de cambios pendientes; crear hechos artificiales, sondas de
prueba en producción o alterar marcas temporales.
