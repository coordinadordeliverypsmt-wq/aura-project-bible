---
documento: "Architecture Review — M2 Exit"
milestone: "M2 — Manos Digitales"
fecha: 2026-07-21
autor: "CTO"
estado: "Presentado al CEO para gate de cierre"
base: "commit 82c8cfd"
---

# Architecture Review — M2 Exit

Conforme a D25 (Architecture Review en cada frontera de milestone) y a la Definition of Done
declarada en el Architecture Review M2 Entry §7.

## 1. Resumen de la fase

M2 debía dar a AURA **manos digitales**: capacidad de actuar sobre el computador principal bajo
gobierno estricto. Se completó en seis fases, una más de las planificadas:

| Fase | Contenido | Estado |
|---|---|---|
| M2.0 | Corrección de H1 (firma de `Adapter`), H2 (audit log persistente), H3 (catálogo explícito) | ✅ |
| M2.1 | Catálogo de 9 operaciones tipadas, validación de ámbito, pruebas adversariales | ✅ |
| M2.2 | Adaptador del computador con puerta única y protección TOCTOU | ✅ |
| M2.3 | Motor de automatización con dry-run obligatorio | ✅ |
| M2.4 | Centro único de notificaciones | ✅ |
| **M2.5** | **Integración (ALERTA-005): conexión del orquestador a los componentes** | ✅ |

**M2.5 no estaba planificada.** Se abrió al detectar que los tres componentes construidos en
M2.2–M2.4 eran inalcanzables desde la conversación. Se detalla en §3.

## 2. Definition of Done — verificación punto por punto

| # | Criterio | Estado | Evidencia |
|---|---|---|---|
| 1 | H1, H2, H3 corregidos | ✅ | `test_contrato_adapter_firma`, `test_audit_log`, `test_catalogo_acciones` |
| 2 | Catálogo cerrado, clasificado y probado por acción | ✅ | 97 pruebas parametrizadas sobre las 27 acciones |
| 3 | Las 7 evaluaciones de §6 en PASS | ✅ | Todas, más la de alcanzabilidad añadida en M2.5 |
| 4 | Cero acciones con efecto sin pasar por Permisos | ✅ | Camino único de ejecución; verificado con caso de control |
| 5 | Audit log persistente e íntegro tras reinicio | ✅ | `test_audit_log_sobrevive_reinicio` |
| 6 | Kill switch detiene conversación **y** automatizaciones | ✅ | Demostrado en demo real, ambas vías |
| 7 | Dry-run sin efectos colaterales | ✅ | Huella completa del árbol (tamaño + mtime) |
| 8 | Quality Gate PASS, sin regresión de M1 | ✅ | **234 passed, 3 skipped + 8 contratos** |
| 9 | Demo de capacidad M2 con stack real, **0 errores no recuperados** | ⚠️ | **8/9 capacidades.** Ver §4 |
| 10 | Architecture Review M2-Exit + Executive Summary | ✅ | Este documento |
| 11 | Sin alertas de arquitectura abiertas | ✅ | ALERTA-005 resuelta |

## 3. ALERTA-005 — el hallazgo que definió el cierre

Al preparar la demo de capacidad se comprobó que `AdaptadorComputador`, `MotorAutomatizacion` y
`CentroNotificaciones` **solo se instanciaban en sus propias pruebas**. El orquestador conocía un
único adaptador. Una petición como *"busca mis facturas"* moría tras Permisos.

Peor: cuando Permisos autorizaba una acción que ningún adaptador podía atender, el orquestador
devolvía la frase de éxito del LLM. **AURA afirmaba haber hecho algo que no hizo** — y el error no
provenía del modelo sino del Core, precisamente la fuente que ADR-0014 declara única autoridad sobre
los hechos del sistema.

### Lo que se corrigió

1. **Registro de adaptadores.** Una capacidad, un dueño; una capacidad reclamada dos veces se
   rechaza al registrar en lugar de resolverse por orden de inserción.

2. **Camino único de ejecución.** El orquestador **no llama a ningún adaptador**: delega en el motor,
   que pasa a ser el único ejecutor del sistema, compartido por conversación, reglas y
   notificaciones. Se descartó escribir un segundo flujo en el orquestador: dos implementaciones del
   mismo control acaban divergiendo, que es el error que M2.2 ya había evitado exigiendo una sola
   llamada a `validar()`.

3. **Permisos antes que adaptador.** Durante el refactor puse la resolución del adaptador primero
   —parecía razonable, fallar rápido— y las pruebas e2e de lista roja detectaron una regresión real:
   **una acción roja sin adaptador dejaba de pasar por HITL y desaparecía del registro forense.** Un
   intento de `transferencia` debe quedar auditado aunque AURA no tenga forma de transferir nada. Que
   la capacidad no exista es una circunstancia de la instalación, no una razón para no aplicar el
   control. Orden final: dry-run → **Permisos/HITL** → resolución de adaptador → ejecución.

4. **Prohibido el éxito sin evidencia.** La frase del modelo solo sobrevive si el adaptador devolvió
   un resultado. En cualquier otro caso se descarta y el Core informa el hecho real.

### La medida que ataca la causa

ALERTA-004 y ALERTA-005 fueron **el mismo fallo con un día de diferencia**: algo declarado en un
documento de arquitectura, ausente del código, invisible porque las pruebas verificaban la pieza en
aislamiento. M2 llegó a tener 218 pruebas en verde con su capacidad principal inalcanzable.

Se añadió `test_alcanzabilidad_capacidades.py` al Quality Gate:

- Recorre `registro.capacidades()`, **no una lista escrita a mano**: registrar un adaptador sin
  cablearlo hace fallar el gate.
- El espía **delega** en el adaptador real y se comprueba el efecto en el sistema de archivos.
- Caso de control: una acción sin adaptador no puede reportarse como éxito.
- **Validada por mutación**: al forzar `registro.para()` a devolver `None` —reproduciendo
  ALERTA-005— la prueba falla. Una prueba que nunca se ha visto fallar no es evidencia de nada.

## 4. Demo de capacidad con stack real — resultado honesto

Ejecutada con Ollama local (D24), sin APIs de terceros.

| Capacidad | Mocks | Stack real |
|---|---|---|
| Actúa sobre el computador cuando se lo piden hablando | ✅ | ✅ |
| Previsualiza ANTES de pedir confirmación | ✅ | ✅ |
| Ejecuta lo destructivo solo tras confirmar | ✅ | ✅ |
| Nunca reporta éxito sin evidencia de ejecución | ✅ | ⚠️ no ejercitada |
| Automatiza por reglas con dry-run obligatorio | ✅ | ✅ |
| Kill switch detiene conversación Y automatizaciones | ✅ | ✅ |
| Consolida y prioriza notificaciones | ✅ | ✅ |
| Rechaza fuentes fuera del MVP | ✅ | ✅ |
| Purga contenido de terceros al cerrar sesión | ✅ | ✅ |
| | **9/9** | **8/9** |

Evidencia del turno destructivo, con efecto real verificado:

```
Usuario: "Borra el archivo /tmp/aura_m2_.../documentos/borrador-viejo.txt"
  (HITL) AURA pide confirmar 'borrar_archivo'
         previsualizacion: se eliminaria .../borrador-viejo.txt (30 bytes)
  efecto real: el archivo YA NO existe
```

### Por qué 8/9, y por qué no es un fallo del sistema

La capacidad no ejercitada requiere que el modelo emita una acción sin adaptador. Ante
*"Recuérdame comprar pan mañana"*, el modelo **eligió `abrir_archivo`** — una acción absurda para esa
petición. Al existir adaptador, el escenario no llegó a producirse.

La garantía sí está verificada, por prueba determinista
(`test_accion_sin_adaptador_no_se_reporta_como_exito`) y en la corrida con dobles. Lo que la demo no
pudo hacer es provocar el escenario con un modelo que elige por su cuenta.

**El hallazgo relevante es otro:** el modelo de 0,5 B elige acciones poco fiables — una claramente
equivocada y otra aproximada (`listar_directorio` en lugar de `buscar_archivo`) de tres peticiones.
Y sin embargo **no causó ningún daño**: la acción errónea era de lista verde, solo lectura, y el
catálogo impidió cualquier otra cosa.

Eso es exactamente lo que la arquitectura debía demostrar. La seguridad de AURA **no depende de que
el modelo acierte**. Un modelo que se equivoca produce una acción inútil, no una destructiva.

### Errores no recuperados: cero — tras corregir uno que la demo encontró

La primera ejecución **derribó el turno completo** con `FileNotFoundError`: una regla que dispara dos
veces sobre el mismo archivo encontraba el origen ya movido, y `os.lstat` propagaba la excepción a
través del motor.

El estado del disco es una condición del entorno, no un error de programa. Corregido: degrada a
`detenida` (dry-run) o `error` (ejecución) sin derribar el turno, con dos pruebas de regresión. **Un
defecto real que solo aparece ejecutando de verdad** — la justificación de por qué la DoD exige una
demo sobre stack real y no solo pruebas.

## 5. Latencia — medición inválida, no medición favorable

| Turno | Tiempo |
|---|---|
| 1 | 467.858 ms |
| 2 | 147.739 ms |
| 3 | 145.984 ms |

**Estas cifras no son utilizables** y no deben citarse como medición de M2:

- Con `qwen2.5:3b` la demo **agotó 600 s por turno** y abortó. Al inspeccionar: 156 MB de RAM libre,
  es decir, el sistema estaba haciendo swap. **Toda medición con swapping es inválida** por criterio
  ya establecido en este proyecto.
- La corrida que sí completó usó `qwen2.5:0.5b` con `load average 6,9 en una máquina de 2 núcleos`:
  el modelo competía por CPU con el resto del escritorio. Contención, no rendimiento del sistema.

**HC-1 sigue Pendiente de validación en entorno objetivo (D24).** M2 no lo mueve ni podía moverlo.
Registrar un número contaminado como si fuera una medición sería peor que no medir.

## 6. Contratos e invariantes

| Contrato | Compromiso M2 Entry | Resultado |
|---|---|---|
| `ModelProvider` | Invariante | ✅ Sin cambios en la interfaz |
| `MemoryStore` | Invariante | ✅ |
| `EventBus` | Invariante | ✅ |
| `VoiceAdapter` | Invariante | ✅ |
| `Adapter` | Corregir la firma (H1) | ✅ Corregido y verificado con `inspect.signature` |
| ADR-0014 | Invariante y reforzado | ✅ **Reforzado**: el Core dejó de reportar hechos falsos |
| ADR-0001, ADR-0003, D24 | Invariantes | ✅ |
| D32 | Vigente | ✅ `mover_archivo`/`renombrar_archivo` siguen en lista roja |

Nota sobre ADR-0014: M2.5 amplió su alcance en la práctica. Hasta ahora se aplicaba a la memoria —el
LLM no puede inventar recuerdos—. El hallazgo secundario de ALERTA-005 mostró que **el Core también
puede mentir**, y que la regla debe leerse en los dos sentidos: ninguna afirmación del sistema sobre
sus propios actos puede emitirse sin evidencia.

## 7. Riesgos del Architecture Review M2 Entry — cierre

| Riesgo | Estado |
|---|---|
| RN-1 · Pérdida de datos por acción destructiva | **Mitigado.** Lista roja + dry-run + TOCTOU + rechazo de colisión |
| RN-2 · Deriva hacia ejecución de comandos arbitrarios | **Cerrado.** Catálogo finito; `ejecutar_comando` rechazado por deny-por-defecto |
| RN-3 · Automatizaciones fuera del alcance del kill switch | **Cerrado.** Verificado en demo real, ambas vías |
| RN-4 · Escalada de ámbito por rutas relativas o enlaces | **Mitigado.** Rechazo de rutas relativas; validación de literal y resuelta |
| RN-5 · El centro de notificaciones como puerta trasera | **Cerrado.** No ejecuta: delega en el motor |

## 8. Product Readiness — actualizado solo con evidencia obtenida

| Dimensión | Peso | Evidencia | M1 | **M2** |
|---|---|---|---|---|
| Entiende y responde con sentido | 15% | El 0,5 B eligió mal 1 de 3 acciones y aproximó otra; con 3 B no hay dato (timeout) | 12% | **10%** |
| **Responde a tiempo** | **25%** | Sin medición válida; HC-1 abierto | 0% | **0%** |
| Entrada y salida por voz | 15% | Sin cambios en M2 | 5% | **5%** |
| Conversación natural (interrumpible) | 10% | Barge-in sigue diferido | 0% | **0%** |
| Recuerda entre sesiones | 10% | Sin cambios en M2 | 9% | **9%** |
| **Hace cosas útiles (acciones reales)** | **15%** | 9 operaciones alcanzables hablando, con efecto real verificado | 1% | **12%** |
| Disponible sin fricción | 5% | Sigue requiriendo lanzar procesos a mano | 0% | **0%** |
| Seguro y gobernable | 5% | HITL, kill switch, dry-run, grounding, auditoría | 5% | **5%** |
| | | **PRODUCT READINESS** | **32%** | **41%** |

Suma: 10 + 0 + 5 + 0 + 9 + 12 + 0 + 5 = **41**.

### Lectura honesta

**El objetivo declarado al abrir M2 era ~45%. El resultado es 41%.** Las dos diferencias:

- *Disponible sin fricción* debía subir a ~3% y **no subió nada**: M2 no tocó el arranque del
  sistema, que sigue exigiendo lanzar procesos a mano.
- *Entiende y responde con sentido* **bajó de 12% a 10%**, y bajarlo es la parte más incómoda de este
  informe. No es que el sistema empeorara: es que por primera vez hay evidencia de cómo elige
  acciones un modelo local en peticiones reales, y esa evidencia es mediocre. En M1 la cifra reflejaba
  "funciona con LLM local"; ahora refleja lo observado.

La dimensión que sí se movió es la que M2 tenía que mover: **"hace cosas útiles" de 1% a 12%**, con
nueve operaciones reales alcanzables hablando y efecto verificado en disco.

Y el dato que sigue dominando todo lo demás: **a más de dos minutos por turno, AURA no es usable
durante una jornada**, tenga las manos que tenga. La palanca de producto sigue siendo el hardware
objetivo (HC-1), no la siguiente capacidad. Esto se dijo al abrir M2 y el cierre lo confirma.

## 9. Deuda declarada al salir de M2

| Asunto | Estado |
|---|---|
| **HC-1** — latencia en entorno objetivo | Pendiente (D24). Ninguna medición válida disponible |
| **Calidad de decisión del modelo pequeño** | Observada y no resuelta. Contenida por arquitectura, no eliminada |
| **Arranque sin fricción** | No abordado en M2; bloquea Product Readiness |
| **Barge-in, captura de micrófono, VAD** | Diferidos a hito independiente con gate propio |
| **D32** — reclasificación de mover/renombrar | Se revisará con datos de uso reales |
| `swapfile_aurora` ocupa 4 GB del USB sin prestar servicio | Recomendación del CTO pendiente de decisión |

## 10. Recomendación del CTO

**M2 está en condiciones de cerrarse**, con la salvedad explícita del punto 9 de la DoD: la demo con
stack real cubrió 8 de 9 capacidades, y la novena está verificada por prueba determinista aunque no
por la demo. No lo presento como 9/9.

Sobre qué debería venir después, mi recomendación es que **M3 no sea otra capa de capacidades**. El
cierre de M2 deja dos hechos incómodos juntos: el sistema no responde a tiempo y el modelo local
elige regular. Añadir más funciones encima no mejora ninguno de los dos. Antes conviene decidir el
hardware objetivo, porque condiciona qué modelo puede correr y, con él, la calidad de decisión.

Es una recomendación, no una objeción al roadmap: la decisión de prioridad es del CEO.
