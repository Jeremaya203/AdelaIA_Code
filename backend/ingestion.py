"""Ingesta piloto: PDF -> páginas -> chunks 500/50 -> Jina -> Chroma.

Soporta rangos de páginas con sufijo #inicio-fin (1-indexed).
Mide e informa tokens consumidos antes de cerrar (regla de cuotas).
"""
import os
import subprocess
import sys
import tiktoken
from pypdf import PdfReader

from config import settings
from embeddings import embed
from vectorstore import get_collection

ENC = tiktoken.get_encoding("cl100k_base")
CHUNK_TOKENS = 500
OVERLAP_TOKENS = 50


def parse_doc(spec: str) -> tuple[str, int | None, int | None]:
    """Separa ruta y rango opcional #ini-fin."""
    if "#" in spec:
        path, rng = spec.split("#", 1)
        ini, fin = rng.split("-", 1)
        return path, int(ini), int(fin)
    return spec, None, None


def page_text(path: str, pageno: int, page) -> str:
    """Extrae texto: compara pypdf y pdftotext (poppler) y usa el más
    completo. pypdf falla en silencio con fuentes CFF (devuelve poco
    texto); poppler las maneja. Sin poppler, solo pypdf."""
    text = (page.extract_text() or "").strip()
    try:
        proc = subprocess.run(
            ["pdftotext", "-layout", "-f", str(pageno), "-l", str(pageno),
             path, "-"],
            capture_output=True, text=True, timeout=120)
        if proc.returncode == 0:
            alt = proc.stdout.strip()
            if len(alt) > len(text):
                return alt
    except (OSError, subprocess.SubprocessError):
        pass
    return text


def chunk_tokens(tokens: list[int]) -> list[list[int]]:
    """Ventana deslizante de 500 con solape de 50."""
    out, i = [], 0
    step = CHUNK_TOKENS - OVERLAP_TOKENS
    while i < len(tokens):
        out.append(tokens[i:i + CHUNK_TOKENS])
        if i + CHUNK_TOKENS >= len(tokens):
            break
        i += step
    return out


def ingest() -> dict:
    """Indexa PILOT_DOCS; devuelve conteos y tokens medidos."""
    if not settings.rag_ready:
        raise RuntimeError("Faltan GROQ_API_KEY o JINA_API_KEY (.env).")
    col = get_collection(settings.chroma_dir, settings.chroma_collection)
    total_chunks, total_tokens, docs = 0, 0, 0
    here = os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))))  # raiz del repo (app/backend/)
    for spec in settings.pilot_doc_list:
        rel, ini, fin = parse_doc(spec)
        path = os.path.join(here, rel)
        reader = PdfReader(path)
        pages = list(enumerate(reader.pages, start=1))
        if ini is not None:
            pages = [p for p in pages if ini <= p[0] <= (fin or p[0])]
        for pageno, page in pages:
            text = page_text(path, pageno, page)
            if len(text) < 200:
                continue
            toks = ENC.encode(text)
            total_tokens += len(toks)
            ids, bodies, metas = [], [], []
            for j, win in enumerate(chunk_tokens(toks)):
                bodies.append(ENC.decode(win))
                ids.append(f"{os.path.basename(path)}#p{pageno}c{j}")
                metas.append({"archivo": os.path.basename(path),
                              "pagina": pageno})
            if ids and len(col.get(ids=ids)["ids"]) == len(ids):
                continue  # pagina ya indexada; ahorra cuota Jina
            vecs = embed(bodies, settings.jina_api_key)
            col.upsert(ids=ids, documents=bodies, metadatas=metas,
                       embeddings=vecs)
            total_chunks += len(ids)
        docs += 1
    _ = embed(["verificación"], settings.jina_api_key)  # valida modelo+dims
    return {"docs": docs, "chunks": total_chunks,
            "tokens_medidos": total_tokens}


if __name__ == "__main__":
    info = ingest()
    print(f"OK docs={info['docs']} chunks={info['chunks']} "
          f"tokens_txt={info['tokens_medidos']}")
    sys.exit(0)
