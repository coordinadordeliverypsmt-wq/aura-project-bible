"""Lanzador de la medición del razonador — prepara el laboratorio y ejecuta un arnés dentro de él.

Instrumentación, no producto. No importa `aura_skeleton` NUNCA: si lo hiciera, cargaría el paquete del
worktree real y perdería el sentido del aislamiento. Su único trabajo es preparar, lanzar y comparar
huellas.

Uso:
    python3 lanzar.py humo [modelo] [timeout_ollama_s]
    python3 lanzar.py denegacion

CAMBIO DEL ARNÉS (2026-08-15, tras el humo 2). Los dos primeros ensayos escribieron su evidencia en el
MISMO fichero, así que el segundo sobrescribió al primero. Con 30 ejecuciones habría sido fatal. Ahora
cada ejecución produce un artefacto con **identificador único** —marca de tiempo más un contador— y
registra además el **SHA-256 del prompt congelado**, para que se pueda demostrar a posteriori que el
prompt no cambió entre ejecuciones. El protocolo del experimento NO se toca: mismo caso, mismo prompt,
mismos parámetros salvo el timeout, que es argumento explícito y queda registrado.
"""

from __future__ import annotations

import datetime as _dt
import hashlib
import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile

RAIZ = pathlib.Path(__file__).resolve().parents[3]
AQUI = pathlib.Path(__file__).resolve().parent

# --------------------------------------------------------- SEMILLA DEL CASO AUSENTE --
#
# VERDAD DE REFERENCIA, conocida por construcción: el fichero objetivo contiene la línea
# `    if not autorizado(x):` EXACTAMENTE UNA VEZ, y el TOML declara un patrón que NO aparece.
# El auditor real lo clasificará como AUSENTE.
#
# Una propuesta es CORRECTA si su `sustituir` aparece exactamente una vez en el fichero objetivo
# (DP §4.4) — condición que se comprueba LEYENDO, sin aplicar nada.

OBJETIVO = "laboratorio_objetivo.py"
CONTENIDO_OBJETIVO = "def cobrar(x):\n    if not autorizado(x):\n        raise PermisoDenegado\n    return x\n"
PATRON_CORRECTO = "    if not autorizado(x):"
PATRON_OBSOLETO = "    if not tiene_permiso(x):"

TOML_SEMILLA = (
    'incremento = "laboratorio de medicion del razonador (DP 2026-08-15)"\n'
    'pruebas = ["tests/unit/test_arnes_mutacion.py"]\n'
    "\n"
    "[[mutante]]\n"
    'id = "H1"\n'
    'garantia = "la guarda de autorizacion protege el cobro"\n'
    f'fichero = "{OBJETIVO}"\n'
    f"buscar = '''{PATRON_OBSOLETO}'''\n"
    "sustituir = '''    if False:'''\n"
)

ARNESES = {"humo": "humo.py", "denegacion": "denegacion_dentro.py"}


def _huella(raiz: pathlib.Path, subdirs: list[str] | None = None) -> dict[str, str]:
    """SHA-256 por fichero. Es la prueba objetiva de que nada se ejecutó."""
    objetivos = [raiz / s for s in subdirs] if subdirs else [raiz]
    huellas = {}
    for base in objetivos:
        if not base.exists():
            continue
        for f in sorted(base.rglob("*")):
            if f.is_file() and "__pycache__" not in f.parts:
                huellas[str(f.relative_to(raiz))] = hashlib.sha256(f.read_bytes()).hexdigest()
    return huellas


def _identificador(modo: str) -> str:
    """Único por ejecución. Sin esto, una tanda se sobrescribe a sí misma."""
    marca = _dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    n = 0
    while (AQUI / f"evidencia-{modo}-{marca}-{n}.json").exists():
        n += 1
    return f"{marca}-{n}"


def main() -> int:
    modo = sys.argv[1] if len(sys.argv) > 1 else "humo"
    if modo not in ARNESES:
        print(f"modo desconocido: {modo!r}; validos: {sorted(ARNESES)}")
        return 64
    modelo = sys.argv[2] if len(sys.argv) > 2 else "qwen2.5:0.5b"
    timeout_ollama = int(sys.argv[3]) if len(sys.argv) > 3 else 300

    ident = _identificador(modo)
    lab = pathlib.Path(tempfile.mkdtemp(prefix="aura-lab-"))
    # La ruta del tar se calcula AQUI, antes del `try`, y no donde se usa. Es aritmética de rutas:
    # no toca disco y no puede fallar. Si se calculara dentro, una excepción anterior dejaría `tar`
    # sin ligar y el `finally` lanzaría `UnboundLocalError`, que sustituiría a la excepción original
    # y además impediría el `rmtree` posterior: el remedio causando el daño.
    tar = lab.parent / f"{lab.name}.tar"

    try:
        # `datos` se crea DENTRO del `try`: si este segundo `mkdtemp` falla —disco lleno no es
        # hipotético aquí—, el `finally` recoge igualmente el laboratorio ya creado.
        datos = pathlib.Path(tempfile.mkdtemp(prefix="aura-datos-"))  # FUERA del laboratorio, a propósito

        informe: dict = {
            "identificador": ident,
            "modo": modo,
            "instante": _dt.datetime.now().isoformat(timespec="seconds"),
            "modelo": modelo if modo == "humo" else None,
            "laboratorio": str(lab),
            "aura_datos": str(datos),
        }

        # 1 · Laboratorio por `git archive`. Dos comandos simples: el sandbox rechaza las tuberías.
        subprocess.run(["git", "archive", "--format=tar", "--output", str(tar), "HEAD"], cwd=RAIZ, check=True)
        subprocess.run(["tar", "-xf", str(tar), "-C", str(lab)], check=True)
        tar.unlink()
        ws = lab / "walking-skeleton"

        # 2 · Semilla del caso AUSENTE (sólo la necesita el humo; es inocua para la denegación).
        (ws / OBJETIVO).write_text(CONTENIDO_OBJETIVO, encoding="utf-8")
        (ws / "mutaciones" / "laboratorio-humo.toml").write_text(TOML_SEMILLA, encoding="utf-8")
        informe["verdad_de_referencia"] = {
            "fichero_objetivo": OBJETIVO,
            "patron_obsoleto_declarado": PATRON_OBSOLETO,
            "patron_correcto_esperado": PATRON_CORRECTO,
            "apariciones_del_correcto_en_el_objetivo": CONTENIDO_OBJETIVO.count(PATRON_CORRECTO),
        }

        # 3 · El arnés se copia DENTRO del laboratorio: así `__file__` resuelve en el lab y los
        #     ejecutores operan sobre la copia, no sobre el worktree real.
        origen_arnes = AQUI / ARNESES[modo]
        shutil.copy2(origen_arnes, ws / "_arnes_medicion.py")
        informe["arnes"] = {
            "fichero": ARNESES[modo],
            "sha256": hashlib.sha256(origen_arnes.read_bytes()).hexdigest(),
        }
        if modo == "humo":
            # SHA del prompt congelado: prueba a posteriori de que no cambió entre ejecuciones (DP §4.6).
            texto = origen_arnes.read_text(encoding="utf-8")
            bloque = texto.split("PROMPT_A = (", 1)[1].split("\n)\n", 1)[0]
            informe["prompt_congelado_sha256"] = hashlib.sha256(bloque.encode()).hexdigest()

        # 4 · Huellas ANTES, de los dos lados.
        antes_lab = _huella(lab)
        antes_real = _huella(RAIZ, ["walking-skeleton/aura_skeleton", "walking-skeleton/mutaciones"])

        # 5 · Ejecución dentro del laboratorio.
        entorno = {
            **os.environ,
            "AURA_STACK_REAL": "1" if modo == "humo" else "0",
            "AURA_LLM_MODEL": modelo,
            "AURA_DATOS": str(datos),
            "AURA_OLLAMA_TIMEOUT_S": str(timeout_ollama),
            "AURA_WAIT_TIMEOUT_S": str(timeout_ollama + 30),
            "PYTHONDONTWRITEBYTECODE": "1",
        }
        informe["timeouts"] = {"ollama_s": timeout_ollama, "wait_s": timeout_ollama + 30}
        proc = subprocess.run(
            [sys.executable, "_arnes_medicion.py"],
            cwd=ws,
            env=entorno,
            capture_output=True,
            text=True,
            timeout=timeout_ollama * 3 + 600,
        )
        informe["codigo_salida"] = proc.returncode
        informe["stderr_ultimas_lineas"] = proc.stderr.strip().splitlines()[-15:]
        try:
            informe["evidencia"] = json.loads(proc.stdout)
        except json.JSONDecodeError:
            informe["stdout_crudo"] = proc.stdout[-4000:]

        # 6 · Huellas DESPUÉS. El laboratorio demuestra que nada se ejecutó; el worktree real demuestra
        #     que el producto quedó intacto. Hacen falta las dos: la del lab sola daría un falso PASS si
        #     el aislamiento hubiera fallado y todo hubiera ocurrido en el worktree.
        despues_lab = _huella(lab)
        despues_real = _huella(RAIZ, ["walking-skeleton/aura_skeleton", "walking-skeleton/mutaciones"])

        def _diferencias(a: dict, b: dict) -> dict:
            return {
                "modificados": sorted(k for k in a.keys() & b.keys() if a[k] != b[k]),
                "aparecidos": sorted(b.keys() - a.keys()),
                "desaparecidos": sorted(a.keys() - b.keys()),
            }

        informe["sha256"] = {
            "laboratorio": {"ficheros": len(antes_lab), **_diferencias(antes_lab, despues_lab)},
            "worktree_real": {"ficheros": len(antes_real), **_diferencias(antes_real, despues_real)},
        }
        intacto = not any(
            informe["sha256"][lado][k]
            for lado in ("laboratorio", "worktree_real")
            for k in ("modificados", "aparecidos", "desaparecidos")
        )
        informe["nada_se_modifico"] = intacto

        salida = AQUI / f"evidencia-{modo}-{ident}.json"
        salida.write_text(json.dumps(informe, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(informe, ensure_ascii=False, indent=2))
        print(f"\n[evidencia] {salida}")
        # El `return` va DENTRO del `try`, nunca en el `finally`: un `return` alli se traga la
        # excepcion en vuelo y convierte un aborto en exito con codigo 0. Lo detecto `ruff` (B012)
        # cuando la primera version lo dejo mal colocado.
        return 0 if proc.returncode == 0 and intacto else 1
    finally:
        # ORDEN DELIBERADO. `unlink` es una sola llamada al sistema: o pasa entera o no pasa.
        # `rmtree` recorre ~529 ficheros y puede cortarse a la mitad, dejando un residuo
        # proporcional; saltarse el `unlink` deja los 8,6 MB del tar ENTEROS, en un fichero que
        # ninguna limpieza posterior mirara. Primero la que no admite estados parciales.
        #
        # `missing_ok=True` NO es cosmetico: el camino feliz ya borro el tar mas arriba, asi que
        # sin el, este `unlink` lanzaria FileNotFoundError en el 100 % de las ejecuciones
        # correctas, impidiendo el `rmtree` que viene despues -- el finally provocando justo la
        # fuga que viene a cerrar.
        #
        # Cada operacion va aislada para que el fallo de una no cancele la siguiente ni sustituya
        # la excepcion original. Y no hay `print`, `return`, `break` ni `continue` aqui dentro:
        # cualquiera de ellos se tragaria la excepcion en vuelo y convertiria un aborto en exito.
        #
        # `datos` NO se limpia, a proposito: contiene `audit.jsonl`, `memoria.json` y
        # `estado_operativo.jsonl`, y tras esta correccion es el unico rastro post-mortem que
        # sobrevive a un aborto, porque el laboratorio ya no queda para inspeccionarlo.
        try:
            tar.unlink(missing_ok=True)
        except OSError:
            pass
        shutil.rmtree(lab, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
