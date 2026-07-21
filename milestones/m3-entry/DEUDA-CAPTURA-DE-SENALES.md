---
documento: "Verificación de la brecha de captura de señales"
fecha: 2026-07-21
autor: "CTO"
encargo: "CEO — verificar antes de convertir el hallazgo en alerta"
conclusion: "Brecha CONFIRMADA. Deuda técnica heredada, no reapertura de M2."
---

# Verificación — Captura de señales de aprendizaje

Encargo del CEO: (1) confirmar si la Bible exige la instrumentación **implementada** al terminar M2 o
solo prevista; (2) si la omisión es real, inventariar qué señales faltan y separar **bloqueo
absoluto** de **degradación**.

## 1. ¿La Bible lo exigía implementado?

**Sí.** El texto está en el capítulo **2.2, estado "Aprobado"** (2026-07-17), bajo el epígrafe
**"3.3 Requisitos transversales"** — no bajo previsiones ni trabajo futuro:

> *"M1 y M2 **instrumentan desde el día uno** la captura de señales (preferencias, hábitos, feedback)
> que 4.4 necesita — sin esa materia prima, la anticipación de M3 se retrasa semanas por diseño."*

El verbo está en presente de obligación y la expresión *"desde el día uno"* excluye la lectura de
"previsto arquitectónicamente". Un requisito transversal cuyo cumplimiento se difiere al hito que lo
consume no es un requisito transversal.

### Dónde se rompió la cadena — y es responsabilidad mía

El requisito **no era desconocido**. Lo recogí explícitamente en el paquete de cierre de M1, como
recomendación 6 de 7 para M2:

> *"**Instrumentar desde el día uno la captura de señales** que M3 necesitará (2.2 §3.5): sin esa
> materia prima, la anticipación de M3 se retrasa semanas por diseño."*

Y **no lo trasladé a la Definition of Done del Architecture Review M2 Entry.** Las once condiciones
de cierre de M2 no lo mencionan. M2 cumplió íntegramente su DoD; la DoD fue la que omitió un
requisito vigente que yo mismo había señalado tres días antes.

Esto no reabre M2 —su alcance funcional se cumplió— pero conviene que quede escrito con precisión:
**no fue un requisito que se pasara por alto, fue uno que se identificó y luego no se convirtió en
criterio verificable.** Es exactamente el mismo mecanismo de ALERTA-004 y ALERTA-005: lo que no entra
en una DoD o en una prueba, no ocurre.

La recomendación 7 del mismo paquete —*"iniciar el reloj del criterio de calendario de M1"*— corrió
la misma suerte. Vuelve en §4.

## 2. Qué señales faltan exactamente

El capítulo 4.4 §1 define seis señales en dos familias, y 4.4 §2 exige consolidarlas como memoria
**semántica y procedimental**.

**Estado actual del sistema:** escribe **un solo tipo** de memoria, `episodica`, con el contenido
literal `"usuario dijo: {texto}"`. Las memorias **semántica y procedimental no existen** en el
código; la taxonomía de 4.1 §1 está implementada a un tercio.

| # | Señal (4.4 §1) | Estado | Impacto sobre M3 | Clasificación |
|---|---|---|---|---|
| 1 | **Preferencias declaradas** ("prefiero la luz tenue") | No capturada como tal; el texto queda en memoria episódica | El modelo del usuario no se puede construir, pero el dato bruto es **derivable** del histórico | **Degradación** — recuperable por minería retroactiva |
| 2 | **Correcciones** ("no, así no") | No capturada; sin marca que distinga una corrección de una frase cualquiera | Sin ellas el sistema no sabe **qué dejó de acertar**. Derivable con menor fiabilidad | **Degradación** |
| 3 | **Feedback directo** ("no me gusta que…") | No capturada | Idéntico a 2 | **Degradación** |
| 4 | **Patrones de uso** (qué hace, cuándo) | Parcial: el audit log registra acciones con marca de tiempo | Es la señal **mejor posicionada**: el audit log de M2 es materia prima válida | **Degradación leve** |
| 5 | **Temas recurrentes** | Derivable del histórico episódico | Requiere volumen, no instrumentación nueva | **Degradación** |
| 6 | **Aceptación o rechazo de sugerencias** | **Inexistente y no derivable** | AURA **nunca ha hecho una sugerencia**. La señal no se puede recuperar del pasado porque el pasado no la contiene | **Bloqueo estructural** para el arranque en frío |

### Lectura de la tabla

**Ninguna señal está bloqueada de forma permanente.** Cinco de las seis son recuperables o
derivables; lo que falta es la instrumentación que las convierta en memoria semántica/procedimental
consultable, y eso es trabajo de ingeniería acotado.

La sexta —aceptación o rechazo de sugerencias— es un **bloqueo de arranque en frío**, no permanente:
la señal se genera sola en cuanto el sistema empiece a sugerir (M3.3). Su consecuencia práctica es
que **la primera medición de CM4 no puede apoyarse en ella**, y por tanto el umbral de ≤20% de falsos
positivos se medirá al principio sobre un modelo del usuario ciego a su propio acierto. Eso hace
esperable que las primeras semanas de anticipación estén *por encima* del 20%, y conviene decidir de
antemano si eso cuenta como fallo del criterio o como periodo de calibración.

## 3. El hallazgo mayor: no hay historial del que minar

Al verificar cuánto es recuperable retroactivamente encontré algo que cambia el orden de importancia
de todo lo anterior.

**El único fichero de memoria persistente del proyecto contiene 12 entradas**, todas episódicas, de
una sesión de validación del 19 de julio. Todas las demás ejecuciones escriben en directorios
temporales que se borran.

```
walking-skeleton/m1-validacion-datos/memoria.json
  entradas: 12 · tipos: {'episodica': 12} · 2.052 bytes
```

Es decir: **la minería retroactiva de las cinco señales "recuperables" no recuperaría nada**, porque
no hay nada acumulado. El problema no es solo que falte instrumentación: es que **AURA nunca ha
estado en uso real sostenido.**

### La cadena causal completa

```
hardware insuficiente → +2 min por turno → nadie puede usar AURA a diario
   → sin uso real → sin historial → sin señales → CM4 (anticipación) inalcanzable
```

De aquí se sigue una corrección a lo que afirmé en el Architecture Review M3 Entry. Escribí que *"el
reloj empieza el día que se instrumente la captura"*. **Es impreciso.** El reloj empieza el día que
haya **uso real instrumentado**. Instrumentar un sistema que nadie usa produce una tabla vacía con
buen esquema.

Esto refuerza la prioridad que fijaste, y por una razón más fuerte de la que yo había expuesto: **P1
(hardware) no condiciona solo la calidad de M3, condiciona la posibilidad física de generar los datos
que M3 necesita para existir.**

## 4. Deuda gemela: el reloj de CM1

La recomendación 7 del cierre de M1 —iniciar el reloj de la ventana de calendario de memoria— tampoco
se ejecutó, por la misma causa raíz: **no puede haber uso sostenido de semanas si cada turno cuesta
dos minutos.**

Ambas deudas, la de señales y la de CM1, son **la misma deuda con dos nombres**: falta de uso real. Y
ambas son condición de salida de M3 (2.2 §3.2 exige re-verificar los cuatro criterios en conjunto).

## 5. Conclusión

**Brecha confirmada**, en los términos que pediste:

- La Bible la exigía **implementada**, no prevista.
- La omisión es real y su causa es trazable: identificada al cerrar M1, no incorporada a la DoD de M2.
- **Ninguna señal supone bloqueo permanente**; una supone bloqueo de arranque en frío que se resuelve
  solo; el resto son degradaciones con trabajo de ingeniería acotado.
- **El obstáculo dominante no son las señales, es la ausencia de uso real**, y esa depende del
  hardware.

Se trata como **deuda técnica heredada, a abordar en M3.0**, sin reabrir el cierre de M2, conforme a
tu instrucción. No propongo abrir alerta de arquitectura: no hay decisión bloqueada ni riesgo para la
integridad del sistema, y el plan de M3.0 la absorbe.
