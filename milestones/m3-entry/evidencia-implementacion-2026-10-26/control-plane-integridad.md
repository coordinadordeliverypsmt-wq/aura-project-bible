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
  cambio minimo que el CEO debe ratificar.
* Desviaciones del DP: (a) `tarea` se valida como cadena no vacia, no como `TA-…` (el review manual usa `T-A1`, `AUT-…`);
  (b) el review manual exige `id` y `fichero`; `origen` y `riesgo` valen `manual` por defecto.

## Limitaciones declaradas

1. **Autenticidad del origen NO garantizada**: ancla y log son del mismo uid; quien borra la cola puede reescribir el ancla.
2. **Restaurar log Y ancla juntos NO se detecta** (si solo el log, si). Fijado por `test_LIMITE_restaurar_log_Y_ancla_juntos_NO_se_detecta`.
3. **Despliegue sobre el log real**: sin ancla, `verificar_integridad_log` devuelve `integro: False` (`ancla_ausente`) a proposito.
   Hasta ejecutar `adoptar_ancla(directorio, por, motivo)` (decision explicita, deja `ancla_adoptada` en el log) el observatorio y
   los consumidores de `integro` lo veran como no integro. NO se ejecuto sobre el log real.
4. Un escritor se NIEGA a seguir si el log no concuerda con su ancla (`AnclaInconsistente`): fail-closed.
5. Una caida entre el append y el ancla deja el ancla atrasada (reconocida; la adelantan `reparar_ancla` o el siguiente escritor).
6. Escritores manuales concurrentes siguen siendo posibles; el contrato hace correcta la atribucion, no los serializa.
