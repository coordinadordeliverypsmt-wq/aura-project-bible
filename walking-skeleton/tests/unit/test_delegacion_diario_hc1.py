"""M-2 — diario durable de HC-1, recuperación tras reinicio, `resolver_ambigua` y concurrencia del seguimiento.

El diario es de HC-1 (capa propia), NO el log del control-plane. Todo en tmp_path; claves solo de prueba.
"""

from __future__ import annotations

import base64
import json
import os
import stat
import threading
import time
from pathlib import Path
from typing import Any

import pytest

from aura_skeleton.adapters.almacen_consumidas import AlmacenConsumidas
from aura_skeleton.adapters.diario_hc1 import NOMBRE, DiarioHC1
from aura_skeleton.core.delegacion import (
    DOMINIO_RESULTADO,
    Motivo,
    RechazoOrden,
    abrir_sobre,
    bytes_canonicos,
)
from aura_skeleton.core.delegacion_hc1 import Estado, SeguimientoHC1
from aura_skeleton.core.delegacion_nodo import NodoDelegado
from tests.delegacion_apoyo import NODO, OTRO_NODO, T0, AlmacenMemoria, Mundo, campos_validos, firmante_orden, mundo


class Escena:
    """HC-1 con diario real en disco + nodo real con almacén real. `reiniciar_hc1` = proceso nuevo, mismo disco."""

    def __init__(self, tmp_path: Path, **kw: Any) -> None:
        self.dir = tmp_path / "hc1"
        self.m: Mundo = mundo()
        self.kw = kw
        self.hc1 = self.reiniciar_hc1()
        self.nodo = NodoDelegado(
            self.m.politica(), self.m.verificador_hc1(), AlmacenConsumidas(tmp_path / "nodo"), self.m.nodo.firmar
        )

    def reiniciar_hc1(self, **kw: Any) -> SeguimientoHC1:
        self.hc1 = SeguimientoHC1(
            self.m.verificador_nodos(), self.m.reloj, diario=DiarioHC1(self.dir), **{**self.kw, **kw}
        )
        return self.hc1

    def emitir(self, techo: float = 60, **cambios: Any) -> tuple[bytes, str]:
        sobre = firmante_orden(self.m.hc1, campos_validos(**cambios))
        return sobre, self.hc1.registrar_emision(sobre, techo_total_s=techo).id_ejecucion

    def nodo_responde(self, sobre: bytes) -> tuple[bytes, bytes]:
        ac = self.nodo.aceptar(sobre)
        return ac.acuse, self.nodo.ejecutar(ac.orden)


def _estado(hc1: SeguimientoHC1, ident: str) -> Estado:
    ej = hc1.ejecucion(ident)
    assert ej is not None
    return ej.estado


# --- el diario y su durabilidad --------------------------------------------------------------------------


def test_el_diario_es_privado_0700_0600_y_rechaza_directorios_inseguros(tmp_path: Path) -> None:
    DiarioHC1(tmp_path / "d").anotar({"ev": "x"})
    assert stat.S_IMODE(os.stat(tmp_path / "d").st_mode) == 0o700
    assert stat.S_IMODE(os.stat(tmp_path / "d" / NOMBRE).st_mode) == 0o600
    abierto = tmp_path / "abierto"
    abierto.mkdir(mode=0o755)
    os.chmod(abierto, 0o755)
    with pytest.raises(RechazoOrden) as e:
        DiarioHC1(abierto)
    assert e.value.motivo is Motivo.DIARIO_NO_DURABLE
    enlace = tmp_path / "enlace"
    enlace.symlink_to(tmp_path / "d")
    with pytest.raises(RechazoOrden):
        DiarioHC1(enlace)
    os.chmod(tmp_path / "d" / NOMBRE, 0o644)  # fichero con permisos abiertos: fallo cerrado al escribir
    with pytest.raises(RechazoOrden):
        DiarioHC1(tmp_path / "d").anotar({"ev": "y"})


class _EspiaFsync:
    """Instrumenta `os.fsync`: anota si el descriptor era un directorio (y cuál) o un fichero."""

    def __init__(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self.directorios: list[int] = []  # inodos de directorios sincronizados
        self.ficheros = 0
        real = os.fsync

        def espia(fd: int) -> None:
            st = os.fstat(fd)
            if stat.S_ISDIR(st.st_mode):
                self.directorios.append(st.st_ino)
            else:
                self.ficheros += 1
            real(fd)

        monkeypatch.setattr(os, "fsync", espia)


def test_n1_el_diario_hace_fsync_del_fichero_en_cada_registro_y_del_directorio_al_crear(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    espia = _EspiaFsync(monkeypatch)
    d = DiarioHC1(tmp_path / "d")
    assert os.stat(tmp_path).st_ino in espia.directorios  # al crear el directorio se sincroniza su PADRE
    d.anotar({"ev": "a"})
    assert os.stat(tmp_path / "d").st_ino in espia.directorios  # al crear el fichero, el directorio que lo contiene
    antes_f, antes_d = espia.ficheros, len(espia.directorios)
    d.anotar({"ev": "b"})
    assert espia.ficheros > antes_f  # cada registro: fsync del fichero
    assert len(espia.directorios) == antes_d  # control: el directorio no se re-sincroniza si el fichero ya existía


# --- reconstrucción tras reinicio --------------------------------------------------------------------------


def test_control_sin_diario_un_reinicio_pierde_el_seguimiento(tmp_path: Path) -> None:
    esc = Escena(tmp_path)
    _, ident = esc.emitir()
    sin_diario = SeguimientoHC1(esc.m.verificador_nodos(), esc.m.reloj)
    assert sin_diario.ejecucion(ident) is None  # la carencia que M-2 cierra
    assert esc.reiniciar_hc1().ejecucion(ident) is not None  # con diario, se reconstruye


def test_cada_estado_sobrevive_a_un_reinicio(tmp_path: Path) -> None:
    esc = Escena(tmp_path)
    sobre, ident = esc.emitir()
    ej0 = esc.hc1.ejecucion(ident)
    assert ej0 is not None
    acuse, res = esc.nodo_responde(sobre)
    visto: list[Estado] = []

    def reiniciar_y_comprobar(esperado: Estado) -> None:
        h = esc.reiniciar_hc1()
        assert _estado(h, ident) is esperado
        ej = h.ejecucion(ident)
        assert ej is not None and (ej.hash_tarea, ej.vence_en, ej.sobre_orden) == (ej0.hash_tarea, ej0.vence_en, sobre)
        visto.append(esperado)

    reiniciar_y_comprobar(Estado.EMITIDA)
    esc.hc1.recibir_acuse(acuse, NODO)
    reiniciar_y_comprobar(Estado.ACEPTADA)
    esc.hc1.recibir_resultado(res, NODO)
    reiniciar_y_comprobar(Estado.RESULTADO_FIRMADO)
    assert esc.hc1.validar(ident) is True
    reiniciar_y_comprobar(Estado.VALIDADO)
    esc.hc1.incorporar(ident, lambda _: None)
    reiniciar_y_comprobar(Estado.INCORPORADO)
    assert esc.hc1.ejecucion(ident).completada  # type: ignore[union-attr]
    assert len(visto) == 5


def test_el_resultado_posterior_al_reinicio_se_procesa_contra_el_estado_recuperado(tmp_path: Path) -> None:
    esc = Escena(tmp_path)
    sobre, ident = esc.emitir()
    acuse, res = esc.nodo_responde(sobre)
    h = esc.reiniciar_hc1()  # HC-1 cae tras emitir; el nodo ya respondió
    h.recibir_acuse(acuse, NODO)
    h.recibir_resultado(res, NODO)
    assert h.validar(ident) is True
    registro: list[dict[str, Any]] = []
    h.incorporar(ident, registro.append)
    assert len(registro) == 1 and registro[0]["id_ejecucion"] == ident
    h2 = esc.reiniciar_hc1()
    with pytest.raises(RechazoOrden) as e:
        h2.recibir_resultado(res, NODO)
    assert e.value.motivo is Motivo.RESULTADO_DUPLICADO  # el estado recuperado sabe que ya se incorporó


def test_las_vencidas_pasan_a_interrumpida_o_ambiguo_explicitos_y_quedan_anotadas(tmp_path: Path) -> None:
    esc = Escena(tmp_path)
    s1, id_emitida = esc.emitir(techo=30, tarea="t-a")
    s2, id_aceptada = esc.emitir(techo=30, tarea="t-b")
    s3, id_viva = esc.emitir(techo=500, tarea="t-c")
    esc.hc1.recibir_acuse(esc.nodo.aceptar(s2).acuse, NODO)
    esc.m.reloj.t = T0 + 100  # HC-1 estuvo caída 100 s
    h = esc.reiniciar_hc1()
    assert _estado(h, id_emitida) is Estado.INTERRUMPIDA  # sin acuse: reintentable
    assert _estado(h, id_aceptada) is Estado.AMBIGUO  # con acuse: pudo tener efecto
    assert _estado(h, id_viva) is Estado.EMITIDA  # control: lo que no ha vencido sigue en curso
    assert s1 and s3
    h2 = esc.reiniciar_hc1()  # y lo decidido ya está en el diario, no se recalcula
    assert (_estado(h2, id_emitida), _estado(h2, id_aceptada)) == (Estado.INTERRUMPIDA, Estado.AMBIGUO)


def test_linea_final_truncada_se_detecta_y_no_pierde_registros_validos(tmp_path: Path) -> None:
    esc = Escena(tmp_path)
    _, ident = esc.emitir()
    assert esc.reiniciar_hc1().bytes_truncados == 0  # control: un diario íntegro no reporta truncamiento
    ruta = tmp_path / "hc1" / NOMBRE
    fragmento = b'{"ev":"acuse","id":"' + ident.encode()[:10]
    with open(ruta, "ab") as f:
        f.write(fragmento)  # caída a mitad de escritura de un registro
    h = esc.reiniciar_hc1()
    assert h.bytes_truncados == len(fragmento)  # DETECTADA
    assert _estado(h, ident) is Estado.EMITIDA  # el registro válido anterior se conserva
    assert ruta.read_bytes().endswith(b"\n")  # reparado: lo siguiente no se pega al fragmento
    h.recibir_acuse(esc.nodo.aceptar(h.ejecucion(ident).sobre_orden).acuse, NODO)  # type: ignore[union-attr]
    assert all(json.loads(x) for x in ruta.read_text().splitlines())
    assert _estado(esc.reiniciar_hc1(), ident) is Estado.ACEPTADA


def test_linea_ilegible_en_el_medio_es_corrupcion_y_falla_cerrado(tmp_path: Path) -> None:
    esc = Escena(tmp_path)
    esc.emitir()
    ruta = tmp_path / "hc1" / NOMBRE
    ruta.write_bytes(b"basura\n" + ruta.read_bytes())
    with pytest.raises(RechazoOrden) as e:
        esc.reiniciar_hc1()
    assert e.value.motivo is Motivo.DIARIO_ILEGIBLE
    ruta.write_bytes(b'{"ev":"acuse","id":"no-existe","recibida_en":1}\n')  # registro huérfano
    with pytest.raises(RechazoOrden) as e2:
        esc.reiniciar_hc1()
    assert e2.value.motivo is Motivo.DIARIO_ILEGIBLE


class DiarioQueFalla:
    def __init__(self) -> None:
        self.fallar = False
        self.anotados: list[dict[str, Any]] = []

    def anotar(self, registro: dict[str, Any]) -> None:
        if self.fallar:
            raise RechazoOrden(Motivo.DIARIO_NO_DURABLE, "disco lleno")
        self.anotados.append(registro)

    def recuperar(self) -> tuple[list[dict[str, Any]], int]:
        return [], 0


def test_sin_durabilidad_no_hay_transicion_el_diario_se_escribe_antes_que_la_memoria() -> None:
    m = mundo()
    diario = DiarioQueFalla()
    hc1 = SeguimientoHC1(m.verificador_nodos(), m.reloj, diario=diario)
    diario.fallar = True
    campos = campos_validos()
    sobre = firmante_orden(m.hc1, campos)
    with pytest.raises(RechazoOrden) as e:
        hc1.registrar_emision(sobre, 60)
    assert e.value.motivo is Motivo.DIARIO_NO_DURABLE and hc1.ejecucion(campos["id_ejecucion"]) is None
    diario.fallar = False
    ej = hc1.registrar_emision(sobre, 60)  # control: con el diario sano, se registra
    diario.fallar = True
    assert [d["ev"] for d in diario.anotados] == ["emision"]
    with pytest.raises(RechazoOrden):
        hc1.marcar_desconexion(NODO)
    assert ej.estado is Estado.EMITIDA


# --- resolver_ambigua ----------------------------------------------------------------------------------------


def _ambigua(esc: Escena, tarea: str = "t-001") -> tuple[str, bytes, bytes]:
    """Una ejecución AMBIGUA: el nodo acusó y COMPLETÓ, pero el resultado se perdió y HC-1 venció."""
    ahora = esc.m.reloj.t
    sobre, ident = esc.emitir(techo=30, tarea=tarea, emitida_en=ahora, caduca_en=ahora + 60)
    acuse, res = esc.nodo_responde(sobre)
    esc.hc1.recibir_acuse(acuse, NODO)
    esc.m.reloj.t += 100
    esc.hc1.vencer()
    assert _estado(esc.hc1, ident) is Estado.AMBIGUO
    return ident, res, sobre


def test_un_resultado_tardio_tras_ambiguo_no_se_acepta_solo(tmp_path: Path) -> None:
    esc = Escena(tmp_path, autoridades=frozenset({"mauricio"}))
    ident, res, _ = _ambigua(esc)
    with pytest.raises(RechazoOrden) as e:
        esc.hc1.recibir_resultado(res, NODO)
    assert e.value.motivo is Motivo.EJECUCION_NO_EN_CURSO
    assert _estado(esc.hc1, ident) is Estado.AMBIGUO


def test_resolver_ambigua_exige_autoridad_declarada(tmp_path: Path) -> None:
    esc = Escena(tmp_path, autoridades=frozenset({"mauricio"}))
    ident, res, _ = _ambigua(esc)
    for intruso in ("intruso", "", "MAURICIO", None):
        with pytest.raises(RechazoOrden) as e:
            esc.hc1.resolver_ambigua(ident, intruso, "lo apruebo", res)  # type: ignore[arg-type]
        assert e.value.motivo is Motivo.SIN_AUTORIDAD
    assert _estado(esc.hc1, ident) is Estado.AMBIGUO  # nada cambió
    ej = esc.hc1.resolver_ambigua(ident, "mauricio", "el nodo guardó el resultado firmado", res)  # control
    assert ej.estado is Estado.RESULTADO_FIRMADO and ej.resuelta_por == "mauricio"
    sin_autoridades = Escena(tmp_path / "otra")  # por defecto NADIE puede resolver
    ident2, res2, _ = _ambigua(sin_autoridades)
    with pytest.raises(RechazoOrden) as e2:
        sin_autoridades.hc1.resolver_ambigua(ident2, "mauricio", "x", res2)
    assert e2.value.motivo is Motivo.SIN_AUTORIDAD


def test_resolver_ambigua_valida_firma_y_vinculo_y_exige_motivo(tmp_path: Path) -> None:
    esc = Escena(tmp_path, autoridades=frozenset({"mauricio"}))
    ident, res, _ = _ambigua(esc)
    resolver = lambda r, motivo="m": esc.hc1.resolver_ambigua(ident, "mauricio", motivo, r)  # noqa: E731

    def motivo_de(r: bytes, motivo: str = "m") -> Motivo:
        with pytest.raises(RechazoOrden) as e:
            resolver(r, motivo)
        return e.value.motivo

    ab = abrir_sobre(res)
    from aura_skeleton.core.delegacion import empaquetar_sobre

    assert (
        motivo_de(empaquetar_sobre(ab.kid, ab.payload.replace(b'"salida":"', b'"salida":"0'), ab.firma))
        is Motivo.FIRMA_INVALIDA
    )
    assert motivo_de(res, "") is Motivo.CAMPO_INVALIDO and motivo_de(res, "  ") is Motivo.CAMPO_INVALIDO
    base = json.loads(ab.payload)
    otro_hash = esc.m.nodo.firmar(DOMINIO_RESULTADO, bytes_canonicos({**base, "hash_tarea": "e" * 64}))
    assert motivo_de(otro_hash) is Motivo.HASH_NO_CORRESPONDE
    otro_id = esc.m.nodo.firmar(
        DOMINIO_RESULTADO, bytes_canonicos({**base, "id_ejecucion": "11111111-1111-4111-8111-111111111111"})
    )
    assert motivo_de(otro_id) in (Motivo.VINCULO_ROTO, Motivo.EJECUCION_DESCONOCIDA)
    de_otro_nodo = esc.m.otro_nodo.firmar(DOMINIO_RESULTADO, bytes_canonicos({**base, "id_nodo": OTRO_NODO}))
    assert motivo_de(de_otro_nodo) in (Motivo.KID_DESCONOCIDO, Motivo.NODO_AJENO)
    assert _estado(esc.hc1, ident) is Estado.AMBIGUO
    assert resolver(res).estado is Estado.RESULTADO_FIRMADO  # control: el resultado auténtico y vinculado sí


def test_resolver_ambigua_no_acepta_el_resultado_de_otra_ejecucion_del_mismo_nodo(tmp_path: Path) -> None:
    esc = Escena(tmp_path, autoridades=frozenset({"mauricio"}))
    id_a, res_a, _ = _ambigua(esc, "t-a")
    id_b, res_b, _ = _ambigua(esc, "t-b")
    with pytest.raises(RechazoOrden) as e:
        esc.hc1.resolver_ambigua(id_a, "mauricio", "m", res_b)  # firma válida del MISMO nodo, pero de OTRA orden
    assert e.value.motivo is Motivo.VINCULO_ROTO
    assert _estado(esc.hc1, id_a) is Estado.AMBIGUO and _estado(esc.hc1, id_b) is Estado.AMBIGUO
    assert esc.hc1.resolver_ambigua(id_a, "mauricio", "m", res_a).estado is Estado.RESULTADO_FIRMADO  # control
    assert _estado(esc.hc1, id_b) is Estado.AMBIGUO


def test_resolver_ambigua_solo_vale_para_ambiguas_o_interrumpidas(tmp_path: Path) -> None:
    esc = Escena(tmp_path, autoridades=frozenset({"mauricio"}))
    sobre, ident = esc.emitir()
    acuse, res = esc.nodo_responde(sobre)
    esc.hc1.recibir_acuse(acuse, NODO)  # ACEPTADA: está en curso, no ambigua
    with pytest.raises(RechazoOrden) as e:
        esc.hc1.resolver_ambigua(ident, "mauricio", "m", res)
    assert e.value.motivo is Motivo.EJECUCION_NO_EN_CURSO
    with pytest.raises(RechazoOrden) as e2:
        esc.hc1.resolver_ambigua("11111111-1111-4111-8111-111111111111", "mauricio", "m", res)
    assert e2.value.motivo is Motivo.EJECUCION_DESCONOCIDA


def test_la_resolucion_se_registra_persistentemente_y_sigue_el_camino_normal(tmp_path: Path) -> None:
    esc = Escena(tmp_path, autoridades=frozenset({"mauricio"}))
    ident, res, _ = _ambigua(esc)
    esc.hc1.resolver_ambigua(ident, "mauricio", "reenvío manual", res)
    h = esc.reiniciar_hc1()
    ej = h.ejecucion(ident)
    assert ej is not None and ej.estado is Estado.RESULTADO_FIRMADO
    assert (ej.resuelta_por, ej.motivo_resolucion) == ("mauricio", "reenvío manual")
    lineas = [json.loads(x) for x in (tmp_path / "hc1" / NOMBRE).read_text().splitlines()]
    resol = [x for x in lineas if x["ev"] == "resolucion"]
    assert len(resol) == 1 and resol[0]["por"] == "mauricio" and resol[0]["motivo"] == "reenvío manual"
    assert base64.b64decode(resol[0]["sobre"]) == res
    assert h.validar(ident) is True  # y aún hay que validar con el verificador PROPIO antes de incorporar
    assert not ej.completada
    h.incorporar(ident, lambda _: None)
    assert ej.completada


# --- concurrencia ---------------------------------------------------------------------------------------------


class DiarioLento:
    """Abre una ventana de carrera entre «comprobar el estado» y «aplicarlo»: sin cerrojo, todos los hilos la cruzan."""

    def __init__(self) -> None:
        self.anotados: list[dict[str, Any]] = []

    def anotar(self, registro: dict[str, Any]) -> None:
        time.sleep(0.05)
        self.anotados.append(registro)

    def recuperar(self) -> tuple[list[dict[str, Any]], int]:
        return [], 0


def test_n1_el_mismo_resultado_desde_muchos_hilos_se_incorpora_una_sola_vez() -> None:
    m = mundo()
    diario = DiarioLento()
    hc1 = SeguimientoHC1(m.verificador_nodos(), m.reloj, diario=diario)
    sobre = firmante_orden(m.hc1, campos_validos())
    ident = hc1.registrar_emision(sobre, 60).id_ejecucion
    nodo = NodoDelegado(m.politica(), m.verificador_hc1(), AlmacenMemoria(), m.nodo.firmar)
    ac = nodo.aceptar(sobre)
    res = nodo.ejecutar(ac.orden)
    resultados: list[object] = []

    def intentar() -> None:
        try:
            hc1.recibir_resultado(res, NODO)
            resultados.append("ok")
        except RechazoOrden as e:
            resultados.append(e.motivo)

    hilos = [threading.Thread(target=intentar) for _ in range(8)]
    for h in hilos:
        h.start()
    for h in hilos:
        h.join()
    assert resultados.count("ok") == 1
    assert resultados.count(Motivo.RESULTADO_DUPLICADO) == 7
    assert [d["ev"] for d in diario.anotados].count("resultado") == 1
    assert hc1.validar(ident) is True


def test_n1_la_misma_emision_desde_muchos_hilos_se_registra_una_sola_vez() -> None:
    m = mundo()
    diario = DiarioLento()
    hc1 = SeguimientoHC1(m.verificador_nodos(), m.reloj, diario=diario)
    sobre = firmante_orden(m.hc1, campos_validos())
    resultados: list[object] = []

    def intentar() -> None:
        try:
            hc1.registrar_emision(sobre, 60)
            resultados.append("ok")
        except RechazoOrden as e:
            resultados.append(e.motivo)

    hilos = [threading.Thread(target=intentar) for _ in range(6)]
    for h in hilos:
        h.start()
    for h in hilos:
        h.join()
    assert resultados.count("ok") == 1 and resultados.count(Motivo.ORDEN_REPETIDA) == 5
    assert len(diario.anotados) == 1
