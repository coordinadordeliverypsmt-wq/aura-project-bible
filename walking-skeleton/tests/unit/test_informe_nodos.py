"""`informe_nodos`: presentación pura de HC-1 y de los nodos registrados."""

from __future__ import annotations

from aura_skeleton.adapters.receptor_nodos import informe_nodos
from aura_skeleton.core.nodos import RegistroNodos, construir_latido, validar_latido

ID_A = "a" * 32
ARR = "1" * 32
HC1 = {"ram_mb": 16000.0, "nucleos": 8.0, "isa_avx2": 1.0, "gpu_render": 1.0}


def _registro(recibido_en, ram=986.0, omitidas=(), nombre="nodo-01"):
    latido = validar_latido(
        construir_latido(
            ID_A, nombre, 7, ARR, 10.0, {"ram_mb": ram, "nucleos": 2.0, "video_dispositivos": 0.0}, omitidas, "1.0"
        )
    )
    reg = RegistroNodos()
    reg.registrar(latido, recibido_en)
    datos = reg.a_dict()
    datos["nodos"][ID_A]["primer_contacto"] = 1000.0
    datos["nodos"][ID_A]["reinicios"] = 3
    return datos


def _con_receptor(datos, latido):
    return {"receptor": {"latido": latido, "pid": 1}, "nodos": datos["nodos"]}


def test_receptor_vivo_y_nodo_online():
    texto = informe_nodos(_con_receptor(_registro(996.0), 996.0), HC1, 1000.0)
    assert "AURA — nodos y sobres de capacidad" in texto
    assert "HC-1 (este equipo, medido ahora)" in texto
    assert "receptor de nodos: VIVO (hace 4 s)" in texto
    assert f"nodo-01 [{ID_A[:8]}…]  ONLINE" in texto
    assert "último latido: hace 4 s" in texto
    assert "reinicios: 3" in texto and "secuencia 7" in texto and "agente 1.0" in texto
    assert "omitidas: ninguna" in texto
    assert "indican HARDWARE/INTERFAZ PRESENTE" in texto


def test_recursos_hc1_en_orden_alfabetico():
    texto = informe_nodos({"receptor": None, "nodos": {}}, HC1, 1000.0)
    linea = next(x for x in texto.splitlines() if x.strip().startswith("recursos:"))
    assert linea.strip() == "recursos: gpu_render=1 isa_avx2=1 nucleos=8 ram_mb=16000"


def test_receptor_muerto_deja_nodo_unknown_aunque_su_latido_sea_reciente():
    datos = _con_receptor(_registro(999.0), 1000.0 - 31.0)
    texto = informe_nodos(datos, HC1, 1000.0)
    assert "receptor de nodos: NO ESCUCHA (último latido hace 31 s)" in texto
    assert "UNKNOWN" in texto and "HC-1 no está escuchando" in texto
    assert "ONLINE" not in texto


def test_receptor_en_el_limite_sigue_vivo():
    texto = informe_nodos(_con_receptor(_registro(999.0), 970.0), HC1, 1000.0)
    assert "receptor de nodos: VIVO (hace 30 s)" in texto


def test_receptor_que_nunca_latio():
    texto = informe_nodos({"receptor": None, "nodos": _registro(999.0)["nodos"]}, HC1, 1000.0)
    assert "receptor de nodos: NO ESCUCHA (último latido nunca)" in texto
    assert "UNKNOWN" in texto


def test_nodo_viejo_es_offline():
    texto = informe_nodos(_con_receptor(_registro(900.0), 1000.0), HC1, 1000.0)
    assert f"nodo-01 [{ID_A[:8]}…]  OFFLINE" in texto


def test_nodo_con_omitidas_es_degraded_y_las_lista():
    texto = informe_nodos(_con_receptor(_registro(999.0, omitidas=("gpu_render",)), 1000.0), HC1, 1000.0)
    assert "DEGRADED" in texto and "omitidas: gpu_render" in texto


def test_sin_nodos():
    texto = informe_nodos({"receptor": {"latido": 1000.0, "pid": 1}, "nodos": {}}, HC1, 1000.0)
    assert "ningún nodo registrado" in texto


def test_capacidades_del_nodo_segun_su_ram():
    pobre = informe_nodos(_con_receptor(_registro(999.0, ram=986.0), 1000.0), HC1, 1000.0)
    rico = informe_nodos(_con_receptor(_registro(999.0, ram=16000.0), 1000.0), HC1, 1000.0)
    caps_pobre = [x for x in pobre.splitlines() if "capacidades" in x][-1]
    caps_rico = [x for x in rico.splitlines() if "capacidades" in x][-1]
    assert "memoria=DEGRADADA" in caps_pobre
    assert "memoria=ACTIVA" in caps_rico


def test_capacidades_de_hc1_aparecen():
    texto = informe_nodos({"receptor": None, "nodos": {}}, {"ram_mb": 16000.0, "nucleos": 8.0}, 1000.0)
    primera = next(x for x in texto.splitlines() if "capacidades (CapabilityManager)" in x)
    assert "memoria=ACTIVA" in primera
