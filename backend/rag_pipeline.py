"""Pipeline RAG: recuperar (Chroma+Jina) -> generar (Groq 120B, sin degradación).

Filtra citas contra el contexto: toda norma citada debe existir en los
fragmentos recuperados; si no, se elimina y, de ser necesario, el estado
baja a factibilidad. Nada llega al frontend sin este filtro.
"""
import json
import re
import time
import uuid

from groq import Groq

from config import settings
from embeddings import embed
from prompts import SYSTEM_PROMPT, VIGENTES, build_user_prompt
from schemas import QueryResponse
from vectorstore import get_collection


MAX_POR_DOC = 2

ACTOS_VIGENTES = list(VIGENTES)

RUTA_CRONO = ("cuand", "fecha", "plazo", "crono", "tiempo", "licita",
              "desiert", "precalifica", "adjudica", "compra", "adquisi",
              "inicio", "empieza", "2026", "2027", "2035", "operaci")


def _top(col, vec, n, donde=None):
    res = col.query(query_embeddings=[vec], n_results=n, where=donde)
    return list(zip(res["documents"][0], res["metadatas"][0]))


def retrieve(question: str) -> list[dict]:
    """Top-K con tope por documento + ruta de vigencia.

    1) Pide 3x top_k y conserva máximo 2 fragmentos por archivo en orden
    de ranking (diversidad: los grandes no saturan).
    2) Si la pregunta es de tiempos/proceso (términos RUTA_CRONO),
    mezcla hasta 2 fragmentos de ACTOS_VIGENTES (2025-2026), porque
    la similitud pura entierra los actos cortos bajo la narrativa
    EIA-2022. Enrutamiento por intención, práctica estándar RAG.
    """
    col = get_collection(settings.chroma_dir, settings.chroma_collection)
    vec = embed([question], settings.jina_api_key)[0]
    pares = _top(col, vec, settings.top_k * 3)
    out, por_doc, vistos = [], {}, set()
    for doc, meta in pares:
        arch = meta.get("archivo", "?")
        if por_doc.get(arch, 0) >= MAX_POR_DOC:
            continue
        por_doc[arch] = por_doc.get(arch, 0) + 1
        out.append({"texto": doc, "archivo": arch,
                    "pagina": meta.get("pagina", "?")})
        vistos.add((arch, meta.get("pagina", "?")))
        if len(out) >= settings.top_k:
            break
    ql = question.lower()
    if any(t in ql for t in RUTA_CRONO):
        n_nuevos = sum(1 for c in out if c["archivo"] in ACTOS_VIGENTES)
        if n_nuevos < 2:
            for doc, meta in _top(col, vec, 6,
                                  {"archivo": {"$in": ACTOS_VIGENTES}}):
                clave = (meta.get("archivo", "?"), meta.get("pagina", "?"))
                if clave in vistos:
                    continue
                out.append({"texto": doc, "archivo": meta.get("archivo", "?"),
                            "pagina": meta.get("pagina", "?")})
                vistos.add(clave)
                if sum(1 for c in out
                       if c["archivo"] in ACTOS_VIGENTES) >= 2:
                    break
    return out[:settings.top_k + 2]


def _call_groq(client: Groq, model: str, user_prompt: str) -> str:
    """Llama con JSON mode; si el modelo lo rechaza, reintenta plano."""
    try:
        resp = client.chat.completions.create(
            model=model,
            messages=[{"role": "system", "content": SYSTEM_PROMPT},
                      {"role": "user", "content": user_prompt}],
            temperature=settings.groq_temperature,
            response_format={"type": "json_object"},
        )
    except Exception:
        resp = client.chat.completions.create(
            model=model,
            messages=[{"role": "system", "content": SYSTEM_PROMPT},
                      {"role": "user", "content": user_prompt}],
            temperature=settings.groq_temperature,
        )
    content = resp.choices[0].message.content or ""
    return content[content.find("{"):content.rfind("}") + 1]


def generate(question: str, chunks: list[dict],
             perfil: str | None = None) -> dict:
    """Genera con el primario y reintenta con el fallback si difiere.

    Por defecto ambos apuntan a GPT-OSS 120B (config.py): no hay
    degradación a un modelo menor. Devuelve dict validado o lanza.
    """
    client = Groq(api_key=settings.groq_api_key)
    prompt = build_user_prompt(question, chunks, perfil)
    models = list(dict.fromkeys((settings.groq_model_primary,
                                 settings.groq_model_fallback)))
    last: Exception | None = None
    for model in models:
        try:
            return json.loads(_call_groq(client, model, prompt))
        except Exception as exc:
            last = exc
    raise RuntimeError(f"Groq falló en {models}: {last}")

def _cita_valida(cita: dict, ctx: str, chunks: list[dict]) -> bool:
    """La cita existe en el contexto o en las fuentes recuperadas.

    Tres formas válidas: norma jurídica (regla original + tolerancia de
    formato 'Ley 388 · Art. 61'), nombre oficial del documento (catálogo
    FUENTES de prompts.py) o [archivo] p.X de los fragmentos recuperados.
    Todas son atribución verificable; el nombre de archivo solo se tolera
    como respaldo para no tumbar respuestas con cita válida.
    """
    from prompts import FUENTES
    norma = cita.get("norma", "").lower()
    if norma[:24] in ctx:
        return True
    art = re.search(r"art\.?\s*(\d+)", norma)
    base = re.split(r"[·|\-(]", norma)[0].strip()
    if art and base and len(base) >= 6 and base[:12] in ctx \
            and re.search(r"\b" + art.group(1) + r"\b", ctx):
        return True
    for c in chunks:
        arch = (c.get("archivo", "") or "")
        oficial = FUENTES.get(arch, "").lower()
        if oficial and oficial in norma:
            return True
        base_arch = arch.lower().replace(".pdf", "")
        pag = str(c.get("pagina", "?"))
        if base_arch and base_arch in norma and pag in norma:
            return True
    return False


def filter_citations(data: dict, chunks: list[dict]) -> dict:
    """Conserva solo citas cuya norma aparece en el contexto."""
    ctx = " ".join(c["texto"] for c in chunks).lower()
    kept = [c for c in data.get("citations", [])
            if _cita_valida(c, ctx, chunks)]
    vistos, unicas = set(), []
    for c in kept:
        clave = c.get("norma", "").lower()
        if clave not in vistos:
            vistos.add(clave)
            unicas.append(c)
    kept = unicas
    data["citations"] = kept
    if not kept and data.get("situationStatus", {}).get("type") == "consolidado":
        data["situationStatus"]["type"] = "factibilidad"
        data["situationStatus"]["desc"] = (
            data["situationStatus"].get("desc", "")
            + " [Sin cita recuperada: el respaldo queda pendiente.]")
    return data


def answer(question: str, perfil: str | None = None) -> QueryResponse:
    """Orquesta retrieval + generación + filtro + validación Pydantic."""
    chunks = retrieve(question)
    if not chunks:
        raise RuntimeError("Índice vacío: ejecute ingestion.py primero.")
    data = filter_citations(generate(question, chunks, perfil), chunks)
    data["id"] = f"q-{uuid.uuid4().hex[:12]}-{int(time.time())}"
    return QueryResponse(**data)
