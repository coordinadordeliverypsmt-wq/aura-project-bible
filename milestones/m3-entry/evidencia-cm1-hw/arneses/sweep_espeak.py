import json, sys; sys.path.insert(0, sys.path[0])
import inteligibilidad as I  # reutiliza FR, stt, wer (su bloque principal no corre: ver guardia abajo)
from espeak_tts import Espeak, _lib
FR = I.FR + ["Tu próxima reunión es a las diez.", "He apagado la música.", "La temperatura es de veinte grados.", "Te lo recuerdo mañana."]
res = []
for voz in (b"es-419", b"es"):
    for rate in (130, 150, 175):
        e = Espeak(voz, rate); w = [I.wer(f, I.stt(e.synth(f)[0], e.sr)) for f in FR]
        res.append((voz.decode(), rate, round(sum(w) / len(w), 3)))
        print(res[-1], flush=True)
