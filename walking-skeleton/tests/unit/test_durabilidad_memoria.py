"""DP-DURABILIDAD-MEMORIA, P1: un recuerdo dado por guardado esta en disco; uno fallido no queda en la sesion.

Todo sobre `tmp_path`; nada toca `~/.aura`. T9 (linea final truncada => falla en alto) NO cambia: vive en
`tests/integration/test_olvido_adversarial.py` y sigue verde.
"""

from __future__ import annotations

import errno
import json
import os
import stat

import pytest

from aura_skeleton.modules import memory as memmod
from aura_skeleton.modules.memory import PersistentMemory

UID = "mauricio"


def _espiar_fsync(monkeypatch: pytest.MonkeyPatch, eventos: list[tuple[str, str]]) -> None:
    real = os.fsync

    def espia(fd: int) -> None:
        modo = os.fstat(fd).st_mode
        eventos.append(("fsync", "dir" if stat.S_ISDIR(modo) else "fichero"))
        real(fd)

    monkeypatch.setattr(memmod.os, "fsync", espia)


async def _recuerda(m: PersistentMemory, texto: str) -> bool:
    return any(h["content"] == texto for h in await m.recall(UID, texto, k=10))


# --- fsync -------------------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cada_write_hace_fsync_del_fichero(tmp_path, monkeypatch) -> None:
    m = PersistentMemory(str(tmp_path / "memoria.json"))
    await m.write(UID, "semantica", "primero", {})
    eventos: list[tuple[str, str]] = []
    _espiar_fsync(monkeypatch, eventos)
    await m.write(UID, "semantica", "segundo", {})
    assert ("fsync", "fichero") in eventos
    assert ("fsync", "dir") not in eventos, "control: anexar a un fichero existente no toca el directorio"


@pytest.mark.asyncio
async def test_crear_el_fichero_sincroniza_el_directorio(tmp_path, monkeypatch) -> None:
    m = PersistentMemory(str(tmp_path / "memoria.json"))
    eventos: list[tuple[str, str]] = []
    _espiar_fsync(monkeypatch, eventos)
    await m.write(UID, "semantica", "nace el fichero", {})
    assert eventos.count(("fsync", "dir")) == 1


@pytest.mark.asyncio
async def test_fsync_fallido_el_write_lanza_y_el_recuerdo_no_queda(tmp_path, monkeypatch) -> None:
    ruta = tmp_path / "memoria.json"
    m = PersistentMemory(str(ruta))
    await m.write(UID, "semantica", "historico valido", {})

    def fsync_roto(fd: int) -> None:
        raise OSError(errno.EIO, "fsync fallido")

    with monkeypatch.context() as mp:
        mp.setattr(memmod.os, "fsync", fsync_roto)
        with pytest.raises(OSError):
            await m.write(UID, "semantica", "no confirmado", {})
    assert not await _recuerda(m, "no confirmado"), "la sesion no debe recordar lo que no se confirmo"
    assert await _recuerda(m, "historico valido")
    await m.write(UID, "semantica", "despues del fallo", {})
    reabierta = PersistentMemory(str(ruta))
    assert await _recuerda(reabierta, "historico valido") and await _recuerda(reabierta, "despues del fallo")


class _FicheroLleno:
    def __enter__(self):
        return self

    def __exit__(self, *_a: object) -> None:
        return None

    def write(self, _datos: str) -> int:
        raise OSError(errno.ENOSPC, "No queda espacio en el dispositivo")


@pytest.mark.asyncio
async def test_disco_lleno_el_write_lanza_y_no_queda_en_la_sesion_ni_en_disco(tmp_path, monkeypatch) -> None:
    ruta = tmp_path / "memoria.json"
    m = PersistentMemory(str(ruta))
    await m.write(UID, "semantica", "historico valido", {})
    antes = ruta.read_bytes()
    monkeypatch.setattr(memmod, "open", lambda *_a, **_k: _FicheroLleno(), raising=False)
    with pytest.raises(OSError):
        await m.write(UID, "semantica", "sin espacio", {})
    monkeypatch.delattr(memmod, "open", raising=False)
    assert not await _recuerda(m, "sin espacio")
    assert m._conteo_usuario[UID] == 1, "el conteo derivado tampoco cuenta el write fallido"
    assert ruta.read_bytes() == antes, "el historico no cambia"


@pytest.mark.asyncio
async def test_persist_sincroniza_el_tmp_antes_del_replace_y_el_directorio_despues(tmp_path, monkeypatch) -> None:
    m = PersistentMemory(str(tmp_path / "memoria.json"))
    await m.write(UID, "semantica", "a respaldar", {})
    eventos: list[tuple[str, str]] = []
    _espiar_fsync(monkeypatch, eventos)
    real_replace = os.replace
    monkeypatch.setattr(memmod.os, "replace", lambda a, b: (eventos.append(("replace", "")), real_replace(a, b))[1])
    m.backup()  # usa _persist
    i = eventos.index(("replace", ""))
    assert ("fsync", "fichero") in eventos[:i], "el .tmp debe estar en disco antes de renombrarlo"
    assert ("fsync", "dir") in eventos[i + 1 :], "el rename debe ser duradero"


# --- controles y compatibilidad ---------------------------------------------------------------


def test_control_memoria_vacia_abre_sin_crear_el_fichero(tmp_path) -> None:
    ruta = tmp_path / "memoria.json"
    m = PersistentMemory(str(ruta))
    assert m._items == [] and not ruta.exists()


@pytest.mark.asyncio
async def test_control_historico_valido_sobrevive_al_reinicio_con_formato_identico(tmp_path) -> None:
    ruta = tmp_path / "memoria.json"
    m = PersistentMemory(str(ruta))
    for t in ("uno", "dos", "tres"):
        await m.write(UID, "semantica", t, {"trace_id": "t"})
    lineas = ruta.read_text(encoding="utf-8").splitlines(keepends=True)
    esperado = {"user_id": UID, "kind": "semantica", "content": "uno", "provenance": {"trace_id": "t"}}
    assert lineas[0] == json.dumps(esperado, ensure_ascii=False) + "\n", "formato de linea sin cambios"
    reabierta = PersistentMemory(str(ruta))
    assert [i["content"] for i in reabierta._items] == ["uno", "dos", "tres"]


@pytest.mark.asyncio
async def test_fsync_de_directorio_fallido_lanza_y_se_reintenta_en_el_siguiente_write(tmp_path, monkeypatch) -> None:
    """Si sincronizar el directorio falla al crear el fichero, write lanza y el siguiente write lo REINTENTA:
    no se puede dar exito con la entrada de directorio sin confirmar."""
    ruta = tmp_path / "memoria.json"
    m = PersistentMemory(str(ruta))
    real = os.fsync

    def fsync_dir_roto(fd: int) -> None:
        if stat.S_ISDIR(os.fstat(fd).st_mode):
            raise OSError(errno.EIO, "fsync de directorio fallido")
        real(fd)

    with monkeypatch.context() as mp:
        mp.setattr(memmod.os, "fsync", fsync_dir_roto)
        with pytest.raises(OSError):
            await m.write(UID, "semantica", "primero", {})
    assert not await _recuerda(m, "primero"), "write lanzo: la sesion no lo da por guardado"
    eventos: list[tuple[str, str]] = []
    _espiar_fsync(monkeypatch, eventos)
    await m.write(UID, "semantica", "segundo", {})
    assert ("fsync", "dir") in eventos, "el fsync de directorio pendiente se reintenta"
    reabierta = PersistentMemory(str(ruta))
    assert await _recuerda(reabierta, "segundo")


@pytest.mark.asyncio
async def test_persist_con_fsync_fallido_lanza_y_no_reemplaza_el_original(tmp_path, monkeypatch) -> None:
    ruta = tmp_path / "memoria.json"
    m = PersistentMemory(str(ruta))
    await m.write(UID, "semantica", "original", {})
    antes = ruta.read_bytes()
    reemplazos: list[str] = []
    monkeypatch.setattr(memmod.os, "replace", lambda a, b: reemplazos.append(b))

    def fsync_roto(fd: int) -> None:
        raise OSError(errno.EIO, "fsync fallido")

    monkeypatch.setattr(memmod.os, "fsync", fsync_roto)
    with pytest.raises(OSError):
        m.backup()
    assert reemplazos == [] and ruta.read_bytes() == antes, "sin fsync del .tmp no hay rename: el original intacto"
