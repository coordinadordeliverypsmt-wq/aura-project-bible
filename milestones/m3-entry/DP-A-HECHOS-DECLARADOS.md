# Decision Package A — Hechos declarados del usuario

**Estado:** **DIRECCIÓN APROBADA** (CEO, 2026-08-09) · **Fecha:** 2026-08-09 · **Propone:** APUS-5
**Origen:** defecto reproducido por el CEO en uso real, no por diseño anticipado.
**Fase actual:** evidencia de contrato → `EVIDENCIA-CONTRATO-A-HECHO-DECLARADO.md`.
**Ningún componente funcional se toca hasta la aprobación explícita de esa evidencia.**

---

## 0 · ACTA DEL CEO — las diez reglas que gobiernan este incremento

El CEO aprueba formalmente ampliar `ClaseSenal` en Bible 4.4 §1 con `HECHO_DECLARADO`,
**condicionada** a las diez reglas siguientes. Ninguna es negociable durante la implementación:

1. `HECHO_DECLARADO` es **epistemológicamente distinta** de `PREFERENCIA_DECLARADA`.
2. **No reutilizar** `PREFERENCIA_DECLARADA` para nombres, ocupaciones, proyectos u otros hechos.
3. **No crear una segunda ruta** de persistencia fuera de
   `ConectorConversacion → Senal → AlmacenSenales → memoria semántica → ModeloUsuario`.
4. La procedencia queda **`declarada` desde el primer registro**.
5. Conserva compatibilidad con **refutación y borrado**.
6. La ampliación queda **documentada formalmente** en Bible 4.4 §1 y en los contratos afectados.
7. Alcance limitado a: **nombre · ocupación · proyecto · preferencia**.
8. Las pruebas demuestran que el dato **termina realmente en el Modelo de Usuario** y que la
   recuperación posterior se hace **desde allí**.
9. Existen **pruebas negativas** que demuestran que el sistema no puede «pasar» por simple recall
   episódico o coincidencia léxica.
10. Cubierto por el **Quality Gate** y por el **arnés de mutación** correspondiente.

**Criterio de aceptación fijado por el CEO:** declarar el hecho → persistirlo → verificarlo en el
Modelo de Usuario → reiniciar si corresponde → consultarlo **mediante una intención distinta** →
demostrar que la respuesta procede del Modelo de Usuario y **no** del recall episódico.

Dónde se cumple cada regla: 1-2 en §3 y en `EVIDENCIA…` §1 · 3-5 en `EVIDENCIA…` §2-§3 ·
6 en `EVIDENCIA…` §1-§2 (contrato ejecutable **P1**) · 7 en §4 · 8-9 en `EVIDENCIA…` §4-§5 ·
10 en §6.

---

## 1 · Causa raíz `[EJEC]`

El CEO declaró `Mi nombre es Mauricio` y después `¿Cómo me llamo?` respondió *«No tengo ningún
recuerdo registrado sobre eso»*. Reproducido, con un síntoma que el informe no recogía:
**`¿Qué sabes de mí?` respondía «Todavía no sé nada sobre ti»** pese a dos declaraciones.

La cadena se rompe en **un punto**: `conectores/conversacion.py`, `_clasificar`. Reconoce tres
clases y las tres exigen marcadores de preferencia (`prefiero`, `me gusta`, `suelo`, `odio`…).
`Mi nombre es Mauricio` no contiene ninguno → devuelve `None` → no hay señal → nada llega a memoria
semántica.

**Control ejecutado:** `Prefiero trabajar de noche` → `¿Qué sabes de mí?` → *«Esto es lo que sé de
ti:»*. Con marcador funciona, sin marcador no. **La cadena está sana; le falta una regla.**

La recuperación es consecuencia, no causa: `Cómo me llamo` no comparte ni un término léxico con
`Mi nombre es Mauricio` → 0 hits → ADR-0014 declara la ausencia, correctamente. En cambio
`mi trabajo` sí solapa con `Trabajo en logística`, y por eso **esa sí parece funcionar**. Es una
coincidencia léxica, no conocimiento: la trampa que el criterio de aceptación del CEO obliga a matar.

---

## 2 · Lo que NO se construye

El encargo pedía *«implementar una capa explícita de conocimiento persistente»*. **Ya existe y está
cableada**, verificado por ejecución:

```
ConectorConversacion → Senal → AlmacenSenales → memoria semantica/procedimental → ModeloUsuario
```

con procedencia (`declarada` / `observada`), refutación y borrado. La taxonomía episódica /
semántica / procedimental también existe. Construir una capa nueva chocaría con la regla dura del
proyecto: prohibido crear un componente sin demostrar que no existe equivalente.

---

## 3 · DECISIÓN ARQUITECTÓNICA QUE REQUIERE APROBACIÓN DEL CEO

`ClaseSenal` no es una lista libre. Su docstring dice *«las seis señales de 4.4 §1»*, y la **Bible
4.4 §1** las fija:

> **Explícitas:** correcciones, preferencias declaradas, feedback directo.
> **Implícitas:** patrones de uso, temas recurrentes, aceptación o rechazo de sugerencias.

**«Me llamo Mauricio» no es ninguna de las seis.** No es una preferencia, ni una corrección, ni
feedback. Hacen falta **dos decisiones del CEO**:

| Opción | Qué implica | Coste |
|---|---|---|
| **A1 — añadir `HECHO_DECLARADO` como cuarta explícita** *(recomendada)* | **Amplía la taxonomía de Bible 4.4 §1.** Requiere acta | Toca un contrato estratégico |
| A2 — reutilizar `PREFERENCIA_DECLARADA` | No toca la Bible | **Etiqueta mal el dato de forma permanente** |
| A3 — escribir en memoria semántica fuera de la cadena de señales | No toca la Bible | Crea una segunda ruta: viola INV-7 y ALERTA-005 |

**Por qué se recomienda A1 y por qué A2 es peor de lo que parece:** el propio `senales.py` advierte
que *«el origen epistémico viaja con el dato desde el primer registro: si no se distinguieran desde
el principio, separarlos después exigiría migrar el historial acumulado»*. Registrar un nombre como
«preferencia» es precisamente el error que ese aviso anticipa, y se paga migrando datos reales del
CEO más adelante. A3 es la peor: reintroduce la ruta alternativa que ALERTA-005 existe para prohibir.

**Sin acta del CEO sobre este punto, el incremento no empieza.**

---

## 4 · Qué se construye (si A1 se aprueba)

1. **Una clase de señal**, `HECHO_DECLARADO`, con su familia explícita.
2. **Patrones conservadores y auditables** en `_clasificar`, con la misma disciplina que ya rige el
   fichero: marcador **Y** sujeto en primera persona, y la guarda `_habla_de_tercero` intacta.
   Semilla: `me llamo` · `mi nombre es` · `trabajo en` · `trabajo de` · `soy` + oficio ·
   `estoy trabajando en un proyecto llamado` · `recuerda que` + declaración.
3. **Una superficie determinista de recuperación por intención**, insertada donde ya vive la
   soberanía del Modelo de Usuario —**antes** de la puerta de memoria—: `¿cómo me llamo?` ·
   `¿qué trabajo hago?` · `¿en qué proyecto trabajo?` · `¿qué prefiero?`.

**Nada de esto llama al LLM** (ADR-0014 §2). Nada infiere: si el usuario no lo declaró, no se
registra (restricción 1 de M3.0, *capturar no implica inferir*).

---

## 5 · La regla explícita de promoción (Objetivo 4 del CEO)

Una frase se promueve a conocimiento persistente **sólo si** cumple las tres:

1. **Marcador explícito** de declaración sobre uno mismo, de la lista cerrada.
2. **Sujeto = el usuario.** `_habla_de_tercero` sigue vetando («mi hermana se llama Ana»).
3. **Atributo estable.** `Hoy estoy cansado` **NO** se promueve: no hay marcador de declaración de
   identidad y el adverbio temporal lo marca como estado, no atributo. Queda como episódica, que es
   exactamente lo que el CEO pidió.

**Testeable frase a frase**, como exige el contrato. Compatible con refutación y borrado ya
existentes: un hecho declarado se refuta y se borra por las mismas rutas que hoy.

---

## 6 · Garantías y verificación

| Regla | Cómo se cumple |
|---|---|
| **ADR-0014** | La puerta de memoria **no se toca**. Prueba obligatoria: las **24 negativas** siguen `provider == "core"` con **cero** llamadas al LLM |
| **INV-9** | Sin declaración, no hay hecho. `¿Cómo me llamo?` con usuario nuevo declara que no lo sabe; **no inventa** |
| **INV-7 / ALERTA-005** | Una sola ruta: la cadena existente. Sin segundo camino de escritura |
| **Sin perfiles de terceros** | `_habla_de_tercero` intacta (ALERTA-002) |
| **No contaminación** | `Hoy estoy cansado` → episódica, nunca atributo permanente |
| **Persistencia** | Prueba de **reinicio**: proceso nuevo, misma `AURA_DATOS`, el hecho sigue ahí |

**La prueba que mata la trampa del CEO:** para `¿Qué recuerdas de mi trabajo?` no basta con que la
respuesta contenga «logística» —el recall episódico ya lo consigue por solape léxico—. La prueba debe
**vaciar o desactivar la memoria episódica** y exigir que la respuesta siga saliendo, o afirmar
`provider == "core"` con el texto exacto del Modelo de Usuario. Sin eso, la prueba es decorativa y
pasaría hoy, sin incremento.

**Mutantes obligatorios:** (a) el detector no reconoce la declaración; (b) se promueve cualquier
frase (`Hoy estoy cansado` pasa a permanente); (c) se captura la declaración de un tercero; (d) la
recuperación por intención responde desde el recall episódico en vez del Modelo de Usuario —**este
es el irrenunciable**, porque es el defecto que hoy hace parecer que funciona—; (e) el hecho no
sobrevive al reinicio.

---

## 7 · Lo que este DP NO hace

- **No infiere.** Sigue siendo M3.0: capturar no es deducir.
- **No cubre todas las formas de decir un nombre.** Lista cerrada; crece con el uso real.
- **No toca la redacción de las 17 capacidades** — aparcado por el CEO.
- **No arregla** la deuda de ADR-0014 con corpus sembrado (ver `DEUDA-ADR0014-MEMORIA-VACIA.md`).

---

## 8 · Retorno sobre Tokens

Una clase de señal y una superficie frente a una capa de memoria nueva. **Reutiliza la cadena que ya
existe**, de modo que refutación, borrado, auditoría y aislamiento por usuario vienen gratis y no hay
un segundo modelo que mantener sincronizado. Y da a AURORA el primer dato real sobre su CEO, que es
la materia prima de todo lo que venga después.

---

## 9 · Qué se pide aprobar

1. **A1: `HECHO_DECLARADO` como cuarta señal explícita**, ampliando Bible 4.4 §1. **Requiere acta.**
2. La lista de patrones del §4.2 y la regla de promoción del §5.
3. Las cuatro consultas deterministas del §4.3.
4. El protocolo completo: RED → GREEN → MUTACIÓN → auditoría independiente → integración.
