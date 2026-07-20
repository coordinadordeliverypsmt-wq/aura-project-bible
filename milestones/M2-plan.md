---
documento: "Plan de Milestone M2 — Manos Digitales"
version: 1.0.0
autor: "CTO"
fecha: "2026-07-20"
estado: "Propuesta — pendiente de autorización del CEO"
---

# Milestone M2 — Manos Digitales

## Puerta de entrada

M1 cerrado técnicamente · 4/4 garantías críticas en verde · sin alertas abiertas · entorno APTO.

## Objetivo

AURA pasa de **conversar** a **actuar**: control del computador, automatización de tareas y
notificaciones proactivas. Es el salto que convierte al PIOS de interlocutor en operador.

## El riesgo que define este milestone

En M1, una acción mal autorizada encendía una luz simulada. **En M2, una acción mal autorizada borra
archivos reales, envía mensajes reales o modifica configuración real del sistema.** El perímetro de
seguridad deja de ser teórico.

Consecuencia de diseño, y condición innegociable: **la clasificación de cada nueva capacidad en lista
verde o roja se define y se prueba ANTES de implementar la capacidad**, no después. Ninguna acción con
efecto llega al sistema sin haber pasado antes por Permisos con su prueba determinista.

## Fase 0 — Deuda de M1 (bloqueante, antes de cualquier capacidad nueva)

1. **Auditoría del patrón "mock escrito para pasar la eval".** ALERTA-004 se descubrió porque el doble
   de prueba estaba escrito para cumplir la garantía que debía verificar. Revisar todas las evals y
   pruebas buscando el mismo patrón. Es la recomendación #1 de la Architecture Review M1-Exit.
2. **Inventario de garantías declaradas sin implementación**, aplicando el criterio de ADR-0014: toda
   garantía de la Bible debe tener prueba determinista o dejar de llamarse garantía.

## Fases propuestas

| Fase | Contenido | Salida verificable |
|---|---|---|
| **M2.0** | Deuda de M1 (arriba) | Informe de auditoría; evals corregidas |
| **M2.1** | Perímetro de seguridad ampliado: lista roja para acciones sobre el sistema de archivos, red, procesos y mensajería | Pruebas parametrizadas de HITL por cada acción nueva |
| **M2.2** | Adaptador de control del computador tras contrato `Adapter` | Capacidad demostrada + kill switch verificado sobre acciones reales |
| **M2.3** | Automatización (tareas programadas, disparadores) | Demo de capacidad; auditoría de trazas |
| **M2.4** | Notificaciones proactivas | Demo; control de frecuencia y consentimiento |
| **M2-Exit** | Architecture Review + Executive Summary (D25) | Cierre formal |

## Restricciones heredadas

- **D24:** local-first, sin APIs comerciales ni claves de terceros.
- **ADR-0014:** ninguna garantía puede depender del comportamiento del modelo.
- **ADR-0003 / D9:** lista roja siempre confirmada, tolerancia cero a falsos negativos.
- **D26:** ninguna dependencia nueva sin beneficio medible demostrado.
- **D27 / D31:** Preflight Check obligatorio; almacenamiento distribuido.

## Riesgos abiertos que M2 hereda

1. **HC-1 sin validar.** M2 no lo resuelve: requiere hardware objetivo. Recomendación: separar
   explícitamente validación funcional (posible aquí) de validación de latencia (no posible aquí).
2. **USB principal al límite:** 616 MB libres. `swapfile_aurora` ocupa 4 GB sin prestar servicio.
   M2 añadirá artefactos; conviene resolverlo antes.
3. **Hardware por debajo del mínimo:** cada iteración con LLM real cuesta 2-5 minutos, lo que limita
   el ritmo de validación. Mitigación disponible: usar `qwen2.5:0.5b` para validación funcional —ya
   demostrado equivalente en comportamiento seguro (adherencia 100%)— reservando `3b` para calidad.

## Recomendación del CTO sobre el orden

**No iniciar M2.2 (actuar sobre el computador) antes de completar M2.0 y M2.1.** Dar capacidad de
acción real a un sistema cuyo perímetro de seguridad no ha sido auditado invierte el orden que hizo
que M1 terminara con las garantías en verde.
