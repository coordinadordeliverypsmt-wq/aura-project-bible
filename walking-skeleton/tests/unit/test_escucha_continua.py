"""Escucha continua con palabra de activación (Bible 6.2) — campaña de presencia, 2026-09-27.

Medido antes de construirlo `[EJEC]` con voz real sintetizada en HC-1 y el modelo Vosk pequeño de
español: gramática con distractores fonéticos («ahora», «hora»…) -> 7/10 llamadas detectadas y 14/16
frases ajenas rechazadas; los 2 falsos positivos eran «la aurora boreal…», que contiene la palabra.
Exigir que «Aurora» ABRA la frase (vocativo) los elimina. Tiempo real: ~0,1-0,2 s por segundo de audio.

La Bible autoriza la escucha continua procesada en LOCAL, y exige que fuera de la palabra de
activación no se transmita nada (6.2 §46). Aquí además nada se escribe a disco.
"""

from __future__ import annotations

import io
import json

import pytest

from aura_skeleton.adapters.escucha import OidoContinuo, es_llamada

# --------------------------------------------------------------- qué cuenta como una llamada --


@pytest.mark.parametrize("texto", ["aurora", "oye aurora", "hola aurora", "Oye Aurora"])
def test_reconoce_una_llamada_por_su_nombre(texto):
    assert es_llamada(texto)


@pytest.mark.parametrize(
    "texto",
    [
        "",
        "[unk]",
        "ahora",
        "la aurora",
        "la aurora aurora",
        "que hora es",
        "me la aurora",
        "aurora vamos comer",
        "ora vamos comer",
        "aurora que hora es",
        "hola que tal aurora",
    ],
)
def test_NO_despierta_si_la_frase_no_es_exactamente_una_llamada(texto):
    """Medido por el aire: «ahora vamos a comer» se oye «ora vamos comer»; «la aurora boreal»
    menciona el nombre. Ninguna es una llamada. La orden va DESPUÉS del «¿Sí?»."""
    assert not es_llamada(texto)


# ------------------------------------------------------------------ el oído, con dobles --


class _Reconocedor:
    """Doble de Vosk: cada bloque de audio es una «frase» ya reconocida, en el orden dado."""

    def __init__(self, frases):
        self._frases = list(frases)
        self.bloques = 0

    def AcceptWaveform(self, datos):
        self.bloques += 1
        return bool(self._frases)

    def Result(self):
        return json.dumps({"text": self._frases.pop(0) if self._frases else ""})

    def FinalResult(self):
        return json.dumps({"text": ""})


def _oido(frases, n_bloques=10):
    flujo = io.BytesIO(b"\x00\x00" * 2000 * n_bloques)
    rec = _Reconocedor(frases)
    return OidoContinuo(abrir_flujo=lambda: flujo, reconocedor=lambda: rec, bloque=4000), rec


def test_espera_hasta_oir_su_nombre():
    oido, _rec = _oido(["que hora es", "la aurora", "oye aurora"])
    assert oido.esperar_llamada() is True


def test_si_el_flujo_se_acaba_sin_llamada_no_despierta():
    oido, _rec = _oido(["hola", "que tal"], n_bloques=2)
    assert oido.esperar_llamada() is False


def test_el_audio_escuchado_NO_se_escribe_a_disco(tmp_path, monkeypatch):
    """6.2: fuera de la palabra de activación nada sale del procesamiento local; aquí ni siquiera
    toca el disco. Se vigila cualquier apertura de fichero en escritura durante la escucha."""
    import builtins

    abiertos = []
    original = builtins.open

    def _espia(f, modo="r", *a, **k):
        if any(c in modo for c in "wax+"):
            abiertos.append(f)
        return original(f, modo, *a, **k)

    monkeypatch.setattr(builtins, "open", _espia)
    oido, _ = _oido(["hola", "aurora"])
    oido.esperar_llamada()
    assert abiertos == [], f"la escucha escribio en disco: {abiertos}"


def test_comprobar_sin_modelo_lo_declara(tmp_path):
    from aura_skeleton.adapters.microfono import DispositivoNoDisponible

    oido = OidoContinuo(modelo=str(tmp_path / "no-existe"))
    with pytest.raises(DispositivoNoDisponible, match="modelo"):
        oido.comprobar()


def test_al_dejar_de_escuchar_el_proceso_del_microfono_TERMINA():
    """Cerrar solo la tubería dejaba `parecord` vivo con el micrófono abierto grabando hacia nadie."""
    from aura_skeleton.adapters.escucha import _FlujoDelMicrofono

    class _Proceso:
        def __init__(self, *a, **k):
            self.stdout = io.BytesIO(b"")
            self.terminado = False

        def terminate(self):
            self.terminado = True

        def wait(self, timeout=None):
            return 0

    flujo = _FlujoDelMicrofono(lanzar=_Proceso)
    oido = OidoContinuo(abrir_flujo=lambda: flujo, reconocedor=lambda: _Reconocedor([]))

    assert oido.esperar_llamada() is False
    assert flujo._proceso.terminado, "el microfono siguio abierto tras dejar de escuchar"


# ------------------------------------------------ el bucle continuo en la consola (`--continuo`) --

import asyncio  # noqa: E402

from aura_skeleton import __main__ as principal  # noqa: E402


class _Oido:
    def __init__(self, llamadas):
        self._llamadas = list(llamadas)

    def esperar_llamada(self):
        return self._llamadas.pop(0)


class _Mic:
    def __init__(self):
        self.eventos: list[str] = []

    def escuchar(self, tid):
        self.eventos.append("escuchar")
        return "/tmp/aura/orden.wav"

    def reproducir(self, ruta):
        self.eventos.append(f"reproducir:{ruta}")

    def descartar(self, ruta):
        self.eventos.append(f"descartar:{ruta}")


class _Voz:
    async def tts(self, texto, tid):
        return "/tmp/aura/acuse.wav"


class _Orq:
    voice = _Voz()


class _Sistema:
    orquestador = _Orq()


def test_al_oir_su_nombre_acusa_escucha_responde_y_no_guarda_nada(monkeypatch):
    async def _turno(orq, texto, tid, activado=False):
        assert texto == "/tmp/aura/orden.wav"
        # C1 (DP-VOZ-ACCION §8): el turno posterior a la palabra de activación lleva `activado=True`.
        assert activado is True, "la escucha continua no declaró la activación"
        return {"say": "Son las tres.", "audio": "/tmp/aura/resp.wav"}

    monkeypatch.setattr(principal, "_turno", _turno)
    monkeypatch.setattr(principal, "_informe", lambda _s: "")
    mic = _Mic()

    codigo = asyncio.run(principal._escuchar_continuo(_Sistema(), mic, _Oido([True, False]), telemetria=True))

    assert codigo == 1  # el flujo se acabó
    assert mic.eventos == [
        # «¿Sí?»: frase CONSTANTE de AURA, se sintetiza una vez y se reutiliza (perfil de latencia 2026-10-04,
        # ~2 s por llamada). No es voz del usuario: no se descarta. Lo del usuario sí, abajo.
        "reproducir:/tmp/aura/acuse.wav",
        "escuchar",  # la orden
        "reproducir:/tmp/aura/resp.wav",  # la respuesta
        "descartar:/tmp/aura/orden.wav",
        "descartar:/tmp/aura/resp.wav",  # nada queda en disco
    ], mic.eventos


def test_sin_llamada_no_graba_ni_ejecuta_nada(monkeypatch):
    llamado = []

    async def _turno(*a):
        llamado.append(a)
        return {"say": ""}

    monkeypatch.setattr(principal, "_turno", _turno)
    monkeypatch.setattr(principal, "_informe", lambda _s: "")
    mic = _Mic()

    asyncio.run(principal._escuchar_continuo(_Sistema(), mic, _Oido([False]), telemetria=True))

    assert mic.eventos == [] and llamado == [], "sin oir su nombre, AURA grabo o actuo"


def test_en_escucha_continua_la_telemetria_se_saca_de_la_pantalla_por_defecto(monkeypatch):
    """Encontrado por el mutante CP-M26, que sobrevivía: el modo continuo copia la política de
    `_conversar` (telemetría registrada pero no pintada) y ninguna prueba lo fijaba."""
    from aura_skeleton import observability as obs

    visto = []
    monkeypatch.setattr(obs, "configurar_salida", lambda destino: visto.append(destino))
    monkeypatch.setattr(principal, "_informe", lambda _s: "")

    asyncio.run(principal._escuchar_continuo(_Sistema(), _Mic(), _Oido([False]), telemetria=False))

    assert visto == [None], "la telemetria sigue saliendo en la pantalla durante la escucha"


def test_el_modelo_se_carga_UNA_vez_y_no_en_cada_escucha(monkeypatch):
    """Encontrado en la demo física `[EJEC]`: el modelo Vosk se recargaba en cada `esperar_llamada`
    (varios segundos leyendo de la USB) y AURA quedaba SORDA justo después de cada conversación:
    la persona dijo «Oye Aurora» y no había nadie escuchando."""
    import sys
    import types

    cargas = []

    class _Modelo:
        def __init__(self, ruta):
            cargas.append(ruta)

    falso = types.SimpleNamespace(
        Model=_Modelo, SetLogLevel=lambda *_: None, KaldiRecognizer=lambda *a: _Reconocedor([])
    )
    monkeypatch.setitem(sys.modules, "vosk", falso)
    oido = OidoContinuo(modelo="/modelo", abrir_flujo=lambda: io.BytesIO(b""))

    oido.preparar()
    oido.esperar_llamada()
    oido.esperar_llamada()

    assert cargas == ["/modelo"], f"el modelo se cargo {len(cargas)} veces"


class _ReconocedorSinSilencio:
    """Ruido CONTINUO: `AcceptWaveform` nunca cierra frase (nunca hay silencio); el nombre solo aparece
    en el resultado PARCIAL. Reproduce [EJEC] la condición «TV encendida»: sin pausa, la frase no cierra."""

    def __init__(self, parcial, cierra_en=None):
        self._parcial = parcial
        self._cierra_en = cierra_en  # texto final si en algún bloque SÍ cerrara (None = nunca cierra)
        self.bloques = 0

    def AcceptWaveform(self, datos):
        self.bloques += 1
        return self._cierra_en is not None and self.bloques >= 3

    def Result(self):
        return json.dumps({"text": self._cierra_en or ""})

    def PartialResult(self):
        return json.dumps({"partial": self._parcial})

    def FinalResult(self):
        return json.dumps({"text": ""})


def _oido_ruido(rec, n_bloques=6):
    flujo = io.BytesIO(b"\x00\x00" * 2000 * n_bloques)
    return OidoContinuo(abrir_flujo=lambda: flujo, reconocedor=lambda: rec, bloque=4000)


def test_activa_por_resultado_PARCIAL_cuando_el_ruido_impide_cerrar_la_frase():
    """Ruido continuo: la frase nunca cierra por silencio, pero el parcial ya dice «oye aurora».
    AURA debe activarse igualmente; si no, con la TV encendida se queda sorda."""
    rec = _ReconocedorSinSilencio("oye aurora")
    assert _oido_ruido(rec).esperar_llamada() is True


def test_CONTROL_un_parcial_que_NO_es_llamada_no_despierta():
    """La exactitud se mantiene con parciales: «la aurora boreal» en el parcial NO despierta (0 FP)."""
    rec = _ReconocedorSinSilencio("la aurora boreal", cierra_en=None)
    assert _oido_ruido(rec).esperar_llamada() is False


def test_CONTROL_parcial_incompleto_no_dispara_antes_de_tiempo():
    rec = _ReconocedorSinSilencio("oye")
    assert _oido_ruido(rec).esperar_llamada() is False


def test_parecord_pide_latencia_de_20_ms():
    """`[EJEC]` 2026-09-29: con la latencia por defecto `parecord` entrega el audio con ~2000 ms de
    retraso (P50 2002 ms); con `--latency-msec=20`, la ida y vuelta es P50 85 ms."""
    from aura_skeleton.adapters.escucha import _FlujoDelMicrofono

    ordenes = []

    class _P:
        def __init__(self, orden, **k):
            ordenes.append(orden)
            self.stdout = io.BytesIO(b"")

    _FlujoDelMicrofono(lanzar=_P)
    assert "--latency-msec=20" in ordenes[0]


def test_pulsar_para_hablar_y_el_teclado_NO_declaran_activacion(monkeypatch):
    """C1: solo la escucha continua, tras `esperar_llamada()`, pasa `activado=True`."""
    recibido = []

    async def _turno(orq, texto, tid, activado=False):
        recibido.append(activado)
        return {"say": "", "audio": None}

    monkeypatch.setattr(principal, "_turno", _turno)
    mic = _Mic()

    asyncio.run(principal._turno_de_voz(_Sistema(), mic, "t1"))  # pulsar para hablar
    asyncio.run(principal._turno_de_voz(_Sistema(), mic, "t2", "apaga la tele"))  # teclado

    assert recibido == [False, False], recibido
