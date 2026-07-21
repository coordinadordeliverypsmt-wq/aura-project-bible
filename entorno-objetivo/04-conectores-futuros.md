---
documento: "04 — Arquitectura de conectores futuros"
linea: "Preparación del Entorno Objetivo (D35)"
fecha: 2026-07-21
autor: "CTO"
---

# Arquitectura de conectores futuros

**Nada de esto se implementa.** ADR-0015 autoriza que incorporarlos no rompa el núcleo; **no autoriza
incorporarlos**. Cada fuente requerirá su propia decisión.

## 1. El mecanismo, ya construido

Todo conector futuro implementa el mismo contrato de dos elementos:

```python
@runtime_checkable
class ProveedorContexto(Protocol):
    nombre: str
    async def recoger(self, trace_id: str) -> list[Senal]: ...
```

Añadir una fuente es **añadir un fichero en `conectores/`**. El núcleo no tiene lista de fuentes
admitidas, ni condicionales por tipo, ni imports de conectores — verificado con una prueba que define
una cámara inexistente y comprueba que funciona sin que el núcleo la mencione.

Las tres restricciones permanentes aplican **igual** a toda fuente futura: capturar no implica
inferir, la captura es pasiva, y no se generan perfiles persistentes de terceros.

## 2. Un hallazgo que condiciona la mitad de las fuentes previstas

Al analizar las fuentes una por una aparece un problema que no es de integración, sino de principios.

**Los wearables no exponen sus datos localmente.** Garmin, Fitbit, Oura, Polar y Apple Watch publican
sus métricas a través de **APIs en la nube**: el dispositivo sincroniza con el servidor del
fabricante, y el acceso se hace contra ese servidor, con credenciales de terceros.

Eso choca de frente con dos decisiones fundacionales:

| Decisión | Texto | Conflicto |
|---|---|---|
| **ADR-0001** | Local-first estricto | Los datos ya han salido del perímetro antes de que AURA los lea |
| **D24** | Stack local, **sin claves de terceros** | Estas APIs exigen exactamente eso |

**No es un obstáculo técnico —el conector sería sencillo— sino una contradicción con la identidad del
proyecto.** Y conviene verlo con precisión: AURA no filtraría datos al integrarse; los datos **ya
están** en la nube del fabricante por el diseño del dispositivo. Lo que AURA haría es **traerlos de
vuelta**.

Ese matiz no resuelve el conflicto con D24, pero cambia la pregunta: no es *"¿exponemos datos del
usuario?"*, sino *"¿aceptamos depender de un servicio de terceros para funcionar?"*.

**Requerirá una decisión explícita del CEO y probablemente un ADR.** Lo dejo señalado ahora,
antes de que alguien lo descubra a mitad de implementación.

## 3. Las fuentes, una por una

### 3.1 Cámaras de seguridad

| | |
|---|---|
| **Señales** | Presencia, patrones de entrada y salida |
| **Acceso** | **Local** (RTSP/ONVIF) — compatible con ADR-0001 |
| **Dificultad** | Media técnica, **alta en privacidad** |
| **Bloqueante** | La restricción de terceros |

Una cámara capta a quien pase por delante. La restricción de no generar perfiles de terceros, hoy
resuelta con análisis de texto, se vuelve **cualitativamente más difícil**: exige decidir qué se
extrae del vídeo **antes** de almacenar nada, porque un fotograma guardado ya es un dato sobre las
personas que aparecen en él.

Recomendación anticipada: que el conector emita **sólo eventos abstractos** ("presencia detectada"),
nunca imágenes ni identidades. Y que el procesamiento ocurra en el dispositivo o en el momento, sin
persistir el material original.

### 3.2 Home Assistant (ampliado)

| | |
|---|---|
| **Señales** | Escenas, sensores, dispositivos, rutinas |
| **Acceso** | **Local** (API REST/WebSocket) — plenamente compatible |
| **Dificultad** | **Baja.** El adaptador base ya existe |
| **Bloqueante** | Sólo la existencia de la instalación real (D34) |

**Es la fuente mejor posicionada** y la de mayor relación valor/coste: acceso local, sin
credenciales externas, y el conector puede leer del audit log igual que el actual.

### 3.3 Wearables (Garmin, Apple Watch, Fitbit, Oura, Polar…)

| | |
|---|---|
| **Señales** | Actividad, sueño, rutinas, esfuerzo |
| **Acceso** | **Nube del fabricante** — ver §2 |
| **Dificultad** | Baja técnica, **alta en principios** |
| **Bloqueante** | **Conflicto con ADR-0001 y D24** |

Salvedad: algunos dispositivos permiten exportación local o sincronización sin nube (Gadgetbridge y
similares). Si se decidiera integrar wearables, **priorizar los que admitan lectura local** sería la
vía coherente con el proyecto — y acotaría el conflicto en lugar de aceptarlo.

### 3.4 Sensores biométricos

| | |
|---|---|
| **Señales** | Constantes, estado fisiológico |
| **Acceso** | Variable |
| **Dificultad** | **Alta en todos los ejes** |
| **Bloqueante** | Categoría especial de datos |

**Datos de salud.** En cualquier escenario distinto del uso estrictamente personal (E3/E4), son
categoría especial bajo RGPD, con obligaciones que hoy el proyecto no tiene resueltas.

Recomendación: **no abordarlos hasta que E1–E4 esté decidido**. Es la fuente cuya incorporación
equivocada resulta más cara de revertir.

### 3.5 Sensores ambientales

| | |
|---|---|
| **Señales** | Temperatura, luz, calidad del aire, ruido |
| **Acceso** | **Local**, normalmente vía Home Assistant |
| **Dificultad** | **Baja** |
| **Bloqueante** | Ninguno relevante |

**La fuente más sencilla y menos problemática.** No versa sobre personas; describe un espacio. Buena
candidata para ser la primera fuente nueva tras Home Assistant.

### 3.6 Vehículos

| | |
|---|---|
| **Señales** | Desplazamientos, rutinas de trayecto |
| **Acceso** | Casi siempre **nube del fabricante** |
| **Dificultad** | Alta |
| **Bloqueante** | Mismo conflicto que wearables, más geolocalización |

La ubicación es de las señales más sensibles: revela domicilio, trabajo, hábitos y presencia o
ausencia en casa. Merece tratamiento aparte.

### 3.7 IoT futuro

Sin analizar por definición. El contrato de ADR-0015 lo admite; **cada caso requerirá su decisión.**

## 4. Cuadro de prioridad sugerido

Si algún día se amplían las fuentes, este es el orden que propongo — de menor a mayor fricción con
los principios del proyecto:

| Orden | Fuente | Motivo |
|---|---|---|
| 1 | **Home Assistant ampliado** | Local, ya iniciado, alto valor |
| 2 | **Sensores ambientales** | Local, sencillo, no versa sobre personas |
| 3 | **Cámaras** | Local, pero exige resolver la privacidad de terceros primero |
| 4 | **Wearables con lectura local** | Sólo los que no exijan nube |
| 5 | Wearables por nube · Vehículos | **Requieren decisión sobre ADR-0001/D24** |
| 6 | Biométricos | **Sólo con el escenario de despliegue decidido** |

## 5. La advertencia que cierra este documento

La arquitectura de proveedores hace que **incorporar una fuente sea técnicamente barato**. Ese es su
mérito y también su riesgo: cuando algo cuesta poco esfuerzo, tiende a hacerse sin decidirlo.

Las fuentes de §3.1, §3.3, §3.4 y §3.6 **capturan sin que el usuario diga ni haga nada**. Son de
naturaleza distinta a conversación, ordenador y hogar, que registran actos deliberados. Una cámara y
un sensor biométrico observan por el mero hecho de existir.

> **La facilidad de integración no debe convertirse en criterio de integración.**

Cada fuente merece su gate, con la pregunta de siempre por delante: *¿qué gana el usuario, y qué deja
de controlar a cambio?*
