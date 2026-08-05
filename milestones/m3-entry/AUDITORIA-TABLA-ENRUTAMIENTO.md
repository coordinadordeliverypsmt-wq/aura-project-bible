# Auditoría independiente de la tabla de enrutamiento — VEREDICTO: RECHAZADA

**Fecha:** 2026-08-05 · **Paso 1 de 5** · Medido sobre 220 frases + las 77 de `bateria_memoria.json`.

**La dirección aprobada por el CEO se sostiene:** hacer explícita la precedencia y cambiar el dominio
por defecto de Memoria a Conversación General es correcto y ataca la causa raíz. **Lo rechazado son
las reglas de admisión (§2) y la definición de ambigüedad (§4).**

## Los 3 motivos bloqueantes

1. **No resuelve el defecto que lo motivó** `[EJEC]`. `«buenos días Aurora, ¿qué tienes pendiente para
   hoy?»` no coincide con ningún patrón de `_PAT_TAREAS` (`pendiente` no está). Con la tabla pasa de
   la ruta de Memoria a **Conversación General → LLM**. El defecto no se resuelve: **se mueve, y
   justo al dominio que va al modelo.** Otros 7 ejemplos de la propia tabla tampoco los captura nada
   («cancela el aviso de las 8», «¿por qué crees eso?», «¿cómo va todo?», «¿qué me dijiste ayer?»…).
2. **Rompería ADR-0014** `[EJEC]`. Cobertura sobre las 24 negativas de la batería oficial —las que la
   garantía existe para proteger—: **hoy 24/24 · con la regla de la tabla 0/24.** Van todas al LLM
   («¿cuál es la combinación de mi caja fuerte?»). Revierte la corrección N1-V4 sin declararlo, y
   `test_grounding_core.py` seguiría **en verde** porque sus 4 frases sí llevan marcador: falso PASS.
   Además, el proveedor por defecto ya responde *«Según lo que recuerdo: (sin recuerdos relevantes)»*
   a frases que hoy contesta el núcleo.
3. **No es determinista** `[EJEC]`. §4 fila 2 (gana la prioridad más alta) aplica SIEMPRE porque las
   prioridades son totales; §4 fila 3 (misma especificidad ⇒ aclarar) también, porque los dominios
   5-12 exigen dos señales cada uno. **Se activan a la vez y no hay desempate.** El propio ejemplo de
   §4 se contradice: dice que «¿qué has aprendido de mí?» debe preguntar, y su regla lo resuelve sin
   preguntar.

## Hallazgos adicionales

- **El mutante «irrenunciable» del DP §8.3 NO EXISTE** `[LECT]`: ninguno de los 31 TOML ataca el bloque
  de ADR-0014. Hay que escribirlo ANTES, no darlo por hecho.
- **59 de 220 frases (27 %) cambian de destino.** Solo 51 son el cambio deseado; **8 no están
  declaradas** y pierden su superficie determinista («mis reglas», «novedades», «por qué dices eso»…).
- **4 inversiones de precedencia** respecto al comportamiento actual, con frase testigo cada una.
- **«Sujeto = AURORA» no existe como señal.** Solo hay una denylist de 7 regex que falla en ambos
  sentidos: «¿qué has aprendido **sobre mí**?» vuelca el Plan de Formación con notas internas, y
  «¿qué has aprendido **de ti**?» —que SÍ es sobre AURORA— queda bloqueada.
- **Ruta muerta**: los dominios 8 y 9 dependen de fuentes hoy opcionales. Un router «función pura
  texto→dominio» enrutaría a un dominio sin fuente. Debe devolver **lista ordenada** de candidatos.
- **`--debug` no existe**: §5 lo presenta como disponible. Solo hay `--verificar`, `--gobierno`, `--servir`.

## Las 10 correcciones exigidas (ninguna cambia los 5 criterios del CEO)

**C1** Separar la puerta ADR-0014 del enrutado: la ausencia de recuerdos no es un dominio, es una
condición sobre la ruta al LLM. Punto de partida medido: *pregunta Y objeto personal Y 0 hits* →
17/24 sin sobreproteger ninguna de las 11 frases del CEO. **Hay que llegar a 24/24, y como PRUEBA.**
**C2** Declarar o impedir los 8 cambios de destino no previstos.
**C3** Declarar las 4 inversiones de precedencia con su frase testigo.
**C4** Corregir §4 con un criterio de desempate único, y **construir el mecanismo de aclaración**, que
no existe. `_DESAMBIGUAR` resuelve el referente dentro del Modelo de Usuario, no el dominio.
**C5** Especificar «sujeto = AURORA» como señal positiva y verificable; arreglar `_RE_OBJETO_AJENO`.
**C6** Decir explícitamente que el dominio 13 **sigue ejecutando `recall`** y alimentando el contexto;
si no, AURORA se vuelve amnésica para toda pregunta personal sin marcador.
**C7** El router devuelve **lista ordenada** de dominios admitentes, no uno solo.
**C8** Escribir el mutante irrenunciable + M-A/M-B/M-C y la prueba RED sobre las 24 negativas **antes**
de tocar el orquestador.
**C9** `--debug`: construirlo o reescribir §5.
**C10** Grabar el corpus de equivalencia **antes**: `bateria-intencion.json` (172 casos) existe y
**no lo lee ninguna prueba**, ampliado con las frases de ataque de esta auditoría.

> **Coste de aceptarlo ahora: reescribir dos secciones de un documento.**
> **Coste de descubrirlo tras implementar: revertir un refactor de 13 superficies con ADR-0014 roto y
> sin ninguna prueba que lo señale.**
