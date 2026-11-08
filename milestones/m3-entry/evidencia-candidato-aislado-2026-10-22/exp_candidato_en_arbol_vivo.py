# NOTA (PROMPT 03, Fase A, 2026-10-23): este fichero documenta el DEFECTO PREVIO (candidato verificado en el arbol vivo,
# con verificadores sin raiz como `lambda: ...`). NO se migra. Con el codigo actual, la via sin raiz se rechaza
# explicitamente (`autoconstruccion.VerificadorSinRaiz`); el experimento ya no reproduce el defecto tal cual.
"""Evidencia reproducible: `autoconstruccion.ejecutar` verifica el candidato EN EL ÁRBOL VIVO (DP-CANDIDATO-AISLADO).

NO se ejecuta nunca sobre el repositorio. Uso:
    cp -r entorno/control-plane <TMP>/control-plane && rm -f <TMP>/control-plane/PARADA
    python3 exp_candidato_en_arbol_vivo.py <TMP>/control-plane <TMP>/sandbox

(a) Mientras corre la verificación, ¿qué contiene el fichero objetivo?
(b) Si el proceso muere (SIGKILL) durante la verificación, ¿qué queda en disco y en el log?
"""

import json
import os
import pathlib
import signal
import subprocess
import sys
import time

CP, SANDBOX = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2])
sys.path.insert(0, str(CP))
import autoconstruccion as ac  # noqa: E402


def preparar(d: pathlib.Path) -> tuple[pathlib.Path, dict]:
    d.mkdir(parents=True, exist_ok=True)
    obj = d / "s.py"
    obj.write_text("VALOR = 1\n", encoding="utf-8")
    p = ac.proponer(d, {"fichero": str(obj), "operacion": "sustituir_texto", "buscar": "VALOR = 1",
                        "sustituir": "VALOR = 2", "motivo": "experimento"})
    ac.autorizar(d, p["id"], por="ceo", acta="experimento")
    return obj, p


if len(sys.argv) == 3:
    # (a) lo que ve un lector durante la verificación
    obj, p = preparar(SANDBOX / "a")
    visto = {}
    r = ac.ejecutar(SANDBOX / "a", p, "ceo", verificacion=lambda: visto.setdefault("durante", obj.read_text()) or True)
    print("(a) durante la verificación el fichero contiene:", repr(visto["durante"]))
    print("(a) resultado:", {k: r[k] for k in ("efecto_verificado", "verificacion_sana", "revertido")})
    # (b) muerte abrupta durante la verificación, en un subproceso propio
    hijo = subprocess.Popen([sys.executable, __file__, str(CP), str(SANDBOX), "hijo"], stdout=subprocess.PIPE, text=True)
    print("(b)", hijo.stdout.readline().strip())
    time.sleep(1)
    os.kill(hijo.pid, signal.SIGKILL)  # solo el PID lanzado aquí
    print("(b) código de salida del hijo:", hijo.wait())
    d = SANDBOX / "b"
    print("(b) fichero tras la muerte:", repr((d / "s.py").read_text()))
    print("(b) ficheros en el directorio:", sorted(x.name for x in d.iterdir()))
    eventos = [json.loads(linea).get("tipo") for linea in (d / "eventos.jsonl").read_text().splitlines() if linea.strip()]
    print("(b) eventos registrados:", eventos)
else:
    obj, p = preparar(SANDBOX / "b")

    def dormir() -> bool:
        print("verificando (PID", os.getpid(), ")", flush=True)
        time.sleep(30)
        return True

    ac.ejecutar(SANDBOX / "b", p, "ceo", verificacion=dormir)
