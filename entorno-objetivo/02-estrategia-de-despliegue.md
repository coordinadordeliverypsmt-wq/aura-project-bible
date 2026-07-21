---
documento: "02 — Estrategia de despliegue"
linea: "Preparación del Entorno Objetivo (D35)"
fecha: 2026-07-21
autor: "CTO"
---

# Estrategia de despliegue

> ## ✅ DECIDIDO — D36 (2026-07-21)
>
> **E1 (uso personal) es el escenario inicial oficial. E2 (hogar inteligente) es el objetivo de la
> primera versión estable.** E3 y E4 quedan **fuera del alcance actual** y no condicionan decisiones
> de arquitectura mientras no haya un cambio explícito de alcance.
>
> Este documento se conserva como el análisis que sustentó la decisión. Las secciones sobre E3/E4
> (§3) siguen siendo válidas como advertencia para el día en que se reconsideren, no como trabajo
> pendiente.


Este es el documento central de la línea. Los otros comparan opciones; **este identifica la decisión
que da sentido a esas comparaciones.**

## 1. La pregunta pendiente

> **¿Dónde va a vivir AURA?**

De ella cuelgan, hoy sin resolver: el hardware objetivo (D33), el modelo base, el sistema operativo,
M3.1, M3.2b y la validación de HC-1. **No es una decisión técnica; es de producto**, y por eso no me
corresponde tomarla. Lo que sí me corresponde es exponer qué implica cada respuesta.

## 2. Los cuatro escenarios

### E1 · Uso personal

AURA corre en un equipo del CEO, para el CEO.

| | |
|---|---|
| **Requisitos** | Los del documento 01, una sola vez |
| **Ventaja** | Es el camino más corto a datos de uso real, que es lo que M3 necesita |
| **Riesgo** | Ninguno nuevo |
| **Consecuencia** | Desbloquea M3.2b (datos) pero **no M3.1** si no hay hogar instrumentado |

### E2 · Instalación doméstica

AURA vive en la casa, integrada con el hogar: un equipo dedicado, Home Assistant, dispositivos.

| | |
|---|---|
| **Requisitos** | Los de E1 + instalación de HA + dispositivos reales |
| **Ventaja** | **Único escenario que desbloquea M3 completo**, incluida M3.1 conforme a D34 |
| **Riesgo** | Multiusuario en el hogar: P-ARQ-5 y ALERTA-002 dejan de ser teóricos |
| **Consecuencia** | Es el escenario para el que la Bible está escrita (2.2 §4, 6.3) |

### E3 · Distribución a terceros

Otras personas instalan AURA en sus casas.

| | |
|---|---|
| **Requisitos** | E2 + instalador reproducible + soporte + actualizaciones + documentación de usuario |
| **Ventaja** | Valida el producto fuera del sesgo de su autor |
| **Riesgo** | **Alto y de naturaleza nueva.** Ver §3 |
| **Consecuencia** | Convierte decisiones internas en compromisos con terceros |

### E4 · Producto comercial

AURA se vende.

| | |
|---|---|
| **Requisitos** | E3 + soporte formal + garantías + marco legal + modelo de negocio |
| **Riesgo** | El de E3 más responsabilidad contractual y regulatoria |
| **Consecuencia** | El hardware pasa a ser coste unitario: cambia por completo el criterio de elección |

## 3. Lo que E3 y E4 cambian, y conviene saber antes

No son "E2 con más usuarios". Introducen obligaciones que hoy no existen:

| Asunto | En E1/E2 | En E3/E4 |
|---|---|---|
| **Datos personales** | Del propio usuario, local (ADR-0001) | Terceros tratan datos de terceros. **Aparece el RGPD** y la figura del responsable del tratamiento |
| **Contenido de otras personas** | ALERTA-002 resuelta con alcance de sesión | La misma decisión con **implicaciones legales**, no solo éticas |
| **HITL** | El usuario asume su decisión | Un tercero confirma una acción destructiva. **¿Quién responde si se equivoca?** |
| **Hardware** | Se elige por idoneidad | Se elige por **coste unitario y soporte** — otro criterio |
| **Actualizaciones** | Manuales | Deben poder desplegarse sin romper instalaciones ajenas |
| **Fallo del sistema** | Molestia | **Incidencia con responsabilidad** |

Mi obligación aquí es señalar que **la fila del HITL no está resuelta**. AURA está diseñada para que
un humano confirme lo destructivo; en un producto distribuido, ese humano es un cliente, y el
reparto de responsabilidad cuando confirma un borrado erróneo es una cuestión legal que la
arquitectura no puede contestar sola.

## 4. Qué desbloquea cada escenario

| | E1 personal | E2 doméstico | E3 terceros | E4 comercial |
|---|---|---|---|---|
| Datos de uso real (M3.2b) | ✅ | ✅ | ✅ | ✅ |
| Hogar real (M3.1, D34) | ❌ | ✅ | ✅ | ✅ |
| Validación de HC-1 | ✅ | ✅ | ✅ | ✅ |
| CM1 (memoria en semanas) | ✅ | ✅ | ✅ | ✅ |
| CM4 (anticipación) | Parcial | ✅ | ✅ | ✅ |
| Criterio de coste de hardware | Idoneidad | Idoneidad | **Unitario** | **Unitario + soporte** |
| Marco legal necesario | No | No | **Sí** | **Sí** |

## 5. Recomendación del CTO

**E1 ahora, E2 como objetivo de R1.** Y son compatibles: E1 es el primer paso de E2, no una vía
alternativa.

El razonamiento es de secuencia, no de preferencia:

1. **E1 desbloquea de inmediato lo que hoy más falta: uso real.** El obstáculo dominante de M3 no es
   el hogar, es que **AURA nunca ha estado en uso sostenido** (12 entradas de historial en total). E1
   arregla eso en cuanto haya hardware suficiente, sin esperar a instalar nada más.
2. **E2 es el escenario para el que la Bible está escrita** y el único que cierra M3 completo.
3. **E3 y E4 no deberían decidirse todavía.** Introducen obligaciones legales y de soporte que
   cambiarían decisiones de arquitectura ya tomadas. Comprometerse ahora sería decidir sobre un
   producto que aún no se ha demostrado usable ni un solo día.

### Un matiz sobre el orden

Conviene no leer esto como "primero E1 y luego ya veremos". **El salto de E2 a E3 es el que conviene
decidir pronto**, aunque se ejecute tarde: si AURA va a distribuirse algún día, hay decisiones —de
privacidad, de responsabilidad sobre el HITL, de instalación reproducible— que salen mucho más
baratas si se toman antes que después.

No hace falta comprometerse con E3. Sí conviene saber si está en el horizonte.

## 6. Resolución (D36)

| Pregunta planteada | Resolución del CEO |
|---|---|
| ¿E1 inmediato y E2 objetivo de R1? | **Sí.** E1 inicial oficial; E2 objetivo de la primera versión estable |
| ¿E3/E4 en el horizonte? | **No.** Fuera del alcance actual; no condicionan la arquitectura |
| ¿Cuándo el equipo de E1? | **Pendiente de disponibilidad material**, no de decisión |

**Consecuencia:** al quedar E3/E4 fuera, no se diseña para multiusuario ajeno, soporte a terceros ni
cumplimiento contractual. Las obligaciones legales de §3 —RGPD como responsable del tratamiento,
reparto de responsabilidad del HITL— **no se abordan**, y su aparición futura exigiría una revisión
de arquitectura.

Lo que queda pendiente ya no es una decisión, sino la **disponibilidad material** del entorno:
equipo, Home Assistant, dispositivos y uso cotidiano.
