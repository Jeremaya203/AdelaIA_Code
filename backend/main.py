"""Servidor FastAPI AdelaIA: /api/query, /api/health + CORS."""
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from config import settings
from rag_pipeline import answer
from rate_limit import RateLimitMiddleware
from schemas import HealthResponse, QueryRequest, QueryResponse
from vectorstore import count_chunks

app = FastAPI(title="AdelaIA backend", version="0.1.0")
app.add_middleware(
    RateLimitMiddleware,
    max_req=settings.rate_limit_per_minute,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.origins,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


@app.get("/api/health", response_model=HealthResponse)
def health() -> HealthResponse:
    """Estado del servicio y del índice."""
    return HealthResponse(
        status="ok",
        rag_ready=settings.rag_ready,
        model_primary=settings.groq_model_primary,
        model_fallback=settings.groq_model_fallback,
        indexed_chunks=count_chunks(settings.chroma_dir,
                                    settings.chroma_collection),
    )


@app.post("/api/query", response_model=QueryResponse)
def query(req: QueryRequest) -> QueryResponse:
    """Responde con RAG; 503 honesto si faltan llaves o índice."""
    if not settings.rag_ready:
        raise HTTPException(status_code=503,
                            detail="Motor RAG sin configurar (.env).")
    try:
        return answer(req.question, req.perfil)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
