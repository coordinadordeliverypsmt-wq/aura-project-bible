---
numero: ADR-0019
titulo: "Marco de habilitacion y transparencia de conectores externos (generico, sin conectores concretos)"
estado: accepted
fecha: 2026-07-22
fecha-resolucion: 2026-07-22
decisor: "Mauricio (CEO)"
proponente: "CTO"
impacta: ["ADR-0015", "contexto.py", "composicion.py", "D37", "MA.4"]
origen: "D37 (exige ADR propio para conectores externos); MA.4; reencuadre aprobado por el CEO 2026-07-22"
reabre: "—"
supersede: "—"
superseded-por: "—"
motivo-rechazo: "—"
---

# ADR-0019 — Habilitacion y transparencia de conectores externos

## Contexto

D37 fijo tres condiciones para cualquier conector hacia servicios de terceros —**(1)** habilitacion
explicita (ninguno por defecto), **(2)** transparencia sobre el recorrido del dato, **(3)** ninguno
como requisito— y dejo escrito: *"Su implementacion requerira ADR propio. Hasta entonces, ningun
conector de este tipo se construye."* Este es ese ADR.

Fuerzas en juego:
- **D39 (criterio 8)** autoriza *construir arquitectura que estara lista* para integraciones futuras.
- **D26/D34/D38** lo acotan: nada especulativo, verificable **ahora** y sin entornos artificiales. La
  transparencia *concreta* depende del recorrido de datos de un conector real; construir su contenido
  sin conector seria especular. Lo verificable ahora es el **mecanismo generico**, probado con un doble.
- **ADR-0015:** el Core **no conoce ninguna fuente concreta**; no hay ni debe haber una lista blanca de
  fuentes en el codigo del Core. El mecanismo no puede convertirse en esa lista.
- La **condicion 3 ya esta cumplida:** `RegistroContexto.recoger_todas` degrada ante una fuente caida
  sin derribar la captura (`contexto.py:78`); una fuente externa ausente ya no es un requisito.

## Alternativas consideradas

### A. Disenar la habilitacion/transparencia junto al primer conector real
Pros: la transparencia seria concreta y validable contra un recorrido de datos real. Contras: **no
existe ningun conector aprobado** (D37 los prohibe hasta este ADR); disenarlo ahora seria especular
(D34/D38). **Descartada por el proponente.**

### B. Marco generico, validado solo con un doble (elegida)
Formaliza la decision ya tomada por el CEO (reencuadre de MA.4). Por ser formalizacion de un
mecanismo aprobado, se omiten los 4 niveles (D3).

## Decision

Se define un **mecanismo generico y reutilizable**, sin logica de ningun proveedor concreto:

1. **Auto-declaracion `externo`/`local`.** Un conector declara si es externo; por defecto es **local**.
   Es una extension **aditiva** del contrato de `ProveedorContexto` (ADR-0015 se extiende, no se
   modifica): el Core lee un atributo generico, no un `if fuente == "..."`.
2. **Habilitacion por opt-in explicito.** Ningun conector externo se activa por defecto. Solo se activa
   si su nombre esta en el conjunto de **habilitados por el usuario** (configuracion, no codigo del
   Core — regla 12 de ADR-0004). Los conectores **locales** no se ven afectados: siempre activos.
3. **Declaracion estructurada de transparencia.** Todo conector externo debe portar una
   `DeclaracionTransparencia` con un **esquema generico**: `datos_locales`, `datos_que_salen`,
   `destino`, `proposito`. Un conector externo **sin** esa declaracion **no puede habilitarse**. El
   **contenido** por-conector lo fija el ADR propio de cada conector futuro; aqui solo el esquema.
4. **Ninguno es requisito.** El sistema opera por completo sin ningun conector externo (garantia ya
   dada por la degradacion de ADR-0015; reforzada por una prueba de regresion permanente).
5. **Transparencia observable.** Para los conectores externos habilitados, el mecanismo produce un
   **informe** (que queda local / que sale / destino) — encaja con la observabilidad de arranque (D40).
6. **Sin proveedor real.** No se anaden credenciales, llamadas de red ni integracion con fabricantes.
   El mecanismo se demuestra **exclusivamente con un doble** de conector externo.

**Preserva ADR-0015:** el Core no gana una lista blanca de fuentes; los conectores se auto-declaran y
la habilitacion es configuracion del usuario. Anadir un conector sigue siendo anadir un fichero.

## Consecuencias

**Positivas:** cuando se apruebe el primer conector externo (con su ADR), el mecanismo de consentimiento
y transparencia ya estara construido y probado; el usuario decide y ve el recorrido del dato antes de
que nada salga. **Negativas:** hay un mecanismo mantenido antes de tener un consumidor real (mitigado:
es minimo y generico). **Riesgos aceptados:** la transparencia *concreta* no se valida hasta el primer
conector real; el esquema podria necesitar campos adicionales entonces (evolucion aditiva, regla 11).

## Impacto (acta D11 — obligatorio)

| Dimensión | Impacto |
|---|---|
| Seguridad | Positivo: ningun dato sale sin opt-in explicito; superficie externa apagada por defecto. |
| Privacidad | Positivo: consentimiento informado + transparencia estructurada del recorrido del dato (D37). |
| Modularidad | Positivo: generico y reutilizable; extiende ADR-0015 sin tocar el Core ni añadir logica por fuente. |
| Costo | Neutro: sin servicios ni dependencias nuevas. |
| Experiencia de usuario | Positivo: el usuario habilita y ve que sale; nada ocurre a sus espaldas. |
| Mantenimiento futuro | Un mecanismo mas que mantener sin consumidor aun; minimo y con prueba de regresion. |

## Trazabilidad

Capítulos/decisiones: formaliza **D37**; extiende **ADR-0015** (aditivo); consistente con **ADR-0001**
(local-first) y **D24** (sin claves de terceros). Módulos de código (fase de implementacion): un modulo
generico nuevo (`DeclaracionTransparencia` + gate de habilitacion), un campo de opt-in en
`Configuracion`, y su aplicacion en `composicion` (lo estrictamente necesario). `contexto.py` se
extiende de forma aditiva. **Ningun conector real.**
