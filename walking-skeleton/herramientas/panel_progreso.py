"""AURA Progress Dashboard: proyeccion HTML estatica del estado del PROYECTO.

Es un modulo de PROCESO, no una capacidad del producto: no lo importa AURA, no esta en el
runtime y no se integra en `centro_gobierno.panel()`. Sigue el precedente de
`core/centro_gobierno.publicar()`.

PROYECCION DESECHABLE (ADR-0023): el HTML no lleva estado propio. Se construye de ficheros que ya
existen (mapa maestro, MAPA fisico, DECISION-REQUERIDA, CHECKPOINT, registro del gate); borrarlo y
regenerarlo da lo mismo. Si fuera una segunda fuente de verdad reabriria el patron «declarado != real».

REGLAS DE VERACIDAD:
* El indice NO se calcula aqui: se IMPORTA `herramientas/indice_madurez.py` por ruta. Copiar la
  formula crearia dos indices que divergen.
* Una fuente ilegible produce un bloque con `error`; jamas cifras inventadas.
* Cada bloque lleva `origen`, `fecha`, `fecha_origen` y `desactualizado`. El umbral de antiguedad es un
  parametro del panel, NO una propiedad del sistema. `desactualizado` es `None` si no hay fecha que
  comparar (jamas se sustituye por el mtime del fichero) o si la fecha es futura (`fecha_futura`).
* TODO string que viene de una fuente se CENSURA (MAC, uuid, serie, IP, secretos) UNA vez al construir
  el modelo: `--json` y el HTML ven lo mismo. Los textos de capacidad/bloqueo son literales SALVO censura.
* Cada fuente se valida (esquema) y, si no cumple, produce un bloque `error` visible sin tumbar el resto.
* NUNCA se escribe en las fuentes. Solo se escribe el HTML de salida, de forma atomica.

Uso (desde walking-skeleton/):  python3 -m herramientas.panel_progreso [--json] [--salida RUTA]
"""

from __future__ import annotations

import argparse
import html
import importlib.util
import json
import os
import re
import subprocess
import sys
import tomllib
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from herramientas import procedencia_panel as proc
from herramientas.censura_panel import censurar

RAIZ_REPO = Path(__file__).resolve().parents[2]
REGISTRO_GATE_DEFECTO = Path.home() / ".local/state/aura/quality-gate-ultimo.json"
UMBRAL_DIAS_DEFECTO = 7
TITULO = "AURA Progress Dashboard"

AVISO_DIMENSIONES = "el repositorio no define nombres de dimensión: se muestran solo las letras del mapa maestro"
NOTA_CALIDAD = "El % de pruebas aprobadas NO es avance del proyecto: mide salud de la base, no madurez."
SIGNIFICADO = {
    "mvp": "Lanzamiento: solo las capacidades de alcance MVP (Bible 2.2).",
    "horizonte": "Horizonte completo: todas las capacidades hasta R4 y H.",
}
FORMULA = (
    "core = media por dimensión de min(nivel,3)/3; ready = media de max(nivel-3,0)/3; "
    "índice = (core + ready) / 2. Calculado por herramientas/indice_madurez.py."
)

# Etiquetas de bloqueo DERIVADAS por patrones sobre el texto literal. Son una ayuda de lectura,
# no un dato del mapa maestro: por eso el modelo las marca con `derivada: True`.
_PATRONES_ETIQUETA = (
    ("decisión", re.compile(r"decisi|\bCEO\b|\bacta", re.I)),
    ("hardware/físico", re.compile(r"hardware|encendid|presente|físic|fisic", re.I)),
    ("nube/D24", re.compile(r"D24|nube", re.I)),
)

TOLERANCIA_FUTURO = timedelta(minutes=5)
_FECHA = re.compile(r"(?<![\d-])(\d{4}-\d{2}-\d{2})(?![\d-])")


def _fecha_de_texto(texto: str) -> datetime | None:
    """Primera fecha AAAA-MM-DD VALIDA y aislada (no dentro de un numero mas largo); si no hay, None."""
    for m in _FECHA.finditer(texto or ""):
        try:
            return datetime.strptime(m.group(1), "%Y-%m-%d")
        except ValueError:
            continue
    return None


def _git(raiz: Path, *args: str) -> str | None:
    """Git de SOLO LECTURA sobre `raiz`; None si no hay git, no es un repo o no hay salida."""
    entorno = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    try:
        r = subprocess.run(["git", "-C", str(raiz), *args], capture_output=True, text=True, timeout=5, env=entorno)
    except (OSError, subprocess.SubprocessError):
        return None
    salida = r.stdout.strip()
    return salida if r.returncode == 0 and salida else None


def _fecha_git(raiz: Path, ruta: Path) -> datetime | None:
    """Fecha del ULTIMO COMMIT que toco el fichero (no la del contenido sin commitear)."""
    bruto = _git(raiz, "log", "-1", "--format=%cI", "--", str(ruta))
    try:
        return datetime.fromisoformat(bruto) if bruto else None
    except ValueError:
        return None


def _a_referencia(fecha: datetime, ahora: datetime) -> datetime:
    """Lleva `fecha` al reloj de `ahora`: CONVIERTE si trae zona; solo etiqueta si es ingenua."""
    if fecha.tzinfo is None:
        return fecha if ahora.tzinfo is None else fecha.replace(tzinfo=ahora.tzinfo)
    if ahora.tzinfo is None:
        return fecha.astimezone().replace(tzinfo=None)
    return fecha.astimezone(ahora.tzinfo)


def _bloque(
    origen: str,
    fecha: datetime | None,
    ahora: datetime,
    umbral: int,
    con_hora: bool = False,
    fecha_origen: str = "contenido",
) -> dict[str, Any]:
    desactualizado: bool | None = None
    futura = False
    if fecha is not None:
        ref = _a_referencia(fecha, ahora)
        futura = (ref - ahora) > TOLERANCIA_FUTURO
        desactualizado = None if futura else (ahora - ref) > timedelta(days=umbral)
    texto = None if fecha is None else fecha.isoformat(timespec="seconds") if con_hora else fecha.date().isoformat()
    return {
        "origen": origen,
        "fecha": texto,
        "fecha_origen": None if fecha is None else fecha_origen,
        "fecha_futura": futura,
        "desactualizado": desactualizado,
    }


def _error(origen: str, motivo: str) -> dict[str, Any]:
    return {
        "origen": origen,
        "fecha": None,
        "fecha_origen": None,
        "fecha_futura": False,
        "desactualizado": None,
        "error": censurar(motivo),
    }


def etiquetas_bloqueo(texto: str) -> list[str]:
    """Etiquetas DERIVADAS del texto de un bloqueo; vacio si no hay bloqueo."""
    if not texto.strip():
        return []
    etiquetas = [nombre for nombre, patron in _PATRONES_ETIQUETA if patron.search(texto)]
    return etiquetas or ["dependencia"]


def _cargar_indice() -> Any:
    ruta = RAIZ_REPO / "herramientas/indice_madurez.py"
    spec = importlib.util.spec_from_file_location("indice_madurez_oficial", ruta)
    if spec is None or spec.loader is None:
        raise FileNotFoundError(f"no se puede cargar {ruta}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _escala(texto: str) -> dict[int, str]:
    nombres = {int(n): t.strip() for n, t in re.findall(r"(\d)\s+([^·\d][^·]*)", texto)}
    if sorted(nombres) != list(range(7)):
        raise ValueError(f"la escala del mapa maestro no define los niveles 0-6: {texto!r}")
    return nombres


# --------------------------------------------------------------------------- bloques
_CAMPOS_TEXTO = ("dim", "capacidad", "alcance", "evidencia")
_ALCANCE_CONOCIDO = re.compile(r"MVP|H|R\d")


def _es_entero(x: object) -> bool:
    return isinstance(x, int) and not isinstance(x, bool)


def _validar_capacidades(caps: object) -> list[dict[str, Any]]:
    if not isinstance(caps, list):
        raise ValueError("«capacidades» no es una lista")
    for i, c in enumerate(caps):
        if not isinstance(c, dict):
            raise ValueError(f"capacidad #{i} no es un objeto")
        for campo in _CAMPOS_TEXTO:
            if not isinstance(c.get(campo), str):
                raise ValueError(f"capacidad #{i}: «{campo}» debe ser texto")
        if not _es_entero(c.get("nivel")) or not 0 <= c["nivel"] <= 6:
            raise ValueError(f"capacidad #{i}: «nivel» debe ser un entero 0-6")
        if "bloqueo" in c and not isinstance(c["bloqueo"], str):
            raise ValueError(f"capacidad #{i}: «bloqueo» debe ser texto")
    return caps


def _censurar_capacidad(c: dict[str, Any]) -> dict[str, Any]:
    return {k: censurar(v) if isinstance(v, str) else v for k, v in c.items()}


def _avisos_alcance(caps: list[dict[str, Any]]) -> list[str]:
    cuenta: dict[str, int] = defaultdict(int)
    for c in caps:
        if not _ALCANCE_CONOCIDO.fullmatch(c["alcance"]):
            cuenta[c["alcance"]] += 1
    return [
        f"alcance desconocido «{a}» ({n} capacidades): no cuenta en el índice MVP; no se normaliza"
        for a, n in sorted(cuenta.items())
    ]


class _Mapa:
    """Mapa maestro leido UNA vez; si falla, guarda el motivo y los tres bloques lo propagan."""

    def __init__(self, raiz: Path) -> None:
        self.origen = "milestones/mapa-maestro/capacidades.json"
        self.ruta = raiz / self.origen
        self.error: str | None = None
        self.caps: list[dict[str, Any]] = []
        self.actualizado = ""
        self.escala: dict[int, str] = {}
        self.mvp: dict[str, Any] = {}
        self.horizonte: dict[str, Any] = {}
        self.avisos: list[str] = []
        try:
            datos = json.loads(self.ruta.read_text(encoding="utf-8"))
            self.actualizado = str(datos["actualizado"])
            self.escala = _escala(str(datos["escala"]))
            self.caps = [_censurar_capacidad(c) for c in _validar_capacidades(datos["capacidades"])]
            self.avisos = _avisos_alcance(self.caps)
            im = _cargar_indice()
            try:
                self.mvp = im.calcular(self.caps, "MVP")
                self.horizonte = im.calcular(self.caps, None)
            except im.IndiceInvalido as e:
                raise ValueError(f"IndiceInvalido: {e}") from e
        except (OSError, ValueError, KeyError, TypeError) as e:
            self.error = f"{type(e).__name__}: {e}"

    def bloque(self, ahora: datetime, umbral: int) -> dict[str, Any]:
        if self.error:
            return _error(self.origen, self.error)
        return _bloque(self.origen, _fecha_de_texto(self.actualizado), ahora, umbral)


def _resumen_indice(r: dict[str, Any], clave: str) -> dict[str, Any]:
    return {
        "core": r["core"],
        "ready": r["ready"],
        "indice": r["indice"],
        "n": sum(v["n"] for v in r["dimensiones"].values()),
        "significado": SIGNIFICADO[clave],
        "formula": FORMULA,
    }


def _por_nivel(caps: list[dict[str, Any]]) -> dict[int, int]:
    cuenta = dict.fromkeys(range(7), 0)
    for c in caps:
        cuenta[c["nivel"]] += 1
    return cuenta


def _bloque_global(m: _Mapa, ahora: datetime, umbral: int) -> dict[str, Any]:
    b = m.bloque(ahora, umbral)
    if m.error:
        return b
    b.update(
        mvp=_resumen_indice(m.mvp, "mvp"),
        horizonte=_resumen_indice(m.horizonte, "horizonte"),
        por_nivel=_por_nivel(m.caps),
        total=len(m.caps),
        avisos=m.avisos,
        actualizado=censurar(m.actualizado),
        escala=m.escala,
        por_procedencia=proc.resumen(m.caps),
    )
    return b


def _bloque_dimensiones(m: _Mapa, ahora: datetime, umbral: int) -> dict[str, Any]:
    b = m.bloque(ahora, umbral)
    if m.error:
        return b
    por_dim: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for c in m.caps:
        por_dim[c["dim"]].append(c)
    dims = {}
    for d, v in m.horizonte["dimensiones"].items():
        mvp = m.mvp["dimensiones"].get(d)
        dims[d] = {
            "indice": v["indice"],
            "core": v["core"],
            "ready": v["ready"],
            "n": v["n"],
            "mvp": None
            if mvp is None
            else {"indice": mvp["indice"], "core": mvp["core"], "ready": mvp["ready"], "n": mvp["n"]},
            "por_nivel": _por_nivel(por_dim[d]),
            "capacidades": [c["capacidad"] for c in por_dim[d]],
        }
    b.update(dimensiones=dims, aviso=AVISO_DIMENSIONES)
    return b


def _bloque_capacidades(m: _Mapa, ahora: datetime, umbral: int) -> dict[str, Any]:
    b = m.bloque(ahora, umbral)
    if m.error:
        return b
    b["capacidades"] = [
        {
            "dim": c["dim"],
            "capacidad": c["capacidad"],
            "nivel": c["nivel"],
            "estado": m.escala[c["nivel"]],
            "alcance": c.get("alcance", ""),
            "evidencia": c.get("evidencia", ""),
            "bloqueo": c.get("bloqueo", ""),
            "etiquetas_bloqueo": etiquetas_bloqueo(str(c.get("bloqueo", ""))),
            "derivada": True,
            **proc.anotar(c),
        }
        for c in m.caps
    ]
    return b


def _validar_registro(d: object) -> datetime:
    """Esquema del registro del gate; devuelve la fecha o lanza ValueError con el motivo."""
    if not isinstance(d, dict):
        raise ValueError("el registro no es un objeto JSON")
    if d["resultado"] not in ("PASS", "FAIL"):
        raise ValueError(f"«resultado» debe ser PASS o FAIL: {d['resultado']!r}")
    pasos = d["pasos"]
    if not isinstance(pasos, dict) or not all(isinstance(k, str) and isinstance(v, str) for k, v in pasos.items()):
        raise ValueError("«pasos» debe ser un objeto texto->texto")
    py = d["pytest"]
    if py is not None and not (
        isinstance(py, dict) and all(isinstance(k, str) and _es_entero(v) for k, v in py.items())
    ):
        raise ValueError("«pytest» debe ser null o un objeto texto->entero")
    if not isinstance(d["sha"], str):
        raise ValueError("«sha» debe ser texto")
    if d.get("cambios_sin_commit") is not None and not _es_entero(d["cambios_sin_commit"]):
        raise ValueError("«cambios_sin_commit» debe ser un entero")
    if not isinstance(d["fecha"], str):
        raise ValueError("«fecha» debe ser texto ISO")
    return datetime.fromisoformat(d["fecha"])


def _sha_vs_head(raiz: Path, sha: str) -> str:
    head = _git(raiz, "rev-parse", "HEAD")
    if not head or not re.fullmatch(r"[0-9a-f]{4,40}", sha.lower()):
        return "no comprobado"
    return "coincide" if head.lower().startswith(sha.lower()) else "distinto"


def _bloque_gate(registro: Path | None, raiz: Path, ahora: datetime, umbral: int) -> dict[str, Any]:
    origen = str(registro) if registro else str(REGISTRO_GATE_DEFECTO)
    sin = {"origen": origen, "fecha": None, "desactualizado": None, "estado": "sin registro estructurado"}
    if registro is None or not registro.exists():
        return sin
    try:
        d = json.loads(registro.read_text(encoding="utf-8"))
        fecha = _validar_registro(d)
        b = _bloque(origen, fecha, ahora, umbral, con_hora=True)
        b.update(
            estado="registrado",
            resultado=d["resultado"],
            sha=censurar(d["sha"]),
            pasos={censurar(k): censurar(v) for k, v in d["pasos"].items()},
            pytest={censurar(k): v for k, v in d["pytest"].items()} if d["pytest"] is not None else None,
            cambios_sin_commit=d.get("cambios_sin_commit"),
            sha_vs_head=_sha_vs_head(raiz, d["sha"]),
        )
        b["vigente"] = b["sha_vs_head"] == "coincide"
        return b
    except (OSError, ValueError, KeyError, TypeError) as e:
        return _error(origen, f"{type(e).__name__}: {e}")


def _bloque_calidad(raiz: Path, registro: Path | None, ahora: datetime, umbral: int) -> dict[str, Any]:
    carpeta = raiz / "walking-skeleton/mutaciones"
    b = _bloque("walking-skeleton/mutaciones/*.toml", None, ahora, umbral)
    total, ficheros, rotos = 0, 0, []
    for f in sorted(carpeta.glob("*.toml")):
        try:
            total += len(tomllib.loads(f.read_text(encoding="utf-8")).get("mutante", []))
            ficheros += 1
        except (OSError, tomllib.TOMLDecodeError) as e:
            rotos.append(f"{f.name}: {e}")
    if rotos:
        b["ficheros_con_error"] = rotos
    b.update(
        gate=_bloque_gate(registro, raiz, ahora, umbral),
        garantias_mutacion=total,
        ficheros_mutacion=ficheros,
        nota=NOTA_CALIDAD,
    )
    return b


def _filas_tabla(seccion: str) -> list[list[str]]:
    filas = []
    for linea in seccion.splitlines():
        s = linea.strip()
        if s.startswith("|") and s.endswith("|"):
            celdas = [c.strip().replace("**", "") for c in s.strip("|").split("|")]
            if not all(re.fullmatch(r":?-{3,}:?", c) for c in celdas):
                filas.append(celdas)
    return filas


def _secciones_7(texto: str) -> list[str]:
    partes = re.split(r"(?m)^## ", texto)
    return [p for p in partes if p.startswith("7.")]


def _bloque_ecosistema(raiz: Path, ahora: datetime, umbral: int) -> dict[str, Any]:
    origen = "milestones/m3-entry/MAPA-ECOSISTEMA-FISICO.md"
    ruta = raiz / origen
    try:
        texto = censurar(ruta.read_text(encoding="utf-8"))  # censura ANTES de construir nada
        tablas = [t for t in map(_filas_tabla, _secciones_7(texto)) if len(t) > 1]
        if not tablas:
            raise ValueError("ninguna sección «## 7.» contiene una tabla")
        cab, *filas = tablas[0]
        idx = {}
        for clave in ("equipo", "estado", "bloqueo"):
            pos = [i for i, c in enumerate(cab) if clave in c.lower()]
            if not pos:
                raise ValueError(f"la tabla no tiene columna {clave.capitalize()}")
            idx[clave] = pos[0]
        b = _bloque(origen, _fecha_git(raiz, ruta), ahora, umbral, con_hora=True, fecha_origen="git")
        b["filas"] = [{k: f[i] if i < len(f) else "" for k, i in idx.items()} for f in filas]
        return b
    except (OSError, ValueError) as e:
        return _error(origen, f"{type(e).__name__}: {e}")


def _estado_decision(texto: str) -> str | None:
    m = re.search(r"\*\*Estado:\*\*\s*(.+)", texto) or re.search(r"\*\*Estado:\s*(.+?)\*\*", texto)
    return m.group(1).strip() if m else None


def _bloque_bloqueos(raiz: Path, m: _Mapa, ahora: datetime, umbral: int) -> dict[str, Any]:
    carpeta = raiz / "milestones/m3-entry"
    origen = "milestones/m3-entry/DECISION-REQUERIDA-*.md"
    try:
        ficheros = sorted(carpeta.glob("DECISION-REQUERIDA-*.md"))
        decisiones = []
        for f in ficheros:
            estado = _estado_decision(censurar(f.read_text(encoding="utf-8")))
            decisiones.append(
                {
                    "fichero": censurar(f.name),
                    "estado": estado if estado is not None else "sin línea de estado",
                    "resuelta": bool(estado and estado.lower().startswith("resuelt")),
                }
            )
    except OSError as e:
        return _error(origen, f"{type(e).__name__}: {e}")
    ultimo = max((f for f in (_fecha_git(raiz, x) for x in ficheros) if f), default=None, key=lambda f: f.timestamp())
    b = _bloque(origen, ultimo, ahora, umbral, con_hora=True, fecha_origen="git")
    b.update(
        decisiones=decisiones,
        total=len(decisiones),
        resueltas=sum(1 for d in decisiones if d["resuelta"]),
        pendientes=sum(1 for d in decisiones if not d["resuelta"]),
    )
    if m.error:
        b["por_etiqueta_error"] = censurar(m.error)
        return b
    grupos: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for c in m.caps:
        texto = str(c.get("bloqueo", ""))
        for etiqueta in etiquetas_bloqueo(texto):
            grupos[etiqueta].append(
                {"dim": c["dim"], "capacidad": c["capacidad"], "nivel": c["nivel"], "bloqueo": censurar(texto)}
            )
    b.update(por_etiqueta=dict(grupos), derivada=True)
    return b


def _bloque_checkpoint(raiz: Path, ahora: datetime, umbral: int) -> dict[str, Any]:
    origen = "CHECKPOINT-CONTINUIDAD.md"
    ruta = raiz / origen
    try:
        titulos = re.findall(r"(?m)^## (.+)$", ruta.read_text(encoding="utf-8"))
        if not titulos:
            raise ValueError("el checkpoint no tiene encabezados «## »")
        b = _bloque(origen, _fecha_de_texto(titulos[-1]), ahora, umbral)
        b["titulo"] = censurar(titulos[-1].strip())
        return b
    except (OSError, ValueError) as e:
        return _error(origen, f"{type(e).__name__}: {e}")


def construir_modelo(
    raiz: Path,
    ahora: datetime,
    umbral_dias: int = UMBRAL_DIAS_DEFECTO,
    registro_gate: Path | None = REGISTRO_GATE_DEFECTO,
) -> dict[str, Any]:
    """Modelo del panel. PURO sobre ficheros: solo lee. `registro_gate=None` = sin registro."""
    m = _Mapa(raiz)
    return {
        "generado": ahora.isoformat(timespec="seconds"),
        "umbral_dias": umbral_dias,
        "global": _bloque_global(m, ahora, umbral_dias),
        "dimensiones": _bloque_dimensiones(m, ahora, umbral_dias),
        "capacidades": _bloque_capacidades(m, ahora, umbral_dias),
        "calidad": _bloque_calidad(raiz, registro_gate, ahora, umbral_dias),
        "ecosistema": _bloque_ecosistema(raiz, ahora, umbral_dias),
        "bloqueos": _bloque_bloqueos(raiz, m, ahora, umbral_dias),
        "checkpoint": _bloque_checkpoint(raiz, ahora, umbral_dias),
    }


# --------------------------------------------------------------------------- HTML
def _pct(v: float) -> float:
    """Tanto por uno a porcentaje con 1 decimal, REDONDEADO como la cifra oficial; solo un valor < 100 que
    redondee a 100.0 se muestra 99.9 (nunca se pinta «completo» lo que no lo es)."""
    r = round(v * 100, 1)
    if v < 1 and r >= 100:
        r = 99.9
    return max(0.0, min(100.0, r))


def porcentaje(v: float) -> str:
    return f"{_pct(v):.1f} %"


def _e(x: object) -> str:
    return html.escape(str(x), quote=True)


_CSS = """
:root{--fondo:#fafafa;--texto:#1b1b1f;--borde:#d0d0d8;--barra:#3a6ea5;--pista:#e4e4ea;--aviso:#8a5a00;--error:#b00020}
@media(prefers-color-scheme:dark){:root{--fondo:#16161a;--texto:#e8e8ee;--borde:#3a3a44;--barra:#6aa3e0;--pista:#2a2a32;--aviso:#e0b050;--error:#ff6b81}}
body{font:15px/1.5 system-ui,sans-serif;background:var(--fondo);color:var(--texto);margin:0 auto;max-width:72rem;padding:1rem}
table{border-collapse:collapse;width:100%;margin:.5rem 0}th,td{border:1px solid var(--borde);padding:.3rem .5rem;text-align:left;vertical-align:top}
.barra{background:var(--pista);border-radius:4px;overflow:hidden;min-width:8rem}.barra span{display:block;background:var(--barra);height:.9rem}
.aviso{color:var(--aviso);font-weight:600}.error{color:var(--error);font-weight:600}.nota{opacity:.8}
"""


def _estado_fecha(b: dict[str, Any], umbral: int) -> str:
    if b.get("error"):
        return f'<p class="error">Error: {_e(b["error"])}</p>'
    origen = _e(b.get("fecha_origen") or "sin origen")
    if b.get("fecha_futura"):
        return f'<p class="aviso">fecha futura: {_e(b["fecha"])} (origen: {origen}); no se compara con el umbral</p>'
    if b.get("desactualizado") is None:
        return '<p class="aviso">sin fecha para comparar</p>'
    if b["desactualizado"]:
        return (
            f'<p class="aviso">desactualizado: fuente de {_e(b["fecha"])} (origen: {origen}; umbral {umbral} días)</p>'
        )
    return f'<p class="nota">fuente de {_e(b["fecha"])} (origen: {origen}), dentro del umbral de {umbral} días</p>'


def _barra(v: float) -> str:
    return f'<div class="barra"><span style="width:{_pct(v):.1f}%"></span></div>'


def _seccion_resumen(m: dict[str, Any], u: int) -> str:
    g = m["global"]
    out = ["<h2 id='resumen'>Resumen</h2>", _estado_fecha(g, u)]
    if g.get("error"):
        return "".join(out)
    for clave, titulo in (("mvp", "Lanzamiento (MVP)"), ("horizonte", "Horizonte completo")):
        r = g[clave]
        if r["n"] == 0:
            out.append(
                f"<h3>{titulo}</h3><p>{_e(r['significado'])}</p><p class='aviso'>sin capacidades en este ámbito</p>"
            )
            continue
        out.append(
            f"<h3>{titulo}</h3><p>{_e(r['significado'])}</p>"
            f"<p><b>Índice: {porcentaje(r['indice'])}</b> · Core {porcentaje(r['core'])} · Ready {porcentaje(r['ready'])}</p>"
            f"{_barra(r['indice'])}"
        )
    out.extend(f'<p class="aviso">{_e(a)}</p>' for a in g["avisos"])
    out.append(proc.html_resumen(g["por_procedencia"]))
    out.append(f"<p class='nota'>{_e(FORMULA)}</p><p>Capacidades: {g['total']}. Por nivel:</p><table><tr>")
    out.append("".join(f"<th>{n} {_e(g['escala'][n])}</th>" for n in range(7)) + "</tr><tr>")
    out.append("".join(f"<td>{g['por_nivel'][n]}</td>" for n in range(7)) + "</tr></table>")
    return "".join(out)


def _indice_mvp_dim(mvp: dict[str, Any] | None) -> str:
    if mvp is None:
        return "— (sin capacidades MVP)"
    return f"{porcentaje(mvp['indice'])} (n {mvp['n']})"


def _seccion_dimensiones(m: dict[str, Any], u: int) -> str:
    d = m["dimensiones"]
    out = ["<h2 id='dimensiones'>Dimensiones</h2>", _estado_fecha(d, u)]
    if d.get("error"):
        return "".join(out)
    out.append(
        f"<p class='nota'>{_e(d['aviso'])}</p><table><tr><th>Dim</th><th>n</th><th>Índice (horizonte)</th><th>Barra</th><th>Índice MVP</th></tr>"
    )
    for letra, v in d["dimensiones"].items():
        out.append(
            f"<tr><td>{_e(letra)}</td><td>{v['n']}</td>"
            f"<td>{porcentaje(v['indice'])} (core {porcentaje(v['core'])}, ready {porcentaje(v['ready'])})</td>"
            f"<td>{_barra(v['indice'])}</td><td>{_indice_mvp_dim(v['mvp'])}</td></tr>"
        )
    return "".join(out) + "</table>"


def _seccion_capacidades(m: dict[str, Any], u: int) -> str:
    c = m["capacidades"]
    out = ["<h2 id='capacidades'>Capacidades</h2>", _estado_fecha(c, u)]
    if c.get("error"):
        return "".join(out)
    out.append(
        "<p class='nota'>Las etiquetas de bloqueo son DERIVADAS por patrones; el texto del bloqueo es literal.</p>"
        "<table><tr><th>Dim</th><th>Capacidad</th><th>Estado</th><th>Alcance</th><th>Evidencia</th><th>Procedencia</th><th>Bloqueo</th></tr>"
    )
    for x in c["capacidades"]:
        etiquetas = ", ".join(x["etiquetas_bloqueo"]) or "—"
        out.append(
            f"<tr><td>{_e(x['dim'])}</td><td>{_e(x['capacidad'])}</td><td>{x['nivel']} · {_e(x['estado'])}</td>"
            f"<td>{_e(x['alcance'])}</td><td>{_e(x['evidencia'] or 'sin evidencia')}</td><td>{proc.html_celda(x)}</td>"
            f"<td>{_e(censurar(x['bloqueo'])) or '—'} <i>[{_e(etiquetas)}, derivada]</i></td></tr>"
        )
    return "".join(out) + "</table>"


def _aviso_head(estado: str) -> str:
    if estado == "coincide":
        return "<p class='nota'>sha coincide con HEAD</p>"
    if estado == "distinto":
        return (
            "<p class='aviso'>el sha del registro no coincide con HEAD actual: el gate no corrió sobre este código</p>"
        )
    return "<p class='aviso'>no comprobado contra HEAD: el resultado no se presenta como vigente</p>"


def _seccion_calidad(m: dict[str, Any], u: int) -> str:
    q = m["calidad"]
    g = q["gate"]
    out = ["<h2 id='calidad'>Calidad</h2>", f"<p class='nota'>{_e(q['nota'])}</p>", "<h3>Quality Gate</h3>"]
    if g.get("error"):
        out.append(f'<p class="error">Error: {_e(g["error"])}</p>')
    elif g["estado"] != "registrado":
        out.append(f"<p class='aviso'>{_e(g['estado'])}</p>")
    else:
        p = g["pytest"]
        out.append(_estado_fecha(g, u))
        conteos = (
            "sin conteos de pytest" if p is None else "pytest: " + ", ".join(f"{_e(k)} {_e(v)}" for k, v in p.items())
        )
        cambios = g.get("cambios_sin_commit")
        sha = _e(g["sha"] or "desconocido")
        if g["vigente"]:
            titular = f"<b>{_e(g['resultado'])}</b>"
        elif g["sha_vs_head"] == "distinto":
            titular = f"{_e(g['resultado'])} en otro commit (sha {sha}); no corresponde al HEAD actual"
        else:
            titular = f"{_e(g['resultado'])} (no comprobado contra HEAD)"
        out.append(
            f"<p>{titular} · sha {sha} · {conteos} · "
            f"cambios sin commit: {'no registrado' if cambios is None else _e(cambios)}</p>"
            + _aviso_head(g["sha_vs_head"])
            + "<p>Pasos: "
            + ", ".join(f"{_e(k)} {_e(v)}" for k, v in g["pasos"].items())
            + "</p>"
        )
    out.append(
        f"<h3>Mutación</h3><p>{q['garantias_mutacion']} garantías declaradas en {q['ficheros_mutacion']} ficheros "
        "(declaradas, no ejecuciones: no hay registro de ejecuciones).</p>"
    )
    return "".join(out)


def _seccion_ecosistema(m: dict[str, Any], u: int) -> str:
    e = m["ecosistema"]
    out = ["<h2 id='ecosistema'>Ecosistema</h2>", _estado_fecha(e, u)]
    if e.get("error"):
        return "".join(out)
    out.append("<p class='nota'>Censurado: sin MAC, uuid, serie, secretos; IP solo con el último octeto.</p>")
    out.append("<table><tr><th>Equipo</th><th>Estado</th><th>Bloqueo</th></tr>")
    for f in e["filas"]:
        out.append(f"<tr><td>{_e(f['equipo'])}</td><td>{_e(f['estado'])}</td><td>{_e(f['bloqueo'])}</td></tr>")
    return "".join(out) + "</table>"


def _seccion_bloqueos(m: dict[str, Any], u: int) -> str:
    b = m["bloqueos"]
    out = ["<h2 id='bloqueos'>Bloqueos y decisiones</h2>", _estado_fecha(b, u)]
    if b.get("error"):
        return "".join(out)
    if b["total"] == 0:
        out.append("<p class='aviso'>sin decisiones registradas</p>")
    else:
        out.append(f"<p>Decisiones: {b['pendientes']} pendientes · {b['resueltas']} resueltas.</p><table>")
        out.append("<tr><th>Decisión</th><th>Situación</th><th>Estado declarado</th></tr>")
        for d in b["decisiones"]:
            out.append(
                f"<tr><td>{_e(d['fichero'])}</td><td>{'resuelta' if d['resuelta'] else 'pendiente'}</td><td>{_e(d['estado'])}</td></tr>"
            )
        out.append("</table>")
    if "por_etiqueta_error" in b:
        out.append(f'<p class="error">Error en capacidades: {_e(b["por_etiqueta_error"])}</p>')
        return "".join(out)
    out.append("<h3>Capacidades con bloqueo (agrupación derivada)</h3>")
    for etiqueta, caps in b["por_etiqueta"].items():
        out.append(f"<h4>{_e(etiqueta)} ({len(caps)})</h4><ul>")
        out.extend(f"<li>{_e(c['dim'])} · {_e(c['capacidad'])}: {_e(c['bloqueo'])}</li>" for c in caps)
        out.append("</ul>")
    return "".join(out)


def _seccion_procedencia(m: dict[str, Any]) -> str:
    c = m["checkpoint"]
    out = ["<h2 id='procedencia'>Procedencia y última actualización</h2>"]
    if c.get("error"):
        out.append(f'<p class="error">Error en checkpoint: {_e(c["error"])}</p>')
    else:
        out.append(f"<p>Último punto de control: <b>{_e(c['titulo'])}</b> ({_e(c['fecha'])}).</p>")
    out.append(
        f"<p>Generado {_e(m['generado'])}. Umbral de antigüedad: {m['umbral_dias']} días (configurable, no propiedad del sistema).</p>"
    )
    out.append(
        "<table><tr><th>Bloque</th><th>Origen</th><th>Fecha</th><th>Origen de la fecha</th><th>Desactualizado</th></tr>"
    )
    for k in ("global", "dimensiones", "capacidades", "calidad", "ecosistema", "bloqueos", "checkpoint"):
        b = m[k]
        d = (
            "fecha futura"
            if b.get("fecha_futura")
            else {True: "sí", False: "no", None: "sin dato"}[b["desactualizado"]]
        )
        out.append(
            f"<tr><td>{k}</td><td>{_e(b['origen'])}</td><td>{_e(b['fecha'] or 'sin fecha')}</td>"
            f"<td>{_e(b.get('fecha_origen') or '—')}</td><td>{d}</td></tr>"
        )
    return "".join(out) + "</table>"


def render_html(modelo: dict[str, Any]) -> str:
    """HTML estatico autocontenido (CSS en linea, sin JS). TODO el texto va escapado."""
    u = modelo["umbral_dias"]
    cuerpo = "\n".join(
        (
            _seccion_resumen(modelo, u),
            _seccion_dimensiones(modelo, u),
            _seccion_capacidades(modelo, u),
            _seccion_calidad(modelo, u),
            _seccion_ecosistema(modelo, u),
            _seccion_bloqueos(modelo, u),
            _seccion_procedencia(modelo),
        )
    )
    return (
        "<!doctype html>\n<html lang='es'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width,initial-scale=1'>"
        f"<title>{TITULO}</title><style>{_CSS}</style></head><body><h1>{TITULO}</h1>\n{cuerpo}\n</body></html>\n"
    )


# --------------------------------------------------------------------------- escritura y CLI
def escribir_atomico(texto: str, destino: Path) -> None:
    """Fichero temporal + `os.replace`, como `centro_gobierno.publicar()`: un corte no deja medio panel."""
    destino.parent.mkdir(parents=True, exist_ok=True)
    provisional = destino.with_name(destino.name + ".tmp")
    try:
        provisional.write_text(texto, encoding="utf-8")
        os.replace(provisional, destino)
    except BaseException:
        provisional.unlink(missing_ok=True)
        raise


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="panel_progreso", description=TITULO)
    ap.add_argument("--json", action="store_true", help="imprime el modelo (y no escribe salvo con --salida)")
    ap.add_argument("--salida", type=Path, help="ruta del HTML (por defecto publicado/panel-progreso/index.html)")
    ap.add_argument("--umbral-dias", type=int, default=UMBRAL_DIAS_DEFECTO)
    args = ap.parse_args(argv)
    modelo = construir_modelo(RAIZ_REPO, datetime.now().astimezone(), args.umbral_dias)
    if args.json:
        print(json.dumps(modelo, ensure_ascii=False, indent=2, default=str))
    if not args.json or args.salida:
        destino = args.salida or RAIZ_REPO / "publicado/panel-progreso/index.html"
        escribir_atomico(render_html(modelo), destino)
        print(f"panel escrito en {destino}", file=sys.stderr if args.json else sys.stdout)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
