"""3.ª revisión de seguridad independiente de la delegación: ALTO-1 (instancia única por diario), MEDIO-2 (at-most-once
por tarea para lo no idempotente), MEDIO-3/4 (configuración explícita y obligatoria), MEDIO-5 (relectura del diario sin
confiar en él), MEDIO-6 (tope de escrituras del firmador) y los BAJOS 1-6.

Todo en tmp_path; claves solo de prueba. Cada prueba lleva su caso de CONTROL (el camino legítimo sí funciona).
"""

from __future__ import annotations

import base64
import json
import os
import stat
import subprocess
import sys
import threading
from pathlib import Path
from typing import Any

import pytest

from aura_skeleton.adapters.almacen_consumidas import AlmacenConsumidas
from aura_skeleton.adapters.diario_hc1 import NOMBRE_CENTINELA, DiarioHC1
from aura_skeleton.adapters.firma_delegacion import generar_firmante, revocar, verificador_de
from aura_skeleton.core import delegacion_nodo
from aura_skeleton.core.delegacion import (
    DOMINIO_RESULTADO,
    Capacidad,
    EstadoNodo,
    Motivo,
    PoliticaNodo,
    RechazoOrden,
    SinRevocacion,
    payload_resultado,
)
from aura_skeleton.core.delegacion_hc1 import RECHAZOS_MEMORIA_MAX, Estado, SeguimientoHC1
from aura_skeleton.core.delegacion_nodo import NodoDelegado
from tests.delegacion_apoyo import (
    KID_AUTORIDAD,
    NODO,
    RegistroSintetico,
    campos_validos,
    firmante_orden,
    mundo,
)
from tests.unit.test_delegacion_revision2 import (
    PET,
    Escena,
    Reloj,
    _estado,
    _firmador,
    _lista,
    _motivo,
    _reescribir,
    _reinicio_falla,
    _revocar,
    con_capacidad_con_efectos,  # noqa: F401 - fixture reutilizada
)

RAIZ = Path(__file__).resolve().parents[2]

# =====================================================================================================================
# ALTO-1 — instancia única por diario (flock del centinela), en el mismo proceso y entre procesos
# =====================================================================================================================


def test_alto1_un_segundo_diario_sobre_el_mismo_directorio_falla_cerrado_y_tras_cerrar_arranca(tmp_path: Path) -> None:
    primero = DiarioHC1(tmp_path / "d")
    assert _motivo(DiarioHC1, tmp_path / "d") is Motivo.INSTANCIA_DUPLICADA
    primero.anotar({"ev": "x"})  # la primera instancia sigue operativa
    primero.cerrar()
    segundo = DiarioHC1(tmp_path / "d")  # control: tras cerrar, otra instancia arranca
    assert segundo.recuperar()[0] == [{"ev": "x"}]
    assert _motivo(DiarioHC1, tmp_path / "d") is Motivo.INSTANCIA_DUPLICADA  # y ahora es ELLA la única


def test_alto1_un_diario_cerrado_no_anota_ni_recupera(tmp_path: Path) -> None:
    d = DiarioHC1(tmp_path / "d")
    d.anotar({"ev": "a"})
    d.cerrar()
    d.cerrar()  # idempotente
    assert not d.abierto
    assert _motivo(d.anotar, {"ev": "b"}) is Motivo.INSTANCIA_DUPLICADA
    assert _motivo(d.recuperar) is Motivo.INSTANCIA_DUPLICADA
    otro = DiarioHC1(tmp_path / "d")
    assert otro.recuperar()[0] == [{"ev": "a"}]  # control: nada se escribió desde la instancia cerrada


def test_alto1_dos_seguimientos_sobre_el_mismo_diario_el_segundo_no_arranca(tmp_path: Path) -> None:
    esc = Escena(tmp_path)
    m = esc.m
    with pytest.raises(RechazoOrden) as e:
        SeguimientoHC1(m.verificador_nodos(), m.reloj, diario=DiarioHC1(tmp_path / "hc1"), **m.config_hc1())
    assert e.value.motivo is Motivo.INSTANCIA_DUPLICADA
    esc.emitir()  # la primera sigue operativa
    esc.hc1.cerrar()
    segundo = SeguimientoHC1(m.verificador_nodos(), m.reloj, diario=DiarioHC1(tmp_path / "hc1"), **m.config_hc1())
    assert segundo.recuperadas == 1  # control: tras cerrar la primera, la segunda arranca y ve su historia


_CODIGO_HIJO = """
import sys
from pathlib import Path
from aura_skeleton.adapters.diario_hc1 import DiarioHC1
d = DiarioHC1(Path(sys.argv[1]))
print("listo", flush=True)
sys.stdin.readline()
"""


def _hijo_con_el_diario(directorio: Path) -> subprocess.Popen[str]:
    proc = subprocess.Popen(
        [sys.executable, "-c", _CODIGO_HIJO, str(directorio)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        text=True,
        cwd=RAIZ,
        env={**os.environ, "PYTHONPATH": str(RAIZ)},
    )
    assert proc.stdout is not None and proc.stdout.readline().strip() == "listo"
    return proc


def test_alto1_dos_procesos_el_segundo_no_arranca_y_si_el_primero_muere(tmp_path: Path) -> None:
    hijo = _hijo_con_el_diario(tmp_path / "d")
    try:
        assert _motivo(DiarioHC1, tmp_path / "d") is Motivo.INSTANCIA_DUPLICADA  # otro PROCESO la tiene
        m = mundo()
        with pytest.raises(RechazoOrden) as e:
            SeguimientoHC1(m.verificador_nodos(), m.reloj, diario=DiarioHC1(tmp_path / "d"), **m.config_hc1())
        assert e.value.motivo is Motivo.INSTANCIA_DUPLICADA
    finally:
        hijo.kill()  # SIGKILL: el kernel suelta el flock aunque el proceso no pueda limpiar nada
        hijo.wait(10)
    assert DiarioHC1(tmp_path / "d").abierto  # control: muerto el primero, el segundo arranca


def test_alto1_el_centinela_no_sigue_enlaces_simbolicos(tmp_path: Path) -> None:
    d = tmp_path / "d"
    d.mkdir(mode=0o700)
    destino = tmp_path / "destino"
    destino.write_bytes(b"")
    os.chmod(destino, 0o600)  # destino seguro: solo el enlace lo delata
    (d / NOMBRE_CENTINELA).symlink_to(destino)
    assert _motivo(DiarioHC1, d) is Motivo.DIARIO_NO_DURABLE
    (d / NOMBRE_CENTINELA).unlink()
    assert DiarioHC1(d).abierto  # control: sin enlace, arranca


def test_alto1_el_centinela_es_privado_y_no_se_retira(tmp_path: Path) -> None:
    DiarioHC1(tmp_path / "d").cerrar()
    ruta = tmp_path / "d" / NOMBRE_CENTINELA
    assert stat.S_IMODE(os.stat(ruta).st_mode) == 0o600 and ruta.exists()  # no se borra al cerrar (G-1: sin unlink)
    os.chmod(ruta, 0o644)
    assert _motivo(DiarioHC1, tmp_path / "d") is Motivo.DIARIO_NO_DURABLE  # centinela con permisos abiertos


class _RegistroEspia(RegistroSintetico):
    def __init__(self) -> None:
        super().__init__()
        self.llamadas = 0

    def __call__(self, hecho: dict[str, Any]) -> None:
        self.llamadas += 1
        super().__call__(hecho)


def test_alto1_incorporar_va_bajo_la_instancia_unica_sin_instancia_no_consulta_ni_registra(tmp_path: Path) -> None:
    esc = Escena(tmp_path)
    ident = esc.hasta_validado()
    registro = _RegistroEspia()
    esc.hc1.ejecucion(ident).estado = Estado.INCORPORACION_INCIERTA  # type: ignore[union-attr]
    esc.hc1.cerrar()  # esta instancia ya no es la única: otra podría estar registrando
    assert _motivo(esc.hc1.incorporar, ident, registro) is Motivo.INSTANCIA_DUPLICADA
    assert registro.llamadas == 0 and registro == []
    otra = esc.reiniciar_hc1()  # control: la instancia vigente sí incorpora, UNA vez
    otra.incorporar(ident, registro)
    assert registro.llamadas == 1 and _estado(otra, ident) is Estado.INCORPORADO


def test_alto1_dos_hilos_incorporando_a_la_vez_registran_una_sola_vez(tmp_path: Path) -> None:
    esc = Escena(tmp_path)
    ident = esc.hasta_validado()
    registro = _RegistroEspia()
    resultados: list[object] = []

    def intentar() -> None:
        try:
            esc.hc1.incorporar(ident, registro)
            resultados.append("ok")
        except RechazoOrden as e:
            resultados.append(e.motivo)

    hilos = [threading.Thread(target=intentar) for _ in range(6)]
    for h in hilos:
        h.start()
    for h in hilos:
        h.join()
    assert registro.llamadas == 1 and len(registro) == 1  # ya_registrado -> registrar es atómico
    assert resultados.count("ok") == 1


def test_alto1_el_nonce_no_se_consume_dos_veces_con_instancias_sucesivas(tmp_path: Path) -> None:
    esc = Escena(tmp_path)
    id_a, res_a = esc.ambigua("t-a")
    id_b, res_b = esc.ambigua("t-b")
    nonce = "dddddddd-dddd-4ddd-8ddd-dddddddddddd"
    esc.hc1.resolver_ambigua(id_a, esc.m.autorizacion(id_a, res_a, nonce=nonce), res_a)
    m = esc.m
    with pytest.raises(
        RechazoOrden
    ) as e:  # mientras la primera vive, no hay segunda instancia con otro estado de nonces
        SeguimientoHC1(m.verificador_nodos(), m.reloj, diario=DiarioHC1(tmp_path / "hc1"), **m.config_hc1())
    assert e.value.motivo is Motivo.INSTANCIA_DUPLICADA
    segunda = esc.reiniciar_hc1()  # control: sucesiva (la primera cerró) y CONOCE el nonce ya gastado
    assert _motivo(segunda.resolver_ambigua, id_b, esc.m.autorizacion(id_b, res_b, nonce=nonce), res_b) \
        is Motivo.NONCE_REUTILIZADO  # fmt: skip
    assert segunda.resolver_ambigua(id_b, esc.m.autorizacion(id_b, res_b), res_b)


# =====================================================================================================================
# MEDIO-2 — lo no idempotente no se reemite con NINGÚN intento previo
# =====================================================================================================================

POSTERIORES_A_LA_EMISION = [
    Estado.EMITIDA,
    Estado.ACEPTADA,
    Estado.RESULTADO_FIRMADO,
    Estado.VALIDADO,
    Estado.VERIFICACION_FALLIDA,
    Estado.INCORPORANDO,
    Estado.INCORPORACION_INCIERTA,
    Estado.INCORPORADO,
    Estado.AMBIGUO,
    Estado.INTERRUMPIDA,
]


def _emitir_directo(esc: Escena, **cambios: Any) -> Any:
    return esc.hc1.registrar_emision(firmante_orden(esc.m.hc1, campos_validos(**cambios)), 60)


def test_medio2_la_lista_de_estados_bloqueantes_es_exactamente_la_de_la_revision() -> None:
    assert set(POSTERIORES_A_LA_EMISION) == set(Estado)  # no hay estado posterior a la emisión que quede fuera


@pytest.mark.parametrize("estado", POSTERIORES_A_LA_EMISION)
@pytest.mark.usefixtures("con_capacidad_con_efectos")
def test_medio2_capacidad_no_idempotente_no_se_reemite_con_un_intento_previo_en_cualquier_estado(
    tmp_path: Path,
    estado: Estado,
) -> None:
    esc = Escena(tmp_path)
    cap = {"capacidad": "escribir_nota_externa", "tarea": "t-9"}
    previo = _emitir_directo(esc, **cap, intento=1)
    previo.estado = estado
    assert _motivo(_emitir_directo, esc, **cap, intento=2) is Motivo.TAREA_CON_INTENTO_AMBIGUO
    assert len(esc.hc1._por_id) == 1  # no se emitió nada
    assert _emitir_directo(esc, **{**cap, "tarea": "t-10"}, intento=1)  # control: otra tarea no está bloqueada


@pytest.mark.parametrize("estado", POSTERIORES_A_LA_EMISION)
def test_medio2_control_capacidad_idempotente_conserva_la_regla_actual(tmp_path: Path, estado: Estado) -> None:
    esc = Escena(tmp_path)
    previo = _emitir_directo(esc, tarea="t-9", intento=1)
    previo.estado = estado
    if estado in (Estado.EMITIDA, Estado.ACEPTADA):  # un intento VIVO sigue bloqueando (regla existente)
        assert _motivo(_emitir_directo, esc, tarea="t-9", intento=2) is Motivo.EJECUCION_NO_EN_CURSO
    else:
        assert _emitir_directo(esc, tarea="t-9", intento=2).intento == 2


@pytest.mark.usefixtures("con_capacidad_con_efectos")
def test_medio2_un_intento_incorporado_de_lo_no_idempotente_tampoco_se_repite(
    tmp_path: Path,
) -> None:
    esc = Escena(tmp_path)
    ej = _emitir_directo(esc, capacidad="escribir_nota_externa", tarea="t-9", intento=1)
    ej.estado = Estado.INCORPORADO
    assert _motivo(_emitir_directo, esc, capacidad="escribir_nota_externa", tarea="t-9", intento=2) \
        is Motivo.TAREA_CON_INTENTO_AMBIGUO  # fmt: skip
    esc2 = Escena(tmp_path / "ctrl")  # control: la misma secuencia con la capacidad idempotente SÍ avanza
    ej2 = _emitir_directo(esc2, tarea="t-9", intento=1)
    ej2.estado = Estado.INCORPORADO
    assert _emitir_directo(esc2, tarea="t-9", intento=2).intento == 2


# =====================================================================================================================
# MEDIO-3 / MEDIO-4 — configuración explícita y obligatoria
# =====================================================================================================================


def _construir(tmp_path: Path, quitar: tuple[str, ...] = (), n: int = 0, **cambios: Any) -> SeguimientoHC1:
    m = mundo()
    conf = m.config_hc1(**cambios)
    for k in quitar:
        del conf[k]
    if "diario" not in conf:
        conf["diario"] = DiarioHC1(tmp_path / f"d{n}")
    return SeguimientoHC1(m.verificador_nodos(), m.reloj, **conf)


def test_medio3_el_control_de_construccion_completa_funciona(tmp_path: Path) -> None:
    assert _construir(tmp_path).kid_hc1 == "hc1-k1"


@pytest.mark.parametrize("campo", ["kid_hc1", "fuente_revocados", "kids_autoridad", "verificar_hc1", "diario"])
def test_medio3_y_4_omitir_un_campo_obligatorio_no_construye(tmp_path: Path, campo: str) -> None:
    quitar = (campo,)
    conf = mundo().config_hc1(diario=DiarioHC1(tmp_path / "d"))
    for k in quitar:
        del conf[k]
    m = mundo()
    with pytest.raises(TypeError):
        SeguimientoHC1(m.verificador_nodos(), m.reloj, **conf)


def test_medio3_verificar_hc1_no_invocable_no_construye(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        _construir(tmp_path, verificar_hc1=None)
    assert _construir(tmp_path, n=1)  # control


@pytest.mark.parametrize("kid", ["", None, "con espacio", "x" * 65, 7])
def test_medio3_kid_hc1_vacio_o_invalido_no_construye(tmp_path: Path, kid: Any) -> None:
    with pytest.raises(ValueError):
        _construir(tmp_path, kid_hc1=kid)


@pytest.mark.parametrize("fuente", [None, "no invocable", 42])
def test_medio3_fuente_revocados_obligatoria_e_invocable(tmp_path: Path, fuente: Any) -> None:
    with pytest.raises(ValueError):
        _construir(tmp_path, fuente_revocados=fuente)
    assert _construir(tmp_path, n=1, fuente_revocados=SinRevocacion())  # control: declarar «sin revocación» vale
    assert SinRevocacion()() == frozenset()


def test_medio3_kids_autoridad_vacio_exige_declarar_sin_autoridad_humana(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        _construir(tmp_path, kids_autoridad=frozenset(), verificar_autoridad=None)
    with pytest.raises(ValueError):  # la declaración contradice kids configurados
        _construir(tmp_path, n=1, sin_autoridad_humana=True)
    declarado = _construir(
        tmp_path, n=2, kids_autoridad=frozenset(), verificar_autoridad=None, sin_autoridad_humana=True
    )
    assert declarado.sin_autoridad_humana  # control: explícito, sí


def test_medio3_sin_autoridad_humana_resolver_ambigua_rechaza_siempre(tmp_path: Path) -> None:
    esc = Escena(tmp_path, kids_autoridad=frozenset(), sin_autoridad_humana=True)  # conserva verificar_autoridad
    ident, res = esc.ambigua()
    valida = esc.m.autorizacion(ident, res)  # firmada por una clave a la que el verificador SÍ da por buena
    assert _motivo(esc.hc1.resolver_ambigua, ident, valida, res) is Motivo.SIN_AUTORIDAD
    assert _estado(esc.hc1, ident) is Estado.AMBIGUO
    con = Escena(tmp_path / "con")  # control: con autoridad declarada, la misma autorización vale
    id2, res2 = con.ambigua()
    assert con.hc1.resolver_ambigua(id2, con.m.autorizacion(id2, res2), res2)


def test_medio3_politica_nodo_exige_fuente_revocados_explicita() -> None:
    m = mundo()
    base: dict[str, Any] = {
        "id_nodo": NODO, "emisores": {"hc1-k1": "hc1"}, "capacidades": frozenset({"calcular_resumen_sha256"}),
        "reloj": m.reloj, "arranque": 0.0,
    }  # fmt: skip
    with pytest.raises(TypeError):
        PoliticaNodo(**base)
    for malo in (None, "x", 3):
        with pytest.raises(ValueError):
            PoliticaNodo(**base, fuente_revocados=malo)
    assert PoliticaNodo(**base, fuente_revocados=SinRevocacion()).fuente_revocados() == frozenset()  # control


def test_medio4_sin_diario_no_hay_seguimiento(tmp_path: Path) -> None:
    m = mundo()
    conf = m.config_hc1()
    with pytest.raises(TypeError):
        SeguimientoHC1(m.verificador_nodos(), m.reloj, **conf)  # diario omitido
    with pytest.raises(ValueError, match="obligatorio"):
        SeguimientoHC1(m.verificador_nodos(), m.reloj, diario=None, **conf)  # type: ignore[arg-type]
    assert SeguimientoHC1(m.verificador_nodos(), m.reloj, diario=DiarioHC1(tmp_path / "d"), **conf)  # control


def test_medio4_una_construccion_fallida_no_retiene_la_instancia_unica(tmp_path: Path) -> None:
    diario = DiarioHC1(tmp_path / "d0")  # referencia propia: la prueba no depende de cuándo se recolecte la basura
    with pytest.raises(ValueError):
        _construir(tmp_path, kid_hc1="", diario=diario)
    assert not diario.abierto  # la construcción fallida lo cerró: no queda una instancia a medias reteniendo el cerrojo
    assert DiarioHC1(tmp_path / "d0").abierto  # y se puede reintentar con la configuración buena


# =====================================================================================================================
# MEDIO-5 — al releer el diario: se recalcula la validación, se verifica la firma de HC-1 y no hay tiempos no finitos
# =====================================================================================================================


def _verificacion_fallida(esc: Escena) -> str:
    """Un resultado FIRMADO por el nodo cuya salida es incorrecta: el verificador propio de la capacidad lo rechaza."""
    sobre, ident = esc.emitir(tarea="t-mal")
    ac = esc.nodo.aceptar(sobre)
    mal = esc.m.nodo.firmar(DOMINIO_RESULTADO, payload_resultado(ac.orden, NODO, "0" * 64))
    esc.hc1.recibir_acuse(ac.acuse, NODO)
    esc.hc1.recibir_resultado(mal, NODO)
    assert esc.hc1.validar(ident) is False
    return ident


def test_medio5_la_validacion_se_restaura_recalculandola_no_leyendo_el_ok_del_diario(tmp_path: Path) -> None:
    esc = Escena(tmp_path)
    bueno = esc.hasta_validado(tarea="t-ok")
    malo = _verificacion_fallida(esc)
    nuevo = esc.reiniciar_hc1()  # control: el diario íntegro se recupera y la validación se restaura
    assert nuevo.ejecucion(bueno).validacion is True and nuevo.ejecucion(bueno).estado is Estado.VALIDADO  # type: ignore[union-attr]
    assert nuevo.ejecucion(malo).validacion is False and nuevo.ejecucion(malo).estado is Estado.VERIFICACION_FALLIDA  # type: ignore[union-attr]

    def mentir(rs: list[dict[str, Any]]) -> list[dict[str, Any]]:
        for r in rs:
            if r["ev"] == "validacion" and r["id"] == malo:
                r["ok"] = True  # el diario dice «validado» de un resultado que NO verifica
        return rs

    _reescribir(tmp_path, mentir)
    _reinicio_falla(esc)


def test_medio5_un_ok_falso_en_el_diario_de_un_resultado_valido_tambien_falla_cerrado(tmp_path: Path) -> None:
    esc = Escena(tmp_path)
    ident = esc.hasta_validado()

    def negar(rs: list[dict[str, Any]]) -> list[dict[str, Any]]:
        for r in rs:
            if r["ev"] == "validacion" and r["id"] == ident:
                r["ok"] = False
        return rs

    _reescribir(tmp_path, negar)
    _reinicio_falla(esc)


def test_medio5_la_emision_del_diario_debe_estar_firmada_por_hc1(tmp_path: Path) -> None:
    esc = Escena(tmp_path)
    esc.emitir()
    esc.reiniciar_hc1()  # control

    def intrusa(rs: list[dict[str, Any]]) -> list[dict[str, Any]]:
        falsa = firmante_orden(generar_firmante("hc1-k1"), campos_validos(tarea="t-intrusa"))  # mismo kid, OTRA clave
        for r in rs:
            if r["ev"] == "emision":
                r["sobre"] = base64.b64encode(falsa).decode()
        return rs

    _reescribir(tmp_path, intrusa)
    _reinicio_falla(esc)


def test_medio5_registrar_emision_solo_acepta_ordenes_firmadas_por_el_kid_de_hc1(tmp_path: Path) -> None:
    esc = Escena(tmp_path)
    intrusa = firmante_orden(generar_firmante("hc1-k1"), campos_validos(tarea="t-x"))
    assert _motivo(esc.hc1.registrar_emision, intrusa, 60) is Motivo.FIRMA_INVALIDA
    assert esc.hc1._por_id == {}
    esc2 = Escena(tmp_path / "dos")
    otro = generar_firmante("hc1-k2")  # firma BUENA y conocida del verificador, pero no es el kid de HC-1
    esc2.reiniciar_hc1(verificar_hc1=verificador_de({"hc1-k1": esc2.m.hc1.publica(), "hc1-k2": otro.publica()}))
    de_otro = firmante_orden(otro, campos_validos(tarea="t-y", kid="hc1-k2"))
    assert _motivo(esc2.hc1.registrar_emision, de_otro, 60) is Motivo.KID_DESCONOCIDO
    assert esc2.hc1.registrar_emision(firmante_orden(esc2.m.hc1, campos_validos(tarea="t-z")), 60)  # control


@pytest.mark.parametrize("valor", [float("inf"), float("nan"), float("-inf"), 1e999])
@pytest.mark.parametrize("donde", ["vence_en", "recibida_en"])
def test_medio5_un_tiempo_no_finito_en_el_diario_es_diario_manipulado(tmp_path: Path, donde: str, valor: float) -> None:
    esc = Escena(tmp_path)
    sobre, _ = esc.emitir()
    ac = esc.nodo.aceptar(sobre)
    esc.hc1.recibir_acuse(ac.acuse, NODO)
    esc.reiniciar_hc1()  # control: los tiempos finitos se leen

    def romper(rs: list[dict[str, Any]]) -> list[dict[str, Any]]:
        for r in rs:
            if donde in r:
                r[donde] = valor
        return rs

    _reescribir(tmp_path, romper)
    _reinicio_falla(esc)


@pytest.mark.parametrize("techo", [float("inf"), float("nan"), float("-inf"), True, "30"])
def test_medio5_un_techo_no_finito_al_emitir_se_rechaza_y_no_deja_una_ejecucion_sin_vencer_nunca(
    tmp_path: Path, techo: Any
) -> None:
    esc = Escena(tmp_path)
    sobre = firmante_orden(esc.m.hc1, campos_validos())
    assert _motivo(esc.hc1.registrar_emision, sobre, techo) is Motivo.CAMPO_INVALIDO
    assert esc.hc1._por_id == {} and esc.hc1.diario.recuperar()[0] == []
    _, ident = esc.emitir(techo=30)  # control: lo finito se registra y vence
    esc.m.reloj.t += 1000
    esc.hc1.vencer()
    assert _estado(esc.hc1, ident) is Estado.INTERRUMPIDA


def test_medio5_el_kid_del_payload_debe_ser_el_del_sobre(tmp_path: Path) -> None:
    esc = Escena(tmp_path)
    ambiguo = firmante_orden(esc.m.hc1, campos_validos(kid="hc1-k9"))  # firmada por hc1-k1, pero dice ser de hc1-k9
    assert _motivo(esc.hc1.registrar_emision, ambiguo, 60) is Motivo.KID_DESCONOCIDO
    assert esc.hc1.registrar_emision(firmante_orden(esc.m.hc1, campos_validos()), 60)  # control


def test_medio5_la_validacion_en_vivo_queda_registrada(tmp_path: Path) -> None:
    esc = Escena(tmp_path)
    bueno = esc.hasta_validado()
    malo = _verificacion_fallida(esc)
    assert esc.hc1.ejecucion(bueno).validacion is True  # type: ignore[union-attr]
    assert esc.hc1.ejecucion(malo).validacion is False  # type: ignore[union-attr]
    _, ident = esc.emitir(tarea="t-sin-validar")
    assert esc.hc1.ejecucion(ident).validacion is None  # type: ignore[union-attr]


# =====================================================================================================================
# MEDIO-6 — registrar_fallo comparte el tope de escrituras por ventana con los rechazos
# =====================================================================================================================


def test_medio6_los_fallos_inesperados_respetan_el_tope_y_se_declaran_como_suprimidos(tmp_path: Path) -> None:
    reloj = Reloj(1000.0)
    fm, log = _firmador(tmp_path, reloj, tasa_max=1000, tasa_ventana_s=10.0, rechazos_log_max=3)
    for _ in range(10):
        fm.registrar_fallo("peticion_ilegible", 1000)
    entradas = [json.loads(x) for x in log.read_text().splitlines()]
    assert [e["tipo"] for e in entradas] == ["fallo"] * 3  # el log NO se infla con fallos provocados
    assert fm.rechazos_suprimidos == 7
    reloj.t = 1011.0  # nueva ventana: la siguiente entrada escrita declara lo suprimido
    fm.registrar_fallo("error_interno", 1000)
    ultimo = json.loads(log.read_text().splitlines()[-1])
    assert ultimo["tipo"] == "fallo" and ultimo["suprimidos"] == 7 and fm.rechazos_suprimidos == 0
    assert "suprimidos" not in json.loads(log.read_text().splitlines()[0])


def test_medio6_fallos_y_rechazos_comparten_el_mismo_cupo(tmp_path: Path) -> None:
    fm, log = _firmador(tmp_path, Reloj(1000.0), tasa_max=1000, tasa_ventana_s=10.0, rechazos_log_max=2)
    with pytest.raises(RechazoOrden):
        fm.firmar({**PET, "capacidad": "ejecutar_comando"})  # 1 de 2
    fm.registrar_fallo("error_interno")  # 2 de 2
    fm.registrar_fallo("error_interno")  # suprimido
    with pytest.raises(RechazoOrden):
        fm.firmar({**PET, "capacidad": "ejecutar_comando"})  # suprimido también
    assert [json.loads(x)["tipo"] for x in log.read_text().splitlines()] == ["rechazo", "fallo"]
    assert fm.rechazos_suprimidos == 2
    assert fm.firmar(PET)  # control: una firma legítima nunca se suprime


def test_medio6_un_fallo_bajo_el_tope_se_escribe_con_su_causa(tmp_path: Path) -> None:
    fm, log = _firmador(tmp_path, Reloj(1000.0))
    fm.registrar_fallo("peticion_ilegible", 1234)
    e = json.loads(log.read_text().splitlines()[0])
    assert e["causa"] == "peticion_ilegible" and e["uid_par"] == 1234 and "suprimidos" not in e


# =====================================================================================================================
# BAJO 1 — la lista de revocados no se abre bloqueando en un FIFO
# =====================================================================================================================


def test_bajo1_una_lista_que_es_un_fifo_se_rechaza_sin_bloquearse(tmp_path: Path) -> None:
    lista, ruta, _ = _lista(tmp_path)
    os.mkfifo(ruta, 0o600)
    salida: list[object] = []
    hilo = threading.Thread(target=lambda: salida.append(_motivo(lista)), daemon=True)
    hilo.start()
    hilo.join(3)
    assert not hilo.is_alive(), "ListaRevocados se quedó bloqueada abriendo un FIFO"
    assert salida == [Motivo.REVOCACION_ILEGIBLE]
    os.unlink(ruta)
    _revocar(ruta, "k")
    assert lista() == {"k"}  # control: un fichero regular se lee con normalidad


# =====================================================================================================================
# BAJO 2 — el ancla de revocados también la crea revocar() y detecta el vaciado/truncado
# =====================================================================================================================


def test_bajo2_revocar_crea_el_ancla_sin_necesidad_de_haber_leido_antes(tmp_path: Path) -> None:
    lista, ruta, ancla = _lista(tmp_path)
    assert not ancla.exists()
    _revocar(ruta, "k")
    assert ancla.exists() and stat.S_IMODE(os.stat(ancla).st_mode) == 0o600
    os.unlink(ruta)  # nadie llegó a LEER la lista, pero revocar ya dejó el ancla
    assert _motivo(lista) is Motivo.REVOCACION_ILEGIBLE


@pytest.mark.parametrize("dano", ["vaciada", "truncada", "reescrita_mismo_tamano", "prefijo_cambiado"])
def test_bajo2_una_lista_vaciada_truncada_o_reescrita_tras_anclar_es_fallo_cerrado(tmp_path: Path, dano: str) -> None:
    lista, ruta, _ = _lista(tmp_path)
    _revocar(ruta, "kid-a")
    _revocar(ruta, "kid-b")
    assert lista() == {"kid-a", "kid-b"}  # control
    original = ruta.read_bytes()
    if dano == "vaciada":
        ruta.write_bytes(b"")
    elif dano == "truncada":
        ruta.write_bytes(original.splitlines(keepends=True)[0])  # válida por sí sola, pero MÁS CORTA que lo anclado
    elif dano == "reescrita_mismo_tamano":
        ruta.write_bytes(original.replace(b"kid-a", b"kid-z"))
    else:
        ruta.write_bytes(b'{"kid":"kid-q"}\n' + original[len(b'{"kid":"kid-a"}\n') :] + b'{"kid":"kid-c"}\n')
    assert _motivo(lista) is Motivo.REVOCACION_ILEGIBLE
    ruta.write_bytes(original)
    assert lista() == {"kid-a", "kid-b"}  # control: restaurada, vuelve a leerse


def test_bajo2_la_primera_lectura_ancla_una_lista_creada_sin_revocar(tmp_path: Path) -> None:
    lista, ruta, ancla = _lista(tmp_path)
    ruta.write_bytes(b'{"kid":"kid-a"}\n')  # creada a mano: nadie llamó a revocar()
    os.chmod(ruta, 0o600)
    assert not ancla.exists()
    assert lista() == {"kid-a"} and ancla.exists()  # la lectura deja el ancla
    ruta.write_bytes(b"")
    assert _motivo(lista) is Motivo.REVOCACION_ILEGIBLE  # y vaciarla después se detecta


def test_bajo2_la_lista_puede_crecer_y_el_ancla_la_sigue(tmp_path: Path) -> None:
    lista, ruta, ancla = _lista(tmp_path)
    _revocar(ruta, "kid-a")
    assert lista() == {"kid-a"}
    _revocar(ruta, "kid-b")
    assert lista() == {"kid-a", "kid-b"}
    lineas = [json.loads(x) for x in ancla.read_text().splitlines()]
    assert [x["tam"] for x in lineas] == sorted(x["tam"] for x in lineas) and len(lineas) == 2  # monótono, sin repetir
    lista()
    assert len(ancla.read_text().splitlines()) == 2  # leer sin cambios no engorda el ancla


def test_bajo2_una_lista_vacia_anclada_puede_crecer_despues(tmp_path: Path) -> None:
    lista, ruta, _ = _lista(tmp_path)
    ruta.write_bytes(b"")
    os.chmod(ruta, 0o600)
    assert lista() == frozenset()
    _revocar(ruta, "kid-a")
    assert lista() == {"kid-a"}


@pytest.mark.parametrize("dano", ["escribible", "basura", "enlace", "contradictoria", "truncada"])
def test_bajo2_un_ancla_danada_es_fallo_cerrado(tmp_path: Path, dano: str) -> None:
    lista, ruta, ancla = _lista(tmp_path)
    _revocar(ruta, "kid-a")
    assert lista() == {"kid-a"}  # control
    contenido = ancla.read_bytes()
    if dano == "escribible":
        os.chmod(ancla, 0o666)
    elif dano == "basura":
        ancla.write_bytes(b"revocados\n")
    elif dano == "enlace":
        otro = tmp_path / "estado" / "otra"
        otro.write_bytes(contenido)
        os.chmod(otro, 0o600)
        ancla.unlink()
        ancla.symlink_to(otro)
    elif dano == "contradictoria":
        linea = json.loads(contenido.splitlines()[0])
        ancla.write_bytes(contenido + (json.dumps({**linea, "sha256": "0" * 64}) + "\n").encode())
    else:
        ancla.write_bytes(contenido.rstrip(b"\n"))
    assert _motivo(lista) is Motivo.REVOCACION_ILEGIBLE


def test_bajo2_revocar_con_una_lista_alterada_falla_en_vez_de_anclar_lo_alterado(tmp_path: Path) -> None:
    lista, ruta, ancla = _lista(tmp_path)
    _revocar(ruta, "kid-a")
    _revocar(ruta, "kid-b")
    ruta.write_bytes(b"")  # alguien la vacía
    from aura_skeleton.adapters.firma_delegacion import ErrorClave

    with pytest.raises(ErrorClave):
        revocar(ruta, "kid-c", ancla)
    assert _motivo(lista) is Motivo.REVOCACION_ILEGIBLE


# =====================================================================================================================
# BAJO 3 — rotación de kids de autoridad: los retirados solo sirven para releer el historial
# =====================================================================================================================


def _autoridad_rotada() -> tuple[Any, Any, Any]:
    nueva = generar_firmante("autoridad-k2")
    return nueva, "autoridad-k2", nueva.publica()


def test_bajo3_retirar_un_kid_de_autoridad_no_impide_arrancar_sobre_su_historial(tmp_path: Path) -> None:
    esc = Escena(tmp_path)
    ident, res = esc.ambigua()
    esc.hc1.resolver_ambigua(ident, esc.m.autorizacion(ident, res), res)
    nueva, kid2, pub2 = _autoridad_rotada()
    verificador = verificador_de({KID_AUTORIDAD: esc.m.autoridad.publica(), kid2: pub2})
    rotado = {
        "kids_autoridad": frozenset({kid2}),
        "kids_autoridad_retirados": frozenset({KID_AUTORIDAD}),
        "verificar_autoridad": verificador,
    }
    nuevo = esc.reiniciar_hc1(**rotado)
    ej = nuevo.ejecucion(ident)
    assert ej is not None and ej.estado is Estado.RESULTADO_FIRMADO and ej.resuelta_por == KID_AUTORIDAD
    # control: SIN declarar el retirado, ese historial no se puede releer (la rotación sin lista rompe el arranque)
    sin_declarar = {"kids_autoridad": frozenset({kid2}), "verificar_autoridad": verificador}
    assert _motivo(esc.reiniciar_hc1, **sin_declarar) is Motivo.DIARIO_ILEGIBLE


def test_bajo3_un_kid_retirado_nunca_resuelve_nada_nuevo(tmp_path: Path) -> None:
    esc = Escena(tmp_path)
    nueva, kid2, pub2 = _autoridad_rotada()
    verificador = verificador_de({KID_AUTORIDAD: esc.m.autoridad.publica(), kid2: pub2})
    esc.reiniciar_hc1(
        kids_autoridad=frozenset({kid2}), kids_autoridad_retirados=frozenset({KID_AUTORIDAD}),
        verificar_autoridad=verificador,
    )  # fmt: skip
    ident, res = esc.ambigua()
    assert _motivo(esc.hc1.resolver_ambigua, ident, esc.m.autorizacion(ident, res), res) is Motivo.SIN_AUTORIDAD
    assert _estado(esc.hc1, ident) is Estado.AMBIGUO
    ok = esc.hc1.resolver_ambigua(ident, esc.m.autorizacion(ident, res, firmante=nueva), res)  # control: el vigente sí
    assert ok.resuelta_por == kid2


def test_bajo3_sin_autoridad_humana_y_retirados_relee_pero_no_resuelve(tmp_path: Path) -> None:
    esc = Escena(tmp_path)
    ident, res = esc.ambigua()
    esc.hc1.resolver_ambigua(ident, esc.m.autorizacion(ident, res), res)
    nuevo = esc.reiniciar_hc1(
        kids_autoridad=frozenset(), sin_autoridad_humana=True, kids_autoridad_retirados=frozenset({KID_AUTORIDAD})
    )
    assert nuevo.ejecucion(ident).resuelta_por == KID_AUTORIDAD  # type: ignore[union-attr]
    id2, res2 = esc.ambigua("t-2")
    assert _motivo(nuevo.resolver_ambigua, id2, esc.m.autorizacion(id2, res2), res2) is Motivo.SIN_AUTORIDAD


def test_bajo3_un_kid_no_puede_estar_vigente_y_retirado_ni_ser_el_de_hc1_o_un_nodo(tmp_path: Path) -> None:
    for n, retirados in enumerate((frozenset({KID_AUTORIDAD}), frozenset({"hc1-k1"}), frozenset({NODO}))):
        with pytest.raises(ValueError):
            _construir(tmp_path, n=n, kids_autoridad_retirados=retirados)
    assert _construir(tmp_path, n=9, kids_autoridad_retirados=frozenset({"autoridad-vieja"}))  # control


# =====================================================================================================================
# BAJO 4 — `rechazos` en memoria es un anillo con contador
# =====================================================================================================================


def test_bajo4_los_rechazos_en_memoria_tienen_tope_y_el_total_se_cuenta(tmp_path: Path) -> None:
    esc = Escena(tmp_path)
    for _ in range(RECHAZOS_MEMORIA_MAX + 50):
        assert _motivo(esc.hc1.recibir_resultado, b"basura", NODO) is Motivo.SOBRE_MALFORMADO
    assert len(esc.hc1.rechazos) == RECHAZOS_MEMORIA_MAX
    assert esc.hc1.rechazos_total == RECHAZOS_MEMORIA_MAX + 50


def test_bajo4_el_anillo_conserva_los_ultimos_y_no_pierde_nada_bajo_el_tope(tmp_path: Path) -> None:
    esc = Escena(tmp_path)
    _motivo(esc.hc1.recibir_resultado, b"basura", NODO)  # SOBRE_MALFORMADO
    assert esc.hc1.rechazos == [Motivo.SOBRE_MALFORMADO] and esc.hc1.rechazos_total == 1  # control
    for _ in range(RECHAZOS_MEMORIA_MAX):
        _motivo(esc.hc1.recibir_resultado, b"basura", NODO)
    sobre, _ = esc.emitir()
    ac = esc.nodo.aceptar(sobre)
    esc.hc1.recibir_acuse(ac.acuse, NODO)
    _motivo(esc.hc1.recibir_acuse, ac.acuse, NODO)  # ACUSE_DUPLICADO: el ÚLTIMO motivo es el que queda al final
    assert esc.hc1.rechazos[-1] is Motivo.ACUSE_DUPLICADO and len(esc.hc1.rechazos) == RECHAZOS_MEMORIA_MAX


# =====================================================================================================================
# BAJO 5 — la autorización de resolución se liga al hash del resultado firmado concreto
# =====================================================================================================================


def _ambigua_con_dos_resultados(esc: Escena) -> tuple[str, bytes, bytes]:
    ahora = esc.m.reloj.t
    sobre, ident = esc.emitir(techo=30, emitida_en=ahora, caduca_en=ahora + 60)
    ac = esc.nodo.aceptar(sobre)
    res_a = esc.nodo.ejecutar(ac.orden)
    res_b = esc.m.nodo.firmar(DOMINIO_RESULTADO, payload_resultado(ac.orden, NODO, "0" * 64))  # válido y vinculado
    esc.hc1.recibir_acuse(ac.acuse, NODO)
    esc.m.reloj.t += 100
    esc.hc1.vencer()
    assert _estado(esc.hc1, ident) is Estado.AMBIGUO and res_a != res_b
    return ident, res_a, res_b


def test_bajo5_la_autorizacion_solo_vale_para_el_resultado_cuyo_hash_firma(tmp_path: Path) -> None:
    esc = Escena(tmp_path)
    ident, res_a, res_b = _ambigua_con_dos_resultados(esc)
    aut_a = esc.m.autorizacion(ident, res_a)
    assert _motivo(esc.hc1.resolver_ambigua, ident, aut_a, res_b) is Motivo.HASH_NO_CORRESPONDE
    assert _estado(esc.hc1, ident) is Estado.AMBIGUO and esc.hc1._nonces == set()  # no se gastó el nonce
    assert esc.hc1.resolver_ambigua(ident, aut_a, res_a).sobre_resultado == res_a  # control: el autorizado sí


def test_bajo5_el_hash_es_un_campo_firmado_obligatorio(tmp_path: Path) -> None:
    from aura_skeleton.core.delegacion import DOMINIO_RESOLUCION, bytes_canonicos, payload_resolucion

    esc = Escena(tmp_path)
    ident, res = esc.ambigua()
    ahora = esc.m.reloj.t
    sin_hash = {"v": 1, "alg": "ed25519", "id_ejecucion": ident, "decision": "admitir", "motivo": "m",
                "emitida_en": ahora, "caduca_en": ahora + 60, "nonce": "eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee"}  # fmt: skip
    firmada = esc.m.autoridad.firmar(DOMINIO_RESOLUCION, bytes_canonicos(sin_hash))
    assert _motivo(esc.hc1.resolver_ambigua, ident, firmada, res) is Motivo.CAMPOS_FALTANTES
    with pytest.raises(RechazoOrden) as e:  # un hash que no es sha256 hex se rechaza al construir la autorización
        payload_resolucion(ident, "no-es-un-hash", "m", ahora, ahora + 60, "eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee")
    assert e.value.motivo is Motivo.CAMPO_INVALIDO


def test_bajo5_al_releer_el_diario_la_resolucion_debe_corresponder_al_resultado_autorizado(tmp_path: Path) -> None:
    esc = Escena(tmp_path)
    ident, res_a, res_b = _ambigua_con_dos_resultados(esc)
    esc.hc1.resolver_ambigua(ident, esc.m.autorizacion(ident, res_a), res_a)
    esc.reiniciar_hc1()  # control: el diario íntegro se recupera

    def cambiar_resultado(rs: list[dict[str, Any]]) -> list[dict[str, Any]]:
        for r in rs:
            if r["ev"] == "resolucion":
                r["sobre"] = base64.b64encode(res_b).decode()  # otro resultado válido, no el autorizado
        return rs

    _reescribir(tmp_path, cambiar_resultado)
    _reinicio_falla(esc)


# =====================================================================================================================
# BAJO 6 — una interrupción no-Exception tras iniciar el efecto deja la ejecución AMBIGUA, no FALLIDA
# =====================================================================================================================


def _nodo_con_capacidad_que(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, lanza: BaseException) -> Any:
    def ejecutar(_: Any) -> str:
        raise lanza

    cap = Capacidad("calcular_resumen_sha256", lambda a: dict(a), ejecutar, lambda a, s: True, idempotente=True)
    monkeypatch.setattr(delegacion_nodo, "CAPACIDADES", {"calcular_resumen_sha256": cap})
    m = mundo()
    almacen = AlmacenConsumidas(tmp_path / "nodo")
    nodo = NodoDelegado(m.politica(), m.verificador_hc1(), almacen, m.nodo.firmar)
    campos = campos_validos()
    ac = nodo.aceptar(firmante_orden(m.hc1, campos))
    return nodo, ac, almacen, campos["id_ejecucion"], tmp_path / "nodo"


@pytest.mark.parametrize("interrupcion", [KeyboardInterrupt(), SystemExit(3)])
def test_bajo6_una_interrupcion_no_exception_deja_la_ejecucion_ambigua_y_nunca_se_reejecuta(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, interrupcion: BaseException
) -> None:
    nodo, ac, almacen, ident, directorio = _nodo_con_capacidad_que(monkeypatch, tmp_path, interrupcion)
    with pytest.raises(type(interrupcion)):
        nodo.ejecutar(ac.orden)
    assert nodo.estado(ident) is EstadoNodo.AMBIGUA  # NO fallida: el efecto pudo ocurrir
    assert _motivo(nodo.ejecutar, ac.orden) is Motivo.EJECUCION_AMBIGUA
    assert AlmacenConsumidas(directorio).estado(ident) is EstadoNodo.AMBIGUA  # y tras un reinicio, igual
    assert nodo.reenviar_resultado(ident) is None


def test_bajo6_control_una_excepcion_ordinaria_sigue_siendo_fallida(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    nodo, ac, _, ident, _ = _nodo_con_capacidad_que(monkeypatch, tmp_path, RuntimeError("falla de la capacidad"))
    with pytest.raises(RuntimeError):
        nodo.ejecutar(ac.orden)
    assert nodo.estado(ident) is EstadoNodo.FALLIDA
    assert _motivo(nodo.ejecutar, ac.orden) is Motivo.EJECUCION_REPETIDA
