"""VOLUMEN Y SILENCIO DE LA TV, de la orden al efecto releído (acta `decisiones/2026-10-22-acta-ecosistema-domestico.md` §4).

Cadena: orden escrita → Core (sin modelo) → Motor Único (permisos, PARADA) → Home Assistant → atributo releído ANTES y
DESPUÉS → respuesta con lo que realmente cambió. Una orden enviada no es un efecto: si el volumen no se puede leer, no se
envía; si se envía y no cambia, no se da por hecho. Por VOZ sigue rigiendo la opción C (solo encender/apagar).

Todo con dobles: ni Home Assistant ni la TV reales.
"""

from __future__ import annotations

import io
import os
import urllib.error
import uuid

import pytest

from aura_skeleton.adapters.home_assistant_real import HomeAssistantReal
from aura_skeleton.composicion import Configuracion, componer

SALA = "media_player.tv_sala_fmilia_medina_un43ru7100fxza"
TV20 = "media_player.samsung_6_series_55_un55ku6000"


class _HAVolumen:
    """Doble de Home Assistant con las dos TV reales de la casa, encendidas y con volumen legible."""

    def __init__(
        self, efecto=True, sala="on", expone=True, servicio_cae=False, credencial_mala=False, volumen=0.2, pierde=False
    ):
        atributos = {"friendly_name": "Tv sala fmilia medina", "volume_level": volumen, "is_volume_muted": False}
        if not expone:
            atributos = {"friendly_name": "Tv sala fmilia medina"}
        self.estados = {
            SALA: {"state": sala, "attributes": atributos},
            TV20: {
                "state": "on",
                "attributes": {"friendly_name": "Samsung 6 Series 55", "volume_level": 0.5, "is_volume_muted": False},
            },
        }
        self.efecto, self.servicio_cae, self.credencial_mala = efecto, servicio_cae, credencial_mala
        self.pierde = pierde  # tras el servicio, HA deja de dar un volumen legible (None)
        self.servicios: list[str] = []

    def __call__(self, metodo, url, cuerpo=None, token=""):
        if self.credencial_mala:
            raise urllib.error.HTTPError(url, 401, "Unauthorized", {}, io.BytesIO(b""))
        if url.endswith("/api/states"):
            return [{"entity_id": e, **v} for e, v in self.estados.items()]
        if "/api/states/" in url:
            e = url.rsplit("/", 1)[1]
            return {"entity_id": e, **self.estados[e]}
        if "/api/services/" in url:
            if self.servicio_cae:
                raise ConnectionRefusedError("HA cayó al enviar")
            servicio = url.rsplit("/", 1)[1]
            self.servicios.append(servicio)
            if self.pierde:
                self.estados[cuerpo["entity_id"]]["attributes"]["volume_level"] = None
            elif self.efecto:
                a = self.estados[cuerpo["entity_id"]]["attributes"]
                if servicio == "volume_up":
                    a["volume_level"] = round(a["volume_level"] + 0.01, 2)
                elif servicio == "volume_down":
                    a["volume_level"] = round(a["volume_level"] - 0.01, 2)
                elif servicio == "volume_mute":
                    a["is_volume_muted"] = cuerpo["is_volume_muted"]
                elif servicio in ("turn_on", "turn_off"):
                    self.estados[cuerpo["entity_id"]]["state"] = "on" if servicio == "turn_on" else "off"
            return []
        return {"message": "API running."}


class _Espia:
    name = "espia"

    def __init__(self):
        self.llamadas = 0

    async def infer(self, prompt, *a, **k):
        self.llamadas += 1
        return '{"intent":"x","action":"consulta","args":{},"say":"Entendido."}'


class _Voz:
    ultima_confianza = None

    async def stt(self, audio, tid):
        return audio[4:] if audio.startswith("voz:") else audio

    async def tts(self, texto, tid):
        return None


def _aura(tmp_path, ha):
    sis = componer(Configuracion(datos=str(tmp_path), raices_permitidas=(str(tmp_path),)))
    real = HomeAssistantReal(url="http://127.0.0.1:8123", token="t", http=ha, espera_s=0.05)
    for cap in real.capabilities:
        sis.registro_adaptadores._por_capacidad[cap] = real
    espia = _Espia()
    sis.orquestador.router.providers = [espia]
    sis.orquestador.voice = _Voz()
    return sis, espia


async def _di(sis, texto, *, voz=False, activado=False):
    tid = uuid.uuid4().hex[:12]
    await sis.orquestador.handle_utterance("u", f"voz:{texto}" if voz else texto, tid, activado=activado)
    await sis.orquestador.wait(tid)
    return sis.orquestador._results[tid]


def _volumen(ha, e=SALA):
    return ha.estados[e]["attributes"].get("volume_level")


# ----------------------------------------------------------------------------------- camino feliz --


@pytest.mark.asyncio
async def test_subir_el_volumen_de_la_tele_de_la_sala_lo_cambia_y_lo_comprueba(tmp_path):
    ha = _HAVolumen()
    sis, espia = _aura(tmp_path, ha)

    r = await _di(sis, "sube el volumen de la tele de la sala")

    assert ha.servicios == ["volume_up"] and _volumen(ha) == 0.21
    assert "la TV de la sala" in r["say"] and "comprobado" in r["say"] and "21" in r["say"], r["say"]
    assert _volumen(ha, TV20) == 0.5, "tocó la otra TV"
    assert espia.llamadas == 0, "el modelo intervino"


@pytest.mark.asyncio
async def test_bajar_el_volumen_lo_baja_y_lo_comprueba(tmp_path):
    ha = _HAVolumen()
    sis, _ = _aura(tmp_path, ha)

    r = await _di(sis, "baja el volumen de la tele de la sala")

    assert ha.servicios == ["volume_down"] and _volumen(ha) == 0.19
    assert "comprobado" in r["say"] and "19" in r["say"], r["say"]


@pytest.mark.asyncio
async def test_silenciar_y_quitar_el_silencio_se_comprueban_releyendo(tmp_path):
    ha = _HAVolumen()
    sis, _ = _aura(tmp_path, ha)

    r1 = await _di(sis, "silencia la tele de la sala")
    assert ha.estados[SALA]["attributes"]["is_volume_muted"] is True and "comprobado" in r1["say"], r1["say"]

    r2 = await _di(sis, "quita el silencio de la tele de la sala")
    assert ha.estados[SALA]["attributes"]["is_volume_muted"] is False and "comprobado" in r2["say"], r2["say"]
    assert ha.servicios == ["volume_mute", "volume_mute"]


@pytest.mark.asyncio
async def test_quitar_el_silencio_a_una_TV_que_ya_tenia_sonido_no_dice_que_lo_quito(tmp_path):
    ha = _HAVolumen()
    sis, _ = _aura(tmp_path, ha)

    r = await _di(sis, "quita el silencio de la tele de la sala")

    assert (
        "ya veía" in r["say"]
        and "con sonido" in r["say"]
        and "no he cambiado nada" in r["say"]
        and "quité" not in r["say"]
    ), r["say"]
    assert ha.estados[SALA]["attributes"]["is_volume_muted"] is False


@pytest.mark.asyncio
async def test_que_hiciste_tras_subir_el_volumen_lo_recupera_sin_reejecutar(tmp_path):
    ha = _HAVolumen()
    sis, _ = _aura(tmp_path, ha)
    hecho = await _di(sis, "sube el volumen de la tele de la sala")

    r = await _di(sis, "¿qué hiciste?")

    assert hecho["say"] in r["say"] and ha.servicios == ["volume_up"], r["say"]


# ------------------------------------------------------------------------- no se da por hecho --


@pytest.mark.asyncio
async def test_si_el_volumen_no_cambia_no_se_da_por_hecho(tmp_path):
    ha = _HAVolumen(efecto=False)
    sis, _ = _aura(tmp_path, ha)

    r = await _di(sis, "sube el volumen de la tele de la sala")

    assert ha.servicios == ["volume_up"]
    assert "no cambió" in r["say"] and "comprobado" not in r["say"], r["say"]


@pytest.mark.asyncio
async def test_con_la_TV_apagada_no_se_envia_nada_y_se_dice(tmp_path):
    ha = _HAVolumen(sala="off")
    sis, _ = _aura(tmp_path, ha)

    r = await _di(sis, "sube el volumen de la tele de la sala")

    assert ha.servicios == [] and "apagad" in r["say"] and "comprobado" not in r["say"], r["say"]


@pytest.mark.asyncio
async def test_si_HA_no_expone_el_volumen_no_se_envia_porque_no_se_podria_comprobar(tmp_path):
    ha = _HAVolumen(expone=False)
    sis, _ = _aura(tmp_path, ha)

    r = await _di(sis, "sube el volumen de la tele de la sala")

    assert ha.servicios == [] and "comprobado" not in r["say"], r["say"]
    assert "comprobar" in r["say"], r["say"]


@pytest.mark.asyncio
async def test_si_HA_da_el_volumen_como_None_no_se_envia_nada(tmp_path):
    """Revisión ECC 2026-10-22 (MEDIO): la clave existe pero no hay número; antes daba TypeError TRAS enviar la orden."""
    ha = _HAVolumen(volumen=None)
    sis, _ = _aura(tmp_path, ha)

    r = await _di(sis, "sube el volumen de la tele de la sala")

    assert ha.servicios == [] and "comprobar" in r["say"] and "comprobado" not in r["say"], r["say"]


@pytest.mark.asyncio
async def test_si_tras_enviar_el_volumen_deja_de_poder_leerse_no_se_da_por_hecho(tmp_path):
    ha = _HAVolumen(pierde=True)
    sis, _ = _aura(tmp_path, ha)

    r = await _di(sis, "sube el volumen de la tele de la sala")

    assert ha.servicios == ["volume_up"] and "no pude leer el volumen" in r["say"], r["say"]
    assert "comprobado" not in r["say"] and "None" not in r["say"], r["say"]


@pytest.mark.asyncio
async def test_sin_decir_que_TV_con_dos_encendidas_pregunta_cual_y_no_actua(tmp_path):
    ha = _HAVolumen()
    sis, _ = _aura(tmp_path, ha)

    r = await _di(sis, "sube el volumen")

    assert ha.servicios == [] and "cuál" in r["say"], r["say"]


@pytest.mark.asyncio
async def test_con_PARADA_no_se_cambia_el_volumen(tmp_path):
    ha = _HAVolumen()
    sis, _ = _aura(tmp_path, ha)
    open(os.path.join(str(tmp_path), "KILL"), "w").close()

    r = await _di(sis, "sube el volumen de la tele de la sala")

    assert ha.servicios == [] and _volumen(ha) == 0.2 and "kill switch" in r["say"], r["say"]


@pytest.mark.asyncio
async def test_con_HA_caido_al_enviar_no_se_da_por_ejecutada(tmp_path):
    ha = _HAVolumen(servicio_cae=True)
    sis, _ = _aura(tmp_path, ha)

    r = await _di(sis, "sube el volumen de la tele de la sala")

    assert "no la doy por ejecutada" in r["say"] and "comprobado" not in r["say"], r["say"]


@pytest.mark.asyncio
async def test_con_la_credencial_rechazada_lo_dice_y_no_finge(tmp_path):
    ha = _HAVolumen(credencial_mala=True)
    sis, _ = _aura(tmp_path, ha)

    r = await _di(sis, "sube el volumen de la tele de la sala")

    assert "credencial" in r["say"] and "comprobado" not in r["say"], r["say"]


# ------------------------------------------------------------------------------------- por voz --


@pytest.mark.asyncio
async def test_por_VOZ_el_volumen_sigue_fuera_de_la_opcion_C_y_no_se_propone_ni_ejecuta(tmp_path):
    ha = _HAVolumen()
    sis, espia = _aura(tmp_path, ha)

    r = await _di(sis, "sube el volumen de la tele", voz=True, activado=True)
    llamadas_al_modelo = espia.llamadas
    r2 = await _di(sis, "sí", voz=True, activado=True)

    assert ha.servicios == [] and "¿Lo hago?" not in r["say"], r["say"]
    assert "volumen" in r["say"] and "escríbemelo" in r["say"], r["say"]
    assert llamadas_al_modelo == 0, "el modelo decidió sobre la orden hablada"
    # El «sí» no tiene propuesta que confirmar: puede contestarlo la conversación, pero nada se ejecuta.
    assert "comprobado" not in r2["say"] and ha.servicios == []


# -------------------------------------------------- nombre humano como alias del dispositivo --


@pytest.mark.asyncio
async def test_control_apagar_la_tele_de_la_sala_por_texto_ya_no_es_ambiguo_con_dos_TV(tmp_path):
    """«la tele de la sala» resuelve por el nombre humano que AURA ya conoce (`NOMBRE_HUMANO_DE_VOZ`), no por adivinar."""
    ha = _HAVolumen()
    sis, _ = _aura(tmp_path, ha)

    r = await _di(sis, "apaga la tele de la sala")

    assert ha.estados[SALA]["state"] == "off" and ha.estados[TV20]["state"] == "on", r["say"]
    assert "Home Assistant ve" in r["say"], r["say"]


@pytest.mark.asyncio
async def test_un_alias_que_no_casa_no_elige_ninguna_TV(tmp_path):
    ha = _HAVolumen()
    sis, _ = _aura(tmp_path, ha)

    r = await _di(sis, "sube el volumen de la tele del cuarto")

    assert ha.servicios == [] and "comprobado" not in r["say"], r["say"]


# ------------------------------------------------- camino del MODELO: el efecto también se exige --


class _ModeloQuePideVolumen:
    """Proveedor falso que propone subir el volumen de la TV nombrada por su nombre visible en HA."""

    name = "modelo-volumen"

    async def infer(self, prompt, *a, **k):
        return (
            '{"intent":"volumen","action":"subir_volumen",'
            '"args":{"device":"Tv sala fmilia medina"},"say":"Hecho, subí el volumen."}'
        )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("efecto", "esperado", "prohibido"), [(True, "comprobado", "no cambió"), (False, "no cambió", "comprobado")]
)
async def test_si_el_MODELO_propone_subir_el_volumen_solo_se_da_por_hecho_si_se_comprobo(
    tmp_path, efecto, esperado, prohibido
):
    """Mutante M14 (volumen-tv): por el camino del modelo, la frase del modelo («Hecho…») no puede sustituir a la
    verificación del adaptador."""
    ha = _HAVolumen(efecto=efecto)
    sis, _ = _aura(tmp_path, ha)
    sis.orquestador.router.providers = [_ModeloQuePideVolumen()]

    r = await _di(sis, "oye, pon más alto el volumen de la tv sala fmilia medina")

    assert ha.servicios == ["volume_up"], (ha.servicios, r["say"])
    assert esperado in r["say"] and prohibido not in r["say"] and "[accion" not in r["say"], r["say"]


# ------------------------------------------- errores de hogar en lenguaje humano (2026-10-22) --


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("frase", "ha_kw", "humano", "motivo"),
    [
        ("sube el volumen de la tele de la sala", {"sala": "off"}, "No he podido subir el volumen", "apagada"),
        ("silencia la tele de la sala", {"expone": False}, "No he podido silenciar", "comprobar"),
        ("apaga la tele de la sala", {"servicio_cae": True}, "No he podido apagarlo", "no la doy por ejecutada"),
        ("sube el volumen", {}, "No he podido subir el volumen", "cuál"),
    ],
)
async def test_un_error_de_hogar_se_dice_sin_nombres_tecnicos_y_con_su_motivo(tmp_path, frase, ha_kw, humano, motivo):
    """Medido `[EJEC]` contra el HA real (2026-10-22): «Intenté ejecutar «subir_volumen» y no pude: el adaptador rechazo
    la operacion: …». El motivo era cierto; la forma, técnica. Se conserva el motivo entero y se dice qué no se hizo."""
    ha = _HAVolumen(**ha_kw)
    sis, _ = _aura(tmp_path, ha)

    r = await _di(sis, frase)

    assert r["say"].startswith(humano) and motivo in r["say"], r["say"]
    assert "«" not in r["say"].split(":")[0] and "el adaptador rechazo" not in r["say"], r["say"]


@pytest.mark.asyncio
async def test_con_PARADA_el_hogar_dice_que_no_lo_hizo_y_por_que(tmp_path):
    ha = _HAVolumen()
    sis, _ = _aura(tmp_path, ha)
    open(os.path.join(str(tmp_path), "KILL"), "w").close()

    r = await _di(sis, "baja el volumen de la tele de la sala")

    assert r["say"].startswith("No he podido bajar el volumen") and "kill switch" in r["say"], r["say"]
    assert ha.servicios == []


@pytest.mark.asyncio
async def test_control_un_error_que_NO_es_de_hogar_conserva_su_forma(tmp_path):
    sis, _ = _aura(tmp_path, _HAVolumen())

    r = await _di(sis, f"lee el archivo {tmp_path}/no_existe.txt")

    assert "No he podido" not in r["say"], r["say"]


@pytest.mark.asyncio
async def test_control_una_DETENCION_que_no_es_de_hogar_conserva_su_forma(tmp_path):
    """Control (code-reviewer 2026-10-22): la redacción humana es SOLO para el hogar; lo demás sigue diciendo la capacidad."""
    sis, _ = _aura(tmp_path, _HAVolumen())
    open(os.path.join(str(tmp_path), "KILL"), "w").close()

    r = await _di(sis, f"lista el directorio {tmp_path}")

    assert r["say"].startswith("No he ejecutado «listar_directorio»") and "kill switch" in r["say"], r["say"]
