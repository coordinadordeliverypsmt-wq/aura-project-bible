"""OBJETIVO 4.1 — hacer exigible `perimetro.fuera_de_alcance`.

**Hecho medido antes de escribir esta prueba:** `contrato.evaluar()` nunca lee
`perimetro.fuera_de_alcance` — cero apariciones de esa cadena en `contrato.py`. El campo existe en
los TOML reales como prosa (`etiqueta-observatorio-efecto.toml`, `sexta-fuente-estancamiento.toml`) y
ningun codigo lo aplicaba. Estas pruebas fijan que un contrato que se contradice a si mismo —declara
un fichero MODIFICABLE que el propio contrato marca FUERA DE ALCANCE— queda BLOQUEADA, y no
IMPLEMENTABLE como ocurria antes de este incremento.

**Decision sobre la prosa (documentada aqui porque la prueba la ejercita):** `fuera_de_alcance` no es
siempre una lista de rutas — los contratos reales meten prosa entera («review.py, contrato.py,
autoconstruccion.py y el resto del mecanismo de autoridad»). Tratar la entrada entera como una ruta
haria que TODA prosa fallara a resolver y el campo seguiria sin aplicarse (falso negativo silencioso).
Tratar cualquier palabra de la prosa como ruta produciria bloqueos por coincidencias de letras
sueltas (falso positivo). La resolucion elegida:

  1. Si la entrada ES una ruta (absoluta, relativa al repo o relativa a `control-plane/`, con o sin
     `..`, symlink incluido), se compara por RUTA REAL RESUELTA contra cada `modificable` — nunca por
     substring. Dos ficheros con nombres parecidos en directorios distintos NO se confunden.
  2. Si la entrada es prosa, se extraen de ella los TOKENS con pinta de fichero (terminan en `/` →
     segmento de directorio comparado por PARTE COMPLETA de la ruta real, o llevan una extension
     reconocible). Un token de directorio bloquea si ese segmento aparece en la ruta real; un token de
     fichero bare (sin `/`) solo bloquea si es uno de los nombres del mecanismo de autoridad ya
     reconocidos en el codigo (`orquestador._INTOCABLES` mas `review.py`, `contrato.py`,
     `autoconstruccion.py`) — el resto de la prosa (`el resto del mecanismo de autoridad`,
     `kill_switch`, `permisos`, `_efecto_real`...) no produce ni falso positivo ni bloqueo silencioso:
     simplemente no es una referencia reconocible a un fichero, y se documenta como limite explicito,
     no como omision.

Fail-closed: ante la duda sobre si una ruta cae dentro de lo declarado fuera de alcance, se BLOQUEA
(ADR-0003)."""

import pathlib

import contrato as ct

PLANO = pathlib.Path(__file__).parent


def _completo(**cambios):
    """Copia minima del fixture de `test_red_f5_evolucion_autonoma.py`, para no depender de otro
    fichero de pruebas ni de su estado (otros agentes lo estan tocando en paralelo)."""
    base = {
        "id": "FIXTURE-FDA", "nombre": "capacidad de prueba fuera_de_alcance", "version": "1",
        "estado": "AUTORIZADA",
        "intencion": "ejercitar fuera_de_alcance sin inventar una capacidad real",
        "entradas": [{"nombre": "fichero", "fuente": str(PLANO / "review.py"), "formato": "py"}],
        "salidas": [{"resultado": "simbolo retirado", "destino": str(PLANO / "review.py")}],
        "regla_de_transformacion": "es_eliminable() decide, quitar_simbolo() ejecuta",
        "fuentes_de_verdad": {"autoridad": [str(PLANO / "autoconstruccion.py")], "referencia": []},
        "perimetro": {"modificables": [str(PLANO / "review.py")], "fuera_de_alcance": []},
        "autoridad": {"nivel": "REVIEW", "acta": "DEC-ORCH-2",
                      "parte_de_aura": "ejecutar", "parte_del_ceo": "autorizar"},
        "ejecutor": {"verbo": "eliminar_codigo_muerto"},
        "efectos": {"permitidos": ["retirar un simbolo"], "prohibidos": [], "reversible": True},
        "verificacion": {"invariantes": ["INV-9"],
                         "pruebas_minimas": [str(PLANO / "test_red_autoconstruccion.py")],
                         "criterio_de_aceptacion": "el simbolo ya no consta",
                         "evidencia": "cambio_aplicado con efecto_verificado"},
        "trazabilidad": {"especificacion": "fixture", "autorizacion": "DEC-ORCH-2"},
    }
    base.update(cambios)
    return base


def _bloqueada_por_alcance(resultado) -> bool:
    return any("fuera de alcance" in b or "fuera_de_alcance" in b for b in resultado["bloqueos"])


# --------------------------------------------------------------------- 1. literal, mismo fichero --

def test_fichero_declarado_modificable_y_fuera_de_alcance_a_la_vez_bloquea(tmp_path):
    objetivo = tmp_path / "objetivo.py"
    objetivo.write_text("# nada\n")
    r = ct.evaluar(_completo(perimetro={
        "modificables": [str(objetivo)],
        "fuera_de_alcance": [str(objetivo)],
    }), directorio=PLANO)
    assert r["estado"] == ct.BLOQUEADA
    assert _bloqueada_por_alcance(r), r["bloqueos"]


# --------------------------------------------------------------------------- 2. traversal con .. --

def test_traversal_con_puntos_no_escapa_al_bloqueo(tmp_path):
    sub = tmp_path / "sub"
    sub.mkdir()
    objetivo = tmp_path / "objetivo.py"
    objetivo.write_text("# nada\n")
    ruta_con_traversal = str(sub / ".." / "objetivo.py")
    r = ct.evaluar(_completo(perimetro={
        "modificables": [ruta_con_traversal],
        "fuera_de_alcance": [str(objetivo)],
    }), directorio=PLANO)
    assert r["estado"] == ct.BLOQUEADA
    assert _bloqueada_por_alcance(r), r["bloqueos"]


# --------------------------------------------------------------------------- 3. ruta absoluta --

def test_ruta_absoluta_en_fuera_de_alcance_bloquea_ruta_absoluta_en_modificables(tmp_path):
    objetivo = tmp_path / "objetivo.py"
    objetivo.write_text("# nada\n")
    assert pathlib.Path(str(objetivo)).is_absolute()
    r = ct.evaluar(_completo(perimetro={
        "modificables": [str(objetivo)],
        "fuera_de_alcance": [str(objetivo.resolve())],
    }), directorio=PLANO)
    assert r["estado"] == ct.BLOQUEADA
    assert _bloqueada_por_alcance(r), r["bloqueos"]


# --------------------------------------------------------------------------- 4. symlink --

def test_symlink_al_fichero_prohibido_no_evade_el_bloqueo(tmp_path):
    objetivo = tmp_path / "objetivo.py"
    objetivo.write_text("# nada\n")
    enlace = tmp_path / "alias.py"
    enlace.symlink_to(objetivo)
    r = ct.evaluar(_completo(perimetro={
        "modificables": [str(enlace)],
        "fuera_de_alcance": [str(objetivo)],
    }), directorio=PLANO)
    assert r["estado"] == ct.BLOQUEADA
    assert _bloqueada_por_alcance(r), r["bloqueos"]


# ------------------------------------------------------------- 5. fichero VECINO: NO confundir --

def test_fichero_vecino_con_nombre_parecido_no_se_confunde_con_el_prohibido(tmp_path):
    dir_a = tmp_path / "dir_a"
    dir_b = tmp_path / "dir_b"
    dir_a.mkdir()
    dir_b.mkdir()
    prohibido = dir_a / "foo.py"
    prohibido.write_text("# prohibido\n")
    vecino = dir_b / "foo.py"          # mismo nombre, directorio distinto: NO es el mismo fichero
    vecino.write_text("# vecino, no es el mismo fichero\n")

    r = ct.evaluar(_completo(perimetro={
        "modificables": [str(vecino)],
        "fuera_de_alcance": [str(prohibido)],
    }), directorio=PLANO)
    # El vecino NO esta en la lista fuera_de_alcance (es una ruta distinta), asi que esta
    # comprobacion en particular no debe bloquear. (Puede seguir bloqueado por otras razones ajenas
    # a fuera_de_alcance -p.ej. zona_permitida-, por eso se comprueba la ausencia del bloqueo
    # especifico, no el estado global.)
    assert not _bloqueada_por_alcance(r), r["bloqueos"]


def test_substring_del_nombre_no_basta_para_bloquear(tmp_path):
    """`secreto.py` no debe bloquear `secreto_publico.py`: nombre distinto, no substring."""
    prohibido = tmp_path / "secreto.py"
    prohibido.write_text("# prohibido\n")
    parecido = tmp_path / "secreto_publico.py"
    parecido.write_text("# no es el mismo fichero\n")

    r = ct.evaluar(_completo(perimetro={
        "modificables": [str(parecido)],
        "fuera_de_alcance": [str(prohibido)],
    }), directorio=PLANO)
    assert not _bloqueada_por_alcance(r), r["bloqueos"]


# ------------------------------------------------------------- 6. fichero de autoridad, en prosa --

def test_prosa_que_nombra_un_fichero_de_intocables_bloquea():
    """Prosa real tomada de `etiqueta-observatorio-efecto.toml`: nombra `orquestador.py` entre
    parentesis, no como ruta aislada. Si el modificable ES ese fichero (via su ruta real en el
    plano), el contrato tiene que bloquearse aunque la entrada sea prosa, no una lista de rutas."""
    prosa = ("cualquier fichero de _INTOCABLES (orquestador.py, politica-orquestador.toml, "
              "control_plane.py, conftest.py)")
    r = ct.evaluar(_completo(perimetro={
        "modificables": [str(PLANO / "orquestador.py")],
        "fuera_de_alcance": [prosa],
    }), directorio=PLANO)
    assert r["estado"] == ct.BLOQUEADA
    assert _bloqueada_por_alcance(r), r["bloqueos"]


def test_prosa_que_nombra_contrato_py_bloquea_el_mecanismo_de_autoridad():
    prosa = "review.py, contrato.py, autoconstruccion.py y el resto del mecanismo de autoridad"
    r = ct.evaluar(_completo(perimetro={
        "modificables": [str(PLANO / "contrato.py")],
        "fuera_de_alcance": [prosa],
    }), directorio=PLANO)
    assert r["estado"] == ct.BLOQUEADA
    assert _bloqueada_por_alcance(r), r["bloqueos"]


def test_prosa_de_directorio_con_barra_bloquea_ficheros_bajo_ese_directorio(tmp_path):
    (tmp_path / "walking-skeleton").mkdir()
    objetivo = tmp_path / "walking-skeleton" / "modulo.py"
    objetivo.write_text("# producto\n")
    prosa = "walking-skeleton/ y aura_skeleton/ (el producto)"
    r = ct.evaluar(_completo(perimetro={
        "modificables": [str(objetivo)],
        "fuera_de_alcance": [prosa],
    }), directorio=PLANO)
    assert r["estado"] == ct.BLOQUEADA
    assert _bloqueada_por_alcance(r), r["bloqueos"]


def test_prosa_sin_ficheros_reconocibles_no_bloquea_por_si_sola(tmp_path):
    """`el resto del mecanismo de autoridad`, `kill_switch`, `permisos`, `_efecto_real` no son rutas
    ni nombres de fichero reconocibles: no deben producir un bloqueo de fuera_de_alcance por
    coincidencia de letras. Limite documentado, no omision."""
    objetivo = tmp_path / "modulo_neutro.py"
    objetivo.write_text("# nada\n")
    prosa = "kill_switch, permisos, PARADA, _efecto_real y cualquier funcion que decida QUE se cuenta"
    r = ct.evaluar(_completo(perimetro={
        "modificables": [str(objetivo)],
        "fuera_de_alcance": [prosa],
    }), directorio=PLANO)
    assert not _bloqueada_por_alcance(r), r["bloqueos"]


# --------------------------------------------------- 7. no-regresion: los dos contratos reales --

def test_no_regresion_etiqueta_observatorio_efecto_sigue_implementable():
    contrato = ct.contrato_de("etiqueta-observatorio-efecto")
    assert contrato is not None
    r = ct.evaluar(contrato, directorio=PLANO)
    assert r["estado"] == ct.IMPLEMENTABLE, r["bloqueos"]


def test_no_regresion_sexta_fuente_estancamiento_sigue_implementable():
    contrato = ct.contrato_de("sexta-fuente-estancamiento")
    assert contrato is not None
    r = ct.evaluar(contrato, directorio=PLANO)
    assert r["estado"] == ct.IMPLEMENTABLE, r["bloqueos"]
