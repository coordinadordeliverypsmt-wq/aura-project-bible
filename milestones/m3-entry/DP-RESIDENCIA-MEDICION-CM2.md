---
documento: "Decision Package — Residencia ↔ Medición CM2 (audit forense multi-escritor)"
fecha: 2026-11-05
estado: "APROBADO por el CEO (2026-11-05) — alternativa A2, FASE 1 ÚNICAMENTE. Fase 2 y Fase 3 PENDIENTES de su propia validación y autorización"
alcance-aprobado: "Incorporación documental + Fase 1 local (endurecimiento de AuditLog en walking-skeleton/aura_skeleton/observability.py) en la rama integracion/m3-entry"
no-cubre: "Activar residencia · modificar el cron de producción (aura-medir-cm2.sh) · quitar el aplazamiento de CM2 · cambios en producción · cambiar criterios S3/CM2 · PROCEDIMIENTO-INICIO-CM2"
evidencia: "Auditoría de solo lectura 2026-11-05: Graphify + 5 agentes ECC (arquitectura, concurrencia, persistencia, seguridad, QA) + contraste directo del Director"
---

# DP — Residencia ↔ Medición CM2

## 1. Problema demostrado

**El audit forense presupone un único escritor, pero nada lo garantiza.** [HECHO]

- `AuditLog.__init__` lee `_max_seq` una sola vez; `append` incrementa `seq` **en memoria** y escribe sin cerrojo
  (`observability.py:126,132-140`). Dos procesos emiten el **mismo `seq`** (lo reconoce `core/reloj_cm2.py:16-19`).
- El cron de CM2 **se aplaza** si hay un AURA vivo (`~/.local/bin/aura-medir-cm2.sh:78-89`); con más de 7 días
  aplazado, las sondas de día 28 caen fuera de [28,35] y no cuentan (`reloj_cm2.py:52`; PROCEDIMIENTO §7.4, §7.6).
  Una AURA **residente** (`--escuchar`, `adapters/escucha.py`) haría que CM2 no pudiera medir nunca.

**El problema es más amplio que CM2.** [HECHO]

- Ya hay varios escritores hoy: `componer()` llama a `configure_audit` (`composicion.py:398`), de modo que cualquier
  `python -m aura_skeleton` compuesto (`--verificar`, `--gobierno`, CLI, `--iniciar-cm2`, `--medir-cm2`) escribe.
- `_sellar` **pierde registros**: tras `os.replace`, el `open(path,"w").close()` trunca el activo que otro proceso
  haya creado entretanto (contradice D9/MA.3, «nada se elimina»). Nombra el segmento con `registros[0]`/`[-1]`.
- Con un solo escritor: una cola truncada no se cierra y el siguiente `append` destruye un evento válido; un corte
  entre el rename y el manifiesto deja un segmento huérfano invisible cuyo `seq` puede reutilizarse.
- Los cursores por `seq` (`leer_audit_desde`, conector de auditoría) saltan para siempre un `seq` repetido.

## 2. Invariantes que se preservan

1. Append-only y nada se elimina (D9/MA.3). Segmentos y manifiestos existentes siguen válidos (mismo sha256): **el
   formato de línea y de manifiesto no cambia**.
2. El historial es la única fuente de verdad (ADR-0023); las proyecciones se pueden reconstruir.
3. **`seq` único y monótono** entre todos los escritores y segmentos.
4. Ningún evento se pierde por rotación, caída o concurrencia.
5. Criterios de CM2 intactos (población = hechos declarados tipados, 20 sondas, D-CM2-1). La ventana [28,35] es criterio
   ratificado por el CEO el 2026-11-09; hasta esa fecha era un parámetro de implementación sin decisión explícita.
6. Kill switch y PARADA sin cambios; lista roja falla cerrada (ADR-0003); ningún fallo del audit es silencioso (INV-9).
7. Motor Único (ALERTA-005) intacto. Local-first (ADR-0001): `flock` POSIX, solo sistema de ficheros local.
8. S3 abierto; sin siembra.

## 3. Alternativas

| Criterio | A1 · Escritor residente | **A2 · Asignador único de `seq`** | A3 · Ventana de mantenimiento |
|---|---|---|---|
| Causa raíz | No | **Sí, para todos los escritores** | No |
| `_sellar` y cola truncada | No | **Sí** | No |
| Corrección concurrente | Con cerrojo de instancia | Con cerrojo aparte | **Incorrecta** sin cerrojo del kernel |
| Visión «disponible siempre» | Sí | Sí | No (AURA sorda cada noche) |
| ¿Existe lo necesario? | Temporizador/IPC nuevos | Patrón `flock` del control-plane | No (solo SIGTERM) |

**Decisión del CEO (2026-11-05): A2.** A3 se descarta; A1 queda reducido a cerrojo de instancia (Fase 2).

## 4. Fase 1 — diseño aprobado (decisiones del Director)

Solo `walking-skeleton/aura_skeleton/observability.py`. Aditivo; sin dependencias nuevas; **no** se importa
`jsonl_durable` (vive en otra rama; se convergerá tras el merge).

1. **Cerrojo independiente** `<audit>.lock` (p. ej. `audit.jsonl.lock`), creado 0600, que **nunca** se renombra ni
   borra. `LOCK_EX` para escribir y rotar; `LOCK_SH` para leer (`leer_audit_desde`, `segmentos`, `verificar`).
2. **`seq` bajo cerrojo exclusivo.** Dentro del cerrojo: si el activo no cambió desde la última escritura propia
   (mismo inodo y tamaño por `fstat`), `seq` = caché + 1; si cambió, se recalcula `_max_seq` (manifiesto + activo).
   Un `append` fallido no consume `seq`.
3. **Escritura única con detección de parcial.** `os.open(O_WRONLY|O_APPEND|O_CREAT, 0o600)`, un `os.write`; si
   escribe menos bytes de los pedidos → error explícito. `fsync` del fichero; `fsync` del directorio al crearlo.
4. **Cola truncada: se cierra, no se recorta.** Si el activo no acaba en `\n`, se añade `\n` (append-only: no se
   borra ningún byte; la línea parcial queda como línea ilegible que los lectores ya ignoran) y se deja constancia
   con un registro de auditoría. El evento siguiente ya no se destruye.
5. **`_sellar` bajo el mismo cerrojo y reanudable.** Orden: renombrar → manifiesto (+fsync) → fsync de directorio.
   Se elimina el `open(path,"w")` que truncaba. Nombre con mínimo y máximo `seq` reales.
6. **Reconciliación de huérfanos.** Bajo cerrojo exclusivo (al abrir y antes de sellar): todo segmento con el patrón
   de nombre que no figure en el manifiesto se anota (mismas claves) y se deja constancia en el audit.
7. **Política del cerrojo:** espera acotada (constante con nombre). Al agotarse → error explícito `AuditBloqueado`
   (fail-closed); nunca se descarta un registro en silencio.

## 5. Riesgos (por prioridad)

1. ALTO, existe hoy: colisión de `seq` que corrompe cursores. → Fase 1.
2. ALTO, existe hoy: cola truncada que destruye el evento siguiente. → Fase 1.
3. MEDIO-ALTO: `_sellar` no reanudable (huérfanos, truncado bajo carrera). → Fase 1.
4. MEDIO (memoria, fuera de esta fase): `_anexar` sin `fsync`; `_load` no tolera cola truncada. → corrección aparte.
5. BAJO: `KillSwitch()` sin ruta usa `/tmp/aura/KILL` (en producción se usa `~/.aura/KILL`, `composicion.py:394`).

## 6. Pruebas de aceptación (RED primero; copia aislada, `AURA_DATOS` en tmp)

- **R1** 2 procesos reales × N appends → `seq` únicos y contiguos, sin pérdida (sobre el código actual DEBE fallar).
- **R2** R1 con rotación (`umbral_bytes` bajo) → sin pérdida y `verificar` en verde en cada segmento.
- **R3** línea parcial + segundo escritor → el evento siguiente no se pierde; queda constancia.
- **R4** segmento huérfano (corte entre rename y manifiesto) → se reconcilia y sus eventos vuelven a ser visibles.
- **R5** escritura parcial / ENOSPC → error explícito, `seq` no consumido, nada dado por escrito.
- Adicionales: cerrojo liberado tras SIGKILL; espera acotada → `AuditBloqueado`; compatibilidad con segmentos y
  manifiestos previos (sha256 intacto); lectura bajo `LOCK_SH`.
- Mutación (`mutaciones/audit-multiescritor.toml`): `seq` en memoria sin releer, escritura sin cerrojo o con
  `LOCK_SH`, rotar fuera del cerrojo, volver al truncado `open("w")`, no cerrar la cola truncada, no reconciliar
  huérfanos, tragar la escritura parcial, quitar el `fsync`.

## 7. Impacto sobre CM2 y S3

Criterios de CM2 intactos; S3 abierto. La Fase 1 **no** quita el aplazamiento ni activa residencia: elimina la causa
técnica que hoy obliga a aplazar. Sin población seguirá sin haber medición (D-CM2-1).

## 8. Fases y autorizaciones

| Fase | Contenido | Estado |
|---|---|---|
| **1** | Endurecimiento de `AuditLog` (este documento, §4) | **APROBADA** (CEO 2026-11-05) |
| 2 | Cerrojo de instancia única del residente (`flock LOCK_NB`) | PENDIENTE de autorización |
| 3 | Quitar el aplazamiento del cron; actualizar PROCEDIMIENTO §5/§7.4/§7.6 (con acta) | PENDIENTE de autorización |
| — | Activar residencia (decisión de producto; `aura-voz.sh` no existe) | PENDIENTE, decisión aparte |

## 9. Decisiones humanas pendientes

1. Fase 2 y Fase 3 (autorizaciones separadas, tras validar la Fase 1).
2. Nota en ADR-0023 / MA.3 que haga explícito «audit multi-escritor».
3. Lectura agregada y sin contenido del audit real para detectar `seq` duplicados o huérfanos previos (excepción §7.3).
4. Convergencia con `jsonl_durable` tras el merge de la rama de integración.
5. Corrección aparte de la durabilidad de `memoria.json`.

## Retorno sobre tokens

Se corrige una vez, en el componente que ya existe, un defecto que afecta a todos los procesos: no hay que parchear
cada nuevo escritor, se evitan depuraciones futuras de pérdidas silenciosas de evidencia, y AURORA podrá funcionar
de forma continua sin vigilancia humana de las ventanas de medición.
