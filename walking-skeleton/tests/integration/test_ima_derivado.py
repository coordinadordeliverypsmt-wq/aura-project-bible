"""Integracion: el IMA no puede afirmar que una capacidad no existe cuando existe.

EL DEFECTO QUE CIERRA. Tras seis incrementos, el IMA seguia marcando 26/32 y decia "AGENTE AUDITOR: no
existe; hoy audita Claude" cuando el Auditor llevaba dos incrementos cableado y corriendo en el gate.
La comprobacion estaba escrita a mano como `False`. Es el patron declarado != real dentro del propio
instrumento de medida, y invalidaba el criterio de decision: ningun incremento podia demostrar que
aumentaba una dimension si la dimension no se enteraba.
"""

import ast
import tempfile
from pathlib import Path

from aura_skeleton.composicion import Configuracion, componer
from aura_skeleton.core.ima import evaluar

_IMA = Path(__file__).resolve().parents[2] / "aura_skeleton" / "core" / "ima.py"


def _constantes_en_comprobaciones() -> list[str]:
    """Comprobaciones cuyo valor es un literal, no una consulta al sistema."""
    arbol = ast.parse(_IMA.read_text(encoding="utf-8"))
    fn = next(n for n in ast.walk(arbol) if isinstance(n, ast.FunctionDef) and n.name == "evaluar")
    congeladas = []
    for d in ast.walk(fn):
        if isinstance(d, ast.Dict):
            for k, v in zip(d.keys, d.values, strict=False):
                if isinstance(k, ast.Constant) and isinstance(k.value, str) and ast.unparse(v) in ("True", "False"):
                    congeladas.append(k.value)
    return congeladas


def test_NINGUNA_comprobacion_del_IMA_esta_escrita_a_mano():
    """LA GARANTIA: si una capacidad existe, el IMA no puede decir que no.

    Una comprobacion congelada envejece sin que nadie lo note. Lo que requiere juicio se declara
    NO_MEDIBLE con motivo; lo demas se deriva del sistema.
    """
    congeladas = _constantes_en_comprobaciones()
    assert not congeladas, (
        "estas comprobaciones no se derivan del sistema y envejeceran en silencio:\n"
        + "\n".join(f"  · {c}" for c in congeladas)
        + "\n\nDerivalas por introspeccion, o declara la dimension NO_MEDIBLE con su motivo."
    )


def test_el_IMA_reconoce_el_auditor_que_ya_existe():
    """El caso concreto que destapo el defecto."""
    d = {x.nombre: x for x in evaluar(componer(Configuracion(datos=tempfile.mkdtemp())))}
    aud = d["Capacidad de auditoria"]
    assert "audita sus propias decisiones de arquitectura" in aud.evidencias, (
        f"el Auditor esta cableado y el IMA no lo reconoce: {aud.faltan}"
    )


def test_lo_que_exige_juicio_se_declara_NO_MEDIBLE_no_como_constante():
    """Tres propiedades no son observables: convergencia demostrada e intencion de uso del historial."""
    dims = {x.nombre: x for x in evaluar(componer(Configuracion(datos=tempfile.mkdtemp())))}
    for nombre in ("Convergencia del trabajo", "Uso del aprendizaje"):
        assert dims[nombre].medible is False, f"{nombre} no puede medirse por introspeccion"
        assert dims[nombre].instrumentacion_ausente, f"{nombre} debe declarar POR QUE no se mide"


def test_CONTROL_el_indice_sigue_midiendo_algo():
    """Sin esto, todo lo anterior pasaria declarandolo TODO no medible."""
    dims = evaluar(componer(Configuracion(datos=tempfile.mkdtemp())))
    medibles = [d for d in dims if d.medible]
    assert len(medibles) >= 6, f"solo {len(medibles)} dimensiones medibles: el indice se vacio"
    assert sum(d.total for d in medibles) >= 25


def test_la_comprobacion_de_tolerancia_es_REAL_no_un_si_constante():
    """Detectado por mutacion: devolver True siempre pasaria inadvertido con el codigo actual.

    Se le da una clase que NO tolera corrupcion y debe decir que no. Sin este caso negativo, la
    comprobacion podria estar afirmando en vez de comprobando.
    """
    from aura_skeleton.core.ima import _tolera_corrupcion

    class SinTolerancia:
        def _cargar(self):
            for linea in []:
                json_loads(linea)  # noqa: F821 - sin try/except: una linea rota aborta el arranque

    assert _tolera_corrupcion(SinTolerancia()) is False, "debe detectar que NO tolera lineas corruptas"

    class ConTolerancia:
        def _cargar(self):
            for linea in []:
                try:
                    json_loads(linea)  # noqa: F821
                except ValueError:
                    continue

    assert _tolera_corrupcion(ConTolerancia()) is True, "y debe reconocer la que si tolera"
