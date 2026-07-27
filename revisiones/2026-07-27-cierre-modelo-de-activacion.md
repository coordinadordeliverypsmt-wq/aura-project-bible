---
documento: "Cierre del modelo de activacion — fotografia del estado real"
fecha: 2026-07-27
autor: "CTO"
encargo: "CEO — revision breve de estado (no una Architecture Review nueva) antes de empezar a declarar nuevas capacidades"
estado: "Cierre de la infraestructura del modelo de activacion. La arquitectura del modelo esta cerrada; el siguiente objetivo son las capacidades."
base: "main @ b40b8f3 (origin/main sincronizada) — Quality Gate PASS (362 passed / 3 skipped)"
---

# Cierre del modelo de activacion

Fotografia del estado real del sistema tras completar las cuatro etapas de implementacion del modelo de
activacion (Etapas 1-4), como referencia antes de incorporar nuevas capacidades.

## 1. Objetivos previstos

Implementar, sin evolucionar el diseno cerrado en la Architecture Review, el flujo:

> `Detectores -> ActivationContextBuilder -> ActivationContext -> CapabilityManager -> PlanActivacion -> Composicion`

con cuatro etapas pequenas, cada una bajo TDD + mutacion + Quality Gate, manteniendo **el comportamiento
observable de Memoria identico** durante toda la migracion y **sin declarar capacidades nuevas** hasta
tener el flujo validado extremo a extremo.

## 2. Objetivos implementados

| Etapa | Entregado | Integracion |
|---|---|---|
| **1** | Rename mecanico `PerfilEfectivo` -> `PerfilHardware`. Sin cambio de comportamiento. | `fe581c2` / `2a8b800` |
| **2** | `ActivationContext` como **unico contrato de entrada** (`hardware` + `capacidades_soportadas`), `Fuente.SOPORTE` + operadores de presencia, firma `planificar(contexto)`. | `11e96db` / `1988e5d` |
| **3** | `ActivationContextBuilder` (ejecutar/normalizar/construir, con aislamiento de fallos y registro) + Protocols `DetectorHardware` / `DetectorEntorno` por ambito. | `23c7164` / `b0f6ff7` |
| **4** | Cableado del flujo definitivo en la composicion; ensamblaje provisional retirado. | `8478c5f` / `b40b8f3` |

**Estado:** flujo completo **operativo**. Quality Gate **PASS (362 passed / 3 skipped)**;
`main == origin/main @ b40b8f3`, arboles limpios, 0 commits sin publicar.

**Evidencia de transparencia (Etapa 4, diff automatico ANTES/DESPUES vacio):** estado de Memoria en perfil
alto (`activa`) y bajo (`degradada`) con identicos motivos; recall funcional identico; `PlanActivacion`
identico; latencia de `componer()` sin regresion (mediana 4,2 ms en 7 arranques).

## 3. Invariantes preservados

| Invariante | Como se preserva hoy | Como se hace cumplir |
|---|---|---|
| **I-A1 · Manager puro** | `planificar(contexto) -> plan`, sin efectos ni estado retenido. | Prueba de determinismo + mutacion. |
| **I-A2 · Detectores por ambito** | `DetectorHardware.detectar()` (metricas D44) y `DetectorEntorno.capacidades_soportadas()` (hechos de dominio); ninguno invade el otro. | Prueba de contratos por ambito. |
| **I-A3 · Builder sin reglas** | Solo ejecuta, normaliza y construye; aisla fallos y **registra**; **no valida I-AC1**. | **Prueba por AST**: no puede referenciar Registry/Manager/Estado/Decision/Plan/reglas. |
| **I-A4 · Contexto, unico contrato de entrada** | El Manager recibe un solo argumento. | Prueba de firma + inmutabilidad. |
| **I-A5 · Registry declarativo** | Declaraciones pasivas y serializables; toda la inteligencia en el Manager. | Prueba de pasividad/serializacion. |
| **I-AC1 · Solo nombres de capacidades** | Documentado en el contrato; el Builder **preserva** lo que producen los detectores. | Disciplina de revision (decision explicita del CEO: no se valida en ejecucion). |
| **I-AC2 · No enriquecer sin concepto de dominio** | `capacidades_soportadas: frozenset[str]`; ningun DTO artificial. | Documentado en el contrato. |
| **Dependencias unidireccionales** | Detectores -> tipos; Builder -> tipos + Protocols; Manager -> tipos + Registry; Composicion -> todo. | Verificado: los 7 ciclos prohibidos dan 0. |
| **Builder reutilizable** | Una CLI/servicio/test construye un contexto **sin** importar la composicion ni el Manager. | Verificado en ejecucion. |

## 4. Diferencias respecto al diseno original

**Ninguna diferencia de fondo.** El diseno aprobado resulto suficiente: no hubo que detenerse a proponer
cambios de arquitectura en ninguna etapa. Dos precisiones de detalle, ambas aprobadas por el CEO durante
la implementacion:

1. **`capacidades_soportadas` es `frozenset[str]`**, no una coleccion de objetos. Se analizo `HechoSoporte`
   desde DDD y se descarto: no es un concepto del dominio, sino un envoltorio tecnico sobre un `str`
   (I-AC2 fija cuando se reconsiderara).
2. **La prueba de "no decide" verifica responsabilidad, no numero de metodos**: ningun metodo publico del
   Builder puede tener anotacion de retorno `Estado`/`Decision`/`PlanActivacion` (una utilidad futura como
   `diagnostico() -> str` no rompe nada).

Conceptos permanentes introducidos, **exactamente los previstos**: `ActivationContext`,
`ActivationContextBuilder`, `DetectorHardware`, `DetectorEntorno`, `Fuente.SOPORTE` (+ los operadores
`PRESENTE`/`AUSENTE`, inseparables de esa fuente). Coste accidental: **nulo**.

## 5. Deuda tecnica consciente

Toda ella **registrada y deliberada**, no acumulada por descuido:

| Elemento | Naturaleza | Condicion para resolverse |
|---|---|---|
| **Detector de hardware real** (mide capacidad efectiva, D44) | Latente-prevista | Requiere hardware para construirse y validarse. Hoy se inyecta el perfil. |
| **Detectores de entorno reales** | Latente-prevista | Los construira cada capacidad que los necesite; hoy ninguna declarada los usa. |
| **`_PerfilInyectado`** (composicion) | **Adaptador temporal** de cableado | Se elimina al llegar el detector real, **sin tocar Builder ni Manager** (verificado por AST: sin comparaciones, umbrales ni decisiones). |
| **Umbrales de las reglas de Memoria** | Placeholders calibrables | Calibracion con pruebas reales (D44) al disponer de hardware; viven en la declaracion (datos), no en la logica. |
| **Memoria N2/N3** | Latente-prevista | El punto de extension existe; **no hay seleccion dinamica entre implementaciones inexistentes** (N1 es el nivel efectivo). |
| **I-AC1 sin verificacion automatica** | Disciplina de revision | Decision explicita del CEO: validarlo en el Builder rompería I-A3. |

## 6. Proximo bloque funcional

La infraestructura del modelo deja de ser el objetivo. El siguiente bloque es **incorporar capacidades
sobre una base ya validada**, con el patron obligatorio de D46 y el criterio de incorporacion vigente:
una capacidad entra al Registry **solo** cuando puede completar sus diez campos **sin hipotesis**
(decision arquitectonica que la aprueba, contrato funcional, dependencias, comportamiento degradado,
garantias de seguridad e informacion suficiente).

Estado del catalogo hoy: **una sola capacidad declarada — memoria** —, validada extremo a extremo y
plantilla de referencia para las siguientes.

Cuando el CEO decida abrir ese bloque, el primer paso sera determinar **que capacidad** alcanza ese
criterio de madurez, y **madurar su arquitectura** si aun no lo alcanza.

## 7. Reglas de trabajo para las siguientes fases (CEO, 2026-07-27)

Con este cierre, **el modelo de activacion queda cerrado**: cualquier trabajo posterior es
**implementacion, no evolucion arquitectonica**. Rigen estas cinco reglas:

1. **No se introducen** nuevos conceptos, tipos, capas ni abstracciones **sin evidencia objetiva** de que
   el diseno actual es insuficiente.
2. Los invariantes **I-A1…I-A5** e **I-AC1…I-AC2** son **restricciones permanentes**: no pueden relajarse
   durante la implementacion.
3. La **deuda tecnica documentada** (§5) permanece como **deuda consciente**: no se resuelve
   anticipadamente "por si acaso".
4. **Cada nueva capacidad reutiliza el modelo ya construido**: Detectores → ActivationContextBuilder →
   ActivationContext → CapabilityManager → PlanActivacion → Composicion.
5. Si aparece una **limitacion real** que obligue a modificar la arquitectura: **detenerse de inmediato**,
   presentar la evidencia y **esperar decision explicita** del CEO. Ninguna decision de diseno por
   iniciativa propia.

Metodo de trabajo en cada etapa: **TDD (RED → GREEN → refactor), verificacion por mutacion y Quality
Gate**, con gate de integracion del CEO.
