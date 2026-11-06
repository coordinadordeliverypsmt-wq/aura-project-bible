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
    async def _turno(orq, texto, tid):
        assert texto == "/tmp/aura/orden.wav"
        return {"say": "Son las tres.", "audio": "/tmp/aura/resp.wav"}

    monkeypatch.setattr(principal, "_turno", _turno)
    monkeypatch.setattr(principal, "_informe", lambda _s: "")
    mic = _Mic()

    codigo = asyncio.run(principal._escuchar_continuo(_Sistema(), mic, _Oido([True, False]), telemetria=True))

    assert codigo == 1  # el flujo se acabó
    assert mic.eventos == [
        "reproducir:/tmp/aura/acuse.wav",
        "descartar:/tmp/aura/acuse.wav",  # «¿Sí?»
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


# ------------------------------------------- órdenes con fin de habla propio (CM1, 2026-09-29) --
#
# Vosk 0.3.45 no tiene `SetEndpointerDelays` y su endpointer espera 0,5-1 s de silencio `[EJEC]`.
# `escuchar_orden` decide el fin de habla con un VAD de energía; los tiempos se cuentan en MUESTRAS
# leídas (bloques de 20 ms), así que estas pruebas son deterministas.

import array  # noqa: E402

_BLOQUE_BYTES = 640  # 20 ms a 16 kHz s16le


def _bloque(amplitud: int) -> bytes:
    """Bloque de 20 ms: onda cuadrada de RMS = `amplitud`."""
    return array.array("h", [amplitud if i % 2 else -amplitud for i in range(320)]).tobytes()


def _ms(ms: int, amplitud: int) -> list[bytes]:
    return [_bloque(amplitud)] * (ms // 20)


class _FlujoFalso:
    def __init__(self, bloques, infinito_con=None):
        self._bloques = list(bloques)
        self._infinito = infinito_con
        self.lecturas = 0
        self.cerrado = False
        self.tamanos: list[int] = []

    def read(self, n):
        self.lecturas += 1
        self.tamanos.append(n)
        if self._bloques:
            return self._bloques.pop(0)
        return self._infinito if self._infinito is not None else b""

    def close(self):
        self.cerrado = True


class _RecLibre:
    def __init__(self, texto="que hora es"):
        self._texto = texto
        self.recibido = 0

    def AcceptWaveform(self, datos):
        self.recibido += len(datos)
        return True  # su valor NO debe decidir el fin de la orden

    def FinalResult(self):
        return json.dumps({"text": f"  {self._texto} "})


def _oido_orden(flujo, rec=None):
    rec = rec or _RecLibre()
    return OidoContinuo(abrir_flujo=lambda: flujo, reconocedor=lambda: None,
                        reconocedor_libre=lambda: rec), rec


def test_orden_corta_poco_despues_de_300_ms_de_silencio_y_devuelve_el_texto():
    flujo = _FlujoFalso(_ms(300, 50) + _ms(500, 6000) + _ms(2000, 50))
    oido, rec = _oido_orden(flujo)

    assert oido.escuchar_orden(fin_de_habla_ms=300) == "que hora es"  # strip() aplicado

    # 15 bloques previos + 25 de habla + 15 de silencio (300 ms) = 55 lecturas; margen de 2 bloques.
    assert 55 <= flujo.lecturas <= 57, flujo.lecturas  # control: esperar 1 s de silencio daría ~90
    assert set(flujo.tamanos) == {_BLOQUE_BYTES}
    assert rec.recibido == flujo.lecturas * _BLOQUE_BYTES, "todo el audio debe llegar a Vosk"
    assert flujo.cerrado


def test_solo_silencio_devuelve_vacio_tras_max_espera_y_cierra_el_flujo():
    flujo = _FlujoFalso([], infinito_con=_bloque(50))
    oido, _ = _oido_orden(flujo)

    assert oido.escuchar_orden(max_espera_s=1.0) == ""

    assert 50 <= flujo.lecturas <= 52, flujo.lecturas  # 1 s = 50 bloques; sin reloj de pared
    assert flujo.cerrado


def test_ruido_de_fondo_alto_no_impide_detectar_el_fin():
    flujo = _FlujoFalso(_ms(400, 1000) + _ms(500, 6000) + _ms(2000, 1000))
    oido, _ = _oido_orden(flujo)

    assert oido.escuchar_orden(fin_de_habla_ms=300) == "que hora es"

    # Umbral = 3 x 1000: el ruido (1000) no cuenta como habla ni impide el fin.
    assert flujo.lecturas <= 20 + 25 + 15 + 2, flujo.lecturas


def test_ruido_alto_sin_habla_no_se_toma_por_habla():
    flujo = _FlujoFalso([], infinito_con=_bloque(1000))
    oido, _ = _oido_orden(flujo)
    assert oido.escuchar_orden(max_espera_s=1.0) == ""  # control: umbral fijo bajo daría habla sin fin


def test_habla_sin_fin_se_corta_en_max_habla():
    flujo = _FlujoFalso(_ms(300, 50), infinito_con=_bloque(6000))
    oido, _ = _oido_orden(flujo)

    assert oido.escuchar_orden(max_habla_s=2.0) == "que hora es"

    # 15 previos + (3 de confirmación ya cuentan como habla) + hasta 2 s = 100 bloques.
    assert flujo.lecturas <= 15 + 100 + 3, flujo.lecturas
    assert flujo.cerrado


def test_una_pausa_breve_dentro_de_la_frase_no_corta():
    flujo = _FlujoFalso(_ms(300, 50) + _ms(300, 6000) + _ms(160, 50) + _ms(300, 6000) + _ms(2000, 50))
    oido, rec = _oido_orden(flujo)

    assert oido.escuchar_orden(fin_de_habla_ms=300) == "que hora es"

    # Cortó tras la SEGUNDA parte: 15 + 15 + 8 + 15 + 15 = 68 lecturas (+ margen).
    assert flujo.lecturas >= 68, f"cortó en la pausa de 160 ms ({flujo.lecturas} lecturas)"
    assert flujo.lecturas <= 70


def test_un_pico_breve_no_es_inicio_de_habla():
    """Un chasquido de 2 bloques no basta: el inicio exige 3 bloques seguidos por encima del umbral."""
    flujo = _FlujoFalso(_ms(300, 50) + _ms(40, 9000), infinito_con=_bloque(50))
    oido, rec = _oido_orden(flujo)
    assert oido.escuchar_orden(max_espera_s=1.0) == ""


def test_flujo_agotado_con_habla_devuelve_lo_reconocido():
    flujo = _FlujoFalso(_ms(300, 50) + _ms(200, 6000))
    oido, _ = _oido_orden(flujo)
    assert oido.escuchar_orden() == "que hora es"
    assert flujo.cerrado


def test_flujo_agotado_sin_habla_devuelve_vacio():
    flujo = _FlujoFalso(_ms(200, 50))
    oido, _ = _oido_orden(flujo)
    assert oido.escuchar_orden() == ""  # control: FinalResult sin habla devolvería el texto del doble
    assert flujo.cerrado


def test_el_flujo_se_cierra_aunque_el_reconocedor_falle():
    class _Roto(_RecLibre):
        def AcceptWaveform(self, datos):
            raise RuntimeError("vosk caído")

    flujo = _FlujoFalso(_ms(200, 50))
    oido, _ = _oido_orden(flujo, _Roto())
    with pytest.raises(RuntimeError):
        oido.escuchar_orden()
    assert flujo.cerrado


def test_escuchar_orden_no_escribe_a_disco(monkeypatch):
    import builtins

    abiertos = []
    original = builtins.open

    def _espia(f, modo="r", *a, **k):
        if any(c in modo for c in "wax+"):
            abiertos.append(f)
        return original(f, modo, *a, **k)

    monkeypatch.setattr(builtins, "open", _espia)
    oido, _ = _oido_orden(_FlujoFalso(_ms(300, 50) + _ms(300, 6000) + _ms(1000, 50)))
    oido.escuchar_orden()
    assert abiertos == []


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


# ---------------------------------- v2: gramática cerrada para órdenes conocidas (CM1, 2026-09-29) --
#
# `[EJEC]` por el aire: reconocimiento LIBRE («¿Cómo me llamo?» -> «tuvo media hago»; «Mauricio» -> «amor
# eso», que AURA llegó a GUARDAR como nombre) frente a GRAMÁTICA CERRADA (3/3, RTF 0,09-0,12). Con 300 ms
# de silencio «¿Cuál es mi color favorito?» se cortaba tras «cuál es» (4/4); con 450 ms, 0/2 cortes.


class _RecGramatica(_RecLibre):
    def __init__(self, texto):
        super().__init__(texto)
        self.finales = 0

    def FinalResult(self):
        self.finales += 1
        return json.dumps({"text": self._texto})


def _oido_dual(texto_gram, texto_libre="texto libre", gramatica=("como me llamo",)):
    libre, gram = _RecLibre(texto_libre), _RecGramatica(texto_gram)
    flujo = _FlujoFalso(_ms(300, 50) + _ms(500, 6000) + _ms(2000, 50))
    oido = OidoContinuo(abrir_flujo=lambda: flujo, reconocedor=lambda: None, reconocedor_libre=lambda: libre,
                        gramatica_orden=gramatica, reconocedor_gramatica=lambda: gram)
    return oido, libre, gram, flujo


def test_gana_la_gramatica_cuando_reconoce_algo_sin_unk():
    oido, libre, gram, _ = _oido_dual("cómo me llamo")
    assert oido.escuchar_orden() == "cómo me llamo"  # control: devolver siempre el libre daría «texto libre»


def test_gana_el_libre_si_la_gramatica_dice_unk():
    oido, *_ = _oido_dual("cómo [unk] llamo")
    assert oido.escuchar_orden() == "texto libre"  # control: fiarse de la gramática con [unk]


def test_gana_el_libre_si_la_gramatica_no_reconoce_nada():
    oido, *_ = _oido_dual("")
    assert oido.escuchar_orden() == "texto libre"


def test_los_dos_reconocedores_reciben_TODO_el_audio():
    oido, libre, gram, flujo = _oido_dual("cómo me llamo")
    oido.escuchar_orden()
    assert libre.recibido == gram.recibido == flujo.lecturas * _BLOQUE_BYTES > 0


def test_sin_gramatica_no_se_construye_el_reconocedor_de_gramatica():
    construido = []
    flujo = _FlujoFalso(_ms(300, 50) + _ms(500, 6000) + _ms(2000, 50))
    oido = OidoContinuo(abrir_flujo=lambda: flujo, reconocedor=lambda: None,
                        reconocedor_libre=lambda: _RecLibre("libre"),
                        reconocedor_gramatica=lambda: construido.append(1))
    assert oido.escuchar_orden() == "libre" and construido == []  # idéntico a v1


def test_el_fin_de_habla_por_defecto_es_450_ms():
    """Con 300 ms cortaría «cuál es | mi color favorito» (pausa interna típica de ~400 ms)."""
    flujo = _FlujoFalso(_ms(300, 50) + _ms(300, 6000) + _ms(400, 50) + _ms(300, 6000) + _ms(2000, 50))
    oido, _ = _oido_orden(flujo)
    oido.escuchar_orden()
    assert flujo.lecturas >= 15 + 15 + 20 + 15 + 22, flujo.lecturas  # no cortó en la pausa de 400 ms


def test_la_gramatica_se_pasa_a_vosk_con_las_tildes_literales(monkeypatch):
    """`json.dumps` por defecto escapa «ó» como \\u00f3 y Vosk ignora «cómo» («Ignoring word missing in
    vocabulary»): la orden deja de reconocerse. Debe ir con `ensure_ascii=False`."""
    import sys
    import types

    recibido = []
    falso = types.SimpleNamespace(
        KaldiRecognizer=lambda modelo, muestreo, gram=None: recibido.append((modelo, muestreo, gram)))
    monkeypatch.setitem(sys.modules, "vosk", falso)
    oido = OidoContinuo(modelo="m", gramatica_orden=["cómo me llamo", "cuál es mi color favorito"])
    oido._vosk_modelo = "MODELO"  # el modelo ya cargado: no se carga otro

    oido._reconocedor_vosk_gramatica()

    modelo, muestreo, gram = recibido[0]
    assert (modelo, muestreo) == ("MODELO", 16000)
    assert "cómo" in gram and "cuál" in gram and "\\u" not in gram
    assert json.loads(gram) == ["cómo me llamo", "cuál es mi color favorito", "[unk]"]
