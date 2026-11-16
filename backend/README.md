# Backend AdelaIA (piloto)

FastAPI + ChromaDB (disco) + Jina `jina-embeddings-v5-text-small` (1024 dims)
+ Groq `openai/gpt-oss-120b` como modelo único (sin degradación a 20B
por decisión del autor 2026-09-09).
Sin LangChain por decisión escrita 2026-09-07 (menos dependencias, misma API).

## Puesta en marcha

```bash
cd app/backend
uv venv --python 3.12 && uv pip install -r requirements.txt
cp .env.example .env  # completar GROQ_API_KEY y JINA_API_KEY (nunca commitear)
uv run pytest -q
uv run uvicorn main:app --port 8000
```

## Endpoints

- `GET /api/health` → estado, llaves presentes, fragmentos indexados.
- `POST /api/query {"question": "..."}` → JSON del contrato del frontend.
  Sin `.env` o sin índice responde 503 honesto (nunca inventa).

## Ingesta piloto

```bash
uv run python ingestion.py   # indexa PILOT_DOCS, informa tokens medidos
```

Cuotas (declaradas antes de gastar): Groq cobra por token
(120B $0.15/$0.60 por 1M in/out); Jina descuenta del pool del proyecto.
La ingesta completa de 57k chunks NO está incluida (exige tier pago Jina).

## Reglas del motor

System prompt en `prompts.py`: solo hechos verificados contra el corpus
(art.3 Ley 9 derogado; 30 días art.61 como plazo de la entidad; CGP 399;
C-474/2023). `filter_citations` elimina citas ausentes del contexto y baja
a `factibilidad` si no hay respaldo. El mock del frontend con citas sin
verificar fue retirado de `app/src/App.tsx`.
