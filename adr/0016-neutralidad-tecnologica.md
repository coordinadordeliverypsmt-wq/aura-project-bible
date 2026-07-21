---
adr: 16
titulo: "Neutralidad tecnológica: el Core es independiente del modelo y del hardware"
estado: accepted
fecha: 2026-07-21
decide: "CEO"
propone: "CEO"
supersede: null
relacionado: "ADR-0001 (local-first), ADR-0010 (Ollama), ADR-0014 (Core única fuente de verdad), ADR-0015 (proveedores de contexto), D20 (horizonte 10 años), D24 (stack local)"
---

# ADR-0016 — Neutralidad tecnológica

## Decisión

Cuatro principios permanentes de arquitectura:

1. **Core independiente del modelo.**
2. **Core independiente del hardware.**
3. **Modelos, runtimes y aceleradores son reemplazables mediante adaptadores.**
4. **Los proveedores de contexto** (cámaras, wearables, Home Assistant, sensores…) **permanecen
   desacoplados** mediante el mecanismo de ADR-0015.

## Contexto

El análisis de plataforma para R1 comparó cuatro alternativas de hardware y recomendó una. El CEO
aceptó las conclusiones técnicas —el requisito real es la **latencia percibida** (primer token
≤ 500 ms y generación por encima del ritmo del habla) y el Core ya está desacoplado del runtime—
pero **no oficializó ninguna plataforma objetivo**:

> *"No oficializo Apple Silicon como plataforma objetivo del proyecto. Lo considero la plataforma de
> referencia para las pruebas de rendimiento, pero la arquitectura de AURA debe mantenerse
> independiente del hardware específico. La decisión de plataforma definitiva se tomará cuando
> definamos el escenario de despliegue."* — CEO, 2026-07-21

### Por qué diferir la decisión es lo correcto

Los cuatro escenarios de despliegue posibles —uso personal, instalación doméstica, distribución a
terceros, producto comercial— imponen requisitos **incompatibles entre sí**: coste unitario,
reparabilidad, soporte, homogeneidad del parque, dependencia de un fabricante.

Elegir hardware antes de saber cuál aplica sería fijar una restricción a **10 años** (D20) sobre una
incógnita. Y el coste de equivocarse no sería sustituir una máquina: sería descubrir que la
arquitectura se optimizó para una plataforma que el escenario real no admite.

**La neutralidad no es indecisión: es lo que mantiene abierta la decisión hasta que exista
información para tomarla.**

## Consecuencias

### Lo que ya se cumple, verificado

| Principio | Evidencia |
|---|---|
| Core ↔ modelo | El acoplamiento a un modelo o runtime concreto vive en **un solo fichero** (`modules/providers_real.py`). `core/`, `adapters/` y `conectores/` no mencionan ninguno |
| Modelos reemplazables | Contrato `ModelProvider` de dos métodos; `ModelRouter` con *fallback* |
| Contexto desacoplado | ADR-0015, verificado con una prueba que define una fuente inexistente |

### Lo que este ADR añade

**Core independiente del hardware** es un principio nuevo, y conviene ser preciso sobre qué prohíbe:

- **No** prohíbe usar aceleración cuando exista. Prohíbe que el Core **dependa** de ella.
- **Ninguna garantía del sistema** —permisos, validación, auditoría, captura de señales, kill
  switch— puede requerir una CPU, GPU, NPU o cantidad de memoria concreta. Todas son deterministas y
  se ejecutan igual en cualquier máquina.
- Lo que sí varía con el hardware es **la latencia y la calidad de las respuestas**: utilidad, no
  corrección. Es la misma frontera que fija ADR-0014 entre lo que el modelo aporta y lo que el Core
  garantiza.

### Regla derivada, permanente

> **Cambiar de hardware o de modelo puede cambiar lo útil que es AURA. Nunca lo segura que es.**

Verificable: si un cambio de plataforma pudiera degradar una garantía, esa garantía estaba mal
implementada.

### Consecuencia para las mediciones

Toda cifra de rendimiento debe registrarse **junto a la plataforma en que se obtuvo**. Una latencia
sin plataforma asociada no es un dato del sistema: es un dato de una máquina. HC-1 seguirá evaluándose
contra la plataforma de referencia vigente en cada momento, y ese vínculo debe quedar explícito en
cada informe.

## Impacto (acta D11 — obligatorio)

| Dimensión | Impacto |
|---|---|
| **Seguridad** | Positivo: ninguna garantía puede depender de la plataforma; se cierra la vía a "es seguro porque este equipo es así" |
| **Privacidad** | Neutro respecto a ADR-0001, que sigue rigiendo (local-first) |
| **Modularidad** | Positivo alto: refuerza las fronteras ya existentes y las hace explícitas |
| **Costo** | Positivo: evita comprometer capital en hardware antes de conocer el escenario de despliegue |
| **Rendimiento** | **Coste real y aceptado**: renunciar a optimizaciones específicas de plataforma. A cambio, AURA corre en cualquier sitio |
| **Mantenibilidad** | Positivo a 10 años (D20): el hardware envejece mucho más rápido que la arquitectura |
| **Reversibilidad** | Máxima: es precisamente lo que este ADR preserva |

## Riesgos aceptados

- **Se renuncia a exprimir una plataforma concreta.** Un Core que no asume aceleración deja
  rendimiento sobre la mesa. Aceptado: la portabilidad vale más que ese margen, y el cuello de
  botella actual es de dos órdenes de magnitud, no de optimización fina.
- **La decisión diferida podría demorarse indefinidamente.** Mitigación: depende de definir el
  escenario de despliegue, que es una decisión de producto ya identificada como pendiente. Conviene
  no perderla de vista: mientras no se tome, HC-1 permanece sin validar y M3 sin datos de uso real.
