# Cierre — Avisos de NODO-01 (R1) · 2026-10-18

**Estado: CONSTRUIDO Y VERIFICADO, SIN COMMIT** (commit prohibido por el acta: ver §3).
Autorización de construcción: `decisiones/2026-10-18-acta-supervision-nodo-01-R1.md` (orden ejecutiva 5.7.2).
Diseño: `milestones/m3-entry/PROPUESTA-ACTA-SUPERVISION-NODO-01.md` (rev. 2 + nota técnica del título del receptor).

## 1. Evidencia (copiada aquí porque el log original vive fuera del repo, en el directorio temporal del trabajo)

Quality Gate final (2026-10-18 19:29; ningún fichero de código/pruebas/mutación modificado después) — líneas literales:
```
  [ OK ] formato
All checks passed!
  [ OK ] lint
  [ OK ] tipado
3290 passed, 1 skipped, 17 xfailed in 537.47s (0:08:57)
  [ OK ] pruebas
8 passed in 0.07s
  [ OK ] contratos
QUALITY GATE: PASS — listo para integrar/ejecutar
exit=0
```
Mutación `walking-skeleton/mutaciones/avisos-nodos.toml`: **12 detectados, 0 sobreviven, 0 no aplicados** (`exit=0`;
diff de `aura_skeleton` idéntico antes/después). AU-M16 re-anclado y verificado aislado: 1/1.
Pruebas de R1: `tests/unit/test_avisos_nodos.py` + `tests/integration/test_avisos_nodos_cableado.py` (30).
Revisiones: `code-reviewer` APROBAR (tras corregir 1 MEDIO + 4 BAJOS) · `security-reviewer` APROBADO (tras tope de
tamaño) · `arquitecto-evaluador` CABE · `auditor-consistencia` sin discrepancias graves.
Demostración: caída al abrir · recuperación en sesión · sin duplicados en 3 turnos · receptor caído sin falsa caída ·
nodo nunca registrado sin aviso — todos conformes.

## 2. Conciliación con el roadmap

- `milestones/mapa-maestro/AURA_MASTER_DEVELOPMENT_MAP.md` y `capacidades.json`: **no mencionan NODO-01** ni la
  supervisión (solo, de forma lateral, «notificaciones de hogar E2E», línea 183). No registran ningún «cierre» de NODO-01
  que impida R1; el cierre previo es el de DP-NODO-01 v1 (infraestructura/latido, `RESULTADO-NODO-01.md`). R1 entra
  por su acta propia (apertura parcial y nominal de integración solo nodos → Centro).
- `PARADA` (armada) gobierna la autoevolución de AURORA (`entorno/control-plane/orquestador.py:317-334`); no afecta a
  esta construcción ni a commits de sesión.

## 3. P1 (commit local): BLOQUEADO

- **No existe autorización explícita** del CEO para este commit. `CLAUDE.md §3` describe CÓMO se hace un commit, no lo
  autoriza; `DOSSIER-DECISIONES-2026-10-18.md` §P1 es una propuesta sin respuesta registrada.
- **Prohibición expresa:** `decisiones/2026-10-18-acta-supervision-nodo-01-R1.md:15` («Tampoco commit/push/merge ni
  despliegues»), además de la regla repetida en el CHECKPOINT.
- **Aislamiento imposible sin absorber trabajo previo:** `core/nodos.py` y `adapters/receptor_nodos.py` están **enteros
  sin seguimiento** (contienen NODO-01 v1, ejecutado el 2026-10-04 y nunca commiteado), junto con otros 20 ficheros de
  NODO-01 v1 sin seguimiento; `orchestrator.py` (+1420/−137) y `composicion.py` (+231/−11) acumulan semanas de cambios
  previos, de los que R1 son unas pocas líneas.

**Opciones para el CEO:**
(a) commit local de **NODO-01 completo** (v1 + R1: los 26 ficheros de nodos/receptor/mDNS/identidad/pruebas/mutaciones
listados en el CHECKPOINT (p) + hunks de R1 en los 4 versionados) — exige además decidir si los hunks ajenos de
`orchestrator.py`/`composicion.py` entran; (b) commit local de **todo** el trabajo verificado pendiente (P1 completo del
dossier, sin push); (c) mantener sin commit.
