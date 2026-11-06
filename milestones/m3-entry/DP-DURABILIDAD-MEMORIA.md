---
documento: "Decision Package — Durabilidad de memoria.json (PersistentMemory)"
fecha: 2026-11-05
estado: "APROBADO por el CEO (2026-11-05). P1 CERRADA y publicada (473df8d, 8ff5bf9, 5bd18be; cierre documental 0a840eb). P2-B AUTORIZADA por el CEO (2026-11-05) e IMPLEMENTADA en local, pendiente de publicar; la fila T9 del contrato de olvido requiere ratificar su nuevo texto (§8)"
alcance-aprobado: "Persistencia de memoria.json en walking-skeleton/aura_skeleton/modules/memory.py, rama integracion/m3-entry"
no-cubre: "M4 · residencia (Fases 2/3, activación) · delegación remota · autenticación · CM2/S3 · producción · ~/.aura · cron · PARADA · purga física (CONTRATO-OLVIDO §5, BLOQUEADO)"
---

# DP — Durabilidad de `memoria.json`

## 1. Problema reproducido `[EJEC 2026-11-05]`

Tres recuerdos escritos con `await PersistentMemory.write(...)`; se anexa un fragmento `{"user_id": "mauricio", "kind": "no`
(corte a media escritura). Al reabrir: `JSONDecodeError` y los tres recuerdos válidos quedan inaccesibles (en un
directorio temporal; nada de `~/.aura`).

Lectura del código `[LECT]` (`modules/memory.py`):

- `_anexar` escribe con `open("a")` y **no hace `fsync`**: un recuerdo que `write` dio por guardado puede no
  sobrevivir a un corte de energía; el fichero recién creado tampoco tiene su entrada de directorio sincronizada.
- `_persist` (migración, `restore`, `backup`) escribe `.tmp` y hace `os.replace` **sin `fsync` del `.tmp`**: tras un
  corte, el rename puede quedar persistido con el contenido vacío → se perdería **toda** la memoria.
- `write` añade el recuerdo a la proyección en RAM **antes** de escribirlo: si la escritura falla (ENOSPC, EIO),
  la sesión sigue «recordándolo» y desaparece al reiniciar — capacidad fingida (INV-9).
- `_load` no tolera una línea final cortada → apertura fallida.

## 2. Contraste con contratos vigentes — DISENSO del Director

`milestones/m3-entry/CONTRATO-OLVIDO-Y-RETENCION.md` §2 (VIGENTE), fila **T9**: «Línea final truncada → falla en
alto, **no resucita en silencio**». Pruebas: `test_T9_una_lapida_truncada_hace_fallar_la_apertura_no_resucita_en_silencio`
y `test_T9_una_linea_final_truncada_cualquiera_es_fail_loud` (`tests/integration/test_olvido_adversarial.py`).

Motivo: la última línea puede ser una **lápida** (`olvidar`, G-7) o una **marca** `refutada` (`marcar`). Ignorarla
deshace en silencio la orden soberana del usuario (ADR-0017): lo olvidado reaparece, lo refutado vuelve a darse por
cierto. Por eso «`_load` tolera la última línea incompleta» **no se implementa** sin decisión: cambiaría un contrato
vigente. El problema del §1 (recuerdos inaccesibles) es real; el fallo en alto es deliberado.

## 3. P1 — CERRADA (sin conflicto con ningún contrato)

1. **`_anexar` duradero:** escritura + `flush` + `os.fsync` del fichero; `fsync` del directorio cuando el fichero se
   crea, y **reintentado** en el siguiente `_anexar` si falló (bandera `_dir_pendiente`; hallazgo MEDIUM de la
   auditoría independiente). Cualquier error (`OSError`, incluido el del `fsync`) se propaga (fallo explícito).
2. **`write` primero en disco, luego en RAM:** si `_anexar` falla, el recuerdo no entra en la proyección ni en el
   índice ni en el conteo. Un `write` fallido no deja rastro lógico.
3. **`_persist` duradero:** `fsync` del `.tmp` antes de `os.replace` y `fsync` del directorio después.
4. Sin cambios de formato (misma línea `json.dumps(item, ensure_ascii=False) + "\n"`), sin dependencias nuevas, sin
   tocar `olvidar`/`marcar`/`_proyectar`/`_load` (anclas de G7-M1..M7, OA-M3) ni T9.

Invariantes: recuerdos históricos válidos intactos; append-only en `write`/`olvidar`/`marcar`; T9 sigue fallando en
alto; ningún `write` dado por bueno sin estar en disco; el formato del fichero no cambia.

Concurrencia: `PersistentMemory` es de un solo escritor por diseño (sin cerrojo); P1 no lo cambia ni lo declara.

## 4. P2 — DECISION_REQUIRED (no ejecutado)

¿Qué hacer con una línea final cortada?

| Opción | Qué hace | Contrato T9 | Riesgo |
|---|---|---|---|
| **P2-A · statu quo** | Sigue fallando en alto (mejorar solo el diagnóstico) | Intacto | La memoria queda inaccesible hasta intervención manual |
| **P2-B · tolerancia selectiva** | Si el fragmento NO puede ser el comienzo de una línea con la clave `(user_id, kind, content)` de un recuerdo existente (no puede ser lápida ni marca), se ignora, se registra en el audit y la siguiente escritura cierra la cola con `\n` (sin borrar bytes). Si es ambiguo → falla en alto como hoy | Cambia «cualquiera es fail-loud» por «toda ambigua es fail-loud»; conserva «no resucita en silencio» | Regla de prefijo sobre JSON: hay que demostrar que no tiene falsos negativos (mutación + casos adversariales) |
| **P2-C · recuperación explícita** | Falla en alto con un error tipado que muestra el fragmento; una orden de recuperación, confirmada por el usuario, cierra la cola y deja constancia | Intacto en la apertura | Superficie nueva (orden de recuperación, quizá lista roja) |

Recomendación del Director: **P2-B**, porque recupera sin intervención los casos que no pueden afectar a la soberanía
y conserva el fallo en alto en todos los demás. Requiere acta del CEO que enmiende la fila T9.

## 5. Pruebas y aceptación de P1

`tests/unit/test_durabilidad_memoria.py`: `fsync` del fichero en cada `write`; `fsync` del directorio al crear;
`fsync` fallido → `write` lanza y el recuerdo no está en `recall` ni tras reiniciar; escritura fallida (ENOSPC)
→ igual; `_persist` hace `fsync` del `.tmp` antes del `replace` y del directorio después; controles (memoria vacía,
histórico válido tras reinicio, escritura posterior a un fallo, formato de línea byte a byte). T9 sin cambios.
Mutación: `mutaciones/durabilidad-memoria.toml`. Quality Gate PASS y auditoría independiente.

## 6. Exclusiones y riesgos

- `olvidar`/`marcar` retiran o marcan en RAM antes de anexar: si la lápida falla, la excepción se propaga, pero la
  sesión ya no muestra lo olvidado hasta reiniciar (y tras reiniciar reaparece). Se deja fuera para no tocar anclas
  G-7; candidato a P3 si el CEO lo prioriza.
- Purga física (contrato §5) bloqueada; no se toca.
- **Escritura parcial (disco lleno a media línea):** puede quedar una línea sin `\n`; el `write` siguiente se
  concatena y `_load` falla en alto (T9). Corregirlo exige recortar bytes (excluido por el CEO) o tolerar líneas
  cortadas al cargar (P2). Se añade a la decisión P2; no se oculta.
- **`fsync` de directorio fallido tras un append correcto:** la línea queda en disco, `write` lanza y la sesión no la
  tiene (sentido conservador, «al menos una vez»); al reabrir aparece. Un reintento del llamador anexa otra línea
  idéntica que la proyección colapsa por clave `(user_id, kind, content)`.
- En Linux un `fsync` fallido puede descartar páginas sucias: tras un error, «está en disco» no es garantía firme;
  por eso el error se propaga siempre.
- Preexistentes (auditoría de seguridad, MEDIUM, fuera de P1): `memoria.json` y su `.tmp` se crean sin modo 0600
  (dependen de la umask) y sin `O_NOFOLLOW`; `.tmp` predecible. Candidatos a un incremento de endurecimiento aparte.

## 7. Cierre de P1 (2026-11-05)

Publicado en `integracion/m3-entry` (push normal, pre-push con Quality Gate PASS):

| Commit | SHA | Contenido |
|---|---|---|
| DP | `473df8def56bd3cba6d72a2ea291896598588cc0` | este documento |
| Código | `8ff5bf9acecfe0028d33e460e8948022cdd59caf` | `walking-skeleton/aura_skeleton/modules/memory.py` |
| Pruebas | `5bd18beefb97604434b52ed91eef9abaeaaada85` | `tests/unit/test_durabilidad_memoria.py` + `mutaciones/durabilidad-memoria.toml` |

Evidencia `[EJEC]` (sobre exactamente el código publicado):

- RED: 5 pruebas de comportamiento fallaban sobre `4ccf202` (2 controles en verde); la del reintento del `fsync`
  de directorio falló antes de su corrección. GREEN: 9/9.
- Regresión (memoria, olvido, lápidas G-7, histórico, batería, G-1): **146 passed, 16 xfailed**.
- T9 (`test_olvido_adversarial.py`): **3/3** en verde — sigue fallando en alto. G-1 (`test_g1_escritura_bajo_nivel`,
  `test_g1_ruta_unica`): **PASS**.
- Mutación `durabilidad-memoria.toml`: **8/8** (DM-1..DM-8). Catálogos previos anclados en `memory.py`:
  `g7-lapida-append-only` 7/7, `olvido-adversarial` 4/4.
- Quality Gate: **PASS** — 4334 passed / 5 skipped / 17 xfailed, contratos 8 (también en el pre-push).
- Auditoría de seguridad independiente: **APROBADO**, sin CRITICAL ni HIGH (MEDIUM preexistentes: modo 0600,
  `O_NOFOLLOW`, orden RAM/disco en `olvidar`/`marcar`).
- Auditoría de corrección independiente: **APROBADO**; sus dos MEDIUM: reintento del `fsync` de directorio
  (corregido, DM-8) y escritura parcial a media línea (documentada en §6, ligada a P2).
- AgentShield: NO DISPONIBLE. Codex/OpenCode: no usados (sin bloqueo).

Riesgos residuales: los de §6, sin cambios. **P2 sigue DECISION_REQUIRED** (§4): `_load`, `olvidar`, `marcar` y
`_proyectar` no se modificaron.

## 8. P2-B — implementación (autorizada por el CEO el 2026-11-05)

Lectura única `_lineas_legibles` (memory.py), compartida por `PersistentMemory._load`, `restore` (solo el separador)
y el reloj de CM2 (`reloj_cm2._MemoriaSoloLectura`, T10: misma lectura). Una línea ilegible se tolera **solo si**:

1. es un **prefijo JSON estricto** de un objeto (`_forma_de_corte`): su único error es el fin de la entrada. Una
   comilla perdida, bytes cambiados o dos líneas fusionadas dejan un token inválido en medio → corrupción → falla en
   alto, aunque esté a mitad del fichero (hallazgo ALTO de la auditoría adversarial, corregido);
2. **no es ambigua** (`_fragmento_ambiguo`): no puede ser el comienzo de una línea con la clave
   `(user_id, kind, content)` de una línea existente, comparando en los dos sentidos y con `ensure_ascii` True y
   False. Lápidas y marcas copian siempre la clave → todo fragmento de lápida o marca es ambiguo. Si alguna línea no
   empieza por esas tres claves en ese orden, o no es un objeto, nada se tolera (fallo cerrado);
3. no se supera `_MAX_FRAGMENTOS_TOLERADOS` (3) en el fichero: una interrupción deja como mucho uno; más es corrupción
   (y acota el coste de la lectura).

Cualquier otra línea ilegible relanza su `JSONDecodeError` (T9). Cada tolerancia deja constancia en el audit
(`memoria.linea_truncada_tolerada`: posición y bytes; sin contenido ni hash, reversible para recuerdos cortos).
`_anexar` cierra una cola sin `\n` anteponiendo `\n` en el mismo write (sin borrar bytes): elimina la fusión del
riesgo residual de P1. Solo `\n` separa líneas: `splitlines()` cortaba en U+2028/U+2029/U+0085, que
`json.dumps(ensure_ascii=False)` no escapa — **defecto preexistente**: un recuerdo con U+2028 dejaba la memoria sin
abrir `[EJEC]`.

**Limitaciones declaradas.** Un corte anterior a que la clave se distinga (p. ej. `{"user_id": "mauricio", "ki`) es
indistinguible de una lápida cortada → sigue fallando en alto al reabrir (prueba
`test_limitacion_un_corte_previo_a_la_clave_...`). Un corte dentro de un escape o literal (`\u00`, `tru`) también.
Dos escritores simultáneos podrían fusionar líneas (PersistentMemory es de un solo escritor por diseño). El reloj de
CM2 tolera lo mismo pero no escribe constancia (es de solo lectura); la deja `PersistentMemory` al arrancar.

**Evidencia `[EJEC]` de P2-B.** RED: 5 pruebas de tolerancia/cierre fallaban; después, los casos A (lápida corrupta a
mitad de fichero) y B (fusión legada) de la auditoría adversarial, los cortes en mitad de token, U+2028 y `restore`.
GREEN: `test_durabilidad_memoria_p2.py` 36 pruebas. Regresión (memoria, olvido, G-7, histórico, batería, reloj CM2,
T11, G-1) en verde. Mutación: `durabilidad-memoria-p2.toml` **12/12** (P2-5 original era equivalente y se sustituyó,
ver el catálogo), `durabilidad-memoria.toml` 8/8, `g7-lapida-append-only` 7/7 y `reloj-cm2` 32/32 (G7-M5 y M23
reanclados a la lectura compartida, misma garantía), `olvido-adversarial` 4/4. Quality Gate **PASS** 4370 passed /
5 skipped / 17 xfailed, contratos 8. Auditoría de seguridad: APROBADO (sin CRITICAL/HIGH; MEDIUM de coste O(F·N) y LOW
de hash reversible, corregidos). Auditoría adversarial: RECHAZADO en primera pasada (lápida corrupta a mitad de
fichero resucitaba) → corregido con el prefijo JSON estricto → **APROBADO** en la segunda: 105 032 mutaciones de un
carácter de lápidas y marcas (a mitad y al final) y 5 219 cortes reales, 0 tolerados. La tolerancia también aplica a
mitad de fichero (es el estado legítimo que deja el cierre con `\n`); ninguna corrupción de un carácter lo produce.

**Contrato T9.** Las tres pruebas T9 siguen en verde sin modificarlas. Cambia el texto de la fila: de «línea final
truncada → falla en alto» a «línea truncada AMBIGUA o corrupta → falla en alto; un corte demostrable que no puede ser
lápida ni marca se tolera con constancia». La enmienda del texto de `CONTRATO-OLVIDO-Y-RETENCION.md` queda para
ratificación del CEO; no se edita aquí.

## Retorno sobre tokens

Corrige una vez, en el único almacén de recuerdos, la pérdida silenciosa por cortes de energía: evita depurar en el
futuro «AURA olvidó lo que le dije» sin causa visible, y deja escrita la decisión pendiente (P2) con opciones, sin
reabrir el análisis.

## 9. P3 — olvidar/marcar atómicos respecto a la RAM (autorizada por el CEO, 2026-11-06)

Cierra el primer punto de §6: `olvidar` y `marcar` persistían la lápida/marca DESPUÉS de cambiar la RAM, así que un
fallo de escritura a mitad dejaba la sesión y el disco inconsistentes (lo olvidado reaparecía al reiniciar, o al revés).
P3 los hace **atómicos respecto a la RAM**: anexan todas las lápidas/marcas primero y solo tocan `self._items`, el
índice, `_conteo_usuario` y la procedencia si **todas** las anexiones tuvieron éxito; si una falla, el error se propaga
(INV-9) y la RAM queda como antes de la llamada. `marcar` construye copias con la procedencia ya actualizada en vez de
mutar los dicts vivos. No hay rollback de disco (append-only): la lápida/marca que sí llegó a disco se proyecta por su
clave `(user_id, kind, content)` igual que la RAM tras el fallo, sin resucitar ni olvidar de más. No se tocó `_anexar`,
`_proyectar`, `_clave` ni el formato de línea; T9, T11 y el olvido de acciones del punto D (vía `ambito="acciones"`)
intactos. El riesgo de fsync parcial que queda es preexistente de P2-B (documentado), y P3 lo reduce al eliminar la
mutación prematura de la RAM.

Evidencia: `tests/unit/test_durabilidad_memoria_p3.py` (12 pruebas, con control); RED sobre `ff2e9c4`;
`mutaciones/durabilidad-memoria-p3.toml` (P3-1..P3-6, incluido P3-6 por la auditoría de corrección). Auditorías
independientes: corrección CABE (condición del mutante simétrico, resuelta); seguridad APROBADO sin CRITICAL ni HIGH.
