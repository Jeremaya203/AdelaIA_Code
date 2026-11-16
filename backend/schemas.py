"""Modelos Pydantic v2 del contrato API (espejo del frontend App.tsx)."""
from typing import Literal
from pydantic import BaseModel, Field


class QueryRequest(BaseModel):
    """Pregunta del ciudadano + perfil opcional (diagnóstico diferenciado)."""

    question: str = Field(min_length=3, max_length=1000)
    perfil: Literal["propietario", "poseedor", "arrendatario",
                    "comerciante", "otro"] | None = None


class SituationStatus(BaseModel):
    """Estado de la situación: norma consolidada o factibilidad sin dato."""

    type: Literal["factibilidad", "proceso", "consolidado"]
    title: str = Field(min_length=3, max_length=160)
    desc: str = Field(min_length=3, max_length=600)


class ActionStep(BaseModel):
    """Paso procesal secuencial."""

    num: int = Field(ge=1, le=6)
    text: str = Field(min_length=3, max_length=400)


class LegalCitation(BaseModel):
    """Cita con respaldo en el corpus recuperado."""

    norma: str = Field(min_length=3, max_length=160)
    resumen: str = Field(min_length=3, max_length=400)
    link: str | None = Field(default=None, max_length=500)


class QueryResponse(BaseModel):
    """Respuesta estructurada para el frontend."""

    id: str
    plainAnswer: str = Field(min_length=3, max_length=1500)
    situationStatus: SituationStatus
    actionSteps: list[ActionStep] = Field(min_length=2, max_length=4)
    # Sin citas: degradación honesta a factibilidad (filtro las elimina
    # todas y el frontend oculta la sección). Nunca 500 por lista vacía.
    citations: list[LegalCitation] = Field(min_length=0, max_length=6)


class HealthResponse(BaseModel):
    """Estado del servicio."""

    status: str
    rag_ready: bool
    model_primary: str
    model_fallback: str
    indexed_chunks: int
