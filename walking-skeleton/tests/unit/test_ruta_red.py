"""`__main__._ruta_red`: que red de nodos leen `--nodos` y `--receptor-nodos` (2026-10-25).

Defecto medido `[EJEC]` con un HOME falso: `AURA_RED=""` resuelve a `~/.aura-red`, IGUAL que la variable
ausente, porque `os.environ.get("AURA_RED") or _RED_POR_DEFECTO` trata la cadena vacia como ausencia. El
resto del sistema dice lo contrario: `receptor_nodos.crear_vigia_nodos` y `estado_autonomo_cp` leen «declarado
y vacio» como «no hay red». Y la bateria fija `AURA_RED=""` (conftest `_sin_red_de_nodos_real`) creyendo que
significa «sin red»: para el CLI significaba el `~/.aura-red` REAL, con la credencial y la PKI del receptor.

Dos capas, con dos estados:

- **Bateria** (corregido): `_sin_red_real_por_defecto` desvia `_RED_POR_DEFECTO` a un temporal por prueba.
  Ninguna prueba en proceso puede resolver el directorio real, este ausente o vacia la variable.
- **Produccion** (corregido): `""` (o solo espacios) significa «sin red» tambien en el CLI. `--nodos` lo dice y
  sale con 0; `--receptor-nodos` sale con 2 ANTES de leer credencial o CA y de conectar. Las pruebas `PROPUESTA_*`
  eran `xfail(strict=True)` mientras el cambio esperaba autorizacion; al aplicarlo se retiro la marca.

El servicio de produccion (`aura-receptor-nodos.service`) fija `AURA_RED` explicito: el cambio no le afecta.
"""

from __future__ import annotations

import json
import os
import pathlib
import re
import time

import pytest

from aura_skeleton import __main__ as principal
from aura_skeleton.core.nodos import RegistroNodos, construir_latido, validar_latido

ID_TRAMPA = "e" * 32


def _red_real() -> str:
    return os.path.realpath(os.path.expanduser("~/.aura-red"))


def _escribir_registro(red, nombre: str = "nodo-trampa") -> None:
    reg = RegistroNodos()
    ahora = time.time()
    latido = validar_latido(
        construir_latido(ID_TRAMPA, nombre, 1, "d" * 32, 10.0, {"ram_mb": 986.0, "nucleos": 2.0}, [], "1.0")
    )
    reg.registrar(latido, ahora - 2)
    (red / "nodos").mkdir(parents=True)
    (red / "nodos" / "registro.json").write_text(
        json.dumps({"receptor": {"latido": ahora - 1, "pid": 1}, **reg.a_dict()}), encoding="utf-8"
    )


# ------------------------------------------------------------------ la bateria (corregido) --


@pytest.mark.parametrize("valor", [None, ""], ids=["ausente", "vacia"])
def test_la_bateria_nunca_resuelve_la_red_real(monkeypatch, valor):
    if valor is None:
        monkeypatch.delenv("AURA_RED", raising=False)
    else:
        monkeypatch.setenv("AURA_RED", valor)
    ruta = principal._ruta_red()
    # `None` es «sin red»: lo que devuelve `_ruta_red` para AURA_RED="" desde la correccion.
    assert ruta is None or os.path.realpath(ruta) != _red_real(), "la bateria resolvio el ~/.aura-red REAL"


# ------------------------------------------------- comportamiento que NO cambia (actual = propuesto) --


def test_ausente_resuelve_al_directorio_por_defecto(monkeypatch, tmp_path):
    monkeypatch.setattr(principal, "_RED_POR_DEFECTO", str(tmp_path / "defecto"))
    monkeypatch.delenv("AURA_RED", raising=False)
    assert principal._ruta_red() == str(tmp_path / "defecto")


def test_explicita_resuelve_a_esa_ruta(monkeypatch, tmp_path):
    monkeypatch.setenv("AURA_RED", str(tmp_path / "explicita"))
    assert principal._ruta_red() == str(tmp_path / "explicita")


def test_nodos_en_proceso_lee_la_red_explicita(monkeypatch, tmp_path, capsys):
    _escribir_registro(tmp_path, "nodo-explicito")
    monkeypatch.setenv("AURA_RED", str(tmp_path))
    assert principal.main(["--nodos"]) == 0
    assert "nodo-explicito" in capsys.readouterr().out


def test_receptor_con_red_explicita_sin_credencial_no_arranca_ni_conecta(monkeypatch, tmp_path, capsys):
    """Sin credencial sale con 2 ANTES de abrir ninguna conexion (control de la prueba PROPUESTA de abajo)."""
    monkeypatch.setenv("AURA_RED", str(tmp_path))
    monkeypatch.setenv("AURA_RED_URL", "tls://127.0.0.1:1")
    assert principal.main(["--receptor-nodos"]) == 2
    assert str(tmp_path / "receptor.credencial") in capsys.readouterr().err


# --------------------------------------------- AURA_RED="" = «sin red» (corregido 2026-10-25) --


def test_PROPUESTA_vacia_es_sin_red_y_nodos_no_lee_el_directorio_por_defecto(monkeypatch, tmp_path, capsys):
    defecto = tmp_path / "defecto"
    _escribir_registro(defecto)
    monkeypatch.setattr(principal, "_RED_POR_DEFECTO", str(defecto))
    monkeypatch.setenv("AURA_RED", "")
    principal.main(["--nodos"])
    assert "nodo-trampa" not in capsys.readouterr().out, "AURA_RED='' leyo el registro del directorio por defecto"


def test_PROPUESTA_vacia_el_receptor_no_busca_credencial_en_el_directorio_por_defecto(monkeypatch, tmp_path, capsys):
    defecto = tmp_path / "defecto"
    monkeypatch.setattr(principal, "_RED_POR_DEFECTO", str(defecto))
    monkeypatch.setenv("AURA_RED", "")
    monkeypatch.setenv("AURA_RED_URL", "tls://127.0.0.1:1")
    assert principal.main(["--receptor-nodos"]) == 2
    assert str(defecto) not in capsys.readouterr().err, "AURA_RED='' busco la credencial en el directorio por defecto"


# ---------------------------------------- subprocesos: el parche en proceso NO llega a un hijo --
#
# `_sin_red_real_por_defecto` solo protege dentro del proceso de pytest. Un `python -m aura_skeleton --nodos` o
# `--receptor-nodos` lanzado en subproceso hereda la bateria. Hasta la correccion de `_ruta_red`, `AURA_RED=""`
# resolvia el `~/.aura-red` REAL: el receptor leia la credencial real y conectaba al nats-server real de
# 127.0.0.1:4222 (revision de seguridad 2026-10-25 (u), MEDIO). Se conserva como defensa en profundidad: un
# subproceso SIN `AURA_RED` seguiria cayendo en el directorio por defecto real. Guardia estatica, mismo patron que
# `test_ninguna_prueba_del_repo_puede_iniciar_el_reloj_real`. Limite: es por fichero; no ve un `env` mal armado.

_LANZA_CLI_DE_NODOS = re.compile(r"[\"']--(?:receptor-)?nodos[\"']")
_FIJA_AURA_RED = re.compile(r"[\"']AURA_RED[\"']\s*:")
_EN_PROCESO = {"conftest.py", "test_ruta_red.py"}  # protegidos por la fixture: llaman a `principal.main` en proceso


def _sin_red_propia(texto: str) -> bool:
    return bool(_LANZA_CLI_DE_NODOS.search(texto)) and not _FIJA_AURA_RED.search(texto)


def test_toda_prueba_que_lanza_el_cli_de_nodos_fija_su_propia_red():
    tests = pathlib.Path(__file__).resolve().parents[1]
    vistos, infractores = 0, []
    for f in sorted(tests.rglob("*.py")):
        if f.name in _EN_PROCESO:
            continue
        texto = f.read_text(encoding="utf-8")
        if _LANZA_CLI_DE_NODOS.search(texto):
            vistos += 1
            if _sin_red_propia(texto):
                infractores.append(str(f.relative_to(tests)))
    assert infractores == [], f"lanzan el CLI de nodos sin AURA_RED propio (heredarian ~/.aura-red real): {infractores}"
    assert vistos >= 2  # control: la guardia ve test_cli_nodos.py y test_nodo_e2e_nats.py


def test_control_la_guardia_detecta_un_lanzamiento_sin_red_propia():
    sin = 'subprocess.run([sys.executable, "-m", "aura_skeleton", "--receptor-nodos"], env=dict(os.environ))'
    con = (
        'env = {**os.environ, "AURA_RED": str(tmp)}; subprocess.run([sys.executable, "-m", "aura_skeleton", "--nodos"])'
    )
    assert _sin_red_propia(sin) and not _sin_red_propia(con)


@pytest.mark.parametrize("valor", ["", "   ", "\t", "\n"], ids=["vacia", "espacios", "tabulador", "salto"])
def test_solo_espacios_tambien_es_sin_red_en_nodos_y_receptor(monkeypatch, tmp_path, capsys, valor):
    """`declarado.strip()`: un valor solo de espacios es tan «vacio» como `""` (mismo criterio que el vigia)."""
    defecto = tmp_path / "defecto"
    _escribir_registro(defecto)
    monkeypatch.setattr(principal, "_RED_POR_DEFECTO", str(defecto))
    monkeypatch.setenv("AURA_RED", valor)
    monkeypatch.setenv("AURA_RED_URL", "tls://127.0.0.1:1")
    assert principal.main(["--nodos"]) == 0
    salida = capsys.readouterr().out
    # En positivo: sin `.strip()`, "   " seria una ruta relativa sin registro y lo negativo pasaria igual.
    assert "red de nodos desactivada" in salida and "nodo-trampa" not in salida, salida
    assert principal.main(["--receptor-nodos"]) == 2
    error = capsys.readouterr().err
    assert "AURA_RED declarado vacio" in error and str(defecto) not in error, error
