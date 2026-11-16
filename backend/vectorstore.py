"""Vector store Chroma con persistencia local."""
import chromadb

_client = None


def get_collection(chroma_dir: str, name: str):
    """Abre (o crea) la colección persistente.

    Sin función de embedding por defecto: Chroma 1.x trae MiniLM local
    (384 dims) y fijaría esa dimensión aunque nuestros vectores Jina sean
    de 1024. Con EF=None la dimensión la definen los vectores explícitos.
    """
    global _client
    if _client is None:
        _client = chromadb.PersistentClient(path=chroma_dir)
    return _client.get_or_create_collection(name=name,
                                            embedding_function=None)


def count_chunks(chroma_dir: str, name: str) -> int:
    """Número de fragmentos indexados (0 si el índice no existe)."""
    try:
        return get_collection(chroma_dir, name).count()
    except Exception:
        return 0
