"""RED de `D-CP-4` = **C** (A + B) — decisión del CEO, 2026-08-23.

Las cinco garantías que el CEO ordenó demostrar:

1. un criterio basado en shell u orden libre del SO **se rechaza**;
2. una capacidad **no registrada** se rechaza;
3. una capacidad **registrada** puede referenciarse;
4. un criterio dentro de `cuerpo` **no puede convertirse en autoridad**;
5. el **Control Plane** es el único origen aceptado del criterio.

**Parte A** (catálogo) = garantías 1-3 · **Parte B** (origen) = garantías 4-5.

**Fuera de alcance, y por eso no se prueba aquí:** los *argumentos* de la capacidad (`R-1`,
delegado a `D-CP-6` por el punto 5 de la decisión), el esquema cerrado (`D-CP-5`) y el cableado de
B4. `CLAUDE.md` no se toca; el catálogo no se amplía y no se inventa ninguna capacidad: las que
aparecen abajo o existen ya en producción, o son deliberadamente inexistentes.
"""

from __future__ import annotations

import importlib

import pytest

# Existe en el catálogo real de producción (`permissions.py`), es verde y de solo lectura.
CAPACIDAD_REGISTRADA = "ejecutar_pruebas"

# No existe, y no se crea: sirve para probar el rechazo.
CAPACIDAD_INEXISTENTE = "desplegar_a_produccion_sin_permiso"

# Órdenes libres del SO. Ninguna es una capacidad; todas deben rechazarse.
ORDENES_DE_SHELL = (
    "python3 -m pytest tests/unit -q",
    "ruff check .",
    "python3 -c 'import os; os.system(\"id\")'",
    "rm -rf /",
    "./quality-gate.sh",
)


def _canal():
    return importlib.import_module("communication_plane")


# ======================================================== PARTE A · catálogo cerrado --


@pytest.mark.parametrize("orden", ORDENES_DE_SHELL)
def test_A1_una_orden_libre_del_sistema_operativo_no_es_un_criterio_valido(orden):
    """`CLAUDE.md`: *«AURORA nunca ejecuta instrucciones arbitrarias del SO»*. La regla 2 de
    `§14.bis`, ya modificada, dice lo mismo: se nombra el resultado, no la herramienta."""
    assert _canal().es_automatizable({"criterio": orden}) is False, (
        f"{orden!r} es una orden del SO y fue aceptada como criterio")


def test_A2_una_capacidad_que_no_esta_en_el_catalogo_se_rechaza():
    """Nombrar algo con forma de capacidad no basta: tiene que **estar registrada**. Si bastara la
    forma, inventar un nombre plausible sería suficiente para pasar el filtro."""
    assert _canal().es_automatizable({"criterio": CAPACIDAD_INEXISTENTE}) is False


def test_A3_una_capacidad_registrada_del_catalogo_si_es_un_criterio_valido():
    """El caso de control de A1 y A2. Sin esto, una función que devolviera siempre `False` pasaría
    las dos anteriores y no serviría para nada."""
    assert _canal().es_automatizable({"criterio": CAPACIDAD_REGISTRADA}) is True


def test_A4_el_catalogo_procede_del_registro_real_y_no_de_una_copia_del_canal():
    """**El criterio se valida contra el catálogo del Motor Único, no contra una lista propia.**

    Dos fuentes de verdad para lo mismo es como nace un «declarado != real»: el día que producción
    registre o retire una capacidad, una copia en el canal seguiría contestando lo de ayer.
    """
    canal = _canal()
    catalogo = canal.catalogo_de_capacidades()
    assert CAPACIDAD_REGISTRADA in catalogo
    assert CAPACIDAD_INEXISTENTE not in catalogo
    # Las cuatro que `MAPA-DECISION-CP-4-Y-5 §1.A` cita como ya verdes en el registro real.
    for esperada in ("ejecutar_pruebas", "verificar_calidad", "auditar_garantias",
                     "diagnosticar_estado"):
        assert esperada in catalogo, f"{esperada} no llego desde el catalogo real"


def test_A5_sin_criterio_no_hay_automatizacion():
    """`§14.bis` regla 4, intacta: si no es expresable, la tarea no es AUTO."""
    canal = _canal()
    assert canal.es_automatizable({"criterio": None}) is False
    assert canal.es_automatizable({}) is False


# ============================================================ PARTE B · origen único --


def test_B1_un_criterio_dentro_del_cuerpo_se_rechaza_al_publicar(tmp_path):
    """`DP-CP §10`: el criterio procede del Control Plane, nunca del canal. Si viajara en `cuerpo`,
    un mensaje entre pares conseguiría fijar qué cuenta como «terminado»."""
    canal = _canal()
    c = canal.abrir(tmp_path)
    with pytest.raises(canal.MensajeInvalido):
        c.publicar(tipo="TASK", de="codex", para="claude",
                   cuerpo={"objetivo": "x", "criterio": CAPACIDAD_REGISTRADA})


def test_B2_ni_siquiera_anidado_a_profundidad(tmp_path):
    """Si solo se mirase el primer nivel, `datos -> meta -> criterio` entraría igual. Es el mismo
    defecto que ya se pagó con la lista negra superficial."""
    canal = _canal()
    c = canal.abrir(tmp_path)
    with pytest.raises(canal.MensajeInvalido):
        c.publicar(tipo="TASK", de="codex", para="claude",
                   cuerpo={"datos": {"meta": {"criterio": CAPACIDAD_REGISTRADA}}})


def test_B3_el_control_plane_es_el_unico_origen_declarado_del_criterio():
    """Declaración comprobable de la dirección de la dependencia, no una nota en un documento."""
    fuentes = _canal().fuentes_de_criterio()
    assert fuentes == ("control_plane",)
    assert "cuerpo" not in fuentes and "mensaje" not in fuentes


def test_B4_un_criterio_colado_en_un_mensaje_no_altera_lo_que_el_control_plane_permite(tmp_path):
    """**La garantía que une A y B con la barrera de B4.** Aunque alguien lograse hacer llegar un
    criterio por el canal, el veredicto lo sigue dando el Control Plane. Es el caso de control de
    B1: sin esto, rechazar el campo parecería suficiente, y no lo es."""
    canal = _canal()
    estado = {"tareas": {"T-1": {"estado": "DECISION_REQUIRED"}}}
    assert canal.permitido("T-1", estado=estado) is False
    assert canal.permitido("T-1", estado=estado,
                           mensaje={"tipo": "TASK",
                                    "cuerpo": {"criterio": CAPACIDAD_REGISTRADA}}) is False
