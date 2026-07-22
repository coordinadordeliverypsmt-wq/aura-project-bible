---
documento: "MA.3 — Diseno: rotacion por archivo del audit log (retencion sin borrado)"
fecha: 2026-07-22
autor: "CTO"
estado: "PROPUESTA DE DISENO — pendiente de gate del CEO. Sin implementacion. Sin cambios en produccion."
origen: "MA.3; contradiccion Bible↔objetivo reportada y resuelta: rotacion por archivo, no por borrado (CEO 2026-07-22)"
---

# MA.3 — Rotacion por archivo del audit log

Principio inviolable (CEO): el audit log es una **traza forense inmutable (D9)**. MA.3 controla el
**crecimiento del almacenamiento**, **no** reduce la evidencia disponible. La rotacion es por
**segmentos de archivo**, nunca por eliminacion de registros.

## 1. Propiedad que debe garantizar el sistema (invariantes)

| # | Invariante | Condicion del CEO |
|---|---|---|
| **I1** | El **fichero activo** nunca supera un umbral configurable; al superarlo se **sella** en un segmento y se abre uno nuevo. | 1 (rotacion por segmentos) |
| **I2** | **Ningun registro se elimina por rotacion.** La suma de registros (activo + segmentos) solo crece. La purga sigue existiendo **solo** a peticion del usuario (Bible 5.5, derecho al olvido) — distinta de la rotacion. | 1 (nunca borrado automatico) |
| **I3** | **Integridad verificable por segmento:** cada segmento sellado tiene un `sha256` en un manifiesto append-only; alterar un byte lo hace detectable. | 2 |
| **I4** | **Reconstruccion completa:** el historial se reconstruye leyendo activo + segmentos, ordenado por `seq`, **sin huecos ni duplicados**. | 3 |
| **I5** | **Cursor robusto a rotacion:** los conectores no pierden ni reprocesan eventos tras rotar ni tras reiniciar. El cursor deja de ser el nº de lineas en memoria y pasa a un **`seq` monotonico persistente**. | 4 |

## 2. Diseno

### 2.1 Identificador estable: `seq` monotonico
Cada registro de auditoria recibe en `append` un `seq` entero monotonico y creciente. Es **aditivo**
al formato actual (`{level, module, msg, trace_id, audit, ts, seq}`) — no rompe a los conectores
(ignoran campos extra) ni contradice el sobre de eventos del bus (3.3 §4.1, que es otra entidad). En
el arranque, `AuditLog` deriva el siguiente `seq` del maximo ya presente (activo + manifiesto), de
modo que es monotonico **entre reinicios**.

### 2.2 Rotacion por archivo (archival)
- Se escribe en el fichero activo `audit.jsonl`.
- Cuando su tamano supera `umbral_bytes`, se **sella**: se renombra a `audit-<seq_ini>-<seq_fin>.jsonl`,
  se calcula su `sha256`, se anexa una linea al **manifiesto de segmentos**
  `audit-segments.manifest.jsonl` (`{segmento, sha256, seq_ini, seq_fin, registros, ts_sellado}`), y
  se abre un `audit.jsonl` nuevo.
- **Nada se borra.** Los segmentos son inmutables (sellados + hash registrado). El manifiesto reutiliza
  el patron ya probado del respaldo de memoria (Bible 3.5 §6 / M1).

### 2.3 Cursor persistente de conectores
- Cada conector persiste su cursor = **ultimo `seq` procesado**, en un fichero pequeno
  (`cursores/<conector>.cursor`).
- `recoger()` lee los registros con `seq > cursor` recorriendo el activo y los segmentos cuyo rango
  `[seq_ini, seq_fin]` incluye seqs mayores que el cursor; procesa; avanza y **persiste** el cursor.
- Rotation-stable (el `seq` no cambia al sellar) y persistente (sobrevive reinicios; ya no reprocesa
  el log entero). Reemplaza al actual `self._leidas` en memoria (`conectores/auditoria.py:33,46`).

### 2.4 API (a implementar en fase 2, tras aprobar este diseno)
- `AuditLog.append(record)` → asigna `seq`, escribe, rota si supera umbral.
- `AuditLog.segmentos()` → segmentos sellados (del manifiesto).
- `AuditLog.verificar(segmento)` → `sha256` vs manifiesto (True/False).
- `AuditLog.reconstruir()` → itera activo + segmentos por `seq`, sin huecos ni duplicados.
- `AuditLog.leer_desde(seq)` → registros con `seq > cursor` (para conectores).
- `Cursor.cargar()/guardar(seq)` → persistencia por conector.

## 3. Pruebas (TDD) — la propiedad, como prueba

Cada invariante tiene su prueba. Las marcadas **[RED-ahora]** ya fallan contra la implementacion
actual (demuestran que la propiedad **no** esta garantizada hoy); las marcadas **[spec]** definen el
objetivo del API nuevo y se verifican en fase 2 con doble degradado (estilo mutacion).

- **T-I1** `test_el_fichero_activo_no_supera_el_umbral` **[RED-ahora]**: escribir registros hasta pasar
  el umbral; el fichero activo se mantiene acotado (hoy crece sin cota → falla).
- **T-I2** `test_la_rotacion_no_elimina_ningun_registro` **[spec]**: forzar varias rotaciones; total de
  registros (activo + segmentos) == escritos. Mutacion: una "rotacion" que trunque debe disparar la prueba.
- **T-I3** `test_cada_segmento_tiene_integridad_verificable` **[spec]**: tras sellar, `verificar` == True;
  alterar un byte del segmento → `verificar` == False.
- **T-I4** `test_reconstruccion_completa_desde_activo_y_segmentos` **[spec]**: escribir N con rotaciones;
  `reconstruir()` devuelve los N por `seq`, sin huecos ni duplicados.
- **T-I5a** `test_el_cursor_no_pierde_ni_duplica_tras_rotacion` **[RED-ahora]**: el conector procesa hasta
  `seq` X; se rota; llegan nuevos; procesa **solo** los nuevos (hoy el offset de lineas se invalida → falla).
- **T-I5b** `test_el_cursor_sobrevive_al_reinicio` **[RED-ahora]**: el conector procesa; nueva instancia
  (reinicio); no reprocesa lo ya visto (hoy `_leidas` en memoria vuelve a 0 → falla).

## 4. Verificacion de contradicciones (disciplina del CEO)

Revisado Bible, ADR, acta e implementacion: **no aparece una contradiccion nueva.** Notas:
- El audit log sigue siendo **inmutable (D9)**: la rotacion sella y archiva, no altera ni borra.
- **Coexiste** con la purga a peticion del usuario (Bible 5.5): rotacion ≠ purga; el derecho al olvido
  se conserva intacto y es la unica via de borrado.
- Anadir `seq` es evolucion **aditiva** del formato (ADR-0004 regla 11: no rompe contratos); no toca el
  sobre de eventos del bus (3.3), que es otra entidad.
- El manifiesto de segmentos reutiliza el patron de integridad del respaldo de memoria (3.5 §6).

## 5. Alcance de la fase de implementacion (fase 2, tras aprobar este diseno)
1. Escribir las pruebas T-I1..T-I5b (TDD, RED).
2. Implementar `seq` + rotacion por archivo + manifiesto de segmentos en `AuditLog`.
3. Reemplazar el cursor de `ConectorDeAuditoria` (`_leidas`) por cursor `seq` persistente.
4. Verificar cada prueba contra un doble degradado (mutacion) antes de darla por buena.
5. Quality Gate verde reproducible → propuesta de integracion antes de publicar.

**Nada de esto se ha implementado.** Este documento es el diseno para tu aprobacion.
