---
adr: 15
titulo: "Toda captura de señales se implementa mediante proveedores de contexto"
estado: accepted
fecha: 2026-07-21
decide: "CEO (gate de M3.0)"
propone: "CEO"
supersede: null
relacionado: "ADR-0001 (local-first), ADR-0014 (Core única fuente de verdad), 4.4 (aprendizaje), 2.2 §4.4 (exclusiones hasta R2)"
---

# ADR-0015 — Proveedores de contexto

## Decisión

> *"Toda captura de señales deberá implementarse mediante un sistema de conectores o proveedores de
> contexto. M3 solo instrumentará las fuentes actuales (conversación, PC y Home Assistant), pero la
> arquitectura deberá permitir incorporar posteriormente cámaras, wearables, sensores biométricos y
> otros dispositivos sin modificar el núcleo del sistema."*
> — CEO, 2026-07-21

## Contexto

M3 necesita capturar señales de aprendizaje (4.4 §1) de varias fuentes. La vía directa —que el
orquestador leyera cada fuente— habría funcionado para las tres del MVP y habría exigido **modificar
el núcleo cada vez que apareciera un sensor nuevo**.

El horizonte del proyecto es de 10 años (D20). Las fuentes de contexto de un PIOS crecen con el
tiempo: hoy conversación y ordenador; mañana presencia, biometría, vehículo, sensores del hogar. Un
núcleo que enumere fuentes envejece mal, y cada ampliación tocaría el componente con mayor
concentración de garantías críticas.

## Consecuencias de diseño

**El núcleo no conoce ninguna fuente concreta.** En `core/contexto.py` no hay —ni debe haber nunca—
una lista de fuentes admitidas, un `if fuente == "camara"` ni un import de un conector. El núcleo
sabe que existen proveedores y que producen señales; **qué proveedores existan es configuración, no
código del Core**.

Contrato mínimo:

```python
@runtime_checkable
class ProveedorContexto(Protocol):
    nombre: str
    async def recoger(self, trace_id: str) -> list[Senal]: ...
```

Un proveedor que además observe conversación puede exponer `observar(texto)`; los que no —una cámara,
un wearable— simplemente no lo implementan, y el núcleo no necesita saber de qué tipo es cada fuente.

### Un proveedor caído degrada la captura, no la derriba

Diferencia deliberada respecto al `RegistroAdaptadores` de M2.5. Allí, un adaptador que falla detiene
la acción: el usuario espera un efecto y merece saber que no ocurrió. Aquí, **un sensor desconectado
no puede dejar ciego al sistema entero**: se registra la fuente en error y las demás siguen
aportando. La lección viene de M2, donde un `OSError` propagado desde un adaptador derribaba el turno
completo.

### Una fuente, un dueño

Dos proveedores con el mismo nombre se rechazan al registrar. La procedencia de una señal (4.4 §2)
sería ambigua, y sin procedencia fiable el modelo del usuario no es auditable ni corregible.

## Alcance en M3

Se instrumentan **tres** fuentes: `conversacion`, `computador` y `home_assistant`. Las dos últimas
derivan sus señales del **audit log que M2 ya escribía** — no se instrumenta nada nuevo del sistema
de archivos ni del hogar.

Cámaras, wearables y sensores biométricos **quedan fuera de M3** y no requerirán tocar el núcleo
cuando se incorporen. Coherente con las exclusiones binarias de 2.2 §4.4 hasta R2.

## Relación con ADR-0014

ADR-0014 establece que el Core es la única autoridad sobre los hechos. Este ADR lo complementa por el
lado de la entrada: **un proveedor aporta observaciones, no verdades**. Una señal capturada es un
hecho sobre *lo que se observó*, nunca una conclusión sobre el usuario. Inferir corresponde a M3.2 y
tendrá su propio ADR.

## Impacto (acta D11 — obligatorio)

| Dimensión | Impacto |
|---|---|
| **Seguridad** | Positivo: los proveedores son pasivos por contrato — observan y reportan, nunca actúan. La superficie de acción del sistema no crece |
| **Privacidad** | **Requiere vigilancia.** Multiplicar fuentes multiplica lo que AURA puede saber. Mitigado por: solo las seis señales de 4.4 §1, nada de terceros, y datos del propio usuario (ADR-0001) |
| **Modularidad** | Positivo alto: añadir una fuente es añadir un fichero en `conectores/`, sin tocar `core/` |
| **Costo** | Nulo. Sin dependencias nuevas |
| **Rendimiento** | Despreciable frente a la latencia dominante. La captura ocurre al cierre del turno, fuera del camino de respuesta |
| **Mantenibilidad** | Positivo: el núcleo deja de crecer con cada integración |
| **Reversibilidad** | Alta: la captura es opcional; sin registro de contexto el sistema se comporta como en M2 |

## Riesgos aceptados

- **Un proveedor mal escrito puede capturar ruido.** Mitigado porque la captura es pasiva: el peor
  resultado es un dato mal etiquetado, nunca una acción equivocada. El coste se paga en M3.2, al
  inferir sobre datos malos, y por eso los clasificadores son deliberadamente conservadores.
- **La extensibilidad podría tentar a añadir fuentes invasivas.** El ADR no autoriza fuentes nuevas:
  autoriza que incorporarlas no rompa el núcleo. Cada fuente futura requiere su propia decisión.
