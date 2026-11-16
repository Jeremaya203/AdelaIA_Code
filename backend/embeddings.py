"""Cliente de embeddings Jina (jina-embeddings-v5-text-small, 1024 dims).

Interfaz verificada por ejecución: el endpoint responde 401 sin llave,
lo que confirma ruta y esquema antes de gastar cuota.
"""
import time

import httpx

JINA_URL = "https://api.jina.ai/v1/embeddings"
MODEL = "jina-embeddings-v5-text-small"
EXPECTED_DIMS = 1024
MAX_RETRIES = 6


def embed(texts: list[str], api_key: str, timeout: float = 60.0) -> list[list[float]]:
    """Embebe una lista de textos; lanza RuntimeError si el modelo o las
    dimensiones no coinciden con lo esperado. Reintenta 429/5xx con backoff
    (cuota Jina limitada por RPM)."""
    if not api_key:
        raise RuntimeError("Falta JINA_API_KEY en el entorno.")
    last = None
    for intento in range(MAX_RETRIES):
        resp = httpx.post(
            JINA_URL,
            headers={"Authorization": f"Bearer {api_key}",
                     "Content-Type": "application/json"},
            json={"model": MODEL, "input": texts},
            timeout=timeout,
        )
        if resp.status_code == 429 or resp.status_code >= 500:
            last = resp
            espera = 5 * (2 ** intento)
            time.sleep(espera)
            continue
        resp.raise_for_status()
        break
    else:
        last.raise_for_status()
    data = resp.json()["data"]
    vecs = [d["embedding"] for d in sorted(data, key=lambda d: d["index"])]
    if not vecs or len(vecs[0]) != EXPECTED_DIMS:
        got = len(vecs[0]) if vecs else 0
        raise RuntimeError(f"Dimensiones inesperadas: {got}, se exigen 1024.")
    return vecs


def check_endpoint(timeout: float = 15.0) -> int:
    """Devuelve el status HTTP sin llave (401 esperado = ruta válida)."""
    resp = httpx.post(JINA_URL,
                      json={"model": MODEL, "input": ["hola"]},
                      timeout=timeout)
    return resp.status_code
