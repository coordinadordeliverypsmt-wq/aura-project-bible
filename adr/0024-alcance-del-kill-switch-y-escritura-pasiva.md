---
adr: 24
titulo: "El alcance del kill switch: qué detiene PARADA, y qué es una escritura pasiva"
estado: accepted
fecha: 2026-09-09
decide: "CEO (D-A006-2, Opción B)"
propone: "CTO"
supersede: null
relacionado: "Bible 5.3 §5 / RN-3 (kill switch), ALERTA-005 (motor único), ALERTA-006, ADR-0003 (HITL), ADR-0014 (Core como autoridad), D-A006 (decisiones/2026-09-09-D-A006-decision-package.md)"
---

# ADR-0024 — El alcance del kill switch

## Principio

> **`PARADA` detiene la ejecución, no la conversación.** Bloquea toda acción gobernada por el Motor
> Único; no convierte en acción ejecutable todo procesamiento conversacional.

## Contexto

`Bible 5.3 §5` y `RN-3` dicen: *«cuando está activado, **NINGUNA acción** se ejecuta, sin excepciones»*.
La auditoría de `ALERTA-006` (2026-09-09) midió que la frase admite dos lecturas legítimas, y que la
diferencia entre ellas no es técnica:

**La palabra que decide es «acción», y en este proyecto no es neutra.** Es vocabulario del `CATALOGO`
de `permissions.py`: lo que pasa por el motor con permisos y HITL. Escribir memoria conversacional
**no es una acción catalogada**. De ahí:

- lectura **literal** → `PARADA` no obliga a bloquear la escritura conversacional;
- lectura por **intención** (*«cómo se detiene todo»*, `5.3`) → sugiere que sí.

Dos hechos medidos `[EJEC]` que obligaron a decidir:

1. **No hay guarda de kill switch al inicio del turno.** `_sistema_detenido()` se comprueba en **un
   solo punto** del orquestador y solo para peticiones de olvido y refutación.
2. **`orchestrator.py` escribe memoria persistente sin pasar por el motor**, y `write` está declarado
   mutante de `memory.py` en `architecture_manifest.toml`.

La alternativa —detener el turno completo— se evaluó y **se descartó por su consecuencia de producto**:
convertiría `PARADA` en un apagado del sistema, y el usuario perdería la única superficie por la que
preguntaría qué está ocurriendo. Una parada de emergencia que impide preguntar por la emergencia es
peor herramienta de seguridad, no mejor.

## Decisión

1. **`PARADA` bloquea las acciones ejecutables y destructivas gobernadas por el Motor Único.** Sin
   cambios: es lo que ya hacía, y sigue siendo la barrera.

2. **`PARADA` NO es un apagado de la conversación.** Con la parada armada, AURA puede seguir
   respondiendo y registrando lo que se dijo.

3. **«Escritura pasiva» se define mecánicamente, como whitelist cerrada de `kind`.** Vive en un solo
   sitio —`contracts.KINDS_PASIVOS`— y hoy contiene exactamente dos: `episodica` (lo que el usuario
   dijo) e `historico` (la orden que pidió, que ni siquiera vuelve en un `recall`, ADR pendiente de su
   propio registro en `D-A006`).

   La definición es **fail-closed**: lo que no puede demostrarse pasivo se trata como NO pasivo. Un
   `kind` nuevo queda bloqueado con `PARADA` armada hasta que alguien lo declare. El olvido no concede.

   *Por qué mecánica y no descriptiva:* «conversación» no es un criterio verificable. Sin uno, cada
   escritura futura la resolvería quien la escribiera — y así nacen las rutas alternativas que
   `ALERTA-005` prohíbe.

4. **Esta decisión NO autoriza `memory.write` fuera del motor.** Lo acota; no lo legitima. Queda
   expresamente registrado que:
   - `memory.write` es una **mutación persistente**;
   - hoy está **fuera del motor, de los permisos y del kill switch**;
   - la Opción B **no significa** «toda escritura conversacional está permitida»;
   - su tratamiento definitivo sigue abierto y **no se resuelve en esta ADR**.

5. **No se crea autoridad nueva.** `memory.write` no pasa a ser acción del motor, `persistencia_autorizada`
   no se amplía, y ningún contrato cambia.

## Consecuencias

**Positivas.** La frontera deja de ser interpretable: es una lista de dos entradas en un solo fichero,
con prueba. `PARADA` conserva su función sin apagar el producto. Y la ausencia de autorización implícita
para `memory.write` queda escrita, de modo que nadie pueda alegarla más adelante.

**Negativas / límites.** El residual persiste: un turno sigue escribiendo memoria con la parada armada.
La whitelist lo acota a lo conversacional, pero no lo elimina. **Se declara como límite conocido, no
como problema resuelto.**

**Verificable.** `tests/unit/test_parada_escritura_pasiva.py` fija los **dos lados** —que lo pasivo sigue
funcionando con la parada armada y que lo no pasivo no ocurre—, porque una prueba que solo comprobara el
segundo se pasaría dejando a AURA muda. Mutación: `mutaciones/parada-escritura-pasiva.toml`,
**5 detectados · 0 supervivientes** `[EJEC]`.

**Coste.** Cero dependencias. La guarda son cuatro líneas en `_finalizar_turno` y una whitelist de dos
entradas en `contracts.py`.

## Alternativas descartadas

- **Opción A · `PARADA` detiene el turno completo.** Compatible con la lectura por intención, pero
  convierte la parada de emergencia en un apagado del producto. **ALTERNATIVA RECHAZADA — COSTE DE
  PRODUCTO**, no de seguridad.
- **Opción B tácita, sin definir «pasivo».** Es la peor de las tres: conserva el hueco y además lo
  normaliza, porque deja la frontera al criterio de quien escriba la siguiente línea.
