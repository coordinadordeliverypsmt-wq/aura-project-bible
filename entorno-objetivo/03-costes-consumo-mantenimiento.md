---
documento: "03 — Costes, consumo energético y mantenimiento"
linea: "Preparación del Entorno Objetivo (D35)"
fecha: 2026-07-21
autor: "CTO"
---

# Costes, consumo y mantenimiento

## 1. Advertencia sobre las cifras

Todo lo económico de este documento es **[terceros]** u **[estimación]**. No he verificado precios ni
consumos en equipos concretos, y los precios varían por región y momento.

**Ninguna compra debería decidirse con estas cifras.** Sirven para comparar órdenes de magnitud y
para una conclusión que sí es robusta: cuál de los costes domina.

## 2. Consumo energético

AURA está **encendida todo el día** — es la condición de un compañero, no una elección de
configuración. Eso convierte el consumo en reposo en el factor dominante, porque el equipo pasará la
mayor parte del tiempo esperando, no infiriendo.

| Plataforma | Reposo **[terceros]** | Carga **[terceros]** |
|---|---|---|
| Mac mini M4 | **3–6 W** | 40–45 W |
| Mini PC N100 | **4–8 W** | < 15 W |
| Sobremesa con GPU dedicada | **46–65 W** | 200 W+ |

### Coste eléctrico anual estimado

**[cálculo]** sobre 8.760 h/año, a 0,15 €/kWh (ajústese a la tarifa real):

| Plataforma | Reposo | kWh/año | Coste anual |
|---|---|---|---|
| Mac mini M4 | 5 W | ~44 | **~7 €** |
| Mini PC N100 | 6 W | ~53 | **~8 €** |
| Sobremesa con GPU | 55 W | ~482 | **~72 €** |

### La conclusión que sí es robusta

La diferencia entre las opciones eficientes y una con GPU dedicada ronda los **65 €/año**. En el
horizonte de 10 años de D20, son **~650 €** — comparable al precio de compra de una máquina
eficiente.

Dicho de otro modo: **una plataforma de bajo consumo puede pagarse sola a lo largo de la vida del
proyecto.** Es un argumento sólido y con una salvedad honesta: sólo aplica si el equipo permanece
encendido todos esos años, que es precisamente lo que AURA supone.

## 3. Coste de adquisición

**[estimación]**, órdenes de magnitud, no presupuestos:

| Plataforma | Orden de magnitud | Nota |
|---|---|---|
| Mini PC N100 16 GB | **Bajo** | La más barata; rinde justo (documento 01) |
| Mac mini Apple Silicon 16 GB | **Medio** | No ampliable: la RAM se elige al comprar y es definitiva |
| Sobremesa x86 + GPU 12 GB | **Medio-alto** | Ampliable y reparable; el más caro de operar |
| Reutilizar equipo existente | — | **[medido]** El actual no cumple el mínimo |

**Un detalle que conviene no pasar por alto en Apple Silicon:** la memoria es unificada y **no
ampliable**. Elegir 16 GB en lugar de 8 no es una preferencia, es una decisión irreversible que
determina qué modelos podrá correr esa máquina durante toda su vida.

## 4. Coste total de propiedad a 5 años

**[estimación]**, sumando adquisición y electricidad:

| | Mini PC N100 | Apple Silicon | x86 + GPU |
|---|---|---|---|
| Adquisición | Bajo | Medio | Medio-alto |
| Electricidad (5 años) | ~40 € | ~35 € | ~360 € |
| Reparabilidad | Media | **Baja** | **Alta** |
| Riesgo de obsolescencia | Alto (rinde justo) | Medio | **Bajo** (ampliable) |

Las dos últimas filas no son cuantificables pero pesan a 10 años (D20). Un equipo ampliable absorbe
un modelo mayor con más RAM; uno sellado obliga a sustituirlo entero.

## 5. Mantenimiento

El coste que se olvida al comparar precios.

| Tarea | Frecuencia | Notas |
|---|---|---|
| Actualizaciones de SO | Mensual | Menor en Debian estable (documento 01) |
| Actualización de Ollama / modelos | Trimestral | **Cada cambio de modelo exige re-verificar la calidad de decisión**, no sólo la latencia |
| Verificación de respaldos | Mensual | D31 + verificación de dispositivo real (D27) |
| Revisión del audit log | Según uso | Crece con el uso; requiere política de rotación |
| Preflight check | Cada sesión | Ya automatizado (D27) |

### Dos costes recurrentes que conviene presupuestar desde ahora

**Re-verificar el modelo tras cada actualización.** No es opcional: el prompt del sistema tiene un
acoplamiento blando al modelo, y un modelo nuevo puede elegir peor sin que la latencia empeore. Un
cambio silencioso de modelo puede degradar la utilidad sin que ninguna métrica de rendimiento lo
delate.

**Rotación del audit log.** Es append-only con `fsync` (H2, M2.0). Crece monótonamente y **es también
la materia prima de las señales implícitas** de M3.0. Una política de rotación mal diseñada podría
borrar el historial que la anticipación necesita — conviene decidirla junto con la retención de
datos, no como tarea de limpieza.

## 6. Lo que no está cuantificado

Con honestidad, para que nadie lo confunda con un presupuesto:

- **Home Assistant y dispositivos** (E2): sin estimar. Depende por completo del hogar.
- **Micrófono y altavoz de calidad conversacional**: necesarios para la captura de voz que sigue
  diferida, y no triviales — un micrófono deficiente degrada el STT antes de que el modelo intervenga.
- **Coste de oportunidad de la espera**: mientras no haya entorno, M3 no avanza. No es monetario,
  pero es real.

## 7. Recomendación del CTO

Para los escenarios **E1/E2** (documento 02), el criterio económico apunta a una plataforma de bajo
consumo, y el argumento fuerte no es el precio de compra sino **el coste de operarla encendida
durante años**.

Pero el criterio económico **no debería decidir solo**. A 10 años, reparabilidad y ampliabilidad pesan
tanto como el consumo, y ahí la opción más eficiente no es la mejor. Si el escenario acabara siendo
**E3/E4**, el criterio cambia por completo: pasa a mandar el coste unitario y la disponibilidad de
soporte, no la elegancia de la solución.

**Es otra razón para responder antes la pregunta del documento 02.**
