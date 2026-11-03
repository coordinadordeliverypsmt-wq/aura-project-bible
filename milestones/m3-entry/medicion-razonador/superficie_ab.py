"""Superficie informativa corregida (I-1) y esquema del brazo B.

**El defecto I-1, medido y no supuesto.** `_catalogo_para_prompt()` del producto solo anexa el
esquema de argumentos a las acciones presentes en `ESPECIFICACIONES`. Hay 33 acciones en `CATALOGO`
y 10 en `ESPECIFICACIONES`, y `proponer_cambio` **no esta entre ellas**: el modelo la ve desnuda. Es
decir, en toda la campana historica **nunca se le dijeron los nombres de los campos que se le
exigian**. Que respondiera con `ruta` y `patron` —los dos nombres mas frecuentes del catalogo que si
vio— deja de ser invencion y pasa a ser la conducta esperable.

El brazo A corrige esa superficie. **En el arnes, no en el producto**: `providers_real.py` queda
intacto por orden del CEO. Este modulo NO representa el producto corregido; representa la superficie
que el producto *deberia* ofrecer.

**Procedencia canonica, no copia.** Los nombres de los campos se importan de
`_CAMPOS_DE_EJECUCION` (`aura_skeleton/core/estado_operativo.py`), y las acciones de `CATALOGO`.
Escribirlos a mano aqui crearia una cuarta representacion del contrato que podria divergir de las
otras tres — exactamente ALERTA-005. `test_protocolo_ab` comprueba el **texto** de este fichero para
impedirlo, no solo el valor resultante.

**El prompt es identico en A y en B.** La unica variable del experimento es el campo `format` de la
peticion HTTP, que no vive aqui. `construir_prompt` acepta el brazo unicamente para dejar constancia
de que se le pidio, y devuelve los mismos bytes en ambos casos.
"""

from __future__ import annotations

import hashlib
import pathlib
import sys

_RAIZ = pathlib.Path(__file__).resolve().parents[3]
_PRODUCTO = _RAIZ / "walking-skeleton"
if str(_PRODUCTO) not in sys.path:
    sys.path.insert(0, str(_PRODUCTO))

# Importacion de SOLO LECTURA de constantes. No se ejecuta el producto, no se compone, no se
# despacha ninguna accion: se leen tres estructuras de datos para derivar la superficie.
from aura_skeleton.core.estado_operativo import _CAMPOS_DE_EJECUCION  # noqa: E402
from aura_skeleton.core.operaciones import ESPECIFICACIONES  # noqa: E402
from aura_skeleton.core.permissions import CATALOGO  # noqa: E402

CAMPOS_DE_EJECUCION: tuple[str, ...] = tuple(_CAMPOS_DE_EJECUCION)

ACCION_BAJO_PRUEBA = "proponer_cambio"

BRAZOS = ("A", "B")


def catalogo_para_prompt() -> str:
    """Como `providers_real._catalogo_para_prompt()`, mas la correccion I-1.

    Se anade el esquema de argumentos de la unica accion bajo prueba. NO se declaran las otras 23
    acciones desnudas: hacerlo engordaria el prompt e introduciria una segunda variable en un
    experimento que solo admite una.
    """
    lineas = []
    for accion, meta in CATALOGO.items():
        spec = ESPECIFICACIONES.get(accion)
        args = spec["args"] if spec and spec["args"] else None
        if accion == ACCION_BAJO_PRUEBA:
            args = CAMPOS_DE_EJECUCION  # <- la correccion I-1, y su unica diferencia con el producto
        sufijo = f" args: {{{', '.join(args)}}}" if args else ""
        lineas.append(f"- {accion} ({meta['lista']}){sufijo}")
    return "\n".join(lineas)


def construir_prompt(caso, brazo: str) -> str:
    """Mismos bytes para A y para B. Verificado por `test_c7`."""
    if brazo not in BRAZOS:
        raise ValueError(f"brazo desconocido: {brazo!r}")
    return (
        "Una garantia declarada en un fichero de mutaciones referencia un patron que ya no aparece "
        "en el fichero objetivo.\n\n"
        f"Garantia declarada:\n{caso.GARANTIA}\n\n"
        f"Patron declarado que ya no aparece:\n{caso.PATRON_OBSOLETO}\n\n"
        f"Fichero objetivo ({caso.NOMBRE_FICHERO}):\n{caso.CONTENIDO}\n"
        "Acciones disponibles:\n"
        f"{catalogo_para_prompt()}\n\n"
        "Responde con un objeto JSON con las claves intent, action, args y say."
    )


def sha_prompt(caso, brazo: str) -> str:
    return hashlib.sha256(construir_prompt(caso, brazo).encode("utf-8")).hexdigest()


# Parametros de generacion, IDENTICOS en A y en B y registrados en cada evidencia.
#
# Sin fijarlos, Ollama muestrea con temperatura ~0,8 y semilla aleatoria: con n=3 y n=1, cualquier
# diferencia entre los brazos seria indistinguible del ruido, y el experimento no mediria el efecto
# de `format` sino la varianza del muestreo. Lo detecto la revision adversarial.
OPCIONES_GENERACION: dict = {"seed": 20260816, "temperature": 0.0, "top_p": 1.0, "top_k": 1}


def esquema_b() -> dict:
    """Esquema del brazo B. Restringe el CONTRATO; jamas la RESPUESTA.

    **`action` NO lleva `enum`.** Lo llevaba, y el CEO lo retiro el 2026-08-16 por una razon de
    interpretacion causal: un `enum` de las 33 acciones mezcla dos restricciones distintas dentro de
    la misma variable — la forma de la salida y el espacio de acciones permitido—. Si B saliera
    mejor, no sabriamos cuanto viene de restringir la forma y cuanto de impedir acciones invalidas.
    Son dos preguntas, y este experimento responde una:

        ¿restringir la FORMA de la salida ayuda a formular correctamente los argumentos?

    La otra pregunta pertenece a un hipotetico brazo C (= B + enum), que **no forma parte de este
    experimento** y no se implementa.

    Los campos de ejecucion se declaran como cadenas libres y **ninguno es obligatorio**. Enumerar
    las lineas candidatas convertiria el experimento en una loteria y el acierto lo produciria la
    gramatica, no el razonamiento. Y exigirlos le quitaria al modelo la posibilidad de callar: hoy
    `qwen2.5:0.5b` dejo un campo vacio en vez de inventarlo, y ese es el comportamiento honesto que
    un `required` convertiria en fabricacion. INV-9.
    """
    campos = {campo: {"type": "string"} for campo in CAMPOS_DE_EJECUCION}
    return {
        "type": "object",
        "properties": {
            "intent": {"type": "string"},
            "action": {"type": "string"},
            "args": {"type": "object", "properties": campos},
            "say": {"type": "string"},
        },
        "required": ["intent", "action", "say"],
    }
