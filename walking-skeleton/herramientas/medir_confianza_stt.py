"""Medición de la confianza del STT real (DP-VOZ-ACCION §8 C4 / §5). HERRAMIENTA DE DESARROLLO, no runtime.

Pregunta: ¿qué `no_speech_prob` y `avg_logprob` produce Whisper cuando transcribe una orden REAL y cuáles
cuando FABRICA una orden o un «sí» a partir de silencio, ruido, un tono, voz cortada o frases ajenas? Con
eso se fijan `UMBRAL_NO_HABLA` y `UMBRAL_LOGPROB` con datos y no a ojo.

TODO EN MEMORIA: el audio se sintetiza (Piper), se mezcla y se transcribe sin tocar el disco; solo se
guardan métricas y el texto transcrito. El micrófono (opcional) se captura con `parecord --raw` a stdout.
Se usa el MISMO camino que AURA (`WhisperPiperVoice._stt_sync`: margen de silencio, vocabulario, `sin_eco`):
se sustituye únicamente `faster_whisper.decode_audio` para que entregue el array en memoria.

    HF_HUB_CACHE=/media/majo1230/AURORA_EXT/hf_cache/hub HF_HUB_OFFLINE=1 \\
      python3 -m herramientas.medir_confianza_stt [--sin-mic] [--salida DIR]
"""

from __future__ import annotations

import argparse
import gc
import io
import json
import os
import subprocess
import wave
from pathlib import Path
from typing import Any

import numpy as np

from aura_skeleton.adapters.voice_real import WhisperPiperVoice
from aura_skeleton.core import hogar

MUESTREO = 16000
VOZ_PIPER = "/media/majo1230/AURORA_EXT/piper_voices/es_MX-ald-medium.onnx"
SALIDA = Path(__file__).resolve().parents[2] / "milestones/m3-entry/evidencia-voz-accion"
# (frase, tipo esperado): "orden" = reconocer() debe dar esa capacidad; "si"/"no" = confirmacion().
ORDENES = [
    ("apaga la televisión", ("apagar_dispositivo", "orden")),
    ("enciende la televisión", ("encender_dispositivo", "orden")),
    ("apaga la tele de la sala", ("apagar_dispositivo", "orden")),
    ("sí", (True, "si")),
    ("no", (False, "no")),
]
AJENAS = ["qué hora es", "mañana llueve"]
SNRS = (None, 20, 10, 5)
VARIANTES_VOZ = (0.9, 1.0, 1.15)  # length_scale de Piper: tres «hablantes» distintos por frase
SEMILLAS_RUIDO = (1,)


def _sintetizar(piper: Any, texto: str, longitud: float) -> np.ndarray:
    import faster_whisper
    from piper import SynthesisConfig

    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        piper.synthesize_wav(texto, w, syn_config=SynthesisConfig(length_scale=longitud))
    buf.seek(0)
    return faster_whisper.decode_audio(buf, sampling_rate=MUESTREO)  # BytesIO: sin disco


def _ruido(color: str, n: int, rng: np.random.Generator) -> np.ndarray:
    blanco = rng.standard_normal(n).astype(np.float32)
    if color == "blanco":
        return blanco
    espectro = np.fft.rfft(blanco)
    espectro /= np.sqrt(np.maximum(np.arange(len(espectro)), 1))  # 1/f en potencia
    return np.fft.irfft(espectro, n).astype(np.float32)


def _mezclar(voz: np.ndarray, snr_db: int, color: str, rng: np.random.Generator) -> np.ndarray:
    ruido = _ruido(color, len(voz), rng)
    p_voz = float(np.mean(voz**2))
    ruido *= np.sqrt(p_voz / 10 ** (snr_db / 10) / max(float(np.mean(ruido**2)), 1e-12))
    return (voz + ruido).astype(np.float32)


def _transcribir(stt: WhisperPiperVoice, audio: np.ndarray) -> tuple[str, dict[str, float] | None]:
    import faster_whisper

    original = faster_whisper.decode_audio
    faster_whisper.decode_audio = lambda *_a, **_k: audio  # type: ignore[assignment]
    try:
        texto = stt._stt_sync("<memoria>")
    finally:
        faster_whisper.decode_audio = original  # type: ignore[assignment]
    return texto, stt.ultima_confianza


def _clasificar(texto: str, esperado: tuple[Any, str] | None) -> dict[str, Any]:
    orden = hogar.reconocer(texto)
    conf = hogar.confirmacion(texto)
    real_ok = False
    if esperado is not None:
        valor, tipo = esperado
        real_ok = (orden is not None and orden[0] == valor) if tipo == "orden" else conf is valor
    return {
        "orden": orden is not None,
        "si": conf is True,
        "no": conf is False,
        "fabricado": orden is not None or conf is True,  # una orden o un «sí» que nadie dijo
        "fiel": real_ok,
    }


def _capturar_mic(segundos: int = 3) -> np.ndarray | None:
    try:
        r = subprocess.run(
            ["parecord", "--raw", "--format=s16le", f"--rate={MUESTREO}", "--channels=1"],
            capture_output=True,
            timeout=segundos,
            check=False,
        )
        datos = r.stdout
    except subprocess.TimeoutExpired as e:
        datos = e.stdout or b""
    except OSError:
        return None
    if len(datos) < MUESTREO:
        return None
    return np.frombuffer(datos[: len(datos) // 2 * 2], dtype=np.int16).astype(np.float32) / 32768.0


def _casos(piper: Any, con_mic: bool):
    """Genera (grupo, etiqueta, audio, esperado) UNO a UNO para no acumular audio en memoria."""
    for frase, esperado in ORDENES:
        for lon in VARIANTES_VOZ:
            voz = _sintetizar(piper, frase, lon)
            for snr in SNRS:
                if snr is None:
                    yield "real", f"{frase}|limpio", voz, esperado
                    continue
                for color in ("blanco", "rosa"):
                    for sem in SEMILLAS_RUIDO:
                        rng = np.random.default_rng(sem * 100 + snr)
                        yield "real", f"{frase}|{color}{snr}dB", _mezclar(voz, snr, color, rng), esperado
    for seg in (1.5, 3.0):
        yield "no_orden", f"silencio|{seg}s", np.zeros(int(MUESTREO * seg), np.float32), None
    for color in ("blanco", "rosa"):
        for amp in (0.002, 0.02, 0.2):
            for sem in (1,):
                r = np.random.default_rng(sem)
                n = _ruido(color, MUESTREO * 2, r)
                n *= amp / max(float(np.std(n)), 1e-9)
                yield "no_orden", f"ruido-{color}|amp{amp}", n.astype(np.float32), None
    t = np.arange(MUESTREO * 2) / MUESTREO
    for hz in (440, 1000, 200):
        yield "no_orden", f"tono|{hz}Hz", (0.3 * np.sin(2 * np.pi * hz * t)).astype(np.float32), None
    for lon in VARIANTES_VOZ:
        for frase, _ in ORDENES[:3]:
            yield "no_orden", f"voz-cortada-0.5s|{frase}", _sintetizar(piper, frase, lon)[: MUESTREO // 2], None
        for frase in AJENAS:
            yield "no_orden", f"frase-ajena|{frase}", _sintetizar(piper, frase, lon), None
    if con_mic:
        for i in range(4):
            mic = _capturar_mic()
            if mic is not None:
                yield "mic_real", f"ambiente|toma{i}", mic, None


def _dist(xs: list[float]) -> dict[str, float | int]:
    if not xs:
        return {"n": 0}
    a = np.array(xs)
    return {
        "n": len(xs),
        "min": round(float(a.min()), 3),
        "p10": round(float(np.percentile(a, 10)), 3),
        "mediana": round(float(np.median(a)), 3),
        "p90": round(float(np.percentile(a, 90)), 3),
        "max": round(float(a.max()), 3),
    }


def _resumen(filas: list[dict[str, Any]]) -> dict[str, Any]:
    dist = _dist

    con = [f for f in filas if f["no_speech_prob"] is not None]
    fab = [f for f in con if f["fabricado"]]
    fiel = [f for f in con if f["grupo"] == "real" and f["fiel"]]
    pasa_antes = {"fabricados": sum(f["fabricado"] for f in filas if f["grupo"] != "real")}
    out: dict[str, Any] = {
        "por_grupo": {g: sum(f["grupo"] == g for f in filas) for g in ("real", "no_orden", "mic_real")},
        "fabricados_sin_umbral": pasa_antes["fabricados"],
        "no_orden_total": sum(f["grupo"] != "real" for f in filas),
        "dist_orden_real_fiel": {"no_speech_prob": dist([f["no_speech_prob"] for f in fiel]),
                                 "avg_logprob": dist([f["avg_logprob"] for f in fiel])},
        "dist_fabricado": {"no_speech_prob": dist([f["no_speech_prob"] for f in fab if f["grupo"] != "real"]),
                           "avg_logprob": dist([f["avg_logprob"] for f in fab if f["grupo"] != "real"])},
    }  # fmt: skip
    out["por_tipo"] = _por_tipo(filas)
    out["umbrales"] = _barrido(filas)
    return out


RECOMENDADO = (0.15, -1.2)  # (UMBRAL_NO_HABLA, UMBRAL_LOGPROB): ver el resumen para su justificación medida


def _tipo(f: dict[str, Any]) -> str:
    """Clase de entrada para las distribuciones: lo que ES, no lo que Whisper transcribió."""
    if f["grupo"] == "mic_real":
        return "mic_real"
    if f["grupo"] == "real":
        return "orden_o_si_real" + ("_entendido" if f["fiel"] else "_mal_entendido")
    etiqueta = f["etiqueta"].split("|")[0]
    return "voz_no_orden" if etiqueta.startswith(("voz-cortada", "frase-ajena")) else "no_habla_sintetico"


def _por_tipo(filas: list[dict[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for tipo in sorted({_tipo(f) for f in filas}):
        sub = [f for f in filas if _tipo(f) == tipo and f["no_speech_prob"] is not None]
        a_, b_ = RECOMENDADO
        out[tipo] = {
            "n": len(sub),
            "no_speech_prob": _dist([f["no_speech_prob"] for f in sub]),
            "avg_logprob": _dist([f["avg_logprob"] for f in sub]),
            "pasan_el_filtro_recomendado": sum(_acepta(f, a_, b_) for f in sub),
            "fabricados": sum(f["fabricado"] for f in sub),
            "fabricados_que_pasan": sum(f["fabricado"] and _acepta(f, a_, b_) for f in sub),
        }
    return out


def _acepta(f: dict[str, Any], u_nsp: float, u_lp: float) -> bool:
    if f["no_speech_prob"] is None:
        return False  # sin cifras no hay transcripción que dejar pasar
    return bool(f["no_speech_prob"] <= u_nsp and f["avg_logprob"] >= u_lp)


def _barrido(filas: list[dict[str, Any]]) -> dict[str, Any]:
    nsps = [x / 100 for x in range(5, 101, 5)]
    lps = [-x / 10 for x in range(2, 21, 1)]
    falsos = [f for f in filas if f["grupo"] != "real" and f["fabricado"]]
    reales = [f for f in filas if f["grupo"] == "real" and f["fiel"]]
    candidatos = []
    for a in nsps:
        for b in lps:
            if any(_acepta(f, a, b) for f in falsos):
                continue
            por_snr: dict[str, str] = {}
            for etiqueta in ("limpio", "20dB", "10dB", "5dB"):
                tot = [f for f in filas if f["grupo"] == "real" and f["etiqueta"].endswith(etiqueta)]
                ok = sum(1 for f in tot if f["fiel"] and _acepta(f, a, b))
                por_snr[etiqueta] = f"{ok}/{len(tot)}"
            ok_total = sum(1 for f in reales if _acepta(f, a, b))
            candidatos.append({"UMBRAL_NO_HABLA": a, "UMBRAL_LOGPROB": b, "ordenes_conservadas": ok_total,
                               "de": len(reales), "por_snr": por_snr})  # fmt: skip
    candidatos.sort(key=lambda c: (-c["ordenes_conservadas"], -c["UMBRAL_LOGPROB"]))
    # Cada métrica por separado, para decir cuál aporta.
    solo: dict[str, Any] = {}
    for nombre, rejilla in (("solo_no_habla", [(a, -99.0) for a in nsps]), ("solo_logprob", [(2.0, b) for b in lps])):
        mejores = [(a, b) for a, b in rejilla if not any(_acepta(f, a, b) for f in falsos)]
        solo[nombre] = max(((sum(1 for f in reales if _acepta(f, a, b)), a, b) for a, b in mejores), default=None)
    return {"fabricados_totales": len(falsos), "mejores_con_cero_fabricados": candidatos[:5],
            "sin_separacion_limpia": not candidatos, "cada_metrica_sola": solo}  # fmt: skip


def medir(salida: Path, con_mic: bool) -> dict[str, Any]:
    piper_mod = __import__("piper")
    piper = piper_mod.PiperVoice.load(VOZ_PIPER)
    stt = WhisperPiperVoice(whisper_model=os.environ.get("AURA_WHISPER_MODEL", "base"), piper_voice=VOZ_PIPER)
    filas: list[dict[str, Any]] = []
    import sys
    import time

    # Punto de control (solo métricas y texto): una transcripción de ruido puede tardar minutos y una
    # interrupción no debe costar toda la medición. Se reanuda saltando los casos ya medidos.
    parcial = salida / ".medicion-parcial.jsonl"
    salida.mkdir(parents=True, exist_ok=True)
    hechos = [json.loads(x) for x in parcial.read_text(encoding="utf-8").splitlines()] if parcial.exists() else []
    for i, (grupo, etiqueta, audio, esperado) in enumerate(_casos(piper, con_mic)):
        if i < len(hechos):
            filas.append(hechos[i])
            continue
        t0 = time.monotonic()
        try:
            texto, conf = _transcribir(stt, audio)
        except Exception as e:  # noqa: BLE001 - un caso roto no tumba la medición, se registra
            texto, conf = f"<error: {type(e).__name__}>", None
        fila = {"grupo": grupo, "etiqueta": etiqueta, "texto": texto,
                "no_speech_prob": None if conf is None else round(conf["no_speech_prob"], 4),
                "avg_logprob": None if conf is None else round(conf["avg_logprob"], 4),
                **_clasificar(texto, esperado)}  # fmt: skip
        filas.append(fila)
        with parcial.open("a", encoding="utf-8") as p:
            p.write(json.dumps(fila, ensure_ascii=False) + "\n")
        print(f"[{len(filas)}] {time.monotonic() - t0:.1f}s {etiqueta} -> {texto!r}", file=sys.stderr, flush=True)
    gc.collect()
    resumen = _resumen(filas)
    (salida / "medicion-confianza-stt.json").write_text(
        json.dumps({"modelo": stt._wm_name, "resumen": resumen, "casos": filas}, ensure_ascii=False, indent=1),
        encoding="utf-8",
    )
    return resumen


def reanalizar(salida: Path) -> dict[str, Any]:
    """Recalcula clasificación y umbrales sobre las transcripciones ya medidas (sin volver a transcribir)."""
    ruta = salida / "medicion-confianza-stt.json"
    datos = json.loads(ruta.read_text(encoding="utf-8"))
    esperado_de = dict(ORDENES)
    filas = []
    for f in datos["casos"]:
        esperado = esperado_de.get(f["etiqueta"].split("|")[0]) if f["grupo"] == "real" else None
        filas.append({**f, **_clasificar(f["texto"], esperado)})
    resumen = _resumen(filas)
    ruta.write_text(
        json.dumps({"modelo": datos["modelo"], "resumen": resumen, "casos": filas}, ensure_ascii=False, indent=1),
        encoding="utf-8",
    )
    return resumen


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--reanalizar", action="store_true", help="recalcula sobre el JSON existente, sin transcribir")
    ap.add_argument("--sin-mic", action="store_true")
    ap.add_argument("--salida", type=Path, default=SALIDA)
    args = ap.parse_args()
    if args.reanalizar:
        print(json.dumps(reanalizar(args.salida), ensure_ascii=False, indent=1))
        return 0
    print(json.dumps(medir(args.salida, not args.sin_mic), ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
