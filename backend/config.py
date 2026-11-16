"""Configuración del backend AdelaIA.

Toda llave sale del entorno (.env local, nunca commiteado).
Sin llaves, el servidor arranca igual pero /api/query responde 503 honesto.
"""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Ajustes leídos del entorno."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    groq_api_key: str = ""
    jina_api_key: str = ""
    groq_model_primary: str = "openai/gpt-oss-120b"
    # Sin degradación a 20B por decisión del autor (2026-09-09): el modelo
    # menor pierde precisión jurídica y eleva el riesgo de alucinación.
    groq_model_fallback: str = "openai/gpt-oss-120b"
    groq_temperature: float = 0.3
    cors_origins: str = "http://localhost:5173"
    chroma_dir: str = "./chroma_db"
    chroma_collection: str = "adelaia_operativo"
    pilot_docs: str = ""
    top_k: int = 6
    rate_limit_per_minute: int = 30

    @property
    def origins(self) -> list[str]:
        """Orígenes CORS como lista."""
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def pilot_doc_list(self) -> list[str]:
        """Documentos piloto como lista."""
        return [d.strip() for d in self.pilot_docs.split(",") if d.strip()]

    @property
    def rag_ready(self) -> bool:
        """True solo si hay llaves para recuperar y generar."""
        return bool(self.groq_api_key and self.jina_api_key)


settings = Settings()
