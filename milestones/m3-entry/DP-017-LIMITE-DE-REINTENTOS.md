# Decision Package — Capacidad 017: usar el historial para decidir

**Estado:** aprobado por el CEO · **Fecha:** 2026-08-10 · **Propone:** APUS-5
**Origen:** defecto MEDIDO tras integrar Pieza 2, no diseño anticipado.

---

## 1 · El defecto, medido `[EJEC]`

Pieza 2 hizo que una tarea aprobada vuelva al trabajo. Si después falla **por otra razón** —error del
adaptador, veredicto negativo del ejecutor—, se bloquea, y en el latido siguiente vuelve a reabrirse
porque su decisión sigue aprobada:

```
latido 1: reabiertas=1  estado=abierta  intentos=1
latido 2: reabiertas=1  estado=abierta  intentos=2
latido 3: reabiertas=1  estado=abierta  intentos=3
latido 4: reabiertas=1  estado=abierta  intentos=4
```

En `--servir` esto gira **indefinidamente**. No compromete la seguridad —nada se ejecuta sin permiso,
y el permiso es válido— pero AURORA consume su latido sin avanzar.

**Y la columna de la derecha es la clave: `intentos` YA cuenta bien.** El material para decidir
existe (`estado_operativo.py:183`); el único que lo lee hoy es el IMA, y sólo para comprobar que el
campo existe (`ima.py:124`). Ésa es exactamente la capacidad 017: *usar su historial para decidir*.

---

## 2 · Qué se decide

Un **límite explícito de reintentos**. Al alcanzarlo, la tarea **deja de reabrirse sola** y queda
**escalada al CEO** conservando su historial completo. El ciclo sigue con las demás tareas.

Es aritmética sobre un campo que ya existe. **Sin LLM, sin inferencia, sin componentes nuevos.**

---

## 3 · Alcance mínimo

| Se toca | Qué |
|---|---|
| `core/decisiones.py` | `reabrir_aprobadas` consulta `intentos` antes de reabrir; al alcanzar el límite, anexa el bloqueo de escalada **una sola vez** |
| Constante `_LIMITE_DE_REINTENTOS` | Umbral **con nombre y motivo documentado**, no un número suelto en una comparación |
| Pruebas y mutantes | Lo de siempre |

**No se toca:** `ESTADOS` ni el protocolo de transiciones (la tarea sigue `bloqueada`, que ya es el
estado correcto: no hay que inventar uno nuevo) · el confirmador · la huella · el motor · las listas
verde/roja · el kill switch.

---

## 4 · El umbral, y por qué ese número

**`_LIMITE_DE_REINTENTOS = 3`.**

No es un número mágico y no se elige por estética. Se deriva de para qué sirve reintentar:

- **1 intento no basta**: el primer fallo puede ser transitorio —un fichero ocupado, un `OSError` del
  disco—, y esos son precisamente los que el motor ya declara recuperables.
- **2 permite exactamente un reintento**, que no distingue «transitorio» de «reproducible».
- **3 da dos reintentos**: si un fallo se repite tres veces con la misma aprobación vigente, no es
  circunstancial. Insistir más gasta latidos sin información nueva.

**Lo que hace al número defendible no es su valor, sino que sea VISIBLE y AJUSTABLE**: vive en una
constante con nombre, se documenta aquí, y una prueba lo fija de modo que cambiarlo obligue a
declararlo. Si el uso real demuestra que 3 es poco o mucho, se cambia con evidencia — que es la regla
del CEO sobre valores numéricos (2026-08-04).

---

## 5 · Criterio de aceptación

1. Una tarea aprobada que falla repetidamente **deja de reabrirse** al alcanzar el límite. El bucle
   medido en §1 se cierra: `reabiertas=0` a partir de ahí.
2. La tarea queda **escalada**, con un bloqueo explícito que dice cuántos intentos hubo. El CEO lo ve
   en el Centro de Gobierno, que ya muestra los bloqueos.
3. **El historial se conserva**: `intentos` y los bloqueos anteriores siguen ahí. Una aprobación
   posterior no los borra.
4. **El ciclo continúa** con las demás tareas: una escalada no detiene a AURORA.
5. Por debajo del límite, el comportamiento **no cambia**: la reapertura sigue funcionando.
6. La escalada se anexa **una sola vez**, no en cada latido.

---

## 6 · Mutantes previstos

(a) el límite desaparece — vuelve el bucle · (b) el límite se compara con `>` en vez de `>=`, dando un
intento de más · (c) la escalada no se anexa: la tarea se para en silencio y el CEO nunca se entera ·
(d) la escalada se anexa en cada latido y llena el historial de ruido · (e) reabrir borra `intentos`
· (f) el límite se aplica a TODAS las tareas y no sólo a las que superaron el umbral.

---

## 7 · Impacto sobre la métrica de gobierno

**¿Qué trabajo nuevo puede completar AURORA por sí misma?** El mismo que con Pieza 2 — pero ahora
**sin gastar su latido en trabajo que ya demostró no salir**. Pieza 2 le dio continuidad; 017 le da
criterio para no malgastarla. Es el primer uso real de su propio historial para tomar una decisión.

**Lo que NO hace:** no elige entre estrategias, no diagnostica la causa del fallo, no reordena el
backlog por aprendizaje. Eso es 015/016, congeladas por hardware. Aquí sólo se decide **dejar de
insistir**, que es la decisión más simple que puede tomarse con un historial — y la que hoy falta.
