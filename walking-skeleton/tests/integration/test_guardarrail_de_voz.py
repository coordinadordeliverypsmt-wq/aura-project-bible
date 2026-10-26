"""Guardarraíl de voz — Voice persistence, OPCIÓN B (acta del CEO, 2026-09-16).

POR QUÉ UN LANZADOR Y NO UNA VARIABLE. El acta **D27** ya resolvió este problema para los modelos de
Ollama, y su lanzador lo deja escrito: *«Una variable de entorno no es una garantia:
/media/.../AURORA_EXT existe igual con el USB desmontado»*. Medido en esta máquina: el directorio del
punto de montaje **existe en el disco interno** aunque la USB no esté, así que comprobar la ruta no
prueba nada. Lo que prueba algo es comprobar el **dispositivo real** con `df --output=source`.

QUÉ HACE ESTE LANZADOR, siguiendo el patrón D27:

    1. la USB con la etiqueta declarada está conectada       (lsblk por etiqueta)
    2. está montada donde se espera                          (mountpoint)
    3. los modelos residen FÍSICAMENTE en ese dispositivo    (df --output=source)   <- la clave
    4. los ficheros existen y son legibles                   (.onnx + .onnx.json + caché de Whisper)

DIFERENCIA DELIBERADA CON D27. Ollama **escribe** en su almacén, por eso D27 exige `-w` y **aborta**.
La voz solo **lee**, y AURA ya sabe entregar los turnos en texto cuando no hay voz. Abortar dejaría al
usuario sin producto por un periférico; por eso, por defecto, este lanzador **degrada con honestidad**:
no exporta las variables, lo dice, y arranca igual. `--exigir-voz` recupera el comportamiento estricto
de D27 para quien quiera voz o nada.

NO descarga, NO instala, NO copia y NO cambia de modelo: solo mira y decide si puede exportar.
"""

from __future__ import annotations

import os
import pathlib
import subprocess

RAIZ = pathlib.Path(__file__).resolve().parents[3]
LANZADOR = RAIZ / "entorno" / "scripts" / "voz-usb.sh"


def _correr(args: list[str], entorno: dict[str, str]) -> subprocess.CompletedProcess:
    env = {**os.environ, **entorno}
    return subprocess.run(["bash", str(LANZADOR), *args], capture_output=True, text=True, timeout=60, env=env)


def _voz_falsa(raiz: pathlib.Path) -> pathlib.Path:
    """Un árbol de voz con la forma real: `.onnx` + `.onnx.json` + caché de Whisper."""
    (raiz / "piper_voices").mkdir(parents=True, exist_ok=True)
    (raiz / "piper_voices" / "es_MX-ald-medium.onnx").write_bytes(b"onnx")
    (raiz / "piper_voices" / "es_MX-ald-medium.onnx.json").write_text("{}", encoding="utf-8")
    (raiz / "hf_cache" / "hub").mkdir(parents=True, exist_ok=True)
    return raiz


def test_el_lanzador_existe_y_es_ejecutable():
    assert LANZADOR.is_file(), f"no existe el lanzador en {LANZADOR}"
    assert os.access(LANZADOR, os.X_OK), "el lanzador no tiene permiso de ejecucion"


def test_sintaxis_valida():
    assert subprocess.run(["bash", "-n", str(LANZADOR)], capture_output=True).returncode == 0


# ======================================================= EL CAMINO SANO --


def test_con_la_USB_montada_y_los_modelos_dentro_declara_la_voz_disponible(tmp_path):
    raiz = _voz_falsa(tmp_path / "AURORA_EXT")
    r = _correr(["--verificar"], {"AURA_VOZ_RAIZ": str(raiz), "AURA_VOZ_SIN_COMPROBAR_DISPOSITIVO": "1"})
    assert r.returncode == 0, r.stdout + r.stderr
    assert "VOZ DISPONIBLE" in r.stdout, r.stdout
    assert "AURA_PIPER_VOICE=" in r.stdout and "es_MX-ald-medium.onnx" in r.stdout, r.stdout
    assert "HF_HOME=" in r.stdout and "HF_HUB_OFFLINE=1" in r.stdout, "debe forzar el modo sin red"


# ======================================================= LAS CUATRO NEGATIVAS --


def test_sin_la_USB_lo_dice_y_no_exporta_nada(tmp_path):
    """El caso real: la ruta existe en el disco interno aunque la USB no esté.

    El motivo importa, no solo el veredicto. Afirmar únicamente «no disponible» dejaba vivo un mutante
    que borraba la comprobación del dispositivo y se apoyaba en la del punto de montaje: dos causas
    distintas, mismo titular (GV-M1, 2026-09-16). La primera puerta de D27 es *«¿está conectado?»*.
    """
    raiz = _voz_falsa(tmp_path / "AURORA_EXT")  # ficheros presentes, pero NO en un dispositivo USB
    r = _correr(["--verificar"], {"AURA_VOZ_RAIZ": str(raiz), "AURA_VOZ_ETIQUETA": "ETIQUETA-QUE-NO-EXISTE"})
    assert r.returncode != 0, "declaró la voz disponible sin comprobar el dispositivo"
    assert "VOZ NO DISPONIBLE" in r.stdout, r.stdout
    assert "no esta conectado" in r.stdout, f"no dice que el dispositivo no está conectado: {r.stdout}"
    assert "AURA_PIPER_VOICE=" not in r.stdout, "exportó la voz sin USB"


def test_si_falta_el_onnx_lo_dice_con_su_ruta(tmp_path):
    raiz = _voz_falsa(tmp_path / "AURORA_EXT")
    (raiz / "piper_voices" / "es_MX-ald-medium.onnx").unlink()
    r = _correr(["--verificar"], {"AURA_VOZ_RAIZ": str(raiz), "AURA_VOZ_SIN_COMPROBAR_DISPOSITIVO": "1"})
    assert r.returncode != 0 and "VOZ NO DISPONIBLE" in r.stdout, r.stdout
    assert "es_MX-ald-medium.onnx" in r.stdout, "no dice qué fichero falta"


def test_si_falta_el_json_de_la_voz_tambien_se_detecta(tmp_path):
    """Piper exige el `.onnx.json` junto al modelo; sin él aborta con un error ilegible."""
    raiz = _voz_falsa(tmp_path / "AURORA_EXT")
    (raiz / "piper_voices" / "es_MX-ald-medium.onnx.json").unlink()
    r = _correr(["--verificar"], {"AURA_VOZ_RAIZ": str(raiz), "AURA_VOZ_SIN_COMPROBAR_DISPOSITIVO": "1"})
    assert r.returncode != 0 and ".onnx.json" in r.stdout, r.stdout


def test_si_falta_la_cache_de_whisper_se_detecta(tmp_path):
    raiz = _voz_falsa(tmp_path / "AURORA_EXT")
    import shutil

    shutil.rmtree(raiz / "hf_cache")
    r = _correr(["--verificar"], {"AURA_VOZ_RAIZ": str(raiz), "AURA_VOZ_SIN_COMPROBAR_DISPOSITIVO": "1"})
    assert r.returncode != 0 and "VOZ NO DISPONIBLE" in r.stdout, r.stdout


# ======================================================= LA REGLA DE D27 --


def test_no_basta_con_que_la_ruta_exista_hay_que_comprobar_el_DISPOSITIVO(tmp_path):
    """La lección literal de D27. Sin `AURA_VOZ_SIN_COMPROBAR_DISPOSITIVO`, la comprobación es real."""
    raiz = _voz_falsa(tmp_path / "AURORA_EXT")
    r = _correr(["--verificar"], {"AURA_VOZ_RAIZ": str(raiz)})
    assert r.returncode != 0, "aceptó una ruta del disco interno como si fuera la USB"
    assert "dispositivo" in r.stdout.lower() or "usb" in r.stdout.lower(), r.stdout


# ======================================================= DEGRADACIÓN vs ESTRICTO --


def test_por_defecto_degrada_y_deja_arrancar_sin_voz(tmp_path):
    """AURA ya entrega los turnos en texto: un periférico no puede dejar al usuario sin producto."""
    raiz = _voz_falsa(tmp_path / "AURORA_EXT")
    r = _correr(["--verificar", "--degradar"], {"AURA_VOZ_RAIZ": str(raiz), "AURA_VOZ_ETIQUETA": "NO-EXISTE"})
    assert r.returncode == 0, "con --degradar el arranque no debe bloquearse"
    assert "VOZ NO DISPONIBLE" in r.stdout and "texto" in r.stdout.lower(), r.stdout


def test_con_exigir_voz_se_niega_a_arrancar_como_hace_D27(tmp_path):
    raiz = _voz_falsa(tmp_path / "AURORA_EXT")
    r = _correr(["--verificar", "--exigir-voz"], {"AURA_VOZ_RAIZ": str(raiz), "AURA_VOZ_ETIQUETA": "NO-EXISTE"})
    assert r.returncode != 0, "con --exigir-voz debe abortar"
    assert "ABORTADO" in r.stdout, r.stdout


# ======================================================= NO HACE DAÑO --


def test_el_lanzador_no_descarga_ni_copia_ni_instala():
    """Contrato explícito del acta: solo mira. Se comprueba sobre el propio texto del script."""
    texto = LANZADOR.read_text(encoding="utf-8")
    for prohibido in ("curl", "wget", "pip install", "ollama pull", "huggingface-cli", "cp -", "rsync"):
        assert prohibido not in texto, f"el lanzador contiene {prohibido!r}: debe limitarse a comprobar"
