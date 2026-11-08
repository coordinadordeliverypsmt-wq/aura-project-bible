"""Reloj de CM2 — integracion: ejecutor (hecho_id + eventos), sonda de solo lectura y flags de CLI.

Resolucion S3 §2.1 (orden del CEO, 2026-10-06). TODO ocurre en `tmp_path`: ninguna prueba toca
`~/.aura` ni `entorno/control-plane/`. La medicion OFICIAL (`--iniciar-cm2` real) NO se ejecuta aqui.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess

import pytest

from aura_skeleton import observability as obs
from aura_skeleton.core.ejecutor_modelo_usuario import EjecutorModeloUsuario
from aura_skeleton.modules.memory import PersistentMemory

UID = "mauricio"
DIA = 86400.0
T0 = 1_700_000_000.0


@pytest.fixture(autouse=True)
def _audit_limpio():
    obs.reset_audit()
    yield
    obs.reset_audit()


@pytest.fixture(autouse=True)
def _aislar_datos_reales(tmp_path, monkeypatch):
    """Ninguna prueba de este fichero puede tocar el AURA_DATOS real (ni iniciar el reloj oficial)."""
    monkeypatch.setenv("AURA_DATOS", str(tmp_path / "aislado"))
    monkeypatch.setenv("HOME", str(tmp_path / "home"))


@pytest.fixture
def datos(tmp_path):
    d = tmp_path / "datos"
    d.mkdir()
    (d / "memoria.json").write_text("")  # un AURA_DATOS «en uso»: `iniciar` rechaza un directorio vacio
    return str(d)


def _audit(datos: str) -> str:
    return os.path.join(datos, "audit.jsonl")


def _memoria(datos: str) -> PersistentMemory:
    return PersistentMemory(os.path.join(datos, "memoria.json"))


def _eventos(datos: str, nombre: str | None = None) -> list[dict]:
    todos = [r for r in obs.leer_audit_desde(_audit(datos), -1) if str(r.get("evento", "")).startswith("cm2.")]
    return [r for r in todos if nombre is None or r["evento"] == nombre]


async def _declarar(ej, uid: str, texto: str, ts: float, clase: str = "hecho_declarado", trace: str = "t") -> None:
    await ej.execute(
        "registrar_informacion_usuario",
        {
            "user_id": uid,
            "contenido": texto,
            "tipo": "semantica",
            "procedencia": {"trace_id": trace, "fuente": "usuario", "clase": clase, "origen": "declarada", "ts": ts},
        },
        trace,
        "ev",
    )


def _hecho_ids(mem, uid: str, texto: str | None = None) -> list[str | None]:
    return [
        i["provenance"].get("hecho_id")
        for i in mem._items
        if i["user_id"] == uid and i["kind"] == "semantica" and (texto is None or i["content"] == texto)
    ]


@pytest.fixture
def ej(datos):
    obs.configure_audit(_audit(datos))
    return EjecutorModeloUsuario(_memoria(datos))


# ============================================================ hecho_id ==


async def test_hecho_id_es_opaco_y_distinto_entre_usuarios_con_el_mismo_texto(ej, datos):
    texto = "mi color favorito es azul"
    await _declarar(ej, "ana", texto, T0)
    await _declarar(ej, "luis", texto, T0)
    mem = ej._memoria
    (a,), (b,) = _hecho_ids(mem, "ana"), _hecho_ids(mem, "luis")
    assert a and b and a != b
    assert len(a) == 32 and int(a, 16) >= 0
    # No se deriva del contenido: ningun digest habitual del texto (ni de usuario+texto) coincide.
    for cand in (texto, f"ana{texto}", f"ana:{texto}", f"ana|{texto}"):
        for h in (hashlib.md5, hashlib.sha1, hashlib.sha256):  # noqa: S324
            assert a != h(cand.encode()).hexdigest()[:32]


async def test_hecho_id_se_hereda_entre_versiones_incluidas_cerradas_y_refutadas(ej):
    mem = ej._memoria
    await _declarar(ej, UID, "mi coche es rojo", T0)
    await _declarar(ej, UID, "mi coche es azul", T0 + DIA)
    # refutar la v2 y volver a declarar: la identidad sigue siendo la misma
    await ej.execute("refutar_informacion_usuario", {"user_id": UID, "contiene": "azul"}, "t", "ev")
    await _declarar(ej, UID, "mi coche es verde", T0 + 2 * DIA)
    ids = _hecho_ids(mem, UID)
    assert len(ids) == 3 and len(set(ids)) == 1 and ids[0]


async def test_hecho_id_estable_tras_reiniciar_la_memoria_desde_disco(ej, datos):
    await _declarar(ej, UID, "mi coche es rojo", T0)
    primero = _hecho_ids(ej._memoria, UID)[0]
    assert primero
    reabierta = _memoria(datos)  # lee el fichero de nuevo: simula reinicio
    assert _hecho_ids(reabierta, UID) == [primero]
    await _declarar(EjecutorModeloUsuario(reabierta), UID, "mi coche es azul", T0 + DIA)
    assert set(_hecho_ids(reabierta, UID)) == {primero}


async def test_hecho_id_distinto_por_atributo(ej):
    await _declarar(ej, UID, "mi coche es rojo", T0)
    await _declarar(ej, UID, "me llamo Mauricio", T0)
    a, b = _hecho_ids(ej._memoria, UID)
    assert a and b and a != b


async def test_sin_identidad_o_sin_clase_hecho_declarado_no_hay_hecho_id_ni_evento(ej, datos):
    await _declarar(ej, UID, "trabajo en Lenovo", T0)  # HECHO_DECLARADO pero sin atributo tipado
    await _declarar(ej, UID, "mi coche es rojo", T0, clase="preferencia_declarada")  # tiene identidad, otra clase
    assert _hecho_ids(ej._memoria, UID) == [None, None]
    assert _eventos(datos) == []


async def test_los_cuatro_campos_de_vigencia_no_cambian_y_hecho_id_es_aparte(ej):
    await _declarar(ej, UID, "mi coche es rojo", T0)
    await _declarar(ej, UID, "mi coche es azul", T0 + DIA)
    v1, v2 = [i["provenance"] for i in ej._memoria._items]
    assert v1["valid_until"] == T0 + DIA and v1["version"] == 1 and v1["supersedes"] is None
    assert v2["version"] == 2 and v2["supersedes"] == 1 and v2["valid_from"] == T0 + DIA and v2["valid_until"] is None
    assert v1["hecho_id"] == v2["hecho_id"]


# ============================================================= eventos ==


async def test_hecho_registrado_lleva_hecho_id_version_y_valid_from(ej, datos):
    await _declarar(ej, UID, "mi coche es rojo", T0)
    await _declarar(ej, UID, "mi coche es azul", T0 + DIA)
    evs = _eventos(datos, "cm2.hecho_registrado")
    hid = _hecho_ids(ej._memoria, UID)[0]
    assert [(e["hecho_id"], e["version"], e["valid_from"]) for e in evs] == [(hid, 1, T0), (hid, 2, T0 + DIA)]
    assert all(e["msg"] == "hecho registrado" and e["module"] == "reloj-cm2" and e["level"] == "CM2" for e in evs)


async def test_los_eventos_cm2_no_contienen_el_texto_declarado(ej, datos):
    secreto = "zafiro-secreto"
    await _declarar(ej, UID, f"mi coche es {secreto}", T0)
    await _declarar(ej, UID, f"mi coche es {secreto}2", T0 + DIA)
    await ej.execute("refutar_informacion_usuario", {"user_id": UID, "contiene": secreto + "2"}, "t", "ev")
    await ej.execute("olvidar_informacion_usuario", {"user_id": UID, "contiene": "mi coche"}, "t", "ev")
    evs = _eventos(datos)
    assert {e["evento"] for e in evs} == {"cm2.hecho_registrado", "cm2.hecho_retirado"}
    volcado = json.dumps(evs, ensure_ascii=False)
    for pieza in (secreto, "coche", "mi coche"):
        assert pieza not in volcado


async def test_olvido_emite_hecho_retirado_con_causa_olvido(ej, datos):
    await _declarar(ej, UID, "mi coche es rojo", T0)
    hid = _hecho_ids(ej._memoria, UID)[0]
    await ej.execute("olvidar_informacion_usuario", {"user_id": UID, "contiene": None}, "t", "ev")
    (e,) = _eventos(datos, "cm2.hecho_retirado")
    assert (e["hecho_id"], e["causa"]) == (hid, "olvido")


async def test_refutacion_emite_hecho_retirado_con_causa_refutacion_y_solo_si_marco(ej, datos):
    await _declarar(ej, UID, "mi coche es rojo", T0)
    hid = _hecho_ids(ej._memoria, UID)[0]
    await ej.execute("refutar_informacion_usuario", {"user_id": UID, "contiene": "rojo"}, "t", "ev")
    # refutar lo ya refutado no marca nada y por tanto no emite un segundo evento
    await ej.execute("refutar_informacion_usuario", {"user_id": UID, "contiene": "rojo"}, "t", "ev")
    (e,) = _eventos(datos, "cm2.hecho_retirado")
    assert (e["hecho_id"], e["causa"]) == (hid, "refutacion")


async def test_olvidar_entradas_sin_hecho_id_no_emite_retirada(ej, datos):
    await _declarar(ej, UID, "trabajo en Lenovo", T0)
    await ej.execute("olvidar_informacion_usuario", {"user_id": UID, "contiene": None}, "t", "ev")
    assert _eventos(datos) == []


# ================================================= sonda: solo lectura ==


def _sha(ruta: str) -> str:
    with open(ruta, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def _iniciar(datos: str, ts: float = T0) -> None:
    """Inicia el reloj en un AURA_DATOS de tmp con el `ts` del evento fijado (por defecto T0 = el `valid_from`
    de los hechos de las pruebas): el calendario cuenta desde max(valid_from, inicio)."""
    from unittest.mock import patch

    from aura_skeleton.core import reloj_cm2

    with patch.object(obs.time, "time", return_value=ts):
        reloj_cm2.iniciar(datos, confirmo=True)


async def _tres_hechos(ej) -> None:
    await _declarar(ej, UID, "mi coche es rojo", T0)
    await _declarar(ej, UID, "me llamo Mauricio", T0)
    await _declarar(ej, UID, "mi color favorito es azul", T0)


async def test_sin_evento_de_inicio_medir_no_emite_sondas_e_informa_no_iniciado(ej, datos):
    from aura_skeleton.core import reloj_cm2

    await _tres_hechos(ej)
    antes = _sha(_audit(datos))
    texto = reloj_cm2.medir(datos, ahora=T0 + 40 * DIA)
    assert "NO iniciado" in texto and "3" in texto
    assert _eventos(datos, "cm2.sonda") == []
    assert _sha(_audit(datos)) == antes  # ni siquiera escribe en el audit


async def test_con_evento_de_inicio_emite_sondas_vigentes_y_es_idempotente(ej, datos):
    from aura_skeleton.core import reloj_cm2

    await _tres_hechos(ej)
    _iniciar(datos)
    texto = reloj_cm2.medir(datos, ahora=T0 + 29 * DIA)
    sondas = _eventos(datos, "cm2.sonda")
    assert len(sondas) == 9  # 3 hechos x (7, 14, 28)
    assert {s["resultado"] for s in sondas} == {"vigente"}
    assert {s["dia"] for s in sondas} == {7, 14, 28}
    assert all(s["estado_retirada"] == "ninguna" and s["n_entradas_memoria"] >= 3 for s in sondas)
    assert "sin datos suficientes" in texto
    reloj_cm2.medir(datos, ahora=T0 + 29 * DIA)
    assert len(_eventos(datos, "cm2.sonda")) == 9
    reloj_cm2.medir(datos, ahora=T0 + 60 * DIA)
    assert len(_eventos(datos, "cm2.sonda")) == 9


async def test_la_sonda_no_escribe_la_memoria_ni_con_kill_switch_armado(ej, datos):
    from aura_skeleton.core import reloj_cm2

    await _tres_hechos(ej)
    _iniciar(datos)
    with open(os.path.join(datos, "KILL"), "w", encoding="utf-8") as f:
        f.write("armado")
    antes = _sha(os.path.join(datos, "memoria.json"))
    reloj_cm2.medir(datos, ahora=T0 + 29 * DIA)
    assert _sha(os.path.join(datos, "memoria.json")) == antes
    assert len(_eventos(datos, "cm2.sonda")) == 9  # sigue leyendo y auditando
    assert not os.path.exists(os.path.join(datos, "memoria.json.tmp"))


async def test_la_sonda_no_llama_al_llm(ej, datos, monkeypatch):
    from aura_skeleton.core import reloj_cm2
    from aura_skeleton.core.orchestrator import Orchestrator
    from aura_skeleton.modules.router import ModelRouter

    await _tres_hechos(ej)
    _iniciar(datos)

    def _prohibido(*_a, **_k):
        raise AssertionError("la sonda no puede instanciar el orquestador ni consultar un modelo")

    monkeypatch.setattr(Orchestrator, "__init__", _prohibido)
    monkeypatch.setattr(ModelRouter, "route", _prohibido, raising=False)
    reloj_cm2.medir(datos, ahora=T0 + 29 * DIA)
    assert len(_eventos(datos, "cm2.sonda")) == 9


async def test_perdida_no_pedida_cuenta_como_no_recuperada_y_la_retirada_del_usuario_se_excluye(ej, datos):
    from aura_skeleton.core import reloj_cm2

    await _declarar(ej, UID, "mi coche es rojo", T0)
    await _declarar(ej, UID, "me llamo Mauricio", T0)
    _iniciar(datos)
    # (a) desaparece SIN evento: se quita de la memoria directamente (no es una peticion del usuario)
    ej._memoria.olvidar(lambda i: i["content"] == "mi coche es rojo")
    # (b) el usuario olvida por el camino normal: hay evento
    await ej.execute("olvidar_informacion_usuario", {"user_id": UID, "contiene": "me llamo"}, "t", "ev")
    reloj_cm2.medir(datos, ahora=T0 + 29 * DIA)
    d28 = [s for s in _eventos(datos, "cm2.sonda") if s["dia"] == 28]
    por_estado = sorted((s["estado_retirada"], s["resultado"]) for s in d28)
    assert por_estado == [("ninguna", "sin_consulta"), ("olvido", "sin_consulta")]
    eventos = obs.leer_audit_desde(_audit(datos), -1)
    t = reloj_cm2.tasa_dia28(eventos, minimo=1)
    assert (t.valor, t.denominador, t.excluidos) == (0.0, 1, 1)


async def test_valor_refutado_ya_no_se_recupera_como_vigente(ej, datos):
    from aura_skeleton.core import reloj_cm2

    await _declarar(ej, UID, "mi coche es rojo", T0)
    _iniciar(datos)
    await ej.execute("refutar_informacion_usuario", {"user_id": UID, "contiene": "rojo"}, "t", "ev")
    reloj_cm2.medir(datos, ahora=T0 + 8 * DIA)
    (s,) = _eventos(datos, "cm2.sonda")
    assert s["resultado"] == "nada" and s["estado_retirada"] == "refutacion"


async def test_calendario_sobrevive_a_la_rotacion_del_audit_log(datos):
    from aura_skeleton.core import reloj_cm2

    obs._audit = obs.AuditLog(_audit(datos), umbral_bytes=300)  # rota casi en cada evento
    ej2 = EjecutorModeloUsuario(_memoria(datos))
    await _tres_hechos(ej2)
    assert obs._audit.segmentos(), "la prueba exige que el audit haya rotado"
    _iniciar(datos)
    reloj_cm2.medir(datos, ahora=T0 + 8 * DIA)
    sondas = _eventos(datos, "cm2.sonda")
    assert len(sondas) == 3 and {s["dia"] for s in sondas} == {7}
    reloj_cm2.medir(datos, ahora=T0 + 8 * DIA)  # releer todo (segmentos + activo) no duplica
    assert len(_eventos(datos, "cm2.sonda")) == 3


# ======================================================================= CLI ==


def test_cli_medir_sin_marcador_informa_y_no_compone(datos, monkeypatch, capsys):
    from aura_skeleton import __main__ as principal

    monkeypatch.setenv("AURA_DATOS", datos)

    def _no_componer(*_a, **_k):
        raise AssertionError("--medir-cm2 no debe componer AURA completa")

    monkeypatch.setattr(principal, "componer", _no_componer)
    assert principal.main(["--medir-cm2"]) == 0
    salida = capsys.readouterr().out
    assert "reloj de CM2: NO iniciado" in salida
    assert _eventos(datos) == []


def test_cli_iniciar_sin_confirmacion_no_emite_nada(datos, monkeypatch, capsys):
    from aura_skeleton import __main__ as principal

    monkeypatch.setenv("AURA_DATOS", datos)
    assert principal.main(["--iniciar-cm2"]) == 0
    assert "--confirmo-inicio" in capsys.readouterr().out
    assert _eventos(datos) == [] and not os.path.exists(_audit(datos))


def test_cli_iniciar_con_confirmacion_emite_cm2_inicio_en_el_tmp(datos, monkeypatch, capsys):
    from aura_skeleton import __main__ as principal

    monkeypatch.setenv("AURA_DATOS", datos)
    assert principal.main(["--iniciar-cm2", "--confirmo-inicio"]) == 0
    assert "iniciado" in capsys.readouterr().out
    (e,) = _eventos(datos, "cm2.inicio")
    assert e["msg"] == "inicio de la medicion" and set(e) <= {
        "level",
        "module",
        "msg",
        "trace_id",
        "audit",
        "evento",
        "ts",
        "seq",
    }
    # DP-RESIDENCIA-MEDICION-CM2 §4.1: cerrojo persistente, creado en la primera escritura; ningun otro marcador.
    assert sorted(os.listdir(datos)) == ["audit.jsonl", "audit.jsonl.lock", "memoria.json"]


def test_segundo_inicio_es_idempotente(datos):
    from aura_skeleton.core import reloj_cm2

    reloj_cm2.iniciar(datos, confirmo=True)
    antes = _sha(_audit(datos))
    assert "ya iniciado" in reloj_cm2.iniciar(datos, confirmo=True)
    assert _sha(_audit(datos)) == antes
    assert len(_eventos(datos, "cm2.inicio")) == 1


def test_el_inicio_sobrevive_a_la_rotacion_y_medir_lo_ve(datos):
    from aura_skeleton.core import reloj_cm2

    obs._audit = obs.AuditLog(_audit(datos), umbral_bytes=100)
    obs.log("CM2", "reloj-cm2", "inicio de la medicion", "-", audit=True, evento="cm2.inicio")
    obs.log("X", "m", "relleno " * 20, "-", audit=True)
    assert obs._audit.segmentos(), "la prueba exige que el inicio quede en un segmento sellado"
    assert reloj_cm2.medir(datos, ahora=T0).startswith("reloj de CM2: iniciado")


def test_sin_confirmacion_iniciar_no_emite(datos):
    from aura_skeleton.core import reloj_cm2

    assert "NO iniciado" in reloj_cm2.iniciar(datos, confirmo=False)
    assert not os.path.exists(_audit(datos))


def test_reloj_cm2_no_escribe_a_disco_por_su_cuenta_g1_pasa_sin_exclusion():
    """G-1 R-A y R-B pasan SIN que el manifiesto nombre `reloj_cm2`: el inicio es un evento de auditoria."""
    import pathlib
    import sys

    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "unit"))
    import verificador_g1 as verificador  # noqa: I001

    manifiesto = pathlib.Path(__file__).resolve().parents[2] / "architecture_manifest.toml"
    assert "reloj_cm2" not in manifiesto.read_text(encoding="utf-8")
    for violaciones in (verificador.violaciones_ra(), verificador.violaciones_rb()):
        assert not violaciones, verificador.explicar(violaciones)


# ============================================== lectura de memoria sin duplicar la proyeccion ==


async def test_la_lectura_solo_lectura_aplica_la_misma_proyeccion_que_persistent_memory(ej, datos):
    from aura_skeleton.core import reloj_cm2

    await _declarar(ej, UID, "mi coche es rojo", T0)
    await _declarar(ej, UID, "me llamo Mauricio", T0)
    await _declarar(ej, UID, "mi coche es azul", T0 + DIA)  # cierra la v1 (marca => linea nueva, ultima gana)
    await ej.execute("olvidar_informacion_usuario", {"user_id": UID, "contiene": "me llamo"}, "t", "ev")
    ruta = os.path.join(datos, "memoria.json")
    antes = _sha(ruta)
    leida = reloj_cm2._MemoriaSoloLectura(ruta)._items
    assert leida == _memoria(datos)._items
    assert _sha(ruta) == antes
    # control de la lapida: lo olvidado por el flujo real NO esta, aunque su linea original siga en disco
    assert "me llamo Mauricio" not in [i["content"] for i in leida]
    assert "me llamo Mauricio" in open(ruta, encoding="utf-8").read()


# ================================================== sondas tardias (extremo a extremo) ==


async def test_medir_a_los_40_dias_registra_las_sondas_pero_la_de_28_no_entra_en_la_tasa(ej, datos):
    from aura_skeleton.core import reloj_cm2

    await _tres_hechos(ej)
    _iniciar(datos)
    texto = reloj_cm2.medir(datos, ahora=T0 + 40 * DIA)
    d28 = [s for s in _eventos(datos, "cm2.sonda") if s["dia"] == 28]
    assert len(d28) == 3 and all(s["edad_dias"] == 40.0 for s in d28)
    t = reloj_cm2.tasa_dia28(obs.leer_audit_desde(_audit(datos), -1), minimo=1)
    assert t.denominador == 0 and t.fuera_de_ventana == 3
    assert "3 tardia(s)" in texto


async def test_medir_dentro_de_la_tolerancia_cuenta_en_la_tasa(ej, datos):
    from aura_skeleton.core import reloj_cm2

    await _tres_hechos(ej)
    _iniciar(datos)
    reloj_cm2.medir(datos, ahora=T0 + 30 * DIA)
    t = reloj_cm2.tasa_dia28(obs.leer_audit_desde(_audit(datos), -1), minimo=1)
    assert (t.denominador, t.recuperados) == (3, 3)


# ===================================== memoria parcial, datos invalidos, flags excluyentes ==


async def test_memoria_con_linea_parcial_lanza_memoria_no_legible_y_no_emite_sondas(ej, datos):
    from aura_skeleton.core import reloj_cm2

    await _tres_hechos(ej)
    _iniciar(datos)
    with open(os.path.join(datos, "memoria.json"), "a", encoding="utf-8") as f:
        f.write('{"user_id": "mauricio", "kind": "sem')  # AURA escribiendo
    with pytest.raises(reloj_cm2.MemoriaNoLegible, match="no se mide; reintentar"):
        reloj_cm2.medir(datos, ahora=T0 + 29 * DIA)
    assert _eventos(datos, "cm2.sonda") == []


async def test_cli_medir_con_memoria_parcial_sale_con_codigo_distinto_de_cero(ej, datos, capsys, monkeypatch):
    from aura_skeleton import __main__ as principal

    await _tres_hechos(ej)  # declarados en T0 (2023): a fecha real ya vencieron las sondas
    _iniciar(datos)
    with open(os.path.join(datos, "memoria.json"), "a", encoding="utf-8") as f:
        f.write('{"user_id": "mauricio", "kind": "sem')
    monkeypatch.setenv("AURA_DATOS", datos)
    assert principal.main(["--medir-cm2"]) == 1
    assert "no se mide; reintentar" in capsys.readouterr().out
    assert _eventos(datos, "cm2.sonda") == []


def test_iniciar_con_datos_inexistentes_no_crea_el_directorio_ni_emite(tmp_path):
    from aura_skeleton.core import reloj_cm2

    inexistente = str(tmp_path / "no-existe")
    with pytest.raises(reloj_cm2.DatosNoValidos):
        reloj_cm2.iniciar(inexistente, confirmo=True)
    assert not os.path.exists(inexistente)


def test_iniciar_en_directorio_sin_memoria_ni_audit_se_rechaza_sin_emitir(tmp_path):
    from aura_skeleton.core import reloj_cm2

    vacio = tmp_path / "vacio"
    vacio.mkdir()
    with pytest.raises(reloj_cm2.DatosNoValidos):
        reloj_cm2.iniciar(str(vacio), confirmo=True)
    assert os.listdir(vacio) == []


def test_cli_iniciar_con_datos_invalidos_sale_con_codigo_distinto_de_cero(tmp_path, monkeypatch, capsys):
    from aura_skeleton import __main__ as principal

    inexistente = str(tmp_path / "no-existe")
    monkeypatch.setenv("AURA_DATOS", inexistente)
    assert principal.main(["--iniciar-cm2", "--confirmo-inicio"]) == 1
    assert "no se crea nada" in capsys.readouterr().out
    assert not os.path.exists(inexistente)


def test_iniciar_y_medir_juntos_es_un_error_explicito(datos, monkeypatch, capsys):
    from aura_skeleton import __main__ as principal

    monkeypatch.setenv("AURA_DATOS", datos)
    with pytest.raises(SystemExit) as e:
        principal.main(["--iniciar-cm2", "--medir-cm2"])
    assert e.value.code == 2
    assert "mutuamente excluyentes" in capsys.readouterr().err
    assert _eventos(datos) == []


# ============================================ el kill switch (b) no condiciona la medicion ==


async def test_con_y_sin_kill_switch_la_medicion_produce_las_mismas_sondas_y_el_mismo_hash(ej, datos, tmp_path):
    import shutil

    from aura_skeleton.core import reloj_cm2

    await _tres_hechos(ej)
    _iniciar(datos)
    otro = str(tmp_path / "datos_kill")
    shutil.copytree(datos, otro)
    with open(os.path.join(otro, "KILL"), "w", encoding="utf-8") as f:
        f.write("armado")
    reloj_cm2.medir(datos, ahora=T0 + 29 * DIA)
    reloj_cm2.medir(otro, ahora=T0 + 29 * DIA)

    def firma(d):
        return sorted(
            (s["hecho_id"], s["dia"], s["resultado"], s["estado_retirada"], s["edad_dias"], s["n_entradas_memoria"])
            for s in _eventos(d, "cm2.sonda")
        )

    assert firma(datos) == firma(otro) and len(firma(datos)) == 9
    assert _sha(os.path.join(datos, "memoria.json")) == _sha(os.path.join(otro, "memoria.json"))


# ============================================ sin efectos por importar o consultar; sin inicio real ==


def _huella(directorio: str) -> dict[str, str]:
    """Hash de TODO el directorio (rutas relativas -> sha256; los directorios vacios constan)."""
    salida: dict[str, str] = {}
    for raiz, dirs, ficheros in os.walk(directorio):
        for d in dirs:
            salida[os.path.relpath(os.path.join(raiz, d), directorio) + "/"] = "dir"
        for f in ficheros:
            salida[os.path.relpath(os.path.join(raiz, f), directorio)] = _sha(os.path.join(raiz, f))
    return salida


def _correr(args: list[str], datos: str, home: str) -> subprocess.CompletedProcess[str]:
    import pathlib
    import sys

    raiz = str(pathlib.Path(__file__).resolve().parents[2])
    env = {**os.environ, "AURA_DATOS": datos, "HOME": home, "PYTHONPATH": raiz}
    return subprocess.run([sys.executable, *args], cwd=raiz, env=env, capture_output=True, text=True, timeout=120)


async def test_importar_el_modulo_y_medir_sin_inicio_no_tocan_ni_un_fichero(ej, datos, tmp_path):
    await _tres_hechos(ej)
    home = tmp_path / "home_real"
    home.mkdir()
    antes_d, antes_h = _huella(datos), _huella(str(home))
    assert "audit.jsonl" in antes_d  # control: la huella ve el audit (si no, la prueba seria decorativa)

    imp = _correr(["-c", "import aura_skeleton.core.reloj_cm2"], datos, str(home))
    assert imp.returncode == 0, imp.stderr
    assert (_huella(datos), _huella(str(home))) == (antes_d, antes_h)

    cli = _correr(["-m", "aura_skeleton", "--medir-cm2"], datos, str(home))
    assert cli.returncode == 0, cli.stderr
    assert "NO iniciado" in cli.stdout
    assert (_huella(datos), _huella(str(home))) == (antes_d, antes_h)
    assert _eventos(datos, "cm2.sonda") == [] and _eventos(datos, "cm2.inicio") == []


def test_la_huella_detecta_un_fichero_nuevo_y_una_modificacion(datos):
    antes = _huella(datos)
    with open(os.path.join(datos, "nuevo"), "w") as f:
        f.write("x")
    assert _huella(datos) != antes
    despues = _huella(datos)
    with open(os.path.join(datos, "memoria.json"), "a") as f:
        f.write("x")
    assert _huella(datos) != despues


def test_ninguna_prueba_del_repo_puede_iniciar_el_reloj_real():
    """Guardia estatica: toda llamada a `iniciar(` o `--iniciar-cm2` en tests usa un AURA_DATOS de tmp."""
    import pathlib
    import re

    tests = pathlib.Path(__file__).resolve().parents[1]
    yo = pathlib.Path(__file__).resolve()
    llamada = re.compile(r"reloj_cm2\.iniciar\(|[\"']--iniciar-cm2[\"']")
    visto = 0
    for f in tests.rglob("*.py"):
        if f == yo:
            continue
        assert not llamada.search(f.read_text(encoding="utf-8")), f"{f} inicia el reloj fuera del fichero guardado"
    texto = yo.read_text(encoding="utf-8")
    for n, linea in enumerate(texto.splitlines(), 1):
        if re.search(r"reloj_cm2\.iniciar\(", linea) and "def " not in linea:
            visto += 1
            assert re.search(r"iniciar\((datos|otro|inexistente|str\(vacio\)|str\(tmp_path)", linea), (
                f"linea {n}: {linea}"
            )
    assert visto >= 3  # control: la guardia ve las llamadas que hay
    assert "AURA_DATOS" in texto and "_aislar_datos_reales" in texto  # el aislamiento autouse sigue ahi


async def test_reconstruccion_tras_reinicio_sin_estado_en_memoria(ej, datos):
    """Un proceso nuevo (audit reiniciado) reconstruye el calendario SOLO desde el audit.jsonl: no repite sondas."""
    from aura_skeleton.core import reloj_cm2

    await _tres_hechos(ej)
    _iniciar(datos)
    reloj_cm2.medir(datos, ahora=T0 + 8 * DIA)
    assert len(_eventos(datos, "cm2.sonda")) == 3
    obs.reset_audit()  # «reinicio»: ni cursor ni singleton
    reloj_cm2.medir(datos, ahora=T0 + 8 * DIA)
    assert len(_eventos(datos, "cm2.sonda")) == 3
    reloj_cm2.medir(datos, ahora=T0 + 15 * DIA)
    assert sorted(s["dia"] for s in _eventos(datos, "cm2.sonda")) == [7, 7, 7, 14, 14, 14]


async def test_hechos_anteriores_al_inicio_no_se_sondean_a_28_dias_el_primer_dia(ej, datos):
    from aura_skeleton.core import reloj_cm2

    await _tres_hechos(ej)  # declarados en T0
    _iniciar(datos, ts=T0 + 60 * DIA)  # el reloj arranca 60 dias DESPUES
    reloj_cm2.medir(datos, ahora=T0 + 60 * DIA + 1)
    assert _eventos(datos, "cm2.sonda") == []
    reloj_cm2.medir(datos, ahora=T0 + 67 * DIA)
    sondas = _eventos(datos, "cm2.sonda")
    assert sorted(s["dia"] for s in sondas) == [7, 7, 7]
    assert all(s["edad_dias"] == 7.0 and s["version_edad_dias"] == 7.0 for s in sondas)


def test_el_informe_del_cli_muestra_inicio_y_seq(datos, monkeypatch, capsys):
    from aura_skeleton import __main__ as principal

    monkeypatch.setenv("AURA_DATOS", datos)
    assert principal.main(["--iniciar-cm2", "--confirmo-inicio"]) == 0
    capsys.readouterr()
    assert principal.main(["--medir-cm2"]) == 0
    salida = capsys.readouterr().out
    (e,) = _eventos(datos, "cm2.inicio")
    assert "inicio del reloj: " in salida and f"(seq {e['seq']})" in salida


# ------------------------------------------- cadena de PRODUCCION hasta la sonda de dia 28 (gate S3) --
#
# Hueco medido 2026-10-25 (mutante C1 de `mutaciones/cm2-cableado-produccion.toml`): ninguna prueba recorria
# `componer` → turno de declaracion → `cm2.hecho_registrado` en `<datos>/audit.jsonl` → `medir` a 28 dias. Si
# la composicion auditaba en otro fichero, el reloj quedaba ciego con todo en verde, y la poblacion real en 0
# se habria atribuido a la falta de uso (D-CM2-1) en vez de a un defecto. El tiempo no se simula en el
# sistema: solo se pasa un `ahora` explicito a `medir`.


class _EspiaModelo:
    """Sustituye a los proveedores: un hecho declarado no necesita modelo, y si llegara se contaria."""

    name = "espia"

    def __init__(self) -> None:
        self.llamadas = 0

    async def infer(self, prompt: str, modo: str = "accion") -> str:
        self.llamadas += 1
        return json.dumps({"intent": "x", "action": "consulta", "args": {}, "say": "MARCA-MODELO"})


def _produccion_iniciada(datos: str):
    """El reloj de ESTE tmp iniciado, y AURA compuesta como en produccion (stack mock) sobre el mismo directorio."""
    from aura_skeleton.composicion import Configuracion, componer
    from aura_skeleton.core import reloj_cm2

    assert reloj_cm2.iniciar(datos, confirmo=True) == "reloj de CM2: iniciado"
    obs.reset_audit()
    s = componer(Configuracion(datos=datos, raices_permitidas=(datos,), usar_stack_real=False))
    espia = _EspiaModelo()
    s.orquestador.router.providers = [espia]
    return s, espia


async def _turno_real(s, texto: str) -> None:
    import uuid

    tid = uuid.uuid4().hex[:12]
    await s.orquestador.handle_utterance(UID, texto, tid)
    await s.orquestador.wait(tid)
    obs.reset_audit()


def _sondas_a(datos: str, dias: float) -> list[dict]:
    import time

    from aura_skeleton.core import reloj_cm2

    reloj_cm2.medir(datos, ahora=time.time() + dias * DIA)
    obs.reset_audit()
    return _eventos(datos, "cm2.sonda")


async def test_produccion_una_declaracion_real_llega_al_reloj_y_a_28_dias_es_sonda_vigente(datos):
    from aura_skeleton.core import reloj_cm2

    s, espia = _produccion_iniciada(datos)
    await _turno_real(s, "mi color favorito es el azul")
    assert len(_eventos(datos, "cm2.hecho_registrado")) == 1
    sondas = _sondas_a(datos, 28.3)
    assert [(e["dia"], e["resultado"]) for e in sondas if e["dia"] == 28] == [(28, "vigente")], sondas
    t = reloj_cm2.tasa_dia28(_eventos(datos), minimo=1)
    assert (t.veredicto, t.denominador, t.recuperados) == (reloj_cm2.MEDIDA, 1, 1), t
    assert espia.llamadas == 0, "una declaracion de hecho propio no puede necesitar el modelo"


async def test_produccion_control_un_turno_que_no_declara_no_puebla_el_reloj(datos):
    """Control: si la poblacion saliera de cualquier turno, este tambien contaria."""
    s, _ = _produccion_iniciada(datos)
    await _turno_real(s, "hola")
    assert _eventos(datos, "cm2.hecho_registrado") == []
    assert _sondas_a(datos, 28.3) == []


async def test_produccion_antes_del_dia_28_no_hay_sonda_de_dia_28(datos):
    """El gate no se adelanta: a los 27,9 dias el hecho real solo tiene las sondas de 7 y 14."""
    from aura_skeleton.core import reloj_cm2

    s, _ = _produccion_iniciada(datos)
    await _turno_real(s, "mi ciudad es Bogotá")
    assert sorted(e["dia"] for e in _sondas_a(datos, 27.9)) == [7, 14]
    assert reloj_cm2.tasa_dia28(_eventos(datos), minimo=1).veredicto == reloj_cm2.SIN_DATOS
