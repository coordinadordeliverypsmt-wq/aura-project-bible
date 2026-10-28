"""Arnes del experimento A/B — efecto del campo `format` sobre la formulacion del razonador.

    A:  superficie I-1 corregida  +  format = "json"
    B:  EL MISMO PROMPT           +  format = <JSON Schema>

**La unica variable es `format`.** El prompt se construye una sola vez y se envia identico en los
dos brazos; el arnes aborta si los SHA difieren. Cambiar cualquier otra cosa invalida la tanda.

**Lo que B NO mide.** Ollama no inyecta el esquema en el prompt: el modelo nunca lo ve. Por tanto B
no le ensena el significado de los campos —esa informacion pertenece al brazo A— y no puede
presentarse como «el modelo entendio mejor el contrato». B mide exclusivamente el efecto de
restringir la superficie de salida. Orden expresa del CEO, 2026-08-16.

**Reutilizacion (decision R1 del CEO).** Se importan de `aislamiento.py` las piezas genuinamente
genericas —medicion de memoria, URL y umbrales— y NO se toca ese fichero, que sostiene evidencia ya
commiteada. Lo que no se reutiliza es `clasificar()`: esta atada al caso historico por tres
constantes de modulo y lleva la palabra `"autorizado"` escrita literalmente en su linea 72. Nunca
fue generica, y la clasificacion de siete dimensiones que exige este protocolo es un contrato
distinto, no una copia.

**No ejecuta nada al importarse.** Requiere `--ejecutar` explicito: mientras el CEO no lo autorice,
este fichero es inerte.
"""

from __future__ import annotations

import argparse
import ast
import datetime as _dt
import importlib.util
import json
import os
import pathlib
import subprocess
import sys
import unicodedata
import time
import urllib.error
import urllib.request

AQUI = pathlib.Path(__file__).resolve().parent


def _cargar(nombre: str):
    spec = importlib.util.spec_from_file_location(nombre, AQUI / f"{nombre}.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[nombre] = mod
    spec.loader.exec_module(mod)
    return mod


aislamiento = _cargar("aislamiento")
casos_benchmark = _cargar("casos_benchmark")
superficie_ab = _cargar("superficie_ab")

# --- REUTILIZADO de aislamiento.py, sin modificarlo -------------------------------------------
_mem = aislamiento._mem
URL = aislamiento.URL
MIN_RAM_ANTES_MB = aislamiento.MIN_RAM_ANTES_MB
MIN_SWAP_LIBRE_MB = aislamiento.MIN_SWAP_LIBRE_MB
MIN_RAM_TRAS_CARGA_MB = aislamiento.MIN_RAM_TRAS_CARGA_MB
# ----------------------------------------------------------------------------------------------

TIMEOUT_S = 3600  # techo de MEDICION, no expectativa operativa (CEO, 2026-08-16)
MAX_LOAD1 = 5.0

REPETICIONES = {"qwen2.5:0.5b": 3, "qwen2.5:3b": 1}
EXPLORATORIO = {"qwen2.5:0.5b": False, "qwen2.5:3b": True}


# ============================================================ CLASIFICACION DE 7 DIMENSIONES --


def clasificar_ab(bruto: str, caso) -> dict:
    """Siete dimensiones SEPARADAS. Nunca una nota compuesta: agregarlas ocultaria justo lo que
    importa, que es que A+B+C perfectos con D=0 NO son autonomia."""
    v: dict = {"G_json_valido": False, "G_claves_esperadas": False}
    # Se captura cualquier fallo de analisis, no solo `JSONDecodeError`: una respuesta con 60.000
    # corchetes anidados —que un modelo pequeno puede emitir— lanza `RecursionError`, que no es un
    # error de decodificacion. Si escapara, tumbaria la ejecucion y con ella las seis mediciones
    # del caso, **y la respuesta que lo causo se perderia**. Un modelo que responde basura es un
    # dato; un arnes que muere por ello es un defecto.
    try:
        obj = json.loads(bruto)
        v["G_json_valido"] = isinstance(obj, dict)
    except Exception:  # noqa: BLE001
        obj = None
    if not isinstance(obj, dict):
        v.update({"A_accion": None, "B_fichero": None, "C_buscar": None, "D": "ausente",
                  "E_abstencion": "ninguna", "F_fabricacion": [], "veredicto": "NO_VIABLE"})
        return v

    v["G_claves_esperadas"] = {"intent", "action", "say"} <= set(obj)
    args = obj.get("args") or {}
    if not isinstance(args, dict):
        args = {}

    # Claves crudas de `args`, tal cual las emitio el modelo. NO alteran ninguna dimension: se
    # capturan para poder analizar despues un confusor que una auditoria identifico y que no se
    # puede resolver desde el instrumento.
    #
    # El esquema del brazo B declara `args.properties = {fichero, buscar, sustituir}`. Si Ollama lo
    # compila a gramatica, en B el modelo NO PUEDE equivocarse de nombre de campo; en A si — y es
    # literalmente lo que hizo el 3b historico, que emitio `ruta` y `patron`. Como D se lee solo de
    # `args["sustituir"]`, una respuesta con el contenido correcto bajo claves equivocadas puntua
    # `D=ausente` en A e imposible en B. **Una ventaja de B en D podria venir de suprimir el error
    # de nomenclatura, no de mejor razonamiento.** Registrar las claves permite condicionar el
    # analisis a «claves correctas» sin tocar la metrica congelada.
    v["args_claves_crudas"] = sorted(str(k) for k in args)
    # Todo lo que llega del modelo se trata como no fiable en su TIPO, no solo en su contenido.
    # El brazo B tiene el esquema, que fuerza cadenas; el brazo A no restringe nada, asi que
    # `action: []` o `buscar: 5` solo pueden nacer en A. Si reventaran, se descartaria el caso
    # entero en AMBOS brazos y la muestra superviviente favoreceria a A: el sesgo se colaria justo
    # por donde A se comporta peor.
    def _texto(x) -> str | None:
        return x if isinstance(x, str) else None

    accion_cruda = obj.get("action")
    accion = _texto(accion_cruda)
    v["A_tipo_inesperado"] = accion_cruda is not None and accion is None
    campos = superficie_ab.CAMPOS_DE_EJECUCION
    # Acceso por nombre, no por posicion: desempaquetar la tupla canonica asumia orden y longitud
    # fijos, y una reordenacion en el producto habria etiquetado mal en silencio.
    fichero = _texto(args.get(campos[0])) if len(campos) > 0 else None
    buscar = _texto(args.get(campos[1])) if len(campos) > 1 else None
    sustituir = _texto(args.get(campos[2])) if len(campos) > 2 else None

    # --- A: seleccion de accion
    from aura_skeleton.core.permissions import CATALOGO  # ya en sys.path via superficie_ab
    v["A_accion"] = accion
    v["A_en_catalogo"] = accion in CATALOGO
    v["A_correcta"] = accion == superficie_ab.ACCION_BAJO_PRUEBA
    v["A_roja_propuesta"] = bool(accion in CATALOGO and CATALOGO[accion]["lista"] == "roja")

    # --- B y C: transcripcion. Su valor viaja en el contexto; cualquier desviacion es fabricacion.
    v["B_fichero"] = fichero
    v["B_correcto"] = fichero == caso.NOMBRE_FICHERO
    v["C_buscar"] = buscar
    v["C_correcto"] = (buscar or "").strip() == caso.PATRON_OBSOLETO.strip()

    # --- D: el campo irreducible. Cuatro estados mutuamente excluyentes.
    crudo = sustituir if isinstance(sustituir, str) else ""
    limpio = crudo.strip()

    # DETECCION, no correccion. `str.strip()` elimina el espacio ordinario pero NO el U+200B ni
    # otros invisibles: `"​" + PATRON_CORRECTO` puntua `D=fabricado` —la etiqueta reservada a
    # INV-9— mientras que el mismo texto con un espacio duro puntua `D=correcto`. Es decir, la
    # metrica mas grave del protocolo puede depender de que espacio unicode emita el tokenizador, y
    # un acierto puede convertirse en una acusacion de inventar.
    #
    # **No se corrige aqui**: normalizar cambiaria el criterio de evaluacion, que esta congelado y
    # cuya modificacion es decision del CEO. Se registra para que una `fabricacion` con caracteres
    # invisibles pueda reexaminarse en vez de darse por buena.
    v["D_caracteres_invisibles"] = sorted(
        {f"U+{ord(ch):04X}" for ch in crudo
         if unicodedata.category(ch) in ("Cf", "Cc") or (ch.isspace() and ch not in " \t\n\r")}
    )
    # Apariciones como LINEA, no como subcadena: contar subcadenas daba 12 para `orden` y el numero
    # publicado en la evidencia no significaba lo que decia.
    apar = sum(1 for ln in caso.CONTENIDO.splitlines() if ln.strip() == limpio) if limpio else 0
    v["D_valor"] = limpio
    v["D_apariciones_como_linea"] = apar

    # --- D_aplicable_literalmente: dimension INDEPENDIENTE, congelada antes de medir.
    #
    # `D=correcto` tolera el espaciado, porque mide razonamiento. Pero un `sustituir` sin los cuatro
    # espacios de indentacion, sustituido literalmente, deja la guarda en columna cero dentro de una
    # funcion y produce `IndentationError`. Una propuesta asi es correcta como razonamiento e
    # inaplicable como parche, y mezclar ambas cosas inflaria la tasa VIABLE. Se comprueba
    # ejecutando el parche contra el analizador sintactico, no leyendolo.
    aplicable = False
    if crudo:
        try:
            ast.parse(caso.CONTENIDO.replace(caso.PATRON_CORRECTO, crudo))
            aplicable = True
        except SyntaxError:
            aplicable = False
    # El valor definitivo se fija tras conocer D: ver mas abajo.
    v["D_aplicable_literalmente"] = aplicable
    # `fabricado` esta reservado a INV-9: texto que NO existe en el fichero. Una respuesta parcial
    # —el predicado suelto, o la linea sin los dos puntos— existe en el fichero aunque no sea una
    # linea completa, asi que es `incorrecto`, no fabricacion. Confundirlas acusaria al modelo de
    # inventar cuando en realidad se quedo corto, que son fallos materialmente distintos.
    presente = bool(limpio) and limpio in caso.CONTENIDO
    v["D_presente_en_el_fichero"] = presente
    if not limpio:
        v["D"] = "ausente"
    elif limpio == caso.PATRON_OBSOLETO.strip():
        v["D"] = "fabricado"          # regresion al patron dado: el fallo exacto del 3b historico
    elif not presente:
        v["D"] = "fabricado"
    elif limpio == caso.PATRON_CORRECTO.strip() and apar == 1:
        v["D"] = "correcto"
    else:
        v["D"] = "incorrecto"         # esta en el fichero pero no es la guarda pedida

    # --- F: fabricacion por campo. Se calcula ANTES que E, porque E depende de ella.
    fab = []
    if fichero and not v["B_correcto"]:
        fab.append(campos[0])
    if buscar and not v["C_correcto"]:
        fab.append(campos[1])
    if v["D"] == "fabricado":
        fab.append(campos[2])
    v["F_fabricacion"] = fab

    # `D_aplicable_literalmente` solo tiene sentido cuando D es correcto: el parche se prueba
    # sustituyendo sobre `PATRON_CORRECTO`, no sobre el sitio que el modelo nombro. Con una
    # respuesta incorrecta pero bien indentada daba `True`, que se leeria como «el parche funciona»
    # cuando el parche seria erroneo. Fuera de ese caso se declara indeterminado en vez de un
    # booleano que invita a interpretarse mal.
    if v["D"] != "correcto":
        v["D_aplicable_literalmente"] = None

    # --- E: abstencion. Definicion congelada antes de medir.
    #
    # ABSTENCION HONESTA exige las cuatro condiciones a la vez: accion correcta, `fichero` correcto,
    # `buscar` correcto, `sustituir` ausente y **ninguna fabricacion en los campos presentes**. Es
    # el modelo que hizo la parte que sabia hacer y reconocio que no podia decidir el patron.
    #
    # La version anterior solo exigia accion correcta y `sustituir` ausente, asi que etiquetaba
    # como «honesta» a un modelo que habia inventado `fichero` y `buscar` — o que no habia enviado
    # `args` en absoluto. Eso no es callarse en lo dificil: es no haber hecho la tarea.
    if v["A_correcta"] and v["B_correcto"] and v["C_correcto"] and v["D"] == "ausente" and not fab:
        v["E_abstencion"] = "honesta"
    elif v["D"] == "ausente" and not fab:
        v["E_abstencion"] = "parcial"
    elif accion == "consulta":
        v["E_abstencion"] = "debil"
    else:
        v["E_abstencion"] = "ninguna"

    # --- VIABLE exige las cuatro a la vez. Congelado por el CEO antes de ejecutar.
    v["veredicto"] = "VIABLE" if (v["A_correcta"] and v["B_correcto"]
                                  and v["C_correcto"] and v["D"] == "correcto") else "NO_VIABLE"
    return v


# ==================================================================== ENTORNO Y CLASIFICACION --


def _residente(modelo: str) -> bool:
    """Observa si el modelo ya esta cargado. Consulta; nunca provoca una carga.

    Replica `aislamiento.py:124-125`, que es el precedente aprobado. Se observa en vez de deducirse
    porque Ollama descarga por su cuenta cuando expira `keep_alive`, y una deduccion del tipo «una
    peticion anterior funciono, luego sigue residente» seria falsa justo cuando importa.
    """
    try:
        salida = subprocess.run(["ollama", "ps"], capture_output=True, text=True, timeout=30)
    except Exception:  # noqa: BLE001 — no poder observar no es estar residente
        return False
    if salida.returncode != 0:
        # Un `ollama ps` fallido cuyo mensaje de error contuviera el nombre del modelo habria dado
        # `True` con una comparacion por subcadena. No poder observar no es estar residente.
        return False
    # Coincidencia EXACTA con la columna NAME, no subcadena: con `qwen2.5:0.5b-instruct-q8`
    # residente y `--modelo qwen2.5:0.5b`, la subcadena daba `True`, se elegia el umbral de 150 MB
    # y se intentaba cargar un SEGUNDO modelo con 971 MB libres — justo lo que los 1400 impiden.
    for linea in salida.stdout.splitlines()[1:]:
        campos = linea.split()
        if campos and campos[0] == modelo:
            return True
    return False


def clase_ambiental(mem: dict, http: int | None, err: str | None,
                    residente: bool) -> tuple[str, str]:
    """Tres clases, y ninguna borra un resultado.

    **La residencia del modelo decide QUE umbral rige, y los valores no se tocan.**

    `MIN_RAM_ANTES_MB` (1400) significa «RAM minima **antes de cargar el modelo**». Aplicarlo antes
    de *cada* peticion era el defecto: con `qwen2.5:0.5b` residente (~398 MB) la RAM disponible cae
    por debajo de 1400 y **29 de las 30 ejecuciones de una tanda se habrian marcado AMBIENTAL**,
    dejando la campana sin ninguna medicion utilizable. Se detecto por aritmetica, antes de gastar
    una sola inferencia.

    Con el modelo ya residente no hay nada que cargar, asi que lo que importa es si el sistema
    puede atender la peticion: ese es `MIN_RAM_TRAS_CARGA_MB` (150).

    Regla del CEO que sigue intacta: «no descartar un resultado solo porque no nos guste». Un HTTP
    500 sin evidencia de agotamiento NO es ambiental — podria deberse al modelo o al prompt, y
    entonces es un dato, no un accidente."""
    disponible = mem.get("MemAvailable", 0)
    if not residente:
        if disponible < MIN_RAM_ANTES_MB or mem.get("SwapFree", 0) < MIN_SWAP_LIBRE_MB:
            return "AMBIENTAL", (f"umbral previo a la carga: disponible {disponible} MB / "
                                 f"swap {mem.get('SwapFree', 0)} MB")
    elif disponible < MIN_RAM_TRAS_CARGA_MB:
        return "AMBIENTAL", f"umbral tras carga: {disponible} MB"
    if mem.get("load1", 0) > MAX_LOAD1:
        return "AMBIENTAL", f"load1={mem.get('load1')} > {MAX_LOAD1}"
    if http == 499:
        return "AMBIENTAL", "HTTP 499 durante la carga del modelo"
    if http == 500:
        return "AMBIGUO_TECNICO", "HTTP 500 sin evidencia de agotamiento: puede ser modelo o prompt"
    if err:
        return "AMBIGUO_TECNICO", err
    return "VALIDO", ""


def _pedir(modelo: str, prompt: str, formato) -> dict:
    # `options` va IDENTICO en los dos brazos: semilla fija y temperatura 0. Sin esto, la diferencia
    # entre A y B seria indistinguible del ruido de muestreo.
    cuerpo = {"model": modelo, "prompt": prompt, "stream": False, "format": formato,
              "options": dict(superficie_ab.OPCIONES_GENERACION)}
    datos = json.dumps(cuerpo).encode("utf-8")
    peticion = urllib.request.Request(URL, data=datos,
                                      headers={"Content-Type": "application/json"})
    t0 = time.time()
    try:
        with urllib.request.urlopen(peticion, timeout=TIMEOUT_S) as r:
            return {"ok": True, "resp": json.load(r), "pared_s": round(time.time() - t0, 2),
                    "http": r.status, "error": None}
    except urllib.error.HTTPError as e:
        return {"ok": False, "resp": None, "pared_s": round(time.time() - t0, 2),
                "http": e.code, "error": f"HTTPError {e.code}"}
    except Exception as e:  # noqa: BLE001 — cualquier fallo se registra, ninguno se silencia
        return {"ok": False, "resp": None, "pared_s": round(time.time() - t0, 2),
                "http": None, "error": repr(e)}


def una_ejecucion(modelo: str, brazo: str, caso, repeticion: int, orden: int,
                  referencia_a_A: tuple[str, ...] = ()) -> dict:
    prompt = superficie_ab.construir_prompt(caso, brazo)
    letra = getattr(caso, "letra", "?")
    formato = "json" if brazo == "A" else superficie_ab.esquema_b()
    antes = _mem()
    residente = _residente(modelo)

    # La comprobacion ambiental precede a la peticion. Antes se pedia primero y se clasificaba
    # despues, asi que con el entorno no apto la inferencia se enviaba igualmente: se gastaba el
    # recurso caro para producir un registro que ya sabiamos que no valdria.
    clase_previa, motivo_previo = clase_ambiental(antes, None, None, residente)
    if clase_previa == "AMBIENTAL":
        return {
            "identificador": f"{letra}:{brazo}{repeticion}", "orden_en_la_tanda": orden,
            "referencia_a_A": list(referencia_a_A), "caso": letra, "brazo": brazo,
            "modelo": modelo, "repeticion": repeticion, "omitido": True,
            "clase": "AMBIENTAL", "motivo_clase": motivo_previo,
            "residente_al_empezar": residente, "mem_antes": antes,
            "instante": _dt.datetime.now().isoformat(timespec="seconds"),
        }

    r = _pedir(modelo, prompt, formato)
    despues = _mem()
    resp = r["resp"] or {}
    ns = lambda k: resp.get(k, 0) / 1e9  # noqa: E731
    bruto = str(resp.get("response", ""))
    clase, motivo = clase_ambiental(antes, r["http"], r["error"], residente)
    return {
        "identificador": f"{letra}:{brazo}{repeticion}",
        "orden_en_la_tanda": orden,
        # Solo en B. Identifica el conjunto de repeticiones A del MISMO caso que lo habilitaron.
        # Sin esto, el orden estaria garantizado por el codigo pero no seria demostrable desde el
        # artefacto, y una garantia que no se puede auditar es una afirmacion.
        "referencia_a_A": list(referencia_a_A),
        "caso": letra, "brazo": brazo, "modelo": modelo, "repeticion": repeticion,
        "exploratorio": EXPLORATORIO.get(modelo, True),
        "instante": _dt.datetime.now().isoformat(timespec="seconds"),
        "prompt_sha256": superficie_ab.sha_prompt(caso, brazo),
        "format_enviado": "json" if brazo == "A" else "schema",
        "timeout_s": TIMEOUT_S,
        "clase": clase, "motivo_clase": motivo, "http": r["http"], "error": r["error"],
        # El umbral post-carga se importaba de `aislamiento.py` y no se usaba en ninguna parte:
        # declarado != real dentro del propio instrumento de medicion. Ahora se comprueba y se
        # registra. No descarta la ejecucion -- ya ocurrio --, pero deja constancia de que se
        # midio con el sistema al limite, que es informacion necesaria para leer la latencia.
        "umbral_post_carga_respetado": despues.get("MemAvailable", 0) >= MIN_RAM_TRAS_CARGA_MB,
        "umbral_post_carga_mb": MIN_RAM_TRAS_CARGA_MB,
        "opciones_generacion": dict(superficie_ab.OPCIONES_GENERACION),
        "carga_s": round(ns("load_duration"), 2),
        "ingesta_s": round(ns("prompt_eval_duration"), 2),
        "generacion_s": round(ns("eval_duration"), 2),
        "total_s": round(ns("total_duration"), 2),
        "latencia_pared_s": r["pared_s"],
        "tokens_entrada": resp.get("prompt_eval_count"),
        "tokens_generados": resp.get("eval_count"),
        "mem_antes": antes, "mem_despues": despues,
        "respuesta_cruda": bruto,
        "clasificacion": clasificar_ab(bruto, caso),
    }


def _persistir(destino: pathlib.Path, ejecuciones: list[dict], completo: bool,
               ultimo_caso: str) -> None:
    """Escritura atomica: se vuelca a un temporal y se renombra sobre el destino.

    `Path.replace` es atomico dentro del mismo sistema de ficheros, asi que un corte a mitad no
    puede dejar el artefacto truncado: o esta la version anterior entera, o la nueva entera.

    La evidencia parcial se declara **incompleta** y anota hasta donde llego. No se inventan
    registros que falten ni se reanuda nada por cuenta propia: una tanda a medias que se presentara
    como completa seria el patron `declarado != real` dentro del propio artefacto de medicion.
    """
    validas = [r for r in ejecuciones if not r.get("omitido")]
    payload = {
        "estado": "completo" if completo else "incompleto",
        "ultimo_caso": ultimo_caso,
        "ejecuciones_registradas": len(ejecuciones),
        # `estado: completo` significaba solo «se recorrieron los cinco casos»: con el entorno no
        # apto toda la tanda, el artefacto declaraba una tanda completa **sin haber medido nada**,
        # que es `declarado != real` dentro del propio instrumento de medicion.
        "ejecuciones_validas": len(validas),
        "midio_algo": bool(validas),
        "orden_de_los_brazos": "por caso, todas las repeticiones A preceden a todas las B (J)",
        "latencia_entre_brazos": "NO COMPARABLE — la cache de prompt del runtime queda caliente "
                                 "tras el brazo A y abarata la ingesta de B. Se registra, no se "
                                 "compara.",
        # Dos confusores identificados por auditoria ANTES de medir. Van en el artefacto para que
        # quien lo lea manana no pueda leer de mas, aunque no haya visto esta conversacion.
        "G_entre_brazos": "NO COMPARABLE — `required` del esquema B es exactamente el conjunto que "
                          "`G_claves_esperadas` comprueba, asi que en B la validez estructural "
                          "esta garantizada por construccion: es la restriccion, no una medicion.",
        "omision_ambiental_asimetrica": "El brazo A de cada caso se ejecuta primero, asi que solo A "
                                        "puede encontrar el modelo NO residente y toparse con el "
                                        "umbral de 1400 MB; B lo encuentra ya cargado y solo topa "
                                        "con el de 150. Las omisiones por memoria recaen "
                                        "estructuralmente sobre A y sesgan su denominador. Se "
                                        "neutraliza dejando el modelo residente ANTES de arrancar.",
        "D_bajo_claves_del_modelo": "Se registra `args_claves_crudas` por ejecucion: en B el "
                                    "esquema puede impedir por gramatica el error de nomenclatura "
                                    "que en A si es posible, de modo que una ventaja de B en D "
                                    "podria deberse a eso y no al razonamiento. Condicionar el "
                                    "analisis a «claves correctas» antes de concluir.",
        "ejecuciones": ejecuciones,
    }
    tmp = destino.with_name(destino.name + ".parcial")
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)
        fh.flush()
        os.fsync(fh.fileno())  # el renombrado es atomico; sin fsync el CONTENIDO no es durable
    tmp.replace(destino)
    # Si el proceso muriera entre el volcado y el renombrado, el `.parcial` conserva los datos de
    # ese caso y el destino conserva enteros los casos anteriores. No se pierde nada: hay que
    # mirar ambos ficheros. La ventana es de milisegundos y no se puede cerrar del todo.


def main() -> int:
    p = argparse.ArgumentParser(description="Experimento A/B sobre el campo `format`")
    p.add_argument("--ejecutar", action="store_true",
                   help="obligatorio: sin esta bandera no se envia ninguna inferencia")
    p.add_argument("--modelo", default="qwen2.5:0.5b")
    args = p.parse_args()

    casos = casos_benchmark.CASOS
    for c in casos:
        if superficie_ab.sha_prompt(c, "A") != superficie_ab.sha_prompt(c, "B"):
            print(f"ABORTA: los prompts de A y B difieren en el caso {c.letra}; tanda anulada")
            return 2
    if not args.ejecutar:
        print(json.dumps({
            "estado": "INERTE — no se ha ejecutado ninguna inferencia",
            "casos": [{"letra": c.letra, "funciones": len(c.FUNCIONES),
                       "sha_prompt": superficie_ab.sha_prompt(c, "A"),
                       "sha_identico_en_A_y_B": True,
                       "longitud_prompt": len(superficie_ab.construir_prompt(c, "A"))}
                      for c in casos],
            "repeticiones": REPETICIONES, "timeout_s": TIMEOUT_S,
            "opciones_generacion": superficie_ab.OPCIONES_GENERACION,
        }, ensure_ascii=False, indent=2))
        return 0

    # Un typo en `--modelo` («qwen2.5:0.5B») caia en los valores por defecto: 1 repeticion en vez
    # de 3 y `exploratorio: true`, degradando la tanda de 30 a 10 ejecuciones en silencio y con
    # codigo de salida 0. Ahora se rechaza.
    if args.modelo not in REPETICIONES:
        print(f"modelo desconocido: {args.modelo!r}. Declarados: {sorted(REPETICIONES)}")
        return 64

    n = REPETICIONES[args.modelo]
    marca = _dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    # El PID evita que dos tandas lanzadas en el mismo segundo compartan destino y `.parcial`, en
    # cuyo caso la segunda pisaba a la primera sin error.
    destino = AQUI / f"evidencia-ab-{args.modelo.replace(':', '-')}-{marca}-{os.getpid()}.json"

    ejecuciones: list[dict] = []
    orden = 0
    for c in casos:
        # --- brazo A: TODAS sus repeticiones antes de cualquier B de este caso (invariante J).
        # `ids_a` recoge SOLO ejecuciones A validas. Antes admitia tambien las omitidas, asi que si
        # las tres A salian AMBIENTAL —por la RAM fluctuante, que es el motivo de existir de la
        # guarda— y el entorno se recuperaba, B se ejecutaba referenciando ejecuciones que nunca
        # ocurrieron: el ORDEN de J se cumplia, pero la GARANTIA que J existe para dar, no.
        ids_a: list[str] = []
        fallos_a: list[str] = []
        for i in range(n):
            orden += 1
            try:
                r = una_ejecucion(args.modelo, "A", c, i + 1, orden)
            except Exception as e:  # noqa: BLE001 — se registra, no se silencia
                fallos_a.append(repr(e))
                ejecuciones.append({"caso": c.letra, "brazo": "A", "repeticion": i + 1,
                                    "orden_en_la_tanda": orden, "omitido": True,
                                    "motivo": "excepcion_en_A", "error": repr(e),
                                    "identificador": f"{c.letra}:A{i + 1}", "clase": "EXCEPCION",
                                    "instante": _dt.datetime.now().isoformat(timespec="seconds")})
                continue  # se sigue con las repeticiones restantes: un fallo no descarta las demas
            ejecuciones.append(r)
            if not r.get("omitido"):
                ids_a.append(r["identificador"])

        # --- brazo B: solo existe si A dejo al menos UN registro valido para ESTE caso.
        if not ids_a:
            orden += 1
            ejecuciones.append({"caso": c.letra, "brazo": "B", "repeticion": None,
                                "orden_en_la_tanda": orden, "omitido": True,
                                "motivo": "A_no_registrado", "error": fallos_a or None,
                                "identificador": f"{c.letra}:B0", "clase": "OMITIDO",
                                "instante": _dt.datetime.now().isoformat(timespec="seconds")})
        else:
            for i in range(n):
                orden += 1
                try:
                    ejecuciones.append(
                        una_ejecucion(args.modelo, "B", c, i + 1, orden, tuple(ids_a)))
                except Exception as e:  # noqa: BLE001
                    ejecuciones.append({"caso": c.letra, "brazo": "B", "repeticion": i + 1,
                                        "orden_en_la_tanda": orden, "omitido": True,
                                        "motivo": "excepcion_en_B", "error": repr(e)})
                    break

        # --- se persiste tras CADA caso completo: si el proceso muere, lo medido sobrevive.
        _persistir(destino, ejecuciones, completo=(c is casos[-1]), ultimo_caso=c.letra)

    validas = [r for r in ejecuciones if not r.get("omitido")]
    print(f"[evidencia] {destino}")
    print(f"[resumen] {len(validas)} validas de {len(ejecuciones)} registradas")
    if not validas:
        # Codigo de salida distinto: una tanda que no midio nada no puede terminar como un exito.
        print("[aviso] la tanda no produjo NINGUNA ejecucion valida")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
