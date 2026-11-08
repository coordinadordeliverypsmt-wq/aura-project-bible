"""Una tarea no puede ser una autorización huérfana (CEO, 2026-09-20).

EL DEFECTO, MEDIDO. `formacion.formacion()` deriva cada oportunidad de un contrato concreto y guarda
su identidad en `detalle["numero"]`. `planificador.a_tarea()` construye la tarea copiando `fichero`,
`operacion`, `buscar`, `sustituir`… y **no copia esa identidad**. A partir de ahí la tarea circula
sola: ni `review.ejecutar_bajo_review` ni `autoconstruccion.ejecutar` comprueban que se corresponda
con ningún contrato. Ambos verifican zona, intocables, alcance del verbo y unicidad del patrón —
todo correcto, y nada de eso ata la tarea a la autorización que la produjo.

POR QUÉ IMPORTA AUNQUE HOY NADIE PUEDA EXPLOTARLO. El anillo no redacta contratos y `milestones/`
está fuera de su zona, así que hoy los textos que viajan en la tarea vienen necesariamente de un
contrato real. Pero esa garantía la da el perímetro, no la tarea: si algún día una oportunidad
entrara por otra fuente, o si los textos se alteraran entre planificar y ejecutar, **nada lo
notaría**. Llevar la identidad del contrato convierte una propiedad circunstancial en una
comprobable.

QUÉ FIJA ESTA PRUEBA, Y QUÉ NO. Fija que la identidad **viaja**. No fija todavía que alguien la
**verifique** antes de escribir: `contrato.corresponde_tarea_a_contrato()` ya existe para eso, pero
enchufarla en el circuito de ejecución toca la puerta de escritura y es un acto aparte. Aquí se
cierra la mitad que no necesita autoridad nueva: transportar un dato que ya existía y se tiraba.
"""

from __future__ import annotations

import pathlib

import descubrimiento as des
import planificador as plan

CONTRATO = "etiqueta-observatorio-efecto"

PLANO = pathlib.Path(__file__).resolve().parent
#: Procedencia REAL. `Oportunidad.__post_init__` exige que la fuente se pueda ir a mirar: *«una
#: procedencia que no se puede ir a mirar es indistinguible de una inventada»*. Con una ruta
#: inventada estas pruebas fallarían por construir mal el fixture, no por el vacío que persiguen —
#: y una prueba que falla por el motivo equivocado no prueba nada.
FUENTE = str(PLANO.parent.parent / "milestones/m3-entry/capacidades/etiqueta-observatorio-efecto.toml") + ":1"
DESTINO = str(PLANO / "observatorio.py")


def _oportunidad_de_contrato(**cambios) -> des.Oportunidad:
    """Una oportunidad con la forma exacta que produce `formacion.formacion()` para un contrato."""
    base = dict(
        id="OP-prueba12345",
        fuente=FUENTE,
        justificacion="hacer inequivoca la etiqueta",
        alcance=DESTINO,
        accion="implementar_incremento_especificado",
        autoridad="DR-E",
        criterio_de_finalizacion={"capacidad": "ejecutar_pruebas"},
        evidencia_requerida={"tipo": "fichero_existe", "ruta": DESTINO},
        riesgo="bajo",
        estado=des.OPORTUNIDAD_REAL,
        detalle={"numero": CONTRATO, "nombre": "Etiqueta inequivoca",
                 "estado_en_el_plan": "con contrato", "contrato": "IMPLEMENTABLE",
                 "operacion": "sustituir_texto",
                 "buscar": '"Trabajo ejecutado (total)"',
                 "sustituir": '"Trabajo ejecutado con efecto acreditado (total)"'},
    )
    base.update(cambios)
    return des.Oportunidad(**base)


def test_la_tarea_lleva_la_identidad_del_contrato_que_la_autoriza():
    """RED el 2026-09-20: `a_tarea` perdía `detalle["numero"]` y la tarea quedaba huérfana."""
    tarea = plan.a_tarea(_oportunidad_de_contrato())

    assert tarea is not None, "una OPORTUNIDAD_REAL tiene que poder planificarse"
    assert tarea.get("contrato") == CONTRATO, (
        "la tarea no dice de que contrato viene: nadie aguas abajo puede comprobar la correspondencia"
    )


def test_una_tarea_sin_contrato_lo_declara_VACIO_no_lo_inventa():
    """El código muerto no nace de un contrato. La ausencia se declara; no se rellena con un placeholder.

    Un valor inventado sería peor que ninguno: aguas abajo parecería una autorización real.
    """
    op = _oportunidad_de_contrato(
        accion="eliminar_codigo_muerto",
        detalle={"simbolo": "_funcion_muerta", "forma": "funcion"},   # sin `numero`
    )

    tarea = plan.a_tarea(op)

    assert tarea is not None
    assert tarea.get("contrato") == "", "una tarea sin contrato no puede declarar uno"


def test_la_identidad_viaja_SIN_alterar_lo_que_ya_viajaba():
    """Caso de control: añadir un campo no puede cambiar los que el ejecutor ya consume.

    Si `fichero`, `operacion`, `buscar` o `sustituir` cambiaran, el incremento autorizado dejaría de
    aplicarse — y la prueba pasaría igual mirando solo el campo nuevo.
    """
    op = _oportunidad_de_contrato()

    tarea = plan.a_tarea(op)

    assert tarea["fichero"] == op.alcance
    assert tarea["accion"] == "implementar_incremento_especificado"
    assert tarea["operacion"] == "sustituir_texto"
    assert tarea["buscar"] == '"Trabajo ejecutado (total)"'
    assert tarea["sustituir"] == '"Trabajo ejecutado con efecto acreditado (total)"'


def test_lo_que_no_es_OPORTUNIDAD_REAL_sigue_sin_producir_tarea():
    """La puerta anterior no se toca: planificar algo bloqueado sería una ruta alternativa."""
    op = _oportunidad_de_contrato(estado=des.DECISION_REQUIRED)

    assert plan.a_tarea(op) is None
