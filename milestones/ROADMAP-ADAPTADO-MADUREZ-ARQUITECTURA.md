---
documento: "Roadmap adaptado — Línea MA (Madurez de Arquitectura)"
fecha: 2026-07-21
autor: "CTO"
origen: "D39 — desarrollo continuo con restricciones de hardware"
estado: "Propuesta — pendiente de gate. No se ha iniciado implementación."
---

# Línea MA — Madurez de Arquitectura

Adaptación del roadmap a las restricciones actuales (D39). **No sustituye a M3**: es trabajo
transversal que avanza mientras M3.1/M3.2b esperan entorno físico.

**Objetivo declarado por el CEO:** que al llegar el hardware sólo haya que **habilitar** capacidades,
no construirlas.

## 1. De dónde sale este plan

No de una lluvia de ideas: **de la auditoría técnica del 2026-07-21**, que midió la deuda sobre el
código. Cada fase corresponde a un hallazgo con evidencia, y se ordena por el riesgo que cierra.

## 2. Fases propuestas

| Fase | Contenido | Cierra | Criterios D39 |
|---|---|---|---|
| **MA.1** | **Punto de entrada único de producción** | D-1, D-5, Riesgo A | 1,2,3,4,6,7 |
| **MA.2** | **Memoria escalable** | R-1, R-2, D-6, Riesgo B | 1,2,3,7 |
| **MA.3** | **Retención y rotación del audit log** | D-3, Riesgo C | 1,3,5 |
| **MA.4** | **Habilitación y transparencia de conectores** | Condiciones de D37 | 1,2,5,8 |
| **MA.5** | **Limpieza: código muerto y scripts** | D-4, D-5 | 3,4 |

### MA.1 · Punto de entrada único de producción — **prioridad máxima**

**Problema medido:** hoy no existe nada que ejecutar para "usar AURA". Siete scripts construyen el
`Orchestrator` por su cuenta y **ninguno activa la captura de señales de M3.0**.

**Riesgo si no se hace antes del hardware:** al llegar el equipo, lo probable es adaptar deprisa uno
de los siete cableados parciales —el más simple, que es el que menos capacidades enciende— y empezar
a acumular uso real **sin registrar señales**. No se notaría hasta semanas después, con el historial
vacío. Es el patrón de ALERTA-004/005 por tercera vez.

**Alcance:**
- Un ejecutable de producción que cablee **el sistema completo**: adaptadores, motor, contexto,
  memoria persistente, audit log.
- Configuración por fichero y variables de entorno, no por edición de código.
- **Prueba que falle si el punto de entrada no enciende alguna capacidad declarada** — la extensión
  natural de la prueba de alcanzabilidad de M2.5, ahora aplicada al arranque.
- Los scripts de demo pasan a **consumir** ese cableado en vez de replicarlo.

**Por qué es lo primero:** es lo único que convierte "AURA existe" en "AURA se puede usar", y es la
condición para que el día 1 con hardware nuevo sea productivo.

### MA.2 · Memoria escalable

**Problema medido:** `recall()` recorre todos los ítems y `PersistentMemory` reescribe el JSON
completo en cada escritura. Con 12 entradas es irrelevante; **con meses de historial degrada cada
turno**.

**Por qué ahora:** migrar una memoria con meses de datos cuesta mucho más que construirla bien con 12
entradas. Y el historial empieza a crecer **el día que arranque E1**.

La Bible ya define la solución (ADR-0007/0011: Qdrant, RAG híbrido). Conviene evaluar si el MVP
necesita Qdrant o basta un índice más simple: **añadir un servicio externo tiene coste operativo
permanente**, y esa decisión merece su propio análisis dentro de la fase.

### MA.3 · Retención y rotación del audit log

**Problema medido:** el audit log es append-only con `fsync` y **no tiene política de rotación**:
crece sin límite. El proyecto ya llenó un disco una vez (D27/D31).

**El matiz que lo hace delicado:** el audit log es **también la materia prima de las señales
implícitas** de M3.0. Una rotación ingenua borraría el historial que la anticipación necesita. Debe
diseñarse junto con la retención de señales, no como tarea de limpieza.

### MA.4 · Habilitación y transparencia de conectores

D37 fijó tres condiciones para conectores hacia servicios de terceros: **opt-in explícito**,
**transparencia sobre qué dato queda local y cuál sale**, y **ninguno como requisito**.

Esas tres condiciones son **infraestructura**, no integración: se pueden construir y verificar sin
ningún wearable, sin credenciales y sin red. Cuando se apruebe el primer conector externo, el
mecanismo ya estará listo y probado.

Cumple explícitamente el criterio 8 de D39 (*preparar la integración futura de sensores, wearables y
demás conectores aprobados*) **sin construir ningún conector**.

### MA.5 · Limpieza

Subsistema de métricas muerto (`metric_inc`/`metrics`/`_metrics`) y consolidación de los scripts
sueltos tras MA.1. Bajo riesgo, bajo valor individual — **se hace al final, no al principio**, porque
MA.1 cambia qué scripts siguen teniendo sentido.

## 3. Lo que esta línea NO hace

- **No toca `ejecutar()`** (complejidad 14). Es el precio de tener un solo camino de ejecución;
  partirlo mejoraría la métrica y empeoraría la garantía.
- **No añade cobertura con dobles** a `providers_real.py` ni `voice_real.py`. Sería probar el doble,
  no el sistema (D34). Su cobertura real llegará con el hardware.
- **No implementa inferencia, anticipación ni avatar.** Dependen de datos o plataforma.
- **No mueve el Product Readiness** salvo que entregue capacidad verificable al usuario. MA.1 podría
  moverlo levemente —*"disponible sin fricción"* está en 0%— pero sólo con evidencia de que AURA
  arranca y opera de forma sostenida.

## 4. Orden y justificación

```
MA.1 ──> MA.2 ──> MA.3 ──> MA.4 ──> MA.5
 │         │        │        │        └── depende de MA.1 (qué scripts sobreviven)
 │         │        │        └── independiente; podría adelantarse
 │         │        └── conviene tras MA.2 (retención de señales y memoria se diseñan juntas)
 │         └── antes de que crezca el historial
 └── primero: cierra el riesgo de mayor probabilidad × impacto
```

## 5. Definition of Done de la línea

1. Existe **un** ejecutable de producción que enciende el sistema completo, con prueba que lo verifica.
2. La memoria no degrada con el volumen; verificado con una prueba de carga sintética **de
   rendimiento**, no de comportamiento (medir escalabilidad con datos generados es legítimo; inferir
   preferencias con ellos no lo sería).
3. Política de retención decidida, documentada e implementada.
4. Mecanismo de habilitación y transparencia de conectores, verificado sin ningún conector externo.
5. Sin código muerto detectable por el análisis de la auditoría.
6. Quality Gate PASS; sin regresión en las garantías de M1, M2 y M3.0.
7. Auditoría re-ejecutada mostrando la deuda cerrada.

## 6. Decisión requerida del CEO

1. ¿Se aprueba la línea MA y su orden?
2. ¿Se autoriza iniciar **MA.1** de inmediato?
3. Sobre MA.2: ¿se prefiere adoptar Qdrant (ADR-0011, ya decidido en la Bible) o evaluar antes una
   alternativa más simple? Añadir un servicio externo tiene coste operativo permanente y el MVP
   quizá no lo necesite todavía.
