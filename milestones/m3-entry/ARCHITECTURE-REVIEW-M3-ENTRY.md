---
documento: "Architecture Review — M3 Entry"
milestone: "M3 — Presencia (hogar + avatar + aprendizaje/anticipación)"
fecha: 2026-07-21
autor: "CTO"
estado: "Propuesta — pendiente de gate del CEO. NO se ha iniciado implementación."
base: "main @ 6eb33d0 · tag v1.3.0-m2"
---

# Architecture Review — M3 Entry

Conforme a D25. **No se ha escrito una sola línea de código de M3**, según instrucción expresa.

## 0. Hallazgo previo que condiciona el arranque

Antes de planificar nada verifiqué el requisito transversal que la Bible 2.2 §3.3 impone a los hitos
anteriores:

> *"M1 y M2 instrumentan desde el día uno la **captura de señales** (preferencias, hábitos, feedback)
> que 4.4 necesita — sin esa materia prima, la anticipación de M3 se retrasa semanas por diseño."*

**No se instrumentó.** El sistema escribe un único tipo de memoria:

```
memory.write(uid, "episodica", f"usuario dijo: {text}", {...})
```

No existe captura de preferencias, hábitos ni feedback. Las únicas coincidencias de "preferencia" en
el código son un comentario del router y un patrón de detección de consultas.

### Por qué esto importa más que un retraso

La anticipación **no se puede acelerar con más ingeniería**. Un sistema que propone acciones útiles
necesita haber observado al usuario durante semanas; el algoritmo es lo de menos si no hay historial
sobre el que operar. La Bible lo anticipó con precisión —"se retrasa semanas por diseño"—.

> **Corrección posterior (2026-07-21).** En la primera redacción escribí que el retraso *"empieza a
> contar el día que se instrumente la captura"*. Es impreciso: empieza a contar el día que haya **uso
> real instrumentado**. La verificación encargada por el CEO
> ([DEUDA-CAPTURA-DE-SENALES.md](DEUDA-CAPTURA-DE-SENALES.md)) mostró que el proyecto tiene **12
> entradas de memoria persistente en total**, de una sesión de validación: instrumentar un sistema
> que nadie usa produce un esquema vacío. El obstáculo dominante no son las señales, es la ausencia
> de uso real — y esa depende del hardware (P1).

Es el tercer caso del mismo patrón (ALERTA-004, ALERTA-005): declarado en un documento de
arquitectura, ausente del código. Con una diferencia que conviene registrar: **esta vez se detectó
antes de empezar el milestone, no al intentar cerrarlo.** La revisión de entrada hizo su trabajo.

No abro alerta de arquitectura: no hay riesgo para la integridad del sistema ni decisión bloqueada
—la consecuencia es de calendario y se aborda en el orden propuesto (§6).

## 1. Alcance de M3

| Capacidad | Contenido | Capítulo |
|---|---|---|
| **7** · Control básico del hogar | Encender/apagar y escenas vía Home Assistant | 6.3 |
| **8** · Aprendizaje continuo | Adapta preferencias y hábitos con el uso, **sin reentrenar modelos** | 4.4 |
| **3** · Avatar interactivo | Presencia visual sincronizada a la conversación | 6.5 |
| **5** (parcial) | Componente de automatizaciones **sugeridas**, dentro de lista verde D4 | 6.4 |

## 2. Criterio de salida (2.2 §3.2 + 2.5 §5.3)

- **CM4 Anticipación superado:** ≥ **1 acción proactiva valorada por día** de uso normal, con
  **≤ 20% de falsos positivos** (iniciativas irrelevantes o molestas).
- **Re-verificación de los 4 criterios-marco en conjunto**, no solo del nuevo.

### Aviso sobre el segundo punto

La re-verificación conjunta arrastra una deuda que ya señalé al cerrar M1: **CM1 exige "semanas de
calendario" de memoria sostenida y nunca se verificó así.** M1 se cerró como *M1 técnico*, no *M1
pleno*, con ese matiz registrado. Al llegar a M3 esa deuda deja de ser un matiz y se convierte en
condición de salida.

## 3. Riesgos nuevos

| # | Riesgo | Gravedad | Análisis |
|---|---|---|---|
| **RN3-1** | **La proactividad es el primer acto verdaderamente autónomo** | **Alta** | M2.3 ya actuaba sin humano delante, pero ejecutando **reglas que el usuario escribió**. En M3 AURA decide *por inferencia propia* qué proponer y cuándo. Cambia el sujeto de la decisión, no solo el momento |
| **RN3-2** | **El umbral de ≤20% de falsos positivos es inalcanzable con el modelo actual** | **Alta** | Evidencia de M2: el modelo local eligió mal 1 de 3 acciones **con la petición delante**. La anticipación es un problema más difícil —inferir sin que nadie pida nada— y el listón es más exigente. Depende de la decisión de modelo base, no de más código |
| **RN3-3** | **Latencia vs. proactividad** | **Alta** | Una iniciativa que llega dos minutos tarde no es anticipación. A diferencia de M2, aquí la latencia no solo molesta: **invalida la capacidad** |
| **RN3-4** | Perfilado del usuario y privacidad | **Media** | El aprendizaje continuo construye un modelo persistente de hábitos: qué hace, cuándo, con quién. Es materia sensible por definición y toca ALERTA-002 (contenido de terceros) desde un ángulo nuevo |
| **RN3-5** | Autoridad sobre una preferencia inferida | **Media** | ADR-0014 fija que el Core manda sobre los hechos. Una preferencia *inferida* no es un hecho registrado ni una invención del modelo: es una categoría intermedia que el ADR no cubre. **Requiere decisión explícita** |
| **RN3-6** | El avatar compite por recursos ya escasos | **Media** | Render y sincronización labial consumen CPU/GPU en un equipo que hoy no sostiene un modelo de 3 B |
| **RN3-7** | Home Assistant real aún no validado | **Media** | La Bible 2.2 §4 supone "instancia de HA operativa con dispositivos integrados"; hoy el adaptador es un mock y el supuesto **no está verificado**. Su invalidación dispara el circuito de fracaso (§3.5) |
| **RN3-8** | Sugerir automatizaciones erosiona el consentimiento | **Media** | Si AURA propone reglas y el usuario las acepta por rutina, el HITL se degrada a un botón de "sí". La calidad de la propuesta pasa a ser un asunto de seguridad |

## 4. Prerequisitos (bloqueantes, en orden de precedencia)

| # | Prerequisito | Responsable | Bloquea |
|---|---|---|---|
| **P1** | **Decisión de hardware objetivo** | **CEO** | Todo. Determina qué modelo corre y, con él, RN3-2 y RN3-3 |
| **P2** | **Decisión de modelo base** | CEO, con análisis del CTO | Aprendizaje y anticipación |
| **P3** | **Instrumentación de captura de señales** + tiempo de calendario acumulando datos | CTO | Capacidad 8 y CM4 |
| **P4** | Validación del inventario del hogar (HA real, dispositivos) | CEO/CTO | Capacidad 7 |
| **P5** | Decisión sobre RN3-5 (autoridad sobre preferencias inferidas) | CEO, vía ADR | Capacidad 8 |
| **P6** | Ventana de calendario para CM1 (memoria sostenida) | — | Salida de M3 |

**P1 es el prerequisito del que cuelga todo lo demás**, y coincide con la prioridad que ya fijaste.

## 5. Dependencias documentales

| Capítulo | Estado | Necesario para |
|---|---|---|
| 4.4 Aprendizaje y anticipación | Aprobado | Capacidad 8, CM4 |
| 6.3 Hogar inteligente | Aprobado | Capacidad 7 |
| 6.5 Avatar | Aprobado | Capacidad 3 |
| 2.3 Inventario del ecosistema | **Anexo pendiente de validación** | P4 |
| ADR nuevo sobre preferencias inferidas | **No existe** | P5 |

## 6. Orden de implementación propuesto

El principio que lo ordena: **empezar por lo que hace correr el reloj de calendario y por lo que
reduce incertidumbre, no por lo más vistoso.**

| Fase | Contenido | Justificación |
|---|---|---|
| **M3.0** | **Decisiones P1/P2** + **instrumentación de captura de señales** | La captura debe empezar **el primer día**: cada día sin instrumentar es un día que se resta al historial que M3 necesita. Es lo único que el calendario no perdona |
| **M3.1** | **Capacidad 7 — Home Assistant real** | El adaptador ya existe como mock y el contrato está probado desde M1. Convierte un supuesto no verificado (RN3-7) en hecho, temprano y barato |
| **M3.2** | **Capacidad 8 — Aprendizaje continuo** (preferencias y hábitos, sin proactividad todavía) | Separar *aprender* de *actuar por iniciativa propia* permite verificar la calidad del modelo de preferencias **antes** de dejar que lo use para interrumpir |
| **M3.3** | **Anticipación + automatizaciones sugeridas** (CM4) | Solo cuando M3.2 demuestre preferencias fiables. Aquí entra RN3-1 y merece gate propio |
| **M3.4** | **Capacidad 3 — Avatar** | El más caro en recursos y el que **no desbloquea nada**. Colocado al final para que, si el hardware no da, pueda diferirse sin romper el milestone |
| **M3-Exit** | Architecture Review + Executive Summary (D25) | |

### Por qué el avatar va al final y no al principio

Es la capacidad más visible y la tentación natural sería empezar por ella. Pero un avatar sobre un
sistema que tarda dos minutos en responder produce **una cara esperando en silencio**: subraya el
problema en lugar de resolverlo. Además consume los recursos que necesitan las capacidades que sí
sostienen el criterio de salida.

### Por qué M3.2 se separa de M3.3

Es la decisión de diseño más importante de esta propuesta. **Aprender preferencias y actuar por
iniciativa propia son cosas distintas**, y juntarlas impediría saber cuál de las dos falla cuando la
tasa de falsos positivos supere el 20%. Separadas, M3.2 se puede evaluar de forma pasiva —¿acierta
AURA describiendo mis preferencias?— sin que un error moleste al usuario.

## 7. Definition of Done propuesta

1. P1–P5 resueltos y registrados.
2. Captura de señales operativa, con **evidencia de historial acumulado real**, no sintético.
3. Capacidad 7 verificada contra **Home Assistant real**, no mock.
4. Capacidad 8: preferencias inferidas verificables y **corregibles por el usuario**.
5. CM4: ≥1 acción proactiva valorada/día con ≤20% de falsos positivos, **medido en uso real**.
6. Re-verificación conjunta de CM1–CM4, incluida la ventana de calendario de CM1.
7. Toda acción proactiva dentro de lista verde D4 y sujeta al orden canónico de 5.3 §3.1.
8. Quality Gate PASS, incluida la prueba de alcanzabilidad.
9. Demo de capacidad M3 con stack real, **0 errores no recuperados**.
10. Architecture Review M3-Exit + Executive Summary con Product Readiness actualizado.
11. Sin alertas de arquitectura abiertas.

## 8. Product Readiness — proyección honesta

Partiendo de **41%**:

| Dimensión | Peso | Efecto esperado de M3 |
|---|---|---|
| Responde a tiempo | 25% | **Depende de P1, no de M3.** Con el hardware actual sigue en 0% |
| Entiende y responde con sentido | 15% | Depende de P2. Podría recuperar 12–15% con un modelo mayor |
| Hace cosas útiles | 15% | +2–3% (hogar real) |
| Conversación natural | 10% | Sin cambios salvo que se aborde barge-in |
| Resto | 35% | Sin cambios materiales |

**Con hardware objetivo resuelto: ~65–70%. Sin resolverlo: ~46%.** La diferencia entre ambos
escenarios es mayor que todo lo que M3 puede aportar por sí mismo, y es la razón por la que la
prioridad que fijaste —hardware y modelo antes que capacidades— es la correcta.

## 9. Recomendación del CTO

Aprobar el arranque **solo de M3.0**, y dentro de él dar precedencia a la instrumentación de captura
de señales, que puede comenzar **sin esperar a P1**: no depende del hardware y es condición necesaria
para que el historial empiece a acumularse.

Matiz que la verificación posterior obliga a añadir: **es condición necesaria pero no suficiente.**
El historial no crece porque exista instrumentación, sino porque alguien use el sistema a diario, y
eso hoy es materialmente imposible a más de dos minutos por turno. Detalle y alternativas en
[M3.0-PLAN.md](M3.0-PLAN.md) §4.

Las fases M3.1 en adelante deberían esperar a que P1 y P2 estén decididos. Comprometerse antes a un
diseño de anticipación sería fijar decisiones sobre un modelo base que quizá cambie.

## 10. Decisión requerida del CEO

1. ¿Se aprueba el alcance y el orden propuesto (§6), con el avatar al final?
2. ¿Se autoriza iniciar **M3.0** —y en particular la instrumentación de captura de señales— antes de
   resolver P1, para no seguir perdiendo calendario?
3. ¿Se abre un **ADR sobre la autoridad del sistema respecto a preferencias inferidas** (RN3-5)?
4. ¿Cómo se aborda la deuda de **CM1** (semanas de calendario de memoria), que la salida de M3 exige
   y que M1 dejó abierta?
