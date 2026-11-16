"""Ingesta v3: cortes por frase completa + auditoria de cobertura.

- Ningun fragmento termina a mitad de frase (solape = frases completas).
- Ninguna pagina con contenido (>=30 caracteres) queda fuera; las
  omitidas se reportan una por una.
- Por defecto DRY-RUN (cero cuota): informa cobertura por documento.
- Con --embed incrusta en colecciones NUEVAS (nunca toca las vigentes).
Uso: .venv/bin/python ingestion_v3.py [--embed COL] [--docs lista.txt]
"""
import os
import re
import sys

import tiktoken
from pypdf import PdfReader

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ingestion import page_text  # noqa: E402

ENC = tiktoken.get_encoding("cl100k_base")
MAX_TOK = 500
OVERLAP_TOK = 100
MIN_PAGE_CHARS = 30
LOTE_EMBED = 50


def incrustar_lotes(col, ids, cuerpos, metas, api_key):
    """Incrusta por lotes para no exceder el límite por petición."""
    from embeddings import embed
    for i in range(0, len(ids), LOTE_EMBED):
        j = ids[i:i + LOTE_EMBED]
        if j and len(col.get(ids=j)['ids']) == len(j):
            continue
        k2 = min(i + LOTE_EMBED, len(ids))
        vecs = embed(cuerpos[i:k2], api_key)
        col.upsert(ids=j, documents=cuerpos[i:k2],
                   metadatas=metas[i:k2], embeddings=vecs)

BASURA = re.compile(
    r'^\s*(Página \d+ de \d+|Formato [A-Z]+-FR[-\w]*|DO-FR[-\w.]*|'
    r'GL-FR[-\w.]*|Versión \d.*|EVA - Gestor Normativo.*|'
    r'Los datos publicados.*tienen carácter informativo.*|'
    r'El Departamento Administrativo.*no se hace responsable.*|'
    r'Nos encontramos en un proceso permanente.*)\s*$',
    re.IGNORECASE)


def limpiar(texto):
    """Quita pies/formatos/control de cambios; conserva el contenido."""
    texto = re.sub(r'Página \d+ de \d+', ' ', texto)
    texto = re.sub(r'_{5,}', ' ', texto)
    texto = re.sub(r'[A-ZÁÉÍÓÚÑ][\w\sáéíóúñ,\.]*?\d{4}\s+\d+\s+EVA\s*-\s*'
                   r'Gestor Normativo', ' ', texto)
    out = []
    for l in texto.split('\n'):
        s = l.strip()
        if not s:
            continue
        if BASURA.match(s):
            continue
        if re.match(r'^(Versión|Vigencia|Aprobación|Elaboró|Revisó|Código|G\s+\d{2}-\d{2}-\d{4})\b', s):
            continue
        if re.match(r'^[A-Z]\s+\d{2}-\d{2}-\d{4}\b', s):
            continue
        out.append(l)
    return '\n'.join(out)

ABREV = (r'art|arts|num|núm|p|pp|ej|dto|dtos|dr|dra|sr|sra|sres|vs|cap|'
         r'sec|inc|lit|ed|vol|coord|comp|trad|res|exp|sent|no|nros|fig|'
         r'tab|anexo|ley|decreto|articulo|artículo|srta|ud|uds|etc|'
         r'ibid|op|cit|cf|vid|sgtes|ss|párr|fracc')


def partir_frases(texto):
    """Divide en frases sin cortar abreviaturas comunes en español."""
    marca = '\ue000'
    t = re.sub(r'\b(' + ABREV + r')\.\s', lambda m: m.group(1) + marca,
               texto, flags=re.IGNORECASE)
    t = re.sub(r'(\d)\.\s(?=\d)', r'\1' + marca, t)  # 1. 2 -> decimales
    partes = re.split(r'(?<=[.!?…;:»”"\')\]])\s+(?=[A-ZÁÉÍÓÚÑ¿¡«"\'(\d])', t)
    out = []
    for p in partes:
        p = p.replace(marca, '. ').strip()
        p = re.sub(r'\s+', ' ', p)
        if p:
            out.append(p)
    return out


def empaquetar(frases):
    """Agrupa frases en ventanas <=500 tokens con solape de frases."""
    toks = [ENC.encode(f) for f in frases]
    ventanas, i = [], 0
    while i < len(frases):
        acc, n = [], 0
        j = i
        while j < len(frases) and n + len(toks[j]) <= MAX_TOK:
            acc.append(frases[j])
            n += len(toks[j])
            j += 1
        if j == i:  # frase sola mayor a 500: se conserva integra
            acc.append(frases[j])
            j += 1
        ventanas.append(' '.join(acc))
        if j >= len(frases):
            break
        # retrocede frases completas hasta ~100 tokens de solape
        k, s = j - 1, 0
        while k > i and s + len(toks[k]) <= OVERLAP_TOK:
            s += len(toks[k])
            k -= 1
        i = k + 1
    return ventanas


def html_texto(path):
    """Extrae texto de HTML sin dependencias nuevas."""
    from html.parser import HTMLParser

    class T(HTMLParser):
        def __init__(self):
            super().__init__(convert_charrefs=True)
            self.parts = []
            self.salto = {'p', 'li', 'h1', 'h2', 'h3', 'h4', 'tr', 'br',
                          'div', 'title'}

        def handle_starttag(self, tag, attrs):
            if tag in self.salto:
                self.parts.append('\n')

        def handle_data(self, data):
            s = data.strip()
            if s:
                self.parts.append(s + ' ')

    t = T()
    t.feed(open(path, encoding='utf-8', errors='replace').read())
    return re.sub(r'[ \t]+', ' ', ''.join(t.parts))


def auditar_documento(path, ini=None, fin=None):
    """Devuelve (ventanas, reporte). Sin red ni cuota."""
    base = os.path.basename(path)
    if base.lower().endswith(('.html', '.htm')):
        pags = [(1, html_texto(path))]
    else:
        reader = PdfReader(path)
        pags = [(n, pg) for n, pg in enumerate(reader.pages, start=1)]
        if ini is not None:
            pags = [(n, pg) for n, pg in pags if ini <= n <= (fin or n)]
        pags = [(n, page_text(path, n, pg)) for n, pg in pags]
    ventanas, omitidas, src_words = [], [], set()
    for pageno, text in pags:
        text = limpiar(text)
        if len(text.strip()) < MIN_PAGE_CHARS:
            omitidas.append(pageno)
            continue
        for w in re.findall(r'\w+', text.lower()):
            src_words.add(w)
        for j, v in enumerate(empaquetar(partir_frases(text))):
            ventanas.append((f'{base}#p{pageno}c{j}', v, pageno))
    idx_words = set()
    for _, v, _ in ventanas:
        for w in re.findall(r'\w+', v.lower()):
            idx_words.add(w)
    faltan = sorted(src_words - idx_words)
    cortes = sum(1 for _, v, _ in ventanas
                 if not re.search(r'[.!?…:;»”"\'\)\]]\s*$', v.strip()))
    return ventanas, {
        'archivo': base, 'paginas': len(pags), 'omitidas': omitidas,
        'ventanas': len(ventanas),
        'palabras_fuente': len(src_words),
        'palabras_indice': len(idx_words),
        'cobertura': round(100 * len(idx_words) / max(1, len(src_words)), 2),
        'faltan_ej': faltan[:10], 'cortes_mitad_frase': cortes}


def main():
    import json
    here = os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))))
    lista = sys.argv[sys.argv.index('--docs') + 1] \
        if '--docs' in sys.argv else None
    specs = [l.strip() for l in open(lista) if l.strip()] if lista else []
    todo = []
    for s in specs:
        rel, ini, fin = s, None, None
        if '#' in s:
            rel, rng = s.split('#', 1)
            a, b = rng.split('-', 1)
            ini, fin = int(a), int(b)
        todo.append((os.path.join(here, rel), ini, fin))
    rep = [auditar_documento(p, i, f) for p, i, f in todo]
    print(json.dumps([{'archivo': r['archivo'], 'paginas': r['paginas'],
                       'omitidas': r['omitidas'], 'ventanas': r['ventanas'],
                       'cobertura': r['cobertura'],
                       'faltan_ej': r['faltan_ej'],
                       'cortes': r['cortes_mitad_frase']} for _, r in rep],
                     ensure_ascii=False, indent=1))
    if '--embed' in sys.argv:
        from config import settings
        from vectorstore import get_collection
        nombre_col = sys.argv[sys.argv.index('--embed') + 1]
        col = get_collection(settings.chroma_dir, nombre_col)
        tv, tid = 0, 0
        for (ventanas, r) in rep:
            arch = r['archivo']
            ids = [x[0] for x in ventanas]
            cuerpos = [x[1] for x in ventanas]
            metas = [{'archivo': arch, 'pagina': x[2]} for x in ventanas]
            antes = col.count()
            incrustar_lotes(col, ids, cuerpos, metas,
                            settings.jina_api_key)
            tv += col.count() - antes
            tid += sum(len(ENC.encode(x[1])) for x in ventanas)
        print(f'EMBED col={nombre_col} nuevas={tv} tokens={tid}')


if __name__ == '__main__':
    main()
