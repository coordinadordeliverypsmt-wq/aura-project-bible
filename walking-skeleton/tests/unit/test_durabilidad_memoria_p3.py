"""DP-DURABILIDAD-MEMORIA, P3: `olvidar` y `marcar` atomicos respecto a la RAM.

Defecto (ficha P3): `olvidar` quitaba de `self._items` ANTES de anexar cada lapida; `marcar` mutaba
`provenance` de los objetos VIVOS antes de `_anexar`. Si `_anexar` fallaba a mitad (ENOSPC/EIO/fsync),
la sesion ya no mostraba lo olvidado / ya daba por refutado, pero el disco tenia solo parte de las
lapidas/marcas: al reiniciar reaparecia lo olvidado o volvia a darse por cierto lo refutado.

Regla P3: anexar TODAS las lapidas/marcas primero; solo si TODAS tuvieron exito, tocar la RAM
(`self._items`, el indice, `_conteo_usuario`, la procedencia en memoria). Si una anexion falla, el
error se propaga (INV-9) y la RAM queda exactamente como antes de la llamada. Lo ya escrito en disco
antes del fallo es historial append-only valido (no corrompe), pero no debe resucitar ni des-refutar
nada: la proyeccion sigue ganando por clave y la entrada en cuestion segun su ULTIMA linea legible.

Todo sobre `tmp_path`; nada toca `~/.aura`. T9/T11 (fallo en alto ante lo ilegible) no cambian.
"""

from __future__ import annotations

import errno

import pytest

from aura_skeleton.modules.memory import PersistentMemory

UID = "mauricio"


async def _tres(ruta) -> PersistentMemory:
    m = PersistentMemory(str(ruta))
    for t in ("perro se llama Toby", "cumple el 3 de junio", "vive en Bogota"):
        await m.write(UID, "semantica", t, {})
    return m


def _contenidos(m) -> list[str]:
    return sorted(i["content"] for i in m._items)


def _rompe_anexar_en_la_n_esima_vez(monkeypatch: pytest.MonkeyPatch, n: int) -> list[dict]:
    """Deja pasar las primeras `n - 1` llamadas a `_anexar` y rompe la numero `n` con OSError, como si
    fuera un fallo real de escritura (ENOSPC/EIO) dentro de `os.write`/fsync/el `opener`. Las llamadas
    posteriores a la rota NO deberian producirse si la implementacion anexa-todo-o-nada con early exit,
    pero por si acaso tambien se registran para poder afirmarlo con evidencia."""
    llamadas: list[dict] = []
    real = PersistentMemory._anexar

    def espia(self, item: dict) -> None:
        llamadas.append(dict(item))
        if len(llamadas) == n:
            raise OSError(errno.ENOSPC, "No queda espacio en el dispositivo")
        real(self, item)

    monkeypatch.setattr(PersistentMemory, "_anexar", espia)
    return llamadas


# ======================================================== olvidar: fallo a mitad ==================


@pytest.mark.asyncio
async def test_olvidar_con_fallo_en_la_2a_de_3_lapidas_no_olvida_nada_en_la_sesion(tmp_path, monkeypatch) -> None:
    """Control de lo que rompe: sin atomicidad, la primera lapida (Toby) SI se anexo con exito y el
    codigo viejo ya habria quitado las 3 de `self._items` antes de anexar ninguna, asi que la sesion
    mostraria 0 recuerdos olvidables aunque solo 1 de 3 bajas este confirmada en disco."""
    ruta = tmp_path / "memoria.json"
    m = await _tres(ruta)
    llamadas = _rompe_anexar_en_la_n_esima_vez(monkeypatch, n=2)

    def predicado(i: dict) -> bool:
        return True  # las 3 son olvidables

    with pytest.raises(OSError):
        m.olvidar(predicado)

    assert len(llamadas) == 2, "no debe seguir anexando lapidas tras el fallo (anexar-todo-o-nada)"
    assert _contenidos(m) == sorted(["perro se llama Toby", "cumple el 3 de junio", "vive en Bogota"]), (
        "fallo OSError: la sesion debe seguir mostrando TODO lo olvidable, no 0 ni 1"
    )


@pytest.mark.asyncio
async def test_olvidar_con_fallo_a_mitad_el_indice_no_queda_desalineado(tmp_path, monkeypatch) -> None:
    """Control de lo que rompe: si la RAM se tocara sin reconstruir el indice (o se tocara a medias),
    `recall` podria devolver posiciones que ya no corresponden a `self._items`, o perder entradas."""
    ruta = tmp_path / "memoria.json"
    m = await _tres(ruta)
    _rompe_anexar_en_la_n_esima_vez(monkeypatch, n=2)
    with pytest.raises(OSError):
        m.olvidar(lambda i: True)
    assert all(0 <= idx < len(m._items) for lst in m._indice.values() for idx in lst), (
        "el indice debe seguir apuntando dentro de los limites de _items"
    )
    hits = await m.recall(UID, "Toby", k=10)
    assert any(h["content"] == "perro se llama Toby" for h in hits), "recall debe seguir viendo lo no olvidado"


@pytest.mark.asyncio
async def test_olvidar_con_fallo_a_mitad_conteo_usuario_no_cambia(tmp_path, monkeypatch) -> None:
    ruta = tmp_path / "memoria.json"
    m = await _tres(ruta)
    antes = dict(m._conteo_usuario)
    _rompe_anexar_en_la_n_esima_vez(monkeypatch, n=2)
    with pytest.raises(OSError):
        m.olvidar(lambda i: True)
    assert m._conteo_usuario == antes, "la cota de seguridad del recall (D-M-1 A') no debe desviarse del contenido real"


@pytest.mark.asyncio
async def test_olvidar_con_fallo_a_mitad_disco_no_resucita_nada_distinto_al_reiniciar(tmp_path, monkeypatch) -> None:
    """Lo ya escrito en disco antes del fallo (1 lapida de 3) es historial append-only valido y no se
    borra retroactivamente (no hay rollback de disco, segun la ficha). Pero al reabrir, la proyeccion
    debe ganar por la ULTIMA linea de cada clave: la entrada con lapida parcial queda OLVIDADA (su
    ultima linea en disco es la lapida), y las otras 2 (sin ninguna lapida en disco) siguen VIVAS. No
    debe aparecer ninguna entrada duplicada ni ninguna resurreccion distinta de esto."""
    ruta = tmp_path / "memoria.json"
    m = await _tres(ruta)
    llamadas = _rompe_anexar_en_la_n_esima_vez(monkeypatch, n=2)
    with pytest.raises(OSError):
        m.olvidar(lambda i: True)
    primera_lapida_contenido = llamadas[0]["content"]

    reabierta = PersistentMemory(str(ruta))
    contenidos = _contenidos(reabierta)
    assert primera_lapida_contenido not in contenidos, "la unica lapida que SI llego a disco debe proyectarse olvidada"
    assert len(contenidos) == 2, "las otras 2 entradas (sin lapida en disco) deben seguir vivas, sin duplicados"


@pytest.mark.asyncio
async def test_olvidar_normal_sin_fallo_persiste_las_3_lapidas_y_sobrevive_al_reinicio(tmp_path) -> None:
    """Control verde: camino normal, sin ningun fallo inyectado."""
    ruta = tmp_path / "memoria.json"
    m = await _tres(ruta)
    assert m.olvidar(lambda i: True) == 3
    assert m._items == []
    reabierta = PersistentMemory(str(ruta))
    assert reabierta._items == []


@pytest.mark.asyncio
async def test_olvido_de_acciones_punto_d_sigue_funcionando(tmp_path) -> None:
    """Punto D: `olvidar_informacion_usuario` con `ambito='acciones'` llama a esta misma `olvidar`
    (via `EjecutorModeloUsuario._predicado_acciones`). La atomicidad no debe romper ese camino.
    Dos `resultado_accion` se escriben como los escribiria el ejecutor real: `kind=resultado_accion.KIND`,
    contenido serializado por `a_contenido`."""
    from aura_skeleton.core import resultado_accion
    from aura_skeleton.core.ejecutor_modelo_usuario import AMBITO_ACCIONES, _predicado_acciones

    ruta = tmp_path / "memoria.json"
    m = PersistentMemory(str(ruta))
    for i, (cap, res) in enumerate(
        (("encender_dispositivo", {"resultado": {}}), ("apagar_dispositivo", {"resultado": {}}))
    ):
        # trace_id distinto por registro: `leer` rechaza en bloque los trace_id que agrupan contenidos
        # DISTINTOS (fallo cerrado ante ambiguedad) y aqui cada accion es una ejecucion independiente.
        registro, motivo = resultado_accion.construir(cap, res, f"trace-{i}")
        assert registro is not None, motivo
        await m.write(UID, resultado_accion.KIND, resultado_accion.a_contenido(registro), {})
    assert len(resultado_accion.leer_auditando(m, UID)) == 2

    n = m.olvidar(_predicado_acciones(UID))
    assert n == 2
    assert resultado_accion.leer_auditando(m, UID) == []
    reabierta = PersistentMemory(str(ruta))
    assert resultado_accion.leer_auditando(reabierta, UID) == []
    assert AMBITO_ACCIONES == "acciones"


# ======================================================== marcar: fallo a mitad ===================


@pytest.mark.asyncio
async def test_marcar_con_fallo_en_la_2a_de_3_marcas_ninguna_queda_marcada_en_ram(tmp_path, monkeypatch) -> None:
    """Control de lo que rompe: el codigo viejo mutaba `i["provenance"]` de los objetos VIVOS ANTES de
    `_anexar`; si `_anexar` fallaba a mitad, la 1a y 2a entrada ya habrian quedado `refutada=True` en
    RAM aunque solo la 1a este confirmada en disco."""
    ruta = tmp_path / "memoria.json"
    m = await _tres(ruta)

    def predicado(i: dict) -> bool:
        return True  # las 3 son marcables

    _rompe_anexar_en_la_n_esima_vez(monkeypatch, n=2)
    with pytest.raises(OSError):
        m.marcar(predicado, {"refutada": True})

    marcadas_en_ram = [i for i in m._items if i.get("provenance", {}).get("refutada")]
    assert marcadas_en_ram == [], "fallo OSError a mitad: ninguna entrada debe quedar marcada en RAM"


@pytest.mark.asyncio
async def test_marcar_con_fallo_a_mitad_disco_conserva_la_marca_parcial_sin_resucitar_nada_raro(
    tmp_path, monkeypatch
) -> None:
    """La marca que SI llego a disco (1 de 3) es historial valido; al reabrir, esa entrada debe
    proyectarse MARCADA (su ultima linea gana), las otras 2 SIN marcar."""
    ruta = tmp_path / "memoria.json"
    m = await _tres(ruta)
    llamadas = _rompe_anexar_en_la_n_esima_vez(monkeypatch, n=2)
    with pytest.raises(OSError):
        m.marcar(lambda i: True, {"refutada": True})
    confirmada = llamadas[0]["content"]

    reabierta = PersistentMemory(str(ruta))
    por_contenido = {i["content"]: i for i in reabierta._items}
    assert por_contenido[confirmada]["provenance"].get("refutada") is True
    otras = [c for c in por_contenido if c != confirmada]
    assert all(not por_contenido[c]["provenance"].get("refutada") for c in otras)


@pytest.mark.asyncio
async def test_marcar_normal_sin_fallo_marca_las_3_y_sobrevive_al_reinicio(tmp_path) -> None:
    """Control verde."""
    ruta = tmp_path / "memoria.json"
    m = await _tres(ruta)
    assert m.marcar(lambda i: True, {"refutada": True}) == 3
    assert all(i["provenance"].get("refutada") for i in m._items)
    reabierta = PersistentMemory(str(ruta))
    assert all(i["provenance"].get("refutada") for i in reabierta._items)


@pytest.mark.asyncio
async def test_marcar_no_muta_el_dict_devuelto_antes_de_estar_en_disco(tmp_path, monkeypatch) -> None:
    """Si la implementacion mutara el dict vivo en RAM y LUEGO lo anexara, este test no distinguiria
    el orden; pero si falla ANTES de completar todas las anexiones, un dict vivo ya mutado se detecta
    por el test anterior. Este es el control positivo: sin fallo, la marca SI se aplica."""
    ruta = tmp_path / "memoria.json"
    m = await _tres(ruta)
    objetivo = next(i for i in m._items if i["content"] == "vive en Bogota")
    assert "refutada" not in objetivo.get("provenance", {})
    assert m.marcar(lambda i: i["content"] == "vive en Bogota", {"refutada": True}) == 1
    assert objetivo["provenance"]["refutada"] is True, "tras exito completo, el objeto vivo SI refleja la marca"


# ======================================================== idempotencia ============================


@pytest.mark.asyncio
async def test_olvidar_dos_veces_la_misma_entrada_es_idempotente(tmp_path) -> None:
    ruta = tmp_path / "memoria.json"
    m = await _tres(ruta)
    assert m.olvidar(lambda i: i["content"] == "vive en Bogota") == 1
    assert m.olvidar(lambda i: i["content"] == "vive en Bogota") == 0, "ya no esta en _items: no hay nada que olvidar"
    reabierta = PersistentMemory(str(ruta))
    assert "vive en Bogota" not in _contenidos(reabierta)


@pytest.mark.asyncio
async def test_marcar_dos_veces_la_misma_entrada_es_idempotente(tmp_path) -> None:
    ruta = tmp_path / "memoria.json"
    m = await _tres(ruta)
    assert m.marcar(lambda i: i["content"] == "vive en Bogota", {"refutada": True}) == 1
    assert m.marcar(lambda i: i["content"] == "vive en Bogota", {"refutada": True}) == 1, "se puede volver a marcar"
    reabierta = PersistentMemory(str(ruta))
    objetivo = next(i for i in reabierta._items if i["content"] == "vive en Bogota")
    assert objetivo["provenance"]["refutada"] is True
