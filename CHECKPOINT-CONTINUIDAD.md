# CHECKPOINT DE CONTINUIDAD

**Actualizado:** 2026-08-15 · **Rama:** `worktree-m3-entry` · **HEAD:** `b664b42`
**`main` = `origin/main` = `d933a08`** (intacto — este incremento NO está integrado)

---

## 1 · Dónde está el trabajo

Incremento **«transportar la evidencia estructurada del fallo hasta la tarea derivada»**, opción A
aprobada por el CEO: se enriquece `oyente_de_transiciones`; **`desde_verificacion` NO se cablea**.

Commits de la rama, del más antiguo al más nuevo:

| Commit | Qué es |
|---|---|
| `19bb9db` | `feat` — el contexto viaja del veredicto a la tarea derivada |
| `f252ad9` | `fix` — defecto **D1** (el contexto apuntaba al fichero equivocado) + camino destructivo |
| `6ab99f9` | `docs` — retirada la condición 4 del criterio de aceptación (orden del CEO) |
| `b664b42` | `fix` — correcciones de la **segunda auditoría**: retirada la herencia de args |

**El árbol está limpio.** Todo lo corregido está commiteado.

## 2 · Estado exacto: qué falta para cerrar

El CEO fijó 9 condiciones antes del cierre. Situación:

| # | Condición | Estado |
|---|---|---|
| 1 | Auditoría independiente sobre la versión corregida | **EN VUELO** sobre `b664b42` — sin resultado todavía |
| 2 | Verificar que D1 quedó cerrado | delegado a esa auditoría (punto A del encargo) |
| 3 | Verificar que ningún camino vuelve destructivo un contexto incompleto | delegado (punto B) |
| 4 | Mutación y Quality Gate finales | **PENDIENTE** — no se ejecutan hasta que la auditoría termine |
| 5 | Retirar la condición 4 de las pruebas | HECHO (`6ab99f9`) |
| 6 | Medición final de los 7 casos | **HECHA** — ver §3 |
| 7 | No abrir dominio nuevo | respetado |
| 8 | No cablear `desde_verificacion` | respetado |
| 9 | No avanzar a objetivos autónomos / hardware / cambio de modelo | respetado |

**No integrar ni publicar.** Orden literal del CEO.

## 3 · Medición final de los 7 casos [EJEC] sobre `b664b42`

| Caso | Llega contexto | Ejecutable | Solo declarado | Resoluble sin LLM |
|---|---|---|---|---|
| 1 · auditor AUSENTE | sí | no | **sí** | NO |
| 2 · auditor AMBIGUO | sí | no | **sí** | NO |
| 3 · auditor DEGENERADO | sí | no | **sí** | NO |
| 4 · QA en rojo | sí | no | no | NO |
| 5 · diagnóstico | sí | no | no | NO |
| 6 · sin ejecutor para el responsable | sí | no | no | NO |
| 7 · programador en rojo | sí | no | no | NO |

**0/7 completables sin LLM.** Los 7 llegan con contexto —eso es nuevo y real—; ninguno se resuelve
sin razonar. Esta medición la quiere conservar el CEO tal cual: **no** buscar otro dominio ni fabricar
un caso mecánicamente resoluble para mejorarla.

## 4 · Conclusión que el CEO exige, literal, en el informe de cierre

> **Este incremento no aumenta todavía la autonomía de ejecución de AURORA; aumenta la calidad de la
> información que AURORA puede transportar hasta su siguiente capacidad de razonamiento.**

El siguiente Decision Package debe partir de esta evidencia real, no de la expectativa de que el LLM
ya pueda resolverla.

## 5 · Decisiones tomadas que NO se reabren

- **La herencia de args está retirada entera.** La introduje yo y era una regresión de gobierno: un
  cambio de lista roja **denegado** por el CEO engendraba una derivada que re-pedía la misma
  autorización con `intentos=0`, saltándose el umbral de la capacidad 017. Además no aportaba nada en
  el caso legítimo: repetía el cambio que ya había fallado.
- **Todo-o-nada en `fichero`/`buscar`/`sustituir`**, con contenido real tras `strip()`. `fichero` +
  `buscar` sin `sustituir` NO es contexto ejecutable: el dry-run devuelve `viable` y el efecto es
  **borrar el patrón**, y como eso no rompe pruebas el QA lo respaldaría. Lo incompleto viaja como
  `*_declarado`, que ningún ejecutor consume. **El CEO ordenó mantener esa separación estricta.**
- **El filtro vive en el punto de paso** (`solo_ejecutable_completo`, en el oyente), no en un llamador.
- **El contexto viaja por `args`, nunca por `evidencias`**: de la evidencia sale el identificador de la
  tarea derivada, así que contaminarla rompería la deduplicación.
- `CLAVE_CONTEXTO` y `contexto_de_correccion` viven en `estado_operativo.py`, **no** en
  `planificacion.py`: el contexto viaja dentro de la `Tarea`, y ponerlos en el planificador obligaba al
  Director a importar de allí (lo detecta `test_el_director_NO_conoce_la_planificacion`).

## 6 · Siguiente paso exacto

1. **Esperar la auditoría independiente** sobre `b664b42` y leer su veredicto.
2. Si **RECHAZA**: corregir, volver a auditar. No cerrar.
3. Si **ACEPTA**: ejecutar, **en solitario y en este orden**:
   ```bash
   cd walking-skeleton
   python3 -m herramientas.mutar mutaciones/contexto-derivado.toml   # esperado: 12 detectados, 0 supervivientes
   ./quality-gate.sh                                                  # esperado: PASS
   ```
   **Nada en paralelo con `herramientas.mutar`** (regla del CEO, 2026-08-09): muta los ficheros en el
   sitio, así que mientras corre el árbol NO contiene el código real. Si el proceso muere por SIGKILL,
   `git checkout -- <fichero>` recupera.
4. Entregar el informe de cierre en **cinco bloques** con la conclusión literal del §4.
5. **NO integrar. NO publicar.** Esperar orden del CEO.

## 7 · Riesgos abiertos

- La auditoría en vuelo puede volver a rechazar: **dos** anteriores ya lo hicieron, y las dos
  encontraron defectos reales que yo no había visto.
- Mis propios mutantes se desapuntan al editar el código (ya pasó con C4 y C7). Si la mutación reporta
  `NO_APLICADO`, el mutante **no protege nada**: hay que reapuntarlo, no ignorarlo.

## 8 · Deuda registrada, fuera de alcance por decisión del CEO — NO corregir

- `milestones/m3-entry/DEUDA-PANEL-BLOQUEO-SIN-MOTIVO.md`
- `milestones/m3-entry/DEUDA-ADR0014-MEMORIA-VACIA.md`

## 9 · Diferido por el CEO — no abrir sin acta

Incremento B (Experiencia Conversacional v1, DP escrito), 010–012 (Traductor Operativo), 015/016
(bloqueados por hardware), la decisión de hardware, y el cableado de `desde_verificacion`.
