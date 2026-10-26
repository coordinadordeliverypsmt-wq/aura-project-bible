---
documento: "Medición del turno cognitivo en HC-1 — dos campañas, la primera refutada por la segunda"
tipo: "Evidencia de medición (no es un Decision Package, no decide nada)"
fecha: 2026-09-15
mantenido-por: "APUS-5 (CTO)"
perimetro: "milestones/m3-entry/DP-COGNICION-LOCAL-Y-RENDIMIENTO.md §3 (métricas), §8 (criterios de salida) y §9 (qué está permitido tocar)"
---

# Medición del turno cognitivo en HC-1

> **LEE ESTO PRIMERO.** Este fichero documenta un error de medición propio, cómo se detectó y qué se
> hizo con él. La **campaña 1** afirmó que recortar el sobre del JSON y pedir brevedad acortaba el turno
> cognitivo un ~60 %. **Era falso.** La **campaña 2**, con la máquina sana y un protocolo que controla la
> caché de Ollama, no encontró ninguna mejora demostrable, y **el cambio se revirtió entero**:
> `modules/providers_real.py` y sus pruebas vuelven a ser idénticos a `6dad6af`.
> Se conserva todo —datos crudos incluidos— porque el proyecto ha pagado ocho veces el patrón
> «declarado ≠ real», y esta vez el declarante fue el propio CTO.

**Clasificación de evidencia** (D47): todo lo de abajo es `[EJEC]`, medido contra Ollama real con
`qwen2.5:0.5b` (Q4_K_M, 494 M), el único modelo instalado. Las métricas salen de la propia API
(`load_duration`, `prompt_eval_*`, `eval_*`, `total_duration`): **no se estima nada**.

---

## Campaña 1 — REFUTADA (`campana-1-refutada/`)

Una sola pregunta (`por que el cielo es azul?`), repetida cinco veces, antes y después del cambio.

| corrida | tokens generados | turno | ingesta | tok/s generación |
|---|---|---|---|---|
| antes 1 | 63 | 211,4 s | 160 tok / 1,1 s | 0,43 |
| antes 2 | 143 | 313,7 s | 160 tok / 1,3 s | 0,46 |
| después 1 | 35 | 206,8 s | 162 tok / 110,3 s | 0,48 |
| después 2 | 53 | 118,6 s | 162 tok / 2,6 s | 0,46 |
| después 3 | 34 | 81,7 s | 162 tok / 3,5 s | 0,44 |

Conclusiones que se publicaron a partir de estos datos, **las tres falsas**:

1. «La ingesta es el 0,5 % del turno» y «la cifra del DP (3,5 tok/s) no se reproduce».
2. «La latencia del turno es ~2,2 s por token generado».
3. «El turno cognitivo es un ~60 % más corto tras el cambio».

### Por qué eran falsas — tres contaminaciones que se sumaron

- **Caché de prompt de Ollama.** Repetir el prompt idéntico permite al servidor reutilizar el prefijo ya
  evaluado, y la ingesta parece instantánea. La primera llamada de la serie —la que el vigilante de
  memoria de la sesión abortó— ya había dejado el prefijo en caché. La prueba de que era caché y no
  rendimiento: «después 1», la primera con el system prompt **nuevo**, pagó **110,3 s** de ingesta.
  Se interpretó entonces como paginación. Era un fallo de caché.
- **Presión de memoria.** La sesión de construcción ocupaba ~3 GB de los 3,6 GiB; la máquina paginaba.
  La generación a 0,45 tok/s es la de una máquina degradada: sana genera a ~2 tok/s.
- **n = 1 pregunta.** Con temperatura por defecto el modelo emite longitudes muy distintas ante la misma
  pregunta (63 y 143 tokens en dos corridas seguidas). Una sola pregunta no mide una distribución.

La estabilidad de la tasa (0,43–0,48) se presentó como prueba de que «la máquina no cambió». Era
cierto **dentro** de esa sesión, y precisamente por eso no detectaba que la sesión entera estaba
degradada.

### Cómo se detectó

La máquina se reinició entre sesiones. Al repetir con el sistema limpio, la primera corrida dio
**3,6 tok/s de ingesta y 2,46 tok/s de generación** —las cifras del DP §2— y no las de la campaña 1.

---

## Campaña 2 — la válida (`campana-2-bateria/`)

### Protocolo

- Máquina recién reiniciada, sin swap en uso, sin otros procesos pesados.
- **Seis preguntas distintas**, verificadas antes de medir contra el enrutado real del producto:
  `_es_turno_cognitivo` verdadero, referente `mundo`, sin dominio sensible, sin acción y no resolubles
  por la aritmética determinista. Una primera lista incluía «¿quién escribió Don Quijote?» (desviada por
  dominio sensible `personas_reales`) y «¿cómo funciona el motor de un coche?» (cae en la puerta de
  ADR-0014): se sustituyeron, porque medirlas habría sido medir un camino que el usuario no recorre.
- **Calentamiento por variante**, no contado: cambiar el system prompt invalida el prefijo cacheado. Tras
  calentar, todas las variantes quedan en la condición real de una conversación —mismo system, pregunta
  nueva—.
- Tres variantes, en serie, un turno cada vez:
  - `legado` — el prompt de `6dad6af`: pide `intent`, `action`, `args`, `say`.
  - `breve` — sin `intent`/`args`, con «Responde BREVE: dos frases como máximo».
  - `entregado` — sin `intent`/`args`, sin brevedad (el que se llegó a dejar en el árbol).

### Resultados — tokens generados, la métrica que no depende de caché ni de contención

| caso | legado | breve | entregado |
|---|---|---|---|
| definición («¿qué es la fotosíntesis?») | 68 | 54 | 57 |
| explicación («¿por qué el cielo es azul?») | 43 | 50 | 29 |
| concepto («¿qué es un agujero negro?») | 32 | 78 | 69 |
| palabra («¿qué significa resiliencia?») | 42 | **333** | 80 |
| incierta («¿qué es la materia oscura?») | 91 | 43 | 51 |
| hipótesis («¿qué pasaría si la luna desapareciera?») | 41 | 43 | **199** |
| **mediana** | **42,5** | 52 | 63 |
| máximo | 91 | 333 | 199 |
| turno total — mediana | 34,9 s | 38,2 s | 45,6 s |
| turno total — máximo | 57,3 s | **189,1 s** | 131,9 s |
| `intent` emitido | 5/6 | 0/6 | 0/6 |
| JSON válido | 6/6 | 6/6 | 6/6 |

**Ingesta** (corregido tras la auditoría independiente, que recalculó estas cifras y no las encontró en
los ficheros). En los 18 turnos medidos, con el prefijo ya caliente, la ingesta de ~160 tokens fue de
**3,1 a 11,7 s**. Solo **dos** llamadas de los datos conservados fueron frías: `legado-calentamiento`
(**38,3 s**) y `entregado-calentamiento` (**22,8 s**). El calentamiento de `breve` (**2,5 s**) **no** fue
frío: la variante con brevedad era la del árbol en la primera corrida tras el reinicio, que ya había
dejado ese mismo prefijo en caché. Esa primera corrida midió **44,2 s** de ingesta en frío, pero su
fichero se sobrescribió al repetir el caso y **no está en `campana-2-bateria/`**: la cifra se cita solo
como observación no conservada, no como dato.

### Conclusiones

1. **Ninguna variante acorta el turno de forma demostrable.** Con n = 6 la varianza propia del modelo lo
   domina todo. La única señal —débil— apunta en contra: las dos colas largas aparecieron solo en las
   variantes modificadas.
2. **Quitar `intent` no ahorra tokens.** El modelo legado lo emitía en 5 de 6 turnos, pero sin él no
   genera menos: redistribuye en `say`. El razonamiento «son tokens que el código tira» era correcto
   sobre el sobre y **falso sobre el total**.
3. **La instrucción de brevedad no mostró efecto.** El disparo más largo de toda la campaña (333 tokens)
   ocurrió con ella puesta.
4. **La cifra de ingesta del DP sí se reproduce en frío**: 160 tokens en 44,2 s de la corrida no
   conservada dan 3,6 tok/s, y `legado-calentamiento` —conservada— da 156 tokens en 38,3 s, 4,1 tok/s. La
   campaña 1 la negó por la caché.
5. **La caché de prefijo importa en uso real, y afecta a la palanca 1 del DP.** En una conversación el
   system prompt es constante y queda cacheado, pero el buffer de diálogo va delante de la pregunta y
   **cambia en cada turno**, así que cada turno re-evalúa todo lo que hay desde el buffer. Con 6 turnos de
   buffer, esa ingesta crece. **No se ha medido en sesión multiturno**: queda como la medición que
   falta para decidir si la palanca 1 tiene recorrido.

### Decisión tomada con esta evidencia

El DP §8 exige como criterio de salida *«latencia del turno cognitivo reducida de forma medida en
HC-1»*. **No se cumple**, así que el cambio no se conserva: `providers_real.py`,
`tests/unit/test_frontera_cognitiva.py` y `tests/unit/test_contrato_cognitivo.py` se restauraron al
contenido de `6dad6af`, y su catálogo de mutación se retiró. El catálogo existente del contrato
cognitivo (`mutaciones/contrato-cognitivo.toml`) sigue en **7/7 detectados** sobre el código restaurado.

**Observación que sí sobrevive y queda anotada, sin actuar:** la prueba
`test_el_prompt_cognitivo_conserva_el_contrato_de_salida` justifica exigir `intent` y `args` con
*«No se rompe `_parse_decision`: mismas cuatro claves»*. Esa premisa es inexacta —`_parse_decision`
nunca lee `intent`—. No se corrige porque cambiarla sin una mejora demostrada detrás es precisamente lo
que acaba de revertirse.

---

## Campaña 3 — conversación multiturno real (`campana-3-multiturno/`)

La campaña 2 midió turnos sueltos. Pero en una conversación el buffer `[conversacion reciente: ...]`
cambia cada turno. Esta campaña lo mide a través del **orquestador real** (composición del producto con
voz mock —el stack real revienta en el TTS sin voz Piper— y un proveedor que envía el mismo cuerpo que
`OllamaProvider` y registra las métricas de la API). Ocho preguntas cognitivas seguidas, todas
verificadas contra el enrutado real.

### Resultados — `multiturno-2.json` (8 turnos)

| turno | prompt | tokens ingeridos | ingesta | generación | total |
|---|---|---|---|---|---|
| T1 | 132 car. | 158 | 6,5 s | 75 tok / 26,5 s | 33,6 s |
| T2 | 469 | 234 | 27,8 s | 58 tok / 36,3 s | 64,6 s |
| T3 | 665 | 297 | 38,7 s | 54 tok / 25,4 s | 64,9 s |
| T4 | 862 | 354 | 19,3 s | 61 tok / 27,6 s | 47,5 s |
| T5 | 1116 | 422 | 37,7 s | 63 tok / 44,1 s | 82,5 s |
| T6 | 1343 | 487 | 24,2 s | 58 tok / 24,2 s | 49,2 s |
| T7 | 1564 | 553 | 27,9 s | 63 tok / 47,6 s | 76,2 s |
| **T8** | **1429** | **541** | **144,8 s** | 54 tok / 42,1 s | **187,8 s** |

`multiturno-1.json` (6 turnos, otra ejecución) reproduce el mismo patrón de T1–T6: prompt de 132 a 1356
caracteres, ingesta estable entre 19,7 y 42,7 s.

### Conclusiones

1. **Hasta el turno 7 la caché de prefijo contiene el coste.** El prompt se multiplica por diez, pero cada
   turno solo re-evalúa lo nuevo —el último intercambio, que va al FINAL del buffer—: ingesta de 19 a
   39 s.
2. **En el turno 8 la ventana empieza a deslizar y la caché se rompe entera.** El buffer conserva 6
   turnos (`_DIALOG_N = 6`, `del buffer[: max(0, len(buffer) - self._DIALOG_N)]`). Al descartar el más
   antiguo cambia el PRINCIPIO del buffer, y todo lo que va detrás se re-evalúa: **144,8 s de ingesta**
   con un prompt más corto que el de T7. Se predijo antes de medirlo, por la estructura del prompt, y se
   cumplió.
3. **Desde el turno 8, cada turno supera o roza el timeout por defecto de 180 s** (este: 187,8 s). En
   HC-1, una conversación larga con el modelo se vuelve inutilizable a partir de ahí.
4. A diferencia de las campañas 1 y 2, **esta métrica es estructural**, no estocástica: depende de qué
   parte del prompt coincide con la anterior, no de cuántos tokens decide generar el modelo. n = 1
   conversación es aquí mucho más informativa que n = 6 preguntas lo fue para la generación.

**No se aplicó ninguna corrección**: toda política de ventana cambia cuánta conversación ve el modelo, y
ninguna elimina el pico. Se eleva como `DR-4` en `milestones/m3-entry/DECISIONES-REQUERIDAS-2026-09-15.md`.

---

## DR-3 aprobada — derivación del tope de generación

Con DR-3 aprobada («límite con aviso honesto»), el tope de tokens del turno cognitivo
(`LIMITE_GENERACION_COGNITIVA` en `modules/providers_real.py`) se fijó en **160** con esta evidencia:

- **n = 54** generaciones reales medidas hoy (campaña 2, campaña 3 y la línea base de DR-4).
- Distribución: mediana **63**, p75 **83**, p90 **129**, p95 **146**, máximo 333.
- Un tope de 160 corta **3 de 54** turnos (5,6 %): los de 199, 232 y 333 tokens. Con 128 cortaría 6
  (11,1 %); con 200, 2 (3,7 %).
- A la peor tasa de generación sana observada (**1,19 tok/s**), 160 tokens son ~134 s: cabe en el
  timeout de 180 s con la ingesta controlada. 200 tokens (~168 s) ya no dejaría margen.

**No es una propiedad de la arquitectura** (regla del CEO, 2026-08-04): depende de `qwen2.5:0.5b` y de
HC-1, y así lo declara el código. Cuando se corta, AURA no entrega el fragmento: dice que la respuesta
quedó incompleta.

---

## El hallazgo que sí es firme: la cola larga y el timeout

**2 de 18 turnos** generaron ≥ 199 tokens. Uno de ellos duró **189,1 s** con la máquina sana.
`OllamaProvider.DEFAULT_TIMEOUT_S` es **180 s** (decidido como valor visible por `D-FC-7`). Con los
valores por defecto, ese turno se habría perdido tras tres minutos de espera del usuario.

- Un tope de generación (`num_predict`) acortaría esa cola, pero con decodificado restringido por
  esquema un corte a mitad deja un JSON inválido: `_parse_decision` respondería *«No entendí bien;
  ¿puedes reformularlo?»* — un mensaje falso, porque el modelo sí entendió y se extendió.
- Subir el timeout convierte la espera en una respuesta, pero alarga la peor espera.
- Entregar una respuesta truncada (reparando el JSON en la frase completa más cercana) sería otra
  opción, y cambia lo que el usuario recibe.

**Las tres son cambios de comportamiento con consecuencias para el usuario**, no optimizaciones: se
elevan como decisión, no se aplican. n = 18 con 2 colas es poca muestra para fijar un tope.

---

## Límite declarado

n = 6 por variante. Sirve para **refutar** una mejora del 60 % —que exigiría una separación que no
aparece— y para detectar que la cola existe. **No sirve** para afirmar un efecto pequeño en ningún
sentido, ni para estimar la frecuencia de la cola con precisión. Para decidir `num_predict` haría
falta una batería mayor y, sobre todo, turnos multiturno reales con buffer de diálogo.
