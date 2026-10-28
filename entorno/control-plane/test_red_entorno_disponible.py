"""RED de DR-A — septima fuente: **observacion del entorno de ejecucion**.

El acta aprueba OBSERVAR, nada mas. Estas pruebas fijan las dos mitades de esa frontera:

1. que AURA **pueda ver** una capacidad que realmente esta ahi, con evidencia que se puede ir a mirar;
2. que **no pueda hacer nada** con ella: ni ejecutar, ni escribir, ni concederse autoridad, ni
   convertir «no pude observar» en «no existe».

La segunda mitad es la que importa: una fuente que observa el sistema operativo es la que mas cerca
esta de poder tocarlo, asi que las garantias se fijan por AST sobre el fuente, no por confianza.
"""
from __future__ import annotations

import ast
import hashlib
import inspect
import pathlib

import descubrimiento as des
import entorno_disponible as ent
import orquestador as orq
import planificador as plan
import pytest
import review as rv


# ---------------------------------------------------------------- utilidades del entorno simulado

def _net_tcp(tmp_path, puertos_escuchando=(11434,), *, basura=False):
    """Un `/proc/net/tcp` creible. `st=0A` es LISTEN; el resto de estados no cuentan."""
    cab = ("  sl  local_address rem_address   st tx_queue rx_queue tr tm->when retrnsmt"
           "   uid  timeout inode\n")
    lineas = [cab]
    for i, p in enumerate(puertos_escuchando):
        lineas.append(f"{i:4d}: 0100007F:{p:04X} 00000000:0000 0A 00000000:00000000 "
                      f"00:00000000 00000000  1000        0 12345 1\n")
    # Una conexion establecida (st=01) al mismo puerto NO es un listener.
    lineas.append("  99: 0100007F:1F90 0100007F:2CAA 01 00000000:00000000 "
                  "00:00000000 00000000  1000        0 99999 1\n")
    if basura:
        lineas.append("esto no es una linea de /proc/net/tcp\n")
    f = tmp_path / "net_tcp"
    f.write_text("".join(lineas))
    return f


def _proc(tmp_path, procesos=("ollama",)):
    """Un `/proc` con directorios numericos y su `comm`, como el real."""
    d = tmp_path / "proc"
    d.mkdir(exist_ok=True)
    for i, nombre in enumerate(procesos, start=100):
        p = d / str(i)
        p.mkdir(exist_ok=True)
        (p / "comm").write_text(nombre + "\n")
    (d / "noes_un_pid").mkdir(exist_ok=True)   # /proc tiene mucho que no es un proceso
    return d


def _manifests(tmp_path, modelos=(("qwen2.5", "0.5b"),)):
    """El arbol de manifests de un proveedor local: `<familia>/<tag>` = un modelo disponible."""
    d = tmp_path / "manifests"
    for familia, tag in modelos:
        (d / familia).mkdir(parents=True, exist_ok=True)
        (d / familia / tag).write_text('{"schemaVersion":2}')
    d.mkdir(parents=True, exist_ok=True)
    return d


def _observando(tmp_path, **kw):
    """Las tres rutas que la fuente observa, con lo que haga falta por defecto.

    Los defaults se construyen **solo si no se paso el valor**: los tres escriben en rutas fijas de
    `tmp_path`, asi que evaluarlos siempre sobrescribia el escenario del test con el caso favorable
    —y las pruebas de ausencia pasaban en verde viendo un entorno completo."""
    if "proc" not in kw:
        kw["proc"] = _proc(tmp_path)
    if "net_tcp" not in kw:
        kw["net_tcp"] = _net_tcp(tmp_path)
    if "manifests" not in kw:
        kw["manifests"] = _manifests(tmp_path)
    return kw


def _huella(raiz: pathlib.Path) -> str:
    """Hash de todo el arbol: contenido y nombres. Si la fuente escribe algo, cambia."""
    h = hashlib.sha256()
    for f in sorted(raiz.rglob("*")):
        h.update(str(f.relative_to(raiz)).encode())
        if f.is_file():
            h.update(f.read_bytes())
    return h.hexdigest()


# ---------------------------------------------------------------------------- 1 · ve lo que hay

def test_detecta_una_capacidad_disponible(tmp_path):
    """Proceso vivo + puerto escuchando + un modelo en disco = capacidad DISPONIBLE."""
    obs = ent.observar(ent.RAZONAMIENTO_LOCAL, **_observando(tmp_path))
    assert obs["estado"] == ent.DISPONIBLE
    assert obs["senales"]["proceso"] is True
    assert obs["senales"]["puerto"] is True
    assert "qwen2.5:0.5b" in obs["senales"]["modelos"]


def test_la_evidencia_se_puede_ir_a_mirar(tmp_path):
    """La procedencia es un fichero real, no una afirmacion: `fuente_verificable` lo exige."""
    ops = ent.entorno(tmp_path, tmp_path, **_observando(tmp_path))
    assert len(ops) == 1
    assert des.fuente_verificable(ops[0].fuente)
    assert pathlib.Path(ops[0].fuente.rsplit(":", 1)[0]).is_file()


# --------------------------------------------------------- 2 · el servicio no esta (AUSENTE ≠ ?)

def test_sin_puerto_escuchando_la_capacidad_esta_ausente(tmp_path):
    """Observado y no esta: AUSENTE. Es una afirmacion con evidencia, no un desconocimiento."""
    obs = ent.observar(ent.RAZONAMIENTO_LOCAL,
                       **_observando(tmp_path, net_tcp=_net_tcp(tmp_path, puertos_escuchando=())))
    assert obs["estado"] == ent.AUSENTE


def test_sin_proceso_la_capacidad_esta_ausente(tmp_path):
    obs = ent.observar(ent.RAZONAMIENTO_LOCAL,
                       **_observando(tmp_path, proc=_proc(tmp_path, procesos=("bash", "python3"))))
    assert obs["estado"] == ent.AUSENTE


def test_servidor_sin_modelos_no_es_capacidad(tmp_path):
    """Hay con que razonar, pero nada que razonar: la capacidad no esta completa."""
    obs = ent.observar(ent.RAZONAMIENTO_LOCAL,
                       **_observando(tmp_path, manifests=_manifests(tmp_path, modelos=())))
    assert obs["estado"] == ent.AUSENTE


def test_una_conexion_no_es_un_listener(tmp_path):
    """`st=01` (ESTABLISHED) hacia el puerto no prueba que alguien escuche en el."""
    obs = ent.observar(ent.RAZONAMIENTO_LOCAL,
                       **_observando(tmp_path, net_tcp=_net_tcp(tmp_path, puertos_escuchando=())))
    assert obs["senales"]["puerto"] is False


def test_ausente_no_eleva_nada(tmp_path):
    ops = ent.entorno(tmp_path, tmp_path,
                      **_observando(tmp_path, net_tcp=_net_tcp(tmp_path, puertos_escuchando=())))
    assert ops == []


# ------------------------------------------- 3 y 4 · no observable ≠ ausente (el corazon de DR-A)

def test_sin_permisos_es_desconocido_no_ausente(tmp_path):
    """Lo que no se pudo leer es DESCONOCIDO. Convertirlo en AUSENTE seria inventar una ausencia."""
    f = _net_tcp(tmp_path)
    f.chmod(0o000)
    try:
        obs = ent.observar(ent.RAZONAMIENTO_LOCAL, **_observando(tmp_path, net_tcp=f))
        assert obs["estado"] == ent.DESCONOCIDO
        assert obs["senales"]["puerto"] is None      # None = no se pudo observar
    finally:
        f.chmod(0o644)


def test_fichero_ausente_es_desconocido_no_ausente(tmp_path):
    obs = ent.observar(ent.RAZONAMIENTO_LOCAL,
                       **_observando(tmp_path, net_tcp=tmp_path / "no_existe"))
    assert obs["estado"] == ent.DESCONOCIDO


def test_proc_ilegible_es_desconocido(tmp_path):
    obs = ent.observar(ent.RAZONAMIENTO_LOCAL, **_observando(tmp_path, proc=tmp_path / "no_hay"))
    assert obs["estado"] == ent.DESCONOCIDO


def test_datos_incompletos_no_rompen_la_observacion(tmp_path):
    """Una linea corrupta no invalida el resto: se ignora, pero no se finge lo que no se leyo."""
    obs = ent.observar(ent.RAZONAMIENTO_LOCAL,
                       **_observando(tmp_path, net_tcp=_net_tcp(tmp_path, basura=True)))
    assert obs["estado"] == ent.DISPONIBLE


def test_desconocido_nunca_se_eleva_como_capacidad(tmp_path):
    """**Fail-closed.** Sin observacion completa no hay conocimiento que elevar."""
    ops = ent.entorno(tmp_path, tmp_path, **_observando(tmp_path, proc=tmp_path / "no_hay"))
    assert ops == []


# ------------------------------------------------------- 6 y 7 · observa, no actua ni escribe

_PROHIBIDO_EJECUTAR = ("subprocess", "Popen", "system", "run", "call", "check_output",
                       "socket", "connect", "urlopen", "Request", "spawn", "fork", "exec")
_PROHIBIDO_ESCRIBIR = ("write_text", "write_bytes", "mkdir", "touch", "unlink", "rmdir",
                       "remove", "chmod", "rename", "replace", "registrar_evento", "transicion",
                       "guardar", "autorizar", "habilitar", "ejecutar", "open")


def test_la_fuente_no_puede_ejecutar_nada_por_ast():
    """No basta con que hoy no ejecute: no debe poder. Se comprueba sobre el fuente."""
    arbol = ast.parse(pathlib.Path(inspect.getfile(ent)).read_text())
    nombres = {n.attr for n in ast.walk(arbol) if isinstance(n, ast.Attribute)}
    nombres |= {n.id for n in ast.walk(arbol) if isinstance(n, ast.Name)}
    for mod in ast.walk(arbol):
        if isinstance(mod, ast.Import):
            nombres |= {a.name.split(".")[0] for a in mod.names}
        if isinstance(mod, ast.ImportFrom) and mod.module:
            nombres.add(mod.module.split(".")[0])
    assert not (nombres & set(_PROHIBIDO_EJECUTAR)), nombres & set(_PROHIBIDO_EJECUTAR)


def test_la_fuente_no_puede_escribir_por_ast():
    arbol = ast.parse(pathlib.Path(inspect.getfile(ent)).read_text())
    nombres = {n.attr for n in ast.walk(arbol) if isinstance(n, ast.Attribute)}
    nombres |= {n.id for n in ast.walk(arbol) if isinstance(n, ast.Name)}
    assert not (nombres & set(_PROHIBIDO_ESCRIBIR)), nombres & set(_PROHIBIDO_ESCRIBIR)


def test_observar_no_modifica_nada_del_entorno(tmp_path):
    """Garantia medida, no declarada: el arbol observado tiene la misma huella antes y despues."""
    obs_kw = _observando(tmp_path)
    antes = _huella(tmp_path)
    ent.entorno(tmp_path, tmp_path, **obs_kw)
    assert _huella(tmp_path) == antes


# --------------------------------------------------- 8 y 9 · conocimiento, nunca autorizacion

def test_la_observacion_nunca_es_ejecutable(tmp_path):
    """`DECISION_REQUIRED` es el techo. El planificador no puede convertirla en tarea."""
    ops = ent.entorno(tmp_path, tmp_path, **_observando(tmp_path))
    assert ops[0].estado == des.DECISION_REQUIRED
    assert plan.a_tarea(ops[0]) is None


def test_la_fuente_nunca_genera_oportunidad_real(tmp_path):
    """Ni con el entorno mas favorable: no existe camino a OPORTUNIDAD_REAL."""
    for kw in ({}, {"manifests": _manifests(tmp_path, modelos=(("qwen2.5", "0.5b"),
                                                               ("llama3.2", "1b")))}):
        for op in ent.entorno(tmp_path, tmp_path, **_observando(tmp_path, **kw)):
            assert op.estado != des.OPORTUNIDAD_REAL
    # Por AST y no por `in fuente`: la cadena aparece en el docstring **explicando** que no puede
    # producirla, y prohibir la palabra impediria documentar la garantia. Lo que no debe existir es
    # el simbolo como codigo — `des.OPORTUNIDAD_REAL` o el literal exacto—, y eso si se detecta.
    arbol = ast.parse(pathlib.Path(inspect.getfile(ent)).read_text())
    usados = {n.attr for n in ast.walk(arbol) if isinstance(n, ast.Attribute)}
    usados |= {n.id for n in ast.walk(arbol) if isinstance(n, ast.Name)}
    usados |= {n.value for n in ast.walk(arbol)
               if isinstance(n, ast.Constant) and isinstance(n.value, str)}
    assert "OPORTUNIDAD_REAL" not in usados


def test_no_amplia_la_autoridad(tmp_path):
    """La accion que nombra es HUMAN, y no entra en AUTO ni en lo maximo delegable."""
    ops = ent.entorno(tmp_path, tmp_path, **_observando(tmp_path))
    assert orq.nivel_de(ops[0].accion) == "HUMAN"
    assert ops[0].accion not in orq.acciones_de_nivel("AUTO")
    assert ops[0].accion not in rv.TODO_LO_DELEGABLE
    assert ops[0].autoridad == "CEO"


def test_no_concluye_que_puede_conectarlo(tmp_path):
    """El caso objetivo del acta: puede decir «esta ahi», nunca «por tanto lo conecto»."""
    ops = ent.entorno(tmp_path, tmp_path, **_observando(tmp_path))
    justificacion = ops[0].justificacion.lower()
    assert "qwen2.5:0.5b" in str(ops[0].detalle)
    for verbo in ("conectar", "conecto", "integrar", "integro", "habilitar", "activar"):
        assert verbo not in justificacion, f"la fuente propone {verbo!r}: eso es una decision"


# ------------------------------------------------- 10 y 11 · integracion y anti-duplicacion

def test_la_fuente_esta_cableada_en_FUENTES():
    """ALERTA-005: una capacidad que no esta cableada no existe, por buena que sea."""
    assert des.FUENTES.get("capacidades_del_entorno") is ent.entorno
    # Eran 7 hasta que el acta del CEO (2026-09-07) anadio la octava, `capacidades_declaradas`, que
    # lee el plan de formacion. El numero se sube aqui **porque hay un acta**, no para que la prueba
    # pase: su trabajo es avisar de que el catalogo cambio, y aviso.
    assert len(des.FUENTES) == 8


def test_convive_con_las_seis_fuentes_existentes():
    """Las seis anteriores siguen ahi, con su nombre y su funcion."""
    for previa in ("codigo_muerto", "invocables_sin_clasificar", "eventos_sin_puerta",
                   "decisiones_pendientes", "bloqueos_registrados", "estancamiento"):
        assert previa in des.FUENTES


def test_misma_capacidad_mismo_id(tmp_path):
    """El id sale de la capacidad, no del momento: el antiduplicados la reconoce vuelta tras vuelta."""
    kw = _observando(tmp_path)
    assert ent.entorno(tmp_path, tmp_path, **kw)[0].id == ent.entorno(tmp_path, tmp_path, **kw)[0].id


def test_el_id_no_depende_del_catalogo_de_modelos(tmp_path):
    """La identidad es **la capacidad**, no su inventario.

    Si el id dependiera de los modelos, descargar uno nuevo cambiaria el id de una capacidad que es
    la misma: el antiduplicados dejaria de reconocerla y AURA volveria a elevar lo ya elevado. Es el
    mismo defecto que `_id_de` documenta —perder el rastro en silencio— visto desde el otro lado."""
    uno, dos = tmp_path / "uno", tmp_path / "dos"
    uno.mkdir()
    dos.mkdir()
    con_un_modelo = ent.entorno(uno, uno, **_observando(uno))[0]
    con_dos_modelos = ent.entorno(dos, dos, **_observando(
        dos, manifests=_manifests(dos, modelos=(("qwen2.5", "0.5b"), ("llama3.2", "1b")))))[0]
    assert con_un_modelo.detalle["modelos"] != con_dos_modelos.detalle["modelos"]
    assert con_un_modelo.id == con_dos_modelos.id


def test_a_lo_sumo_una_por_capacidad(tmp_path):
    """Dos modelos no son dos capacidades: la capacidad es «razonar en local», y es una."""
    kw = _observando(tmp_path, manifests=_manifests(
        tmp_path, modelos=(("qwen2.5", "0.5b"), ("qwen2.5", "3b"), ("llama3.2", "1b"))))
    assert len(ent.entorno(tmp_path, tmp_path, **kw)) <= len(ent.CAPACIDADES)


def test_una_fuente_rota_no_tumba_el_descubrimiento(tmp_path, monkeypatch):
    """`descubrir()` aisla cada fuente: si esta falla, las otras seis siguen."""
    def _explota(*_a, **_k):
        raise RuntimeError("observacion imposible")
    monkeypatch.setitem(des.FUENTES, "capacidades_del_entorno", _explota)
    with pytest.raises(RuntimeError):
        _explota()
    assert "capacidades_del_entorno" in des.FUENTES
