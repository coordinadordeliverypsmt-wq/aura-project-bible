# -------------------------------- una frase con DOS declaraciones registra las dos (campaña, 2026-09-27)
#
# Encontrado en la prueba FÍSICA de voz `[EJEC]`: la persona dijo por el aire «Me llamo Mauricio y me
# gusta el color verde», Whisper lo transcribió exacto, y aun así AURA contestó después «Todavía no me
# has dicho cómo te llamas». El conector clasificaba UNA sola clase por enunciado, la preferencia («me
# gusta») ganaba, y el nombre se perdía. Por texto nadie habla así; por voz, casi todo el mundo.

import asyncio as _asyncio  # noqa: E402

from aura_skeleton.conectores.conversacion import (  # noqa: E402
    ConectorConversacion as _Conector,
)
from aura_skeleton.conectores.conversacion import (  # noqa: E402
    es_declaracion_de_hecho_propio as _es_decl,
)


def _recoger(texto):
    c = _Conector()
    c.observar(texto)
    return _asyncio.run(c.recoger("T"))


def test_una_frase_con_nombre_y_gusto_registra_las_DOS_senales():
    clases = sorted(s.clase.name for s in _recoger("Me llamo Mauricio y me gusta el color verde."))
    assert clases == ["HECHO_DECLARADO", "PREFERENCIA_DECLARADA"], clases


def test_la_frase_compuesta_es_una_declaracion_de_hecho_propio():
    """Si no, el turno cae al modelo (113 s medidos) en vez del acuse determinista del Core."""
    assert _es_decl("Me llamo Mauricio y me gusta el color verde.")


def test_CONTROL_un_hecho_con_y_dentro_NO_se_parte():
    """«y transporte» no es otra declaración: partir aquí truncaría el hecho a «logística»."""
    senales = _recoger("trabajo de logística y transporte")
    assert len(senales) == 1 and "transporte" in senales[0].contenido, senales


def test_CONTROL_una_frase_con_una_parte_que_no_declara_nada_no_se_parte():
    """Conservador a propósito: solo se parte cuando TODAS las partes declaran algo. Aquí «hoy hace
    calor» no declara nada, así que la frase se trata entera, igual que antes de este cambio."""
    senales = _recoger("me llamo Mauricio y hoy hace calor")
    assert len(senales) <= 1, senales
