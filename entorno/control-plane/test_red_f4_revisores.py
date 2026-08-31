"""RED · **F4** = `C5` con `RevisorSubagente` / `RevisorHumano`.

`§20`: F4 depende de *«F3 + §25.2»*. F3 está hecha y **§25.2 es `D-ORCH-2`, aprobada por el CEO el
2026-08-26**. F4 queda por tanto autorizada.

Contrato literal de `§8.2`:

```python
@dataclass(frozen=True)
class Veredicto:
    veredicto: str          # "conforme" | "objeciones" | "rechazo" | "fuera_de_alcance"
    motivos: tuple[str, ...]
    evidencia_citada: tuple[str, ...]   # rutas y líneas; sin cita, no cuenta
    revisor: str
    instante: str
    # NO existe campo "autoriza". Deliberadamente.
```

**`§8.3 · Degradación`**: *«Si no hay revisor disponible, la tarea que exige revisión pasa a
`WAITING_FOR_REVIEW` y **espera**. **No se autoaprueba jamás.** Las tareas `AUTO` siguen avanzando: el
sistema no se detiene entero porque falte el revisor.»*
"""

from __future__ import annotations

import pathlib

import control_plane as cp
import pytest

import revisores as rev


# ============================================ EL VEREDICTO CONTRACTUAL --


def test_el_veredicto_tiene_los_CINCO_campos_del_contrato_y_ninguno_de_autorizacion():
    campos = set(rev.Veredicto.__dataclass_fields__)
    assert campos == {"veredicto", "motivos", "evidencia_citada", "revisor", "instante"}
    for prohibido in ("autoriza", "autorizado", "aprobado", "permite"):
        assert prohibido not in campos, f"el contrato dice: «NO existe campo {prohibido}»"


def test_solo_los_CUATRO_veredictos_del_contrato_son_validos():
    assert rev.VEREDICTOS == ("conforme", "objeciones", "rechazo", "fuera_de_alcance")
    for valido in rev.VEREDICTOS:
        rev.Veredicto(veredicto=valido, motivos=(), evidencia_citada=("f.py:1",),
                      revisor="r", instante="2026-08-26T00:00:00")
    with pytest.raises(ValueError, match="veredicto"):
        rev.Veredicto(veredicto="aprobado", motivos=(), evidencia_citada=("f.py:1",),
                      revisor="r", instante="2026-08-26T00:00:00")


def test_SIN_CITA_no_cuenta():
    """`§8.2`: *«rutas y líneas; **sin cita, no cuenta**»*. Un «conforme» sin evidencia es una
    opinión, y una opinión no mueve una tarea."""
    sin_cita = rev.Veredicto(veredicto="conforme", motivos=(), evidencia_citada=(),
                             revisor="r", instante="2026-08-26T00:00:00")
    assert rev.cuenta(sin_cita) is False
    con_cita = rev.Veredicto(veredicto="conforme", motivos=(), evidencia_citada=("entorno/control-plane/m.py:12",),
                             revisor="r", instante="2026-08-26T00:00:00")
    assert rev.cuenta(con_cita) is True


def test_el_veredicto_es_INMUTABLE():
    v = rev.Veredicto("conforme", (), ("f.py:1",), "r", "2026-08-26T00:00:00")
    with pytest.raises(Exception):
        v.veredicto = "rechazo"


def test_ningun_veredicto_AUTORIZA():
    """Lo que `D-ORCH-2` no cambió: `1.1:93`, la autoridad final no es delegable."""
    for valor in rev.VEREDICTOS:
        v = rev.Veredicto(valor, (), ("f.py:1",), "r", "2026-08-26T00:00:00")
        assert rev.autoriza(v) is False


# ============================================ EL EXPEDIENTE --


def test_el_expediente_lleva_lo_que_el_revisor_necesita_y_nada_mas():
    e = rev.Expediente(tarea_id="T-1", accion="eliminar_codigo_muerto", fichero="entorno/control-plane/m.py",
                       diagnostico="codigo muerto", criterios={"cambia_alcance": False})
    assert e.tarea_id == "T-1"
    import json
    texto = json.dumps(e.como_dict(), ensure_ascii=False).lower()
    for prohibido in ("api_key", "token", "secret", "password"):
        assert prohibido not in texto


# ============================================ LOS CUATRO REVISORES --


def test_los_cuatro_revisores_previstos_existen_con_su_estado():
    """`§8.2`: *«`RevisorSubagente` (hoy), `RevisorHumano` (buzón, hoy), `RevisorLocal` (Ollama,
    **hoy pero sin capacidad**), `RevisorExterno` (**bloqueado**, §25.1)»*."""
    assert rev.RevisorSubagente().disponible() is True
    assert rev.RevisorHumano().disponible() is True
    assert rev.RevisorLocal().disponible() is False, "previsto pero SIN capacidad"
    assert rev.RevisorExterno().disponible() is False, "bloqueado por §25.1 + D24"


def test_el_revisor_EXTERNO_esta_bloqueado_y_lanza_si_se_le_invoca():
    """`§25.1` sin resolver y D24 sin enmendar. Que exista la clase no es que pueda usarse."""
    e = rev.Expediente("T", "eliminar_codigo_muerto", "entorno/control-plane/m.py", "x", {})
    with pytest.raises(rev.RevisorBloqueado, match="D24|25.1"):
        rev.RevisorExterno().revisar(e)


def test_el_revisor_LOCAL_no_finge_capacidad():
    """INV-9. El DP lo prevé «sin capacidad»; devolver un veredicto inventado sería fingirla."""
    e = rev.Expediente("T", "eliminar_codigo_muerto", "entorno/control-plane/m.py", "x", {})
    with pytest.raises(rev.RevisorSinCapacidad):
        rev.RevisorLocal().revisar(e)


def test_el_RevisorSubagente_usa_los_agentes_que_YA_existen():
    r = rev.RevisorSubagente()
    assert r.nombre in ("auditor-consistencia", "arquitecto-evaluador")
    assert (pathlib.Path(rev.RAIZ_AGENTES) / f"{r.nombre}.md").exists()


def test_el_RevisorSubagente_emite_veredicto_CON_evidencia_citada():
    r = rev.RevisorSubagente()
    e = rev.Expediente("T-1", "eliminar_codigo_muerto", "entorno/control-plane/m.py", "codigo muerto",
                       {"cambia_alcance": False, "respeta_decisiones": True,
                        "d21_afirmativas": True, "materia_reservada": False})
    v = r.revisar(e)
    assert v.veredicto == "conforme", f"salió {v.veredicto}: {v.motivos}"
    assert v.evidencia_citada, "sin cita no contaría"
    assert rev.cuenta(v) is True


def test_el_RevisorSubagente_OBJETA_cuando_un_criterio_falla():
    r = rev.RevisorSubagente()
    e = rev.Expediente("T-1", "eliminar_codigo_muerto", "entorno/control-plane/m.py", "x",
                       {"cambia_alcance": True, "respeta_decisiones": True,
                        "d21_afirmativas": True, "materia_reservada": False})
    v = r.revisar(e)
    assert v.veredicto == "objeciones" and v.motivos


def test_el_RevisorSubagente_declara_FUERA_DE_ALCANCE_lo_reservado():
    r = rev.RevisorSubagente()
    e = rev.Expediente("T-1", "modificar_adr", "adr/x.md", "x", {})
    assert r.revisar(e).veredicto == "fuera_de_alcance"


# ============================================ REVISOR HUMANO · buzón --


def test_el_RevisorHumano_deja_la_peticion_en_un_BUZON_y_no_responde_solo(tmp_path):
    """El buzón es asíncrono a propósito: pedirle a una persona que revise **no** produce un
    veredicto, produce una espera."""
    d = pathlib.Path(tmp_path)
    r = rev.RevisorHumano(directorio=d)
    e = rev.Expediente("T-1", "eliminar_codigo_muerto", "entorno/control-plane/m.py", "x", {})
    assert r.revisar(e) is None, "sin respuesta humana todavía no hay veredicto"
    pendientes = rev.buzon_pendientes(d)
    assert [p["tarea_id"] for p in pendientes] == ["T-1"]


def test_el_buzon_solo_lo_responde_un_HUMANO(tmp_path):
    d = pathlib.Path(tmp_path)
    r = rev.RevisorHumano(directorio=d)
    r.revisar(rev.Expediente("T-1", "eliminar_codigo_muerto", "entorno/control-plane/m.py", "x", {}))
    for no_humano in ("aura", "orquestador", "auditor-consistencia"):
        with pytest.raises(rev.RevisorNoHumano):
            rev.responder_buzon(d, "T-1", veredicto="conforme", por=no_humano,
                               evidencia_citada=("entorno/control-plane/m.py:1",))
    v = rev.responder_buzon(d, "T-1", veredicto="conforme", por="ceo",
                            evidencia_citada=("entorno/control-plane/m.py:1",))
    assert v.revisor == "ceo" and rev.cuenta(v) is True
    assert rev.buzon_pendientes(d) == []


def test_una_respuesta_del_buzon_SIN_cita_no_cuenta(tmp_path):
    d = pathlib.Path(tmp_path)
    rev.RevisorHumano(directorio=d).revisar(rev.Expediente("T-1", "eliminar_codigo_muerto", "entorno/control-plane/m.py", "x", {}))
    with pytest.raises(ValueError, match="cita|evidencia"):
        rev.responder_buzon(d, "T-1", veredicto="conforme", por="ceo", evidencia_citada=())


# ============================================ §8.3 · DEGRADACIÓN --


def test_sin_revisor_la_tarea_ESPERA_en_WAITING_FOR_REVIEW(tmp_path):
    """`§8.3` literal. Y ese es el estado que F1 añadió al vocabulario: aquí empieza a usarse."""
    d = pathlib.Path(tmp_path)
    cp.registrar_evento(d, "tarea_registrada", {"id": "T-1", "accion": "eliminar_codigo_muerto"})
    cp.transicion(d, "T-1", "WORKING", autoridad="orquestador", causa="empieza")
    resultado = rev.pedir_revision(d, rev.Expediente("T-1", "eliminar_codigo_muerto", "entorno/control-plane/m.py", "x", {}),
                                   revisores=[rev.RevisorLocal(), rev.RevisorExterno()],
                                   autoridad="orquestador")
    assert resultado["veredicto"] is None
    assert resultado["estado"] == "WAITING_FOR_REVIEW"
    assert cp.estado_de(d, "T-1") == "WAITING_FOR_REVIEW"


def test_sin_revisor_JAMAS_se_autoaprueba(tmp_path):
    """`§8.3`: *«No se autoaprueba jamás»*. Es la garantía central de F4."""
    d = pathlib.Path(tmp_path)
    cp.registrar_evento(d, "tarea_registrada", {"id": "T-1", "accion": "eliminar_codigo_muerto"})
    cp.transicion(d, "T-1", "WORKING", autoridad="orquestador", causa="empieza")
    resultado = rev.pedir_revision(d, rev.Expediente("T-1", "eliminar_codigo_muerto", "entorno/control-plane/m.py", "x", {}),
                                   revisores=[rev.RevisorLocal(), rev.RevisorExterno()],
                                   autoridad="orquestador")
    assert resultado["veredicto"] is None
    assert cp.estado_de(d, "T-1") != "COMPLETED"
    assert not any(e["tipo"] == "veredicto_emitido" for e in cp.leer_eventos(d))


def test_las_tareas_AUTO_siguen_avanzando_sin_revisor():
    """`§8.3`: *«el sistema no se detiene entero porque falte el revisor»*."""
    assert rev.exige_revision("eliminar_codigo_muerto") is True
    for auto in ("ejecutar_pruebas", "verificar_calidad", "auditar_garantias", "diagnosticar_estado"):
        assert rev.exige_revision(auto) is False


def test_se_usa_el_PRIMER_revisor_disponible_de_la_cadena(tmp_path):
    d = pathlib.Path(tmp_path)
    cp.registrar_evento(d, "tarea_registrada", {"id": "T-1", "accion": "eliminar_codigo_muerto"})
    cp.transicion(d, "T-1", "WORKING", autoridad="orquestador", causa="empieza")
    resultado = rev.pedir_revision(
        d, rev.Expediente("T-1", "eliminar_codigo_muerto", "entorno/control-plane/m.py", "x",
                          {"cambia_alcance": False, "respeta_decisiones": True,
                           "d21_afirmativas": True, "materia_reservada": False}),
        revisores=[rev.RevisorLocal(), rev.RevisorExterno(), rev.RevisorSubagente()],
        autoridad="orquestador")
    assert resultado["veredicto"].veredicto == "conforme"
    assert resultado["estado"] == "REVISADA"
    assert any(e["tipo"] == "veredicto_emitido" for e in cp.leer_eventos(d))


def test_un_revisor_que_emite_SIN_CITA_es_saltado_y_se_busca_otro(tmp_path):
    """Cierra la rama que ninguna prueba ejercitaba: *«sin cita, no cuenta»* no es solo una etiqueta
    en el informe, decide si ese veredicto **entra o no** en la cadena. Sin este caso, un mutante que
    aceptaba veredictos sin evidencia sobrevivía."""
    d = pathlib.Path(tmp_path)
    cp.registrar_evento(d, "tarea_registrada", {"id": "T-1", "accion": "eliminar_codigo_muerto"})
    cp.transicion(d, "T-1", "WORKING", autoridad="orquestador", causa="empieza")

    class RevisorSinCita:
        nombre = "sin-cita"

        def disponible(self):
            return True

        def revisar(self, _e):
            return rev.Veredicto("conforme", (), (), self.nombre, "2026-08-26T00:00:00")

    expediente = rev.Expediente("T-1", "eliminar_codigo_muerto", "entorno/control-plane/m.py", "x",
                                {"cambia_alcance": False, "respeta_decisiones": True,
                                 "d21_afirmativas": True, "materia_reservada": False})

    resultado = rev.pedir_revision(d, expediente, revisores=[RevisorSinCita()],
                                   autoridad="orquestador")
    assert resultado["veredicto"] is None, "un veredicto sin cita no cierra la revisión"
    assert cp.estado_de(d, "T-1") == "WAITING_FOR_REVIEW", "y la tarea espera"

    resultado = rev.pedir_revision(d, expediente,
                                   revisores=[RevisorSinCita(), rev.RevisorSubagente()],
                                   autoridad="orquestador")
    assert resultado["veredicto"].revisor == "auditor-consistencia", "se saltó al que no citaba"
    assert rev.cuenta(resultado["veredicto"]) is True
