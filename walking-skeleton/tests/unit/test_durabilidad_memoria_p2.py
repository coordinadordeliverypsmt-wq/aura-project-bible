"""DP-DURABILIDAD-MEMORIA, P2-B: tolerancia SELECTIVA de una linea cortada.

Se tolera (y se deja constancia) solo un fragmento con forma de corte que NO puede ser el comienzo de una linea con la
clave `(user_id, kind, content)` de una linea existente: no puede ser lapida (`olvidar`) ni marca (`marcar`), asi que
ignorarlo no resucita ni des-refuta nada. Todo lo ambiguo sigue fallando en alto (T9). Todo sobre `tmp_path`.
"""

from __future__ import annotations

import json
import os

import pytest

from aura_skeleton import observability as obs
from aura_skeleton.core.reloj_cm2 import MemoriaNoLegible, _MemoriaSoloLectura
from aura_skeleton.modules.memory import PersistentMemory

UID = "mauricio"


@pytest.fixture
def audit(tmp_path):
    a = obs.configure_audit(str(tmp_path / "audit.jsonl"))
    yield a
    obs.reset_audit()


def _tolerancias(a) -> list[dict]:
    return [r for r in a.reconstruir() if r.get("evento") == "memoria.linea_truncada_tolerada"]


async def _tres(ruta) -> PersistentMemory:
    m = PersistentMemory(str(ruta))
    for t in ("perro se llama Toby", "cumple el 3 de junio", "vive en Bogota"):
        await m.write(UID, "semantica", t, {})
    return m


def _contenidos(m) -> list[str]:
    return sorted(i["content"] for i in m._items)


def _cortar(ruta, linea: dict, n: int) -> None:
    """Anexa los primeros `n` caracteres de la serializacion real de `linea` (corte a media escritura)."""
    with open(ruta, "a", encoding="utf-8") as f:
        f.write(json.dumps(linea, ensure_ascii=False)[:n])


# --- se tolera: escritura NUEVA cortada --------------------------------------------------------


@pytest.mark.asyncio
async def test_fragmento_de_un_recuerdo_nuevo_se_tolera_y_los_validos_siguen(tmp_path, audit) -> None:
    ruta = tmp_path / "memoria.json"
    await _tres(ruta)
    nuevo = {"user_id": UID, "kind": "semantica", "content": "le gusta el cafe", "provenance": {}}
    _cortar(ruta, nuevo, 61)  # corta dentro del content ("le g"): la clave nueva ya es distinta de todas
    previo = ruta.read_bytes()
    m = PersistentMemory(str(ruta))
    assert _contenidos(m) == sorted(["perro se llama Toby", "cumple el 3 de junio", "vive en Bogota"])
    (t,) = _tolerancias(audit)
    assert t["bytes"] == 61 and t["linea"] == 4, "constancia: tamano y posicion del fragmento"
    assert "sha256" not in t and "le g" not in json.dumps(t), "constancia sin contenido ni huella reversible"
    assert ruta.read_bytes() == previo, "abrir no escribe"


@pytest.mark.asyncio
async def test_tras_tolerar_la_siguiente_escritura_cierra_la_cola_sin_borrar_bytes(tmp_path, audit) -> None:
    ruta = tmp_path / "memoria.json"
    await _tres(ruta)
    _cortar(ruta, {"user_id": UID, "kind": "semantica", "content": "le gusta el cafe", "provenance": {}}, 60)
    previo = ruta.read_bytes()
    m = PersistentMemory(str(ruta))
    await m.write(UID, "semantica", "trabaja de noche", {})
    assert ruta.read_bytes().startswith(previo), "append-only: el fragmento sigue en disco"
    for _ in range(2):  # reabrir dos veces: idempotente, sin duplicados
        r = PersistentMemory(str(ruta))
        assert _contenidos(r) == sorted(
            ["perro se llama Toby", "cumple el 3 de junio", "vive en Bogota", "trabaja de noche"]
        )


@pytest.mark.asyncio
async def test_escritura_parcial_en_la_sesion_no_se_fusiona_con_la_siguiente(tmp_path, audit, monkeypatch) -> None:
    """Riesgo residual de P1: disco lleno a media linea y la sesion sigue."""
    ruta = tmp_path / "memoria.json"
    m = await _tres(ruta)
    real_open = open

    class _Parcial:
        def __init__(self, f):
            self._f = f

        def __enter__(self):
            return self

        def __exit__(self, *a):
            self._f.close()

        def write(self, datos: str) -> int:
            self._f.write(datos[: self.corte])
            self._f.flush()
            raise OSError(28, "No queda espacio en el dispositivo")

    _Parcial.corte = 70  # tras el comienzo del content: la clave ya no coincide con ninguna existente
    from aura_skeleton.modules import memory as memmod

    with monkeypatch.context() as mp:
        mp.setattr(
            memmod,
            "open",
            lambda p, modo="r", **k: _Parcial(real_open(p, modo, **k)) if modo == "a" else real_open(p, modo, **k),
            raising=False,
        )
        with pytest.raises(OSError):
            await m.write(UID, "semantica", "fragmento sin confirmar", {})
    await m.write(UID, "semantica", "despues del disco lleno", {})
    r = PersistentMemory(str(ruta))
    assert "despues del disco lleno" in _contenidos(r) and "fragmento sin confirmar" not in _contenidos(r)


@pytest.mark.asyncio
async def test_limitacion_un_corte_previo_a_la_clave_sigue_fallando_en_alto_al_reabrir(tmp_path, audit) -> None:
    """Limitacion declarada: un corte antes de que la clave se distinga no se distingue de una lapida cortada.
    La sesion puede seguir escribiendo (la cola se cierra), pero al reabrir falla en alto, como exige T9."""
    ruta = tmp_path / "memoria.json"
    m = await _tres(ruta)
    _cortar(ruta, {"user_id": UID, "kind": "semantica", "content": "otra cosa", "provenance": {}}, 40)
    await m.write(UID, "semantica", "sigue escribiendo", {})
    with pytest.raises(json.JSONDecodeError):
        PersistentMemory(str(ruta))


@pytest.mark.asyncio
async def test_memoria_que_solo_tiene_un_fragmento_abre_vacia(tmp_path, audit) -> None:
    ruta = tmp_path / "memoria.json"
    _cortar(ruta, {"user_id": UID, "kind": "semantica", "content": "x", "provenance": {}}, 20)
    assert PersistentMemory(str(ruta))._items == [] and len(_tolerancias(audit)) == 1


# --- NO se tolera: ambiguo o corrupto (T9 intacto) ---------------------------------------------


@pytest.mark.asyncio
async def test_lapida_cortada_tras_la_clave_sigue_fallando_en_alto(tmp_path, audit) -> None:
    ruta = tmp_path / "memoria.json"
    m = await _tres(ruta)
    m.olvidar(lambda i: i["content"] == "vive en Bogota")
    texto = ruta.read_text(encoding="utf-8")
    ruta.write_text(texto[: len(texto) - 8], encoding="utf-8")  # solo falta la cola de la lapida
    with pytest.raises(json.JSONDecodeError):
        PersistentMemory(str(ruta))
    with pytest.raises(MemoriaNoLegible):
        _MemoriaSoloLectura(str(ruta))
    assert _tolerancias(audit) == []


@pytest.mark.asyncio
async def test_marca_cortada_sigue_fallando_en_alto(tmp_path, audit) -> None:
    ruta = tmp_path / "memoria.json"
    m = await _tres(ruta)
    m.marcar(lambda i: i["content"] == "cumple el 3 de junio", {"refutada": True})
    texto = ruta.read_text(encoding="utf-8")
    ruta.write_text(texto[: len(texto) - 6], encoding="utf-8")
    with pytest.raises(json.JSONDecodeError):
        PersistentMemory(str(ruta))


@pytest.mark.asyncio
@pytest.mark.parametrize("n", [1, 5, 14, 30, 45, 52, 80])
async def test_fragmento_compatible_con_una_clave_existente_falla_en_alto(tmp_path, audit, n) -> None:
    """Cortes tempranos (antes de que la clave se distinga) o de una linea con la MISMA clave: ambiguos."""
    ruta = tmp_path / "memoria.json"
    await _tres(ruta)
    _cortar(ruta, {"user_id": UID, "kind": "semantica", "content": "vive en Bogota", "provenance": {"x": 1}}, n)
    with pytest.raises(json.JSONDecodeError):
        PersistentMemory(str(ruta))


@pytest.mark.asyncio
@pytest.mark.parametrize("basura", ['{"user_id": "mauricio", roto}', "esto no es json", '["x"'])
async def test_linea_corrupta_sin_forma_de_corte_falla_en_alto(tmp_path, audit, basura) -> None:
    ruta = tmp_path / "memoria.json"
    await _tres(ruta)
    with open(ruta, "a", encoding="utf-8") as f:
        f.write(basura)
    with pytest.raises(json.JSONDecodeError):
        PersistentMemory(str(ruta))


@pytest.mark.asyncio
async def test_linea_con_otro_orden_de_claves_hace_ambiguo_todo_fragmento(tmp_path, audit) -> None:
    ruta = tmp_path / "memoria.json"
    await _tres(ruta)
    with open(ruta, "a", encoding="utf-8") as f:
        f.write(json.dumps({"kind": "semantica", "user_id": UID, "content": "orden raro", "provenance": {}}) + "\n")
    _cortar(ruta, {"user_id": UID, "kind": "semantica", "content": "le gusta el cafe", "provenance": {}}, 60)
    with pytest.raises(json.JSONDecodeError):
        PersistentMemory(str(ruta))


# --- el reloj de CM2 lee exactamente igual -----------------------------------------------------


@pytest.mark.asyncio
async def test_el_reloj_tolera_lo_mismo_y_ve_las_mismas_entradas(tmp_path, audit) -> None:
    ruta = tmp_path / "memoria.json"
    await _tres(ruta)
    _cortar(ruta, {"user_id": UID, "kind": "semantica", "content": "le gusta el cafe", "provenance": {}}, 60)
    assert sorted(i["content"] for i in _MemoriaSoloLectura(str(ruta))._items) == _contenidos(
        PersistentMemory(str(ruta))
    )


def test_control_memoria_sana_sin_constancia(tmp_path, audit) -> None:
    ruta = tmp_path / "memoria.json"
    ruta.write_text(json.dumps({"user_id": UID, "kind": "k", "content": "c", "provenance": {}}) + "\n")
    assert len(PersistentMemory(str(ruta))._items) == 1 and _tolerancias(audit) == []
    assert os.path.getsize(ruta) > 0


@pytest.mark.asyncio
@pytest.mark.parametrize("sep", [" ", " ", "\x85", "\x1c", "\x1e", "\x0b", "\x0c"])
async def test_recuerdo_con_separador_unicode_sobrevive_al_reinicio_sin_tolerancias(tmp_path, audit, sep) -> None:
    """json.dumps(ensure_ascii=False) NO escapa estos separadores y str.splitlines() SI corta en ellos: el unico
    separador de lineas del fichero es '\\n'. Antes de P2 la memoria no abria; con splitlines se perderia el recuerdo."""
    ruta = tmp_path / "memoria.json"
    m = PersistentMemory(str(ruta))
    texto = f"linea uno{sep}{{ sigue"
    await m.write(UID, "semantica", texto, {})
    await m.write(UID, "semantica", "normal", {})
    assert sorted(i["content"] for i in PersistentMemory(str(ruta))._items) == sorted([texto, "normal"])
    assert sorted(i["content"] for i in _MemoriaSoloLectura(str(ruta))._items) == sorted([texto, "normal"])
    assert _tolerancias(audit) == []


@pytest.mark.asyncio
async def test_mas_fragmentos_que_el_tope_es_corrupcion_y_falla_en_alto(tmp_path, audit) -> None:
    """Una interrupcion real deja como mucho un fragmento; muchos son corrupcion (y acotan el coste de la lectura)."""
    from aura_skeleton.modules import memory as memmod

    ruta = tmp_path / "memoria.json"
    await _tres(ruta)
    for i in range(memmod._MAX_FRAGMENTOS_TOLERADOS + 1):
        _cortar(ruta, {"user_id": UID, "kind": "semantica", "content": f"nuevo {i} x", "provenance": {}}, 63)
        with open(ruta, "a", encoding="utf-8") as f:
            f.write("\n")
    with pytest.raises(json.JSONDecodeError):
        PersistentMemory(str(ruta))


@pytest.mark.asyncio
async def test_control_hasta_el_tope_de_fragmentos_se_tolera(tmp_path, audit) -> None:
    from aura_skeleton.modules import memory as memmod

    ruta = tmp_path / "memoria.json"
    await _tres(ruta)
    for i in range(memmod._MAX_FRAGMENTOS_TOLERADOS):
        _cortar(ruta, {"user_id": UID, "kind": "semantica", "content": f"nuevo {i} x", "provenance": {}}, 63)
        with open(ruta, "a", encoding="utf-8") as f:
            f.write("\n")
    assert len(PersistentMemory(str(ruta))._items) == 3
    assert len(_tolerancias(audit)) == memmod._MAX_FRAGMENTOS_TOLERADOS


def _w(contenido: str, **extra) -> str:
    return json.dumps(
        {"user_id": "u", "kind": "k", "content": contenido, "provenance": {}, **extra}, ensure_ascii=False
    )


def test_lapida_corrupta_a_mitad_de_fichero_no_se_tolera_ni_resucita(tmp_path, audit) -> None:
    """Auditoria adversarial, caso A: una comilla perdida dentro de una lapida (corrupcion, no corte) tiene
    'forma de corte' y no es prefijo de ninguna clave; tolerarla resucitaria lo olvidado. Debe fallar en alto."""
    lapida = _w("secreto", _olvidada=True).replace('"secreto"', '"secreto')
    ruta = tmp_path / "memoria.json"
    ruta.write_text(_w("secreto") + "\n" + lapida + "\n" + _w("otro") + "\n", encoding="utf-8")
    with pytest.raises(json.JSONDecodeError):
        PersistentMemory(str(ruta))
    with pytest.raises(MemoriaNoLegible):
        _MemoriaSoloLectura(str(ruta))


def test_fusion_legada_de_lapida_cortada_con_la_linea_siguiente_falla_en_alto(tmp_path, audit) -> None:
    """Caso B: fichero escrito antes del cierre de cola: lapida cortada + linea siguiente en la MISMA linea."""
    lapida = _w("secreto", _olvidada=True)
    cortada = lapida[: lapida.index("secreto") + 3]
    ruta = tmp_path / "memoria.json"
    ruta.write_text(_w("secreto") + "\n" + cortada + _w("otro") + "\n", encoding="utf-8")
    with pytest.raises(json.JSONDecodeError):
        PersistentMemory(str(ruta))


@pytest.mark.parametrize("cola", ["\\", "\\u00", "tru"])
def test_cortes_en_mitad_de_token_fallan_en_alto_por_prudencia(tmp_path, audit, cola) -> None:
    """Un corte dentro de un escape o de un literal no es un prefijo JSON demostrable: falla en alto (disponibilidad,
    nunca integridad)."""
    ruta = tmp_path / "memoria.json"
    ruta.write_text(_w("a") + "\n" + '{"user_id": "u", "kind": "k", "content": "nuevo", ' + cola, encoding="utf-8")
    with pytest.raises(json.JSONDecodeError):
        PersistentMemory(str(ruta))


def test_linea_que_no_es_objeto_falla_de_forma_controlada(tmp_path, audit) -> None:
    ruta = tmp_path / "memoria.json"
    ruta.write_text(_w("a") + "\n[1, 2]\n" + '{"user_id": "u", "kind": "k", "content": "nue', encoding="utf-8")
    with pytest.raises(json.JSONDecodeError):
        PersistentMemory(str(ruta))


@pytest.mark.asyncio
async def test_restore_conserva_un_recuerdo_con_separador_unicode(tmp_path, audit) -> None:
    ruta = tmp_path / "memoria.json"
    m = PersistentMemory(str(ruta))
    await m.write(UID, "semantica", "a b", {})
    nombre = m.backup()
    assert m.restore(nombre) is True
    assert [i["content"] for i in PersistentMemory(str(ruta))._items] == ["a b"]
