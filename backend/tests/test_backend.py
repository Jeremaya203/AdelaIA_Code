"""Tests offline del backend (sin llaves ni red)."""
import re

from fastapi.testclient import TestClient

from ingestion import chunk_tokens
from main import app
from prompts import SYSTEM_PROMPT, build_user_prompt
from schemas import QueryRequest, QueryResponse

client = TestClient(app)


def test_chunk_overlap_invariant():
    """Solape de 50 entre ventanas consecutivas de 500."""
    toks = list(range(1200))
    wins = chunk_tokens(toks)
    assert wins[0] == list(range(500))
    assert wins[1][:50] == wins[0][-50:]
    assert all(len(w) <= 500 for w in wins)


def test_query_contract_minimal():
    """El contrato exige 2-4 pasos y >=1 cita."""
    good = {"id": "q-1", "plainAnswer": "Texto claro.",
            "situationStatus": {"type": "factibilidad", "title": "Título",
                                "desc": "Descripción"},
            "actionSteps": [{"num": 1, "text": "Paso uno."},
                            {"num": 2, "text": "Paso dos."}],
            "citations": [{"norma": "Ley 388 de 1997 · Art. 61",
                           "resumen": "Resumen breve."}]}
    QueryResponse(**good)


def test_prompt_prohibe_vigencia_art3():
    """El system prompt debe fijar la derogación del art.3 Ley 9."""
    assert "derogado" in SYSTEM_PROMPT
    assert "138" in SYSTEM_PROMPT


def test_prompt_exige_base_comercios():
    """Regla 9 (auditoría Camilo A5/C10): sin base del PRG, factibilidad."""
    assert "subsidio de" in SYSTEM_PROMPT and "arriendo" in SYSTEM_PROMPT
    assert "factibilidad" in SYSTEM_PROMPT


def test_prompt_exige_fuente_desembolso():
    """Regla 10: plazos de pago solo con cita literal del contexto."""
    assert "desembolso" in SYSTEM_PROMPT.lower() or "Desembolsos" in SYSTEM_PROMPT


def test_prompt_pagos_no_ligados_a_obra():
    """Regla 11 (caso A6): pagos desligados del avance salvo cita."""
    assert "avance de la obra" in SYSTEM_PROMPT


def test_prompt_avaluo_con_verificacion():
    """Regla 12 (caso A4): mencionar verificación previa del avalúo."""
    assert "verificación" in SYSTEM_PROMPT


def test_respuesta_sin_citas_degrada_sin_500():
    """Filtro que vacía citas + esquema que lo admite: 200 factibilidad."""
    from rag_pipeline import filter_citations
    from schemas import QueryResponse
    data = {"plainAnswer": "Texto claro de prueba.",
            "situationStatus": {"type": "consolidado", "title": "Título",
                                "desc": "Descripción"},
            "actionSteps": [{"num": 1, "text": "Paso uno."},
                            {"num": 2, "text": "Paso dos."}],
            "citations": [{"norma": "Fuente inexistente",
                           "resumen": "Resumen."}]}
    out = QueryResponse(**{"id": "q-test",
                            **filter_citations(data, [{"texto": "otro texto",
                                                       "archivo": "ley.pdf",
                                                       "pagina": 1}])})
    assert out.situationStatus.type == "factibilidad"
    assert out.citations == []


def test_prompt_sin_plazos_inventados():
    """Ningún plazo en días hábiles escrito en el prompt (regla 6)."""
    nums = re.findall(r"(\d+)\s*días hábiles", SYSTEM_PROMPT)
    assert nums == [], nums


def test_health_sin_llaves(monkeypatch):
    """Sin llaves: ok + rag_ready False + 503 honesto en /api/query."""
    monkeypatch.setattr("config.settings.groq_api_key", "")
    monkeypatch.setattr("config.settings.jina_api_key", "")
    r = client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok" and body["rag_ready"] is False
    q = client.post("/api/query", json={"question": "¿hola?"})
    assert q.status_code == 503


def test_perfil_opcional():
    """El perfil viaja del request al prompt sin alterar hechos."""
    req = QueryRequest(question="¿Tengo derecho a compensación?",
                       perfil="arrendatario")
    assert req.perfil == "arrendatario"
    assert QueryRequest(question="¿Tengo derecho a compensación?").perfil is None
    chunks = [{"texto": "Ley 388 de 1997 art. 61.", "archivo": "ley.pdf",
               "pagina": 1}]
    assert "arrendatario" in build_user_prompt("¿?", chunks, "arrendatario")
    assert "Perfil" not in build_user_prompt("¿?", chunks, None)


def test_filter_citas_formato_articulo():
    """La cita 'Ley 388 · Art. 61' vale si contexto trae ley y artículo."""
    from rag_pipeline import filter_citations
    chunks = [{"texto": "Ley 388 de 1997, artículo 61: oferta y expropiación.",
               "archivo": "contexto.pdf", "pagina": 5}]
    data = {"citations": [{"norma": "Ley 388 de 1997 · Art. 61",
                           "resumen": "Plazo de 30 días."}],
            "situationStatus": {"type": "consolidado", "title": "T",
                                "desc": "D"}}
    out = filter_citations(data, chunks)
    assert len(out["citations"]) == 1
    data2 = {"citations": [{"norma": "Ley 999 de 2099 · Art. 1",
                            "resumen": "Inexistente."}],
             "situationStatus": {"type": "consolidado", "title": "T",
                                 "desc": "D"}}
    out2 = filter_citations(data2, chunks)
    assert out2["citations"] == []
    assert out2["situationStatus"]["type"] == "factibilidad"


def test_filter_citas_fuente_documental():
    """La cita [archivo] p.X vale si ese fragmento fue recuperado."""
    from rag_pipeline import filter_citations
    chunks = [{"texto": "Cronograma de adquisiciones.", "archivo": "prg.pdf",
               "pagina": 196}]
    data = {"citations": [{"norma": "prg.pdf p.196", "resumen": "Pasos."}],
            "situationStatus": {"type": "consolidado", "title": "T",
                                "desc": "D"}}
    assert len(filter_citations(data, chunks)["citations"]) == 1
    data["citations"] = [{"norma": "otro.pdf p.1", "resumen": "X"}]
    out = filter_citations(data, chunks)
    assert out["citations"] == []


def test_rate_limit_429(monkeypatch):
    """Más de N POST /api/query por minuto devuelve 429 honesto."""
    import main
    from rate_limit import RateLimitMiddleware
    monkeypatch.setattr("config.settings.groq_api_key", "")
    monkeypatch.setattr("config.settings.jina_api_key", "")
    app2 = main.app
    estados = []
    for _ in range(main.settings.rate_limit_per_minute + 2):
        r = client.post("/api/query", json={"question": "¿hola?"})
        estados.append(r.status_code)
    assert 429 in estados
    assert all(s in (503, 429) for s in estados)
    assert isinstance(app2.user_middleware, list)
    assert any(m.cls is RateLimitMiddleware for m in app2.user_middleware)


def test_filter_citas_nombre_oficial():
    """El nombre oficial del catálogo vale aunque no esté en el texto."""
    from rag_pipeline import filter_citations
    chunks = [{"texto": "Compensaciones por reasentamiento.",
               "archivo": "AP-DR-002_Politica_Reasentamiento_PLMB_V01.pdf",
               "pagina": 283}]
    data = {"citations": [{
        "norma": "Política de Reasentamiento AP-DR-002 (PLMB, V01), p.283",
        "resumen": "Plazo de 15 días."}],
        "situationStatus": {"type": "consolidado", "title": "T",
                            "desc": "D"}}
    assert len(filter_citations(data, chunks)["citations"]) == 1
