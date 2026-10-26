# Se ejecuta EN EL NODO con su credencial real. Nunca imprime la contraseña.
import asyncio, json, os, ssl, sys, time
sys.path.insert(0, os.path.expanduser("~/.aura-nodo/app"))
import nats
D = os.path.expanduser("~/.aura-nodo")
conf = json.load(open(f"{D}/nodo.conf")); pw = open(f"{D}/credencial").read().strip()
url = conf["servidores"][-1]; yo = conf["usuario"][5:]; otro = "0" * 32
def ctx():
    c = ssl.create_default_context(cafile=f"{D}/ca.crt"); c.check_hostname = False; return c
async def main():
    errores = []
    async def cb(e): errores.append(type(e).__name__ + ":" + str(e)[:80])
    nc = await nats.connect(url, user=conf["usuario"], password=pw, tls=ctx(), error_cb=cb, allow_reconnect=False)
    await nc.subscribe("nodo.latido.>"); await nc.flush(); await asyncio.sleep(1)
    print("A1 suscribirse a nodo.latido.> :", "DENEGADO" if any("Permissions Violation" in e and "Subscription" in e for e in errores) else f"¿PERMITIDO? {errores}")
    errores.clear(); await nc.publish(f"nodo.latido.{otro}", b"{}"); await nc.flush(); await asyncio.sleep(1)
    print("A2 publicar en el subject de OTRO nodo :", "DENEGADO" if any("Permissions Violation" in e and "Publish" in e for e in errores) else f"¿PERMITIDO? {errores}")
    cuerpo = json.dumps({"type": f"nodo.latido.{otro}", "trace_id": "ataque", "user_id": "sistema", "event_id": "ataque0000001",
        "payload": {"esquema": "nodo.latido/1", "nodo_id": otro, "nombre": "fantasma", "secuencia": 0, "arranque": otro,
                    "intervalo_s": 10, "recursos": {"ram_mb": 1.0, "nucleos": 1.0}, "omitidas": [], "agente": "ataque"}}).encode()
    await nc.publish(f"nodo.latido.{yo}", cuerpo); await nc.flush()
    print("A3 suplantar a OTRO por el cuerpo, en MI subject: enviado (HC-1 debe rechazarlo)")
    await nc.close()
    for nombre, kw in (("sin credencial", dict(tls=ctx())), ("contraseña errónea", dict(tls=ctx(), user=conf["usuario"], password="x"))):
        try:
            c = await nats.connect(url, allow_reconnect=False, connect_timeout=5, **kw); await c.close(); print(f"A4 {nombre}: ¿ACEPTADO?")
        except Exception as e: print(f"A4 {nombre}: RECHAZADO ({type(e).__name__})")
    try:
        c = await nats.connect(url.replace("tls://", "nats://"), user=conf["usuario"], password=pw, allow_reconnect=False, connect_timeout=5); await c.close(); print("A5 sin TLS: ¿ACEPTADO?")
    except Exception as e: print(f"A5 sin TLS: RECHAZADO ({type(e).__name__})")
asyncio.run(main())
