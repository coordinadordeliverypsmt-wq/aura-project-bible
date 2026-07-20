"""Catalogo de OPERACIONES TIPADAS del computador (M2.1).

Define QUE argumentos acepta cada accion y QUE nunca puede hacer, antes de que exista adaptador
alguno. `permissions.CATALOGO` (H3) decide *si una accion necesita confirmacion*; este modulo decide
*si los argumentos concretos son admisibles*. Son preguntas distintas y ambas se resuelven en el
NUCLEO, nunca en el LLM (ADR-0014).

Riesgo RN-2 del Architecture Review M2 Entry: un "agente del computador" tiende a derivar en
"ejecuta este comando", lo que volveria irrelevante la lista roja —cualquier accion destructiva
podria envolverse en un comando—. Por eso el adaptador **solo** podra exponer operaciones de este
catalogo: no hay ruta para ejecucion libre.
"""

from __future__ import annotations

import os


class ErrorDeValidacion(Exception):
    """Los argumentos no son admisibles. El adaptador NUNCA debe recibirlos."""


# Argumentos que espera cada operacion. `rutas` indica cuales deben validarse como rutas del
# sistema de archivos. `permite_comodin` es False salvo en busqueda: un comodin en una operacion
# que altera o destruye convierte un error en una perdida masiva.
ESPECIFICACIONES: dict[str, dict] = {
    "buscar_archivo": {"args": ("patron", "raiz"), "rutas": ("raiz",), "permite_comodin": True},
    "listar_directorio": {"args": ("ruta",), "rutas": ("ruta",), "permite_comodin": False},
    "leer_archivo": {"args": ("ruta",), "rutas": ("ruta",), "permite_comodin": False},
    "abrir_archivo": {"args": ("ruta",), "rutas": ("ruta",), "permite_comodin": False},
    "consultar_estado_sistema": {"args": (), "rutas": (), "permite_comodin": False},
    "mover_archivo": {"args": ("origen", "destino"), "rutas": ("origen", "destino"), "permite_comodin": False},
    "renombrar_archivo": {"args": ("origen", "destino"), "rutas": ("origen", "destino"), "permite_comodin": False},
    "escribir_archivo": {"args": ("ruta", "contenido"), "rutas": ("ruta",), "permite_comodin": False},
    "borrar_archivo": {"args": ("ruta",), "rutas": ("ruta",), "permite_comodin": False},
}


def raices_por_defecto() -> tuple[str, ...]:
    """Ambito permitido por defecto: el directorio del usuario.

    Deliberadamente estrecho. Ampliarlo es una decision explicita de configuracion, no un efecto
    lateral de que el usuario pida algo fuera de ese ambito.
    """
    return (os.path.expanduser("~"),)


def ruta_en_ambito(ruta_absoluta: str, raices: tuple[str, ...] | None = None) -> bool:
    """True si una ruta YA absoluta y resuelta sigue dentro del ambito permitido.

    Se expone para la proteccion TOCTOU del adaptador: tras abrir un descriptor de directorio hay
    que reverificar que ese descriptor sigue apuntando dentro del ambito, y esa comprobacion debe
    usar exactamente el mismo criterio que la validacion inicial. Duplicar la logica alli seria
    arriesgar que ambas divergieran.
    """
    raices = raices or raices_por_defecto()
    for raiz in raices:
        raiz_real = os.path.realpath(os.path.expanduser(raiz))
        if ruta_absoluta == raiz_real or ruta_absoluta.startswith(raiz_real + os.sep):
            return True
    return False


def _validar_ruta(valor: str, raices: tuple[str, ...], permite_comodin: bool) -> str:
    if not isinstance(valor, str) or not valor.strip():
        raise ErrorDeValidacion("ruta vacia o no textual")
    if not permite_comodin and any(c in valor for c in "*?["):
        raise ErrorDeValidacion(f"comodin no permitido en esta operacion: {valor!r}")

    expandida = os.path.expanduser(valor)
    # Las rutas RELATIVAS se rechazan. Se resolverian contra el directorio de trabajo del proceso,
    # que no forma parte del modelo de seguridad: la misma peticion seria admisible o no segun
    # desde donde se lanzara AURA. Detectado por prueba adversarial en M2.1: '../../etc/passwd'
    # resultaba ACEPTADO por quedar el cwd dentro del ambito permitido, lo cual era casualidad.
    if not os.path.isabs(expandida):
        raise ErrorDeValidacion(f"ruta relativa no permitida (debe ser absoluta o '~/...'): {valor!r}")

    # Se distinguen DOS rutas y cada una cumple un papel distinto:
    #   literal  -> normaliza '.' y '..' pero NO resuelve enlaces. Es sobre la que se OPERA.
    #   resuelta -> resuelve enlaces. Sirve solo para COMPROBAR el ambito.
    #
    # Devolver la resuelta era un error de diseno detectado en M2.2: si el usuario pide borrar
    # 'enlace.txt' y se devuelve su destino, se borra OTRO archivo del que el usuario no hablo.
    # El ambito se comprueba sobre ambas: la literal para que no apunte fuera, y la resuelta para
    # que ningun enlace sirva de escape.
    literal = os.path.abspath(expandida)
    resuelta = os.path.realpath(expandida)
    for candidata in (literal, resuelta):
        if not ruta_en_ambito(candidata, raices):
            raise ErrorDeValidacion(f"ruta fuera del ambito permitido: {valor!r} -> {candidata!r}")
    return literal


def validar(accion: str, args: dict, raices: tuple[str, ...] | None = None) -> dict:
    """Devuelve los argumentos normalizados, o lanza `ErrorDeValidacion`.

    Se rechaza toda accion ausente del catalogo: no existe camino para ejecucion arbitraria (RN-2).
    """
    if accion not in ESPECIFICACIONES:
        raise ErrorDeValidacion(f"operacion no permitida (fuera del catalogo): {accion!r}")

    espec = ESPECIFICACIONES[accion]
    raices = raices or raices_por_defecto()

    faltantes = [a for a in espec["args"] if a not in args]
    if faltantes:
        raise ErrorDeValidacion(f"faltan argumentos para {accion!r}: {faltantes}")

    sobrantes = [a for a in args if a not in espec["args"]]
    if sobrantes:
        # Un argumento no declarado podria ser un intento de alterar el comportamiento del adaptador.
        raise ErrorDeValidacion(f"argumentos no declarados para {accion!r}: {sobrantes}")

    normalizados = dict(args)
    for nombre in espec["rutas"]:
        normalizados[nombre] = _validar_ruta(args[nombre], raices, espec["permite_comodin"])
    return normalizados
