# Tabla de enrutamiento de intenciones — para revisión del CEO

**Estado: RECHAZADA como contrato de implementacion por auditoria independiente (2026-08-05).**
**La DIRECCION aprobada por el CEO se sostiene; lo que se rechaza son las REGLAS DE ADMISION (§2) y
la definicion de ambiguedad (§4). Ver `AUDITORIA-TABLA-ENRUTAMIENTO.md` — 10 correcciones exigidas.**

> **AVISO — NO IMPLEMENTAR ESTA TABLA TAL CUAL.** Tres defectos medidos `[EJEC]`, cada uno bloqueante:
> 1. **No resuelve el defecto que la motivo.** *"que tienes pendiente"* NO coincide con ningun patron
>    del dominio 8: con esta tabla acaba en el LLM. La afirmacion en negrita de §2 («El caso del CEO,
>    resuelto») **era FALSA**: la escribio APUS-5 sin ejecutarla. 8 de los 24 ejemplos de la propia
>    tabla no los captura ningun patron existente.
> 2. **Romperia ADR-0014.** La regla del dominio 12 («pregunta Y marcador») lleva la garantia de
>    **24/24 a 0/24** sobre las negativas de `bateria_memoria.json`, revirtiendo la correccion N1-V4
>    sin declararlo. Ninguna prueba ni mutante actual lo detectaria.
> 3. **No es determinista.** §4 filas 2 y 3 se activan a la vez en todos los solapes reales medidos y
>    no hay desempate; la aclaracion resulta **inalcanzable**; «sujeto = AURORA» no esta definido.
**La fase de arquitectura queda CERRADA: no se admiten más cambios de diseño.**

### Criterios definitivos fijados por el CEO al aprobar

1. El enrutado es **explícito y determinista**. Esta tabla es su contrato.
2. **Ambigüedad** = más de un dominio admite el turno y ninguno tiene precedencia objetiva ⇒ **pedir
   aclaración**. **Sin puntuaciones ni modelos probabilísticos.**
3. **Memoria solo se activa** ante referencia al pasado compartido o a recuerdos. **Nunca captura una
   pregunta por defecto.**
4. **Conversación General es el dominio de cierre, nunca Memoria.** Sin inventar hechos ni recuerdos:
   **ADR-0014 sigue siendo obligatorio**.
5. Las **acciones** mantienen prioridad sobre las consultas **solo cuando la intención de ejecutar sea
   INEQUÍVOCA**. *(Refuerza el §1: ante duda entre acción y consulta, se pide aclaración.)*

**Pasos restantes, exclusivamente técnicos:** auditoría de la tabla → implementación →
RED/GREEN/MUTACIÓN → auditoría independiente → integración.
**Después, el CEO evaluará AURORA solo por la experiencia de uso diario.**

Refactor de la cascada existente, no componente nuevo (condición 1). Hace explícita la precedencia
que hoy fija el orden en que se escribieron las líneas.

---

## 1 · Principios de precedencia

1. **Las ACCIONES ganan a las CONSULTAS.** Una acción mal leída como consulta **pierde su efecto** y
   el usuario cree que se hizo algo que no se hizo. Una consulta mal leída como acción es peor aún,
   por eso las acciones exigen marcador **y** dominio.
2. **De lo más específico a lo más general.** Un dominio que exige dos señales precede a uno que
   exige una.
3. **El dominio por defecto es Conversación General**, nunca Memoria (condición 2).
4. **Ambigüedad ⇒ preguntar, no adivinar** (condición 3). Definición determinista en §4.
5. **Toda decisión de enrutado se audita, y no se muestra al usuario en modo normal** (condición 4).

---

## 2 · La tabla

Prioridad 1 = se evalúa primero. `[LECT]` — los patrones actuales deben verificarse contra el código
antes de implementar; los dominios y su orden son la propuesta a aprobar.

| # | Dominio | Tipo | Ejemplos del usuario | Regla de admisión | Fuente que responde |
|---|---|---|---|---|---|
| 1 | **Olvidar / refutar** | acción | «olvida que me gusta el café», «eso no es cierto» | marcador de olvido **Y** referencia a algo sabido | Modelo de Usuario |
| 2 | **Cancelar automatización** | acción | «cancela el aviso de las 8», «ya no quiero esa regla» | marcador de cancelación **Y** mención del dominio de reglas | Almacén de Reglas |
| 3 | **Crear automatización** | acción | «cada vez que llegue a casa enciende la luz» | estructura condicional **Y** acción sobre dispositivo | Almacén de Reglas |
| 4 | **Aprobar / decidir** | acción | «sí, apruebo», «no lo hagas» | **solo si hay una decisión pendiente abierta** | Buzón de decisiones *(Pieza 2, no existe aún)* |
| 5 | **Modelo de Usuario — consultar** | consulta | «¿qué sabes de mí?», «¿por qué crees eso?» | pregunta **Y** sujeto = el usuario | Modelo de Usuario |
| 6 | **Automatizaciones — consultar** | consulta | «¿qué automatizaciones tengo?» | pregunta **Y** mención de reglas | Almacén de Reglas |
| 7 | **Notificaciones** | consulta | «¿qué ha pasado?», «¿tengo avisos?» | pregunta **Y** marcador de novedad | Centro de Notificaciones |
| 8 | **Estado Operativo** | consulta | «¿en qué estás trabajando?», «**¿qué tienes pendiente?**» | pregunta **Y** sujeto = trabajo de AURORA | Estado Operativo |
| 9 | **Centro de Gobierno** | consulta | «¿por qué estás bloqueada?», «¿cómo va todo?» | pregunta **Y** sujeto = situación de AURORA | Centro de Gobierno |
| 10 | **Capacidades** | consulta | «¿qué puedes hacer?», «¿qué capacidades tienes?» | pregunta **Y** sujeto = habilidades de AURORA | Registro de capacidades |
| 11 | **Plan de Formación** | consulta | «¿qué has aprendido?» *(sobre sí misma)* | pregunta **Y** sujeto = aprendizaje de AURORA | Plan de Formación |
| 12 | **Memoria Episódica** | consulta | «¿qué me dijiste ayer?», «¿qué acordamos?» | pregunta **Y** referencia explícita al **pasado compartido** | Memoria · **ADR-0014 aquí** |
| 13 | **Conversación General** | — | «buenos días», «gracias», «¿cómo estás?» | **por defecto: todo lo que nadie reclamó** | Asistente Conversacional |

**El caso del CEO, resuelto:** *«buenos días Aurora, ¿qué tienes pendiente para hoy?»* → **dominio 8**
(pregunta + sujeto = trabajo de AURORA). Hoy cae en el 12 y responde «no tengo ningún recuerdo».

---

## 3 · El cambio esencial

**Ninguna regla de admisión es «es una pregunta».** Toda consulta exige pregunta **Y** sujeto/dominio.
Hoy `_es_consulta_de_memoria` termina en `or _es_pregunta(texto)` y por eso captura todo lo que nadie
reclamó. En la tabla, ese cajón lo ocupa **Conversación General**, y Memoria pasa a exigir referencia
explícita al pasado compartido.

**ADR-0014 no se toca, se delimita.** Cuando el dominio 12 se activa y no hay recuerdos, la respuesta
sigue siendo determinista y sin LLM. Lo que cambia es **cuándo** se llega ahí.

**En el dominio 13 el LLM redacta, pero nunca afirma hechos del sistema.** Los hechos siguen viniendo
del Core (ADR-0014 §1). Un saludo no necesita hechos; si el usuario pide un dato, el router lo habrá
mandado a su dominio.

---

## 4 · Ambigüedad: qué significa «no clasificar con suficiente confianza»

Un router determinista **no tiene puntuación probabilística**, así que «confianza» debe definirse de
forma verificable. Propuesta:

> **Hay ambigüedad cuando dos o más dominios admiten el turno y ninguno es más específico que el otro.**

Es medible, reproducible y comprobable con una prueba. Tres casos:

| Situación | Decisión |
|---|---|
| Un solo dominio admite | Se enruta ahí |
| Varios admiten, **uno tiene prioridad más alta** | Gana el de prioridad más alta (precedencia declarada) |
| Varios admiten **con la misma especificidad**, o el turno mezcla acción y consulta | **Se pide aclaración** |

Ejemplos reales que deben pedir aclaración:
- *«¿qué has aprendido de mí?»* → dominio 5 (sobre el usuario) **y** 11 (aprendizaje de AURORA).
  Es la frase que la auditoría destapó respondiéndose mal. **Debe preguntar**, no elegir.
- *«¿qué está pasando con mi pedido?»* → 7 (novedades) **y** nada de AURORA. Debe preguntar o pasar a 13.

Redacción de la aclaración: una sola pregunta corta, sin jerga ni nombres de módulos
(*«¿te refieres a lo que sé de ti, o a lo que he aprendido yo trabajando?»*).

**Riesgo declarado:** preguntar demasiado también rompe la conversación. **Debe medirse** cuántos
turnos de un uso real acaban en aclaración; si es alto, se ajusta la tabla, no el principio.

---

## 5 · Auditoría del enrutado (condición 4)

Cada turno registra en `audit.jsonl`: dominio elegido · dominios que admitían · si hubo ambigüedad ·
regla que decidió. **No se imprime en modo usuario**; visible con `--debug`.

Esto convierte cada queja futura del CEO en un dato: se podrá ver **por qué** el router decidió lo que
decidió, en vez de deducirlo. Es la instrumentación que hoy falta para que la evidencia de uso sea
accionable.

---

## 6 · Lo que hay que verificar antes de implementar

1. **Los patrones actuales de los 12 detectores** `[LECT]` — hay que leerlos y mapearlos uno a uno a
   esta tabla. Ningún dominio puede quedar sin cobertura previa.
2. **Prueba de equivalencia** (exigida en el DP): corpus grabado ANTES, y la lista de cambios
   esperados declarada por adelantado. **El único cambio deseado es que las preguntas que hoy caen en
   Memoria por descarte dejen de hacerlo.** Todo lo demás debe permanecer idéntico.
3. **El mutante irrenunciable** «el LLM responde cuando no hay recuerdos» debe seguir muriendo.

---

## 7 · Preguntas abiertas para el CEO

1. **Dominio 4 (aprobar/decidir)**: depende de la Pieza 2, que no existe. ¿Se reserva el hueco en la
   tabla o se omite hasta entonces? *(Recomendación: reservarlo — la tabla es el sitio natural y
   documenta la dependencia.)*
2. **«¿qué has aprendido de mí?»**: ¿aclaración, o se decide que el usuario casi siempre quiere el
   dominio 5 y se enruta ahí? *(Recomendación: aclaración. Es la frase que ya se respondió mal.)*
3. **Umbral de aclaración**: ¿se acepta empezar preguntando de más y relajarlo con evidencia de uso,
   o al revés? *(Recomendación: preguntar de más al principio — es coherente con «preferible
   preguntar que contestar algo incorrecto».)*
