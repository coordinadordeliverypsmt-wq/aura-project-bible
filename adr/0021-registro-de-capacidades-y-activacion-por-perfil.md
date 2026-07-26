---
numero: ADR-0021
titulo: "Registro de capacidades y activacion automatica por perfil de capacidad efectiva (Capability Registry / Manager)"
estado: accepted
fecha: 2026-07-26
fecha-resolucion: 2026-07-26
decisor: "Mauricio (CEO)"
proponente: "CTO"
impacta: ["ADR-0020", "ADR-0018", "ADR-0019", "ADR-0004", "ADR-0016", "ADR-0003", "P-ARQ-1", "D33", "D34", "D38", "D43", "D44", "D45", "Bible 3.1", "Bible 3.2", "Bible 3.4", "Bible 5.3"]
origen: "Directriz del CEO 2026-07-26: arquitectura completa con capacidades latentes; generalizar ADR-0020 a todo el sistema mediante un Registro de Capacidades"
reabre: "—"
supersede: "—"
superseded-por: "—"
motivo-rechazo: "—"
---

# ADR-0021 — Registro de capacidades y activacion por perfil de capacidad efectiva

## Contexto

**ADR-0020** establecio que la **memoria** se implementa en perfiles de capacidad detras de un contrato
unico, con seleccion automatica por hardware verificado (D27) y capacidad efectiva por pruebas (D44).
**D43** ya declaraba que ese modo de evolucionar "rige cualquier componente futuro con implementaciones
dependientes de recursos". El proyecto, ademas, **ya construye puntos de habilitacion sin construir la
capacidad entera**: bus por escenario (**ADR-0018**, E1 activo / E2 reservado) y marco de conectores
externos (**ADR-0019 / MA.4**, opt-in + transparencia + degradacion, sin un solo conector real).

**Directriz del CEO (2026-07-26).** El objetivo final no es solo que existan capacidades latentes, sino
que AURA disponga de un **Registro de Capacidades (Capability Registry)**: cada capacidad es un **modulo
autonomo** que se **auto-declara**, y un **Capability Manager** —sin conocimiento especifico de ninguna
capacidad— recorre el registro y decide cuales activar segun la **capacidad efectiva** del entorno
(D44). Este ADR generaliza ADR-0020 de la memoria a **todo el sistema**.

## Alternativas consideradas

### A. Logica de activacion dispersa (cada capacidad, o la composicion, decide por si misma)
El orquestador/composicion tendria que conocer cada capacidad y su regla de habilitacion. Contras:
acoplamiento creciente, el nucleo "sabe" de cada capacidad, anadir una capacidad toca el nucleo.
Contradice P-ARQ-4 (sustituibilidad) y D40 (la composicion ensambla, no decide). **Descartada.**

### B. Registro de capacidades autodeclarativas + Manager agnostico (elegida)
Inversion de dependencias: la capacidad declara lo que necesita; el Manager solo evalua el registro
contra la capacidad efectiva. Materializa la directriz del CEO. Por ser formalizacion de una decision ya
tomada, se omiten los 4 niveles (D3).

## Decision

### 1. Capacidad = modulo autonomo autodeclarativo
Cada capacidad del sistema es un **modulo autonomo, autocontenido, verificable y auditable** que declara
en el **Registro de Capacidades**, como minimo, **diez campos**. Un contrato completo por capacidad evita
que atributos como la seguridad o la autonomia queden dispersos entre distintos ADR o documentos:

1. **Contrato funcional** — la interfaz estable que ofrece cuando esta activa (P-ARQ-4).
2. **Prerequisitos minimos** — recursos necesarios para activarse (RAM, GPU, CPU, disco, dependencias de entorno).
3. **Mecanismo de deteccion** — como se comprueba, con **pruebas reales** (D44), si el entorno la soporta;
   no specs, sino capacidad efectiva verificada (latencia, memoria disponible, velocidad de inferencia).
4. **Comportamiento degradado** — que ofrece cuando no puede activarse plenamente; degradacion **limpia**,
   nunca fallo silencioso (coherente con ADR-0019 y el checklist de arquitectura 3.1 §2.3.10).
5. **Criterio de promocion automatica** — la condicion objetiva (verificada por 3) bajo la cual el Manager
   la **activa** o sube su nivel.
6. **Criterio de degradacion automatica** — la condicion bajo la cual el Manager la **desactiva** o baja su
   nivel, **sin perdida de informacion ni de coherencia** (ver §7).
7. **Grado de latencia** — **activable** (implementacion ya existente tras el contrato, se enciende/apaga
   sola por perfil) o **prevista** (la arquitectura reserva su contrato y su lugar; la implementacion se
   realizara y validara cuando el hardware/datos lo permitan, ADR-0004, sin rediseno).
8. **Dependencias** — otras capacidades o servicios de los que depende.
9. **Garantias de seguridad a mantener** — las que deben preservarse mientras este activa (gate HITL,
   ADR-0001, minimizacion). **Innegociables** (ver §4); acotan el campo 10.
10. **Nivel de autonomia permitido** — el nivel **maximo** de autonomia de la capacidad y como evoluciona
    segun recursos y decisiones arquitectonicas vigentes, en una escala creciente y **siempre subordinada
    al campo 9 y a P-ARQ-1 / ADR-0003 / Bible 5.3**: (a) solo observacion, (b) recomendacion, (c) ejecucion
    con autorizacion (HITL), (d) ejecucion automatica controlada, (e) ejecucion autonoma limitada, (f)
    ejecucion autonoma completa (**solo cuando la arquitectura lo permita**). El Manager decide no solo
    **si** activar una capacidad, sino **hasta donde** puede actuar en ese hardware y contexto — nunca por
    encima del gate HITL de una accion de lista roja (D9/ADR-0003).

### 2. Capability Manager agnostico
El **Capability Manager no conoce ninguna capacidad concreta**. En instalacion/arranque/reconfiguracion:
(a) determina la **capacidad efectiva** del entorno (D44: specs + pruebas reales + prerequisitos minimos);
(b) recorre el registro; (c) **promueve** las capacidades cuyo criterio de promocion (campo 5) se cumple y
cuyas dependencias (8) y garantias de seguridad (9) estan satisfechas, y **degrada** las que cumplen su
criterio de degradacion (campo 6); (d) fija **hasta donde** puede actuar cada una segun su nivel de
autonomia permitido (campo 10), nunca por encima de sus garantias de seguridad. Anadir una capacidad nueva
es **registrar un modulo**, no tocar el Manager ni el nucleo.

### 3. Dos grados de latencia (ninguna capacidad es "pendiente")

| Grado | Significado | Al cambiar el hardware |
|---|---|---|
| **Latente-activable** | Implementacion ya existe tras el contrato; inactiva solo por perfil | **Activacion automatica literal** |
| **Latente-prevista** | La arquitectura reserva contrato y lugar; la implementacion se realiza+valida cuando el hardware/datos lo permiten (ADR-0004) | Se **habilita** = se construye+valida en su lugar previsto, **sin nueva arquitectura** |

Esta distincion respeta **regla 13 / D3 / D34 / D38** (no se construye ni se especula lo que no se
necesita ni puede validarse): "preparada para todas" significa que **todas tienen su lugar y su contrato
en el registro**, no que todas esten construidas y solo apagadas.

### 4. Invariante de seguridad (D33) — innegociable
Activar mas capacidades **nunca** relaja la seguridad. Cada capacidad declara (campo 9) las garantias que
debe preservar; el Manager **no activa** una capacidad si sus garantias no pueden mantenerse. **La utilidad
escala con el hardware; la seguridad, jamas** (ADR-0016 / D33). Encender Home Assistant no salta el gate
HITL; encender vision no elude ADR-0001/minimizacion. **El nivel de autonomia (campo 10) esta subordinado
a este invariante y al gate HITL (P-ARQ-1 / ADR-0003 / Bible 5.3):** por mucha capacidad efectiva que
tenga el hardware, una accion de lista roja **siempre** requiere confirmacion humana. La autonomia escala
con los recursos y el contexto **dentro** de la seguridad, nunca por encima de ella.

### 5. Alcance — todo el sistema
Aplica a **toda** capacidad, no solo a la memoria: **IA local, memoria, modelos de inferencia, voz,
vision, Home Assistant, automatizaciones, agentes, conectores externos, avatar y cualquier capacidad
futura**. La memoria (ADR-0020) pasa a ser **una capacidad mas del registro**; ADR-0018 y ADR-0019 son
**instancias** del patron.

### 6. Principio de evolucion (formaliza D45)
AURA **nunca cambia de arquitectura** al mejorar el hardware; **solo incrementa el numero de capacidades
que puede ejercer**. Por tanto: **nunca** ediciones Lite/Pro/Enterprise; **nunca** un "AURA 2"; **nunca**
migraciones manuales entre perfiles; el usuario **instala AURA una sola vez** y **jamas elige perfiles,
ediciones o versiones**. AURA detecta el entorno, determina el perfil efectivo (D44) y **se reorganiza
sola**, habilitando o deshabilitando capacidades de forma **transparente, reversible y sin perdida de
memoria, configuracion, historial ni compatibilidad**. **Objetivo final:** al conectar AURA a un equipo
mas potente, este simplemente **"despierta"** capacidades que la arquitectura **ya tenia previstas** —no
aparece un proyecto distinto ni una nueva version—.

### 7. Crecer y retroceder: evolucion simetrica sin perdida
La evolucion **no es solo "activar mas"**. Toda capacidad debe poder **crecer y tambien retroceder
automaticamente** —promocion (campo 5) y degradacion (campo 6)— **sin perdida de informacion ni de
coherencia del sistema**. Si el hardware disminuye o cambia el contexto, el Manager **degrada
elegantemente** (usando el comportamiento degradado del campo 4), conservando memoria, configuracion e
historial y preservando el contrato de datos (ADR-0020). La reversibilidad es una **propiedad de primera
clase**, no un caso excepcional: un portatil modesto → un equipo potente → de vuelta al modesto debe
recorrer ese camino sin que el usuario pierda nada ni intervenga.

## Consecuencias

**Positivas:** un solo proyecto/codigo/arquitectura para todo el rango de hardware; el nucleo no crece al
anadir capacidades (registro + Manager agnostico); la evolucion es aditiva y **simetrica** (crece y
retrocede sin perdida); la seguridad y la autonomia quedan **autocontenidas** en cada capacidad y
verificadas por el Manager. **Negativas:** hay que mantener y probar el registro y el Manager, y cada
capacidad debe declarar sus **diez campos** con rigor; los **criterios de promocion/degradacion por
capacidad** deben definirse con pruebas reales (dependiente de hardware, fase posterior). **Riesgos
aceptados:** la calibracion de los umbrales D44 por capacidad es la incognita hardware-sensible, a medir
al reanudar; el registro debe ser la **fuente unica** de la clasificacion de capacidades (D41).

## Impacto (acta D11 — obligatorio)

| Dimensión | Impacto |
|---|---|
| Seguridad | Neutro/invariante: la seguridad no escala con el hardware (D33); cada capacidad declara y el Manager exige sus garantias (campo 9); el nivel de autonomia (campo 10) queda subordinado al gate HITL (P-ARQ-1/ADR-0003). |
| Privacidad | Neutro/positivo: capacidades locales (ADR-0001); activar mas no crea canales de fuga; conectores externos siguen ADR-0019. |
| Modularidad | Muy positivo: capacidades como modulos autonomos tras contrato (P-ARQ-4); Manager agnostico; nucleo estable (D40). |
| Costo | Positivo: un solo codigo, sin ramas/ediciones; se activa solo lo que el hardware justifica (D26, regla 13). |
| Experiencia de usuario | Positivo: instalar una vez; mas hardware = mas capacidad, sin intervencion ni migracion. |
| Mantenimiento futuro | Requiere mantener registro + Manager y probar activacion; a cambio, anadir capacidades no toca el nucleo. |

## Trazabilidad

**Generaliza ADR-0020** (memoria por perfiles) a todo el sistema y se convierte en **uno de los pilares
fundamentales de la arquitectura de AURA** (ya no es un ADR de memoria ni de hardware). Convierte
**ADR-0018** y **ADR-0019** en instancias del patron. Se apoya en **ADR-0004** (evolucion sin rediseno,
interfaces estables), **P-ARQ-4** (sustituibilidad), **ADR-0016 / D33** (seguridad invariante, utilidad
escalable), **P-ARQ-1 / ADR-0003 / Bible 5.3** (HITL: acota el nivel de autonomia del campo 10), **D27**
(hardware verificado), **D43** (evolucion por capacidades), **D44** (capacidad efectiva por pruebas),
**D41** (fuente unica: el registro) y **regla 13 / D3 / D34 / D38** (no construir/especular de mas: de
ahi los dos grados de latencia). Registra el principio permanente **D45**. **Requiere actualizar la
Bible** (3.1 principios; 3.2 arquitectura de referencia; 3.4 capacidades como modulos) —**materia
reservada al CEO**: la propuesta queda preparada y **en espera** hasta consolidar D45 + ADR-0021, para
hacer una sola actualizacion (una unica fuente de verdad)—. **Modulos de codigo: ninguno en esta fase**
(congelacion controlada, linea base 2026-07-26): este ADR fija el contrato y el lugar del Capability
Registry/Manager; su implementacion es una fase posterior, a habilitar cuando exista hardware para
validarla (D34/D44).
