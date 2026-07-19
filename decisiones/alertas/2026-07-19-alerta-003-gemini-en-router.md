---
documento: "ALERTA DE ARQUITECTURA 003"
estado: "Activa — pendiente de gate extraordinario del CEO"
fecha: 2026-07-19
emisor: "Fable (CTO), conforme al acta D15 y la constitucion 1.1 §4"
trabajo-suspendido: "El parche solicitado a aura_skeleton/modules/router.py (cablear Google Gemini como proveedor principal con clave de API) y la instalacion de google-generativeai. NO se aplica hasta el veredicto del CEO."
---

# ALERTA-003 — Cablear Gemini (API comercial + clave) como proveedor principal contradice D24/D1/ADR-0001/ADR-0010/P-ARQ-4

Estructura obligatoria de 10 secciones (acta D16).

## 1. Problema detectado

Se solicito refactorizar `router.py` para: importar `google.generativeai`, leer `GEMINI_API_KEY`, y usar Gemini (nube comercial) como **proveedor principal**, con Ollama solo como fallback. Esto choca con decisiones de rango 1 aprobadas el 2026-07-18:

- **D24:** "para validar HC-1 y como baseline reproducible **no se utilizaran APIs comerciales ni claves de terceros**… no se solicitan claves de API ni soluciones propietarias salvo justificacion arquitectonica previamente documentada y aprobada". No existe tal justificacion aprobada.
- **D1 / ADR-0001 (local-first estricto):** los datos del usuario (incluido el contexto de memoria del prompt) no salen a la nube salvo minimizacion; el default debe ser local.
- **ADR-0010 (accepted):** Ollama local es el runtime de LLM elegido, precisamente para no depender de claves/proveedores.
- **P-ARQ-4 (ningun proveedor unico) + 4.2:** los proveedores se conectan **tras el contrato `ModelProvider`**; el router enruta entre proveedores, no llama a un SDK concreto. Cablear `genai` dentro de `router.py` rompe la abstraccion.
- **D26:** `google-generativeai` es una dependencia nueva propietaria sin beneficio medible documentado.

**Diagnostico del parche, incorrecto:** "el sistema falla porque usa Ollama por defecto y no detecta la clave de Gemini". Usar Ollama por defecto **es el diseno aprobado**, no un bug. Un fallo de `demo_capacidad_m1.py --real` significa que **Ollama no esta corriendo/instalado** en el hardware objetivo — el fix correcto es arrancar Ollama (`verify-stack`), no reemplazarlo por una nube comercial.

## 2. Riesgos si se ignora

- **Reversion silenciosa de local-first (D1/D24):** el contexto del usuario iria a Google; se rompe el pilar de privacidad.
- **Lock-in de proveedor (contra P-ARQ-4, D19):** dependencia estrategica de un unico proveedor comercial (precio, ToS, deprecacion, disponibilidad).
- **Baseline no reproducible:** HC-1 dejaria de ser medible sin una clave de pago y conectividad; se invalida la validacion local.
- **Ruptura de la abstraccion:** `genai` en `router.py` acopla el router a Gemini; futuros proveedores exigirian tocar el router (contra P-ARQ-3/4).
- **Precedente:** aplicar un cambio que contradice decisiones de rango 1 sin gate erosiona la gobernanza.

## 3. Tres alternativas posibles

### A. Mantener local-first; arreglar la causa REAL del fallo (recomendada)
El fallo de `--real` es operativo: Ollama no esta arriba. Acciones: correr `verify-stack`, `ollama serve`, `ollama pull`; mejorar el mensaje de error de `OllamaProvider` y anadir el log `[ROUTER] Intentando usar proveedor: OLLAMA`. **Cero cambios de arquitectura; respeta D24/D1/ADR-0010.**

### B. Gemini como recurso OPCIONAL tras el contrato (si el CEO lo decide, con enmienda de D24)
La D2 admite ChatGPT/Claude/Gemini como capacidades del MVP, pero la D24 los dejo **opcionales tras el router y nunca como default de validacion**. Si el CEO quiere habilitarlos: se crea un **`GeminiProvider` que implementa `ModelProvider`** (como `OllamaProvider`), seleccionable por **config explicita**, con **minimizacion previa (ADR-0001 r5)**, **nunca como default** del baseline local, y **enmendando la D24** (justificacion documentada + `google-generativeai` justificada por D26). El router permanece agnostico; Ollama sigue siendo el default local.

### C. Rechazar el cambio (statu quo)
Se mantiene el diseno local-first; se documenta el rechazo.

## 4. Recomendacion del CTO

**Alternativa A.** El sintoma ("falla") es operativo (Ollama no corriendo), no arquitectonico; la solucion es hacer funcionar Ollama, no reemplazarlo por una nube comercial. Si ademas el CEO quiere Gemini como **opcion** (no default), hacerlo por la **Alternativa B** (GeminiProvider tras el contrato + enmienda de D24), **jamas** cableando `genai` en `router.py` ni como proveedor principal. El parche solicitado tal cual **no debe aplicarse**.

## 5. Impacto en costo

A: cero (local, gratis tras hardware). B/parche: costo recurrente por token + gestion de clave. El parche convierte un baseline gratuito en uno de pago.

## 6. Impacto en rendimiento

A: latencia local deterministica (HC-1 medible). Parche: latencia de red + rate limits + caidas del proveedor; HC-1 local invalidado.

## 7. Impacto en seguridad y privacidad

Parche: prompts y contexto de memoria del usuario salen a la nube de Google -> contradice D1/ADR-0001 (local-first, minimizacion); rompe el pilar de privacidad. A/B(min): protegido.

## 8. Impacto en mantenibilidad

Parche: `genai` en `router.py` acopla el router a un proveedor; cambiar de proveedor obliga a tocar el router (contra P-ARQ-3/4). B (GeminiProvider tras contrato) es mantenible y sustituible.

## 9. Impacto a 10 anos

Parche: dependencia estrategica de un unico proveedor comercial — exactamente el lock-in que D19/D24/P-ARQ-4 prohiben. A/B preservan la independencia.

## 10. Compatibilidad con versiones anteriores

El parche rompe el contrato de abstraccion de proveedores y el baseline local-first; exigiria enmendar D24, ADR-0001 y ADR-0010. La Alternativa A es 100% compatible; la B es compatible si se implementa tras el contrato con enmienda de D24.

## Resolucion

Pendiente del gate extraordinario del CEO. El CTO recomienda A (arreglar Ollama). Si el CEO desea Gemini como opcion, B con enmienda de D24 y `GeminiProvider` tras el contrato. El parche solicitado (genai en router.py, Gemini principal, clave como default) no se aplica.
