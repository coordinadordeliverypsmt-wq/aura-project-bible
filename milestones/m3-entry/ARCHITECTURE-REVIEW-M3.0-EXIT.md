---
documento: "Architecture Review — M3.0 Exit"
milestone: "M3 — Presencia"
fase: "M3.0 — Infraestructura de captura de señales"
fecha: 2026-07-21
autor: "CTO"
estado: "Presentado al CEO para gate. No se ha iniciado M3.1."
---

# Architecture Review — M3.0 Exit

## 1. Qué se construyó

Infraestructura de captura, almacenamiento, clasificación y validación de señales de aprendizaje,
**funcionando con independencia del rendimiento del modelo**, conforme a tu decisión.

| Componente | Función |
|---|---|
| `core/senales.py` | Las seis señales de 4.4 §1, con origen epistémico y rechazo de terceros |
| `core/contexto.py` | Registro de proveedores (ADR-0015). El núcleo no conoce ninguna fuente concreta |
| `core/almacen_senales.py` | Persistencia como memoria **semántica** y **procedimental**, con procedencia |
| `conectores/conversacion.py` | Fuente 1 — preferencias, correcciones y feedback declarados |
| `conectores/computador.py` | Fuente 2 — patrones de uso, derivados del audit log |
| `conectores/hogar.py` | Fuente 3 — patrones de uso del hogar, del mismo audit log |

**Quality Gate: PASS — 252 pruebas** (18 nuevas), 3 omitidas, 8 contratos. Sin regresión en M1 ni M2.

### Deuda saldada

Hasta M2 el sistema escribía **un solo tipo** de memoria (`episodica`), con la taxonomía de 4.1 §1
implementada a un tercio. **Las memorias semántica y procedimental ya existen.**

## 2. Las tres restricciones, y cómo se hacen cumplir

No basta con declararlas: cada una tiene una prueba que falla si se incumple.

### Capturar no implica inferir

`Senal.inferida` es **siempre `False`** en M3.0, y el campo `origen` (`declarada` / `observada`) se
persiste desde el primer registro. No porque haga falta hoy, sino porque **cuando M3.2 empiece a
inferir, el historial ya distinguirá ambas cosas sin necesidad de migrarlo.**

### La instrumentación es completamente pasiva

Garantizado por construcción, no por disciplina: la captura ocurre **al cierre del turno, después de
que la respuesta ya esté decidida**. Es estructuralmente imposible que influya en lo que AURA
contesta.

La prueba `test_captura_no_altera_la_respuesta` ejecuta la misma petición con y sin captura y exige
respuestas idénticas. Además, un fallo en la captura **no le cuesta el turno al usuario**: se registra
y se sigue. La captura es infraestructura para el futuro; la conversación es el producto de hoy.

### No se construyen perfiles persistentes de terceros

Una señal marcada como de tercero **no se crea**, y se descarta en silencio: registrar "hubo una señal
sobre un tercero" ya sería un rastro sobre esa persona.

Caso resuelto de forma conservadora: *"No me gusta que mi hermana use mi computador"* es una
preferencia **del usuario**, pero persistirla dejaría rastro sobre otra persona. **No se captura.**
Ante la duda, no se captura.

## 3. La decisión de arquitectura: ADR-0015

Registrada como ADR. La propiedad que pediste se verifica con una prueba que **define una cámara que
no existe en el sistema** y comprueba que funciona sin que ningún fichero del núcleo la mencione.

En `core/contexto.py` no hay lista de fuentes admitidas, ni `if fuente == "camara"`, ni imports de
conectores. **Qué proveedores existan es configuración, no código del Core.**

Una diferencia deliberada respecto al registro de adaptadores de M2.5: allí un adaptador que falla
detiene la acción, porque el usuario espera un efecto; aquí **un sensor desconectado no puede dejar
ciego al sistema entero**. Degrada y sigue.

## 4. Verificación — y dos fallos que encontré en mi propio trabajo

Todo se construyó con TDD estricto: prueba primero, verla fallar, código mínimo.

**Fallo 1 — una prueba que habría sido inútil.** Al escribir las pruebas de los conectores del
sistema inventé los nombres de campo del audit log (`tag`, `modulo`, `mensaje`). El formato real es
`level`, `module`, `msg`. Los conectores habrían pasado las pruebas y **fallado con datos reales**.
Detectado al contrastar contra `observability.py` antes de implementar.

**Fallo 2 — un falso PASS en la prueba de privacidad.** La prueba usaba *"A Ana le gusta el café"*.
Pasaba, pero **no porque la protección funcionara**: el clasificador nunca llegaba a considerar esa
frase una señal. Descubierto por prueba de mutación. Sustituida por un caso que sí ejercita la
protección; verificado que ahora la mutación la hace fallar.

Ambos fallos son el mismo error que este proyecto ya ha pagado tres veces —una prueba que verifica el
doble en vez del sistema— y ambos se detectaron **antes** de entregar.

### Validación por mutación

| Mutación | Resultado |
|---|---|
| El clasificador marca toda frase como preferencia | **Detectada** — cae el caso de control |
| Se ignora la comprobación de terceros | **Detectada** — cae la prueba de privacidad |

## 5. Lo que M3.0 NO hace

- **No infiere** preferencias ni construye el modelo del usuario (M3.2).
- **No anticipa** ni sugiere nada (M3.3).
- **No genera historial por sí mismo.** Esto merece énfasis: la infraestructura está lista, pero
  **el historial solo crecerá cuando alguien use AURA a diario.** C sin D produce un esquema vacío,
  como advertía el plan.

## 6. Estado de los datos

Conforme a tu decisión, los datos que se acumulen desde ahora tienen **carácter exploratorio** y no
se usarán para evaluar CM1 ni CM4. La validación estadística empezará cuando exista hardware capaz
de sostener uso cotidiano.

Esto no los hace inútiles: permitirán verificar que la captura clasifica bien **antes** de que las
cifras cuenten, que es exactamente cuando conviene descubrir que un clasificador está mal calibrado.

## 7. Product Readiness

**Sin cambios: 41%.** M3.0 no entrega ninguna capacidad al usuario, por diseño. Mover la cifra aquí
sería falsear la métrica: entrega la posibilidad de que las siguientes capacidades se puedan
construir y medir, y eso no es producto todavía.

## 8. Pendiente antes de M3.1

| Asunto | Estado |
|---|---|
| P1 — hardware objetivo | **Pendiente de decisión del CEO** |
| P2 — modelo base | Pendiente, depende de P1 |
| P5 — ADR de preferencias inferidas | **No redactado.** Corresponde a M3.2; conviene antes de inferir |
| Bloque D — uso real | Bloqueado por P1 |

## 9. Decisión requerida del CEO

1. ¿Se aprueba el cierre de M3.0?
2. ¿Quieres que prepare el **análisis comparativo de hardware objetivo y modelo base** (P1/P2) como
   insumo para tu decisión? Es documentación, no implementación, y es hoy el trabajo con mayor
   impacto disponible.
3. ¿Se conecta la captura a las demos existentes para empezar a acumular historial exploratorio, o
   se espera a que haya uso real?
