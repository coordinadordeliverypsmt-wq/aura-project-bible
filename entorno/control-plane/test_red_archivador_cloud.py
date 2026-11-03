"""`DR-CLOUD-1` — el archivador: **AURA copia al archivo Cloud, y nada más**.

No es memoria cognitiva: es preservación. Y por eso su contrato es casi todo prohibiciones. Un
archivador con permiso para mover o borrar no es un archivador, es un riesgo con buena intención.

Tres barreras, y ninguna depende de que quien lo llame se porte bien:

* **Lista blanca de categorías.** Siete carpetas y ni una más; una categoría inventada no crea
  destino, lo rechaza.
* **Lista negra de contenido.** `.git`, `estado.json`, `eventos.jsonl`, credenciales, caches y
  modelos no se archivan aunque se pidan explícitamente. El runtime vivo se queda en local.
* **Solo copia.** El módulo no importa nada capaz de mover ni de borrar, y hay una prueba que lo
  comprueba sobre el árbol sintáctico, no sobre la buena fe.

Ante Drive ausente **no pasa nada**: se registra el fallo y el original no se toca. Fail-closed es
aquí literal — la ausencia de destino nunca puede convertirse en una modificación del origen.
"""

from __future__ import annotations

import ast
import hashlib
import pathlib

import archivador_cloud as ac


def _repo(tmp_path):
    """Un árbol local mínimo con lo archivable y lo que jamás debe archivarse."""
    raiz = tmp_path / "repo"
    (raiz / ".git").mkdir(parents=True)
    (raiz / "docs").mkdir(parents=True)
    (raiz / ".git" / "config").write_text("[core]\n", encoding="utf-8")
    (raiz / "docs" / "informe.md").write_text("# informe\ncontenido\n", encoding="utf-8")
    (raiz / "estado.json").write_text('{"vivo": true}', encoding="utf-8")
    (raiz / "eventos.jsonl").write_text('{"seq": 1}\n', encoding="utf-8")
    (raiz / ".env").write_text("TOKEN=secreto\n", encoding="utf-8")
    return raiz


def _drive(tmp_path):
    d = tmp_path / "drive" / "AURA_CLOUD"
    d.mkdir(parents=True)
    return d


# ------------------------------------------------------------ categorías --

def test_una_categoria_de_la_lista_blanca_archiva(tmp_path):
    raiz, drive = _repo(tmp_path), _drive(tmp_path)
    r = ac.archivar(raiz, "06_BACKUPS", [raiz / "docs" / "informe.md"], destino=drive)
    assert r["ok"] is True and r["copiados"] == 1
    assert (drive / "06_BACKUPS" / "informe.md").read_text(encoding="utf-8").startswith("# informe")


def test_una_categoria_inventada_no_crea_destino(tmp_path):
    raiz, drive = _repo(tmp_path), _drive(tmp_path)
    r = ac.archivar(raiz, "07_LO_QUE_SEA", [raiz / "docs" / "informe.md"], destino=drive)
    assert r["ok"] is False and r["copiados"] == 0
    assert not (drive / "07_LO_QUE_SEA").exists(), "una categoría inválida no crea carpeta"
    assert any("categoria" in e.lower() for e in r["errores"])


def test_las_siete_categorias_son_exactamente_las_del_archivo():
    assert ac.CATEGORIAS == ("01_CHECKPOINTS", "02_DECISIONES", "03_QUALITY_GATES",
                             "04_MEDICIONES", "05_AUDITORIAS", "06_BACKUPS", "99_ARCHIVO")


# ------------------------------------------------------- lo que nunca se archiva --

def test_git_no_se_archiva_aunque_se_pida(tmp_path):
    raiz, drive = _repo(tmp_path), _drive(tmp_path)
    r = ac.archivar(raiz, "99_ARCHIVO", [raiz / ".git" / "config"], destino=drive)
    assert r["copiados"] == 0
    assert r["ficheros"][0]["resultado"] == ac.RECHAZADO
    assert not (drive / "99_ARCHIVO" / "config").exists()


def test_estado_json_no_se_archiva(tmp_path):
    """Runtime vivo: se queda en local. Archivarlo sería congelar algo que cambia solo."""
    raiz, drive = _repo(tmp_path), _drive(tmp_path)
    r = ac.archivar(raiz, "06_BACKUPS", [raiz / "estado.json"], destino=drive)
    assert r["copiados"] == 0 and r["ficheros"][0]["resultado"] == ac.RECHAZADO


def test_eventos_jsonl_no_se_archiva(tmp_path):
    raiz, drive = _repo(tmp_path), _drive(tmp_path)
    r = ac.archivar(raiz, "06_BACKUPS", [raiz / "eventos.jsonl"], destino=drive)
    assert r["copiados"] == 0 and r["ficheros"][0]["resultado"] == ac.RECHAZADO


def test_una_credencial_no_se_archiva(tmp_path):
    raiz, drive = _repo(tmp_path), _drive(tmp_path)
    r = ac.archivar(raiz, "06_BACKUPS", [raiz / ".env"], destino=drive)
    assert r["copiados"] == 0 and r["ficheros"][0]["resultado"] == ac.RECHAZADO
    assert not (drive / "06_BACKUPS" / ".env").exists()


def test_el_registro_no_filtra_el_contenido_del_secreto(tmp_path):
    """Rechazar no basta: el registro tampoco puede llevarse el secreto dentro."""
    raiz, drive = _repo(tmp_path), _drive(tmp_path)
    import json
    texto = json.dumps(ac.archivar(raiz, "06_BACKUPS", [raiz / ".env"], destino=drive))
    assert "secreto" not in texto and "TOKEN=" not in texto


def test_un_fichero_fuera_de_la_raiz_no_se_archiva(tmp_path):
    raiz, drive = _repo(tmp_path), _drive(tmp_path)
    fuera = tmp_path / "ajeno.md"
    fuera.write_text("no es del repositorio\n", encoding="utf-8")
    r = ac.archivar(raiz, "99_ARCHIVO", [fuera], destino=drive)
    assert r["copiados"] == 0 and r["ficheros"][0]["resultado"] == ac.RECHAZADO


def test_caches_y_modelos_estan_en_la_lista_negra(tmp_path):
    raiz, drive = _repo(tmp_path), _drive(tmp_path)
    for relativa in ("__pycache__/m.pyc", ".pytest_cache/x", ".ollama/models/blob"):
        f = raiz / relativa
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text("x", encoding="utf-8")
        r = ac.archivar(raiz, "99_ARCHIVO", [f], destino=drive)
        assert r["copiados"] == 0, f"{relativa} no debía archivarse"


# ------------------------------------------------------------- fail-closed --

def test_sin_destino_disponible_no_se_toca_el_original(tmp_path):
    raiz = _repo(tmp_path)
    origen = raiz / "docs" / "informe.md"
    antes = origen.read_bytes()
    r = ac.archivar(raiz, "06_BACKUPS", [origen], destino=tmp_path / "no_montado" / "AURA_CLOUD")
    assert r["ok"] is False and r["copiados"] == 0
    assert origen.exists() and origen.read_bytes() == antes, "el original queda intacto"
    assert any("destino" in e.lower() for e in r["errores"])


# ------------------------------------------------------------ idempotencia --

def test_archivar_dos_veces_lo_mismo_no_duplica(tmp_path):
    raiz, drive = _repo(tmp_path), _drive(tmp_path)
    origen = raiz / "docs" / "informe.md"
    ac.archivar(raiz, "06_BACKUPS", [origen], destino=drive)
    r = ac.archivar(raiz, "06_BACKUPS", [origen], destino=drive)
    assert r["ok"] is True and r["copiados"] == 0
    assert r["ficheros"][0]["resultado"] == ac.YA_ARCHIVADO
    assert len(list((drive / "06_BACKUPS").iterdir())) == 1


def test_un_contenido_distinto_versiona_sin_destruir(tmp_path):
    """Conflicto: el original archivado **no se sobrescribe**. Se guarda una versión nueva."""
    raiz, drive = _repo(tmp_path), _drive(tmp_path)
    origen = raiz / "docs" / "informe.md"
    ac.archivar(raiz, "06_BACKUPS", [origen], destino=drive)
    primero = (drive / "06_BACKUPS" / "informe.md").read_text(encoding="utf-8")
    origen.write_text("# informe\nCONTENIDO NUEVO\n", encoding="utf-8")
    r = ac.archivar(raiz, "06_BACKUPS", [origen], destino=drive)
    assert r["ficheros"][0]["resultado"] == ac.VERSIONADO
    assert (drive / "06_BACKUPS" / "informe.md").read_text(encoding="utf-8") == primero, (
        "la copia anterior nunca se destruye")
    versiones = [p for p in (drive / "06_BACKUPS").iterdir() if p.name != "informe.md"]
    assert len(versiones) == 1 and "CONTENIDO NUEVO" in versiones[0].read_text(encoding="utf-8")


def test_la_deteccion_de_identico_usa_el_contenido_no_solo_el_nombre(tmp_path):
    raiz, drive = _repo(tmp_path), _drive(tmp_path)
    origen = raiz / "docs" / "informe.md"
    r = ac.archivar(raiz, "06_BACKUPS", [origen], destino=drive)
    esperado = hashlib.sha256(origen.read_bytes()).hexdigest()
    assert r["ficheros"][0]["hash"] == esperado


# ------------------------------------------------------------- auditabilidad --

def test_el_resultado_es_auditable(tmp_path):
    raiz, drive = _repo(tmp_path), _drive(tmp_path)
    r = ac.archivar(raiz, "04_MEDICIONES", [raiz / "docs" / "informe.md"], destino=drive)
    assert set(r) >= {"ok", "categoria", "destino", "copiados", "bytes", "ficheros", "errores",
                      "instante"}
    f = r["ficheros"][0]
    assert set(f) >= {"origen", "destino", "resultado", "bytes", "hash"}
    assert r["bytes"] == (raiz / "docs" / "informe.md").stat().st_size


def test_el_original_nunca_se_modifica(tmp_path):
    raiz, drive = _repo(tmp_path), _drive(tmp_path)
    origen = raiz / "docs" / "informe.md"
    antes = (origen.read_bytes(), origen.stat().st_mode)
    ac.archivar(raiz, "06_BACKUPS", [origen], destino=drive)
    assert (origen.read_bytes(), origen.stat().st_mode) == antes


# ------------------------------------------- las garantías, sobre el árbol sintáctico --

def test_el_modulo_no_puede_borrar_ni_mover():
    """La garantía central. No basta con no llamarlas: no se importa nada que las ofrezca."""
    fuente = (pathlib.Path(__file__).parent / "archivador_cloud.py").read_text(encoding="utf-8")
    arbol = ast.parse(fuente)
    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.Import):
            for alias in nodo.names:
                assert alias.name.split(".")[0] not in {"os", "subprocess", "shutil", "socket",
                                                        "urllib", "requests", "http"}, alias.name
        elif isinstance(nodo, ast.ImportFrom):
            assert (nodo.module or "").split(".")[0] not in {"os", "subprocess", "shutil"}
        elif isinstance(nodo, ast.Attribute):
            assert nodo.attr not in {"unlink", "rmdir", "rmtree", "move", "replace", "rename",
                                     "remove"}, nodo.attr
        elif isinstance(nodo, ast.Call) and isinstance(nodo.func, ast.Name):
            assert nodo.func.id not in {"eval", "exec", "compile"}


def test_el_modulo_no_habla_con_la_red():
    """Drive llega por GVFS: es una ruta del sistema de ficheros, no una llamada de red. `A8` sigue
    valiendo tal cual está escrita."""
    fuente = (pathlib.Path(__file__).parent / "archivador_cloud.py").read_text(encoding="utf-8")
    for prohibido in ("import requests", "import urllib", "import http.client", "from github",
                      "import socket"):
        assert prohibido not in fuente


def test_no_esta_conectado_al_ciclo_autonomo():
    """Aislado por ahora: ningún módulo del motor lo importa."""
    base = pathlib.Path(__file__).parent
    for modulo in ("ciclo_autonomo.py", "motor_autonomia.py", "orquestador.py", "review.py",
                   "revisores.py", "descubrimiento.py", "planificador.py", "agentes.py"):
        assert "archivador_cloud" not in (base / modulo).read_text(encoding="utf-8")


def test_un_nombre_que_delata_un_secreto_se_rechaza_aunque_no_este_en_la_lista(tmp_path):
    """Lo destapó un mutante que sobrevivía: `.env` se bloquea por su nombre exacto, así que la
    heurística de nombres sospechosos no la ejercitaba nadie. Un `notas_token_produccion.md` no
    figura en ninguna lista fija y no debe salir de la máquina."""
    raiz, drive = _repo(tmp_path), _drive(tmp_path)
    for nombre in ("notas_token_produccion.md", "api_key_respaldo.txt", "mi_password.md",
                   "credential_dump.md", "clave_private.md"):
        f = raiz / "docs" / nombre
        f.write_text("da igual el contenido\n", encoding="utf-8")
        r = ac.archivar(raiz, "99_ARCHIVO", [f], destino=drive)
        assert r["copiados"] == 0, f"{nombre} no debía archivarse"
        assert r["ficheros"][0]["resultado"] == ac.RECHAZADO
        assert not (drive / "99_ARCHIVO" / nombre).exists()


def test_lo_que_no_es_un_fichero_regular_se_rechaza(tmp_path):
    """El otro mutante superviviente. Un directorio, un enlace roto o un socket no son artefactos de
    archivo, y tratarlos como tales rompería la copia a mitad."""
    raiz, drive = _repo(tmp_path), _drive(tmp_path)
    carpeta = raiz / "docs" / "subcarpeta"
    carpeta.mkdir()
    r = ac.archivar(raiz, "99_ARCHIVO", [carpeta], destino=drive)
    assert r["copiados"] == 0 and r["ficheros"][0]["resultado"] == ac.RECHAZADO
    roto = raiz / "docs" / "enlace_roto.md"
    roto.symlink_to(raiz / "docs" / "no_existe.md")
    r = ac.archivar(raiz, "99_ARCHIVO", [roto], destino=drive)
    assert r["copiados"] == 0 and r["ficheros"][0]["resultado"] == ac.RECHAZADO


def test_la_lista_negra_se_aplica_dentro_de_la_raiz_no_por_encima(tmp_path):
    """Lo encontró la primera prueba real contra Drive, no las unitarias: este repositorio vive bajo
    `.claude/worktrees/`, y mirar la ruta **absoluta** hacía que dos segmentos prohibidos bloqueasen
    el árbol entero. La raíz declarada define el ámbito; lo de más arriba no es asunto del
    archivador. Dentro, la lista negra sigue mandando."""
    contenedor = tmp_path / ".claude" / "worktrees"
    raiz = contenedor / "repo"
    (raiz / "docs").mkdir(parents=True)
    legitimo = raiz / "docs" / "informe.md"
    legitimo.write_text("# informe\n", encoding="utf-8")
    drive = _drive(tmp_path)
    r = ac.archivar(raiz, "99_ARCHIVO", [legitimo], destino=drive)
    assert r["copiados"] == 1, "un fichero legítimo no puede quedar bloqueado por dónde esté el repo"
    # Y dentro de la raíz, la lista negra sigue aplicándose igual.
    anidado = raiz / "worktrees" / "otro.md"
    anidado.parent.mkdir(parents=True)
    anidado.write_text("x", encoding="utf-8")
    assert ac.archivar(raiz, "99_ARCHIVO", [anidado], destino=drive)["copiados"] == 0


# ========================= la copia se demuestra, no se supone (DR-CLOUD-2) =========================
#
# El hueco que cerró la auditoría: se calculaba el hash del **origen** y se usaba para decidir
# idempotencia, pero nadie releía lo efectivamente escrito. Una escritura truncada o corrupta —Drive
# por GVFS no es transaccional— pasaba por éxito. Ahora la copia solo se declara buena si el destino,
# releído del disco, tiene el mismo hash que el origen.


def _copia_defectuosa(contenido):
    """Sustituye la escritura real por una que miente: escribe otra cosa, o nada."""
    def _falsa(origen, destino):
        if contenido is None:
            return 0                      # ni siquiera crea el fichero
        destino.write_bytes(contenido)
        return len(contenido)
    return _falsa


def test_una_copia_correcta_queda_confirmada_por_relectura(tmp_path):
    raiz, drive = _repo(tmp_path), _drive(tmp_path)
    origen = raiz / "docs" / "informe.md"
    r = ac.archivar(raiz, "06_BACKUPS", [origen], destino=drive)
    f = r["ficheros"][0]
    assert f["resultado"] == ac.COPIADO and r["ok"] is True
    assert f["verificado"] is True, "la copia debe demostrarse releyendo el destino"
    assert f["hash_destino"] == f["hash"] == hashlib.sha256(origen.read_bytes()).hexdigest()


def test_un_destino_con_contenido_distinto_es_error(tmp_path, monkeypatch):
    """Escritura corrupta: lo que llegó no es lo que se quería archivar."""
    raiz, drive = _repo(tmp_path), _drive(tmp_path)
    origen = raiz / "docs" / "informe.md"
    monkeypatch.setattr(ac, "_copiar", _copia_defectuosa(b"otra cosa distinta\n"))
    r = ac.archivar(raiz, "06_BACKUPS", [origen], destino=drive)
    f = r["ficheros"][0]
    assert f["resultado"] == ac.ERROR and f["verificado"] is False
    assert r["ok"] is False and r["copiados"] == 0
    assert any("verificacion" in e.lower() or "discrepancia" in e.lower() for e in r["errores"])


def test_un_destino_truncado_es_error(tmp_path, monkeypatch):
    """El fallo típico de un medio lento: la escritura se corta a mitad."""
    raiz, drive = _repo(tmp_path), _drive(tmp_path)
    origen = raiz / "docs" / "informe.md"
    monkeypatch.setattr(ac, "_copiar", _copia_defectuosa(origen.read_bytes()[:4]))
    r = ac.archivar(raiz, "06_BACKUPS", [origen], destino=drive)
    assert r["ficheros"][0]["resultado"] == ac.ERROR and r["ok"] is False


def test_un_destino_que_no_llego_a_existir_es_error(tmp_path, monkeypatch):
    raiz, drive = _repo(tmp_path), _drive(tmp_path)
    origen = raiz / "docs" / "informe.md"
    monkeypatch.setattr(ac, "_copiar", _copia_defectuosa(None))
    r = ac.archivar(raiz, "06_BACKUPS", [origen], destino=drive)
    f = r["ficheros"][0]
    assert f["resultado"] == ac.ERROR and f["verificado"] is False
    assert not (drive / "06_BACKUPS" / "informe.md").exists()


def test_ante_discrepancia_el_origen_sigue_intacto_y_el_destino_no_se_borra(tmp_path, monkeypatch):
    """Fail-closed: se informa del fallo, no se «arregla». Borrar el destino sería destruir evidencia
    de lo que ocurrió, y tocar el origen es justo lo que un archivador nunca hace."""
    raiz, drive = _repo(tmp_path), _drive(tmp_path)
    origen = raiz / "docs" / "informe.md"
    antes = origen.read_bytes()
    monkeypatch.setattr(ac, "_copiar", _copia_defectuosa(b"corrupto\n"))
    ac.archivar(raiz, "06_BACKUPS", [origen], destino=drive)
    assert origen.read_bytes() == antes, "el origen no se toca"
    assert (drive / "06_BACKUPS" / "informe.md").read_bytes() == b"corrupto\n", (
        "el destino defectuoso se conserva como evidencia, no se borra")


def test_el_versionado_tambien_se_verifica(tmp_path):
    """La segunda vía de escritura no puede quedarse sin la garantía."""
    raiz, drive = _repo(tmp_path), _drive(tmp_path)
    origen = raiz / "docs" / "informe.md"
    ac.archivar(raiz, "06_BACKUPS", [origen], destino=drive)
    origen.write_text("# informe\notro contenido\n", encoding="utf-8")
    r = ac.archivar(raiz, "06_BACKUPS", [origen], destino=drive)
    f = r["ficheros"][0]
    assert f["resultado"] == ac.VERSIONADO and f["verificado"] is True
    assert f["hash_destino"] == f["hash"]


def test_ya_archivado_tambien_declara_su_verificacion(tmp_path):
    """Si ya estaba, la comprobación de igualdad **es** la verificación: el destino se releyó."""
    raiz, drive = _repo(tmp_path), _drive(tmp_path)
    origen = raiz / "docs" / "informe.md"
    ac.archivar(raiz, "06_BACKUPS", [origen], destino=drive)
    f = ac.archivar(raiz, "06_BACKUPS", [origen], destino=drive)["ficheros"][0]
    assert f["resultado"] == ac.YA_ARCHIVADO and f["verificado"] is True
    assert f["hash_destino"] == f["hash"]
