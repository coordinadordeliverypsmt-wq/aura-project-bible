"""Plugin de diagnostico: tras cada prueba, rutas NUEVAS bajo $HOME (falso) y la prueba que las creo."""
import json, os

_HOME = os.environ["HOME"]
_SALIDA = os.environ["VIGIA_SALIDA"]
_vistos: set[str] = set()


def _barrer() -> set[str]:
    rutas = set()
    for raiz, dirs, ficheros in os.walk(_HOME):
        prof = raiz[len(_HOME):].count(os.sep)
        if prof >= 3:
            dirs[:] = []
        for n in dirs + ficheros:
            rutas.add(os.path.relpath(os.path.join(raiz, n), _HOME))
    return rutas


def pytest_sessionstart(session):
    _vistos.update(_barrer())


def pytest_runtest_teardown(item, nextitem):
    nuevas = _barrer() - _vistos
    if nuevas:
        _vistos.update(nuevas)
        with open(_SALIDA, "a") as f:
            f.write(json.dumps({"prueba": item.nodeid, "nuevas": sorted(nuevas)[:20]}) + "\n")
