"""RED · B2 — una sola ejecución controlada del canal con un agente REAL.

`PLAN-B2.md` lo define entero y esto no lo amplía. Su **§7** pide exactamente esto: *«cuatro pruebas
con un doble local que imita al agente; ejercitan el ciclo entero de B2 sin una sola invocación
real»*. Aquí están, y con ellas el veredicto queda probado **antes** de gastar la invocación.

**Las seis evidencias de §4**, todas verificables sin juicio: exit code 0 · `is_error: false`
—nunca `subtype`, *«que ya se midió mintiendo»*— · existe un `RESULT` · `in_reply_to` correcto ·
`cuerpo["suma"] == 42` · `seq` monótona e integridad de la cadena.

**Y la distinción que §4 exige y es la razón de ser del verificador:** si 1–2 pasan pero 3–5 fallan,
*«el canal funciona y el agente no siguió la instrucción»*. **Es un resultado distinto de un canal
roto**, y confundirlos haría inútil el experimento.
"""

from __future__ import annotations

import communication_plane as cp
import pytest
from verificador_b2 import (
    TAREA,
    publicar_tarea,
    veredicto,
    verificar_b2,
)

SOBRE_OK = {"is_error": False, "subtype": "success", "total_cost_usd": 0.01,
            "usage": {"input_tokens": 10, "output_tokens": 5}}


def _canal(tmp_path):
    return cp.abrir(str(tmp_path))


def _responde(canal, id_tarea, suma=42, in_reply_to=True, de="claude-code"):
    """Doble local del agente: publica el RESULT que B2 espera del receptor real."""
    return canal.publicar(tipo="RESULT", de=de, para="orquestador-local",
                          cuerpo={"suma": suma},
                          in_reply_to=id_tarea if in_reply_to else None)


# ============================================ EL CAMINO BUENO · meta-control --


def test_doble_que_responde_bien_da_las_SEIS_evidencias(tmp_path):
    """**Meta-control del verificador.** Si no existiera, un verificador que dijera «no» siempre
    pasaría todas las pruebas de abajo y B2 sería imposible de aprobar aunque el agente acertara."""
    canal = _canal(tmp_path)
    id_tarea = publicar_tarea(canal)
    _responde(canal, id_tarea)

    ev = verificar_b2(canal, id_tarea, SOBRE_OK, codigo_salida=0)
    assert all(ev.values()), f"faltan evidencias: {[k for k, v in ev.items() if not v]}"
    assert veredicto(ev) == "GREEN"


def test_la_tarea_publicada_es_la_del_plan(tmp_path):
    """17+25=42, *«mecánicamente verificable, sin juicio, sin prosa que evaluar»* (§2)."""
    canal = _canal(tmp_path)
    id_tarea = publicar_tarea(canal)
    t = canal.leer(id_tarea)
    assert t["tipo"] == "TASK" and t["para"] == "claude-code"
    assert (t["cuerpo"]["a"], t["cuerpo"]["b"]) == (17, 25)
    assert TAREA["objetivo"] == "sumar"


# ================================== CANAL OK PERO EL AGENTE NO SIGUIO (§4) --


def test_sin_RESULT_el_canal_esta_OK_y_el_agente_no_siguio(tmp_path):
    """El caso que §4 obliga a distinguir. El canal no tiene la culpa."""
    canal = _canal(tmp_path)
    id_tarea = publicar_tarea(canal)

    ev = verificar_b2(canal, id_tarea, SOBRE_OK, codigo_salida=0)
    assert ev["exit_cero"] and ev["sin_error_en_sobre"] and ev["integridad"]
    assert not ev["hay_result"]
    assert veredicto(ev) == "CANAL_OK_AGENTE_NO_SIGUIO"


def test_una_suma_incorrecta_no_es_GREEN(tmp_path):
    canal = _canal(tmp_path)
    id_tarea = publicar_tarea(canal)
    _responde(canal, id_tarea, suma=41)

    ev = verificar_b2(canal, id_tarea, SOBRE_OK, codigo_salida=0)
    assert ev["hay_result"] and not ev["suma_correcta"]
    assert veredicto(ev) == "CANAL_OK_AGENTE_NO_SIGUIO"


def test_un_RESULT_sin_in_reply_to_no_cierra_el_hilo(tmp_path):
    """Sin `in_reply_to` el canal no puede reconstruir a qué respondía: la trazabilidad se pierde."""
    canal = _canal(tmp_path)
    id_tarea = publicar_tarea(canal)
    _responde(canal, id_tarea, in_reply_to=False)

    ev = verificar_b2(canal, id_tarea, SOBRE_OK, codigo_salida=0)
    assert not ev["responde_a_la_tarea"]
    assert veredicto(ev) != "GREEN"


# ============================================== EL SOBRE · trampa ya medida --


def test_is_error_true_con_subtype_success_NO_es_exito(tmp_path):
    """Medido el 2026-08-17: `claude -p` devolvió `is_error: true` **junto a**
    `subtype: "success"`. Fiarse de `subtype` daría por buena una ejecución fallida."""
    canal = _canal(tmp_path)
    id_tarea = publicar_tarea(canal)
    _responde(canal, id_tarea)

    ev = verificar_b2(canal, id_tarea,
                      {"is_error": True, "subtype": "success"}, codigo_salida=0)
    assert not ev["sin_error_en_sobre"]
    assert veredicto(ev) != "GREEN"


def test_exit_distinto_de_cero_no_es_GREEN(tmp_path):
    canal = _canal(tmp_path)
    id_tarea = publicar_tarea(canal)
    _responde(canal, id_tarea)
    ev = verificar_b2(canal, id_tarea, SOBRE_OK, codigo_salida=1)
    assert not ev["exit_cero"] and veredicto(ev) != "GREEN"


def test_un_sobre_sin_is_error_se_rechaza(tmp_path):
    """Ausencia de dato no es dato."""
    canal = _canal(tmp_path)
    id_tarea = publicar_tarea(canal)
    _responde(canal, id_tarea)
    ev = verificar_b2(canal, id_tarea, {"subtype": "success"}, codigo_salida=0)
    assert not ev["sin_error_en_sobre"]


# ==================================================== INTEGRIDAD DEL CANAL --


def test_la_integridad_se_comprueba_DESPUES_de_escribir_el_agente(tmp_path):
    """§4.6: la cadena de hashes debe seguir íntegra **tras** la escritura del receptor, que es
    justo cuando podría romperse."""
    canal = _canal(tmp_path)
    id_tarea = publicar_tarea(canal)
    _responde(canal, id_tarea)
    ev = verificar_b2(canal, id_tarea, SOBRE_OK, codigo_salida=0)
    assert ev["integridad"] is True


def test_una_cadena_manipulada_se_detecta(tmp_path):
    """Control del control: si `integridad` no pudiera dar False, no estaría comprobando nada."""
    canal = _canal(tmp_path)
    id_tarea = publicar_tarea(canal)
    _responde(canal, id_tarea)

    ruta = cp.ruta_log(str(tmp_path))
    lineas = ruta.read_text(encoding="utf-8").splitlines()
    lineas[0] = lineas[0].replace('"sumar"', '"restar"')
    ruta.write_text("\n".join(lineas) + "\n", encoding="utf-8")

    ev = verificar_b2(canal, id_tarea, SOBRE_OK, codigo_salida=0)
    assert ev["integridad"] is False


@pytest.mark.parametrize("coste", [{"total_cost_usd": 0.01}, {}])
def test_el_coste_se_registra_sin_inventar_cuota_restante(coste, tmp_path):
    """§6: del envoltorio se toma lo medido; `cuota_restante` queda `UNKNOWN`."""
    r = cp.registrar_coste({**coste, "usage": {"output_tokens": 5}})
    assert r["cuota_restante"] == "UNKNOWN"


# ===== B2-M8 · EQUIVALENTE DEMOSTRADO POR EJECUCIÓN, no por intuición --
#
# `B2-M8` quita `huecos_de_secuencia` de la comprobación de integridad y **sobrevive**. Intenté
# cerrarlo con un caso discriminante y **la hipótesis era mía y resultó falsa**: creí que una línea
# ilegible se descartaría dejando la cadena intacta y un hueco en `seq`. Medido, no ocurre.
#
#   línea INTERMEDIA ilegible  -> integro=False (el encadenamiento de la siguiente ya no casa)
#   ÚLTIMA línea ilegible      -> integro=True, pero NO deja hueco: falta una cola, no un centro
#
# Las dos únicas formas de perder una línea dan el mismo veredicto con y sin la comprobación de
# huecos. **No se puede construir un canal con `integro=True` y hueco de `seq`**, así que el mutante
# no degrada ninguna garantía observable: es defensa en profundidad.
#
# No se añade una prueba decorativa para matarlo. Se deja escrito por qué no se puede.
