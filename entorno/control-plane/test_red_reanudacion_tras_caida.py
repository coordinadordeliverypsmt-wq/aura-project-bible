"""Reanudacion tras caida (DP-RECUPERACION-TRAS-CAIDAS, 2026-10-26).

Defecto medido `[EJEC]`: SIGKILL a mitad de la verificacion -> la tarea queda `tarea_planificada` sin `cambio_aplicado`
y `elegible` la trata PARA SIEMPRE como «puede estar corriendo»: nunca se reintenta ni se informa, y la cola dice
«agotada» con el trabajo sin hacer (declarado != real, INV-9). Contrato: la constancia de planificacion lleva la
IDENTIDAD del ejecutor (pid + starttime + arranque); una tarea sin resultado cuyo ejecutor ya no existe esta
INTERRUMPIDA, consume un intento y vuelve a ser elegible dentro del presupuesto; agotado, queda AGOTADA: observable
por `estado_de` y con el evento `presupuesto_de_tarea_agotado`, que el motor emite tambien para las agotadas por
interrupcion (DP §10).
"""

import os
import pathlib
import signal
import subprocess
import sys
import textwrap

import pytest

import control_plane as cp
import planificador as pl

PLANO = pathlib.Path(__file__).resolve().parent


def _tarea(id_tarea="TA-1"):
    return {"id": id_tarea, "origen": "OP-x", "accion": "eliminar_codigo_muerto", "fichero": "m.py", "riesgo": "bajo"}


def _planificada_por(d, ejecutor, id_tarea="TA-1"):
    """Constancia como la dejaria OTRO proceso (o una version anterior, si `ejecutor` es None)."""
    datos = {k: v for k, v in _tarea(id_tarea).items()}
    if ejecutor is not None:
        datos["ejecutor"] = ejecutor
    cp.registrar_evento(d, "tarea_planificada", datos)


def _resultado(d, *, revertido):
    cp.registrar_evento(d, "cambio_aplicado", {"id": "P-1", "fichero": "m.py", "simbolo": "_x", "efecto_verificado": True,
                                               "verificacion_sana": not revertido, "revertido": revertido,
                                               "autoridad": "orquestador"})


def _pid_muerto() -> int:
    p = subprocess.Popen([sys.executable, "-c", "pass"])
    p.wait()
    return p.pid


# ------------------------------------------------------------------------- el contrato --

def test_la_constancia_de_planificacion_lleva_la_identidad_del_ejecutor(tmp_path):
    pl.registrar_planificada(tmp_path, _tarea())
    datos = [e for e in cp.leer_eventos(tmp_path) if e["tipo"] == "tarea_planificada"][-1]["datos"]
    assert datos["ejecutor"]["pid"] == os.getpid()
    assert datos["ejecutor"]["inicio"] and datos["ejecutor"]["arranque"]


def test_terminacion_normal_completa_y_no_se_reintenta(tmp_path):
    pl.registrar_planificada(tmp_path, _tarea())
    _resultado(tmp_path, revertido=False)
    assert (pl.estado_de(tmp_path, "TA-1"), pl.elegible(tmp_path, "TA-1")) == ("completada", False)


def test_fallo_recuperable_es_reintentable_dentro_del_presupuesto(tmp_path):
    pl.registrar_planificada(tmp_path, _tarea())
    _resultado(tmp_path, revertido=True)
    assert (pl.estado_de(tmp_path, "TA-1"), pl.elegible(tmp_path, "TA-1")) == ("revertida_reintentable", True)


def test_con_el_ejecutor_VIVO_esta_en_curso_y_no_se_duplica(tmp_path):
    pl.registrar_planificada(tmp_path, _tarea())  # este proceso, vivo
    assert (pl.estado_de(tmp_path, "TA-1"), pl.elegible(tmp_path, "TA-1")) == ("en_curso", False)


def test_con_el_ejecutor_MUERTO_esta_interrumpida_y_vuelve_a_ser_elegible(tmp_path):
    _planificada_por(tmp_path, {"pid": _pid_muerto(), "inicio": "1", "arranque": pl._arranque()})
    assert (pl.estado_de(tmp_path, "TA-1"), pl.elegible(tmp_path, "TA-1")) == ("interrumpida_reintentable", True)


def test_un_PID_REUTILIZADO_no_pasa_por_el_ejecutor_original(tmp_path):
    """Mismo pid que un proceso vivo (este), otro starttime: es otro proceso; el original murio."""
    _planificada_por(tmp_path, {"pid": os.getpid(), "inicio": "0", "arranque": pl._arranque()})
    assert pl.estado_de(tmp_path, "TA-1") == "interrumpida_reintentable"


def test_tras_un_REINICIO_de_la_maquina_ningun_ejecutor_anterior_sigue_vivo(tmp_path):
    yo = pl._identidad_del_ejecutor()
    _planificada_por(tmp_path, {**yo, "arranque": "otro-arranque"})
    assert pl.estado_de(tmp_path, "TA-1") == "interrumpida_reintentable"


def test_un_evento_HISTORICO_sin_ejecutor_sigue_siendo_conservador(tmp_path):
    """Compatibilidad: el log real anterior no tiene `ejecutor`. No se puede saber si murio: no se reofrece."""
    _planificada_por(tmp_path, None)
    assert (pl.estado_de(tmp_path, "TA-1"), pl.elegible(tmp_path, "TA-1")) == ("sin_resultado_historico", False)


def test_dos_interrupciones_AGOTAN_y_queda_explicito(tmp_path):
    for _ in range(pl.TOPE_DE_REINTENTOS):
        _planificada_por(tmp_path, {"pid": _pid_muerto(), "inicio": "1", "arranque": pl._arranque()})
    assert (pl.estado_de(tmp_path, "TA-1"), pl.elegible(tmp_path, "TA-1")) == ("agotada", False)


def test_dos_supervisores_no_pueden_planificar_a_la_vez_la_misma_tarea(tmp_path):
    """Comprobar-y-anadir bajo el cerrojo del log: la segunda constancia se rechaza si la primera sigue viva."""
    pl.registrar_planificada(tmp_path, _tarea())
    with pytest.raises(pl.TareaNoElegible):
        pl.registrar_planificada(tmp_path, _tarea())
    assert sum(1 for e in cp.leer_eventos(tmp_path) if e["tipo"] == "tarea_planificada") == 1


def test_una_tarea_interrumpida_se_puede_volver_a_planificar_y_la_nueva_constancia_es_la_viva(tmp_path):
    _planificada_por(tmp_path, {"pid": _pid_muerto(), "inicio": "1", "arranque": pl._arranque()})
    pl.registrar_planificada(tmp_path, _tarea())
    assert (pl.intentos_de(tmp_path, "TA-1"), pl.estado_de(tmp_path, "TA-1")) == (2, "en_curso")


# -------------------------------------------------------- extremo a extremo con SIGKILL real --

_GUION = textwrap.dedent('''
    import os, pathlib, signal, sys
    import aislamiento as ais, motor_autonomia as motor, orquestador, review, verificador as vf
    # Mismo criterio que las 33 pruebas que ya lo hacen: el sandbox es tmp, no el arbol vivo. Sin esto, bajo el
    # arnes de mutacion el verificador lanza `ArnesEnCurso` y la verificacion (y el SIGKILL) nunca ocurren.
    orquestador.mutacion_en_curso = lambda: False
    base, fase = pathlib.Path(sys.argv[1]), sys.argv[2]
    zona = base / "entorno" / "control-plane"
    def verificar(raiz):
        if fase == "matar":
            os.kill(os.getpid(), signal.SIGKILL)
        prueba = pathlib.Path(raiz) / "entorno" / "control-plane" / "test_modulo_inocuo.py"
        return vf.ejecutar_pruebas([str(prueba)], prueba.parent, confinar=ais.preparar_estricto(raiz)).sano
    if fase == "matar":
        zona.mkdir(parents=True)
        (zona / "modulo_inocuo.py").write_text("def _muerta():\\n    return 1\\n\\n\\ndef viva():\\n    return 2\\n")
        (zona / "test_modulo_inocuo.py").write_text("from modulo_inocuo import viva\\n\\n\\ndef test_viva():\\n    assert viva() == 2\\n")
        review.habilitar(base, por="ceo", acta="SANDBOX de prueba", alcance=("eliminar_codigo_muerto",))
    i = motor.trabajar(base, zona, verificacion=verificar, max_tareas=3)
    print(i["ejecutadas"], i["motivo_de_parada"])
''')


@pytest.mark.skipif(not __import__("aislamiento").estricto_disponible(), reason="sin confinamiento estricto")
def test_E2E_SIGKILL_en_la_verificacion_se_recupera_sin_duplicar_y_la_siguiente_no_repite(tmp_path):
    guion = tmp_path / "guion.py"
    guion.write_text(_GUION)
    base = tmp_path / "sandbox"
    (tmp_path / "tmp").mkdir()  # el SIGKILL impide a autoconstruccion borrar su copia: que no caiga en el /tmp real
    entorno = {**os.environ, "PYTHONPATH": str(PLANO), "AURA_AUTOCONSTRUCCION_ESTADO": str(tmp_path / "estado"),
               "TMPDIR": str(tmp_path / "tmp")}
    matar = subprocess.run([sys.executable, str(guion), str(base), "matar"], env=entorno, capture_output=True, text=True,
                           timeout=300)
    assert matar.returncode == -signal.SIGKILL, matar.stderr  # control: interrupcion REAL durante la verificacion
    # la copia que el SIGKILL deja sin borrar queda en el tmp de ESTA prueba, no en el /tmp del sistema
    assert list((tmp_path / "tmp").glob("aura-candidato-*")), "el candidato huerfano debe quedar contenido"
    zona = base / "entorno" / "control-plane"
    assert "_muerta" in (zona / "modulo_inocuo.py").read_text(), "el proyecto no puede quedar a medias"
    assert pl.estado_de(base, [e for e in cp.leer_eventos(base) if e["tipo"] == "tarea_planificada"][0]["datos"]["id"]) \
        == "interrumpida_reintentable"

    reanudar = subprocess.run([sys.executable, str(guion), str(base), "seguir"], env=entorno, capture_output=True,
                              text=True, timeout=300)
    assert reanudar.stdout.split()[:1] == ["1"], reanudar.stdout + reanudar.stderr  # la reanuda y la completa
    assert "_muerta" not in (zona / "modulo_inocuo.py").read_text()

    siguiente = subprocess.run([sys.executable, str(guion), str(base), "seguir"], env=entorno, capture_output=True,
                               text=True, timeout=300)
    assert siguiente.stdout.split()[:1] == ["0"], siguiente.stdout  # no repite lo completado
    eventos = cp.leer_eventos(base)
    promovidos = [e for e in eventos if e["tipo"] == "cambio_aplicado" and e["datos"].get("promovido")]
    assert len(promovidos) == 1, "exactamente UNA promocion: sin duplicados"
    assert cp.verificar_integridad_log(base)["integro"] is True


# ------------------------------------------ revision independiente (code-reviewer, 2026-10-26) --

@pytest.mark.parametrize("tipo,datos,estado", [
    ("decision_requerida", {"origen": "OP-x", "motivo": "zona prohibida"}, "elevada"),
    ("revision_sin_revisor_capaz", {"accion": "eliminar_codigo_muerto", "propuesto_por": "aura"}, "esperando_revisor"),
    ("veredicto_emitido", {"revisor": "r", "propuesto_por": "aura", "objeciones": ["x"], "cumple": False}, "objetada"),
])
def test_M1_un_cierre_SIN_resultado_no_se_confunde_con_una_interrupcion(tmp_path, tipo, datos, estado):
    """El motor eleva, espera revisor o recibe objeciones SIN escribir `cambio_aplicado`. Aunque su supervisor ya
    no viva, eso no es una interrupcion: la tarea NO se reofrece (como antes del contrato)."""
    _planificada_por(tmp_path, {"pid": _pid_muerto(), "inicio": "1", "arranque": pl._arranque()})
    cp.registrar_evento(tmp_path, tipo, {"id": "TA-1", **datos})
    assert (pl.estado_de(tmp_path, "TA-1"), pl.elegible(tmp_path, "TA-1")) == (estado, False)


def test_M2_no_poder_LEER_proc_no_es_lo_mismo_que_un_proceso_muerto(tmp_path, monkeypatch):
    """`hidepid` u otro espacio de nombres: PermissionError. Ante la duda, vivo: nunca se duplica."""
    real = pathlib.Path.read_text

    def sin_permiso(self, *a, **k):
        if str(self).startswith("/proc/") and str(self).endswith("/stat") and str(self) != "/proc/self/stat":
            raise PermissionError("hidepid")
        return real(self, *a, **k)

    _planificada_por(tmp_path, {"pid": 1, "inicio": "1", "arranque": pl._arranque()})
    monkeypatch.setattr(pathlib.Path, "read_text", sin_permiso)
    assert (pl.estado_de(tmp_path, "TA-1"), pl.elegible(tmp_path, "TA-1")) == ("en_curso", False)


def _proc_stat_que(falla_con, tmp_path, monkeypatch):
    real = pathlib.Path.read_text

    def lector(self, *a, **k):
        if str(self).startswith("/proc/") and str(self).endswith("/stat") and str(self) != "/proc/self/stat":
            if isinstance(falla_con, str):
                return falla_con
            raise falla_con
        return real(self, *a, **k)

    monkeypatch.setattr(pathlib.Path, "read_text", lector)


def test_M2_con_hidepid_2_un_ejecutor_VIVO_invisible_en_proc_no_se_da_por_muerto(tmp_path, monkeypatch):
    """`hidepid=2`: el pid ajeno NO aparece en /proc (ENOENT) aunque viva. Se contrasta con `kill(pid, 0)`."""
    _planificada_por(tmp_path, {"pid": os.getpid(), "inicio": pl._inicio_de(os.getpid()), "arranque": pl._arranque()})
    _proc_stat_que(FileNotFoundError("hidepid=2"), tmp_path, monkeypatch)
    assert (pl.estado_de(tmp_path, "TA-1"), pl.elegible(tmp_path, "TA-1")) == ("en_curso", False)


def test_M2_control_con_ENOENT_un_ejecutor_que_de_verdad_murio_sigue_interrumpido(tmp_path, monkeypatch):
    _planificada_por(tmp_path, {"pid": _pid_muerto(), "inicio": "1", "arranque": pl._arranque()})
    _proc_stat_que(FileNotFoundError("no existe"), tmp_path, monkeypatch)
    assert (pl.estado_de(tmp_path, "TA-1"), pl.elegible(tmp_path, "TA-1")) == ("interrumpida_reintentable", True)


def test_B2_un_stat_MALFORMADO_es_duda_y_no_muerte(tmp_path, monkeypatch):
    _planificada_por(tmp_path, {"pid": 1, "inicio": "1", "arranque": pl._arranque()})
    _proc_stat_que("1 (x) R", tmp_path, monkeypatch)  # sin el campo 22: IndexError
    assert (pl.estado_de(tmp_path, "TA-1"), pl.elegible(tmp_path, "TA-1")) == ("en_curso", False)


def test_B1_con_el_inicio_PROPIO_ilegible_no_se_registra_un_ejecutor(tmp_path, monkeypatch):
    monkeypatch.setattr(pl, "_inicio_de", lambda pid: pl._DESCONOCIDO)
    pl.registrar_planificada(tmp_path, _tarea())
    datos = [e for e in cp.leer_eventos(tmp_path) if e["tipo"] == "tarea_planificada"][-1]["datos"]
    assert "ejecutor" not in datos and pl.estado_de(tmp_path, "TA-1") == "sin_resultado_historico"


def test_M4_un_intento_vivo_tras_uno_revertido_esta_en_curso_aunque_el_tope_crezca(tmp_path, monkeypatch):
    monkeypatch.setattr(pl, "TOPE_DE_REINTENTOS", 3)
    pl.registrar_planificada(tmp_path, _tarea())
    _resultado(tmp_path, revertido=True)
    pl.registrar_planificada(tmp_path, _tarea())  # segundo intento, VIVO, sin resultado aun
    assert (pl.estado_de(tmp_path, "TA-1"), pl.elegible(tmp_path, "TA-1")) == ("en_curso", False)


def test_B1_sin_identidad_completa_no_se_registra_un_ejecutor_que_atascaria_la_tarea(tmp_path, monkeypatch):
    monkeypatch.setattr(pl, "_arranque", lambda: "")
    pl.registrar_planificada(tmp_path, _tarea())
    datos = [e for e in cp.leer_eventos(tmp_path) if e["tipo"] == "tarea_planificada"][-1]["datos"]
    assert "ejecutor" not in datos and pl.estado_de(tmp_path, "TA-1") == "sin_resultado_historico"


def test_B3_el_inicio_es_el_STARTTIME_de_verdad(tmp_path):
    """Contraste independiente: un proceso lanzado DESPUES tiene un starttime >= el nuestro, y el campo no es un
    contador que coincida entre procesos (p. ej. `num_threads` = 1 en ambos)."""
    hijo = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(5)"])
    try:
        nuestro, suyo = pl._inicio_de(os.getpid()), pl._inicio_de(hijo.pid)
        crudo = pathlib.Path(f"/proc/{hijo.pid}/stat").read_text()
        assert int(suyo) >= int(nuestro) and suyo == crudo[crudo.rindex(")") + 2:].split()[19]
        assert int(suyo) > 100, "un starttime en ticks desde el arranque no es un contador pequeno"
    finally:
        hijo.kill()
        hijo.wait()


def test_B3_un_ejecutor_ZOMBI_cuenta_como_muerto(tmp_path):
    import time
    hijo = subprocess.Popen([sys.executable, "-c", "pass"])
    for _ in range(100):
        if pathlib.Path(f"/proc/{hijo.pid}/stat").read_text().rsplit(")", 1)[1].split()[0] == "Z":
            break
        time.sleep(0.02)
    try:
        assert pl._inicio_de(hijo.pid) is None
    finally:
        hijo.wait()


def test_B3_registrar_planificada_ESPERA_al_cerrojo_del_log(tmp_path):
    """Atomicidad: si otro proceso tiene el cerrojo del log, la constancia espera a que lo suelte."""
    import time
    guion = ("import sys, time, pathlib; sys.path.insert(0, %r); import control_plane as cp\n"
             "with cp.lock_estado(pathlib.Path(%r)):\n    print('tomado', flush=True); time.sleep(1.5)\n") % (str(PLANO), str(tmp_path))
    otro = subprocess.Popen([sys.executable, "-c", guion], stdout=subprocess.PIPE, text=True)
    assert otro.stdout.readline().strip() == "tomado"
    t0 = time.monotonic()
    pl.registrar_planificada(tmp_path, _tarea())
    esperado = time.monotonic() - t0
    otro.wait()
    assert esperado >= 1.0, f"la constancia no espero al cerrojo ({esperado:.2f}s)"


# ------------------------------------- cierre de las condiciones del revisor (decision del CEO, 2026-10-26) --

def _sandbox(tmp_path, monkeypatch):
    """Sandbox con una oportunidad REAL (codigo muerto) y review habilitado SOLO en su log desechable."""
    import orquestador
    import review
    monkeypatch.setattr(orquestador, "mutacion_en_curso", lambda: False)
    monkeypatch.setenv("AURA_AUTOCONSTRUCCION_ESTADO", str(tmp_path / "estado-ac"))
    base = tmp_path / "sb"
    zona = base / "entorno" / "control-plane"
    zona.mkdir(parents=True)
    (zona / "modulo_inocuo.py").write_text("def _muerta():\n    return 1\n\n\ndef viva():\n    return 2\n")
    (zona / "test_modulo_inocuo.py").write_text("from modulo_inocuo import viva\n\n\ndef test_viva():\n    assert viva() == 2\n")
    review.habilitar(base, por="ceo", acta="SANDBOX de prueba", alcance=("eliminar_codigo_muerto",))
    import descubrimiento as des
    tarea = pl.siguiente(base, des.descubrir(zona, base))
    assert tarea is not None, "control: el sandbox tiene que ofrecer trabajo real"
    return base, zona, tarea


def test_M3_dos_supervisores_el_que_llega_tarde_PARA_sin_excepcion_y_sin_duplicar(tmp_path, monkeypatch):
    import motor_autonomia as motor
    base, zona, tarea = _sandbox(tmp_path, monkeypatch)
    pl.registrar_planificada(base, tarea)                      # el OTRO supervisor (vivo) se adelanto
    monkeypatch.setattr(motor.plan, "siguiente", lambda d, o: dict(tarea))  # la ventana siguiente() -> registrar
    informe = motor.trabajar(base, zona, verificacion=lambda r: True, max_tareas=3)
    assert informe["motivo_de_parada"] == "tarea tomada por otro supervisor"
    assert (informe["ejecutadas"], pl.intentos_de(base, tarea["id"])) == (0, 1), "ni ejecuta ni cuenta otro intento"


def test_AGOTADA_por_interrupciones_deja_EVENTO_una_sola_vez(tmp_path, monkeypatch):
    import motor_autonomia as motor
    base, zona, tarea = _sandbox(tmp_path, monkeypatch)
    for _ in range(pl.TOPE_DE_REINTENTOS):
        _planificada_por(base, {"pid": _pid_muerto(), "inicio": "1", "arranque": pl._arranque()}, tarea["id"])
    assert pl.estado_de(base, tarea["id"]) == "agotada"
    for _ in range(2):                                          # volver a mirar no es volver a agotar
        informe = motor.trabajar(base, zona, verificacion=lambda r: True, max_tareas=3)
        assert (informe["ejecutadas"], informe["motivo_de_parada"]) == (0, "cola agotada")
    agotados = [e for e in cp.leer_eventos(base)
                if e["tipo"] == motor.EVENTO_PRESUPUESTO_AGOTADO and e["datos"]["id"] == tarea["id"]]
    assert len(agotados) == 1, "agotada y OBSERVABLE en el log, sin repetirse"


def test_COMPLETADA_es_monotona_aunque_un_log_HEREDADO_la_replanificase(tmp_path):
    _planificada_por(tmp_path, None)
    _resultado(tmp_path, revertido=False)
    _planificada_por(tmp_path, None)                            # forma heredada: replanificada tras completarse
    assert (pl.completada(tmp_path, "TA-1"), pl.estado_de(tmp_path, "TA-1"), pl.elegible(tmp_path, "TA-1")) \
        == (True, "completada", False)


def test_el_estado_sale_SOLO_del_log_una_proyeccion_desfasada_no_lo_cambia(tmp_path):
    _planificada_por(tmp_path, {"pid": _pid_muerto(), "inicio": "1", "arranque": pl._arranque()})
    antes = pl.estado_de(tmp_path, "TA-1")
    (tmp_path / "estado.json").write_text("{ basura que no es la proyeccion")
    assert pl.estado_de(tmp_path, "TA-1") == antes == "interrumpida_reintentable"


def test_LIMITE_hidepid_2_con_PID_REUTILIZADO_es_conservador_espera_y_no_duplica(tmp_path, monkeypatch):
    """Limite conocido y aceptado (DP §2): el pid existe (es otro proceso) pero /proc no deja verlo. Se espera."""
    _planificada_por(tmp_path, {"pid": os.getpid(), "inicio": "inicio-de-OTRO-proceso", "arranque": pl._arranque()})
    _proc_stat_que(FileNotFoundError("hidepid=2"), tmp_path, monkeypatch)
    assert (pl.estado_de(tmp_path, "TA-1"), pl.elegible(tmp_path, "TA-1")) == ("en_curso", False)


# --- la primitiva PUBLICA de «comprobar y anadir» (sustituye al uso de `cp._registrar_sin_lock`) ---

def test_API_registrar_evento_si_anade_SOLO_si_la_condicion_se_cumple(tmp_path):
    assert cp.registrar_evento_si(tmp_path, "nota", {"n": 1}, lambda: False) is None
    assert cp.leer_eventos(tmp_path) == []
    evento = cp.registrar_evento_si(tmp_path, "nota", {"n": 2}, lambda: True)
    assert evento["tipo"] == "nota" and [e["datos"] for e in cp.leer_eventos(tmp_path)] == [{"n": 2}]
    assert cp.verificar_integridad_log(tmp_path)["integro"] is True


def test_API_registrar_evento_si_NIEGA_los_eventos_gobernados_como_registrar_evento(tmp_path):
    gobernado = sorted(cp.EVENTOS_GOBERNADOS)[0]
    with pytest.raises(cp.EventoNoGobernado):
        cp.registrar_evento_si(tmp_path, gobernado, {}, lambda: True)
    assert cp.leer_eventos(tmp_path) == []


def test_API_registrar_evento_si_evalua_la_condicion_DENTRO_del_cerrojo(tmp_path, monkeypatch):
    dentro = []
    real = cp.lock_estado

    @__import__("contextlib").contextmanager
    def espia(d):
        with real(d) as c:
            dentro.append(True)
            yield c
            dentro.append(False)

    monkeypatch.setattr(cp, "lock_estado", espia)
    vista = []
    cp.registrar_evento_si(tmp_path, "nota", {}, lambda: vista.append(list(dentro)) or True)
    assert vista == [[True]], "la condicion se evalua con el cerrojo tomado"


def test_el_planificador_ya_NO_usa_el_escritor_PRIVADO_del_log():
    import ast
    arbol = ast.parse((PLANO / "planificador.py").read_text(encoding="utf-8"))
    assert "_registrar_sin_lock" not in {n.attr for n in ast.walk(arbol) if isinstance(n, ast.Attribute)}


# --- §8: muerte ENTRE promover y registrar `cambio_aplicado` ---

_GUION_REGISTRO = _GUION.replace(
    "if fase == \"matar\":\n    zona.mkdir",
    "if fase == \"matar_al_registrar\":\n"
    "    import control_plane as cp\n"
    "    _real = cp.registrar_evento\n"
    "    def _registrar(d, tipo, datos=None):\n"
    "        if tipo == \"cambio_aplicado\" and (datos or {}).get(\"promovido\"):\n"
    "            os.kill(os.getpid(), signal.SIGKILL)  # promovido en disco, sin constancia en el log\n"
    "        return _real(d, tipo, datos)\n"
    "    cp.registrar_evento = _registrar\n"
    "if fase in (\"matar\", \"matar_al_registrar\"):\n    zona.mkdir")


@pytest.mark.skipif(not __import__("aislamiento").estricto_disponible(), reason="sin confinamiento estricto")
def test_E2E_muerte_entre_PROMOVER_y_REGISTRAR_no_cuenta_otro_intento_ni_duplica(tmp_path):
    assert _GUION_REGISTRO != _GUION, "control: la fase nueva tiene que haberse inyectado"
    guion = tmp_path / "guion.py"
    guion.write_text(_GUION_REGISTRO)
    base = tmp_path / "sandbox"
    (tmp_path / "tmp").mkdir()
    entorno = {**os.environ, "PYTHONPATH": str(PLANO), "AURA_AUTOCONSTRUCCION_ESTADO": str(tmp_path / "estado"),
               "TMPDIR": str(tmp_path / "tmp")}
    matar = subprocess.run([sys.executable, str(guion), str(base), "matar_al_registrar"], env=entorno,
                           capture_output=True, text=True, timeout=300)
    assert matar.returncode == -signal.SIGKILL, matar.stderr
    zona = base / "entorno" / "control-plane"
    assert "_muerta" not in (zona / "modulo_inocuo.py").read_text(), "control: la promocion SI llego al disco"
    id_tarea = [e for e in cp.leer_eventos(base) if e["tipo"] == "tarea_planificada"][0]["datos"]["id"]
    assert not [e for e in cp.leer_eventos(base) if e["tipo"] == "cambio_aplicado"], "control: sin constancia"

    seguir = subprocess.run([sys.executable, str(guion), str(base), "seguir"], env=entorno, capture_output=True,
                            text=True, timeout=300)
    assert seguir.stdout.split()[:1] == ["0"], seguir.stdout + seguir.stderr   # nada que volver a ejecutar
    eventos = cp.leer_eventos(base)
    assert pl.intentos_de(base, id_tarea) == 1, "la recuperacion no puede contar un intento de mas"
    # D2 (DP-AUTOCONSTRUCCION): el diario guarda la verificacion REAL y `recuperar()` la copia al `cambio_aplicado`
    # recuperado (`recuperado: true`). La tarea queda `completada` -no elegible, no se repite- en vez de ambigua.
    assert (pl.estado_de(base, id_tarea), pl.elegible(base, id_tarea)) == ("completada", False)
    assert [e["datos"]["resultado"] for e in eventos if e["tipo"] == "recuperacion_al_arranque"] == \
        ["promocion_confirmada"], "el log tiene que decir que se recupero, no callarlo"
    assert len([e for e in eventos if e["tipo"] == "cambio_aplicado" and e["datos"].get("promovido")]) == 1
    assert cp.verificar_integridad_log(base)["integro"] is True


@pytest.mark.parametrize("pendiente", ["bloqueado", "ocupado"])
def test_con_una_RECUPERACION_pendiente_el_motor_NO_planifica(tmp_path, monkeypatch, pendiente):
    """Un diario ambiguo (bloqueado) u otro proceso recuperando (ocupado): no hay dos recuperaciones a la vez."""
    import motor_autonomia as motor
    base, zona, tarea = _sandbox(tmp_path, monkeypatch)
    informe_rec = {"pendientes": 1, "resultados": [], "escribio": False, "bloqueado": False, "ocupado": False}
    monkeypatch.setattr(motor.ac, "recuperar", lambda d: {**informe_rec, pendiente: True})
    informe = motor.trabajar(base, zona, verificacion=lambda r: True, max_tareas=3)
    assert informe["motivo_de_parada"] == "recuperacion pendiente"
    assert pl.intentos_de(base, tarea["id"]) == 0, "nada se planifica mientras haya una recuperacion pendiente"


def test_control_una_tarea_COMPLETADA_en_su_ultimo_intento_NO_se_anuncia_agotada(tmp_path, monkeypatch):
    import motor_autonomia as motor
    base, zona, tarea = _sandbox(tmp_path, monkeypatch)
    _planificada_por(base, {"pid": _pid_muerto(), "inicio": "1", "arranque": pl._arranque()}, tarea["id"])
    _planificada_por(base, {"pid": _pid_muerto(), "inicio": "1", "arranque": pl._arranque()}, tarea["id"])
    _resultado(base, revertido=False)
    assert pl.estado_de(base, tarea["id"]) == "completada"
    motor.trabajar(base, zona, verificacion=lambda r: True, max_tareas=3)
    assert not [e for e in cp.leer_eventos(base) if e["tipo"] == motor.EVENTO_PRESUPUESTO_AGOTADO]


# ---------------- segunda ronda de revision (code-reviewer + security-reviewer, 2026-10-26) ----------------

def test_SUPERVISOR_UNICO_el_segundo_para_sin_planificar_nada(tmp_path, monkeypatch):
    """`cambio_aplicado` se atribuye a su tarea por ORDEN en el log (lleva el id de la propuesta, no el de la tarea).
    Dos supervisores sobre tareas DISTINTAS intercalarian sus eventos y uno se llevaria el resultado del otro. Con un
    solo supervisor por log el orden vuelve a ser una atribucion correcta."""
    import motor_autonomia as motor
    base, zona, tarea = _sandbox(tmp_path, monkeypatch)
    with cp.supervisor_unico(base) as tomado:                    # el OTRO supervisor, en pleno ciclo
        assert tomado is True
        informe = motor.trabajar(base, zona, verificacion=lambda r: True, max_tareas=3)
    assert informe["motivo_de_parada"] == "otro supervisor en curso"
    assert pl.intentos_de(base, tarea["id"]) == 0, "el segundo no planifica nada"
    informe = motor.trabajar(base, zona, verificacion=lambda r: True, max_tareas=3)   # control: libre, trabaja
    assert informe["motivo_de_parada"] != "otro supervisor en curso" and pl.intentos_de(base, tarea["id"]) == 1


def test_SUPERVISOR_UNICO_muere_con_su_dueno_un_SIGKILL_no_lo_deja_tomado(tmp_path):
    hijo = subprocess.Popen([sys.executable, "-c",
                             "import sys, time, control_plane as cp\n"
                             f"with cp.supervisor_unico({str(tmp_path)!r}) as t:\n"
                             "    print(t, flush=True); time.sleep(60)\n"],
                            env={**os.environ, "PYTHONPATH": str(PLANO)}, stdout=subprocess.PIPE, text=True)
    try:
        assert hijo.stdout.readline().strip() == "True"
        with cp.supervisor_unico(tmp_path) as tomado:
            assert tomado is False, "control: mientras vive, el cerrojo es suyo"
    finally:
        hijo.send_signal(signal.SIGKILL)
        hijo.wait()
    with cp.supervisor_unico(tmp_path) as tomado:
        assert tomado is True, "muerto el dueno, el cerrojo se libera solo"


@pytest.mark.parametrize("pid", [2 ** 40, 0, -1, "no-es-un-pid"])
def test_A1_un_PID_malformado_en_el_log_no_tumba_el_ciclo_y_queda_del_lado_conservador(tmp_path, pid):
    _planificada_por(tmp_path, {"pid": pid, "inicio": "1", "arranque": pl._arranque()})
    assert (pl.estado_de(tmp_path, "TA-1"), pl.elegible(tmp_path, "TA-1")) == ("en_curso", False)


def test_el_motor_solo_usa_RECUPERAR_de_autoconstruccion_el_deshacer_gobernado_no_ejecucion_nueva():
    import ast
    arbol = ast.parse((PLANO / "motor_autonomia.py").read_text(encoding="utf-8"))
    usados = {n.attr for n in ast.walk(arbol)
              if isinstance(n, ast.Attribute) and isinstance(n.value, ast.Name) and n.value.id == "ac"}
    assert usados == {"recuperar", "ZonaProhibida"}, usados


# Era un xfail estricto (LIMITE CONOCIDO DP §8): su alarma saltó al cerrarse D2 y se convierte en prueba normal.
@pytest.mark.skipif(not __import__("aislamiento").estricto_disponible(), reason="sin confinamiento estricto")
def test_PENDIENTE_la_promocion_recuperada_deberia_constar_COMPLETADA(tmp_path):
    guion = tmp_path / "guion.py"
    guion.write_text(_GUION_REGISTRO)
    base = tmp_path / "sandbox"
    (tmp_path / "tmp").mkdir()
    entorno = {**os.environ, "PYTHONPATH": str(PLANO), "AURA_AUTOCONSTRUCCION_ESTADO": str(tmp_path / "estado"),
               "TMPDIR": str(tmp_path / "tmp")}
    for fase in ("matar_al_registrar", "seguir"):
        subprocess.run([sys.executable, str(guion), str(base), fase], env=entorno, capture_output=True, timeout=300)
    id_tarea = [e for e in cp.leer_eventos(base) if e["tipo"] == "tarea_planificada"][0]["datos"]["id"]
    assert pl.estado_de(base, id_tarea) == "completada"


@pytest.mark.parametrize("pid", [0, -1, 2 ** 40])
def test_A1_fuera_de_rango_NUNCA_se_pregunta_a_kill_ni_por_un_grupo_de_procesos(tmp_path, monkeypatch, pid):
    llamadas = []
    monkeypatch.setattr(pl.os, "kill", lambda p, s: llamadas.append(p))
    _proc_stat_que(FileNotFoundError("no existe"), tmp_path, monkeypatch)
    _planificada_por(tmp_path, {"pid": pid, "inicio": "1", "arranque": pl._arranque()})
    assert pl.estado_de(tmp_path, "TA-1") == "en_curso" and llamadas == []


def test_H1_un_supervisor_RECHAZADO_no_abre_ni_cierra_ciclo_el_observatorio_sigue_viendo_al_que_trabaja(tmp_path,
                                                                                                      monkeypatch):
    """Tercera revision (H1): el rechazado escribia `motor_iniciado` + `ciclo_detenido`, cerraba en el observatorio el
    ciclo LEGITIMO en curso, dejaba huerfanos sus cambios y ponia el estado de AURA en ERROR mientras trabajaba."""
    import aura
    import motor_autonomia as motor
    import observatorio as obs
    base, zona, _ = _sandbox(tmp_path, monkeypatch)
    with cp.supervisor_unico(base):                              # A, en pleno ciclo
        cp.registrar_evento(base, "motor_iniciado", {"raiz": str(zona), "tope": 3, "review": True})
        informe = motor.trabajar(base, zona, verificacion=lambda r: True, max_tareas=3)   # B, rechazado
        tipos = [e["tipo"] for e in cp.leer_eventos(base)]
        assert tipos.count("motor_iniciado") == 1 and "ciclo_detenido" not in tipos, tipos[-4:]
        assert tipos.count("supervisor_rechazado") == 1, "el rechazo consta, pero fuera de los ciclos"
        assert obs.ciclos(base)[-1]["abierto"] is True, "el ciclo de A sigue abierto"
    assert informe["motivo_de_parada"] == "otro supervisor en curso"
    assert aura.codigo_de_salida(informe) == aura.SALIDA_OK, "H2: que otro este trabajando no es un fallo del cron"
