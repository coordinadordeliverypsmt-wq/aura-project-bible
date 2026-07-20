---
documento: "Architecture Review — M2.3 Exit (motor de automatización con dry-run)"
version: 1.0.0
autor: "CTO"
fecha: "2026-07-20"
estado: "Pendiente de aprobación del CEO"
---

# Architecture Review — M2.3 Exit

**Quality Gate: PASS — 202 pruebas + 8 contratos** (al entrar en M2.3: 190 + 8).

## Evidencia central: el dry-run no produce ningún efecto real

La comprobación no compara "el archivo sigue existiendo", sino una **huella completa del árbol**:
nombre, tamaño y `mtime` en **nanosegundos** de cada archivo. Detecta incluso una sobrescritura por
contenido del mismo tamaño.

| Operación simulada | Huella antes == después |
|---|---|
| `borrar_archivo` | ✅ idéntica |
| `escribir_archivo` (sobrescritura) | ✅ idéntica |
| `mover_archivo` | ✅ idéntica |
| Plan **no viable** (destino ocupado) | ✅ idéntica |

El último caso importa: un plan que se rechaza tampoco puede dejar rastro a medio camino.

## Restricciones exigidas por el CEO

| Restricción | Implementación | Evidencia |
|---|---|---|
| Dry-run obligatorio para toda operación que altere estado | El motor no intenta ejecutar sin plan viable | `test_dry_run_inviable_impide_la_ejecucion` |
| Ninguna acción roja sin previsualización **y** confirmación | El plan viaja hasta quien confirma | `test_la_confirmacion_recibe_la_previsualizacion` |
| Pruebas adversariales | 12 pruebas, todas intentando burlar el motor | — |
| D32 vigente | `mover_archivo` / `renombrar_archivo` siguen en roja | `test_toda_accion_destructiva_del_catalogo_exige_dry_run` |

## Decisiones de diseño

**Toda acción pasa por Permisos, incluidas las verdes.** Además de aplicar las listas, es lo que hace
que el **kill switch alcance al motor de reglas** y no solo al turno conversacional (RN-3). Verificado:
con el kill switch armado, la regla se detiene y el árbol queda intacto.

**La previsualización viaja a Permisos, nunca al adaptador.** El adaptador rechaza argumentos no
declarados (M2.1), así que `_previsualizacion` se añade solo al contexto de confirmación. Confirmar a
ciegas una acción destructiva no es consentimiento informado.

**Un adaptador que no sepa simular no puede alterar el estado.** Si la acción altera y el adaptador
carece de `simular`, la regla se detiene. No hay ruta que evite el dry-run por omisión de capacidad.

**`AdaptadorSimulable` es un Protocol separado, no una ampliación de `Adapter`.** Ese contrato acaba
de fijarse con prueba de firma (H1); ampliarlo obligaría a todo adaptador existente a implementar
simulación. La capacidad es opcional y **declarada**.

**Las comprobaciones previas se comparten entre simulación y ejecución** (`_comprobar_destructiva`).
Si divergieran, el dry-run podría aprobar algo que luego falla —o al revés— y la previsualización
dejaría de ser información fiable.

## Defectos encontrados durante M2.3

**En el sistema:** ninguno nuevo. Las protecciones de M2.2 (TOCTOU, ámbito, enlaces) se reutilizaron
sin cambios.

**En mis propias pruebas, dos:**
1. La prueba del kill switch tomaba la huella **antes** de armarlo, y el archivo disparador se crea en
   el mismo directorio: la huella cambiaba por el montaje de la prueba, no por un efecto real.
2. Reutilicé el nombre `st` para valores de tipo `stat_result` y `stat_result | None` en la misma
   función; mypy lo detectó.

Ambos son fallos de la prueba, no del sistema — pero los registro porque una prueba que falla por la
razón equivocada es tan inútil como una que pasa por la razón equivocada (criterio de T1).

## Caso de control

`test_control_la_automatizacion_si_ejecuta_cuando_todo_es_correcto`: con plan viable y confirmación,
la regla **sí** borra el archivo. Sin este caso, un motor que rechazara todo daría PASS en las ocho
pruebas de seguridad anteriores.

## Estado y siguiente paso

| Condición | Estado |
|---|---|
| Dry-run obligatorio | ✅ |
| Roja sin previsualización+confirmación imposible | ✅ |
| Kill switch alcanza al motor | ✅ |
| Sin efectos reales en simulación | ✅ evidencia por huella |
| D32 vigente | ✅ |

**M2.3 completada.** Con el motor de dry-run implementado y validado, **procede la reevaluación de
D32**: decidir si `mover_archivo` y `renombrar_archivo` pasan a lista verde condicionadas a
previsualización obligatoria, y si la Bible (6.4 §1) o la implementación deben enmendarse para
eliminar la divergencia.
