"""Pruebas del AURA Progress Dashboard (herramientas/panel_progreso.py).

El panel es un modulo de PROCESO, no una capacidad del producto: proyecta ficheros que ya existen
(mapa maestro, MAPA fisico, DECISION-REQUERIDA, CHECKPOINT, registro del gate) a un HTML estatico.
Lo unico que no puede hacer es MENTIR, asi que cada prueba lleva su caso de control:

* el indice sale de `herramientas/indice_madurez.calcular` (misma fuente que el oficial), nunca de
  una formula copiada;
* una fuente rota produce un bloque con `error`, nunca cifras inventadas;
* el ecosistema se publica CENSURADO (MAC, uuid, serie, IP, secretos);
* el panel nunca escribe en las fuentes.

Raiz FALSA en tmp_path con ficheros minimos; un caso con el repo real comprueba la coherencia.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import re
from datetime import datetime
from pathlib import Path

import pytest

from herramientas import panel_progreso as pp

RAIZ_REAL = Path(__file__).resolve().parents[3]
AHORA = datetime(2026, 10, 22, 12, 0, 0)
ESCALA = "0 inexistente · 1 concepto · 2 prototipo · 3 implementada · 4 integrada · 5 demostrada E2E · 6 operativa"

CAPS = [
    {"dim": "A", "capacidad": "uno", "nivel": 4, "alcance": "MVP", "evidencia": "x.py", "bloqueo": ""},
    {
        "dim": "A",
        "capacidad": "dos",
        "nivel": 1,
        "alcance": "R2",
        "evidencia": "",
        "bloqueo": "Decisión del CEO pendiente",
    },
    {
        "dim": "B",
        "capacidad": "tres",
        "nivel": 3,
        "alcance": "MVP",
        "evidencia": "y.py",
        "bloqueo": "hardware sin encender",
    },
]

MAPA = """# Mapa
## 7. Siguiente accion
Texto sin tabla.

## 7. Inventario contrastado

| Equipo | Observa | Estado | Bloqueo |
|---|---|---|---|
| Camara .110 | MAC 88:E6:28:BB:69:C1 en 192.168.20.110 | IDENTIFICADO | urn:uuid:11111111-2222-3333-4444-555555555555 |
| DVR | serie AJWL200708101YP47Q874KI4TR112829 | NO SE TOCA | contraseña admin123 |

## 8. Otro
"""


def _montar(tmp_path: Path, caps: list[dict] | None = None, mapa: str = MAPA) -> Path:
    raiz = tmp_path / "repo"
    (raiz / "milestones/mapa-maestro").mkdir(parents=True)
    (raiz / "milestones/m3-entry").mkdir(parents=True)
    (raiz / "walking-skeleton/mutaciones").mkdir(parents=True)
    datos = {"actualizado": "2026-10-20 (prueba)", "escala": ESCALA, "capacidades": CAPS if caps is None else caps}
    (raiz / "milestones/mapa-maestro/capacidades.json").write_text(json.dumps(datos), encoding="utf-8")
    (raiz / "milestones/m3-entry/MAPA-ECOSISTEMA-FISICO.md").write_text(mapa, encoding="utf-8")
    (raiz / "milestones/m3-entry/DECISION-REQUERIDA-A.md").write_text(
        "# A\n**Estado:** RESUELTA por el CEO el 2026-10-22\n", encoding="utf-8"
    )
    (raiz / "milestones/m3-entry/DECISION-REQUERIDA-B.md").write_text(
        "# B\n**Estado: PROPUESTA (no autorizada)**\n", encoding="utf-8"
    )
    (raiz / "CHECKPOINT-CONTINUIDAD.md").write_text(
        "## 2026-10-01 · viejo\nx\n## 2026-10-22 (f) · ultimo punto\ny\n", encoding="utf-8"
    )
    (raiz / "walking-skeleton/mutaciones/a.toml").write_text(
        'incremento = "a"\n[[mutante]]\nid = "M1"\n[[mutante]]\nid = "M2"\n', encoding="utf-8"
    )
    return raiz


def _modelo(raiz: Path, **kw):
    kw.setdefault("registro_gate", None)
    return pp.construir_modelo(raiz, AHORA, **kw)


def _indice_oficial():
    spec = importlib.util.spec_from_file_location("im", RAIZ_REAL / "herramientas/indice_madurez.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ---------------------------------------------------------------- global / dimensiones / capacidades
def test_global_coincide_exactamente_con_calcular(tmp_path):
    im = _indice_oficial()
    m = _modelo(_montar(tmp_path))["global"]
    for clave, ambito in (("mvp", "MVP"), ("horizonte", None)):
        esperado = im.calcular(CAPS, ambito)
        assert m[clave]["indice"] == esperado["indice"]
        assert m[clave]["core"] == esperado["core"]
        assert m[clave]["ready"] == esperado["ready"]
    # control: MVP y horizonte son numeros distintos (no se ha usado el mismo ambito dos veces)
    assert m["mvp"]["indice"] != m["horizonte"]["indice"]
    assert m["mvp"]["significado"] and m["horizonte"]["formula"]
    assert m["fecha"] == "2026-10-20"


def test_global_recuentos_por_nivel_calculados_del_json(tmp_path):
    m = _modelo(_montar(tmp_path))["global"]
    assert m["por_nivel"] == {0: 0, 1: 1, 2: 0, 3: 1, 4: 1, 5: 0, 6: 0}
    assert m["total"] == 3


def test_dimensiones_agregacion_y_recuentos(tmp_path):
    d = _modelo(_montar(tmp_path))["dimensiones"]
    assert set(d["dimensiones"]) == {"A", "B"}
    a = d["dimensiones"]["A"]
    assert a["n"] == 2 and a["por_nivel"][4] == 1 and a["por_nivel"][1] == 1
    assert a["capacidades"] == ["uno", "dos"]
    esperado = _indice_oficial().calcular(CAPS, None)["dimensiones"]["A"]
    assert a["indice"] == esperado["indice"] and a["core"] == esperado["core"] and a["ready"] == esperado["ready"]
    assert "no define nombres de dimensión" in d["aviso"]
    # control: B no arrastra las capacidades de A
    assert d["dimensiones"]["B"]["capacidades"] == ["tres"]


def test_estado_es_nombre_oficial_de_la_escala(tmp_path):
    caps = _modelo(_montar(tmp_path))["capacidades"]["capacidades"]
    assert [c["estado"] for c in caps] == ["integrada", "concepto", "implementada"]
    assert caps[1]["bloqueo"] == "Decisión del CEO pendiente"  # literal salvo censura (ver test_modelo_censura_*)


def test_nivel_sin_evidencia_da_error_y_no_indice(tmp_path):
    malas = [{"dim": "A", "capacidad": "x", "nivel": 3, "alcance": "MVP", "evidencia": "", "bloqueo": ""}]
    m = _modelo(_montar(tmp_path, caps=malas))
    assert "sin evidencia" in m["global"]["error"]
    assert "mvp" not in m["global"] and "indice" not in m["global"]
    # control: con evidencia el mismo caso no falla
    ok = [{**malas[0], "evidencia": "z.py"}]
    assert "error" not in _modelo(_montar(tmp_path / "b", caps=ok))["global"]


def test_json_malformado_da_error(tmp_path):
    raiz = _montar(tmp_path)
    (raiz / "milestones/mapa-maestro/capacidades.json").write_text("{no es json", encoding="utf-8")
    m = _modelo(raiz)
    assert m["global"]["error"] and m["dimensiones"]["error"] and m["capacidades"]["error"]
    # control: los bloques de otras fuentes siguen vivos
    assert "error" not in m["checkpoint"]


@pytest.mark.parametrize(("dias", "esperado"), [(7, False), (1, True)])
def test_desactualizado_segun_umbral(tmp_path, dias, esperado):
    # `actualizado` es 2026-10-20 y AHORA 2026-10-22: 2 dias de antiguedad
    m = _modelo(_montar(tmp_path), umbral_dias=dias)
    assert m["global"]["desactualizado"] is esperado
    assert m["umbral_dias"] == dias


# ---------------------------------------------------------------- calidad
def test_falta_registro_gate_es_sin_registro(tmp_path):
    q = _modelo(_montar(tmp_path), registro_gate=tmp_path / "no-existe.json")["calidad"]
    assert "sin registro" in q["gate"]["estado"]
    assert "pytest" not in q["gate"]


def test_registro_gate_pass_y_fail_se_leen(tmp_path):
    base = {
        "fecha": "2026-10-22T10:00:00",
        "sha": "abc1234",
        "pasos": {"formato": "OK", "lint": "OK", "tipado": "OK", "pruebas": "OK", "contratos": "OK"},
        "pytest": {"passed": 3560, "failed": 0, "skipped": 1, "xfailed": 0, "errors": 0},
    }
    for res in ("PASS", "FAIL"):
        f = tmp_path / f"g-{res}.json"
        f.write_text(json.dumps({**base, "resultado": res}), encoding="utf-8")
        g = _modelo(_montar(tmp_path / res), registro_gate=f)["calidad"]["gate"]
        assert g["resultado"] == res and g["sha"] == "abc1234" and g["pytest"]["passed"] == 3560
        assert g["desactualizado"] is False  # 2 horas
    viejo = tmp_path / "viejo.json"
    viejo.write_text(json.dumps({**base, "resultado": "PASS", "fecha": "2026-09-01T10:00:00"}), encoding="utf-8")
    assert _modelo(_montar(tmp_path / "v"), registro_gate=viejo)["calidad"]["gate"]["desactualizado"] is True


def test_registro_gate_corrupto_da_error(tmp_path):
    f = tmp_path / "g.json"
    f.write_text("{roto", encoding="utf-8")
    assert _modelo(_montar(tmp_path), registro_gate=f)["calidad"]["gate"]["error"]


def test_garantias_de_mutacion_y_nota(tmp_path):
    q = _modelo(_montar(tmp_path))["calidad"]
    assert q["garantias_mutacion"] == 2 and q["ficheros_mutacion"] == 1
    assert "NO es avance del proyecto" in q["nota"]


# ---------------------------------------------------------------- etiquetas de bloqueo
@pytest.mark.parametrize(
    ("texto", "etiqueta"),
    [
        ("Decisión del CEO pendiente", "decisión"),
        ("hardware sin encender", "hardware/físico"),
        ("solo nube, D24", "nube/D24"),
        ("falta el modulo X", "dependencia"),
    ],
)
def test_etiquetas_bloqueo_derivadas_y_marcadas(tmp_path, texto, etiqueta):
    assert etiqueta in pp.etiquetas_bloqueo(texto)
    caps = [{"dim": "A", "capacidad": "c", "nivel": 1, "alcance": "MVP", "evidencia": "", "bloqueo": texto}]
    c = _modelo(_montar(tmp_path, caps=caps))["capacidades"]["capacidades"][0]
    assert etiqueta in c["etiquetas_bloqueo"] and c["derivada"] is True


def test_sin_bloqueo_no_hay_etiquetas():
    assert pp.etiquetas_bloqueo("") == []
    assert "dependencia" not in pp.etiquetas_bloqueo("decisión del CEO")


# ---------------------------------------------------------------- censura
def test_censurar_mac_uuid_serie_ip_secreto():
    t = pp.censurar(
        "mac 88:e6:28:BB:69:c1 y urn:uuid:11111111-2222-3333-4444-555555555555, serie AJWL200708101YP47Q874KI4TR112829, "
        "ip 192.168.20.110, contraseña hunter2 y token=abcdef"
    )
    for sensible in ("88:e6", "urn:uuid", "AJWL2007", "192.168", "hunter2", "abcdef"):
        assert sensible not in t
    assert ".110" in t


def test_censurar_no_toca_texto_normal():
    normal = "Cámara .110 en el dormitorio, firmware 3.5.1.1108, nivel 4 de CAPACIDAD y TV SAMSUNG."
    assert pp.censurar(normal) == normal
    assert pp.censurar("IP 192.168.20.110") == "IP .110"
    assert pp.censurar("ya censurada .110") == "ya censurada .110"


def test_ecosistema_censurado_en_el_modelo(tmp_path):
    e = _modelo(_montar(tmp_path))["ecosistema"]
    assert [f["equipo"] for f in e["filas"]] == ["Camara .110", "DVR"]
    assert e["filas"][0]["estado"] == "IDENTIFICADO"
    volcado = json.dumps(e)
    assert not re.search(r"[0-9A-F]{2}(:[0-9A-F]{2}){5}", volcado, re.I)
    assert "urn:uuid" not in volcado and "AJWL2007" not in volcado and "admin123" not in volcado
    assert "192.168" not in volcado and ".110" in volcado


def test_ecosistema_sin_tabla_o_sin_columna_es_error(tmp_path):
    assert "error" in _modelo(_montar(tmp_path, mapa="## 7. Nada\nsolo texto\n"))["ecosistema"]
    sin_estado = "## 7. Inv\n\n| Equipo | Otra |\n|---|---|\n| a | b |\n"
    assert "Estado" in _modelo(_montar(tmp_path / "b", mapa=sin_estado))["ecosistema"]["error"]


def test_html_del_mapa_real_sin_mac_ni_uuid():
    modelo = pp.construir_modelo(RAIZ_REAL, AHORA, registro_gate=None)
    assert modelo["ecosistema"].get("filas"), modelo["ecosistema"]
    html = pp.render_html(modelo)
    assert not re.search(r"\b[0-9A-F]{2}(?::[0-9A-F]{2}){5}\b", html, re.I)
    assert "urn:uuid" not in html.lower()
    # control: el MAPA real SI contiene MAC (la censura trabaja sobre algo)
    mapa = (RAIZ_REAL / "milestones/m3-entry/MAPA-ECOSISTEMA-FISICO.md").read_text(encoding="utf-8")
    assert re.search(r"\b[0-9A-F]{2}(?::[0-9A-F]{2}){5}\b", mapa, re.I)


# ---------------------------------------------------------------- bloqueos / checkpoint
def test_bloqueos_resueltas_vs_pendientes_y_agrupacion(tmp_path):
    b = _modelo(_montar(tmp_path))["bloqueos"]
    por = {d["fichero"]: d for d in b["decisiones"]}
    assert por["DECISION-REQUERIDA-A.md"]["resuelta"] is True
    assert por["DECISION-REQUERIDA-B.md"]["resuelta"] is False
    assert b["resueltas"] == 1 and b["pendientes"] == 1
    assert [c["capacidad"] for c in b["por_etiqueta"]["decisión"]] == ["dos"]
    assert [c["capacidad"] for c in b["por_etiqueta"]["hardware/físico"]] == ["tres"]


def test_checkpoint_ultimo_encabezado(tmp_path):
    c = _modelo(_montar(tmp_path))["checkpoint"]
    assert c["titulo"] == "2026-10-22 (f) · ultimo punto"
    assert c["fecha"] == "2026-10-22" and c["desactualizado"] is False


# ---------------------------------------------------------------- HTML
def test_html_escapa_script_y_titulo(tmp_path):
    caps = [
        {
            "dim": "A",
            "capacidad": "<script>alert(1)</script>",
            "nivel": 1,
            "alcance": "MVP",
            "evidencia": "",
            "bloqueo": "<img onerror=x>",
        }
    ]
    html = pp.render_html(_modelo(_montar(tmp_path, caps=caps)))
    assert "<script" not in html.lower() and "&lt;script&gt;" in html
    assert "<img onerror" not in html
    assert "<title>AURA Progress Dashboard</title>" in html
    for seccion in (
        "Resumen",
        "Dimensiones",
        "Capacidades",
        "Calidad",
        "Ecosistema",
        "Bloqueos y decisiones",
        "Procedencia",
    ):
        assert seccion in html


def test_html_muestra_error_sin_datos_y_desactualizado(tmp_path):
    raiz = _montar(tmp_path)
    (raiz / "milestones/mapa-maestro/capacidades.json").write_text("{roto", encoding="utf-8")
    html = pp.render_html(_modelo(raiz))
    assert "Error" in html and "sin registro" in html
    # `actualizado` = 2026-10-20 y AHORA = 2026-10-22: con umbral 1 es viejo, con 30 no.
    viejo = pp.render_html(_modelo(_montar(tmp_path / "b"), umbral_dias=1))
    assert "desactualizado: fuente de 2026-10-20" in viejo
    fresco = pp.render_html(_modelo(_montar(tmp_path / "c"), umbral_dias=30))
    assert "desactualizado: fuente de" not in fresco  # rompe si el aviso se pinta siempre
    assert "dentro del umbral de 30" in fresco


def test_html_sin_fecha_dice_sin_fecha_y_no_al_dia(tmp_path):
    caps = [{"dim": "A", "capacidad": "x", "nivel": 1, "alcance": "MVP", "evidencia": "", "bloqueo": ""}]
    raiz = _montar(tmp_path, caps=caps)
    datos = json.loads((raiz / "milestones/mapa-maestro/capacidades.json").read_text(encoding="utf-8"))
    datos["actualizado"] = "sin fecha alguna"
    (raiz / "milestones/mapa-maestro/capacidades.json").write_text(json.dumps(datos), encoding="utf-8")
    m = _modelo(raiz)
    assert m["global"]["desactualizado"] is None and m["global"]["fecha"] is None
    html = pp.render_html(m)
    assert "sin fecha para comparar" in html
    assert "dentro del umbral" not in html.split("id='dimensiones'")[0]  # el resumen NO se declara al dia


def test_porcentaje_redondea_a_un_decimal_y_topa_en_99_9():
    assert pp.porcentaje(0.7306) == "73.1 %"  # el oficial publica 73,1; truncar daria 73.0
    assert pp.porcentaje(0.5) == "50.0 %" and pp.porcentaje(0.0) == "0.0 %"
    assert pp.porcentaje(0.9996) == "99.9 %"  # redondeo daria 100.0 sin ser 100
    assert pp.porcentaje(0.99996) == "99.9 %"
    assert pp.porcentaje(1.0) == "100.0 %"


def test_html_de_las_capacidades_reales_no_contradice_el_indice_oficial():
    im = _indice_oficial()
    caps = im.cargar(str(RAIZ_REAL / "milestones/mapa-maestro/capacidades.json"))
    oficial = im.calcular(caps, "MVP")
    html = pp.render_html(pp.construir_modelo(RAIZ_REAL, AHORA, registro_gate=None))
    assert f"Índice: {round(oficial['indice'] * 100, 1):.1f} %" in html
    assert f"Core {round(oficial['core'] * 100, 1):.1f} %" in html
    assert f"Ready {round(oficial['ready'] * 100, 1):.1f} %" in html


# ---------------------------------------------------------------- pureza y escritura
def _huella(raiz: Path) -> dict[str, tuple[float, str]]:
    return {
        str(p): (p.stat().st_mtime, hashlib.sha256(p.read_bytes()).hexdigest())
        for p in sorted(raiz.rglob("*"))
        if p.is_file()
    }


def test_construir_modelo_no_modifica_fuentes(tmp_path):
    raiz = _montar(tmp_path)
    antes = _huella(raiz)
    m = _modelo(raiz)
    pp.render_html(m)
    assert _huella(raiz) == antes
    # control: la huella detecta un cambio real
    (raiz / "CHECKPOINT-CONTINUIDAD.md").write_text("otro", encoding="utf-8")
    assert _huella(raiz) != antes


def test_escritura_atomica_y_fallo_deja_el_anterior(tmp_path, monkeypatch):
    destino = tmp_path / "sub/index.html"
    pp.escribir_atomico("viejo", destino)
    assert destino.read_text(encoding="utf-8") == "viejo"
    pp.escribir_atomico("nuevo", destino)
    assert destino.read_text(encoding="utf-8") == "nuevo"

    def falla(*_a, **_k):
        raise OSError("corte")

    monkeypatch.setattr(os, "replace", falla)
    with pytest.raises(OSError):
        pp.escribir_atomico("a medias", destino)
    assert destino.read_text(encoding="utf-8") == "nuevo"
    assert not list(destino.parent.glob("*.tmp"))


def test_cli_json_y_salida(tmp_path, capsys):
    salida = tmp_path / "o/index.html"
    assert pp.main(["--json", "--umbral-dias", "3"]) == 0
    datos = json.loads(capsys.readouterr().out)
    assert datos["umbral_dias"] == 3 and "global" in datos
    assert pp.main(["--salida", str(salida)]) == 0
    assert "AURA Progress Dashboard" in salida.read_text(encoding="utf-8")


def test_repo_real_coherente_con_oficial():
    m = pp.construir_modelo(RAIZ_REAL, AHORA, registro_gate=None)
    im = _indice_oficial()
    caps = im.cargar(str(RAIZ_REAL / "milestones/mapa-maestro/capacidades.json"))
    assert m["global"]["mvp"]["indice"] == im.calcular(caps, "MVP")["indice"]
    assert m["global"]["horizonte"]["indice"] == im.calcular(caps, None)["indice"]
    assert m["global"]["total"] == len(caps)
    assert m["checkpoint"]["titulo"]


# ---------------------------------------------------------------- revision independiente (2026-10-22)
def _gate_ok(**kw):
    base = {
        "fecha": "2026-10-22T10:00:00",
        "sha": "abc1234",
        "cambios_sin_commit": 4,
        "resultado": "PASS",
        "pasos": {"formato": "OK", "lint": "OK", "tipado": "OK", "pruebas": "OK", "contratos": "OK"},
        "pytest": {"passed": 10, "failed": 0, "skipped": 0, "xfailed": 0, "errors": 0},
    }
    return {**base, **kw}


def _con_gate(tmp_path, datos, nombre="g"):
    f = tmp_path / f"{nombre}.json"
    f.write_text(json.dumps(datos), encoding="utf-8")
    return _modelo(_montar(tmp_path / nombre), registro_gate=f)


def test_gate_con_pytest_null_no_tumba_el_html(tmp_path):
    # registro_gate escribe pytest=null si no hay linea resumen. Rompe si render hace p.items() sobre None.
    m = _con_gate(tmp_path, _gate_ok(pytest=None))
    assert m["calidad"]["gate"]["pytest"] is None
    html = pp.render_html(m)
    assert "sin conteos de pytest" in html
    # control: con conteos NO aparece esa frase
    assert "sin conteos de pytest" not in pp.render_html(_con_gate(tmp_path, _gate_ok(), "ok"))


@pytest.mark.parametrize(
    "malo",
    [
        {"resultado": "MAYBE"},
        {"resultado": None},
        {"pasos": ["formato"]},
        {"pasos": {"formato": 1}},
        {"pytest": ["passed"]},
        {"pytest": {"passed": "x"}},
        {"pytest": {"passed": True}},
        {"fecha": "no es fecha"},
        {"fecha": 20261022},
        {"cambios_sin_commit": "muchos"},
        {"sha": 123},
    ],
)
def test_gate_con_esquema_invalido_da_bloque_error_visible(tmp_path, malo):
    m = _con_gate(tmp_path, _gate_ok(**malo))
    g = m["calidad"]["gate"]
    assert g["error"], malo
    assert "Error" in pp.render_html(m)
    # control: el resto del panel sigue vivo
    assert "error" not in m["global"]


@pytest.mark.parametrize(
    "caps",
    [
        ["x"],
        [{"dim": 1, "capacidad": "c", "nivel": 1, "alcance": "MVP", "evidencia": ""}],
        [{"dim": "A", "capacidad": "c", "nivel": True, "alcance": "MVP", "evidencia": ""}],
        [{"dim": "A", "capacidad": "c", "nivel": 7, "alcance": "MVP", "evidencia": ""}],
        [{"dim": "A", "capacidad": "c", "nivel": "3", "alcance": "MVP", "evidencia": "e"}],
        [{"dim": "A", "capacidad": "c", "nivel": 1, "alcance": None, "evidencia": ""}],
        [{"dim": "A", "capacidad": "c", "nivel": 1, "alcance": "MVP", "evidencia": 5}],
        [{"dim": "A", "capacidad": "c", "nivel": 1, "alcance": "MVP", "evidencia": "", "bloqueo": 3}],
    ],
)
def test_capacidades_mal_tipadas_dan_error_sin_tumbar_el_resto(tmp_path, caps):
    m = _modelo(_montar(tmp_path, caps=caps))
    assert m["global"]["error"] and m["capacidades"]["error"] and m["dimensiones"]["error"]
    assert "error" not in m["checkpoint"] and "error" not in m["ecosistema"]
    assert "Error" in pp.render_html(m)  # y render no revienta


def test_capacidades_que_no_es_lista_da_error(tmp_path):
    raiz = _montar(tmp_path)
    datos = {"actualizado": "2026-10-20", "escala": ESCALA, "capacidades": {"a": 1}}
    (raiz / "milestones/mapa-maestro/capacidades.json").write_text(json.dumps(datos), encoding="utf-8")
    assert _modelo(raiz)["global"]["error"]


@pytest.mark.parametrize("texto", ["2026-13-45", "2026-02-30", "x"])
def test_actualizado_invalido_es_sin_fecha_y_no_crashea(tmp_path, texto):
    raiz = _montar(tmp_path)
    datos = json.loads((raiz / "milestones/mapa-maestro/capacidades.json").read_text(encoding="utf-8"))
    datos["actualizado"] = texto
    (raiz / "milestones/mapa-maestro/capacidades.json").write_text(json.dumps(datos), encoding="utf-8")
    g = _modelo(raiz)["global"]
    assert g["fecha"] is None and g["desactualizado"] is None and "mvp" in g


def test_fecha_de_texto_respeta_limites():
    assert pp._fecha_de_texto("2026-10-22 (f)") == datetime(2026, 10, 22)
    assert pp._fecha_de_texto("12026-10-221") is None  # no casa dentro de un numero mas largo
    assert pp._fecha_de_texto("2026-13-45") is None
    assert pp._fecha_de_texto("2026-13-45 y luego 2026-10-21") == datetime(2026, 10, 21)
    assert pp._fecha_de_texto("") is None


@pytest.mark.parametrize(
    ("entrada", "prohibidos"),
    [
        ("Contraseña Wi-Fi: Casa 1234", ["Casa", "1234"]),
        ("clave: abc123", ["abc123"]),
        ("pass=hunter2", ["hunter2"]),
        ("PSK: s3cr3t", ["s3cr3t"]),
        ("Authorization: Bearer abc.def", ["abc.def"]),
        ("rtsp://admin:pw123@192.168.1.5/stream", ["admin", "pw123", "192.168.1"]),
        ('password: "mi clave larga"', ["mi clave larga", "clave larga", "larga"]),
        ("PASSWORD：zeta99 ok", ["zeta99"]),
        ("api_key = k-111-222", ["k-111-222"]),
        ("API-KEY: k333", ["k333"]),
        ("secret: uno dos tres", ["uno dos tres", "tres"]),
        ("pwd=p4ss", ["p4ss"]),
        ("passwd: q9", ["q9"]),
        ("Contrasena: sinene77", ["sinene77"]),
        ("| wifi | contraseña: Casa 1234 | otra |", ["Casa", "1234"]),
        ("contraseña admin123", ["admin123"]),
        ("mac 88-E6-28-BB-69-C1 x", ["88-E6"]),
        ("mac 88e6.28bb.69c1 x", ["88e6.28bb"]),
        ("id 11111111-2222-3333-4444-555555555555 z", ["11111111-2222"]),
    ],
)
def test_censurar_cubre_secretos_y_identificadores(entrada, prohibidos):
    salida = pp.censurar(entrada)
    for p in prohibidos:
        assert p not in salida, (entrada, salida)
    assert "[" in salida  # algo se censuro de verdad


def test_censurar_conserva_lo_que_no_es_secreto():
    assert "otra" in pp.censurar("| wifi | contraseña: Casa 1234 | otra |")  # corta en el limite de celda
    assert pp.censurar("clave de bóveda del proyecto") == "clave de bóveda del proyecto"  # sin separador
    assert pp.censurar("fecha 2026-10-22 y 2026-10-23") == "fecha 2026-10-22 y 2026-10-23"
    assert pp.censurar("passport control") == "passport control"  # `pass` solo como palabra


def test_modelo_censura_todo_string_de_fuente(tmp_path):
    caps = [
        {
            "dim": "A",
            "capacidad": "cam token=sek-cap",
            "nivel": 2,
            "alcance": "MVP",
            "evidencia": "ver pass=sek-evi",
            "bloqueo": "Decisión: clave: sek-blo",
        }
    ]
    raiz = _montar(tmp_path, caps=caps)
    (raiz / "CHECKPOINT-CONTINUIDAD.md").write_text("## 2026-10-22 password: sek-chk\n", encoding="utf-8")
    m = _modelo(raiz)
    volcado = json.dumps(m, ensure_ascii=False)
    for s in ("sek-cap", "sek-evi", "sek-blo", "sek-chk"):
        assert s not in volcado, s
    assert "sek" not in pp.render_html(m)
    # control: la capacidad sigue presente (se censura el valor, no se descarta la fila)
    assert m["capacidades"]["capacidades"][0]["capacidad"].startswith("cam token")


def test_ambito_vacio_no_es_cero_por_ciento(tmp_path):
    caps = [{"dim": "A", "capacidad": "x", "nivel": 3, "alcance": "R2", "evidencia": "e", "bloqueo": ""}]
    m = _modelo(_montar(tmp_path, caps=caps))
    assert m["global"]["mvp"]["n"] == 0 and m["global"]["horizonte"]["n"] == 1
    html = pp.render_html(m)
    assert "sin capacidades en este ámbito" in html
    resumen = html.split("id='dimensiones'")[0]
    assert resumen.count("Índice:") == 1  # solo el horizonte tiene cifra
    # control: con MVP presente no aparece
    normal = _modelo(_montar(tmp_path / "n"))
    assert normal["global"]["mvp"]["n"] == 2
    assert "sin capacidades en este ámbito" not in pp.render_html(normal)


def test_alcance_desconocido_se_avisa_y_no_se_normaliza(tmp_path):
    caps = [{"dim": "A", "capacidad": "x", "nivel": 3, "alcance": "mvp", "evidencia": "e", "bloqueo": ""}]
    m = _modelo(_montar(tmp_path, caps=caps))
    assert m["global"]["mvp"]["n"] == 0  # NO se normaliza: el oficial manda
    assert any("mvp" in a for a in m["global"]["avisos"])
    assert "alcance desconocido" in pp.render_html(m)
    assert _modelo(_montar(tmp_path / "ok"))["global"]["avisos"] == []


def test_fecha_sin_origen_comprobable_no_se_inventa_con_mtime(tmp_path):
    raiz = _montar(tmp_path)
    (raiz / "CHECKPOINT-CONTINUIDAD.md").write_text("## punto sin fecha\n", encoding="utf-8")
    m = _modelo(raiz)
    assert m["checkpoint"]["fecha"] is None and m["checkpoint"]["desactualizado"] is None
    # ecosistema y decisiones: sin git en la raiz falsa -> sin fecha, NO «al dia» por mtime
    assert m["ecosistema"]["fecha"] is None and m["ecosistema"]["desactualizado"] is None
    assert m["bloqueos"]["fecha"] is None and m["bloqueos"]["desactualizado"] is None


def test_fecha_de_git_se_marca_como_origen_git(tmp_path, monkeypatch):
    monkeypatch.setattr(pp, "_git", lambda raiz, *a: "2026-10-21T10:00:00+00:00" if a[:1] == ("log",) else None)
    m = _modelo(_montar(tmp_path))
    assert m["ecosistema"]["fecha_origen"] == "git" and m["ecosistema"]["desactualizado"] is False
    assert m["bloqueos"]["fecha_origen"] == "git"
    assert m["global"]["fecha_origen"] == "contenido"
    assert "git" in pp.render_html(m)


@pytest.mark.parametrize(
    ("head", "esperado"),
    [("abc1234ffff0000", "coincide"), ("fff0000aaaabbbb", "distinto"), (None, "no comprobado")],
)
def test_gate_compara_sha_con_head(tmp_path, monkeypatch, head, esperado):
    monkeypatch.setattr(pp, "_git", lambda raiz, *a: head if a[:1] == ("rev-parse",) else None)
    m = _con_gate(tmp_path, _gate_ok())
    g = m["calidad"]["gate"]
    assert g["sha_vs_head"] == esperado and g["cambios_sin_commit"] == 4
    html = pp.render_html(m)
    assert "cambios sin commit: 4" in html
    assert ("no coincide con HEAD" in html) is (esperado == "distinto")


def test_gate_sha_desconocido_no_se_declara_coincidente(tmp_path, monkeypatch):
    monkeypatch.setattr(pp, "_git", lambda raiz, *a: "abc1234ffff" if a[:1] == ("rev-parse",) else None)
    assert _con_gate(tmp_path, _gate_ok(sha="desconocido"))["calidad"]["gate"]["sha_vs_head"] == "no comprobado"


def test_dimensiones_muestran_indice_mvp_y_raya_si_no_hay(tmp_path):
    caps = [
        {"dim": "A", "capacidad": "a", "nivel": 6, "alcance": "MVP", "evidencia": "e", "bloqueo": ""},
        {"dim": "A", "capacidad": "a2", "nivel": 0, "alcance": "R2", "evidencia": "", "bloqueo": ""},
        {"dim": "B", "capacidad": "b", "nivel": 3, "alcance": "R2", "evidencia": "e", "bloqueo": ""},
    ]
    m = _modelo(_montar(tmp_path, caps=caps))
    html = pp.render_html(m)
    sec = html.split("<h2 id='dimensiones'>")[1].split("<h2 ")[0]
    fila_a = next(f for f in sec.split("<tr>") if f.startswith("<td>A<"))
    fila_b = next(f for f in sec.split("<tr>") if f.startswith("<td>B<"))
    # horizonte de A = 50.0 %, MVP de A = 100.0 %: solo la columna MVP puede aportar «100.0 %»
    assert pp.porcentaje(m["dimensiones"]["dimensiones"]["A"]["mvp"]["indice"]) == "100.0 %" in fila_a
    assert "—" in fila_b and "MVP" in sec


def test_barra_no_pinta_100_si_el_texto_no_es_100(tmp_path):
    m = _modelo(_montar(tmp_path))
    m["global"]["mvp"]["indice"] = 0.99996
    html = pp.render_html(m)
    assert "99.9 %" in html
    assert "width:100.0%" not in html and "width:99.9%" in html
    m["global"]["mvp"]["indice"] = 1.0
    assert "width:100.0%" in pp.render_html(m)


def test_gate_con_fecha_futura_no_cuenta_como_al_dia(tmp_path):
    m = _con_gate(tmp_path, _gate_ok(fecha="2026-10-25T10:00:00"))
    g = m["calidad"]["gate"]
    assert g["fecha_futura"] is True and g["desactualizado"] is None
    assert "fecha futura" in pp.render_html(m)
    assert _con_gate(tmp_path, _gate_ok(), "ok")["calidad"]["gate"].get("fecha_futura") is not True


def test_zona_horaria_se_convierte_no_se_reetiqueta(tmp_path):
    from datetime import UTC

    ahora = datetime(2026, 10, 22, 12, 0, 0, tzinfo=UTC)
    # 08:00-05:00 = 13:00 UTC: una hora en el FUTURO. Reetiquetar daria 08:00 UTC (pasado, «al dia»).
    f = tmp_path / "g.json"
    f.write_text(json.dumps(_gate_ok(fecha="2026-10-22T08:00:00-05:00")), encoding="utf-8")
    g = pp.construir_modelo(_montar(tmp_path / "r"), ahora, registro_gate=f)["calidad"]["gate"]
    assert g["fecha_futura"] is True and g["desactualizado"] is None


def test_sin_decisiones_no_es_cero_pendientes(tmp_path):
    raiz = _montar(tmp_path)
    for f in (raiz / "milestones/m3-entry").glob("DECISION-REQUERIDA-*.md"):
        f.unlink()
    html = pp.render_html(_modelo(raiz))
    assert "sin decisiones registradas" in html and "0 pendientes" not in html
    assert "1 pendientes" in pp.render_html(_modelo(_montar(tmp_path / "c")))  # control


# ---------------------------------------------------------------- mutacion (panel-progreso.toml): supervivientes cerrados
def test_porcentaje_se_acota_a_0_100():
    """P5: el tope [0,100] es de la funcion publica, no solo de lo que hoy produce el indice."""
    assert pp.porcentaje(1.2) == "100.0 %"
    assert pp.porcentaje(-0.1) == "0.0 %"
    assert pp.porcentaje(0.5) == "50.0 %"  # control


def test_nivel_fuera_de_rango_lo_rechaza_la_validacion_de_esquema(tmp_path):
    """P9: el rechazo debe venir de la validacion («entero 0-6»), no de un fallo posterior casual."""
    mala = [{"dim": "A", "capacidad": "c", "nivel": 7, "alcance": "MVP", "evidencia": "e", "bloqueo": ""}]
    assert "entero 0-6" in _modelo(_montar(tmp_path, caps=mala))["global"]["error"]
    mala[0]["nivel"] = -1
    assert "entero 0-6" in _modelo(_montar(tmp_path / "n", caps=mala))["global"]["error"]


def test_escala_incompleta_da_error_de_escala(tmp_path):
    """P21: una escala que no define 0-6 es un error visible; la completa (control) no."""
    raiz = _montar(tmp_path)
    ruta = raiz / "milestones/mapa-maestro/capacidades.json"
    datos = json.loads(ruta.read_text(encoding="utf-8"))
    datos["escala"] = "0 inexistente · 1 concepto · 2 prototipo"
    ruta.write_text(json.dumps(datos), encoding="utf-8")
    assert "escala" in _modelo(raiz)["global"]["error"]
    assert "error" not in _modelo(_montar(tmp_path / "ok"))["global"]  # control


def test_pasos_del_gate_se_censuran_en_el_modelo(tmp_path):
    """P27: lo que el registro del gate trae en `pasos` tambien pasa por la censura."""
    pasos = {"pruebas": "FAIL token=abcdef999", "lint": "OK"}
    g = _con_gate(tmp_path, _gate_ok(pasos=pasos))["calidad"]["gate"]
    assert "abcdef999" not in json.dumps(g["pasos"]) and g["pasos"]["lint"] == "OK"


def test_censurar_no_trata_como_ip_un_numero_con_octeto_mayor_de_255():
    """C10: «300.1.1.999» no es una IP (es, p. ej., una version): se deja tal cual."""
    assert pp.censurar("version 300.1.1.999") == "version 300.1.1.999"
    assert pp.censurar("ip 10.1.1.250") == "ip .250"  # control


# ---------------------------------------------------------------- procedencia de la evidencia (2026-10-22)
def _cap(nombre, evidencia, nivel=3, alcance="MVP", dim="A"):
    return {"dim": dim, "capacidad": nombre, "nivel": nivel, "alcance": alcance, "evidencia": evidencia, "bloqueo": ""}


def _caps_proc(tmp_path, *caps):
    m = _modelo(_montar(tmp_path, caps=list(caps)))
    return m, {x["capacidad"]: x for x in m["capacidades"]["capacidades"]}


def _fila(html: str, nombre: str) -> str:
    return next(f for f in html.split("<tr>") if f"<td>{nombre}</td>" in f)


def test_evidencia_ejec_es_ejecucion_real_declarada(tmp_path):
    _, c = _caps_proc(tmp_path, _cap("real", "[EJEC] corrida del 2026-10-01"))
    x = c["real"]
    assert x["procedencia"] == "ejecucion_real_declarada" and x["derivada"] is True
    assert x["con_pruebas"] is False
    assert "no implica verificación física" in x["procedencia_etiqueta"]


def test_ejec_con_tests_sigue_siendo_real_y_marca_con_pruebas(tmp_path):
    _, c = _caps_proc(tmp_path, _cap("mixta", "[EJEC] 3 pruebas en tests/unit/test_x.py"))
    assert c["mixta"]["procedencia"] == "ejecucion_real_declarada" and c["mixta"]["con_pruebas"] is True


def test_solo_tests_o_mutaciones_es_pruebas_automatizadas_y_el_html_no_dice_real(tmp_path):
    m, c = _caps_proc(
        tmp_path,
        _cap("conTests", "tests/unit/test_a.py"),
        _cap("conMut", "mutaciones/b.toml"),
    )
    assert c["conTests"]["procedencia"] == c["conMut"]["procedencia"] == "pruebas_automatizadas"
    html = pp.render_html(m)
    for n in ("conTests", "conMut"):
        fila = _fila(html, n)
        assert "dobles/simulación" in fila and "real" not in fila.lower()


def test_evidencia_de_acta_o_documento_es_desconocida_y_no_se_infiere_real(tmp_path):
    _, c = _caps_proc(tmp_path, _cap("acta", "acta del CEO 2026-08-01, ADR-0014"), _cap("cod", "aura_skeleton/x.py"))
    assert c["acta"]["procedencia"] == c["cod"]["procedencia"] == "desconocida"
    assert c["acta"]["procedencia_etiqueta"] == "procedencia desconocida"


def test_evidencia_vacia_es_sin_evidencia_aunque_haya_otras(tmp_path):
    _, c = _caps_proc(tmp_path, _cap("vacia", "", 0), _cap("blancos", "   ", 0), _cap("otra", "[EJEC] x"))
    assert c["vacia"]["procedencia"] == c["blancos"]["procedencia"] == "sin_evidencia"
    assert c["vacia"]["con_pruebas"] is False and c["otra"]["procedencia"] != "sin_evidencia"


def test_nivel_5_sin_ejec_lleva_aviso_y_no_cambia_nivel_ni_indice(tmp_path):
    im = _indice_oficial()
    caps = [_cap("alta", "tests/unit/test_a.py", nivel=5), _cap("alta6", "acta", nivel=6), _cap("ok", "[EJEC] x", 5)]
    m, c = _caps_proc(tmp_path, *caps)
    assert (
        c["alta"]["aviso_procedencia"] == c["alta6"]["aviso_procedencia"] == "nivel alto sin ejecución real declarada"
    )
    assert c["ok"]["aviso_procedencia"] == ""  # control
    assert (c["alta"]["nivel"], c["alta6"]["nivel"]) == (5, 6)
    assert m["global"]["horizonte"]["indice"] == im.calcular(caps, None)["indice"]
    html = pp.render_html(m)
    assert "nivel alto sin ejecución real declarada" in _fila(html, "alta")
    assert "nivel alto sin ejecución real declarada" not in _fila(html, "ok")


def test_nivel_4_sin_ejec_no_lleva_aviso(tmp_path):
    _, c = _caps_proc(tmp_path, _cap("media", "x.py", nivel=4))
    assert c["media"]["aviso_procedencia"] == ""


def test_resumen_cuenta_por_procedencia_total_y_ambito(tmp_path):
    caps = [
        _cap("a", "[EJEC] x"),
        _cap("b", "[EJEC] y", alcance="R2"),
        _cap("c", "tests/t.py"),
        _cap("d", "acta", alcance="R2"),
        _cap("e", "", nivel=0, alcance="R2"),
        _cap("f", "acta", nivel=5),
    ]
    m, _ = _caps_proc(tmp_path, *caps)
    r = m["global"]["por_procedencia"]
    assert r["total"] == {
        "ejecucion_real_declarada": 2,
        "pruebas_automatizadas": 1,
        "desconocida": 2,
        "sin_evidencia": 1,
    }
    assert r["mvp"]["ejecucion_real_declarada"] == 1 and r["fuera_mvp"]["ejecucion_real_declarada"] == 1
    assert sum(r["mvp"].values()) + sum(r["fuera_mvp"].values()) == 6 == m["global"]["total"]
    assert r["nivel_alto_sin_ejecucion"] == 1 and r["derivada"] is True
    html = pp.render_html(m)
    assert "Procedencia de la evidencia" in html and "solo pruebas automatizadas" in html


def test_fuente_inexistente_da_bloque_error_tambien_en_procedencia(tmp_path):
    raiz = _montar(tmp_path)
    (raiz / "milestones/mapa-maestro/capacidades.json").unlink()
    m = _modelo(raiz)
    assert m["capacidades"]["error"] and m["global"]["error"] and "por_procedencia" not in m["global"]
    assert "Error:" in pp.render_html(m)


def test_fuente_desactualizada_avisa_en_el_html(tmp_path):
    m = _modelo(_montar(tmp_path), umbral_dias=1)
    assert m["capacidades"]["desactualizado"] is True
    assert "desactualizado" in pp.render_html(m)


def test_gate_en_otro_commit_avisa_y_no_presenta_pass_como_vigente(tmp_path, monkeypatch):
    monkeypatch.setattr(pp, "_git", lambda raiz, *a: "fff0000aaaabbbb" if a[:1] == ("rev-parse",) else None)
    m = _con_gate(tmp_path, _gate_ok())
    assert m["calidad"]["gate"]["vigente"] is False
    html = pp.render_html(m)
    assert "PASS en otro commit (sha abc1234); no corresponde al HEAD actual" in html
    assert "<b>PASS</b>" not in html


def test_gate_en_el_mismo_commit_si_es_vigente(tmp_path, monkeypatch):
    monkeypatch.setattr(pp, "_git", lambda raiz, *a: "abc1234ffff0000" if a[:1] == ("rev-parse",) else None)
    m = _con_gate(tmp_path, _gate_ok())
    assert m["calidad"]["gate"]["vigente"] is True
    html = pp.render_html(m)
    assert "<b>PASS</b>" in html and "otro commit" not in html


def test_gate_con_sha_desconocido_dice_no_comprobado_nunca_coincide(tmp_path, monkeypatch):
    monkeypatch.setattr(pp, "_git", lambda raiz, *a: "abc1234ffff" if a[:1] == ("rev-parse",) else None)
    m = _con_gate(tmp_path, _gate_ok(sha="desconocido"))
    g = m["calidad"]["gate"]
    assert g["sha_vs_head"] == "no comprobado" and g["vigente"] is False
    html = pp.render_html(m)
    assert "no comprobado contra HEAD" in html
    assert "sha coincide con HEAD" not in html and "<b>PASS</b>" not in html


def test_gate_con_head_no_comprobable_dice_no_comprobado(tmp_path, monkeypatch):
    monkeypatch.setattr(pp, "_git", lambda raiz, *a: None)
    html = pp.render_html(_con_gate(tmp_path, _gate_ok()))
    assert "no comprobado contra HEAD" in html and "sha coincide con HEAD" not in html


# ---------------------------------------------------------------- privacidad de extremo a extremo
SECRETOS = (
    "AA:BB:CC:DD:EE:01",
    "12345678-1234-1234-1234-123456789abc",
    "SERIE9ZZ8YY7XX6WW5",
    "192.168.77.201",
    "rtsp://usuarioX:claveX@",
    "usuarioX:claveX",
    "Bearer tokenZ99",
    "tokenZ99",
    "Casa 1234",
)
FUGA = (
    "mac AA:BB:CC:DD:EE:01 uuid 12345678-1234-1234-1234-123456789abc serie SERIE9ZZ8YY7XX6WW5 "
    "ip 192.168.77.201 rtsp://usuarioX:claveX@h/s Bearer tokenZ99 Contraseña Wi-Fi: Casa 1234 "
    '"><img onerror=1>'
)


def _sin_fugas(texto: str, donde: str) -> None:
    for s in SECRETOS:
        assert s not in texto, f"{donde}: fuga de {s!r}"


def test_privacidad_extremo_a_extremo_ninguna_fuente_filtra_en_html_ni_json(tmp_path):
    caps = [
        {
            "dim": f"A {FUGA}",
            "capacidad": f"cap {FUGA}",
            "nivel": 5,
            "alcance": "MVP",
            "evidencia": f"[EJEC] {FUGA}",
            "bloqueo": f"Decisión {FUGA}",
        }
    ]
    mapa = (
        "## 7. Inventario\n\n| Equipo | Estado | Bloqueo |\n|---|---|---|\n"
        f"| {FUGA.replace('|', '/')} | {FUGA.replace('|', '/')} | {FUGA.replace('|', '/')} |\n"
    )
    raiz = _montar(tmp_path, caps=caps, mapa=mapa)
    datos = json.loads((raiz / "milestones/mapa-maestro/capacidades.json").read_text())
    datos["escala"] = ESCALA
    datos["actualizado"] = f"2026-10-20 {FUGA}"
    (raiz / "milestones/mapa-maestro/capacidades.json").write_text(json.dumps(datos), encoding="utf-8")
    (raiz / f"milestones/m3-entry/DECISION-REQUERIDA-{FUGA[:0]}C.md").write_text(
        f"# C\n**Estado:** PENDIENTE {FUGA}\n", encoding="utf-8"
    )
    (raiz / "CHECKPOINT-CONTINUIDAD.md").write_text(f"## 2026-10-22 {FUGA}\n", encoding="utf-8")
    gate = _gate_ok(sha=FUGA, pasos={f"paso {FUGA}": f"OK {FUGA}"}, pytest={f"k {FUGA}": 1})
    f = tmp_path / "gate.json"
    f.write_text(json.dumps(gate), encoding="utf-8")
    m = _modelo(raiz, registro_gate=f)
    html = pp.render_html(m)
    volcado = json.dumps(m, ensure_ascii=False, default=str)
    _sin_fugas(html, "html")
    _sin_fugas(volcado, "json")
    assert '"><img' not in html and "<img" not in html
    # control: las fuentes SÍ se leyeron (no se pasó por un bloque de error vacío)
    assert not m["calidad"]["gate"].get("error") and not m["ecosistema"].get("error")
    assert m["capacidades"]["capacidades"] and m["bloqueos"]["total"] >= 1


def test_privacidad_errores_de_la_fuente_tambien_se_censuran(tmp_path):
    f = tmp_path / "gate.json"
    f.write_text(json.dumps(_gate_ok(resultado=FUGA)), encoding="utf-8")
    g = _modelo(_montar(tmp_path / "r"), registro_gate=f)["calidad"]["gate"]
    assert g.get("error")
    _sin_fugas(json.dumps(g), "error del gate")
