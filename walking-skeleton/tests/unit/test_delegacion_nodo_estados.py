"""M-3 (estados persistentes del nodo), B-4 (almacén endurecido) y N1 (orden, concurrencia, persistencia).

La ejecución es *at-most-once*: tras una caída, una ejecución EJECUTANDO sin COMPLETADA es AMBIGUA y JAMÁS se
re-ejecuta sola. Cada prueba lleva su control positivo.
"""

from __future__ import annotations

import base64
import json
import multiprocessing
import os
import stat
import threading
from pathlib import Path
from typing import Any

import pytest

from aura_skeleton.adapters.almacen_consumidas import NOMBRE, NOMBRE_EJECUCIONES, AlmacenConsumidas
from aura_skeleton.core import delegacion_nodo
from aura_skeleton.core.delegacion import (
    Capacidad,
    EstadoNodo,
    Motivo,
    RechazoOrden,
    validar_orden,
)
from aura_skeleton.core.delegacion_nodo import NodoDelegado
from tests.delegacion_apoyo import T0, Mundo, campos_validos, firmante_orden, mundo
from tests.unit.test_delegacion_diario_hc1 import _EspiaFsync


class Contador:
    """Capacidad de PRUEBA que cuenta (en un fichero, visible entre procesos) cuántas veces se ejecuta de verdad."""

    def __init__(self, ruta: Path, falla: bool = False) -> None:
        self.ruta, self.falla = ruta, falla

    def ejecutar(self, args: Any) -> str:
        fd = os.open(self.ruta, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
        os.write(fd, b"x\n")
        os.close(fd)
        if self.falla:
            raise RuntimeError("fallo de la capacidad")
        return "0" * 64

    @property
    def veces(self) -> int:
        return self.ruta.read_text().count("\n") if self.ruta.exists() else 0


@pytest.fixture
def contador(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Contador:
    cont = Contador(tmp_path / "ejecuciones.cuenta")
    cap = Capacidad("calcular_resumen_sha256", lambda a: dict(a), cont.ejecutar, lambda a, s: True, idempotente=True)
    monkeypatch.setattr(delegacion_nodo, "CAPACIDADES", {"calcular_resumen_sha256": cap})
    return cont


class Escena:
    def __init__(self, tmp_path: Path) -> None:
        self.dir = tmp_path / "nodo"
        self.m: Mundo = mundo()
        campos = campos_validos()
        self.sobre = firmante_orden(self.m.hc1, campos)
        self.ident = campos["id_ejecucion"]
        self.almacen = AlmacenConsumidas(self.dir)
        self.nodo = self.nuevo_nodo(self.almacen)

    def nuevo_nodo(self, almacen: AlmacenConsumidas) -> NodoDelegado:
        return NodoDelegado(self.m.politica(), self.m.verificador_hc1(), almacen, self.m.nodo.firmar)

    def reiniciar(self) -> tuple[AlmacenConsumidas, NodoDelegado]:
        """Proceso nuevo: almacén e instancia nuevos sobre el mismo directorio."""
        self.almacen = AlmacenConsumidas(self.dir)
        self.nodo = self.nuevo_nodo(self.almacen)
        return self.almacen, self.nodo


# --- máquina de estados ------------------------------------------------------------------------------------


def test_estados_consumida_ejecutando_completada_con_resultado_guardado(tmp_path: Path, contador: Contador) -> None:
    e = Escena(tmp_path)
    assert e.almacen.estado(e.ident) is None  # nunca vista
    ac = e.nodo.aceptar(e.sobre)
    assert e.almacen.estado(e.ident) is EstadoNodo.CONSUMIDA
    e.almacen.iniciar_ejecucion(e.ident)
    assert e.almacen.estado(e.ident) is EstadoNodo.EJECUTANDO  # en esta instancia, ejecutando de verdad
    e.almacen.fallar(e.ident)
    assert e.almacen.estado(e.ident) is EstadoNodo.FALLIDA
    e2 = Escena(tmp_path / "limpio")
    ac2 = e2.nodo.aceptar(e2.sobre)
    res = e2.nodo.ejecutar(ac2.orden)
    assert e2.almacen.estado(e2.ident) is EstadoNodo.COMPLETADA
    assert e2.almacen.resultado_guardado(e2.ident) == res
    assert ac.orden.campos["id_ejecucion"] == e.ident and contador.veces == 1


def test_una_segunda_llamada_a_ejecutar_sobre_la_misma_orden_se_rechaza_en_la_misma_instancia(
    tmp_path: Path, contador: Contador
) -> None:
    e = Escena(tmp_path)
    ac = e.nodo.aceptar(e.sobre)
    primero = e.nodo.ejecutar(ac.orden)  # control: la primera sí
    assert contador.veces == 1
    with pytest.raises(RechazoOrden) as err:
        e.nodo.ejecutar(ac.orden)
    assert err.value.motivo is Motivo.EJECUCION_REPETIDA
    assert contador.veces == 1  # la capacidad NO volvió a correr
    assert e.nodo.reenviar_resultado(e.ident) == primero


def test_el_resultado_guardado_se_reenvia_idempotente_tras_reiniciar(tmp_path: Path, contador: Contador) -> None:
    e = Escena(tmp_path)
    res = e.nodo.ejecutar(e.nodo.aceptar(e.sobre).orden)
    _, nodo2 = e.reiniciar()
    assert nodo2.reenviar_resultado(e.ident) == res  # mismos bytes firmados, no una ejecución nueva
    assert nodo2.reenviar_resultado(e.ident) == res
    assert nodo2.estado(e.ident) is EstadoNodo.COMPLETADA and contador.veces == 1
    with pytest.raises(RechazoOrden) as err:
        nodo2.aceptar(e.sobre)  # y la orden sigue sin poder volver a aceptarse
    assert err.value.motivo is Motivo.ORDEN_REPETIDA


def test_tras_una_caida_ejecutando_es_ambigua_y_nunca_se_reejecuta(tmp_path: Path, contador: Contador) -> None:
    e = Escena(tmp_path)
    ac = e.nodo.aceptar(e.sobre)
    e.almacen.iniciar_ejecucion(e.ident)  # el nodo empezó a ejecutar... y murió antes de `completar`
    assert e.almacen.estado(e.ident) is EstadoNodo.EJECUTANDO  # control: MIENTRAS vive, sigue ejecutando
    almacen, nodo = e.reiniciar()
    assert almacen.estado(e.ident) is EstadoNodo.AMBIGUA
    with pytest.raises(RechazoOrden) as err:
        nodo.ejecutar(ac.orden)
    assert err.value.motivo is Motivo.EJECUCION_AMBIGUA
    with pytest.raises(RechazoOrden) as err2:
        nodo.aceptar(e.sobre)
    assert err2.value.motivo is Motivo.ORDEN_REPETIDA
    assert nodo.reenviar_resultado(e.ident) is None  # no hay resultado que reenviar
    assert contador.veces == 0  # JAMÁS se ejecutó
    almacen3, _ = e.reiniciar()  # y sigue ambigua en cada reinicio posterior
    assert almacen3.estado(e.ident) is EstadoNodo.AMBIGUA


def test_una_ejecucion_que_falla_queda_fallida_y_no_se_reintenta_sola(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cont = Contador(tmp_path / "cuenta", falla=True)
    cap = Capacidad("calcular_resumen_sha256", lambda a: dict(a), cont.ejecutar, lambda a, s: True, idempotente=True)
    monkeypatch.setattr(delegacion_nodo, "CAPACIDADES", {"calcular_resumen_sha256": cap})
    e = Escena(tmp_path)
    ac = e.nodo.aceptar(e.sobre)
    with pytest.raises(RuntimeError):
        e.nodo.ejecutar(ac.orden)
    assert e.almacen.estado(e.ident) is EstadoNodo.FALLIDA and cont.veces == 1
    with pytest.raises(RechazoOrden) as err:
        e.nodo.ejecutar(ac.orden)
    assert err.value.motivo is Motivo.EJECUCION_REPETIDA and cont.veces == 1
    assert e.reiniciar()[0].estado(e.ident) is EstadoNodo.FALLIDA


def test_no_se_puede_ejecutar_lo_que_no_se_consumio(tmp_path: Path) -> None:
    almacen = AlmacenConsumidas(tmp_path / "nodo")
    with pytest.raises(RechazoOrden) as err:
        almacen.iniciar_ejecucion("11111111-1111-4111-8111-111111111111")
    assert err.value.motivo is Motivo.EJECUCION_DESCONOCIDA
    almacen.consumir("11111111-1111-4111-8111-111111111111", 1)
    almacen.iniciar_ejecucion("11111111-1111-4111-8111-111111111111")  # control
    with pytest.raises(RechazoOrden) as err2:
        almacen.completar("22222222-2222-4222-8222-222222222222", b"x")  # nunca empezó
    assert err2.value.motivo is Motivo.EJECUCION_NO_EN_CURSO


# --- concurrencia: exactamente una ejecución ----------------------------------------------------------------


def test_n1_muchos_hilos_con_la_misma_orden_ejecutan_exactamente_una_vez(tmp_path: Path, contador: Contador) -> None:
    e = Escena(tmp_path)
    ac = e.nodo.aceptar(e.sobre)
    # instancias DISTINTAS sobre el mismo directorio: el cerrojo de fichero, no el de la instancia, es lo que decide
    nodos = [e.nuevo_nodo(AlmacenConsumidas(e.dir)) for _ in range(8)]
    resultados: list[object] = []

    def intentar(n: NodoDelegado) -> None:
        try:
            n.ejecutar(ac.orden)
            resultados.append("ok")
        except RechazoOrden as err:
            resultados.append(err.motivo)

    hilos = [threading.Thread(target=intentar, args=(n,)) for n in nodos]
    for h in hilos:
        h.start()
    for h in hilos:
        h.join()
    assert resultados.count("ok") == 1 and contador.veces == 1
    assert all(r in ("ok", Motivo.EJECUCION_REPETIDA, Motivo.EJECUCION_AMBIGUA) for r in resultados)


def test_n1_muchos_hilos_validando_la_misma_orden_aceptan_exactamente_una(tmp_path: Path) -> None:
    m = mundo()
    sobre = firmante_orden(m.hc1, campos_validos())
    resultados: list[object] = []

    def intentar() -> None:
        try:
            validar_orden(
                sobre, politica=m.politica(), verificar=m.verificador_hc1(), almacen=AlmacenConsumidas(tmp_path / "n")
            )
            resultados.append("ok")
        except RechazoOrden as err:
            resultados.append(err.motivo)

    hilos = [threading.Thread(target=intentar) for _ in range(10)]
    for h in hilos:
        h.start()
    for h in hilos:
        h.join()
    assert resultados.count("ok") == 1 and resultados.count(Motivo.ORDEN_REPETIDA) == 9


def _ejecutar_en_proceso(args: tuple[str, str], q: Any, orden: Any, ruta_cuenta: str) -> None:
    from aura_skeleton.core import delegacion_nodo as dn

    cont = Contador(Path(ruta_cuenta))
    dn.CAPACIDADES = {  # type: ignore[assignment,misc]
        "calcular_resumen_sha256": Capacidad(
            "calcular_resumen_sha256", lambda a: dict(a), cont.ejecutar, lambda a, s: True, idempotente=True
        )
    }
    m = mundo()
    nodo = NodoDelegado(m.politica(), m.verificador_hc1(), AlmacenConsumidas(Path(args[0])), m.nodo.firmar)
    try:
        nodo.ejecutar(orden)
        q.put("ok")
    except RechazoOrden as err:
        q.put(err.motivo.value)


def test_n1_procesos_distintos_con_la_misma_orden_ejecutan_exactamente_una_vez(
    tmp_path: Path, contador: Contador
) -> None:
    e = Escena(tmp_path)
    ac = e.nodo.aceptar(e.sobre)
    ctx = multiprocessing.get_context("fork")
    cola = ctx.Queue()
    ps = [
        ctx.Process(target=_ejecutar_en_proceso, args=((str(e.dir), ""), cola, ac.orden, str(contador.ruta)))
        for _ in range(6)
    ]
    for p in ps:
        p.start()
    for p in ps:
        p.join(20)
    salidas = [cola.get(timeout=5) for _ in ps]
    assert salidas.count("ok") == 1, salidas
    assert contador.veces == 1
    assert all(s in ("ok", Motivo.EJECUCION_REPETIDA.value, Motivo.EJECUCION_AMBIGUA.value) for s in salidas)


# --- N1: orden de llegada ---------------------------------------------------------------------------------------


def _validar(m: Mundo, campos: dict[str, Any], almacen: AlmacenConsumidas, **kw: Any) -> Any:
    return validar_orden(
        firmante_orden(m.hc1, campos), politica=m.politica(**kw), verificar=m.verificador_hc1(), almacen=almacen
    )


def _motivo(m: Mundo, campos: dict[str, Any], almacen: AlmacenConsumidas, **kw: Any) -> Motivo:
    with pytest.raises(RechazoOrden) as err:
        _validar(m, campos, almacen, **kw)
    return err.value.motivo


def test_n1_epoch_menor_que_el_ultimo_visto_se_rechaza_aunque_la_orden_sea_nueva(tmp_path: Path) -> None:
    m = mundo()
    alm = AlmacenConsumidas(tmp_path / "n")
    _validar(m, campos_validos(epoch_hc1=2), alm)
    assert _motivo(m, campos_validos(epoch_hc1=1), alm) is Motivo.EPOCH_ANTIGUO
    _validar(m, campos_validos(epoch_hc1=3), alm)  # control: un epoch mayor sube el máximo...
    assert _motivo(m, campos_validos(epoch_hc1=2), alm) is Motivo.EPOCH_ANTIGUO  # ...y 2 deja de valer
    assert (
        _motivo(m, campos_validos(epoch_hc1=1), AlmacenConsumidas(tmp_path / "n")) is Motivo.EPOCH_ANTIGUO
    )  # reinicio


def test_n1_ordenes_independientes_del_mismo_epoch_se_aceptan_en_cualquier_orden_una_vez_cada_una(
    tmp_path: Path,
) -> None:
    m = mundo()
    alm = AlmacenConsumidas(tmp_path / "n")
    a = campos_validos(tarea="t-a", epoch_hc1=5, emitida_en=T0, caduca_en=T0 + 60)
    b = campos_validos(tarea="t-b", epoch_hc1=5, emitida_en=T0 + 2, caduca_en=T0 + 62)
    m.reloj.t = T0 + 3
    _validar(m, b, alm)  # llega primero la emitida DESPUÉS
    _validar(m, a, alm)  # y luego la anterior: mismo epoch, otra orden => se acepta
    for c in (a, b):
        assert _motivo(m, c, alm) is Motivo.ORDEN_REPETIDA  # pero cada una solo una vez
    assert _motivo(m, campos_validos(tarea="t-c", epoch_hc1=4), alm) is Motivo.EPOCH_ANTIGUO


def test_n1_emitida_antes_del_arranque_se_rechaza_y_en_el_limite_exacto_se_acepta(tmp_path: Path) -> None:
    m = mundo()
    alm = AlmacenConsumidas(tmp_path / "n")
    assert _motivo(m, campos_validos(emitida_en=T0 - 1), alm, arranque=T0) is Motivo.EMITIDA_ANTES_DEL_ARRANQUE
    _validar(m, campos_validos(emitida_en=T0), alm, arranque=T0)  # control: igual que el arranque, sí


# --- B-4: almacén endurecido --------------------------------------------------------------------------------------


def test_b4_directorio_existente_con_permisos_abiertos_ajeno_o_enlace_falla_cerrado(tmp_path: Path) -> None:
    abierto = tmp_path / "abierto"
    abierto.mkdir()
    os.chmod(abierto, 0o755)
    with pytest.raises(RechazoOrden) as err:
        AlmacenConsumidas(abierto)
    assert err.value.motivo is Motivo.ALMACEN_ILEGIBLE
    os.chmod(abierto, 0o700)
    AlmacenConsumidas(abierto)  # control: el mismo directorio con 0700 sirve
    real = tmp_path / "real"
    AlmacenConsumidas(real)
    enlace = tmp_path / "enlace"
    enlace.symlink_to(real)
    with pytest.raises(RechazoOrden):
        AlmacenConsumidas(enlace)
    un_fichero = tmp_path / "fichero"
    un_fichero.write_text("x")
    with pytest.raises(RechazoOrden):
        AlmacenConsumidas(un_fichero)


def test_b4_fichero_de_consumidas_con_permisos_abiertos_falla_cerrado(tmp_path: Path) -> None:
    alm = AlmacenConsumidas(tmp_path / "n")
    alm.consumir("a" * 36, 1)
    os.chmod(alm.ruta, 0o666)
    with pytest.raises(RechazoOrden) as err:
        alm.consumir("b" * 36, 1)
    assert err.value.motivo is Motivo.ALMACEN_ILEGIBLE
    os.chmod(alm.ruta, 0o600)
    alm.consumir("b" * 36, 1)  # control


def test_b4_linea_final_truncada_se_detecta_y_se_recuperan_los_consumos_validos(tmp_path: Path) -> None:
    alm = AlmacenConsumidas(tmp_path / "n")
    alm.consumir("a" * 36, 1)
    alm.consumir("b" * 36, 2)
    assert AlmacenConsumidas(tmp_path / "n").bytes_recuperados == 0  # control: sin caída no hay recuperación
    fragmento = b'{"id":"ccccccccccccccccccccccccccccccccccc'
    with open(alm.ruta, "ab") as f:
        f.write(fragmento)  # caída a mitad de escritura
    nuevo = AlmacenConsumidas(tmp_path / "n")
    nuevo.consumir("d" * 36, 2)  # NO falla: se recorta el fragmento y se sigue
    assert nuevo.bytes_recuperados == len(fragmento)  # detectado y cuantificado
    for valido in ("a" * 36, "b" * 36, "d" * 36):
        with pytest.raises(RechazoOrden) as err:
            nuevo.consumir(valido, 2)
        assert err.value.motivo is Motivo.ORDEN_REPETIDA  # ningún consumo válido se perdió
    texto = alm.ruta.read_bytes()
    assert texto.endswith(b"\n") and b"ccccc" not in texto
    assert [json.loads(x)["id"] for x in texto.splitlines()] == ["a" * 36, "b" * 36, "d" * 36]
    # DOCUMENTADO: un fragmento truncado, aunque parezca un JSON completo, no llegó a confirmarse al llamante
    with open(alm.ruta, "ab") as f:
        f.write(b'{"id":"e' + b"e" * 35 + b'","epoch":2}')  # sin salto de línea final
    AlmacenConsumidas(tmp_path / "n").consumir("e" * 36, 2)  # puede consumirse: nunca se confirmó


def test_b4_las_ejecuciones_tambien_recuperan_la_linea_truncada(tmp_path: Path, contador: Contador) -> None:
    e = Escena(tmp_path)
    res = e.nodo.ejecutar(e.nodo.aceptar(e.sobre).orden)
    with open(e.dir / NOMBRE_EJECUCIONES, "ab") as f:
        f.write(b'{"id":"zz","est')
    almacen, nodo = e.reiniciar()
    assert nodo.reenviar_resultado(e.ident) == res and almacen.bytes_recuperados == len(b'{"id":"zz","est')
    assert almacen.estado(e.ident) is EstadoNodo.COMPLETADA


def test_b4_una_linea_ilegible_en_el_medio_no_es_una_caida_falla_cerrado(tmp_path: Path) -> None:
    alm = AlmacenConsumidas(tmp_path / "n")
    alm.consumir("a" * 36, 1)
    alm.ruta.write_bytes(b"basura\n" + alm.ruta.read_bytes())
    with pytest.raises(RechazoOrden) as err:
        alm.consumir("b" * 36, 1)
    assert err.value.motivo is Motivo.ALMACEN_ILEGIBLE


# --- N1/B-4: persistencia con fsync de fichero y de directorio ------------------------------------------------------


def test_n1_el_almacen_hace_fsync_del_fichero_y_del_directorio_al_crear(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    espia = _EspiaFsync(monkeypatch)
    alm = AlmacenConsumidas(tmp_path / "n")
    assert os.stat(tmp_path).st_ino in espia.directorios  # directorio creado: se sincroniza el padre
    antes = espia.ficheros
    alm.consumir("a" * 36, 1)
    assert os.stat(tmp_path / "n").st_ino in espia.directorios  # fichero creado: se sincroniza su directorio
    assert espia.ficheros > antes  # y el contenido
    d_antes, f_antes = len(espia.directorios), espia.ficheros
    alm.consumir("b" * 36, 1)
    assert espia.ficheros > f_antes and len(espia.directorios) == d_antes  # control: solo el fichero, ya existente


def test_m3_los_estados_se_escriben_con_fsync_antes_de_devolver(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    alm = AlmacenConsumidas(tmp_path / "n")
    alm.consumir("a" * 36, 1)
    espia = _EspiaFsync(monkeypatch)
    alm.iniciar_ejecucion("a" * 36)
    n1 = espia.ficheros
    assert n1 >= 2  # el fichero de ejecuciones se crea (fsync) y se escribe el registro (fsync)
    alm.completar("a" * 36, b"firmado")
    assert espia.ficheros > n1
    assert (
        base64.b64decode(json.loads((tmp_path / "n" / NOMBRE_EJECUCIONES).read_text().splitlines()[-1])["resultado"])
        == b"firmado"
    )
    assert stat.S_IMODE(os.stat(tmp_path / "n" / NOMBRE_EJECUCIONES).st_mode) == 0o600
    assert (tmp_path / "n" / NOMBRE).exists()
