# Delegación segura a nodos — evidencia de implementación (2026-10-26/27)

Rama `pista/delegacion-segura` (worktree aislado `pista-nodos`, base `bf13a47`). Biblioteca probada **en aislamiento**:
**la delegación sigue DESHABILITADA en producción** — nada la cablea a `receptor`, `composicion` ni `__main__`, y el
comportamiento por defecto de `nodo_agente` no cambia sin `spki_fijada`.

Commits: (1) `feat(nodos): delegacion segura - biblioteca inicial (A1-A3, N1, N2) sin revisar` (estado previo a la
revisión, trazabilidad); (2) `fix(nodos): ...` con las correcciones de la revisión de seguridad independiente.

Clasificación de evidencia (D47): `[EJEC]` medido ejecutando · `[LECT]` leído · `[INFER]` deducido · `[HIPO]` no verificado.

## 1. Estado

| Área | Estado |
|---|---|
| A1 orden firmada (Ed25519, dominio, bytes exactos, esquema cerrado, `alg`, revocación, NFC) | implementado y probado `[EJEC]` |
| A2 resultado/acuse firmados y vinculados (`hash_tarea`), estados 1-5, `resolver_ambigua` | implementado y probado `[EJEC]` |
| A3 fijación SPKI (TLS 1.3, CERT_REQUIRED, STRICT, corte de handshake) | implementado y probado `[EJEC]` |
| N1 anti-replay persistente, epoch, concurrencia, fsync | implementado y probado `[EJEC]` |
| N2 firmador con política (tasa, epoch monótono persistido, log encadenado, socket seguro) | implementado y probado `[EJEC]` |
| M-1/M-2/M-3, B-1..B-6 de la revisión independiente | corregidos, cada uno con prueba y caso de control `[EJEC]` |
| Mutación (91 mutantes declarados) | declarados, **NO ejecutados** (los ejecuta el orquestador) |

## 2. Decisiones de diseño

* **Profundidad (M-1).** `leer_json_estricto` cuenta el anidamiento en una pasada lineal (ignorando cadenas) ANTES de
  `json.loads`; `PROFUNDIDAD_MAX = 32`. Todo lo hostil sale como `RechazoOrden(SOBRE_MALFORMADO)` (sobre, payload, acuse,
  resultado, emisión). Nunca `RecursionError`.
* **Diario de HC-1 (M-2).** Capa propia (`adapters/diario_hc1.py` sobre `jsonl_durable.py`), **no** el log del
  control-plane. Cada transición se anota ANTES de aplicarse en memoria (write-ahead); al construir `SeguimientoHC1` se
  reconstruye y se aplica `vencer()` (EMITIDA→INTERRUMPIDA, ACEPTADA→AMBIGUO, anotado). Al cablear, el callback
  `registrar` de `incorporar` irá al **log de HC-1 con ancla (D-LOG-1)**; este diario solo sostiene el estado
  operativo. Ventana conocida: caída entre `registrar` y `incorporado` ⇒ se re-incorporaría ⇒ el destino de `registrar`
  debe ser idempotente por `id_ejecucion`.
* **Estados del nodo (M-3).** `consumidas.jsonl` + `ejecuciones.jsonl`: CONSUMIDA → EJECUTANDO → COMPLETADA (resultado
  firmado guardado) | FALLIDA. AMBIGUA no se escribe: se deduce de un EJECUTANDO que no pertenece a la instancia viva.
  `NodoDelegado.ejecutar` marca EJECUTANDO (fsync, flock) antes de correr nada; una segunda llamada —misma instancia,
  otra instancia u otro proceso— se rechaza. Nunca se re-ejecuta una AMBIGUA/FALLIDA sola. El resultado ya firmado se
  reenvía idempotente (`reenviar_resultado`).
* **`resolver_ambigua(id, por, motivo, resultado_firmado)`.** Única vía para admitir un resultado de una ejecución
  AMBIGUA/INTERRUMPIDA: `por` ∈ `autoridades` (configuración, no el mensaje), motivo no vacío, firma del nodo
  destinatario y vínculo exacto (tarea, intento, `id_ejecucion`, `hash_tarea`); queda en el diario (`resolucion`) y la
  ejecución continúa por `validar` e `incorporar`. Un resultado tardío por el camino normal se rechaza.
* **Regex (B-1).** Patrones sin ancla + `coincide()` con `fullmatch` en todos los puntos.
* **Firmador.** Un fallo de codificación es un rechazo registrado; un fallo inesperado se registra (`fallo`) y el
  servidor sigue vivo. Tasa por ventana deslizante (defecto 60/60 s; solo cuentan las firmas, no los rechazos de política).
  `epoch` persistido (`epoch.jsonl`, append-only con fsync de fichero y directorio): se niega a arrancar con uno menor
  que el último y usa `max(configurado, último+1)` (cada reinicio sube el epoch). Log encadenado (`prev` = sha256 de la
  línea anterior) y `verificar_cadena_log`.
* **`crear_servidor` y G-1 (decisión a elevar).** La regla G-1/R-B (`tests/unit/test_g1_ruta_unica.py`) prohíbe a este
  módulo `unlink`/`os.replace` sin una exclusión `opera=[...]` en `architecture_manifest.toml` (aprobación del CEO). No se
  tocó el manifiesto. Consecuencia: **no se borra nada**: un objeto que no sea un socket propio en la ruta (fichero,
  enlace, socket ajeno) o un socket propio residual falla CERRADO sin tocarse (`ErrorClave`), y el operador retira el
  residual a mano. El epoch y la lista de revocados son **append-only** (sin `replace`). **DECISION_REQUIRED (CEO):**
  si se quiere que el firmador retire solo su socket residual, hace falta `[[mutaciones.excluido]] modulo =
  "aura_skeleton/adapters/firmador_hc1.py" opera = ["unlink"]` con motivo y fecha.
* **`alg`.** Campo firmado dentro del payload (orden, resultado, acuse); solo `"ed25519"`, sin negociación.
* **Revocación.** `PoliticaNodo.revocados` (kid revocado ⇒ `KID_REVOCADO` antes de verificar), `verificador_de(...,
  revocados)` para claves de nodo en HC-1, y lista persistente JSONL append-only `revocar`/`cargar_revocados` (ausente = vacía;
  ilegible, truncada, ajena o con permisos abiertos = fallo cerrado).
* **Canonicalización.** Solo la forma canónica exacta pasa; las cadenas deben estar en NFC (se **rechaza** lo no-NFC, no
  se normaliza en silencio); `1` ≠ `1.0` (el campo entero rechaza el float).
* **Fijación SPKI.** `aplicar_fijacion` exige `CERT_REQUIRED` y CA cargada, fuerza `VERIFY_X509_STRICT` y TLS ≥ 1.3;
  `not_valid_*_utc` si la versión de `cryptography` lo ofrece (compatible con 41).
* **Reglas N1 «fuera de orden».** `epoch_hc1` menor que el máximo visto ⇒ `EPOCH_ANTIGUO`; dentro del mismo epoch, las
  órdenes independientes se aceptan en cualquier orden, una vez cada una; `emitida_en` anterior al arranque ⇒ rechazo.

## 3. Cobertura (garantía → pruebas; todas con caso de control)

Rutas relativas a `walking-skeleton/tests/`. «robustez» = `unit/test_delegacion_robustez.py`, «diario» =
`unit/test_delegacion_diario_hc1.py`, «estados» = `unit/test_delegacion_nodo_estados.py`, «firmador+» =
`unit/test_firmador_hc1_endurecido.py`, «spki+» = `unit/test_fijacion_spki_endurecida.py`, «e2e» =
`integration/test_delegacion_e2e_nats.py`.

| Requisito | Pruebas |
|---|---|
| A1 firma sobre bytes exactos, dominio, esquema cerrado, N8 | `unit/test_delegacion_orden_firmada.py` (previas) |
| A1 `alg` fijo y firmado | robustez: `test_a1_alg_distinto_de_ed25519…`, `test_a1_alg_es_obligatorio_y_va_firmado…` |
| A1 revocación (orden, persistencia, HC-1) | robustez: `test_a1_orden_firmada_con_un_kid_revocado…`, `test_a1_la_lista_de_revocados_persiste…`, `test_a1_hc1_no_acepta_firmas_de_una_clave_de_nodo_revocada` |
| A1 canonicalización (bytes, `\u`, 1 vs 1.0, NFC/NFD) | robustez: `test_a1_solo_la_forma_canonica_exacta_pasa`, `test_a1_uno_y_uno_punto_cero_son_distintos`, `test_a1_nfc_y_nfd…`, `test_a1_payload_orden_del_firmador_tambien_exige_nfc` |
| M-1 profundidad | robustez: `test_m1_*` (5); firmador+: `test_b2_el_servidor_responde_y_sigue_vivo…` (línea profunda) |
| B-1 `fullmatch` | robustez: `test_b1_*` (3, `"abc\n"` y análogos) |
| A2 resultado/acuse/vínculo/estados | `unit/test_delegacion_resultado_firmado.py` (previas, con `alg`) |
| M-2 diario HC-1 (reconstrucción, vencidas, truncamiento, write-ahead, permisos) | diario: `test_cada_estado_sobrevive_a_un_reinicio`, `test_el_resultado_posterior_al_reinicio…`, `test_las_vencidas_pasan_a_interrumpida_o_ambiguo…`, `test_linea_final_truncada…`, `test_linea_ilegible_en_el_medio…`, `test_sin_durabilidad_no_hay_transicion…`, `test_el_diario_es_privado…` |
| M-3 estados del nodo, AMBIGUA, no re-ejecución, reenvío idempotente | estados: `test_estados_…`, `test_una_segunda_llamada_a_ejecutar…`, `test_el_resultado_guardado_se_reenvia…`, `test_tras_una_caida_ejecutando_es_ambigua…`, `test_una_ejecucion_que_falla…`, `test_no_se_puede_ejecutar_lo_que_no_se_consumio` |
| M-3 `resolver_ambigua` | diario: `test_un_resultado_tardio…`, `test_resolver_ambigua_exige_autoridad_declarada`, `…_valida_firma_y_vinculo_y_exige_motivo`, `…_no_acepta_el_resultado_de_otra_ejecucion…`, `…_solo_vale_para_ambiguas…`, `test_la_resolucion_se_registra_persistentemente…` |
| N1 anti-replay persistente | `unit/test_delegacion_anti_replay.py` (previas) |
| N1 fuera de orden | estados: `test_n1_epoch_menor…`, `test_n1_ordenes_independientes_del_mismo_epoch…`, `test_n1_emitida_antes_del_arranque…` |
| N1 concurrencia (hilos, procesos, `SeguimientoHC1`) | estados: `test_n1_muchos_hilos_…` (2), `test_n1_procesos_distintos…`; diario: `test_n1_el_mismo_resultado_desde_muchos_hilos…`, `test_n1_la_misma_emision_desde_muchos_hilos…`; previa: 6 procesos en anti_replay |
| N1/B-4 persistencia con fsync de fichero y directorio | diario: `test_n1_el_diario_hace_fsync…`; estados: `test_n1_el_almacen_hace_fsync…`, `test_m3_los_estados_se_escriben_con_fsync…`; firmador+: `test_b3_el_epoch_se_persiste_con_fsync…`; e2e 12 |
| B-4 almacén (permisos, línea truncada) | estados: `test_b4_*` (6) |
| A3 SPKI base | `unit/test_fijacion_spki.py`, `unit/test_nodo_agente_spki.py` (previas) |
| A3/B-6 contexto (CERT_REQUIRED, CA, STRICT, TLS 1.3, `_utc`) | spki+: `test_b6_*` (3), `test_a3_el_contexto_conserva…` |
| A3 corte a mitad de handshake (socket y asyncio) | spki+: `test_a3_un_corte_a_mitad_del_handshake…` (4 modos), `test_a3_el_corte_tambien_falla_cerrado_con_asyncio…` |
| N2 firmador base | `unit/test_firmador_hc1.py` (previas) |
| B-2 codificación / servidor vivo | firmador+: `test_b2_*` |
| B-3 tasa, epoch monótono | firmador+: `test_b3_*` (6) |
| B-5 socket seguro, log encadenado | firmador+: `test_b5_*` (7) |
| E2E 1-9 | e2e: `test_01 … test_09`, `test_09b` (registro sintético, antes «10») |
| E2E 10 caída de HC-1 y del nodo | e2e: `test_10_caida_de_hc1_y_del_nodo…` |
| E2E 11 ambigua no se repite; vía explícita | e2e: `test_11_una_ejecucion_ambigua_no_se_repite…` |
| E2E 12 resultado vinculado, diario con fsync, reverificable offline | e2e: `test_12_resultado_aceptado_vinculado…` |

Mutación: `walking-skeleton/mutaciones/delegacion-segura.toml` — 91 mutantes (45 previos, 4 de ellos reescritos por
cambio de código: M27, M34, M43, M44; 46 nuevos M46-M91 (los de esta tanda), uno por garantía nueva). Comprobado que cada `buscar` aparece
**exactamente una vez** en su fichero. **No ejecutados** (orden expresa). Posible carrera: M59 (sin `flock`) depende
del reparto de hilos/procesos; si sobrevive, endurecer la prueba, no declararlo equivalente.

## 4. Amenazas FUERA del modelo de confianza (no cubiertas, declaradas)

* **Mismo uid.** Cualquier proceso del mismo usuario puede leer la clave de firma, editar/borrar `consumidas.jsonl`,
  `ejecuciones.jsonl`, `seguimiento.jsonl`, `epoch.json`, la lista de revocados y el log del firmador (y reabrir el
  replay). La separación del firmador protege de errores y de código sin acceso a ficheros del usuario, no de un atacante
  con el mismo uid. Remedio: usuario de sistema distinto (requiere root), HSM/TPM o almacenamiento protegido.
* **Recorte de las últimas entradas del log del firmador / del diario**: la cadena detecta edición, borrado e
  intercalado, no el truncado a una línea completa. Exige ancla externa (D-LOG-1).
* **Compromiso de HC-1 o de la clave de firma**: quien firma como HC-1 manda órdenes válidas dentro de la política.
* **Compromiso de la CA privada + clave del servidor** (la fijación SPKI lo mitiga solo si el pin no se renueva solo).
* **Denegación de servicio** (inundación de órdenes válidas, llenado de disco): fuera de alcance salvo la tasa del firmador.
* **Canal lateral / tiempos**, **fallo físico del disco** que ignore `fsync`.
* El diario de HC-1 se **confía al releerlo** (no revalida las firmas de nuestras propias órdenes): un atacante con
  escritura sobre él puede fabricar estado.

## 5. Limitaciones

* **Mismo uid** (véase arriba): no hay custodia real de la clave.
* **Reloj real no implementado**: `Reloj.sincronizado()` es un contrato; el nodo de producción no tiene aún una fuente de
  hora fiable (NTP/RTC verificada). Las pruebas usan relojes falsos y, en e2e, `time.time()`.
* **La delegación NO está cableada**: ni `receptor`, ni `composicion`, ni `__main__`; no existe la capacidad delegable
  real (solo `calcular_resumen_sha256` de prueba, verificada recomputando — N14).
* El callback `registrar` de `incorporar` apunta hoy a un destino sintético; al cablear irá al log de HC-1 con ancla (D-LOG-1).
* `VERIFY_X509_STRICT` ya lo activaba el nodo; si una CA privada de producción no cumple el modo estricto, la fijación
  (que lo fuerza) fallará cerrado: comprobarlo antes de activar `spki_fijada`.
* Una orden CONSUMIDA que no llegó a EJECUTANDO tras una caída no se repone sola: exige una orden NUEVA de HC-1.

## 6. Comandos ejecutados y resultado `[EJEC]`

Desde `walking-skeleton/` del worktree `pista-nodos`:

| Comando | Exit | Resumen |
|---|---|---|
| `python3 -m pytest -q -p no:cacheprovider tests/unit tests/integration -k "delegac or firma or spki or nodo_agente or consumid or firmador"` (antes de tocar nada, tras el commit 1) | 0 | 128 pasadas |
| mismo comando, con las correcciones | 0 | 400 passed, 3622 deselected, 1 xfailed (57 s); incluye los 14 E2E con nats-server local (10-12 nuevos), estables en 3 ejecuciones consecutivas |
| `./quality-gate.sh` (1.ª pasada) | 1 | pruebas: 2 failed — G-1/R-B acusó `os.replace` (×2) y `unlink` (×1) en `firma_delegacion.py`/`firmador_hc1.py`; corregido sin tocar `architecture_manifest.toml` (append-only, sin borrar) |
| `./quality-gate.sh` (final) | 0 | formato OK · lint OK · mypy OK (101 ficheros) · pruebas OK: 4074 passed, 3 skipped, 17 xfailed (865 s) · contratos 8 passed · **QUALITY GATE: PASS** |
| comprobación de `buscar` del TOML (tomllib: cada `buscar` aparece exactamente una vez en su `fichero`) | 0 | 91 mutantes, 0 anomalías |

`herramientas.mutar` **no se ejecutó** (lo hace el orquestador): el estado de los 91 mutantes es «declarados».

## 7. Pendiente / para el orquestador

* Ejecutar `python3 -m herramientas.mutar mutaciones/delegacion-segura.toml` (sin nada en paralelo, regla del CEO 2026-08-09).
  Los 4 mutantes preexistentes cuyo texto cambió (M27, M34, M43, M44) se reescribieron; sus garantías siguen vigentes.
* DECISION_REQUIRED (CEO): exclusión G-1 `opera=["unlink"]` para `firmador_hc1.py` si se quiere retirada automática del
  socket residual (hoy falla cerrado).
* Antes de cablear: reloj fiable, usuario/almacenamiento distinto para clave y estados, ancla D-LOG-1 para `registrar`.

---

## 8. Segunda revisión de seguridad independiente y batería oficial de mutación (2026-10-27)

Cierra los hallazgos de la 2.ª revisión y el superviviente M19 de la batería oficial. Las secciones 1-7 describen el
estado tras el commit anterior; **donde difieran (diario «confiado al releerlo», `autoridades` como cadena, revocados
fijos, 91 mutantes), manda esta sección.** Pruebas nuevas: `tests/unit/test_delegacion_revision2.py` (60 casos, cada uno
con control); adaptadas: `test_delegacion_diario_hc1.py`, `test_delegacion_resultado_firmado.py`,
`test_delegacion_nodo_estados.py`, `test_firmador_hc1_endurecido.py`, `test_delegacion_e2e_nats.py`, `delegacion_apoyo.py`.

| Hallazgo | Causa | Corrección | Pruebas (todas con control) |
|---|---|---|---|
| **M19** sobrevivía | Único camino que lo ejercía: la comprobación `kid == subject` (antes) ya rechazaba al nodo B; nadie probaba un resultado firmado por A cuyo `id_nodo` dijera B, así que el `if c["id_nodo"] != id_nodo_subject` era inalcanzable por las pruebas. | Sin cambio de código en la comprobación; se separan `_leer_sin_contabilizar` (firma + esquema + `id_nodo`) y `_leer` (revocación + contabilidad). | `test_m19_*`: B firma correctamente `id_nodo=B` y se entrega como de A -> `KID_DESCONOCIDO`; entregado como de B -> `NODO_AJENO`; A firma `id_nodo=B` -> `NODO_AJENO`; idem acuses. Control: el suyo por su subject se acepta. Verificado a mano: con M19 aplicado las pruebas viejas (`test_delegacion_resultado_firmado.py`) PASAN (por eso sobrevivía) y las nuevas FALLAN (2). |
| **C1** duplicado de `resultado_remoto` | `incorporar` registraba el hecho y DESPUÉS anotaba en el diario: un fallo del diario o una caída entre ambos lo duplicaba al reintentar. | `incorporando` (durable) ANTES de `registrar`; `Registrar` pasa a ser un protocolo con `ya_registrado(id_ejecucion)` OBLIGATORIO (`TypeError` si falta) e idempotente; estados nuevos `INCORPORANDO` e `INCORPORACION_INCIERTA` (el diario con «incorporando» sin «incorporado» se lee así al reiniciar). `incorporar` consulta `ya_registrado` antes de registrar. | Orden observado desde dentro de `registrar`; fallo del diario al anotar `incorporando` (no registra), tras registrar (reintento: 1 registro, 1 llamada), caída entre `incorporando` y `registrar` (reinicio -> `INCORPORACION_INCIERTA` -> 1 registro), caída entre `registrar` e `incorporado` (reinicio -> no vuelve a llamar a `registrar`). |
| **C2** revocación no viva / ausente = permitir | `PoliticaNodo.revocados` y `verificador_de(revocados)` eran fijos de arranque; `cargar_revocados` devolvía vacío ante fichero ausente. | `adapters.firma_delegacion.ListaRevocados(ruta, ancla)`: se relee en CADA llamada (`flock` compartido, `O_NOFOLLOW`); al ver el fichero por primera vez deja un ANCLA (0600, fsync) en el estado propio; si después falta, está corrupto, truncado, ajeno/escribible o es un enlace -> `REVOCACION_ILEGIBLE` y se rechaza TODO. `PoliticaNodo.fuente_revocados` (nodo, en cada orden) y `SeguimientoHC1.fuente_revocados` (HC-1, en cada acuse/resultado/resolución). | Revocar en caliente surte efecto sin recrear nada (nodo y HC-1); borrar el fichero tras crearlo rechaza órdenes, acuses y resultados; lista corrupta/truncada/ajena/enlace; lectura bajo flock (el lector espera a una escritura en curso). Control: un nodo que nunca tuvo lista funciona y no deja ancla. |
| **C3** autoridad = cadena | `resolver_ambigua(…, por: str, …)` aceptaba cualquier cadena de una lista. Nada impedía reemitir una tarea con efectos. | La resolución exige una AUTORIZACIÓN FIRMADA (dominio propio `aura.delegacion.resolucion/1`, campos `id_ejecucion, decision, motivo, emitida_en, caduca_en, nonce`, vida <= 600 s) por un `kid` de `kids_autoridad` con un `verificar_autoridad` APARTE; el constructor rechaza que la autoridad sea la clave de HC-1 o un id de nodo. Nonce de un solo uso persistido en el diario (se reconstruye al reiniciar). `Capacidad.idempotente: bool` (obligatorio; `calcular_resumen_sha256` = `True`): para una capacidad NO idempotente o desconocida, `registrar_emision` rechaza un nuevo intento si hay uno AMBIGUO/INTERRUMPIDA/INCORPORANDO/INCORPORACION_INCIERTA de la misma tarea (`tarea_con_intento_ambiguo`). | Firma inválida, kid de HC-1/nodo/desconocido, dominio equivocado, caducada, vida excesiva, del futuro, de otra ejecución, nonce reutilizado (también tras reiniciar), esquema cerrado, autoridad mal configurada; reemisión bloqueada (ambiguo, interrumpida, incorporación incierta, capacidad desconocida) con controles: idempotente sí se reemite y otra tarea no está bloqueada. |
| **BAJO a** diario de HC-1 | `_aplicar` confiaba en lo releído. | Al releer se re-verifican firmas de resultado y de resolución (y la autorización), el vínculo con la ejecución, las TRANSICIONES (`incorporado` sin `incorporando`, `validacion` sin resultado, emisión repetida…) y las interrupciones se limitan a `{INTERRUMPIDA, AMBIGUO}` coherentes con el estado previo. Diario manipulado -> `DIARIO_ILEGIBLE` con motivo. | Resultado con firma rota, resultados intercambiados, autorización de intruso, nonce repetido, interrupción a estados imposibles, saltos de estado. Control: el diario íntegro se recupera. |
| **BAJO b** `ejecutar` | Aceptar y ejecutar eran independientes. | `revalidar_para_ejecutar`: reloj sincronizado, coherencia de `OrdenValida` (hash de los bytes y campos == lo firmado), revocación vigente y caducidad, ANTES de marcar `EJECUTANDO`; `consumir(id, epoch, hash_tarea)` liga el hash al consumo (`hash_consumido`) y `ejecutar` exige que sea el de la orden entregada. | Caduca entre aceptar y ejecutar; revocada entre ambos; campos o hash adulterados en memoria; otra orden con el mismo `id_ejecucion`; persistencia del hash. En todos, el estado queda `consumida` (no se inició nada). |
| **BAJO c** firmador | Log abierto con `open` propio; los rechazos no gastaban cupo; `Path.stat()` seguía enlaces. | Log vía `abrir_bloqueado` (flock exclusivo + `O_NOFOLLOW` + 0600) y `prev` leído del FICHERO bajo el cerrojo (dos instancias no rompen la cadena); TODA petición gasta cupo; tope `rechazos_log_max` (20) de rechazos ESCRITOS por ventana, el resto se cuenta y la siguiente entrada declara `suprimidos`; `crear_servidor` usa `lstat`. | Enlace simbólico como log (no se escribe a su destino), flock, cadena entre instancias, cupo consumido por rechazos, tope y declaración de suprimidos, `lstat`. (La prueba B-3 «los rechazos no gastan cupo» se invirtió a propósito.) |

### Mutantes (91 -> 139; 48 nuevos M92-M139) y verificación a mano

`mutaciones/delegacion-segura.toml`: comprobación con `tomllib` de que cada `buscar` aparece exactamente UNA vez en su
`fichero` y difiere de `sustituir` (139 mutantes, 0 anomalías). Se reescribieron los `buscar` obsoletos de M5, M24, M43,
M44, M67, M68, M74, M90, M91 (el código cambió; M7 y M18 conservan el texto) y M19 añade la prueba nueva. **No se ejecutó `herramientas.mutar`**:
verificación manual en una COPIA bajo el tmp del trabajo (copiar el árbol, aplicar el `buscar`->`sustituir`, correr las
`pruebas` del mutante, exigir fallo, restaurar): 60 mutantes (los 48 nuevos, M19 y los 11 preexistentes afectados) -> los 60
DETECTADOS (rc=1 = fallo de pruebas, nunca error de sintaxis). En la primera pasada sobrevivieron 4 (M67 equivalente por
una comprobación redundante, M104 y M134 porque el destino del enlace era inseguro y se rechazaba por otro motivo, M131
porque el diario falso se rechazaba antes por otro vínculo): se añadieron/ajustaron pruebas y los 4 mueren.

### Comandos `[EJEC]`

| Comando | Exit | Resumen |
|---|---|---|
| `pytest tests/unit/test_delegacion_revision2.py` | 0 | todas pasan |
| `pytest -k "delegac or firma or spki or nodo_agente or consumid or firmador"` (2 ejecuciones seguidas) | 0, 0 | verde, E2E 14/14 estables 2 de 2 |
| verificación manual de mutantes (copia en tmp del trabajo) | 0 | 60/60 detectados tras el ajuste |
| `./quality-gate.sh` | 0 | formato OK (327 ficheros) · lint OK · mypy OK (101 ficheros) · pruebas OK: 4134 passed, 3 skipped, 17 xfailed (760 s) · contratos 8 passed · **QUALITY GATE: PASS** (incluye G-1 sin añadir excepciones al manifiesto: el ancla se crea con `os.open`, sin `unlink`/`replace`) |

### Límites declarados que siguen vigentes

* Mismo uid: quien borre la lista de revocados Y su ancla (o el diario) reabre el hueco; la integridad física exige otro
  usuario/almacenamiento. El ancla detecta el borrado accidental o parcial, no a un atacante con el mismo uid.
* La rotación/gestión de la clave de autoridad humana y su custodia (distinta de las de HC-1 y nodos) no está
  implementada: hoy el verificador y los `kids_autoridad` se inyectan.
* El destino real de `registrar` (log de HC-1 con ancla D-LOG-1) debe cumplir `ya_registrado`; sigue sin cablear.
* Un nodo revocado no invalida el HISTORIAL ya incorporado: al releer el diario se verifica la firma, no la revocación.
