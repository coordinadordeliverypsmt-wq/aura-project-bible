"""Unit: INV-4 — el aislamiento de fallos es SIMETRICO para toda familia de detectores.

**Gate A-0 (CEO, 2026-07-27).** B1 no se cierra protegiendo la invocacion del detector de hardware: se
cierra fijando el CRITERIO, de modo que una familia de detectores **futura** quede cubierta sin editar
esta prueba. Corregir el caso particular dejaria la clase de defecto abierta.

Criterio uniforme, derivado de los CONTRATOS (`core/detectores.py`), nunca de una lista escrita a mano:

    familia de detector := Protocol declarado en el modulo de contratos de deteccion.

    Toda invocacion de un metodo de familia dentro del Builder debe ejecutarse en el cuerpo de un `try`
    cuyo manejador (a) capture `Exception` —ni `except:` desnudo ni `BaseException`—, (b) **registre** el
    incidente y (c) **no relance**.

Los tres requisitos son literalmente INV-4: *"Aisla el fallo de un detector y **registra** el incidente."*
(a) y (c) son "aisla"; (b) es "registra". `BaseException` queda excluido a proposito: `KeyboardInterrupt`
y `SystemExit` deben seguir terminando el proceso — un fallo del entorno se aisla, una orden del usuario no.

Deteccion por **AST**, no por texto (leccion D41/MA.5-a): un docstring que mencione `try` no satisface nada.

Las pruebas sinteticas del final verifican **el criterio en si mismo**: si el analizador no detectase una
violacion introducida a proposito, la prueba sobre el codigo real seria vacua.
"""

import ast
import pathlib

# --- El criterio, expresado una sola vez y aplicado a cualquier fuente ---


def _fuente(cual: str) -> str:
    from aura_skeleton.core import activation_context_builder, detectores

    mod = {"builder": activation_context_builder, "detectores": detectores}[cual]
    return pathlib.Path(mod.__file__).read_text(encoding="utf-8")


def _familias(fuente_detectores: str) -> dict[str, str]:
    """metodo de deteccion -> familia que lo declara. Descubierto de los Protocol, no listado a mano."""
    familias: dict[str, str] = {}
    for n in ast.walk(ast.parse(fuente_detectores)):
        if isinstance(n, ast.ClassDef) and any(getattr(b, "id", "") == "Protocol" for b in n.bases):
            for m in n.body:
                if isinstance(m, ast.FunctionDef) and not m.name.startswith("_"):
                    familias[m.name] = n.name
    return familias


def _defectos_del_manejador(guarda: ast.Try) -> list[str]:
    """Que le impide AISLAR, si es que algo se lo impide (INV-4)."""
    defectos: list[str] = []
    if not guarda.handlers:
        return ["sin manejador"]
    for h in guarda.handlers:
        if h.type is None:
            defectos.append("except desnudo")
        elif getattr(h.type, "id", "") == "BaseException":
            defectos.append("captura BaseException")
        elif getattr(h.type, "id", "") != "Exception":
            # Hallado durante la validacion por mutacion de B1: un `except RuntimeError` deja pasar
            # cualquier otro fallo del detector. El aislamiento debe ser por AMPLITUD, no por tipo.
            defectos.append(f"captura demasiado estrecha ({ast.unparse(h.type)})")
        if any(isinstance(x, ast.Raise) for x in ast.walk(h)):
            defectos.append("relanza el fallo")
        registra = any(
            isinstance(x, ast.Call) and isinstance(x.func, ast.Attribute) and x.func.attr == "log" for x in ast.walk(h)
        )
        if not registra:
            defectos.append("no registra el incidente")
    return defectos


def _violaciones(fuente_builder: str, fuente_detectores: str) -> list[str]:
    """Invocaciones de deteccion que NO quedan aisladas conforme a INV-4."""
    metodos = _familias(fuente_detectores)
    arbol = ast.parse(fuente_builder)

    protegidas: dict[int, ast.Try] = {}
    for n in ast.walk(arbol):
        if isinstance(n, ast.Try):
            for stmt in n.body:  # solo el CUERPO: una llamada dentro del propio manejador no esta aislada
                for sub in ast.walk(stmt):
                    if isinstance(sub, ast.Call):
                        protegidas[id(sub)] = n

    fallos: list[str] = []
    for c in sorted(
        (
            n
            for n in ast.walk(arbol)
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr in metodos
        ),
        key=lambda x: x.lineno,
    ):
        guarda = protegidas.get(id(c))
        motivos = ["no esta dentro de ningun try"] if guarda is None else _defectos_del_manejador(guarda)
        if motivos:
            fallos.append(f"linea {c.lineno}: {metodos[c.func.attr]}.{c.func.attr}() -> {'; '.join(motivos)}")
    return fallos


# --- El criterio, aplicado al codigo REAL ---


def test_el_modulo_de_contratos_declara_familias_de_deteccion():
    """Si el descubrimiento devolviera vacio, la prueba principal seria vacua: se comprueba primero."""
    familias = _familias(_fuente("detectores"))
    assert set(familias.values()) >= {"DetectorHardware", "DetectorEntorno"}
    assert "detectar" in familias and "capacidades_soportadas" in familias


def test_toda_invocacion_de_detector_en_el_builder_queda_aislada():
    """INV-4 para TODA familia, presente o futura: ninguna deteccion puede abortar el arranque."""
    fallos = _violaciones(_fuente("builder"), _fuente("detectores"))
    assert not fallos, "invocaciones de deteccion sin aislamiento (INV-4):\n  " + "\n  ".join(fallos)


# --- El criterio, verificado contra si mismo (no puede ser vacuo) ---

_DETECTORES_CON_FAMILIA_FUTURA = """
from typing import Protocol
class DetectorHardware(Protocol):
    def detectar(self): ...
class DetectorRed(Protocol):            # familia que hoy no existe
    def enlace_disponible(self): ...
"""

_BUILDER_CON_FAMILIA_FUTURA_DESPROTEGIDA = """
class B:
    def construir(self):
        try:
            h = self._hw.detectar()
        except Exception as e:
            obs.log("WARN", "m", str(e), "-")
            h = None
        return (h, self._red.enlace_disponible())   # familia nueva, sin aislar
"""


def test_el_criterio_cubre_una_familia_de_detectores_FUTURA():
    """Prueba central del Gate A-0: el criterio no conoce 'hardware'; conoce 'familia de detector'."""
    fallos = _violaciones(_BUILDER_CON_FAMILIA_FUTURA_DESPROTEGIDA, _DETECTORES_CON_FAMILIA_FUTURA)
    assert len(fallos) == 1
    assert "DetectorRed.enlace_disponible()" in fallos[0]


def test_el_criterio_rechaza_un_manejador_que_no_registra():
    builder = """
class B:
    def construir(self):
        try:
            return self._hw.detectar()
        except Exception:
            return None
"""
    assert any("no registra" in f for f in _violaciones(builder, _fuente("detectores")))


def test_el_criterio_rechaza_un_manejador_que_relanza():
    builder = """
class B:
    def construir(self):
        try:
            return self._hw.detectar()
        except Exception as e:
            obs.log("WARN", "m", str(e), "-")
            raise
"""
    assert any("relanza" in f for f in _violaciones(builder, _fuente("detectores")))


def test_el_criterio_rechaza_except_desnudo_y_baseexception():
    desnudo = """
class B:
    def construir(self):
        try:
            return self._hw.detectar()
        except:
            obs.log("WARN", "m", "x", "-")
"""
    base = """
class B:
    def construir(self):
        try:
            return self._hw.detectar()
        except BaseException as e:
            obs.log("WARN", "m", str(e), "-")
"""
    assert any("desnudo" in f for f in _violaciones(desnudo, _fuente("detectores")))
    assert any("BaseException" in f for f in _violaciones(base, _fuente("detectores")))


def test_el_criterio_rechaza_una_captura_demasiado_estrecha():
    """Un manejador por tipo concreto no aisla: cualquier otro fallo del detector sigue abortando."""
    estrecho = """
class B:
    def construir(self):
        try:
            return self._hw.detectar()
        except RuntimeError as e:
            obs.log("WARN", "m", str(e), "-")
"""
    assert any("demasiado estrecha" in f for f in _violaciones(estrecho, _fuente("detectores")))


def test_el_criterio_acepta_un_aislamiento_correcto():
    """Sin esta prueba, un criterio que rechazara TODO tambien pasaria las anteriores."""
    correcto = """
class B:
    def construir(self):
        soportadas = set()
        for d in self._entorno:
            try:
                soportadas |= set(d.capacidades_soportadas())
            except Exception as e:
                obs.log("WARN", "m", str(e), "-")
        try:
            h = self._hw.detectar()
        except Exception as e:
            obs.log("WARN", "m", str(e), "-")
            h = None
        return (h, soportadas)
"""
    assert _violaciones(correcto, _fuente("detectores")) == []
