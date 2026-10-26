"""Diagnóstico del STT con VOZ HUMANA (E2E físico 2026-10-04). Herramienta de DESARROLLO, no runtime.

Pregunta que responde con datos: ¿por qué Whisper deforma «enciende la televisión» dicha por una persona
(«Enciente», «No fiende», «telencia», «solución»)? Separa los factores que el pipeline aplica:
  A = pipeline actual (VAD 600 ms + vocabulario `initial_prompt`)
  B = VAD 600 ms, SIN vocabulario
  C = SIN VAD (grabación entera), con vocabulario  (el pipeline de antes del 2026-10-04)
  D = SIN VAD, SIN vocabulario
y mide la señal (RMS de la voz frente al ruido de fondo) con la ganancia del micrófono que haya.

No toca la TV, no pasa por AURA ni por Home Assistant. Graba cada frase SOLO EN MEMORIA (`parecord --raw` a
stdout) y guarda únicamente métricas y textos transcritos en el JSON de salida. Nunca audio.

Uso:  HF_HUB_CACHE=... HF_HUB_OFFLINE=1 python3 -m herramientas.diagnostico_stt_voz_humana SALIDA.json [N] [segundos]
"""

from __future__ import annotations

import json
import subprocess
import sys
import time

import numpy as np

from aura_skeleton.adapters import voice_real
from aura_skeleton.core import hogar

FRASE = __import__("os").environ.get("AURA_DIAG_FRASE", "enciende la televisión")
MUESTREO = voice_real._MUESTREO


def grabar(segundos: float) -> np.ndarray:
    crudo = subprocess.run(
        [
            "timeout",
            str(segundos),
            "parecord",
            "--raw",
            "--channels=1",
            f"--rate={MUESTREO}",
            "--format=s16le",
            "--latency-msec=20",
        ],
        capture_output=True,
        check=False,
    ).stdout
    return np.frombuffer(crudo, dtype=np.int16).astype(np.float32) / 32768.0


def pitido() -> None:
    """Señal audible de «habla ahora» (la persona no ve esta consola). Tono de 0,25 s generado en memoria."""
    t = np.arange(int(MUESTREO * 0.25)) / MUESTREO
    tono = (0.3 * np.sin(2 * np.pi * 880 * t) * 32767).astype(np.int16).tobytes()
    subprocess.run(["pacat", "--raw", "--channels=1", f"--rate={MUESTREO}", "--format=s16le"], input=tono, check=False)


def _reconocida(texto: str) -> bool:
    if FRASE.strip().lower() in ("sí", "si"):
        return hogar.confirmacion(texto) is True
    return hogar.reconocer(texto) == ("encender_dispositivo", "televisión")


def transcribir(modelo, audio: np.ndarray, vad: bool, vocabulario: bool) -> dict:
    tramos = voice_real._tramos_de_habla(audio) if vad else None
    if tramos == []:
        return {"texto": "", "sin_habla": True}
    if tramos:
        audio = audio[tramos[0][0] : tramos[-1][1]]
    margen = np.zeros(MUESTREO * voice_real._MARGEN_S, dtype=audio.dtype)
    t0 = time.perf_counter()
    segs, _ = modelo.transcribe(
        np.concatenate([margen, audio, margen]),
        language="es",
        initial_prompt=voice_real._VOCABULARIO if vocabulario else None,
    )
    segs = list(segs)
    texto = voice_real.sin_eco(" ".join(s.text for s in segs).strip())
    return {
        "texto": texto,
        "ms": round((time.perf_counter() - t0) * 1000),
        "no_habla": round(max((s.no_speech_prob for s in segs), default=1.0), 3),
        "logprob": round(min((s.avg_logprob for s in segs), default=-9.0), 3),
        "reconocida": _reconocida(texto),
        # ¿Lo dejaría pasar el filtro C4 con los umbrales medidos? (no_habla > 0,15 o logprob < -1,2 → «repite»)
        "pasa_c4": not hogar.confianza_baja(
            {
                "no_speech_prob": max((s.no_speech_prob for s in segs), default=1.0),
                "avg_logprob": min((s.avg_logprob for s in segs), default=-9.0),
            }
        ),
    }


#: Modo por bloques de ganancia (2026-10-04): AURA_DIAG_GANANCIAS="27%,50%" mide N frases por ganancia y solo con
#: el pipeline real (A); las variantes sin VAD tardan hasta 4 min por frase sobre el ruido.
GANANCIAS = [g for g in __import__("os").environ.get("AURA_DIAG_GANANCIAS", "").split(",") if g]
RAPIDO = bool(GANANCIAS)
_POR_BLOQUE = [1]


def ganancia_de(i: int) -> str:
    if not GANANCIAS:
        return "sin cambiar"
    g = GANANCIAS[min((i - 1) // _POR_BLOQUE[0], len(GANANCIAS) - 1)]
    subprocess.run(["pactl", "set-source-volume", "@DEFAULT_SOURCE@", g], check=False)
    return g


def main() -> None:
    import faster_whisper

    salida, n, seg = (
        sys.argv[1],
        int(sys.argv[2]) if len(sys.argv) > 2 else 5,
        float(sys.argv[3]) if len(sys.argv) > 3 else 5,
    )
    if GANANCIAS:
        _POR_BLOQUE[0] = max(1, n // len(GANANCIAS))
    modelo = faster_whisper.WhisperModel("base", device="cpu", compute_type="int8", local_files_only=True)
    ganancia = subprocess.run(["pactl", "get-source-volume", "@DEFAULT_SOURCE@"], capture_output=True, text=True).stdout
    print("Silencio 3 s para medir el ruido de fondo…", flush=True)
    ruido = grabar(3)
    rms_ruido = float(np.sqrt(np.mean(ruido**2))) if len(ruido) else 0.0
    filas = []
    for i in range(1, n + 1):
        print(f"\n[{i}/{n}] Cuando veas «HABLA», di: «{FRASE}»", flush=True)
        time.sleep(1.5)
        ganancia_fila = ganancia_de(i)
        print("HABLA", flush=True)
        pitido()
        audio = grabar(seg)
        tramos = voice_real._tramos_de_habla(audio) or []
        voz = audio[tramos[0][0] : tramos[-1][1]] if tramos else audio
        rms_voz = float(np.sqrt(np.mean(voz**2))) if len(voz) else 0.0
        fila = {
            "intento": i,
            "rms_voz": round(rms_voz, 4),
            "snr_db": round(20 * np.log10(rms_voz / rms_ruido), 1) if rms_ruido > 0 and rms_voz > 0 else None,
            "tramos_ms": [(round(a * 1000 / MUESTREO), round(b * 1000 / MUESTREO)) for a, b in tramos],
            "ganancia": ganancia_fila,
            "saturadas_pct": round(float(np.mean(np.abs(audio) >= 0.98)) * 100, 1),
            "A_vad_vocab": transcribir(modelo, audio, True, True),
            **(
                {}
                if RAPIDO
                else {
                    "B_vad": transcribir(modelo, audio, True, False),
                    "C_vocab": transcribir(modelo, audio, False, True),
                    "D_nada": transcribir(modelo, audio, False, False),
                }
            ),
        }
        filas.append(fila)
        print(
            json.dumps({k: (v["texto"] if isinstance(v, dict) else v) for k, v in fila.items()}, ensure_ascii=False),
            flush=True,
        )
    variantes = ("A_vad_vocab",) if RAPIDO else ("A_vad_vocab", "B_vad", "C_vocab", "D_nada")
    resumen = {v: sum(1 for f in filas if f[v].get("reconocida")) for v in variantes}
    if GANANCIAS:
        resumen["por_ganancia"] = {
            g: f"{sum(1 for f in filas if f['ganancia'] == g and f['A_vad_vocab'].get('reconocida'))}/"
            f"{sum(1 for f in filas if f['ganancia'] == g)}"
            for g in GANANCIAS
        }
    json.dump(
        {
            "fecha": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "frase": FRASE,
            "ganancia_micro": ganancia.strip(),
            "rms_ruido": round(rms_ruido, 4),
            "intentos": filas,
            "reconocidas_por_variante": resumen,
        },
        open(salida, "w", encoding="utf-8"),
        ensure_ascii=False,
        indent=1,
    )
    print(f"\nReconocidas por variante (de {n}): {resumen}", flush=True)


if __name__ == "__main__":
    main()
