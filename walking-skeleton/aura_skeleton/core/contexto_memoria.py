"""Memory Context Builder (D-AMP-2) — filtra la MEMORIA RECUPERADA antes de enseñársela al modelo.

Decisión: `decisiones/2026-10-11-D-AMP-2-aprobacion-construccion.md`, sobre `AMP-AURA-DECISIONES.md`
§D-AMP-2. Función PURA: recibe los recuerdos ya filtrados por vigencia (`_da_por_cierto`, aplicado en
el orquestador) y devuelve el texto del bloque `[contexto memoria: ...]`. No escribe, no toca el store,
no llama al motor (respeta G-1); transmite el valor que el Core estableció, literal (respeta ADR-0014).

QUÉ EXCLUYE HOY, y por qué:
  - TERCEROS (siempre): un eco episódico «usuario dijo: mi abuela es enfermera» se escribe aunque la
    captura rechace el hecho semántico, y reentra por `recall`; el filtro de vigencia no lo alcanza —es
    un registro válido de lo que se dijo—. Se detecta con la MISMA regla léxica que gobierna la captura
    (`core/sujeto.habla_de_tercero`): lo que no se guarda como hecho tampoco se enseña como recuerdo.
    Cierra el defecto medido en el DP por la vía de la memoria recuperada.

LÍMITES DECLARADOS (esto NO es una garantía de privacidad cerrada; revisión de seguridad 2026-10-11):
  - Esta función cubre SOLO la memoria recuperada por `recall`. El **buffer de diálogo** (`recent`, en
    `orchestrator.py`) es otra vía hacia el mismo prompt y NO pasa por aquí: un tercero mencionado en la
    conversación EN CURSO reentra durante la ventana de diálogo. Es continuidad conversacional (el
    usuario puede hablar de terceros en su turno) y su comportamiento es el previo al incremento; cubrir
    el buffer con este filtro rompería esa continuidad y queda fuera del alcance del DP (que sitúa el
    Builder «entre recall y el prompt»). Una política para el buffer requeriría decisión del CEO.
  - La detección de terceros es LÉXICA y la lista de `core/sujeto.TERCERO` es cerrada (misma cobertura
    que la captura): fraseos no listados (nombres propios sin relación, «mi colega», «un amigo mío»)
    son falsos negativos. Es una protección incremental, no exhaustiva.
  - El filtrado es por REGISTRO COMPLETO: incluye o excluye el `content` entero, sin redacción parcial
    de la cláusula que menciona al tercero.
  - PERTINENCIA y SENSIBILIDAD: el contrato del DP las lista, pero NO hay criterio definido en
    DP/Bible/ADR ni campo de scope/sensibilidad en el recuerdo (`modules/memory.py`). Quedan como punto
    de extensión NO implementado: exigirían decisión del CEO y ampliar el modelo de memoria.
  - PROPUESTAS: sin vector medido. No se escriben al store, así que no llegan por `recall` (probado en
    `tests/unit/test_contaminacion_propuesta.py`); el buffer ya las reentra etiquetadas vía
    `core/estatus.py`. No se filtra lo que no puede llegar por esta vía.
"""

from __future__ import annotations

from .sujeto import habla_de_tercero, normalizar

_SIN_RECUERDOS = "(sin recuerdos relevantes)"


def _texto(entrada: dict) -> str:
    """El contenido del recuerdo como texto. Una sola lectura de `content`, usada por el filtro y por
    la salida, para que ambas vean lo mismo (el invariante de `modules/memory.py` es que `content` es
    str; `str(...)` solo protege ante un hit malformado, que trataríamos como texto, nunca como None)."""
    return str(entrada.get("content", ""))


def construir_contexto(vigentes: list[dict]) -> str:
    """Texto del bloque `[contexto memoria: ...]` a partir de los recuerdos vigentes.

    `vigentes` ya viene filtrado por vigencia en el orquestador (reutiliza `_da_por_cierto`, no se
    reescribe aquí). Esta función solo decide QUÉ de lo vigente se muestra: excluye los recuerdos cuyo
    contenido habla de un tercero. Si no queda ninguno mostrable, devuelve la misma marca de ausencia
    que ensamblaba el orquestador antes de extraer esta frontera.
    """
    mostrables = [m for m in (_texto(h) for h in vigentes) if not habla_de_tercero(normalizar(m))]
    return " | ".join(mostrables) if mostrables else _SIN_RECUERDOS
