---
documento: "Decision Package — Durabilidad de memoria.json (PersistentMemory)"
fecha: 2026-11-05
estado: "APROBADO por el CEO (2026-11-05, opción A del informe de continuidad). P1 (durabilidad) EN EJECUCIÓN dentro del alcance. P2 (tolerar la cola truncada) DECISION_REQUIRED: contradice el contrato vigente T9"
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

## 3. P1 — en ejecución (sin conflicto con ningún contrato)

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

## Retorno sobre tokens

Corrige una vez, en el único almacén de recuerdos, la pérdida silenciosa por cortes de energía: evita depurar en el
futuro «AURA olvidó lo que le dije» sin causa visible, y deja escrita la decisión pendiente (P2) con opciones, sin
reabrir el análisis.
