# API AdelaIA (FastAPI + Chroma + Groq/Jina por entorno).
# Sin llaves ni índice responde 503 honesto (fail-closed, regla 44).
FROM python:3.12-slim

WORKDIR /srv
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY config.py main.py rag_pipeline.py prompts.py schemas.py embeddings.py \
    ingestion.py vectorstore.py rate_limit.py ./

# El índice Chroma viaja por volumen (se genera en local con ingestion.py
# y se sube por rsync; no va en la imagen ni en git).
VOLUME ["/srv/chroma_db"]
EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
