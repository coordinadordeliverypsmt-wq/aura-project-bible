---
documento: "Roadmap de M3 reordenado tras D34"
fecha: 2026-07-21
autor: "CTO"
motivo: "Ausencia de instalación real de Home Assistant; D34 prohíbe fabricar un entorno para aprobar el milestone"
---

# Roadmap de M3 — reordenado

## 1. Qué bloquea qué

Aplicando D34 con honestidad, y sin fabricar trabajo para aparentar avance:

| Fase | Depende de | Estado |
|---|---|---|
| M3.0 · Infraestructura de captura | — | ✅ **Completada** |
| M3.1 · Hogar real | **Instalación real de HA + dispositivos** | ⏸ **Pendiente (D34)** |
| M3.2 · Aprendizaje continuo | Datos de uso real | ⚠ **Parcialmente bloqueada** — ver §2 |
| M3.3 · Anticipación (CM4) | M3.2 + datos reales + calidad de modelo | ⏸ **Bloqueada** |
| M3.4 · Avatar | Plataforma de despliegue (D33) | ⏸ **Bloqueada** |

**Tres de las cinco fases dependen de la misma decisión pendiente: el escenario de despliegue.** No
es una coincidencia desafortunada, es la estructura del problema: M3 se llama *Presencia*, y la
presencia ocurre en un sitio concreto que todavía no está definido.

## 2. Por qué M3.2 está *parcialmente* bloqueada

D34 aplica a M3.2 igual que a M3.1, y conviene decirlo antes de que alguien lo proponga: **inferir
preferencias a partir de datos sintéticos sería el mismo error que validar el hogar con mocks.** La
calidad de una inferencia depende de los datos sobre los que infiere; probarla con datos fabricados
demostraría que el algoritmo corre, no que acierta.

Pero M3.2 tiene dos mitades con naturalezas distintas:

| Mitad | Naturaleza | ¿Necesita datos reales? |
|---|---|---|
| **M3.2a · Soberanía del modelo del usuario** — ver, corregir, exportar y borrar lo que AURA cree saber | **Determinista** | **No.** "Si corrijo X, X queda corregido" se verifica sin datos reales |
| **M3.2b · Inferencia de preferencias** | **Probabilística** | **Sí.** Su corrección *es* su acierto sobre datos reales |

**M3.2a es trabajo legítimo y disponible ahora.** No es un entorno artificial: es un mecanismo cuya
corrección se comprueba de forma determinista, igual que la captura de M3.0.

Además es un requisito vigente de la Bible que nadie ha implementado:

> *"El modelo del usuario es dato del usuario: local, cifrado, exportable"* — 4.4 §2, remitiendo a
> 4.1 §5 y ADR-0001.

Y estaba en la Definition of Done de M3.0 que el CEO aprobó: *"Capacidad 8: preferencias inferidas
verificables y corregibles por el usuario"*.

### El argumento de orden

Construir la corregibilidad **antes** que la inferencia no es solo lo posible: es lo correcto. Un
sistema que infiere sobre el usuario y no le deja corregirse convierte cada error en permanente. Si
se construyen en el orden inverso, existe una ventana —de duración indefinida, porque depende del
hardware— en la que AURA acumula conclusiones sobre una persona que esa persona no puede rectificar.

## 3. Orden propuesto

| # | Fase | Estado |
|---|---|---|
| 1 | **ADR de preferencias inferidas (P5)** | Disponible — determina el esquema antes de inferir |
| 2 | **M3.2a · Soberanía del modelo del usuario** | Disponible |
| 3 | M3.2b · Inferencia | Espera datos reales |
| 4 | M3.1 · Hogar | Espera instalación real (D34) |
| 5 | M3.3 · Anticipación | Espera 3 |
| 6 | M3.4 · Avatar | Espera plataforma (D33) |

## 4. Lo que este roadmap no hace

**No inventa fases para llenar el hueco.** Tras M3.2a, el trabajo disponible que no dependa del
escenario de despliegue se agota. Decirlo ahora es preferible a descubrirlo dentro de tres fases
mientras se acumula trabajo de dudoso valor.

Si al terminar M3.2a el escenario de despliegue sigue sin definirse, mi recomendación será **detener
M3 y declararlo bloqueado**, en lugar de seguir produciendo infraestructura que nadie puede validar.
Un milestone honestamente detenido informa; uno que avanza sobre decorados, no.
