---
documento: "D47 — Método Jerárquico de Evidencia (estándar de trabajo con Claude Code)"
fecha: 2026-07-28
autor: "CTO / Director"
estado: "APROBADO por el CEO (2026-07-28). Estándar de trabajo por defecto."
alcance: "Todos los trabajos relevantes del proyecto AURA, y futuros proyectos con Claude Code, salvo que el CEO indique expresamente otra metodología."
version: 1.0.0
---

# D47 — Método Jerárquico de Evidencia

> Los trabajos relevantes se deciden por **jerarquía de evidencia, no por consenso**. La autoridad
> proviene de la evidencia, **no del rango**.

## 1. Propósito

Elevar a estándar el método validado el 2026-07-27/28: un solo analista tiene techo; la refutación
adversarial entre niveles, con evidencia clasificada y verificación personal del Director, produce
decisiones más robustas y **expone los errores del propio Director**. Precedente que lo justifica: el
equipo refutó la hipótesis del Director ("Voz es la primera capacidad") y este la sustituyó por **N2 de
memoria** ante evidencia de ejecución producida por los niveles inferiores.

## 2. Roles (la familia de modelos Claude como un equipo)

| Rol | Modelo | Responsabilidad |
|---|---|---|
| **Director / CTO** | Opus 5 | Formula la hipótesis y define qué evidencia puede refutarla. Verifica personalmente lo decisivo. Integra sólo evidencia reproducible. Emite la decisión. |
| **Arquitectos** | Opus (4.8 / 4.7) | **Destruir** la hipótesis, no defenderla. Diseño, invariantes, contratos, riesgos, candidato alternativo. |
| **Ingenieros** | Sonnet (5 / 4.6) | Ejecutan experimentos **reproducibles**; buscan defectos concretos. |
| **Operario / Inspector** | Haiku 4.5 | Tareas mecánicas: inventarios, conteos, matrices, verificaciones. **No decide.** |

*Nota de herramienta:* la API de subagentes de Claude Code permite asignar el **nivel** (opus / sonnet /
haiku), no la versión exacta dentro de una familia. Se mapea el rol al nivel disponible.

## 3. Los siete principios (fijados por el CEO, 2026-07-28)

1. El Director formula la hipótesis y define qué evidencia puede refutarla.
2. Los Arquitectos tienen como misión **destruir** la hipótesis, no defenderla.
3. Los Ingenieros ejecutan experimentos reproducibles.
4. El Operario realiza tareas mecánicas, inventarios y verificaciones.
5. El Director **verifica personalmente** los hechos que cambian la decisión antes de integrar.
6. La salida es **una única decisión**.
7. Si la evidencia no distingue entre alternativas, la respuesta oficial es **"no hay evidencia
   suficiente"** — nunca una elección forzada.

## 4. Flujo

```
(1) Director formula hipótesis + evidencia refutadora
        ↓
(2) Arquitectos (Opus) intentan destruirla
        ↓
(3) Ingenieros (Sonnet) ejecutan experimentos reproducibles
        ↓
(4) Operario (Haiku) inventarios y verificaciones mecánicas
        ↓
(5) Director verifica lo decisivo de primera mano e INTEGRA
        ↓
    → UNA decisión, o "no hay evidencia suficiente"
```

Ningún nivel inferior asume las conclusiones del superior. Todos **falsan**, no defienden.

## 5. Honestidad metodológica

- **La autoridad proviene de la evidencia, no del rango.** No se asume que un modelo o agente tiene razón
  por su posición.
- El Director **debe poder cambiar completamente de conclusión** si un nivel inferior la refuta con
  evidencia. Cambiar de opinión ante evidencia es el funcionamiento correcto del método, no un fallo.
- Ninguna recomendación puede basarse únicamente en elegancia arquitectónica o preferencia personal.

## 6. Integración con Claude Code (ejecución real, no texto)

El método **debe aprovechar las capacidades reales de Claude Code**. Cuando aporte valor, el plan indica
explícitamente:

- qué **modelo** conviene usar (Opus / Sonnet / Haiku);
- qué **agentes especializados** merece la pena lanzar;
- qué **Skills** utilizar;
- qué **experimentos** deben ejecutarse realmente sobre el repositorio;
- qué **comandos, pruebas o scripts** deben ejecutarse;
- qué **archivos** pueden crearse o modificarse;
- qué evidencia procede de **lectura** y cuál de **ejecución**.

Los prompts a subagentes se diseñan **para Claude Code**, no para un LLM genérico: se les ordena ejecutar
(Bash, pruebas, mediciones), leer código con `fichero:línea`, y trabajar en un directorio temporal fuera
del repositorio salvo autorización, verificando `git` limpio al terminar.

## 7. Clasificación obligatoria de evidencia

Toda afirmación de cualquier nivel se etiqueta como una de:

- **[EJECUCIÓN]** — verificado ejecutando algo; incluye el comando y su salida.
- **[LECTURA]** — verificado leyendo código; incluye `fichero:línea`.
- **[INFERENCIA]** — deducción a partir de lo anterior.
- **[HIPÓTESIS]** — conjetura no verificada.

El Director sólo integra **[EJECUCIÓN]** y **[LECTURA]** reproducibles para sostener una decisión;
**[INFERENCIA]** e **[HIPÓTESIS]** se marcan como tales y no bastan por sí solas.

## 8. Alcance y excepción

Estándar por defecto de **AURA** y de **futuros proyectos con Claude Code**. No se aplica a trabajos
triviales o meramente conversacionales. El CEO puede indicar **expresamente** otra metodología para un
trabajo concreto; esa indicación prevalece sobre D47 para ese trabajo.

## 9. Relación con otras decisiones

- **D15 (deber de disenso)**: D47 lo operacionaliza — la refutación deja de ser un acto puntual del CTO
  para ser la estructura del análisis.
- **D25 (Architecture Review por milestone)**: las Reviews importantes se conducen con D47.
- **Régimen de cambio de los invariantes** (`revisiones/2026-07-27-invariantes-definitivos-...md` §5): la
  exigencia de evidencia de implementación/validación real es coherente con la clasificación de §7.
