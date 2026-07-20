---
documento: "Paquete Ejecutivo de Cierre — Milestone M1"
version: 1.0.0
autor: "CTO"
fecha: "2026-07-20"
estado: "Pendiente de aprobación del CEO"
---

# Paquete Ejecutivo de Cierre — Milestone M1

## 1. Lecciones aprendidas

**L1 — Un guardarraíl es código verificable, no una expectativa sobre un modelo.**
Dentro del mismo milestone, dos garantías críticas se comportaron de forma opuesta al sustituir mocks
por LLM real: HITL pasó 3/3 porque **la impone el núcleo**; grounding falló porque se delegaba
implícitamente en el modelo. Origen de ADR-0014.

**L2 — Una eval que valida contra un mock escrito para pasarla no valida nada.**
`grounding_no_fabricacion` estuvo en verde durante todo el desarrollo con mocks porque el doble de
prueba devolvía `"Segun lo que recuerdo: {ctx}"`. Verificaba el mock, no el sistema.

**L3 — El cambio peligroso es el que funciona.**
El parche de ALERTA-003 (Gemini como proveedor principal) **habría hecho pasar la demo**. Ese éxito
aparente habría enviado el contexto del usuario a un tercero, enmascarado el límite real de hardware y
convertido un baseline gratuito en uno de pago — sin un solo test en rojo.

**L4 — Verificar el estado real, nunca la configuración declarada.**
`OLLAMA_MODELS` apuntaba a una ruta correcta que, con el USB desmontado, era el disco interno. Linux no
falla en ese caso: escribe y calla. Origen de D27 y del principio de comprobar el **dispositivo físico**
que respalda cada ruta.

**L5 — Los identificadores estables no son una preferencia de estilo.**
Un reinicio renombró `sda1` → `sdb1`. Todo siguió funcionando porque Preflight y guardarraíl localizan
por **etiqueta**. Con rutas fijas, el sistema habría apuntado al dispositivo equivocado en silencio.

**L6 — Medir antes de teorizar.**
Se refutaron por medición dos hipótesis plausibles sobre la latencia: almacenamiento (la ubicación de
los archivos no afecta al cómputo) y timeout del cliente (era síntoma). La causa real —8.738 ms/token—
solo apareció instrumentando.

## 2. Decisiones arquitectónicas que demostraron ser correctas

| Decisión | Evidencia de M1 |
|---|---|
| **ADR-0003 / D9** — HITL impuesto por el núcleo | 3/3 acciones de lista roja detenidas con LLM real |
| **ADR-0010** — Ollama local como runtime | Sostuvo el núcleo completo sin nube; refutó la premisa de ALERTA-003 |
| **P-ARQ-4 / 4.2** — proveedores tras contrato `ModelProvider` | Añadir un 2.º modelo no tocó una línea del router |
| **D24** — local-first sin claves de terceros | Resistió una solicitud directa de refactor a API comercial |
| **D15** — deber de disenso | Cuatro alertas emitidas, cuatro resueltas, cero decisiones de rango 1 enmendadas |
| **Walking Skeleton primero** | Detectó dos bugs reales de seguridad antes de existir producto |
| **ADR-0014** (nuevo) | Confirmado empíricamente: 0.5b y 3b → misma acción segura, 100% |

## 3. Errores detectados durante M1

### Del sistema
1. **Contaminación de intención por contexto de memoria** — la palabra "luz" en un recuerdo alteraba la
   clasificación. Corregido: clasificar sobre la frase del usuario con prioridad de lista roja.
2. **Bypass de HITL (crítico)** — el orquestador enrutaba a Permisos solo 3 acciones cableadas;
   `transferencia` y `abrir_cerradura` se ejecutaban sin confirmación. Corregido: **toda** acción con
   efecto pasa por Permisos. Test de regresión parametrizado.
3. **Grounding no implementado (ALERTA-004)** — garantía declarada en la Bible y en el arnés, ausente
   del código. Corregido con ADR-0014.

### Del proceso y del CTO
4. **`validar_m1.py` se commiteó vacío** durante un episodio de disco lleno. Lección aplicada: verificar
   que el archivo no queda vacío tras cada escritura crítica.
5. **Falso positivo peligroso en mi propio Preflight** — marcaba `/usr/share/ollama` como obsoleto por su
   mera existencia y proponía `rm -rf`, lo que **habría destruido el symlink al USB**. Corregido.
6. **Verificación de integridad tautológica** — comparé el store interno con el USB sin advertir que el
   primero era un symlink al segundo: comparé archivos consigo mismos. Retirada del registro.
7. **Entrada duplicada en `/etc/fstab`** — mi script comprobaba la cadena `LABEL=` en vez del punto de
   montaje, y añadió una segunda entrada al mismo destino. Corregido.
8. **D28, D29 y D30 sin registrar** — declaradas por el CEO el 2026-07-19 y no escritas en el acta hasta
   la elaboración de este paquete. Fallo de disciplina documental.

## 4. Deuda técnica pendiente

| # | Deuda | Impacto | Prioridad |
|---|---|---|---|
| T1 | **Auditoría del patrón "mock escrito para pasar la eval"** en el resto de pruebas | Podría ocultar otras garantías inexistentes | **Alta — bloquea M2** |
| T2 | **STT real sin validar**: `faster-whisper` no instalado; el adaptador hace passthrough de texto | La cadena de voz está validada solo en TTS | Alta |
| T3 | **HC-1 sin validar** — requiere hardware objetivo | Objetivo de producto sin verificar | Alta (externa) |
| T4 | Latencia medida con **N=5** en lugar de 30 | Muestra estadísticamente débil | Baja (métrica ya inválida) |
| T5 | Sin entorno virtual: falta `python3.12-venv`; paquetes en `~/.local` con `--break-system-packages` | Aislamiento de dependencias imperfecto | Media |
| T6 | `swapfile_aurora` ocupa 4 GB del USB principal **sin prestar servicio** | 616 MB libres; M2 añadirá artefactos | Media |
| T7 | Capacidad 6 del MVP pide **3 LLMs**; validados 2 modelos locales | Alcance de capacidad incompleto | Media |

## 5. Deuda documental pendiente

| # | Deuda | Estado |
|---|---|---|
| DOC1 | **D28, D29, D30 no registradas en el acta** | ✅ **Saldada en este paquete** (acta v1.12.0) |
| DOC2 | `ESTADO-ENTORNO-VERIFICADO.md` refleja un estado anterior a la migración | Pendiente |
| DOC3 | Migración de la Bible a MkDocs (HTML navegable, D12) | Pendiente |
| DOC4 | Trazabilidad Bible → ADR → Código → Pruebas sin auditar sistemáticamente tras ALERTA-004 | Pendiente (ligada a T1) |
| DOC5 | `M1-plan.md` no refleja el resultado final del hito | Pendiente |

## 6. Riesgos que heredará M2

| # | Riesgo | Mitigación propuesta |
|---|---|---|
| R1 | **En M2 una acción mal autorizada borra archivos reales**, no simulados | Definir y probar la clasificación verde/roja **antes** de implementar cada capacidad |
| R2 | Garantías declaradas sin implementación en otras áreas (patrón ALERTA-004) | Fase M2.0 bloqueante |
| R3 | HC-1 sigue sin validar | Separar validación funcional de validación de latencia |
| R4 | Hardware por debajo del mínimo: 2-5 min por iteración con LLM real | Usar `qwen2.5:0.5b` para validación funcional (equivalencia de comportamiento ya demostrada) |
| R5 | USB principal con 616 MB libres | Resolver T6 antes de M2 |
| R6 | **Criterio de la Bible no cumplido:** 2.2 §3.1 exige "semanas de calendario" de memoria sostenida | Ver §9 — M1 está cerrado *técnicamente*, no por uso sostenido |

## 7. Estado de todos los ADR

**14 ADRs, los 14 en estado `accepted`. Ninguno modificado ni derogado durante M1.**

| ADR | Título | Estado | Validado en M1 |
|---|---|---|---|
| 0001 | Local-first estricto | accepted | ✅ resistió ALERTA-003 |
| 0002 | Arquitectura de eventos | accepted | ✅ bus real (NATS) operativo |
| 0003 | Human-in-the-Loop | accepted | ✅ 3/3 lista roja |
| 0004 | Evolución permanente | accepted | ✅ sin sobre-ingeniería |
| 0005-0009 | Stack balanceado | accepted | ✅ íntegramente local |
| 0010 | Ollama runtime LLM | accepted | ✅ sostuvo el núcleo |
| 0011 | Memoria persistente | accepted | ✅ backup/restore verificados |
| 0012 | STT local | accepted | ⚠️ **sin validar** (T2) |
| 0013 | TTS local | accepted | ✅ Piper es_MX |
| **0014** | **Core = única fuente de verdad** | **accepted (nuevo)** | ✅ adherencia 100% |

## 8. Estado de todas las Alertas de Arquitectura

**4 emitidas · 4 resueltas · 0 abiertas · 0 decisiones de rango 1 enmendadas.**

| Alerta | Asunto | Resolución |
|---|---|---|
| 001 | Bus de eventos vs. streaming de baja latencia | RESUELTA — Opción A (canales dedicados + correlación) |
| 002 | Captura de datos de terceros | RESUELTA — Alternativa A con alcance de sesión |
| 003 | Gemini cableado en el router | RESUELTA — Alternativa A, parche rechazado |
| 004 | Grounding declarado pero no implementado | RESUELTA — Alternativa A+B → ADR-0014 |

## 9. Dashboard general del proyecto

### Avance por dimensión

| Dimensión | Avance | Base de cálculo |
|---|---|---|
| **Project Bible v1.0** | **100%** | 36 capítulos aprobados, alcance funcional cerrado (D23) |
| **Decisiones fundacionales** | **100%** | D1-D31 registradas (acta v1.12.0) |
| **ADRs** | **100%** de lo requerido hasta hoy | 14/14 accepted |
| **Alertas resueltas** | **100%** | 4/4 |
| **M1 — cierre técnico** | **100%** | 4/4 garantías críticas en verde, Quality Gate PASS |
| **M1 — criterio pleno de la Bible** | **~15%** | 2.2 §3.1 exige *semanas de calendario* de memoria sostenida |
| **M2 — Manos digitales** | **0%** | No iniciado |
| **M3 — Presencia** | **0%** | No iniciado |
| **HC-1 (latencia)** | **0% validado** | Requiere hardware objetivo (D24) |

### Avance real del MVP

El MVP son **9 capacidades** repartidas en 3 hitos (2.2 §3). M1 cubre las capacidades 1, 2 y 6.

> **Avance real del MVP: ~28%**
> 3 de 9 capacidades implementadas y verificadas técnicamente (33%), ajustado a la baja porque la
> capacidad 6 pide **3 LLMs** y se validaron 2 (T7), y porque el criterio de sostenimiento en calendario
> de M1 no está cumplido.

**Advertencia sobre esta cifra:** mide capacidades construidas, **no** producto listo para uso. HC-1 sin
validar y la ausencia de uso sostenido real significan que el porcentaje refleja ingeniería completada,
no valor entregado al usuario.

### Salud del proyecto

| Indicador | Valor |
|---|---|
| Quality Gate | ✅ PASS (45 pruebas + 4 contratos) |
| Errores no recuperados en validación | 0 |
| Deuda técnica alta | 3 ítems (T1, T2, T3) |
| Alertas abiertas | 0 |
| Decisiones de rango 1 enmendadas | 0 |
| Dependencias propietarias | 0 |
| Disco interno libre | 13 GB (era 889 MB) |

## 10. Recomendaciones del CTO para M2

1. **M2.0 es bloqueante.** No implementar ninguna capacidad nueva antes de auditar el patrón de
   ALERTA-004 (T1). Es la recomendación de mayor prioridad de todo este paquete: dar capacidad de acción
   real sobre archivos y procesos a un sistema cuyas garantías no han sido auditadas invierte el orden
   que hizo que M1 terminara en verde.

2. **Definir el perímetro antes que la capacidad.** Cada acción nueva se clasifica en lista verde/roja y
   se prueba **antes** de que exista el adaptador que la ejecuta.

3. **Cerrar T2 (STT real) al inicio de M2.** ADR-0012 está aceptado pero sin validar; la cadena de voz
   está verificada a medias.

4. **Separar formalmente validación funcional de validación de latencia** mientras no haya hardware
   objetivo, usando `qwen2.5:0.5b` para la primera. La equivalencia de comportamiento seguro entre
   modelos está demostrada (100%).

5. **Resolver T6 antes de empezar** — 616 MB libres en el USB principal no bastan para los artefactos
   de M2.

6. **Instrumentar desde el día uno la captura de señales** que M3 necesitará (2.2 §3.5): sin esa materia
   prima, la anticipación de M3 se retrasa semanas por diseño.

7. **Iniciar el reloj del criterio de calendario de M1.** El uso sostenido de memoria durante semanas
   puede correr **en paralelo** a M2: no requiere trabajo de ingeniería, solo uso real y observación.
   Empezarlo ahora evita que bloquee el cierre del MVP más adelante.
