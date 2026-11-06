"""Reproduccion aislada: composicion de produccion -> declaracion -> cm2.hecho_registrado -> medir a +28 d."""
import asyncio, json, os, sys, tempfile, time, uuid
base = tempfile.mkdtemp(prefix="cm2e2e-")
os.environ["HOME"] = os.path.join(base, "home"); os.environ["AURA_DATOS"] = os.path.join(base, "aislado")
# Ni hogar ni camaras ni plano de control ni red de nodos reales (revision de seguridad 2026-10-25 (s)).
for _v in ("AURA_HA_URL", "AURA_HA_TOKEN", "AURA_CAMARA_RTSP", "AURA_CAMARA_AUDIO_RTSP"):
    os.environ.pop(_v, None)
os.environ["AURA_CONTROL_PLANE"] = ""; os.environ["AURA_RED"] = ""
datos = os.path.join(base, "datos"); os.makedirs(datos)
open(os.path.join(datos, "memoria.json"), "w").close()
from aura_skeleton import observability as obs
from aura_skeleton.composicion import Configuracion, componer
from aura_skeleton.core import reloj_cm2 as r
print("iniciar:", r.iniciar(datos, True)); obs.reset_audit()
s = componer(Configuracion(datos=datos, raices_permitidas=(datos,), usar_stack_real=False))
async def turno(t):
    tid = uuid.uuid4().hex[:12]; await s.orquestador.handle_utterance("mauricio", t, tid); return await s.orquestador.wait(tid)
for t in sys.argv[1:]:
    res = asyncio.run(turno(t)); print(repr(t), "->", res.get("provider"), res.get("dominio"), repr(res.get("say")))
obs.reset_audit()
evs = r._eventos_cm2(datos)
print("eventos cm2:", [e["evento"] for e in evs])
print("poblacion:", len(r.reconstruir_poblacion(evs)))
print(r.medir(datos, ahora=time.time() + 28.3 * 86400))
print("sondas:", [(e["dia"], e["resultado"]) for e in r._eventos_cm2(datos) if e["evento"] == "cm2.sonda"])
print("tasa minimo=1:", r.tasa_dia28(r._eventos_cm2(datos), minimo=1))
print("BASE", base, "(temporal: borrarlo a mano si ya no se necesita)")
