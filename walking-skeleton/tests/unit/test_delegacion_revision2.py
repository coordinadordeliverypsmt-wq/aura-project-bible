"""2.ª revisión de seguridad independiente: M19 (id_nodo vs subject), C1 (incorporación sin duplicados), C2 (revocación viva
y ancla de existencia), C3 (autorización firmada y at-most-once por tarea) y BAJOS a/b/c.

Todo en tmp_path; claves solo de prueba. Cada prueba lleva su caso de CONTROL (el mismo camino, sin la anomalía).
"""

from __future__ import annotations

import base64
import dataclasses
import fcntl
import json
import os
import threading
import time
from pathlib import Path
from types import MappingProxyType
from typing import Any

import pytest

from aura_skeleton.adapters.almacen_consumidas import AlmacenConsumidas
from aura_skeleton.adapters.diario_hc1 import NOMBRE, DiarioHC1
from aura_skeleton.adapters.firma_delegacion import (
    ErrorClave,
    ListaRevocados,
    generar_firmante,
    revocar,
)
from aura_skeleton.adapters.firmador_hc1 import (
    ErrorFirmador,
    Firmador,
    PoliticaFirmador,
    crear_servidor,
    verificar_cadena_log,
)
from aura_skeleton.core import delegacion_hc1
from aura_skeleton.core.delegacion import (
    CAPACIDADES,
    DOMINIO_ACUSE,
    DOMINIO_ORDEN,
    DOMINIO_RESOLUCION,
    DOMINIO_RESULTADO,
    Capacidad,
    Motivo,
    RechazoOrden,
    bytes_canonicos,
    payload_resolucion,
    validar_orden,
)
from aura_skeleton.core.delegacion_hc1 import Estado, SeguimientoHC1
from aura_skeleton.core.delegacion_nodo import NodoDelegado
from tests.delegacion_apoyo import (
    KID_AUTORIDAD,
    NODO,
    OTRO_NODO,
    T0,
    AlmacenMemoria,
    Mundo,
    RegistroSintetico,
    campos_validos,
    firmante_orden,
    mundo,
)


def _motivo(fn: Any, *a: Any, **kw: Any) -> Motivo:
    with pytest.raises(RechazoOrden) as e:
        fn(*a, **kw)
    return e.value.motivo


class Escena:
    """HC-1 (con o sin diario real) + nodo real con almacén real, sobre un único `Mundo`."""

    def __init__(self, tmp_path: Path, diario: bool = True, **kw: Any) -> None:
        self.tmp = tmp_path
        self.m: Mundo = mundo()
        self.kw = kw
        self.con_diario = diario
        self.hc1 = self.reiniciar_hc1()
        self.nodo = NodoDelegado(
            self.m.politica(), self.m.verificador_hc1(), AlmacenConsumidas(tmp_path / "nodo"), self.m.nodo.firmar
        )

    def reiniciar_hc1(self, **kw: Any) -> SeguimientoHC1:
        base: dict[str, Any] = {
            "verificar_autoridad": self.m.verificador_autoridad(),
            "kids_autoridad": frozenset({KID_AUTORIDAD}),
            "kid_hc1": "hc1-k1",
        }
        if self.con_diario:
            base["diario"] = DiarioHC1(self.tmp / "hc1")
        self.hc1 = SeguimientoHC1(self.m.verificador_nodos(), self.m.reloj, **{**base, **self.kw, **kw})
        return self.hc1

    def emitir(self, techo: float = 60, **cambios: Any) -> tuple[bytes, str]:
        sobre = firmante_orden(self.m.hc1, campos_validos(**cambios))
        return sobre, self.hc1.registrar_emision(sobre, techo_total_s=techo).id_ejecucion

    def hasta_validado(self, **cambios: Any) -> str:
        sobre, ident = self.emitir(**cambios)
        ac = self.nodo.aceptar(sobre)
        res = self.nodo.ejecutar(ac.orden)
        self.hc1.recibir_acuse(ac.acuse, NODO)
        self.hc1.recibir_resultado(res, NODO)
        assert self.hc1.validar(ident) is True
        return ident

    def ambigua(self, tarea: str = "t-001") -> tuple[str, bytes]:
        ahora = self.m.reloj.t
        sobre, ident = self.emitir(techo=30, tarea=tarea, emitida_en=ahora, caduca_en=ahora + 60)
        ac = self.nodo.aceptar(sobre)
        res = self.nodo.ejecutar(ac.orden)
        self.hc1.recibir_acuse(ac.acuse, NODO)
        self.m.reloj.t += 100
        self.hc1.vencer()
        assert self.hc1.ejecucion(ident).estado is Estado.AMBIGUO  # type: ignore[union-attr]
        return ident, res


def _estado(hc1: SeguimientoHC1, ident: str) -> Estado:
    ej = hc1.ejecucion(ident)
    assert ej is not None
    return ej.estado


# =====================================================================================================================
# M19 — un resultado/acuse firmado CORRECTAMENTE por el nodo B no vale como procedente del nodo A
# =====================================================================================================================


def _payload_resultado(esc: Escena, ident: str, **cambios: Any) -> dict[str, Any]:
    ej = esc.hc1.ejecucion(ident)
    assert ej is not None
    base: dict[str, Any] = {
        "v": 1, "alg": "ed25519", "tarea": ej.tarea, "intento": ej.intento, "id_nodo": NODO,
        "id_ejecucion": ident, "hash_tarea": ej.hash_tarea, "salida": "0" * 64,
    }  # fmt: skip
    base.update(cambios)
    return base


def _payload_acuse(esc: Escena, ident: str, **cambios: Any) -> dict[str, Any]:
    base = _payload_resultado(esc, ident)
    del base["salida"]
    base["recibida_en"] = T0
    base.update(cambios)
    return base


def test_m19_resultado_firmado_por_el_nodo_b_entregado_como_del_nodo_a_se_rechaza_explicitamente(
    tmp_path: Path,
) -> None:
    esc = Escena(tmp_path, diario=False)
    _, ident = esc.emitir()
    de_b = esc.m.otro_nodo.firmar(DOMINIO_RESULTADO, bytes_canonicos(_payload_resultado(esc, ident, id_nodo=OTRO_NODO)))
    # firmado CORRECTAMENTE por B (id_nodo=B, su clave) pero entregado por el subject de A: el kid no es el del subject
    assert _motivo(esc.hc1.recibir_resultado, de_b, NODO) is Motivo.KID_DESCONOCIDO
    # y entregado como de B (su subject real) tampoco: la orden era para A, B no es el destinatario
    assert _motivo(esc.hc1.recibir_resultado, de_b, OTRO_NODO) is Motivo.NODO_AJENO
    assert _estado(esc.hc1, ident) is Estado.EMITIDA
    de_a = esc.m.nodo.firmar(DOMINIO_RESULTADO, bytes_canonicos(_payload_resultado(esc, ident)))
    assert esc.hc1.recibir_resultado(de_a, NODO).estado is Estado.RESULTADO_FIRMADO  # control: el suyo, por su subject


def test_m19_resultado_de_a_que_dice_ser_de_b_se_rechaza_aunque_la_firma_sea_valida(tmp_path: Path) -> None:
    esc = Escena(tmp_path, diario=False)
    _, ident = esc.emitir()
    miente = esc.m.nodo.firmar(DOMINIO_RESULTADO, bytes_canonicos(_payload_resultado(esc, ident, id_nodo=OTRO_NODO)))
    assert _motivo(esc.hc1.recibir_resultado, miente, NODO) is Motivo.NODO_AJENO  # firma de A, id_nodo de B
    assert _estado(esc.hc1, ident) is Estado.EMITIDA
    bien = esc.m.nodo.firmar(DOMINIO_RESULTADO, bytes_canonicos(_payload_resultado(esc, ident)))
    assert esc.hc1.recibir_resultado(bien, NODO).estado is Estado.RESULTADO_FIRMADO


def test_m19_lo_mismo_para_los_acuses(tmp_path: Path) -> None:
    esc = Escena(tmp_path, diario=False)
    _, ident = esc.emitir()
    de_b = esc.m.otro_nodo.firmar(DOMINIO_ACUSE, bytes_canonicos(_payload_acuse(esc, ident, id_nodo=OTRO_NODO)))
    assert _motivo(esc.hc1.recibir_acuse, de_b, NODO) is Motivo.KID_DESCONOCIDO
    assert _motivo(esc.hc1.recibir_acuse, de_b, OTRO_NODO) is Motivo.NODO_AJENO
    miente = esc.m.nodo.firmar(DOMINIO_ACUSE, bytes_canonicos(_payload_acuse(esc, ident, id_nodo=OTRO_NODO)))
    assert _motivo(esc.hc1.recibir_acuse, miente, NODO) is Motivo.NODO_AJENO
    assert _estado(esc.hc1, ident) is Estado.EMITIDA
    bien = esc.m.nodo.firmar(DOMINIO_ACUSE, bytes_canonicos(_payload_acuse(esc, ident)))
    assert esc.hc1.recibir_acuse(bien, NODO).estado is Estado.ACEPTADA  # control


# =====================================================================================================================
# C1 — incorporar: «incorporando» durable ANTES de registrar, registrar idempotente, INCORPORACION_INCIERTA
# =====================================================================================================================


class Caida(BaseException):
    """Simula un kill del proceso HC-1 en un punto exacto (BaseException: nada la captura por el camino)."""


class DiarioFalible(DiarioHC1):
    def __init__(self, directorio: Path) -> None:
        super().__init__(directorio)
        self.fallar_en: set[str] = set()

    def anotar(self, registro: dict[str, Any]) -> None:
        if registro["ev"] in self.fallar_en:
            raise RechazoOrden(Motivo.DIARIO_NO_DURABLE, "disco lleno")
        super().anotar(registro)


class RegistroEspia(RegistroSintetico):
    """Cuenta las llamadas reales a `registrar` y deja ver el diario en ese instante."""

    def __init__(self, ruta_diario: Path | None = None) -> None:
        super().__init__()
        self.llamadas = 0
        self.ruta_diario = ruta_diario
        self.diario_al_registrar: list[str] = []
        self.caer_dentro = False

    def __call__(self, hecho: dict[str, Any]) -> None:
        self.llamadas += 1
        if self.ruta_diario is not None:
            self.diario_al_registrar = [json.loads(x)["ev"] for x in self.ruta_diario.read_text().splitlines()]
        if self.caer_dentro:
            raise Caida
        super().__call__(hecho)


def _con_diario_falible(tmp_path: Path) -> tuple[Escena, DiarioFalible]:
    esc = Escena(tmp_path)
    diario = DiarioFalible(tmp_path / "hc1")
    esc.hc1 = esc.reiniciar_hc1(diario=diario)
    return esc, diario


def test_c1_incorporando_se_anota_durable_antes_de_registrar(tmp_path: Path) -> None:
    esc = Escena(tmp_path)
    ident = esc.hasta_validado()
    reg = RegistroEspia(tmp_path / "hc1" / NOMBRE)
    esc.hc1.incorporar(ident, reg)
    assert reg.diario_al_registrar[-1] == "incorporando" and "incorporado" not in reg.diario_al_registrar
    assert reg.llamadas == 1 and len(reg) == 1 and _estado(esc.hc1, ident) is Estado.INCORPORADO


def test_c1_fallo_del_diario_al_anotar_incorporando_no_registra_nada(tmp_path: Path) -> None:
    esc, diario = _con_diario_falible(tmp_path)
    ident = esc.hasta_validado()
    reg = RegistroEspia()
    diario.fallar_en = {"incorporando"}
    assert _motivo(esc.hc1.incorporar, ident, reg) is Motivo.DIARIO_NO_DURABLE
    assert reg.llamadas == 0 and _estado(esc.hc1, ident) is Estado.VALIDADO  # nada registrado, nada cambió
    diario.fallar_en = set()
    esc.hc1.incorporar(ident, reg)  # control
    assert len(reg) == 1


def test_c1_fallo_del_diario_tras_registrar_el_reintento_no_duplica(tmp_path: Path) -> None:
    esc, diario = _con_diario_falible(tmp_path)
    ident = esc.hasta_validado()
    reg = RegistroEspia()
    diario.fallar_en = {"incorporado"}
    assert _motivo(esc.hc1.incorporar, ident, reg) is Motivo.DIARIO_NO_DURABLE
    assert len(reg) == 1 and _estado(esc.hc1, ident) is Estado.INCORPORANDO  # registrado, pero sin cerrar
    diario.fallar_en = set()
    esc.hc1.incorporar(ident, reg)  # reintento
    assert len(reg) == 1 and reg.llamadas == 1  # exactamente UN registro y `registrar` no se volvió a llamar
    assert _estado(esc.hc1, ident) is Estado.INCORPORADO


def test_c1_caida_entre_incorporando_y_registrar_tras_reiniciar_es_incierta_y_registra_una_vez(tmp_path: Path) -> None:
    esc = Escena(tmp_path)
    ident = esc.hasta_validado()
    reg = RegistroEspia()
    reg.caer_dentro = True
    with pytest.raises(Caida):
        esc.hc1.incorporar(ident, reg)  # cae dentro de `registrar`, antes de escribir nada
    assert len(reg) == 0
    h = esc.reiniciar_hc1()
    assert _estado(h, ident) is Estado.INCORPORACION_INCIERTA  # estado EXPLÍCITO, no «validado» ni «incorporado»
    assert not h.ejecucion(ident).completada  # type: ignore[union-attr]
    reg.caer_dentro = False
    h.incorporar(ident, reg)
    assert len(reg) == 1 and _estado(h, ident) is Estado.INCORPORADO
    h.incorporar  # noqa: B018 - control: ya incorporado, un segundo intento se rechaza
    assert _motivo(h.incorporar, ident, reg) is Motivo.EJECUCION_NO_EN_CURSO and len(reg) == 1


def test_c1_caida_entre_registrar_e_incorporado_tras_reiniciar_no_vuelve_a_registrar(tmp_path: Path) -> None:
    esc, diario = _con_diario_falible(tmp_path)
    ident = esc.hasta_validado()
    reg = RegistroEspia()
    diario.fallar_en = {"incorporado"}
    with pytest.raises(RechazoOrden):
        esc.hc1.incorporar(ident, reg)  # registró y cayó antes de cerrar
    h = esc.reiniciar_hc1()
    assert _estado(h, ident) is Estado.INCORPORACION_INCIERTA
    h.incorporar(ident, reg)
    assert len(reg) == 1 and reg.llamadas == 1 and _estado(h, ident) is Estado.INCORPORADO
    assert _estado(esc.reiniciar_hc1(), ident) is Estado.INCORPORADO  # y el cierre es durable


def test_c1_un_registrar_sin_ya_registrado_se_rechaza_antes_de_tocar_nada(tmp_path: Path) -> None:
    esc = Escena(tmp_path)
    ident = esc.hasta_validado()
    vistos: list[dict[str, Any]] = []
    with pytest.raises(TypeError):
        esc.hc1.incorporar(ident, vistos.append)  # type: ignore[arg-type]
    assert vistos == [] and _estado(esc.hc1, ident) is Estado.VALIDADO
    esc.hc1.incorporar(ident, RegistroSintetico())  # control


# =====================================================================================================================
# C2 — revocación VIVA y ancla de existencia
# =====================================================================================================================


def _lista(tmp_path: Path) -> tuple[ListaRevocados, Path, Path]:
    estado = tmp_path / "estado"
    estado.mkdir(mode=0o700, parents=True, exist_ok=True)
    ruta, ancla = estado / "revocados.jsonl", estado / "revocados.ancla"
    return ListaRevocados(ruta, ancla), ruta, ancla


def _nodo_con_lista(tmp_path: Path, lista: ListaRevocados) -> tuple[Mundo, NodoDelegado]:
    m = mundo()
    nodo = NodoDelegado(
        m.politica(fuente_revocados=lista), m.verificador_hc1(), AlmacenConsumidas(tmp_path / "nodo"), m.nodo.firmar
    )
    return m, nodo


def test_c2_una_revocacion_posterior_surte_efecto_sin_reiniciar(tmp_path: Path) -> None:
    lista, ruta, _ = _lista(tmp_path)
    m, nodo = _nodo_con_lista(tmp_path, lista)  # la lista NO existe todavía: funciona
    assert nodo.aceptar(firmante_orden(m.hc1, campos_validos())).orden  # control: antes de revocar, se acepta
    revocar(ruta, "hc1-k1")  # revocación EN CALIENTE: ni el nodo ni su política se recrean
    assert _motivo(nodo.aceptar, firmante_orden(m.hc1, campos_validos())) is Motivo.KID_REVOCADO
    revocar(ruta, "otro")  # control: un kid ajeno no afecta a otros emisores
    assert lista() == {"hc1-k1", "otro"}


def test_c2_un_nodo_que_nunca_tuvo_lista_funciona_y_no_deja_ancla(tmp_path: Path) -> None:
    lista, ruta, ancla = _lista(tmp_path)
    assert lista() == frozenset() and not ruta.exists() and not ancla.exists()
    m, nodo = _nodo_con_lista(tmp_path, lista)
    assert nodo.aceptar(firmante_orden(m.hc1, campos_validos())).orden


def test_c2_borrar_la_lista_tras_crearla_rechaza_todo_con_motivo_explicito(tmp_path: Path) -> None:
    lista, ruta, ancla = _lista(tmp_path)
    m, nodo = _nodo_con_lista(tmp_path, lista)
    revocar(ruta, "kid-ajeno")
    assert nodo.aceptar(firmante_orden(m.hc1, campos_validos())).orden  # existe y se anota el ancla
    assert ancla.exists() and oct(ancla.stat().st_mode & 0o777) == "0o600"
    os.unlink(ruta)  # alguien borra la lista para «levantar» las revocaciones
    assert _motivo(nodo.aceptar, firmante_orden(m.hc1, campos_validos())) is Motivo.REVOCACION_ILEGIBLE
    assert _motivo(lista) is Motivo.REVOCACION_ILEGIBLE
    revocar(ruta, "kid-ajeno")  # la lista vuelve a existir (el ancla sigue): fallo cerrado SOLO mientras falte
    assert nodo.aceptar(firmante_orden(m.hc1, campos_validos())).orden


@pytest.mark.parametrize("dano", ["corrupta", "truncada", "ajena_escribible", "enlace"])
def test_c2_una_lista_ilegible_o_insegura_es_fallo_cerrado(tmp_path: Path, dano: str) -> None:
    lista, ruta, _ = _lista(tmp_path)
    revocar(ruta, "k")
    assert lista() == {"k"}  # control
    if dano == "corrupta":
        ruta.write_bytes(b"basura\n")
    elif dano == "truncada":
        ruta.write_bytes(b'{"kid":"k"}')
    elif dano == "ajena_escribible":
        os.chmod(ruta, 0o666)
    else:
        os.unlink(ruta)
        ruta.symlink_to(tmp_path / "estado" / "otra")
        (tmp_path / "estado" / "otra").write_bytes(b'{"kid":"k"}\n')
        os.chmod(tmp_path / "estado" / "otra", 0o600)  # el destino es LEGIBLE y seguro: solo el enlace lo delata
    assert _motivo(lista) is Motivo.REVOCACION_ILEGIBLE


def test_c2_la_lista_se_lee_bajo_flock_compartido(tmp_path: Path) -> None:
    lista, ruta, _ = _lista(tmp_path)
    revocar(ruta, "k")
    fd = os.open(ruta, os.O_RDWR)
    fcntl.flock(fd, fcntl.LOCK_EX)  # una escritura en curso
    hecho = threading.Event()
    hilo = threading.Thread(target=lambda: (lista(), hecho.set()), daemon=True)
    hilo.start()
    assert not hecho.wait(0.4)  # el lector espera: no lee a medias
    os.close(fd)  # libera el cerrojo
    assert hecho.wait(3)
    hilo.join(3)


def _hc1_con_lista(tmp_path: Path) -> tuple[Escena, Path]:
    lista, ruta, _ = _lista(tmp_path)
    return Escena(tmp_path, diario=False, fuente_revocados=lista), ruta


def test_c2_hc1_revocacion_en_caliente_de_un_nodo_afecta_a_acuses_y_resultados(tmp_path: Path) -> None:
    esc, ruta = _hc1_con_lista(tmp_path)
    sobre, ident = esc.emitir()
    ac = esc.nodo.aceptar(sobre)
    res = esc.nodo.ejecutar(ac.orden)
    esc.hc1.recibir_acuse(ac.acuse, NODO)  # control: antes de revocar se acepta
    revocar(ruta, NODO)  # el nodo se revoca con HC-1 ya en marcha
    assert _motivo(esc.hc1.recibir_resultado, res, NODO) is Motivo.KID_REVOCADO
    assert _estado(esc.hc1, ident) is Estado.ACEPTADA
    _, ident2 = esc.emitir(tarea="t-2")
    sobre2 = esc.hc1.ejecucion(ident2).sobre_orden  # type: ignore[union-attr]
    assert _motivo(esc.hc1.recibir_acuse, esc.nodo.aceptar(sobre2).acuse, NODO) is Motivo.KID_REVOCADO


def test_c2_hc1_lista_borrada_tras_crearla_rechaza_resultados_y_acuses(tmp_path: Path) -> None:
    esc, ruta = _hc1_con_lista(tmp_path)
    revocar(ruta, "kid-ajeno")
    sobre, ident = esc.emitir()
    ac = esc.nodo.aceptar(sobre)
    res = esc.nodo.ejecutar(ac.orden)
    esc.hc1.recibir_acuse(ac.acuse, NODO)  # control: lista presente, se acepta (y se ancla)
    os.unlink(ruta)
    assert _motivo(esc.hc1.recibir_resultado, res, NODO) is Motivo.REVOCACION_ILEGIBLE
    assert Motivo.REVOCACION_ILEGIBLE in esc.hc1.rechazos and _estado(esc.hc1, ident) is Estado.ACEPTADA


# =====================================================================================================================
# C3 — autorización firmada para resolver, kid de autoridad, nonce de un solo uso, at-most-once por tarea
# =====================================================================================================================


def _resolver_motivo(esc: Escena, ident: str, autorizacion: bytes, res: bytes) -> Motivo:
    return _motivo(esc.hc1.resolver_ambigua, ident, autorizacion, res)


def test_c3_autorizacion_con_firma_invalida_se_rechaza(tmp_path: Path) -> None:
    esc = Escena(tmp_path)
    ident, res = esc.ambigua()
    aut = json.loads(esc.m.autorizacion(ident))
    payload = base64.b64decode(aut["p"]).replace(b"nodo guard", b"nodo guaRd")
    adulterada = json.dumps({**aut, "p": base64.b64encode(payload).decode()}).encode()
    assert _resolver_motivo(esc, ident, adulterada, res) is Motivo.FIRMA_INVALIDA
    assert _estado(esc.hc1, ident) is Estado.AMBIGUO
    assert esc.hc1.resolver_ambigua(ident, esc.m.autorizacion(ident), res).estado is Estado.RESULTADO_FIRMADO


@pytest.mark.parametrize("quien", ["hc1", "nodo", "desconocido"])
def test_c3_autorizacion_de_un_kid_que_no_es_de_autoridad_se_rechaza(tmp_path: Path, quien: str) -> None:
    esc = Escena(tmp_path)
    ident, res = esc.ambigua()
    firmante = {"hc1": esc.m.hc1, "nodo": esc.m.nodo, "desconocido": generar_firmante("intruso-k9")}[quien]
    assert _resolver_motivo(esc, ident, esc.m.autorizacion(ident, firmante=firmante), res) is Motivo.SIN_AUTORIDAD
    assert _estado(esc.hc1, ident) is Estado.AMBIGUO


@pytest.mark.parametrize("config", [{"verificar_autoridad": None}, {"kids_autoridad": frozenset()}])
def test_c3_sin_verificador_o_sin_kids_de_autoridad_nadie_resuelve(tmp_path: Path, config: dict[str, Any]) -> None:
    esc = Escena(tmp_path, **config)
    ident, res = esc.ambigua()
    assert _resolver_motivo(esc, ident, esc.m.autorizacion(ident), res) is Motivo.SIN_AUTORIDAD
    assert _estado(esc.hc1, ident) is Estado.AMBIGUO
    ok = Escena(tmp_path / "ok")  # control: con autoridad completa, la misma autorización sí vale
    ident2, res2 = ok.ambigua()
    assert ok.hc1.resolver_ambigua(ident2, ok.m.autorizacion(ident2), res2)


def test_c3_la_firma_de_autoridad_con_otro_dominio_no_vale(tmp_path: Path) -> None:
    esc = Escena(tmp_path)
    ident, res = esc.ambigua()
    ahora = esc.m.reloj.t
    payload = payload_resolucion(ident, "m", ahora, ahora + 60, "12345678-1234-4234-8234-123456789012")
    como_orden = esc.m.autoridad.firmar(DOMINIO_ORDEN, payload)  # misma clave, dominio equivocado
    assert _resolver_motivo(esc, ident, como_orden, res) is Motivo.FIRMA_INVALIDA
    assert esc.hc1.resolver_ambigua(ident, esc.m.autoridad.firmar(DOMINIO_RESOLUCION, payload), res)  # control


def test_c3_autorizacion_caducada_demasiado_larga_o_del_futuro_se_rechaza(tmp_path: Path) -> None:
    esc = Escena(tmp_path)
    ident, res = esc.ambigua()
    ahora = esc.m.reloj.t
    assert _resolver_motivo(esc, ident, esc.m.autorizacion(ident, emitida_en=ahora - 100, caduca_en=ahora - 1), res) \
        is Motivo.AUTORIZACION_CADUCADA  # fmt: skip
    assert _resolver_motivo(esc, ident, esc.m.autorizacion(ident, caduca_en=ahora + 100_000), res) \
        is Motivo.CADUCIDAD_EXCESIVA  # fmt: skip
    assert _resolver_motivo(esc, ident, esc.m.autorizacion(ident, emitida_en=ahora + 60, caduca_en=ahora + 120), res) \
        is Motivo.EMITIDA_EN_EL_FUTURO  # fmt: skip
    assert _estado(esc.hc1, ident) is Estado.AMBIGUO
    assert esc.hc1.resolver_ambigua(ident, esc.m.autorizacion(ident), res)  # control: vigente


def test_c3_el_nonce_es_de_un_solo_uso_y_sobrevive_al_reinicio(tmp_path: Path) -> None:
    esc = Escena(tmp_path)
    id_a, res_a = esc.ambigua("t-a")
    id_b, res_b = esc.ambigua("t-b")
    nonce = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
    esc.hc1.resolver_ambigua(id_a, esc.m.autorizacion(id_a, nonce=nonce), res_a)
    assert _resolver_motivo(esc, id_b, esc.m.autorizacion(id_b, nonce=nonce), res_b) is Motivo.NONCE_REUTILIZADO
    h = esc.reiniciar_hc1()  # proceso nuevo: el nonce usado se reconstruye del diario
    assert _motivo(h.resolver_ambigua, id_b, esc.m.autorizacion(id_b, nonce=nonce), res_b) is Motivo.NONCE_REUTILIZADO
    assert h.resolver_ambigua(id_b, esc.m.autorizacion(id_b), res_b)  # control: nonce nuevo


def test_c3_la_autorizacion_es_de_una_ejecucion_concreta(tmp_path: Path) -> None:
    esc = Escena(tmp_path)
    id_a, res_a = esc.ambigua("t-a")
    id_b, _ = esc.ambigua("t-b")
    assert _resolver_motivo(esc, id_a, esc.m.autorizacion(id_b), res_a) is Motivo.VINCULO_ROTO
    assert esc.hc1.resolver_ambigua(id_a, esc.m.autorizacion(id_a), res_a)  # control


@pytest.mark.parametrize("cambio", [{"decision": "rechazar"}, {"motivo": "  "}, {"motivo": "x" * 300}])
def test_c3_decision_y_motivo_del_esquema_cerrado(tmp_path: Path, cambio: dict[str, Any]) -> None:
    esc = Escena(tmp_path)
    ident, res = esc.ambigua()
    campos = {
        "v": 1, "alg": "ed25519", "id_ejecucion": ident, "decision": "admitir", "motivo": "m",
        "emitida_en": esc.m.reloj.t, "caduca_en": esc.m.reloj.t + 60, "nonce": "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
    }  # fmt: skip
    firmada = esc.m.autoridad.firmar(DOMINIO_RESOLUCION, bytes_canonicos({**campos, **cambio}))
    assert _resolver_motivo(esc, ident, firmada, res) is Motivo.CAMPO_INVALIDO
    extra = esc.m.autoridad.firmar(DOMINIO_RESOLUCION, bytes_canonicos({**campos, "por": "mauricio"}))
    assert _resolver_motivo(esc, ident, extra, res) is Motivo.CAMPOS_DESCONOCIDOS
    assert esc.hc1.resolver_ambigua(ident, esc.m.autoridad.firmar(DOMINIO_RESOLUCION, bytes_canonicos(campos)), res)


def test_c3_la_autoridad_no_puede_ser_la_clave_de_hc1_ni_la_de_un_nodo(tmp_path: Path) -> None:
    m = mundo()
    base: dict[str, Any] = {"verificar_autoridad": m.verificador_autoridad(), "kid_hc1": "hc1-k1"}
    for malo in ("hc1-k1", NODO, OTRO_NODO):
        with pytest.raises(ValueError):
            SeguimientoHC1(m.verificador_nodos(), m.reloj, kids_autoridad=frozenset({malo}), **base)
    SeguimientoHC1(m.verificador_nodos(), m.reloj, kids_autoridad=frozenset({KID_AUTORIDAD}), **base)  # control


# --- at-most-once POR TAREA -----------------------------------------------------------------------------------------


@pytest.fixture
def con_capacidad_con_efectos(monkeypatch: pytest.MonkeyPatch) -> None:
    efectos = Capacidad(
        "escribir_nota_externa", lambda a: dict(a), lambda a: "ok", lambda a, s: True, idempotente=False
    )
    monkeypatch.setattr(delegacion_hc1, "CAPACIDADES", {**CAPACIDADES, efectos.nombre: efectos})


def test_c3_calcular_resumen_sha256_se_declara_idempotente_y_toda_capacidad_declara_el_campo() -> None:
    assert CAPACIDADES["calcular_resumen_sha256"].idempotente is True
    assert all(isinstance(c.idempotente, bool) for c in CAPACIDADES.values())


def _emitir_directo(esc: Escena, **cambios: Any) -> Any:
    return esc.hc1.registrar_emision(firmante_orden(esc.m.hc1, campos_validos(**cambios)), 60)


@pytest.mark.parametrize("como", ["ambiguo", "interrumpida", "incorporacion_incierta"])
def test_c3_capacidad_no_idempotente_con_intento_incierto_no_se_reemite(
    tmp_path: Path, con_capacidad_con_efectos: None, como: str
) -> None:
    esc = Escena(tmp_path, diario=False)
    cap = {"capacidad": "escribir_nota_externa", "tarea": "t-9"}
    ej = _emitir_directo(esc, **cap, intento=1)
    if como == "ambiguo":
        esc.hc1.recibir_acuse(
            esc.m.nodo.firmar(DOMINIO_ACUSE, bytes_canonicos(_payload_acuse(esc, ej.id_ejecucion))), NODO
        )
        esc.m.reloj.t += 1000
        esc.hc1.vencer()
        assert ej.estado is Estado.AMBIGUO
    elif como == "interrumpida":
        esc.hc1.marcar_desconexion(NODO)
        assert ej.estado is Estado.INTERRUMPIDA
    else:
        ej.estado = Estado.INCORPORACION_INCIERTA
    assert _motivo(_emitir_directo, esc, **cap, intento=2) is Motivo.TAREA_CON_INTENTO_AMBIGUO
    assert len(esc.hc1._por_id) == 1  # no se emitió nada
    _emitir_directo(esc, **{**cap, "tarea": "t-10"}, intento=1)  # control: OTRA tarea no está bloqueada


@pytest.mark.parametrize("como", ["ambiguo", "interrumpida"])
def test_c3_control_capacidad_idempotente_si_se_reemite(tmp_path: Path, como: str) -> None:
    esc = Escena(tmp_path, diario=False)
    ej = _emitir_directo(esc, tarea="t-9", intento=1)
    if como == "ambiguo":
        esc.hc1.recibir_acuse(
            esc.m.nodo.firmar(DOMINIO_ACUSE, bytes_canonicos(_payload_acuse(esc, ej.id_ejecucion))), NODO
        )
        esc.m.reloj.t += 1000
        esc.hc1.vencer()
    else:
        esc.hc1.marcar_desconexion(NODO)
    assert ej.estado in (Estado.AMBIGUO, Estado.INTERRUMPIDA)
    assert _emitir_directo(esc, tarea="t-9", intento=2).intento == 2


def test_c3_una_capacidad_desconocida_para_el_registro_se_trata_como_no_idempotente(tmp_path: Path) -> None:
    esc = Escena(tmp_path, diario=False)
    ej = _emitir_directo(esc, capacidad="capacidad_inventada", tarea="t-9", intento=1)
    esc.hc1.marcar_desconexion(NODO)
    assert ej.estado is Estado.INTERRUMPIDA
    assert _motivo(_emitir_directo, esc, capacidad="capacidad_inventada", tarea="t-9", intento=2) \
        is Motivo.TAREA_CON_INTENTO_AMBIGUO  # fmt: skip


# =====================================================================================================================
# BAJO a — recuperación del diario: firmas y transiciones re-verificadas, diario manipulado => fallo cerrado
# =====================================================================================================================


def _reescribir(tmp_path: Path, transformar: Any) -> None:
    ruta = tmp_path / "hc1" / NOMBRE
    registros = [json.loads(x) for x in ruta.read_text().splitlines()]
    nuevos = transformar(registros)
    ruta.write_text("".join(json.dumps(r, sort_keys=True, separators=(",", ":")) + "\n" for r in nuevos))


def _reinicio_falla(esc: Escena) -> None:
    assert _motivo(esc.reiniciar_hc1) is Motivo.DIARIO_ILEGIBLE


def test_bajo_a_un_resultado_con_firma_rota_en_el_diario_falla_cerrado(tmp_path: Path) -> None:
    esc = Escena(tmp_path)
    esc.hasta_validado()
    esc.reiniciar_hc1()  # control: el diario íntegro se recupera

    def romper(rs: list[dict[str, Any]]) -> list[dict[str, Any]]:
        for r in rs:
            if r["ev"] == "resultado":
                sobre = json.loads(base64.b64decode(r["sobre"]))
                sobre["p"] = base64.b64encode(
                    base64.b64decode(sobre["p"]).replace(b'"salida":"', b'"salida":"0')
                ).decode()
                r["sobre"] = base64.b64encode(json.dumps(sobre).encode()).decode()
        return rs

    _reescribir(tmp_path, romper)
    _reinicio_falla(esc)


def test_bajo_a_un_resultado_de_otra_ejecucion_en_el_diario_falla_cerrado(tmp_path: Path) -> None:
    esc = Escena(tmp_path)
    a = esc.hasta_validado(tarea="t-a")
    b = esc.hasta_validado(tarea="t-b")
    assert a != b

    def intercambiar(rs: list[dict[str, Any]]) -> list[dict[str, Any]]:
        res = [r for r in rs if r["ev"] == "resultado"]
        res[0]["sobre"], res[1]["sobre"] = res[1]["sobre"], res[0]["sobre"]
        return rs

    _reescribir(tmp_path, intercambiar)
    _reinicio_falla(esc)


def test_bajo_a_una_resolucion_con_autorizacion_falsa_o_nonce_repetido_en_el_diario_falla_cerrado(
    tmp_path: Path,
) -> None:
    esc = Escena(tmp_path)
    id_a, res_a = esc.ambigua("t-a")
    id_b, res_b = esc.ambigua("t-b")
    esc.hc1.resolver_ambigua(id_a, esc.m.autorizacion(id_a, nonce="cccccccc-cccc-4ccc-8ccc-cccccccccccc"), res_a)
    esc.hc1.resolver_ambigua(id_b, esc.m.autorizacion(id_b), res_b)
    esc.reiniciar_hc1()  # control

    def autorizacion_de_intruso(rs: list[dict[str, Any]]) -> list[dict[str, Any]]:
        falsa = esc.m.autorizacion(id_a, firmante=generar_firmante(KID_AUTORIDAD))  # mismo kid, OTRA clave
        for r in rs:
            if r["ev"] == "resolucion" and r["id"] == id_a:
                r["autorizacion"] = base64.b64encode(falsa).decode()
        return rs

    original = (tmp_path / "hc1" / NOMBRE).read_text()
    _reescribir(tmp_path, autorizacion_de_intruso)
    _reinicio_falla(esc)
    (tmp_path / "hc1" / NOMBRE).write_text(original)

    def nonce_repetido(rs: list[dict[str, Any]]) -> list[dict[str, Any]]:
        # la autorización de B es auténtica y de B, pero reutiliza el nonce de la de A
        reutiliza = esc.m.autorizacion(id_b, nonce="cccccccc-cccc-4ccc-8ccc-cccccccccccc")
        for r in rs:
            if r["ev"] == "resolucion" and r["id"] == id_b:
                r["autorizacion"] = base64.b64encode(reutiliza).decode()
        return rs

    _reescribir(tmp_path, nonce_repetido)
    _reinicio_falla(esc)


@pytest.mark.parametrize("estado", ["incorporado", "validado", "emitida", "resultado_firmado", "zzz"])
def test_bajo_a_las_interrupciones_del_diario_solo_pueden_ser_interrumpida_o_ambiguo(
    tmp_path: Path, estado: str
) -> None:
    esc = Escena(tmp_path)
    esc.emitir()
    esc.hc1.marcar_desconexion(NODO)
    assert (
        _estado(esc.reiniciar_hc1(), esc.hc1._por_id and next(iter(esc.hc1._por_id))) is Estado.INTERRUMPIDA
    )  # control

    def forzar(rs: list[dict[str, Any]]) -> list[dict[str, Any]]:
        for r in rs:
            if r["ev"] == "interrupcion":
                r["estado"] = estado
        return rs

    _reescribir(tmp_path, forzar)
    _reinicio_falla(esc)


def test_bajo_a_transiciones_imposibles_en_el_diario_fallan_cerrado(tmp_path: Path) -> None:
    esc = Escena(tmp_path)
    _, ident = esc.emitir()
    ruta = tmp_path / "hc1" / NOMBRE
    original = ruta.read_text()
    for ev in ("incorporado", "incorporando", "validacion"):  # saltos: nunca hubo resultado ni validación
        extra = {"ev": ev, "id": ident, "ok": True}
        ruta.write_text(original + json.dumps(extra, sort_keys=True) + "\n")
        _reinicio_falla(esc)
    ruta.write_text(original + json.dumps({"ev": "interrupcion", "id": ident, "estado": "ambiguo"}) + "\n")
    _reinicio_falla(esc)  # EMITIDA solo se interrumpe a INTERRUMPIDA
    ruta.write_text(original + original.splitlines()[0] + "\n")
    _reinicio_falla(esc)  # emisión repetida
    ruta.write_text(original)
    assert _estado(esc.reiniciar_hc1(), ident) is Estado.EMITIDA  # control


# =====================================================================================================================
# BAJO b — ejecutar revalida caducidad y revocación y comprueba que ejecuta LO CONSUMIDO
# =====================================================================================================================


def _nodo_simple(tmp_path: Path, **kw: Any) -> tuple[Mundo, NodoDelegado, AlmacenConsumidas]:
    m = mundo()
    alm = AlmacenConsumidas(tmp_path / "nodo")
    return m, NodoDelegado(m.politica(**kw), m.verificador_hc1(), alm, m.nodo.firmar), alm


def test_bajo_b_una_orden_que_caduca_entre_aceptar_y_ejecutar_no_se_ejecuta(tmp_path: Path) -> None:
    m, nodo, alm = _nodo_simple(tmp_path)
    ac = nodo.aceptar(firmante_orden(m.hc1, campos_validos()))
    m.reloj.t = T0 + 61  # pasó caduca_en = T0 + 60
    assert _motivo(nodo.ejecutar, ac.orden) is Motivo.ORDEN_CADUCADA
    assert alm.estado(ac.orden.campos["id_ejecucion"]).value == "consumida"  # type: ignore[union-attr]  # ni se inició
    otra = nodo.aceptar(firmante_orden(m.hc1, campos_validos(emitida_en=T0 + 61, caduca_en=T0 + 120)))
    assert nodo.ejecutar(otra.orden)  # control: dentro de plazo se ejecuta


def test_bajo_b_un_kid_revocado_entre_aceptar_y_ejecutar_no_se_ejecuta(tmp_path: Path) -> None:
    lista, ruta, _ = _lista(tmp_path)
    m, nodo = _nodo_con_lista(tmp_path, lista)
    ac = nodo.aceptar(firmante_orden(m.hc1, campos_validos()))
    revocar(ruta, "hc1-k1")
    assert _motivo(nodo.ejecutar, ac.orden) is Motivo.KID_REVOCADO
    assert nodo.estado(ac.orden.campos["id_ejecucion"]).value == "consumida"  # type: ignore[union-attr]
    m2, nodo2 = _nodo_con_lista(tmp_path / "otro", _lista(tmp_path / "otro")[0])
    assert nodo2.ejecutar(nodo2.aceptar(firmante_orden(m2.hc1, campos_validos())).orden)  # control: sin revocar


def test_bajo_b_una_orden_valida_adulterada_en_memoria_no_se_ejecuta(tmp_path: Path) -> None:
    m, nodo, _ = _nodo_simple(tmp_path)
    orden = nodo.aceptar(firmante_orden(m.hc1, campos_validos())).orden
    otros_args = MappingProxyType({**orden.campos, "argumentos": {"texto": "OTRO TEXTO"}})
    with pytest.raises(RechazoOrden) as e:
        nodo.ejecutar(dataclasses.replace(orden, campos=otros_args))
    assert e.value.motivo is Motivo.VINCULO_ROTO and "campos" in str(e.value)
    with pytest.raises(RechazoOrden) as e2:
        nodo.ejecutar(dataclasses.replace(orden, hash_tarea="0" * 64))
    assert e2.value.motivo is Motivo.VINCULO_ROTO and "hash_tarea" in str(e2.value)
    assert nodo.ejecutar(orden)  # control: la auténtica sí


def test_bajo_b_se_ejecuta_lo_consumido_no_otra_orden_con_el_mismo_id(tmp_path: Path) -> None:
    m, nodo, alm = _nodo_simple(tmp_path)
    ident = campos_validos()["id_ejecucion"]
    consumida = nodo.aceptar(firmante_orden(m.hc1, campos_validos(id_ejecucion=ident)))
    otra = validar_orden(  # OTRA orden, firmada por HC-1, con el MISMO id_ejecucion, validada contra otro almacén
        firmante_orden(m.hc1, campos_validos(id_ejecucion=ident, argumentos={"texto": "distinto"})),
        politica=m.politica(), verificar=m.verificador_hc1(), almacen=AlmacenMemoria(),
    )  # fmt: skip
    assert otra.hash_tarea != consumida.orden.hash_tarea
    with pytest.raises(RechazoOrden) as e:
        nodo.ejecutar(otra)  # internamente coherente, pero no es la consumida
    assert e.value.motivo is Motivo.VINCULO_ROTO and "consumida" in str(e.value)
    assert nodo.ejecutar(consumida.orden)  # control
    assert alm.hash_consumido(ident) == consumida.orden.hash_tarea


def test_bajo_b_el_consumo_liga_el_hash_y_persiste(tmp_path: Path) -> None:
    alm = AlmacenConsumidas(tmp_path / "a")
    alm.consumir("id-1", 1, "ab" * 32)
    alm.consumir("id-2", 1)
    nuevo = AlmacenConsumidas(tmp_path / "a")  # proceso nuevo
    assert nuevo.hash_consumido("id-1") == "ab" * 32
    assert nuevo.hash_consumido("id-2") is None and nuevo.hash_consumido("id-3") is None


# =====================================================================================================================
# BAJO c — firmador: flock + O_NOFOLLOW en el log, tope de rechazos escritos, lstat del directorio del socket
# =====================================================================================================================

PET = {"tarea": "t-1", "intento": 1, "destinatario": NODO, "capacidad": "calcular_resumen_sha256",
       "argumentos": {"texto": "hola"}, "vida_s": 60}  # fmt: skip


class Reloj:
    def __init__(self, t: float = 5000.0) -> None:
        self.t = t

    def __call__(self) -> float:
        return self.t


def _firmador(tmp_path: Path, reloj: Reloj | None = None, **kw: Any) -> tuple[Firmador, Path]:
    d = tmp_path / "f"
    d.mkdir(mode=0o700, exist_ok=True)
    pol: dict[str, Any] = {"emisor": "hc1", "kid": "hc1-k1", "destinatarios": frozenset({NODO}),
                           "capacidades": frozenset({"calcular_resumen_sha256"}), "epoch": 7}  # fmt: skip
    pol.update(kw)
    return Firmador(
        generar_firmante("hc1-k1"), PoliticaFirmador(**pol), d / "log.jsonl", ahora=reloj or Reloj()
    ), d / "log.jsonl"


def test_bajo_c_el_log_no_sigue_enlaces_simbolicos(tmp_path: Path) -> None:
    fm, log = _firmador(tmp_path)
    fm.firmar(PET)  # control: escribe en el log
    destino = tmp_path / "f" / "destino.jsonl"
    destino.write_bytes(b"")
    os.chmod(destino, 0o600)  # el destino es un fichero seguro: solo el enlace simbólico lo delata
    os.unlink(log)
    log.symlink_to(destino)  # alguien sustituye el log por un enlace
    with pytest.raises(ErrorFirmador):
        fm.firmar(PET)
    assert destino.read_bytes() == b""  # NO se escribió a través del enlace


def test_bajo_c_el_log_se_escribe_bajo_flock_exclusivo(tmp_path: Path) -> None:
    fm, log = _firmador(tmp_path)
    fm.firmar(PET)
    fd = os.open(log, os.O_RDWR)
    fcntl.flock(fd, fcntl.LOCK_EX)
    hecho = threading.Event()
    hilo = threading.Thread(target=lambda: (fm.firmar(PET), hecho.set()), daemon=True)
    hilo.start()
    assert not hecho.wait(0.4)  # espera al cerrojo
    os.close(fd)
    assert hecho.wait(3)
    hilo.join(3)
    assert verificar_cadena_log(log)[0] == 2


def test_bajo_c_la_cadena_se_continua_desde_el_disco_aunque_escriba_otra_instancia(tmp_path: Path) -> None:
    a, log = _firmador(tmp_path)
    a.firmar(PET)
    b = Firmador(generar_firmante("hc1-k1"), a._pol, log, ahora=Reloj())  # segunda instancia sobre el mismo log
    b.firmar(PET)
    a.firmar(PET)  # `a` no vio lo que escribió `b`: prev se toma del fichero, no de la memoria
    assert verificar_cadena_log(log)[0] == 3


def test_bajo_c_tope_de_rechazos_escritos_por_ventana_y_declaracion_de_suprimidos(tmp_path: Path) -> None:
    reloj = Reloj(1000.0)
    fm, log = _firmador(tmp_path, reloj, tasa_max=1000, tasa_ventana_s=10.0, rechazos_log_max=3)
    for _ in range(10):
        with pytest.raises(RechazoOrden):
            fm.firmar({**PET, "capacidad": "ejecutar_comando"})
    entradas = [json.loads(x) for x in log.read_text().splitlines()]
    assert [e["tipo"] for e in entradas] == ["rechazo"] * 3  # el log NO se infla
    assert fm.rechazos_suprimidos == 7
    reloj.t = 1011.0  # nueva ventana: el siguiente rechazo escrito DECLARA lo suprimido
    with pytest.raises(RechazoOrden):
        fm.firmar({**PET, "capacidad": "ejecutar_comando"})
    ultimo = json.loads(log.read_text().splitlines()[-1])
    assert ultimo["suprimidos"] == 7 and fm.rechazos_suprimidos == 0
    assert "suprimidos" not in json.loads(log.read_text().splitlines()[0])
    assert verificar_cadena_log(log)[0] == 4
    assert fm.firmar(PET)  # control: una firma legítima sigue pudiendo registrarse


def test_bajo_c_rechazos_de_tasa_tambien_respetan_el_tope(tmp_path: Path) -> None:
    fm, log = _firmador(tmp_path, Reloj(1000.0), tasa_max=1, tasa_ventana_s=100.0, rechazos_log_max=2)
    fm.firmar(PET)
    for _ in range(6):
        with pytest.raises(RechazoOrden) as e:
            fm.firmar(PET)
        assert e.value.motivo is Motivo.TASA_EXCEDIDA
    assert [json.loads(x)["tipo"] for x in log.read_text().splitlines()] == ["firma", "rechazo", "rechazo"]


def test_bajo_c_crear_servidor_usa_lstat_del_directorio_y_no_sigue_enlaces(tmp_path: Path) -> None:
    fm, _ = _firmador(tmp_path)
    real = tmp_path / "real"
    real.mkdir(mode=0o700)
    enlace = tmp_path / "enlace"
    enlace.symlink_to(real)
    with pytest.raises(ErrorClave):
        crear_servidor(fm, enlace / "f.sock", frozenset({os.getuid()}))
    srv = crear_servidor(fm, real / "f.sock", frozenset({os.getuid()}))  # control: el directorio real sí
    srv.server_close()
    assert time.monotonic() > 0
