"""RED · `§12 · Recuperación`, la fila de la escritura interrumpida.

El `§12` declara esta respuesta:

> | Escritura de evidencia interrumpida | `sha256` de la línea no cuadra / **línea truncada** |
> | **Línea descartada del log**, tarea `FAILED` |

Medido `[EJEC]` antes de este fichero, sobre un log con la última línea a medias:

```
leer_eventos               -> JSONDecodeError: Unterminated string starting at: line 1 column 27
proyectar                  -> JSONDecodeError
registrar_evento           -> JSONDecodeError
verificar_integridad_log   -> JSONDecodeError
```

**Ninguna línea se descarta: el Control Plane entero deja de ser legible.** Y lo peor de la lista es
`registrar_evento`: el sistema no puede ni anotar que está roto, así que no hay forma de que se
recupere solo ni de que deje constancia. Para un componente cuya razón de ser es sobrevivir a un
`SIGKILL` —el criterio `A4`, que este proyecto ya midió con un `kill -9` real— es el fallo exacto que
tenía que soportar.

**La línea truncada NO es lo mismo que la línea alterada, y tratarlas igual sería un error caro.**
Solo la **última** línea puede quedar a medias por una escritura interrumpida: las anteriores ya
estaban completas y con `fsync`. Una línea rota **en medio** no viene de una caída — viene de que
alguien tocó el fichero—, y descartarla en silencio convertiría el log encadenado en un registro que
se repara solo borrando lo que le molesta. Esa distingue el arreglo de un agujero.
"""

from __future__ import annotations

import json

import control_plane as cp
import pytest


def _log_con_dos_eventos(directorio):
    cp.registrar_evento(directorio, "tarea_registrada", {"id": "T-1", "accion": "ejecutar_pruebas"})
    cp.registrar_evento(directorio, "algo_mas", {"x": 1})
    return cp.ruta_eventos(directorio)


# ================================ LA COLA TRUNCADA: se descarta y el sistema SIGUE --


def test_una_ULTIMA_linea_truncada_no_deja_ilegible_el_log(tmp_path):
    """Lo que `§12` promete: la línea se descarta, y lo demás se lee."""
    ruta = _log_con_dos_eventos(tmp_path)
    ruta.write_text(ruta.read_text(encoding="utf-8") + '{"seq":3,"tipo":"parcial","dat',
                    encoding="utf-8")
    eventos = cp.leer_eventos(tmp_path)
    assert [e["seq"] for e in eventos] == [1, 2], "los completos se leen; el partido no"


def test_la_proyeccion_sobrevive_a_una_escritura_interrumpida(tmp_path):
    ruta = _log_con_dos_eventos(tmp_path)
    ruta.write_text(ruta.read_text(encoding="utf-8") + '{"seq":3,"tipo":"tar', encoding="utf-8")
    proyeccion = cp.proyectar(tmp_path)
    assert "T-1" in proyeccion["tareas"], "la tarea registrada antes de la caída sigue ahí"


def test_el_sistema_puede_VOLVER_A_ESCRIBIR_tras_una_caida(tmp_path):
    """La más importante de todas. Si `registrar_evento` no funciona, el Control Plane no puede
    siquiera dejar constancia de que se cayó, y no hay recuperación posible sin editar a mano."""
    ruta = _log_con_dos_eventos(tmp_path)
    ruta.write_text(ruta.read_text(encoding="utf-8") + '{"seq":3,"ti', encoding="utf-8")
    nuevo = cp.registrar_evento(tmp_path, "despues_de_la_caida", {"ok": True})
    # `seq` 4, no 3: el descarte es **un evento mas** y ocupa el suyo. Que el hecho de haberse
    # reparado consuma una posicion en la historia es lo correcto — lo contrario seria una
    # reparacion que no deja hueco donde constar.
    assert nuevo["seq"] == 4
    tipos = [e["tipo"] for e in cp.leer_eventos(tmp_path)]
    assert tipos[-2:] == ["linea_truncada_descartada", "despues_de_la_caida"]


def test_la_cola_truncada_se_RETIRA_del_fichero_no_se_ignora_para_siempre(tmp_path):
    """Ignorarla al leer no basta: en cuanto se añada un evento nuevo, la línea partida deja de ser
    la última y pasa a ser una línea rota **en medio**, que es el caso que sí debe fallar. Hay que
    quitarla del fichero, no mirar hacia otro lado."""
    ruta = _log_con_dos_eventos(tmp_path)
    ruta.write_text(ruta.read_text(encoding="utf-8") + '{"seq":3,"ti', encoding="utf-8")
    cp.registrar_evento(tmp_path, "despues", {})
    for linea in ruta.read_text(encoding="utf-8").splitlines():
        if linea.strip():
            json.loads(linea)      # todas las lineas del fichero vuelven a ser validas


def test_el_descarte_queda_REGISTRADO_no_ocurre_en_silencio(tmp_path):
    """Un log encadenado que se repara solo y sin decirlo es un log en el que no se puede confiar.
    El descarte es un hecho del sistema y va al propio historial."""
    ruta = _log_con_dos_eventos(tmp_path)
    ruta.write_text(ruta.read_text(encoding="utf-8") + '{"seq":3,"ti', encoding="utf-8")
    cp.registrar_evento(tmp_path, "despues", {})
    tipos = [e["tipo"] for e in cp.leer_eventos(tmp_path)]
    assert "linea_truncada_descartada" in tipos


def test_la_cadena_de_hashes_sigue_INTEGRA_tras_el_descarte(tmp_path):
    """Descartar la cola no puede romper el encadenado: si lo rompiera, el arreglo de un fallo
    esperado dejaría el log permanentemente marcado como manipulado."""
    ruta = _log_con_dos_eventos(tmp_path)
    ruta.write_text(ruta.read_text(encoding="utf-8") + '{"seq":3,"ti', encoding="utf-8")
    cp.registrar_evento(tmp_path, "despues", {})
    assert cp.verificar_integridad_log(tmp_path)["integro"] is True


# ============================== LA LINEA ROTA EN MEDIO: eso NO es una caida --


def test_una_linea_rota_EN_MEDIO_no_se_descarta_en_silencio(tmp_path):
    """Solo la **última** línea puede quedar a medias por una escritura interrumpida: las anteriores
    ya estaban completas y con `fsync`. Una rota en medio viene de que alguien tocó el fichero.

    Si se descartara igual, el log encadenado se convertiría en un registro que se repara solo
    borrando lo que le estorba — y esa es precisamente la propiedad que un log de auditoría no puede
    tener."""
    ruta = _log_con_dos_eventos(tmp_path)
    lineas = ruta.read_text(encoding="utf-8").splitlines()
    ruta.write_text("\n".join([lineas[0], '{"seq":2,"rot', lineas[1]]) + "\n", encoding="utf-8")
    with pytest.raises(cp.LogCorrupto):
        cp.leer_eventos(tmp_path)


def test_un_log_SANO_no_dispara_ningun_descarte(tmp_path):
    """Caso de control: la reparación tiene que distinguir, no actuar siempre."""
    _log_con_dos_eventos(tmp_path)
    cp.registrar_evento(tmp_path, "normal", {})
    assert "linea_truncada_descartada" not in [e["tipo"] for e in cp.leer_eventos(tmp_path)]
    assert cp.verificar_integridad_log(tmp_path)["integro"] is True


def test_verificar_integridad_INFORMA_de_la_cola_truncada_en_vez_de_explotar(tmp_path):
    """La herramienta que existe para diagnosticar un log dañado no puede ser la que se cae con él."""
    ruta = _log_con_dos_eventos(tmp_path)
    ruta.write_text(ruta.read_text(encoding="utf-8") + '{"seq":3,"ti', encoding="utf-8")
    informe = cp.verificar_integridad_log(tmp_path)
    assert informe["cola_truncada"] is True
    assert informe["integro"] is True, "los eventos completos siguen encadenados entre sí"


def test_retirar_la_cola_NO_TOCA_un_solo_byte_de_los_eventos_anteriores(tmp_path):
    """`§5`, C1: el event log *«nunca: borrarse ni reescribirse»*.

    La primera versión de esta reparación regeneraba el fichero entero desde los eventos leídos.
    Aunque el contenido saliera idéntico, eso es **reescribir el log completo para arreglar su última
    línea**, y bastaría que la serialización produjera un byte distinto del que se escribió para
    alterar la historia en silencio y romper los hashes. Truncar solo puede afectar a la cola: los
    bytes ya cerrados quedan físicamente fuera de alcance.

    Se comprueba por bytes, no por contenido lógico: es la única forma de distinguir «no cambió» de
    «volvió a escribirse igual»."""
    ruta = _log_con_dos_eventos(tmp_path)
    intactos = ruta.read_bytes()
    ruta.write_bytes(intactos + b'{"seq":3,"tipo":"par')
    cp.registrar_evento(tmp_path, "despues", {})
    despues = ruta.read_bytes()
    assert despues.startswith(intactos), (
        "los bytes de los eventos ya cerrados tienen que seguir siendo exactamente los mismos")
