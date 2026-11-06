# Acta — Ratificación del inicio de CM2 y automatización de su medición (2026-10-18)

**Fuente:** orden ejecutiva del CEO «AURA — S3 / CM2: ejecución puntual y automatización segura», recibida en sesión el
2026-10-18. Este documento **transcribe** la orden; no añade alcance.

1. **Ratificación:** se ratifica el inicio histórico de CM2 del 2026-10-07 (evento `cm2.inicio`, seq 1314,
   2026-10-07T22:46:52Z). **Discrepancia original, que se deja constancia:** el inicio se ejecutó con «autorización
   operativa delegada» (CHECKPOINT ~8574-8603) mientras el mismo día el CHECKPOINT (~8296-8365) exigía orden explícita
   del CEO. El evento original **no** se reescribe ni se altera.
2. **Autorizado:** una ejecución puntual de `python -m aura_skeleton --medir-cm2` (escribe en `~/.aura`), y la
   evaluación y configuración posterior de un **cron diario de usuario**, solo tras verificar procedimiento e idempotencia.
3. **No autorizado (literal):** cambiar el código de CM2, borrar eventos, alterar decisiones de privacidad, levantar
   PARADA; commit, push, merge y despliegue siguen prohibidos.
