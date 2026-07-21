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

## 2. Servicios de terceros: local-first no es local-only

> **Corrección (D37, 2026-07-21).** La primera versión de esta sección afirmaba que los wearables
> *"chocan con ADR-0001 (local-first)"*. **Esa formulación era incorrecta** y el CEO la corrigió.
> Convertía un principio de independencia en una prohibición de integración, que es una limitación
> que el principio nunca impuso. Lo que sigue es la lectura vigente.

**El hecho técnico:** Garmin, Fitbit, Oura, Polar y Apple Watch no exponen todas sus métricas
directamente desde el dispositivo. El acceso oficial es a través de **APIs en la nube del
fabricante**.

**Lo que eso NO significa:** que integrarlos rompa local-first.

### Formulación vigente del principio (D37)

1. **AURA funciona completamente sin Internet.** Ninguna capacidad básica depende de un servicio
   externo.
2. **Opcionalmente**, el usuario puede conectar servicios externos para **enriquecer** el contexto.
3. **Si un servicio cae o el usuario revoca el acceso, AURA sigue operando**; simplemente pierde esa
   fuente.

**Lo prohibido es la dependencia funcional, no la existencia de fuentes opcionales.**

La distinción es además la correcta desde el punto de vista de los datos: los datos de un wearable
**ya están** en la nube del fabricante por el diseño del dispositivo, con o sin AURA. Integrarlos no
los expone; los **trae de vuelta** al perímetro del usuario.

### Condiciones ya fijadas para cualquier conector de este tipo (D37)

| Condición | Consecuencia de diseño |
|---|---|
| **Habilitación explícita del usuario** | Ningún conector externo se activa por defecto |
| **Transparencia sobre el recorrido del dato** | Debe quedar claro qué permanece local y qué pasa por el fabricante |
| **Ningún proveedor externo es requisito** | La degradación por pérdida de una fuente debe ser limpia y no afectar a ninguna garantía |

La tercera condición tiene una implicación concreta para el diseño del conector: **la caída de una
fuente externa ya está contemplada** por el mecanismo de ADR-0015 —un proveedor que falla degrada la
captura, no la derriba—, de modo que la arquitectura vigente ya soporta esta exigencia sin cambios.

**Estado: decisión pendiente de arquitectura.** Requerirá ADR propio antes de construir ningún
conector de este tipo.

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
| **Dificultad** | Baja técnica |
| **Bloqueante** | **Decisión pendiente de arquitectura (D37)**, no conflicto de principios |

Salvedad útil: algunos dispositivos permiten exportación local o sincronización sin nube
(Gadgetbridge y similares). Priorizar los que admitan **lectura local** reduce la superficie de
dependencia externa y simplifica la condición de transparencia de D37 — no porque la vía por nube
esté vedada, sino porque menos intermediarios es siempre más fácil de explicar al usuario.

### 3.4 Sensores biométricos

| | |
|---|---|
| **Señales** | Constantes, estado fisiológico |
| **Acceso** | Variable |
| **Dificultad** | **Alta en todos los ejes** |
| **Bloqueante** | Categoría especial de datos |

**Datos de salud**, categoría especial bajo RGPD. Con **D36** el escenario ya está decidido —E1
personal, E2 hogar; E3/E4 fuera de alcance—, lo que **reduce sustancialmente la exposición
regulatoria**: en uso personal y doméstico el usuario trata sus propios datos.

No la elimina del todo: en E2 conviven varias personas en un hogar, y P-ARQ-5 y ALERTA-002 dejan de
ser teóricos. Sigue siendo la fuente cuya incorporación equivocada resulta más cara de revertir, y la
que menos prisa tiene.

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
| **Bloqueante** | Mismas condiciones que wearables (D37), más la sensibilidad de la geolocalización |

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
| 5 | Wearables por nube · Vehículos | **Requieren el ADR pendiente de D37** (opt-in, transparencia, nunca requisito) |
| 6 | Biométricos | Los de mayor sensibilidad; sin urgencia y con el diseño multiusuario de E2 resuelto antes |

## 5. La advertencia que cierra este documento

La arquitectura de proveedores hace que **incorporar una fuente sea técnicamente barato**. Ese es su
mérito y también su riesgo: cuando algo cuesta poco esfuerzo, tiende a hacerse sin decidirlo.

Las fuentes de §3.1, §3.3, §3.4 y §3.6 **capturan sin que el usuario diga ni haga nada**. Son de
naturaleza distinta a conversación, ordenador y hogar, que registran actos deliberados. Una cámara y
un sensor biométrico observan por el mero hecho de existir.

> **La facilidad de integración no debe convertirse en criterio de integración.**

Cada fuente merece su gate, con la pregunta de siempre por delante: *¿qué gana el usuario, y qué deja
de controlar a cambio?*
