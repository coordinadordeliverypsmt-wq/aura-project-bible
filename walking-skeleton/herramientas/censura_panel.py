"""Censura de texto para el panel de progreso: quita lo que identifica un equipo de la red del propietario
(MAC, uuid, numero de serie, IP salvo el ultimo octeto) y los secretos (claves, tokens, Bearer, credenciales en URL).

Son PATRONES, no una lista blanca: lo que no encaja se deja tal cual. Se aplica una vez, al construir el modelo.
"""

from __future__ import annotations

import re

_CLAVE = r"(?:contrase[ñn]a|password|passwd|pass|pwd|clave|psk|token|secret|api[_-]?key)"
_MAC = re.compile(r"\b[0-9A-Fa-f]{2}(?:[:-][0-9A-Fa-f]{2}){5}\b|\b[0-9A-Fa-f]{4}\.[0-9A-Fa-f]{4}\.[0-9A-Fa-f]{4}\b")
_UUID = re.compile(
    r"urn:uuid:[0-9A-Fa-f-]+|\b[0-9A-Fa-f]{8}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{12}\b",
    re.I,
)
_SERIE = re.compile(r"\b(?=[A-Z0-9]*[A-Z])(?=[A-Z0-9]*\d)[A-Z0-9]{12,}\b")
_IPV4 = re.compile(r"\b(?:\d{1,3}\.){3}(\d{1,3})\b")
_URL_CREDENCIALES = re.compile(r"(?<=://)[^/\s:@]+:[^@\s/]*@")
_BEARER = re.compile(r"\b(Bearer)\s+\S+", re.I)
# clave, palabras intermedias en la misma linea, separador (: = ：) y valor HASTA fin de linea o de celda «|»
_SECRETO_SEP = re.compile(rf"\b({_CLAVE})\b([^:=：\n|]{{0,40}}?)(\s*[:=：]\s*)[^\n|]*", re.I)
_SECRETO_ESPACIO = re.compile(
    r"\b(password|contrase[ñn]a|token)\b([ \t]+)(?!\[censurado\])([^\s:=：|]+)(?=[\s|]|$)", re.I
)


# --------------------------------------------------------------------------- censura
def _ip_a_sufijo(m: re.Match[str]) -> str:
    octetos = m.group(0).split(".")
    if all(int(o) <= 255 for o in octetos):
        return "." + m.group(1)
    return m.group(0)  # no es una IP (p. ej. una version): se deja tal cual


def censurar(texto: str) -> str:
    """Quita lo que identifica un equipo concreto de la red del propietario (y los secretos)."""
    texto = _UUID.sub("[uuid]", texto)
    texto = _MAC.sub("[MAC]", texto)
    texto = _URL_CREDENCIALES.sub("[censurado]@", texto)
    texto = _BEARER.sub(lambda m: f"{m.group(1)} [censurado]", texto)
    texto = _SECRETO_SEP.sub(lambda m: f"{m.group(1)}{m.group(2)}{m.group(3)}[censurado]", texto)
    texto = _SECRETO_ESPACIO.sub(lambda m: f"{m.group(1)}{m.group(2)}[censurado]", texto)
    texto = _IPV4.sub(_ip_a_sufijo, texto)
    return _SERIE.sub("[serie]", texto)


# --------------------------------------------------------------------------- utilidades de fuentes
