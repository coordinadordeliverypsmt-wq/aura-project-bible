---
documento: "ALERTA DE ARQUITECTURA 005"
estado: "RESUELTA — Alternativa A (2026-07-21), verificada con stack real"
fecha: 2026-07-20
emisor: "CTO, conforme al acta D15/D16"
trabajo-suspendido: "Ninguno. Cierre de M2 desbloqueado."
---

# ALERTA-005 — Las manos digitales de M2 no están conectadas al cuerpo

Estructura obligatoria de 10 secciones (acta D16).

## 1. Problema detectado

Al preparar la **demo de capacidad M2 con stack real** (DoD 9) verifiqué qué código de producción
instancia los tres componentes construidos en M2.2, M2.3 y M2.4:

```
$ grep -rn "AdaptadorComputador|MotorAutomatizacion|CentroNotificaciones" --include=*.py .
tests/unit/test_adaptador_computador.py:11:  ...
tests/unit/test_automatizacion.py:12:        ...
tests/unit/test_notificaciones.py:11:        ...
aura_skeleton/adapters/computador.py:71:     class AdaptadorComputador:
aura_skeleton/core/automatizacion.py:46:     class MotorAutomatizacion:
aura_skeleton/core/notificaciones.py:67:     class CentroNotificaciones:
```

**Los tres componentes solo son instanciados por sus propias pruebas.** Ningún camino de producción
los alcanza. El orquestador conoce un único adaptador:

```python
# orchestrator.py:78
self.perm, self.voice, self.ha = permissions, voice, ha
# orchestrator.py:125
if ok and action in self.ha.capabilities:
    await self.ha.execute(action, args, tid, cmd_ev.event_id)
```

Consecuencia operativa: **si el usuario le pide a AURA "busca mis facturas" o "borra este archivo",
la petición nunca llega al adaptador del computador.** La acción se autoriza en Permisos y muere ahí,
porque `action not in self.ha.capabilities`. El motor de automatización no está suscrito a ningún
bus. El centro de notificaciones no recibe nada de ninguna fuente real.

**Causa raíz — un enganche declarado y no ejecutado.** El propio Architecture Review M2 Entry §4 lo
listaba como trabajo de M2:

| Componente | Cambio | Naturaleza |
|---|---|---|
| `orchestrator.py` | **Punto de enganche del motor de automatización** | Ampliación |

Ninguna de las cinco fases lo implementó, y **ninguna prueba lo detectó** porque todas construyen los
componentes directamente. Cada fase verificó su pieza en aislamiento; nadie verificó que las piezas
estuvieran unidas.

### Verificación empírica (no solo lectura de código)

Antes de emitir esta alerta reproduje el defecto de forma determinista: sustituí el LLM por un doble
que **siempre** emite `listar_directorio` (acción verde), con un espía sobre el adaptador real, de
modo que el resultado no pueda depender del modelo sino solo del cableado.

```
Usuario pide      : "Lista los archivos de esa carpeta"
LLM (doble) emite : listar_directorio (accion VERDE del catalogo)
AURA responde     : "Listo el directorio. [accion listar_directorio autorizada: auto (lista verde)]"
Llamadas reales al AdaptadorComputador: []
```

**Cero llamadas al adaptador.** Confirmado.

### Hallazgo secundario, más grave que el principal

Léase con atención la respuesta de AURA: **«Listo el directorio.»** No listó nada. La rama que lo
produce es esta:

```python
elif ok:
    say = say + f" [accion {action} autorizada: {reason}]"
```

Cuando Permisos autoriza una acción que ningún adaptador puede atender, el orquestador **devuelve la
frase del LLM como si la acción se hubiera realizado**. El sistema afirma un hecho falso sobre sí
mismo, y lo afirma con el sello de "autorizada".

Esto no es el LLM alucinando: **es el Core reportando mal.** Y por eso es más grave que el hueco de
cableado. ADR-0014 establece que la verdad del sistema proviene del Core; aquí el Core es
precisamente la fuente del error. Un usuario que oye "listo el directorio" y no ve nada puede
atribuirlo a un fallo de pantalla; uno que oiga "borrado" sobre un archivo que sigue ahí —o al revés—
tomará decisiones sobre un estado que no existe.

Corolario para el diseño: **una acción autorizada que nadie puede ejecutar debe ser un error
explícito, nunca un éxito silencioso.**

**Este es el mismo patrón que ALERTA-004.** Allí el grounding estaba declarado en la Bible y en la
cabecera del arnés de evals, y ausente del código. Aquí el enganche está declarado en el Architecture
Review y ausente del código. En ambos casos las pruebas pasaban porque verificaban la pieza, no el
sistema. **El patrón se repitió a un día de distancia: no fue mala suerte, es un hueco en la forma de
probar.**

## 2. Riesgos si se ignora

- **M2 se declararía cerrado sin entregar su capacidad.** El objetivo de M2 son las *manos digitales*.
  Existen, están probadas y son inalcanzables. Cerrar así convierte el milestone en un ejercicio de
  código muerto.
- **El Product Readiness sería falso.** La proyección de cierre de M2 (~45%) sube "hace cosas útiles"
  de 1% a ~12%. Con los adaptadores desconectados esa dimensión **sigue en 1%**: el usuario no puede
  pedir ni una sola de las nueve operaciones. Reportar 45% sería reportar una cifra que el sistema no
  sostiene.
- **El hueco de prueba sobrevive al milestone.** Si no se corrige el *método*, M3 repetirá el patrón:
  componentes correctos, sistema desconectado, pruebas verdes.
- **Riesgo diferido, no presente.** No hay riesgo de seguridad activo: código inalcanzable no puede
  causar daño. El riesgo aparece **al conectarlo**, y es el que se analiza en §7.

## 3. Tres alternativas posibles

**A. Conectar el orquestador a los componentes M2, con dry-run también en la vía conversacional.**
El orquestador recibe un registro de adaptadores y enruta por capacidad. Toda acción que altere estado
—entre por conversación o por regla— se previsualiza antes de pedir confirmación. Es el alcance ya
declarado en M2 Entry §4, no alcance nuevo.

**B. Conectar solo lectura (lista verde) ahora; diferir las acciones que alteran estado a M3.**
Reduce la superficie de riesgo a cero efectos destructivos. Pero entrega media capacidad y deja
`escribir/borrar/mover` en el mismo estado de código muerto, con la deuda intacta.

**C. Declarar M2 cerrado como "capacidades construidas, integración en M3".**
Honesto si se documenta, pero rompe el criterio de terminación 9 (demo de capacidad) y traslada a M3
un trabajo que ya estaba presupuestado en M2.

## 4. Recomendación del CTO

**Alternativa A**, con una restricción de diseño que considero no negociable:

> **La confirmación informada no puede depender de por dónde entró la petición.**

El motor de automatización ya exige dry-run obligatorio antes de confirmar (M2.3). Si la vía
conversacional ejecutara sin previsualización, tendríamos la asimetría exactamente al revés de lo
razonable: **AURA sería más cuidadosa actuando sola que actuando cuando se lo pide un humano.** El
usuario que dice "borra el borrador viejo" merece ver *qué archivo concreto y de cuántos bytes* antes
de decir que sí — sobre todo porque la ruta la propone un LLM, no él.

Añado una segunda medida, dirigida a la causa y no al síntoma: **una prueba de integración que falle
si una capacidad declarada por un adaptador registrado no es alcanzable desde el orquestador.** Sin
eso, corregimos este caso y dejamos vivo el hueco que lo produjo.

## 5. Impacto en costo

**Nulo.** No añade dependencias, servicios ni modelos. Todo el stack sigue siendo local (D24).

## 6. Impacto en rendimiento

**Despreciable frente a la latencia dominante.** El dry-run de una operación de archivo son unas
pocas llamadas `lstat`/`open` — microsegundos — frente a los ~160.000 ms por turno que impone el
hardware actual. No altera HC-1 ni en un sentido ni en otro.

## 7. Impacto en seguridad y privacidad

Este es el punto que merece la atención del CEO, porque **conectar sí aumenta la superficie de
riesgo**: hasta hoy ningún LLM podía originar una operación sobre el sistema de archivos, y con el
enganche podrá proponerla.

Lo que contiene ese riesgo, todo ya construido y probado:

| Control | Origen | Qué impide |
|---|---|---|
| Catálogo finito y tipado | M2.1 | El LLM no puede inventar operaciones; lo no declarado se deniega por defecto |
| Validación de ámbito | M2.1 | Una ruta alucinada fuera de las raíces permitidas se rechaza |
| Lista roja + HITL | ADR-0003 | Nada que altere estado se ejecuta sin un humano diciendo que sí |
| Dry-run + previsualización | M2.3 + esta alerta | La confirmación es informada, no a ciegas |
| Protección TOCTOU | M2.2 | La ruta confirmada es la ruta afectada |
| Kill switch | 5.3 §5 | Corta ambas vías |
| ADR-0014 | M2.0 | El LLM **propone**; el Core **decide**. La clasificación no se le consulta |

**El LLM nunca gana autoridad con este cambio.** Gana la capacidad de sugerir una acción que el Core
clasifica, valida, previsualiza y somete a confirmación. Esa es precisamente la arquitectura para la
que se construyeron M2.1–M2.3; mantenerla desconectada no la hace más segura, solo la hace inútil.

Riesgo residual honesto: una acción **verde** con ruta alucinada podría leer o listar algo que el
usuario no pidió, dentro de sus propias raíces. Es información del propio usuario, sin alteración de
estado ni efecto externo — encaja en el criterio de reversibilidad ya ratificado.

## 8. Impacto en mantenibilidad

**Positivo.** Un registro explícito de adaptadores sustituye al atributo `self.ha` cableado a mano, y
añadir un adaptador futuro (NAS, Android en R2) deja de requerir tocar el orquestador. La prueba de
alcanzabilidad convierte "está conectado" en una propiedad verificada en vez de una suposición.

## 9. Impacto en plazos

**Contenido: horas, no días.** El código existe y está probado; falta el cableado, sus pruebas y la
demo. No compromete el roadmap de M3.

Lo que sí se retrasa es el **cierre de M2**, que no puede firmarse hasta que la capacidad sea
alcanzable. Prefiero un cierre tardío y cierto a uno puntual y falso.

## 10. Decisión requerida del CEO

1. ¿Se aprueba la **Alternativa A** —conectar el orquestador a los componentes M2— como parte del
   alcance ya autorizado de M2 (declarado en M2 Entry §4), o se prefiere B o C?
2. ¿Se ratifica que **el dry-run con previsualización aplique también a la vía conversacional**, y no
   solo a las automatizaciones?
3. ¿Se aprueba añadir la **prueba de alcanzabilidad de capacidades** como criterio permanente, de modo
   que un componente construido y no conectado haga fallar el Quality Gate en cualquier milestone
   futuro?
4. Sobre el hallazgo secundario: ¿se ratifica que **una acción autorizada sin adaptador capaz debe
   producir un error explícito al usuario**, en lugar de la frase de éxito del LLM? Lo considero una
   corrección de defecto y no un cambio de alcance, pero afecta a lo que AURA le dice al usuario sobre
   sus propios actos y prefiero no decidirlo solo.

---

## 11. RESOLUCIÓN — Alternativa A (2026-07-21)

**Gate del CEO:** aprobada la Alternativa A con cinco condiciones. Todas cumplidas.

| Condición del CEO | Cómo se cumplió |
|---|---|
| Sin rutas de ejecución alternativas ni bypass | El orquestador **no llama a ningún adaptador**: delega en el motor, único ejecutor del sistema, compartido por conversación, reglas y notificaciones |
| Mismo flujo también por vía conversacional | Camino único: dry-run → Permisos/HITL → adaptador → ejecución → auditoría |
| Error explícito si no hay adaptador capaz | La frase del modelo solo sobrevive con resultado real del adaptador; en otro caso, error explícito |
| Prueba permanente de alcanzabilidad en el Quality Gate | `tests/integration/test_alcanzabilidad_capacidades.py`, validada por mutación |
| Demo con stack real y Product Readiness solo con evidencia | 8/9 capacidades; Product Readiness 41% (objetivo era 45%) |

### Divergencia respecto al orden literal indicado por el CEO

El CEO especificó: *catálogo → validación de ámbito → permisos/HITL → dry-run → ejecución →
auditoría*. La implementación sitúa el **dry-run antes de Permisos**, no después.

Motivo: el dry-run es lo que hace **informada** la confirmación. Pedirla antes de previsualizar
sería confirmar a ciegas, contradiciendo la condición previa del propio CEO en M2.3 —*"ninguna acción
de lista roja podrá ejecutarse sin previsualización y confirmación explícita"*—. El dry-run no altera
nada, de modo que ejecutarlo antes no añade riesgo. El resto del orden se respeta.

### Corrección detectada durante la implementación

Se probó primero a resolver el adaptador **antes** de Permisos (fallar rápido). Las pruebas e2e de
lista roja detectaron una regresión real: **una acción roja sin adaptador dejaba de pasar por HITL y
desaparecía del registro forense**. Un intento de `transferencia` debe quedar auditado aunque AURA no
tenga hoy forma de transferir nada; que la capacidad no exista es una circunstancia de la
instalación, no una razón para no aplicar el control. Orden final: dry-run → **Permisos** →
adaptador.

### Defecto adicional hallado por la demo

Una regla que dispara dos veces sobre el mismo archivo propagaba `FileNotFoundError` a través del
motor y **derribaba el turno completo**. Corregido: degrada a `detenida` o `error` sin derribar el
turno, con dos pruebas de regresión.

### Estado final

Quality Gate **PASS** — 234 pruebas, 3 omitidas, 8 contratos. Demo con dobles 9/9; con stack real
8/9. Cero errores no recuperados. Evidencia en `milestones/m2-exit/`.
