#!/usr/bin/env python3
"""Publicador de la AURA Project Bible (mandato del acta D12).

Genera en `publicado/` la versión HTML navegable y PDF de todo documento
aprobado (capítulos `Aprobado`, actas/brief `Vinculante`, ADRs `accepted`),
más los artefactos de navegación (INDICE, README, CHANGELOG, índice de ADRs).

Uso: python3 herramientas/publicar.py [--sin-pdf]
Requiere: python3-markdown; para PDF, google-chrome (headless).
"""
import os, re, sys, glob, html, shutil, subprocess

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HTML_DIR = os.path.join(RAIZ, 'publicado', 'html')
PDF_DIR = os.path.join(RAIZ, 'publicado', 'pdf')

try:
    import markdown
except ImportError:
    sys.exit('Falta python3-markdown (sudo apt install python3-markdown)')

CSS = """
body{font-family:Georgia,'Times New Roman',serif;max-width:52rem;margin:2rem auto;
padding:0 1.5rem;line-height:1.6;color:#1a1a2e;background:#fbfaf7}
h1,h2,h3{font-family:Helvetica,Arial,sans-serif;color:#0f3460}
h1{border-bottom:3px solid #0f3460;padding-bottom:.3rem}
h2{border-bottom:1px solid #ccc;padding-bottom:.2rem;margin-top:2rem}
table{border-collapse:collapse;width:100%;font-size:.92em;font-family:Helvetica,Arial,sans-serif}
th,td{border:1px solid #bbb;padding:.4rem .6rem;text-align:left;vertical-align:top}
th{background:#0f3460;color:#fff}
code{background:#eee9e0;padding:.1rem .3rem;border-radius:3px;font-size:.9em}
blockquote{border-left:4px solid #e94560;margin-left:0;padding:.2rem 1rem;background:#f4efe8}
a{color:#0f3460}
.pie{margin-top:3rem;border-top:1px solid #ccc;font-size:.85em;color:#666;
font-family:Helvetica,Arial,sans-serif}
.meta{background:#f4efe8;border:1px solid #ddd;border-radius:6px;padding:.6rem 1rem;
font-size:.85em;font-family:Helvetica,Arial,sans-serif}
"""

def separar_frontmatter(texto):
    if texto.startswith('---\n'):
        fin = texto.find('\n---\n', 4)
        if fin != -1:
            return texto[4:fin], texto[fin + 5:]
    return '', texto

def campo(fm, nombre):
    m = re.search(r'^%s:\s*"?([^"\n#]*)"?' % re.escape(nombre), fm, re.M)
    return m.group(1).strip() if m else ''

def es_publicable(fm, ruta_rel):
    base = os.path.basename(ruta_rel)
    if base in ('INDICE.md', 'README.md', 'CHANGELOG.md', 'plantilla-adr.md'):
        return base != 'plantilla-adr.md'
    estado = campo(fm, 'estado').lower()
    return estado.startswith(('aprobado', 'vinculante', 'accepted'))

def convertir(ruta_rel, fm, cuerpo):
    titulo = campo(fm, 'titulo') or campo(fm, 'documento') or os.path.basename(ruta_rel)[:-3]
    meta = ''
    if fm:
        filas = [(n, campo(fm, n)) for n in
                 ('version', 'estado', 'fecha', 'fecha_aprobacion', 'fecha-resolucion', 'autor', 'responsable', 'prioridad')]
        filas = [(n, v) for n, v in filas if v and v != '—']
        meta = '<div class="meta">' + ' · '.join(f'<b>{html.escape(n)}</b>: {html.escape(v)}' for n, v in filas) + '</div>'
    cuerpo_html = markdown.markdown(cuerpo, extensions=['tables', 'fenced_code', 'toc'])
    cuerpo_html = re.sub(r'href="([^"]+)\.md(#[^"]*)?"', r'href="\1.html\2"', cuerpo_html)
    prof = ruta_rel.count('/')
    inicio = '../' * prof + 'index.html'
    return f"""<!DOCTYPE html><html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(titulo)} — AURA Project Bible</title><style>{CSS}</style></head><body>
<p><a href="{inicio}">← Índice de la Bible</a></p>{meta}
{cuerpo_html}
<div class="pie">AURA Project Bible — generado automáticamente por herramientas/publicar.py (acta D12)</div>
</body></html>"""

def chrome():
    for b in ('google-chrome', 'google-chrome-stable', 'chromium', 'chromium-browser'):
        if shutil.which(b):
            return b
    return None

def main():
    con_pdf = '--sin-pdf' not in sys.argv
    for d in (HTML_DIR, PDF_DIR):
        os.makedirs(d, exist_ok=True)
    publicados = []
    candidatos = ['INDICE.md', 'README.md', 'CHANGELOG.md']
    for patron in ('decisiones/*.md', 'adr/*.md', 'docs/*/*.md'):
        candidatos += sorted(os.path.relpath(p, RAIZ) for p in glob.glob(os.path.join(RAIZ, patron)))
    for rel in candidatos:
        texto = open(os.path.join(RAIZ, rel), encoding='utf-8').read()
        fm, cuerpo = separar_frontmatter(texto)
        if not es_publicable(fm, rel):
            continue
        destino = os.path.join(HTML_DIR, rel[:-3] + '.html')
        os.makedirs(os.path.dirname(destino), exist_ok=True)
        open(destino, 'w', encoding='utf-8').write(convertir(rel, fm, cuerpo))
        publicados.append(rel)
    # índice navegable
    grupos = {}
    for rel in publicados:
        grupos.setdefault(os.path.dirname(rel) or 'raíz', []).append(rel)
    cuerpo = ['# AURA Project Bible — Documentación publicada\n',
              'Solo aparecen documentos **aprobados o vinculantes** (acta D12).\n']
    for grupo in sorted(grupos):
        cuerpo.append(f'\n## {grupo}\n')
        for rel in grupos[grupo]:
            cuerpo.append(f'- [{os.path.basename(rel)[:-3]}]({rel[:-3]}.html)')
    open(os.path.join(HTML_DIR, 'index.html'), 'w', encoding='utf-8').write(
        convertir('index.md', '', '\n'.join(cuerpo)))
    # PDFs
    pdf_ok = 0
    if con_pdf and (nav := chrome()):
        for rel in publicados:
            origen = os.path.join(HTML_DIR, rel[:-3] + '.html')
            destino = os.path.join(PDF_DIR, rel[:-3].replace('/', '--') + '.pdf')
            for extra in ([], ['--no-sandbox']):
                r = subprocess.run([nav, '--headless=new', '--disable-gpu', '--no-pdf-header-footer',
                                    f'--print-to-pdf={destino}', 'file://' + origen] + extra,
                                   capture_output=True, timeout=60)
                if os.path.exists(destino) and os.path.getsize(destino) > 0:
                    pdf_ok += 1
                    break
    print(f'Publicados: {len(publicados)} documentos HTML en publicado/html/ · {pdf_ok} PDF en publicado/pdf/')
    for rel in publicados:
        print(f'  - {rel}')

if __name__ == '__main__':
    main()
