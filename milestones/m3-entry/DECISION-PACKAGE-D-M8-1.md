# DECISION-PACKAGE-D-M8-1 · Kill switch / motor único

> **2026-08-25.** No implementa nada. `aura_skeleton/` sin tocar.
> Evidencia D47: `[EJEC]` medido · `[LECT]` leído.

## 0 · Resultado en una línea

**La pregunta «¿B o C?» ya no procede: el contrato aprobado determina C.** Lo que queda no es
elegir, sino **autorizar** — y la autorización tropieza con un documento que no existe.

## 1 · Garantía afectada

**G-2** — con la parada de emergencia ARMADA, ninguna mutación persistente ocurre.
**G-3 #4** — ninguna operación no catalogada se ejecuta (`RN-2`), demostrada por su efecto.

## 2 · Defecto

Las rutas de soberanía no pasan por `authorize`, así que **no hay a quién preguntarle por el kill
switch**. No es que la comprobación falle: es que no existe el punto donde hacerla.

## 3 · Evidencia `[EJEC]`

Cuatro REDs en rojo, medidas: `test_g2_…no_detiene_el_olvido_del_modelo` ·
`test_g2_…no_detiene_la_refutacion` · `test_g2_…no_detiene_la_creacion_de_reglas` ·
`test_g3_el_olvido_se_ejecuta_sin_estar_catalogado`. Trabajo real en `core/modelo_usuario.py`,
`core/reglas.py` — **zona vetada**.

## 4 · Qué determina el contrato — y es más de lo que parecía

**`DP-D-M-8 §7`, plan de migración, APROBADO por el CEO el 2026-08-17** `[LECT]`:

| Fase | Contenido | Lo que fija |
|---|---|---|
| **F2 · Kill switch universal** | **«Paso 0 en el motor»** | el kill switch se comprueba **dentro del motor**, no en cada rama |
| **F3 · Ejecutor interno** | contrato `simular`/`aplicar` + catálogo con `sujeto` | *«el andamiaje del resto»* |
| **F4 · Migrar rutas** | **soberanía (borrar/refutar) → reglas (crear/desactivar) → señales** | el orden, *«de más peligrosa a menos»* |

Y la cabecera de §7 fija el principio: *«ordenado para que **el sistema esté protegido antes de ser
refactorizado** — al revés se migra a ciegas»*.

**Eso es C, literalmente:** enrutar por el motor, por fases y en un orden ya escrito. **B —enrutar
todo de una vez— contradice §7**, que separa F2, F3 y F4 precisamente para no migrar a ciegas.
No la marco descartada por contrato —el DP no la prohíbe en tantas palabras—, pero **no tiene
respaldo documental y §7 tiene el respaldo contrario**.

**`§4.3` ya retiró la única objeción de producto:** *«pasar por el motor no es lo mismo que pedir
confirmación»*. Enrutar no convierte «olvida esto» en una pregunta.

## 5 · Qué NO determina el contrato — y por qué me detengo

**No existe la especificación de F2/F3.** El único documento `ESPEC-*` del milestone es
`ESPEC-G-1-RUTA-UNICA-DE-MUTACION.md` `[EJEC]`. **`C-ESPEC-F2-F3` figura como bloqueo abierto** de
la Línea A, junto a `D-G1-2`, `D-G1-3`, `D-ORCH-5` y `AUDITORIA-DMOCHO-F0`.

Sin ESPEC de F2, «paso 0 en el motor» no dice **dónde** está ese paso 0, **qué** consulta, **qué
devuelve** cuando el kill switch está armado, ni cómo se comporta el dry-run. Escribirlo por mi
cuenta sería inventar el mecanismo que el proyecto se reservó especificar — el mismo conflicto que
`D-G1-1` ya planteó para G-1, y que se resolvió aprobando una ESPEC, no improvisándola.

**Segundo bloqueo, independiente:** **`F0` sigue `TECHNICALLY_COMPLETE / WAITING_FOR_INDEPENDENT_AUDIT`**
(`AUDITORIA-DMOCHO-F0` = `WAITING_FOR_QUOTA`). §7 exige la red antes de refactorizar, y esa red aún
no está auditada por alguien distinto de quien la escribió.

## 6 · Riesgos

- **Si no se decide:** el titular de `ALERTA-006` sigue vivo — *con la parada de emergencia armada,
  AURA sigue destruyendo datos del usuario*. **Es el bloqueo más grave de Línea A.**
- **Si se implementa sin ESPEC de F2:** se inventa el punto de control del motor y se fija por código
  algo que debía decidirse por contrato. Es «declarado ≠ real» dentro de la garantía madre.
- **Si se implementa antes de auditar F0:** se refactoriza contra una red que nadie ha verificado.

## 7 · Impactos

- **B1-B4:** ninguno. El Communication Plane no importa nada del producto `[EJEC]`.
- **Autoridad:** ninguno. No se crea vía nueva ni se toca `tareas_AUTO`.
- **Kill switch:** C lo consolida como **autoridad única** — hoy es una autoridad que media rama no
  consulta.
- **Motor único:** C es justamente lo que `ALERTA-005` exige. La alternativa A ya quedó descartada
  por crear una segunda vía.
- **REDs afectadas:** las 4 citadas. **Ninguna se modifica.**

## 8 · Decisión exacta requerida al CEO

**No «B o C».** Dos preguntas concretas:

1. **¿Se autoriza escribir `ESPEC-F2-KILL-SWITCH-UNIVERSAL` (paso 0 del motor) y se levanta
   `C-ESPEC-F2-F3`?** Es lo único que separa a D-M8-1 de poder ejecutarse.
2. **¿F2 espera a que `AUDITORIA-DMOCHO-F0` se cierre, o se adelanta?** §7 dice que la red va antes;
   la auditoría depende de la cuota, no de usted.

**No elijo ninguna de las dos.**
