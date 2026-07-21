---
adr: 17
titulo: "Autoridad sobre preferencias inferidas: el usuario tiene la última palabra"
estado: accepted
fecha: 2026-07-21
decide: "CEO (P5, plan de M3.0)"
propone: "CTO"
supersede: null
relacionado: "ADR-0014 (Core única fuente de verdad), ADR-0015 (proveedores de contexto), ADR-0001 (local-first), 4.4 (aprendizaje), 4.1 §5 (soberanía), D6 (jamás aduladora)"
---

# ADR-0017 — Autoridad sobre preferencias inferidas

## El problema

ADR-0014 establece que **el Core es la única autoridad sobre los hechos del sistema** y que el LLM
nunca lo es. Resuelve dos categorías:

| Categoría | Autoridad |
|---|---|
| Hecho registrado ("el usuario dijo X el día D") | El Core |
| Invención del modelo | Nadie: se prohíbe |

Una **preferencia inferida** no encaja en ninguna. *"Sueles apagar las luces sobre las 23:00"* no es
un hecho que nadie declarara, ni una invención sin fundamento: es una **conclusión del sistema sobre
una persona**, derivada de observaciones reales.

La pregunta que este ADR responde: **¿con qué autoridad afirma AURA "sé que prefieres X" cuando nadie
se lo dijo?**

## Decisión

### 1. Una inferencia es una hipótesis, nunca un hecho

El Core mantiene la distinción en el dato mismo, no en la interfaz. Toda entrada del modelo del
usuario lleva `origen`:

| `origen` | Significado | Autoridad |
|---|---|---|
| `declarada` | El usuario lo dijo | **Alta.** Es un hecho registrado (ADR-0014) |
| `observada` | Derivada de acciones registradas en el audit log | Media. El hecho es la acción; la agregación es del Core |
| `inferida` | Conclusión del sistema | **Hipótesis.** Nunca se presenta como hecho |

Ya se persiste desde M3.0, antes de que exista inferencia alguna, precisamente para que el historial
no necesite migrarse después.

### 2. El usuario gana siempre

Cuando una preferencia declarada contradice una inferida, **prevalece la declarada, sin excepción y
sin ponderación**. La inferida se marca como refutada y no vuelve a proponerse en los mismos
términos.

No es una regla de producto amable: es la aplicación de ADR-0014. Un hecho declarado por el usuario
es un hecho del sistema; una inferencia es una conjetura sobre él. Que una conjetura pudiera vencer a
una declaración invertiría la línea de autoridad que sostiene todo el diseño.

### 3. AURA debe poder decir por qué

Toda inferencia conserva **procedencia**: qué observaciones la sustentan y de qué fuente vinieron.
Una inferencia que no puede explicarse **no puede usarse** para anticipar.

El motivo es práctico además de ético: cuando M3.3 empiece a proponer acciones y una resulte
molesta, la única forma de corregir la causa —en lugar de silenciar el síntoma— es saber en qué se
basaba.

### 4. Corregible, exportable y borrable

El modelo del usuario es **dato del usuario** (4.4 §2, 4.1 §5, ADR-0001). Debe poder:

- **verse** — qué cree AURA que sabe;
- **corregirse** — una corrección prevalece sobre cualquier inferencia;
- **exportarse** — en formato legible, sin dependencia de AURA;
- **borrarse** — total o selectivamente, sin degradar el resto del sistema.

Estas cuatro capacidades son **deterministas** y no dependen de que exista inferencia: se construyen
en M3.2a, **antes** de que AURA empiece a inferir.

### 5. Nunca aduladora (D6)

Aprender preferencias no autoriza a complacer. Si el usuario prefiere una respuesta y los hechos
dicen otra cosa, **prevalecen los hechos**. El modelo del usuario personaliza *cómo* se dicen las
cosas, nunca *si son verdad*.

## Consecuencia de orden: corregibilidad antes que inferencia

Se construye primero la corrección y después la inferencia. En el orden inverso existiría una
ventana —de duración indefinida, porque depende de cuándo haya hardware y datos— en la que AURA
acumularía conclusiones sobre una persona que esa persona no podría rectificar.

## Impacto (acta D11 — obligatorio)

| Dimensión | Impacto |
|---|---|
| **Seguridad** | Positivo: ninguna inferencia puede desencadenar acción sin pasar por el orden canónico de 5.3 §3.1 |
| **Privacidad** | **Positivo alto**: el usuario ve, corrige, exporta y borra lo que el sistema cree saber de él |
| **Modularidad** | Neutro: `origen` ya viaja en el dato desde M3.0 |
| **Costo** | Nulo |
| **Rendimiento** | Despreciable |
| **Mantenibilidad** | Positivo: la procedencia hace depurable un comportamiento probabilístico |
| **Reversibilidad** | Máxima: toda inferencia es refutable por definición |

## Riesgos aceptados

- **Guardar procedencia aumenta lo que se almacena sobre el usuario.** Mitigación: es dato propio,
  local (ADR-0001) y borrable. El riesgo de no guardarla —inferencias inexplicables e incorregibles—
  es mayor.
- **Una inferencia refutada podría volver a deducirse** de las mismas observaciones. Mitigación: la
  refutación se persiste como preferencia declarada, que siempre prevalece.
