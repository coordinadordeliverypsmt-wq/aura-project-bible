# Evidencia — D-LOG-1 (ancla externa del log) y D1/D2/D3 (autoconstruccion)

Rama `pista/control-plane-integridad`, base `bf13a47`. Todo `[EJEC]` en el worktree `pista-cp`, con historiales sinteticos y
`AURA_ANCLA_DIR` / `AURA_AUTOCONSTRUCCION_ESTADO` en temporales. No se ejecuto `herramientas.mutar`.

## RED medido (codigo previo, log sintetico de 6 eventos, cola truncada)

    -1 evento : {'integro': True, 'eventos': 5, ...}      -2 : {'integro': True, 'eventos': 4}      -4 : {'integro': True, 'eventos': 2}

## Comandos y resultados

| Comando | Exit | Resumen |
|---|---|---|
| `cd entorno/control-plane && AURA_AUTOCONSTRUCCION_ESTADO=$(mktemp -d) python3 -m pytest -q -p no:cacheprovider test_red_ancla_log.py` | 0 | 44 passed |
| idem `test_red_correlacion_autoconstruccion.py` | 0 | 53 passed |
| idem suite completa del control-plane | 1 | 6 failed, 1523 passed, 3 skipped (690 s). Los 6 fallos NO son nuevos: 4 dependen del log/estado reales del arbol (`capacidad_completada` x2, `frente_autonomo`, `fuera_de_alcance_exigible`) y 2 de planificacion/prioridad de procesos ajenos (`aislamiento_estricto`, EPERM/EACCES del kernel). Reproducidos en una exportacion limpia de `bf13a47` en `/tmp` |
| `cd walking-skeleton && python3 -m pytest -q -p no:cacheprovider tests/unit/test_garantias_vigentes.py tests/unit/test_panel_progreso.py` | 0 | verde tras ampliar 4 patrones (ver abajo) |
| `ruff check` / `ruff format --check` de `walking-skeleton/tests/conftest.py` | 0 | limpio |
| `ls ~/.local/state/aura/anclas` | 2 | no existe: ninguna prueba escribio anclas en el estado real |

Mutantes: 36 declarados en `entorno/control-plane/mutaciones/integridad-y-autoconstruccion.toml`. NO ejecutados con el arnes.
Comprobacion manual previa (copia en `/tmp`, serie, solo `test_red_ancla_log.py` + `test_red_correlacion_autoconstruccion.py`,
`-x`): 36/36 detectados. Los 4 mutantes anteriores afectados (CMC-M14, C12-M5, OB-M20, MOT-M11) se reescribieron y mueren.

## Hallazgos de la implementacion

* El confinamiento estricto (Landlock) niega `chmod`: `mkdir(..., 0o700)` ya fija el modo, `chmod` se tolera si falla.
* `AURA_ANCLA_DIR` lo fija un `autouse` en `entorno/control-plane/conftest.py` y en `walking-skeleton/tests/conftest.py`.
* `ciclo_autonomo.py` usaba ids posicionales `AUT-001`: con C3 (el review manual registra su `tarea_planificada`) colisionaban
  entre vueltas (`TareaNoElegible`). Ahora el id deriva de `fichero::simbolo`. **`ciclo_autonomo.py` esta en `_INTOCABLES`**:
  (SUPERSEDIDO: ver C1 abajo, revertido).
* Desviaciones del DP: (a) `tarea` se valida como cadena no vacia, no como `TA-…` (el review manual usa `T-A1`, `AUT-…`);
  (b) el review manual exige `id` y `fichero`; `origen` y `riesgo` valen `manual` por defecto.

## Limitaciones declaradas

1. **Autenticidad del origen NO garantizada**: ancla y log son del mismo uid; quien borra la cola puede reescribir el ancla.
2. **Restaurar log Y ancla juntos NO se detecta** (si solo el log, si). Fijado por `test_LIMITE_restaurar_log_Y_ancla_juntos_NO_se_detecta`.
3. **Despliegue sobre el log real**: sin ancla, `verificar_integridad_log` devuelve `integro: False` (`ancla_ausente`) a proposito.
   Hasta ejecutar `adoptar_ancla(directorio, por, motivo)` (decision explicita, deja `ancla_adoptada` en el log) el observatorio y
   los consumidores de `integro` lo veran como no integro. NO se ejecuto sobre el log real.
4. (SUPERSEDIDA, ver C2 abajo) El escritor ya no es fail-closed: escribe siempre; las operaciones que deciden sobre el historial (motor) si se bloquean.
5. Una caida entre el append y el ancla deja el ancla atrasada (reconocida; la adelantan `reparar_ancla` o el siguiente escritor).
6. Escritores manuales concurrentes siguen siendo posibles; el contrato hace correcta la atribucion, no los serializa.

---

# Correcciones posteriores (2026-10-26, segunda ronda)

Tres correcciones sobre `d68ff8d`. Todo `[EJEC]` en `pista-cp`, historiales sinteticos, `AURA_AUTOCONSTRUCCION_ESTADO` y
`AURA_ANCLA_DIR` en temporales, pruebas en serie. No se ejecuto `herramientas.mutar`. **Sustituye** a lo dicho arriba sobre
`ciclo_autonomo.py` (hallazgo 3) y sobre la limitacion 4 (el escritor ya no es fail-closed).

## C1 · `ciclo_autonomo.py` revertido (es `_INTOCABLES`, `orquestador.py:85`)

El fichero queda BYTE A BYTE igual que en `bf13a47` (`git diff bf13a47 -- entorno/control-plane/ciclo_autonomo.py` -> 0 bytes).
La colision de ids posicionales `AUT-001` se resuelve en el componente AUTORIZADO, `review.py`:
`clave_de_tarea_manual(tarea) = f"{id}@{sha256(f'{fichero}::{simbolo-o-buscar}')[:12]}"`. Un `review` manual sin `intento`
registra su `tarea_planificada` y correlaciona (`propuesta`/`diario`/`cambio_aplicado`) con ESA clave: dos hallazgos distintos
con el mismo id posicional no colisionan; el MISMO hallazgo reintentado produce la misma clave y el planificador lo reconoce
(`TareaNoElegible`, sin duplicar). Con `intento` (motor) el id sigue siendo el del planificador.
RED medido: con `ciclo_autonomo` de `bf13a47` y el `review` anterior, `test_al_terminar_queda_escrito_el_SIGUIENTE_TRABAJO`
fallaba (`'_muerta_1' is None`: la 2.a vuelta chocaba con `AUT-001`). GREEN sin tocar `ciclo_autonomo`. Pruebas nuevas:
`test_C3_dos_hallazgos_DISTINTOS_...`, `test_C3_dos_simbolos_del_MISMO_fichero_...`, control
`test_C3_CONTROL_el_MISMO_hallazgo_reintentado_...`. (`import hashlib` va dentro de la funcion: `test_red_veracidad_revisor`
cita la linea 63 de `review.py` y un import arriba la habria desplazado.)

## C2 · el escritor ya no se bloquea por el ancla

**Decision (orquestador):** `_registrar_sin_lock` NUNCA lanza por el ancla; siempre anade el evento (fsync). Solo CREA o ADELANTA
el ancla cuando es legitimo. Motivo: con `AnclaInconsistente` en el escritor, el cron de produccion (`despertar_rechazado` cada
30 min) habria fallado al desplegar y se habria perdido evidencia. Un fallo de E/S al escribir el ancla tampoco bloquea (queda
atrasada, visible). El diagnostico sale de UNA funcion (`_diagnosticar`) que usan el verificador y el escritor.

| # | Caso | Evento | Ancla | `integro` | `completitud` |
|---|---|---|---|---|---|
| 1 | log nuevo y vacio | escrito | genesis (seq 0, atomica) ANTES del 1.o; luego se adelanta | True | demostrada |
| 2 | log heredado con eventos y sin ancla | escrito | NO se crea (nunca en silencio) | False | no_demostrable |
| 3 | cadena interna rota | escrito | no se toca | False | no_demostrable |
| 4 | ancla perdida / corrupta / incompatible | escrito | no se sobrescribe (es evidencia) | False | no_demostrable |
| 5 | log no concuerda con el ancla (truncamiento, alteracion, otro historial) | escrito | NO se adelanta: deteccion permanente | False | truncada_o_alterada |
| 6 | integro y ancla valida (al dia o atrasada) | escrito | se adelanta | True | demostrada |
| 7 | caida durante la inicializacion | cubierto por 1: caida entre genesis y 1.o evento = "ancla atrasada" (log vacio sano); nunca "log sin ancla" | | True | demostrada |

`verificar_integridad_log` conserva sus claves y anade `completitud` (cadena, antes booleano) y `completitud_desde` (1; el `seq`
de la adopcion tras `adoptar_ancla`). `adoptar_ancla(directorio, por, motivo, reemplazar=False)`: exige `por`/`motivo`, cadena
valida, registra `ancla_adoptada {por, motivo, seq_adoptado, completitud_previa, ...}`; con `reemplazar=True` renombra el ancla
anterior a `<ancla>.reemplazada-<momento>` (nunca la borra). `reparar_ancla` solo adelanta un ancla ATRASADA; no adopta ni tapa
truncamientos y conserva `desde`.

**D · el motor se niega con historial no verificable:** `motor_autonomia.trabajar` llama a `cp.verificar_integridad_log` al
empezar; si no es integro registra (`_detener`) `ciclo_detenido` con motivo `historial no verificable: <motivo>`, sin planificar
ni promover (solo lee: la guardia AST sigue verde). No es parada normal: `aura.codigo_de_salida` = 2. El despertador y los
eventos pasivos siguen escribiendo.

**E · canal de diagnostico separado: EVALUADO Y NO IMPLEMENTADO.** Un canal aparte (otro fichero/evento con "por que no es
integro") seria una SEGUNDA fuente de verdad que puede divergir del log+ancla, y escribirlo desde el verificador crearia
recursion (verificar -> escribir -> cambia el log -> verificar). El diagnostico es determinista (log + ancla) y lo recalcula el
verificador cada vez; el motor ya deja el motivo en `ciclo_detenido`. Reevaluar solo si aparece un consumidor que no pueda
llamar al verificador.

Pruebas nuevas: `test_red_ancla_escritor.py` (30), 7 casos + cron simulado (3 `despertar_rechazado` sobre log heredado: no
fallan, sigue `no_demostrable`, sin ancla) + truncamiento permanente (8 escrituras) + ancla corrupta intacta + adopcion
(por/motivo, evento, ancla reemplazada conservada, `desde`) + `reparar_ancla` + motor (se niega heredado y truncado; CONTROL
integro trabaja; tras adoptar vuelve a trabajar) + caida inyectada entre genesis y 1.o evento. Pruebas previas que fijaban
`AnclaInconsistente` en el escritor se SUSTITUYERON por garantias mas fuertes (`..._ESCRIBE_pero_no_adelanta_el_ancla_y_la_deteccion_persiste`,
`test_la_escritura_del_ancla_es_atomica` ahora exige tambien que el evento se escriba).

## C3 · `test_red_aislamiento_estricto.py` (fallo AMBIENTAL)

Causa raiz: la sesion hereda `nice -n 12`; la prueba fijaba `setpriority(..., 7)` y `sched_setattr(nice=7)`. Bajar el nice exige
`CAP_SYS_NICE`: daba `EACCES`/`EPERM` incluso para el proceso PROPIO y en el CONTROL sin confinar, tambien en `bf13a47`. La prueba
usa ahora `min(19, max(nice propio, nice victima) + 1)`, siempre permitido. La garantia no cambia (confinado: ajeno EPERM, propio
OK; control: ajeno OK). Limite: a nice 19 el valor coincide con el actual, asi que el control "altera a la victima" no puede
demostrar el cambio de prioridad (si los de afinidad/politica).

## Resultados reales de la segunda ronda

| Comando | Exit | Resumen |
|---|---|---|
| `git diff bf13a47 -- entorno/control-plane/ciclo_autonomo.py` | 0 | vacio (0 bytes) |
| `cd entorno/control-plane && pytest -q -p no:cacheprovider test_red_ancla_escritor.py` | 0 | 30 passed |
| idem `test_red_ancla_log.py test_red_correlacion_autoconstruccion.py test_red_review.py test_red_veracidad_revisor.py` | 0 | 166 passed (junto al anterior) |
| `nice -n 0 ... pytest test_red_aislamiento_estricto.py -k planificacion` (nice efectivo 12, ya heredado) | 0 | 2 passed |
| `nice -n 7 ...` (nice efectivo 19) | 0 | 2 passed |
| suite completa `entorno/control-plane` (`AURA_AUTOCONSTRUCCION_ESTADO` y `AURA_ANCLA_DIR` en temporales) | 1 | 4 failed, 1558 passed, 3 skipped (220 s). Los 4 conocidos de datos/ruta: `capacidad_completada` x2, `frente_autonomo::test_en_el_plano_real_OB3_Y_OB2...`, `fuera_de_alcance_exigible::test_no_regresion_etiqueta...` |
| `cd walking-skeleton && pytest -q -p no:cacheprovider tests/unit/test_garantias_vigentes.py tests/unit/test_panel_progreso.py` | 0 | verde (primero 1818/1820: `C12-M5` y `OB-M20` apuntaban a la linea `base = {...}` del verificador, que cambio; reescritos y verificados) |
| `ls ~/.local/state/aura/anclas` | 2 | no existe |

La suite completa deja de fallar en `test_red_aislamiento_estricto` (antes 6 fallos incluyendo 2 ambientales) y en
`test_red_veracidad_revisor` (que cita la linea 63 de `review.py`).

## Mutantes de la segunda ronda: verificacion MANUAL (sin `herramientas.mutar`)

Copia en `/tmp/mutman/entorno/control-plane` (con `.claude/agents`, que `review.revisores_capaces` necesita). Por mutante: se
aplica `buscar -> sustituir` sobre el fuente de `pista-cp`, se corre `test_red_ancla_log.py test_red_ancla_escritor.py
test_red_correlacion_autoconstruccion.py test_red_review.py` con `-x` y se REVIERTE. Base verde (147 passed) antes y despues
de la tanda. El toml queda con 47 mutantes (36 + 11 nuevos; 5 reescritos porque su patron apuntaba a codigo reemplazado).

| Mutante | Garantia | Resultado |
|---|---|---|
| IL4 (reescrito) | el escritor crea el ancla en un log heredado (caso 2) | DETECTADO |
| IL8 (reescrito) | el escritor adelanta el ancla tras un truncamiento (caso 5) | DETECTADO |
| IL13 (reescrito) | los escritores no actualizan el ancla | DETECTADO |
| IL14 (reescrito) | la genesis no se escribe antes del primer evento (caso 7) | DETECTADO |
| RV2 (reescrito) | la propuesta del review sin correlacion | DETECTADO |
| IL17 | el escritor sobrescribe un ancla corrupta (caso 4) | DETECTADO |
| IL18 | el escritor pierde `completitud_desde` | DETECTADO |
| IL19 | `reparar_ancla` pierde `completitud_desde` | DETECTADO |
| IL20 | `adoptar_ancla` acepta `por`/`motivo` en blanco | DETECTADO |
| IL21 | `reemplazar=True` borra el ancla previa | DETECTADO |
| IL22 | `adoptar_ancla` no registra la completitud previa real | DETECTADO |
| IL23 | genesis con cola inexplicable se da por buena | DETECTADO |
| MH1 | el motor trabaja con historial no verificable | DETECTADO |
| MH2 | el motor comprueba tarde (no detiene) | DETECTADO |
| RV3 | clave de correlacion = id posicional (colision `AUT-001`) | DETECTADO |
| RV4 | la clave ignora el hallazgo dentro del fichero | DETECTADO |
| C12-M5 / OB-M20 (`walking-skeleton/mutaciones`, reescritos) | la cola truncada consta | DETECTADO (cada uno con su prueba) |

Los 31 mutantes restantes del toml no cambiaron de patron (comprobado: cada `buscar` aparece exactamente una vez); no se
re-ejecutaron en esta ronda.
