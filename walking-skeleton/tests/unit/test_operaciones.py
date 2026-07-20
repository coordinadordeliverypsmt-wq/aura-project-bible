"""M2.1 — Validacion de operaciones tipadas del computador.

Pruebas ADVERSARIALES: cada caso intenta activamente burlar el perimetro. Se escriben antes de que
exista adaptador alguno, de modo que la primera linea de codigo que toque archivos reales ya
encuentre el limite puesto (riesgo RN-1).
"""

import os

import pytest

from aura_skeleton.core.operaciones import ESPECIFICACIONES, ErrorDeValidacion, validar


@pytest.fixture
def raiz(tmp_path):
    return (str(tmp_path),)


# --- RN-2: no existe camino para ejecucion arbitraria -----------------------


@pytest.mark.parametrize("accion", ["ejecutar_comando", "shell", "eval", "sudo", "rm"])
def test_operacion_fuera_del_catalogo_se_rechaza(accion, raiz):
    """El adaptador solo puede exponer el catalogo. Sin esto, la lista roja seria irrelevante:
    cualquier accion destructiva podria envolverse en un comando."""
    with pytest.raises(ErrorDeValidacion, match="fuera del catalogo"):
        validar(accion, {"cmd": "rm -rf /"}, raiz)


# --- Perimetro de rutas ----------------------------------------------------


def test_ruta_relativa_se_rechaza(raiz):
    """Se resolveria contra el cwd del proceso, que no es parte del modelo de seguridad.

    Regresion de un fallo real detectado en M2.1: '../../etc/passwd' resultaba ACEPTADO porque el
    cwd quedaba dentro del ambito permitido. Era casualidad, no seguridad.
    """
    with pytest.raises(ErrorDeValidacion, match="relativa"):
        validar("borrar_archivo", {"ruta": "../../etc/passwd"}, raiz)


def test_ruta_absoluta_fuera_del_ambito_se_rechaza(raiz):
    with pytest.raises(ErrorDeValidacion, match="fuera del ambito"):
        validar("borrar_archivo", {"ruta": "/etc/passwd"}, raiz)


def test_travesia_con_puntos_se_rechaza(tmp_path):
    with pytest.raises(ErrorDeValidacion, match="fuera del ambito"):
        validar("borrar_archivo", {"ruta": str(tmp_path / ".." / ".." / "etc" / "passwd")}, (str(tmp_path),))


def test_escape_por_enlace_simbolico_se_rechaza(tmp_path):
    """El caso que pasaria en silencio sin resolver enlaces.

    Un enlace CREADO DENTRO del ambito permitido apunta fuera. Comprobar solo el prefijo textual
    daria un falso OK: la ruta empieza por la raiz permitida. `realpath` resuelve el enlace y
    descubre el destino real.
    """
    enlace = tmp_path / "atajo"
    os.symlink("/etc", enlace)
    with pytest.raises(ErrorDeValidacion, match="fuera del ambito"):
        validar("leer_archivo", {"ruta": str(enlace / "passwd")}, (str(tmp_path),))


# --- Comodines -------------------------------------------------------------


@pytest.mark.parametrize("accion", ["borrar_archivo", "mover_archivo", "escribir_archivo"])
def test_comodin_prohibido_en_operaciones_que_alteran(accion, tmp_path):
    """Un comodin convierte un error de un archivo en una perdida masiva."""
    args = {"ruta": str(tmp_path / "*.txt")}
    if accion == "mover_archivo":
        args = {"origen": str(tmp_path / "*.txt"), "destino": str(tmp_path / "otro")}
    elif accion == "escribir_archivo":
        args["contenido"] = "x"
    with pytest.raises(ErrorDeValidacion, match="comodin"):
        validar(accion, args, (str(tmp_path),))


def test_comodin_permitido_en_busqueda(tmp_path):
    """Buscar es de solo lectura: el comodin ahi es util y no destruye nada."""
    r = validar("buscar_archivo", {"patron": "*.pdf", "raiz": str(tmp_path)}, (str(tmp_path),))
    assert r["raiz"] == os.path.realpath(str(tmp_path))


# --- Contrato de argumentos ------------------------------------------------


def test_argumentos_faltantes_se_rechazan(raiz):
    with pytest.raises(ErrorDeValidacion, match="faltan argumentos"):
        validar("leer_archivo", {}, raiz)


def test_argumentos_no_declarados_se_rechazan(tmp_path):
    """Un argumento inesperado podria alterar el comportamiento del adaptador."""
    with pytest.raises(ErrorDeValidacion, match="no declarados"):
        validar("leer_archivo", {"ruta": str(tmp_path / "n.txt"), "sudo": True}, (str(tmp_path),))


# --- Caso legitimo (control) -----------------------------------------------


def test_ruta_valida_se_acepta_y_normaliza(tmp_path):
    """CONTROL: sin este caso, un validador que rechazara TODO daria falso PASS en los anteriores."""
    destino = tmp_path / "documentos" / "nota.txt"
    r = validar("leer_archivo", {"ruta": str(destino)}, (str(tmp_path),))
    assert os.path.isabs(r["ruta"])


@pytest.mark.parametrize("accion", sorted(ESPECIFICACIONES))
def test_toda_operacion_declara_su_especificacion(accion):
    e = ESPECIFICACIONES[accion]
    assert set(e) == {"args", "rutas", "permite_comodin"}
    assert set(e["rutas"]).issubset(set(e["args"])), "una ruta debe ser tambien un argumento declarado"
