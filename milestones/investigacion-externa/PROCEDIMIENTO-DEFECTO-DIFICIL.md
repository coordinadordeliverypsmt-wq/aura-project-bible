---
documento: "Procedimiento — usar la base de conocimiento externa ante un defecto difícil"
creado: 2026-10-26
origen: "Orden del CEO del 2026-10-26 (Bloque F): convertir la investigación externa en un procedimiento reutilizable"
autoridad: "NINGUNA sobre el sistema. Orienta la ingeniería; no autoriza cambios. Toda implementación sigue CLAUDE.md §2 (DP aprobado → RED → GREEN → mutación → QG → auditoría)"
---

# Procedimiento: defecto difícil → base de conocimiento → experimento → decisión

**Qué es un defecto difícil:**

- el diagnóstico directo no encuentra la causa tras reproducirlo;
- la corrección obvia rompe una garantía;
- el problema ya apareció antes, como en el patrón «declarado ≠ real» de `CLAUDE.md` §5.

**Regla de oro:** la base de conocimiento (`milestones/investigacion-externa/`) **sugiere** hipótesis; **nunca** las da
por buenas ni modifica nada. Un hallazgo externo, aunque sea `PRIORIDAD ALTA`, no es una autorización.

## Los 13 pasos

| # | Paso | Cómo, en AURA | Lo que **no** se hace |
|---|---|---|---|
| 1 | **Reproducir** el problema | En el entorno de desarrollo autorizado o en una copia (`git archive` o la copia aislada del arnés). Una prueba que falle es la reproducción mínima | Reproducir contra producción, `~/.aura`, `estado.json` o `eventos.jsonl` reales; desarmar PARADA |
| 2 | **Acotar con Graphify** | `graphify query|path|explain` desde la raíz del repositorio (`.claude/rules/orquestacion-herramientas.md`). Leer solo las rutas que señale | Lecturas masivas «por si acaso» |
| 3 | **Historial de defectos** | `CHECKPOINT-CONTINUIDAD.md` (buscar el síntoma), `decisiones/alertas/` (ALERTA-00x), `CLAUDE.md` §5, `.claude/ficha-evidencia.md` y los DP del área | Suponer que es nuevo sin buscarlo |
| 4 | **Consultar la base externa** | `INDICE.md` → «Índice por área» y la columna de decisión. Dentro de las fichas, buscar `## Hallazgos` e identificadores `HAL-NNN-n` (p. ej. `HAL-040-2`, donde NNN es el número de la ficha IE) cuyo **problema** coincida | Elegir un repositorio por popularidad o por nombre |
| 5 | **Verificar fuentes primarias** | Releer el código citado por su URL permanente (`blob/<SHA>/…#Lx`) y las **precondiciones** del mecanismo. Si el repositorio avanzó, fijar el nuevo SHA y anotar la diferencia | Dar por reproducido un benchmark publicado, o por cierto lo que solo dice el README |
| 6 | **Comparar con los contratos de AURA** | INV-9, ADR-0003 (lista roja), ADR-0014, D24/ADR-0001 (local-first, sin claves de terceros), motor único (ALERTA-005), solo capacidades registradas, PARADA, «prohibido crear un componente si existe equivalente» y «evidencia del uso real» (`CLAUDE.md` §4) | Relajar un contrato para que la idea encaje |
| 7 | **Diseñar un experimento que pueda refutar** | Hipótesis explícita y su caso de **control** (`CLAUDE.md` §5: «una prueba sin control no vale»), en copia aislada | Un experimento que solo pueda confirmar |
| 8 | **Métricas y criterios antes de probar** | Escribirlos en la ficha o en el DP **antes** de ejecutar: qué cifra, qué umbral y de dónde se deriva (ningún número sin derivación, regla del CEO 2026-08-04) | Fijar el criterio después de ver el resultado |
| 9 | **Revisión ECC y de seguridad** | `arquitecto-evaluador` («¿cabe?»), `security-reviewer` si toca autoridad, red, secretos o ejecución, y un auditor distinto del que propone | Que el proponente se audite a sí mismo |
| 10 | **Pedir autorización** | Decision Package con «Retorno sobre Tokens» → aprobación del CEO | Implementar «para probar» en el árbol vivo |
| 11 | **Ejecutar lo autorizado y registrar** | TDD → mutación (nada en paralelo con `herramientas.mutar`) → auditor de garantías → QG en una exportación limpia y en vivo → revisión independiente. Registrar comando, código de salida y log | Declarar PASS sin comando, salida y evidencia |
| 12 | **Devolver el resultado a la base** | Actualizar la ficha IE (sección del hallazgo: «probado», con fecha, SHA y resultado) **también si el experimento falló**, y el CHECKPOINT | Borrar los experimentos fallidos |
| 13 | **No declarar una solución permanente sin comportamiento verificado** | La capacidad queda **parcial** mientras haya evidencia pendiente (regla del CEO 2026-08-04). `capacidades.json` solo cambia con evidencia de una capacidad efectiva | Promover por documentación |

## Cómo se usa la base en la práctica

1. Partir del **problema**, no del repositorio: buscar en `INDICE.md` por área y en las fichas por la palabra del
   síntoma (por ejemplo «idempotencia», «replay», «correlación», «memoria», «firma»).
2. Tomar como mucho **dos o tres** hallazgos candidatos, de `PRIORIDAD ALTA` o `MEDIA`, y descartar los de clase
   `NO ADOPTAR` salvo que haya evidencia nueva.
3. Copiar a la ficha de evidencia del incremento **solo** el identificador del hallazgo y su criterio de aceptación.

**Clases de hallazgo:**

- **`PRIORIDAD ALTA`:** problema real de AURA, evidencia sólida y aplicabilidad concreta.
- **`PRIORIDAD MEDIA`:** útil, pero incierto.
- **`REFERENCIA`:** conocimiento útil sin aplicación actual.
- **`NO ADOPTAR`:** duplica algo existente, es incompatible, el riesgo es excesivo o la licencia o la procedencia son
  insuficientes.

**Grados de verificación** (de menos a más):

1. `[INFER]`
2. `[README]` o `[PAPER]` (declarado)
3. `[TESTS-DECLARADOS]`
4. `[CÓDIGO]` (inspeccionado en un SHA fijo)
5. `[REPRODUCIDO-POR-TERCEROS]`, con su fuente
6. **`[EJEC-AURA]`**: reproducido por nosotros en un experimento autorizado. **Solo este último es evidencia para
   decidir.**

## Límites

- La base es **memoria de ingeniería**, no fuente de verdad del sistema (ADR-0014, ADR-0023: la verdad es el log y el
  código).
- Puede estar **desactualizada**: cada ficha lleva su SHA y su fecha, y debe revisarse antes de usarla.
- **No contiene código externo**, solo citas cortas con su URL. Copiar código exige revisar la licencia y aprobar un DP.
