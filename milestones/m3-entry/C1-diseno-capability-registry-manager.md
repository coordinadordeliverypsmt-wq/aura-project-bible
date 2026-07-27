---
documento: "C1 — Diseno arquitectonico del Capability Registry y el Capability Manager"
fecha: 2026-07-26
autor: "CTO"
estado: "Diseno para revision y aprobacion del CEO. Sin codigo (congelacion selectiva; solo arquitectura)."
origen: "Fase C, etapa C1; autorizacion del CEO 2026-07-26 (interpretacion 2: congelacion selectiva por capacidad)"
materializa: "ADR-0021, D45, Bible 3.1 P-ARQ-9/§2.4"
---

# C1 — Diseno del Capability Registry y el Capability Manager

Materializa el mecanismo que ADR-0021 especifico y cuya implementacion se difirio. Es trabajo
**determinista**, disponible sin hardware: cierra AURA *como arquitectura* dejando latente solo la
ejecucion dependiente de recursos (interpretacion 2, adoptada por el CEO). Este documento es **diseno**:
no escribe codigo.

## 1. Objetivo y alcance

- **Disenar** el **Capability Registry** (registro de capacidades-subsistema autodeclarativas) y el
  **Capability Manager** (mecanismo agnostico que activa/degrada por perfil de capacidad efectiva).
- **Alcance:** investigacion, contratos, interfaces, invariantes, estrategia de pruebas, riesgos, plan de
  implementacion, criterios de aceptacion y DoD. **Sin codigo.**
- **Fuera de alcance:** implementar el detector de perfil real (D44) y calibrar umbrales (latente-prevista,
  requiere hardware); implementar capacidades concretas.

## 1.1 Criterio guia de la Fase C (CEO, 2026-07-26)

La Fase C **no existe para producir documentacion**; existe para dejar preparada la **arquitectura
definitiva** de AURA. La documentacion es una consecuencia, no el objetivo. Por tanto, toda decision de
C1 debe responder afirmativamente a:

> **¿Esto acerca a AURA a poder activarse automaticamente cuando cambie el hardware?**

Si **si**, forma parte de C1. Si **no**, es documentacion innecesaria u optimizacion prematura y se
descarta. Se mantiene la filosofia del proyecto —**arquitectura primero, contratos primero, comportamiento
observable primero, implementacion despues**— **sin** caer en una fase de solo-documentos: los contratos e
invariantes de este diseño existen para ser **ejercitados por comportamiento observable**, no para
quedarse en prosa.

## 2. Investigacion — estado actual (evidencia)

| Pieza existente | Que aporta a C1 |
|---|---|
| `core/conectores_externos.py` (MA.4, ADR-0019) | **Precedente directo del patron:** declaracion `frozen` versionada + funcion `habilitar()` determinista que produce `(activos, rechazados, informe ordenado)`, probada con dobles, sin conocimiento de ningun proveedor. El Manager es este patron escalado. |
| `core/registro.py` (`RegistroAdaptadores`) | Registro de **capacidad-accion** (verbos: "encender_dispositivo") → adaptador. **Nivel distinto** al Capability Registry (capacidad-**subsistema**). Se conserva; el Registry es la capa superior. |
| `composicion.py` | **Patron de integracion:** la composicion llama al gate (`habilitar(...)`) y ensambla con el resultado. El Manager se integrara igual (la composicion consulta el plan y ensambla). D40: la composicion ensambla, no decide. |
| `contracts.py` (`Adapter.capabilities`) | Las capacidades-accion ya son datos declarados. |

**Gap confirmado:** no existe detector de perfil / capacidad efectiva (D44). En C1 se **abstrae tras una
interfaz**; su implementacion real y su calibracion son **latente-prevista** (se construyen con hardware).

**Distincion de dos niveles (clave para no confundir):**
- **Capacidad-accion** (existente, `RegistroAdaptadores`): "encender_dispositivo", "leer_archivo". Nivel operativo.
- **Capacidad-subsistema** (C1, ADR-0021): "memoria", "voz", "vision", "inferencia_local", "avatar". Nivel
  arquitectonico. Una capacidad-subsistema, cuando esta activa, puede aportar varias capacidades-accion.

## 3. Contratos (datos, no implementacion)

### 3.1 Declaracion de capacidad — los 10 campos de ADR-0021
Una **dataclass `frozen` y versionada** (patron `DeclaracionTransparencia` de MA.4), fuente unica de los
campos (D41; ADR-0021 es normativo):

| # | Campo | Tipo propuesto (diseno) |
|---|---|---|
| 1 | contrato funcional | id + version del Protocol que expone (str + int); no la implementacion |
| 2 | prerequisitos minimos | estructura de recursos (ram, gpu, cpu, disco, deps de entorno) |
| 3 | mecanismo de deteccion | referencia a una **sonda** (nombre de prueba real, D44); ejecutada por el detector |
| 4 | comportamiento degradado | descriptor de que ofrece si no puede activarse plenamente (incl. "nada" si es prevista) |
| 5 | criterio de promocion | **predicado** sobre el perfil efectivo → puede activar/subir |
| 6 | criterio de degradacion | **predicado** sobre el perfil efectivo → debe desactivar/bajar |
| 7 | grado de latencia | enum {`activable`, `prevista`} |
| 8 | dependencias | nombres de otras capacidades requeridas |
| 9 | garantias de seguridad | conjunto de invariantes a preservar (referencias: gate HITL, ADR-0001, minimizacion) |
| 10 | nivel de autonomia permitido | enum ORDENADO: observacion < recomendacion < hitl < automatica_controlada < autonoma_limitada < autonoma_completa |

Los predicados (5/6) se **parametrizan**; sus umbrales reales se calibran con hardware (D44), no en C1.

### 3.2 Perfil de capacidad efectiva (`PerfilEfectivo`)
Dataclass con: specs detectadas + resultados de **pruebas reales** (latencia, memoria disponible, velocidad
de inferencia) + recursos. Producido por un **`DetectorPerfil` (Protocol)**: `detectar() -> PerfilEfectivo`.
En C1 el detector es un **doble inyectable**; el real es latente-prevista.

### 3.3 Plan de activacion (`PlanActivacion`)
Dataclass `frozen` (patron `Habilitacion` de MA.4): `activas`, `degradadas`, `latentes`, `informe`
determinista (ordenado por nombre, independiente del orden de entrada).

## 4. Interfaces (firmas, sin cuerpo)

- `Capacidad` — la declaracion de 10 campos (§3.1).
- `PerfilEfectivo` — §3.2.
- `DetectorPerfil` (Protocol): `detectar() -> PerfilEfectivo`. Real diferido; doble en pruebas.
- `CapabilityManager.planificar(capacidades: Iterable[Capacidad], perfil: PerfilEfectivo) -> PlanActivacion`.
  Funcion **pura y determinista**: recorre el registro, evalua criterios, resuelve dependencias, acota
  autonomia, produce el plan. **No conoce ninguna capacidad concreta.**
- Integracion: `composicion.py` consulta `planificar(...)` y ensambla segun el plan (analogo al gate MA.4).

## 5. Invariantes (a garantizar por pruebas)

- **I1 — Seguridad no escala con hardware (D33/P-ARQ-1).** La autonomia efectiva ≤ nivel declarado (campo
  10) **y** ≤ lo que permiten las garantias (campo 9). Una accion de **lista roja** siempre pasa por HITL
  (ADR-0003/5.3), sea cual sea el perfil. El Manager **nunca** eleva la autonomia por capacidad efectiva.
- **I2 — Degradacion sin perdida (D45).** Degradar conserva memoria, configuracion, historial y
  compatibilidad; el contrato de datos se preserva (ADR-0020).
- **I3 — Determinismo (D41).** Mismo `(registro, perfil)` → mismo plan; informe ordenado, independiente del
  orden de entrada.
- **I4 — Dependencias (campo 8).** Una capacidad no se activa si sus dependencias no estan activas.
- **I5 — Manager agnostico (P-ARQ-4/D40).** El Manager no referencia ninguna capacidad concreta; anadir una
  capacidad = **registrarla**, sin tocar el Manager ni el nucleo.
- **I6 — Latente-prevista no se "enciende" (D34/D38).** Una capacidad `prevista` (sin implementacion) **no**
  pasa a activa aunque el perfil lo permitiera; permanece latente hasta que su implementacion exista (su
  grado pase a `activable`). Evita fingir capacidad no construida.
- **I7 — Simetria reversible (D45).** Promocion y degradacion usan los criterios declarados (5/6); el camino
  perfil↑ y perfil↓ es reversible y sin perdida.

## 6. Estrategia de pruebas (TDD determinista, sin hardware, sin dependencias nuevas)

Pruebas de **comportamiento observable** sobre `planificar(...)`, con **perfiles-doble** y **capacidades-doble**:

1. **Promocion:** perfil que cumple criterio (5) → capacidad `activable` queda en `activas`.
2. **Degradacion:** perfil que cae bajo (6) → capacidad activa pasa a `degradadas`; un doble registra que el
   estado/datos se conservan (I2).
3. **Dependencias (I4):** dependencia no satisfecha → la capacidad no se activa.
4. **Seguridad (I1):** capacidad con autonomia `autonoma_completa` + accion de lista roja → el plan **no**
   eleva la autonomia por encima del gate HITL.
5. **Determinismo (I3):** mismo input en distinto orden → mismo plan e informe.
6. **Latente-prevista (I6):** capacidad `prevista` + perfil que "daria" → permanece en `latentes`.
7. **Agnosticismo (I5):** registrar una capacidad-doble nueva no obliga a tocar el Manager.
8. **Simetria (I7):** perfil↑ activa; perfil↓ degrada; volver a perfil↑ re-activa sin perdida.

**Verificacion por mutacion:** cada invariante tiene una prueba que **falla** contra un Manager degradado
(que ignore dependencias, eleve la autonomia, o pierda estado al degradar). Todo local, stdlib (D24).

## 7. Riesgos

- **R1 — Sobre-diseno (regla 13/D3).** Mitigacion: modelar solo los 10 campos de ADR-0021; el detector se
  **abstrae**, no se construye; sin campos especulativos.
- **R2 — Confusion de niveles.** Mitigacion: §2 distingue capacidad-accion (RegistroAdaptadores, se conserva)
  de capacidad-subsistema (Registry).
- **R3 — Calibracion D44 ausente sin hardware.** Mitigacion: criterios (5/6) parametrizados; C1 prueba la
  **logica** con perfiles-doble; los umbrales reales se calibran al llegar el hardware (latente-prevista).
- **R4 — Activar previstas no implementadas (D34/D38).** Mitigacion: invariante **I6** con prueba.
- **R5 — Acoplamiento del Manager.** Mitigacion: invariante **I5**; precedente MA.4.
- **R6 — Autonomia por encima del gate.** Mitigacion: invariante **I1**, el riesgo mas serio; prueba y mutacion.

## 8. Plan de implementacion (para C1-implementacion, requiere tu aprobacion posterior)

Fase de codigo, TDD estricto (RED→GREEN→Quality Gate→mutacion), sin dependencias/servicios/telemetria:
1. `core/capacidades.py`: dataclasses `Capacidad`, `PerfilEfectivo`, `PlanActivacion` + enums (`GradoLatencia`, `NivelAutonomia`).
2. `core/capability_manager.py`: `planificar(...)` (funcion determinista, patron MA.4).
3. `DetectorPerfil` (Protocol) + detector-**doble** para pruebas; el detector real queda declarado como capacidad **latente-prevista**.
4. Integracion minima en `composicion.py` (analoga al gate MA.4): consultar el plan y ensamblar; **no-op** mientras no haya capacidades registradas (como el gate de conectores nacio no-op).
5. `tests/unit/test_capability_manager.py`: los 8 casos de §6 + mutacion.

## 9. Criterios de aceptacion del diseno

- [ ] Cubre los **10 campos** de ADR-0021 sin duplicar su definicion normativa (D41).
- [ ] Invariantes **I1–I7** explicitos, cada uno con su prueba en §6.
- [ ] Manager **agnostico** (I5), coherente con MA.4/ADR-0019 y con la integracion en `composicion` (D40).
- [ ] Distingue capacidad-accion de capacidad-subsistema (§2).
- [ ] **Sin decisiones nuevas:** solo materializa ADR-0021/D45/P-ARQ-9.
- [ ] Respeta regla 13/D34/D38: detector abstraido, previstas no se encienden (I6).

## 10. Criterio de salida de C1 (CEO, 2026-07-26)

C1 estara **terminado** cuando existan los siete elementos siguientes. Estado actual de este diseño frente
a cada uno (honesto, sin declarar completo lo que aun es base):

| # | Elemento del criterio de salida | Estado en este diseño |
|---|---|---|
| 1 | Diseño completo del **Capability Registry** | **Base solida** (§2–§4): rol y contrato fijados; las **operaciones** (registrar, unicidad de nombre, consulta) se precisan al implementar, al nivel de `RegistroAdaptadores`. |
| 2 | Diseño completo del **Capability Manager** | **Completo a nivel de contrato e invariantes** (§4–§5); el **algoritmo** (orden de evaluacion, cascada de dependencias) se fija al implementar. |
| 3 | **Contrato definitivo** de las capacidades | **Definido** (§3.1, 10 campos con tipos); se **sella** al ejercitarlo con pruebas. |
| 4 | **Modelo de perfiles por capacidad** | **Definido** (§3.2, `PerfilEfectivo` + criterios 5/6 parametrizados); umbrales reales se calibran con hardware (latente-prevista). |
| 5 | **Estrategia de activacion y degradacion automatica** | **Definida** (§5 I2/I7, §6): bidireccional, sin perdida; se **valida por comportamiento observable** al implementar. |
| 6 | **Integracion prevista con la composicion** | **Prevista** (§4, §8.4): patron MA.4, no-op inicial; se concreta al implementar. |
| 7 | **Plan de pruebas completo** | **Completo** (§6): 8 casos + mutacion. |

**Lectura (coherente con §1.1).** Tres elementos (3, 7 y el contrato/invariantes de 2) estan **completos
como diseño**. Los otros cuatro (Registry operativo, algoritmo del Manager, activacion/degradacion e
integracion) estan **definidos como base**, y su forma **definitiva se sella con comportamiento
observable** —es decir, **implementandolos**, no con mas prosa—. Insistir en cerrarlos solo en documento
seria precisamente la "fase de solo-documentos" que el CEO descarta.

**Decision posterior del CEO** (tras integrar y en la revision global de la Fase C): (a) **implementar C1
inmediatamente** —es determinista y no depende del hardware; cerraria los elementos 1, 2, 5 y 6 por
comportamiento observable (TDD + mutacion)—, o (b) **consolidar C1 con el resto de la Fase C** antes de
implementar. Recomendacion del CTO: dado el criterio guia (§1.1) y que estos cuatro elementos se cierran
mejor con comportamiento observable, la via (a) es la que mas acerca a la activacion automatica.

## 11. Pendiente asociado (diferido a peticion del CEO)

La correccion de la ambiguedad "congelacion total" en la **linea base** y en la frase de **ADR-0021**
(implementacion "a fase posterior") se hara **cuando C1 este validada**, en un **unico movimiento**
documental, para no revisar la documentacion dos veces.
