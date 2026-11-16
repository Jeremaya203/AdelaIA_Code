"""System prompt del pipeline RAG (reglas metodológicas de la tesis).

Solo contiene hechos verificados en sesión contra el corpus local:
- Ley 388 art.138 deroga expresamente el art.3 de la Ley 9 de 1989.
- Ley 388 art.61: 30 días hábiles sin acuerdo -> expropiación obligatoria
  (plazo de la entidad, NO derecho del ciudadano al contraavalúo).
- CGP art.399.2: demanda de expropiación en 3 meses; C-474/2023 exequible.
Todo lo demás debe salir del contexto recuperado o declararse inexistente.
"""
SYSTEM_PROMPT = """Eres AdelaIA, herramienta independiente de orientación sobre \
gestión predial de la Línea 2 del Metro de Bogotá. Respondes SOLO con un JSON \
válido con las claves: plainAnswer, situationStatus{type,title,desc}, \
actionSteps[{num,text}] (2 a 4), citations[{norma,resumen}] (1 a 6).

Reglas obligatorias:
1. Lenguaje cotidiano: 1-2 párrafos claros, sin tecnicismos oscuros.
2. Situación A (consolidado): derechos y procedimientos vigentes. Cita la \
norma recuperada con artículo exacto. Si el contexto no trae el dato, usa \
type=factibilidad, nunca inventes.
3. Situación B (factibilidad): si preguntan valores por m2, fechas de \
desalojo o cronogramas y EL CONTEXTO NO TRAE el dato, DECLARA que no \
existe y usa type=factibilidad. Pero los hitos del proceso 2025-2026 \
(desierta 20-ene-2026, precalificación, cronograma vigente) SÍ existen \
cuando el contexto trae el aviso, el acta, la precalificación o el \
cronograma: respóndelos como consolidado con su cita.
4. Hechos fijos verificados (úsalos solo si el contexto los respalda):
   - El art.3 de la Ley 9 de 1989 fue derogado por la Ley 388 de 1997 \
(art.138). Jamás lo cites como vigente.
   - Los 30 días hábiles del art.61 de la Ley 388 obligan a la entidad a \
iniciar expropiación si no hay acuerdo; no son un derecho automático del \
ciudadano a imponer su avalúo.
   - Expropiación judicial: demanda en 3 meses (CGP art.399.2); sin \
excepciones de ninguna clase (art.399.5, exequible según C-474/2023).
5. Cada citation.norma debe aparecer literalmente en el contexto \
recuperado. Prohibido citar jurisprudencia o plazos no presentes en él.
Usa el NOMBRE OFICIAL de la fuente (lista de abajo), nunca el nombre \
de archivo (.pdf). Si el dato viene de un documento del proyecto, cita \
p. ej. "Plan de Reasentamiento Involuntario L2MB (2024), p.196".
6. actionSteps: pasos procesales concretos; todo plazo en días hábiles \
debe venir del contexto o de los hechos fijos. Sin plazo verificado, \
no escribas números de días.
7. Si el número exacto de artículo no figura en el contexto, no lo \
cites: cita la norma general (p. ej. "Ley 388 de 1997") y usa \
type=factibilidad para ese punto.
8. Vigencia: ante fechas que choquen, valen los actos 2025-2026 sobre \
la narrativa EIA-2022 (el EIA describe 2022; el aviso, el acta, la \
precalificación y el cronograma traen lo vigente). Cita siempre la \
fecha del documento fuente junto al dato.
"""

JSON_SKELETON = """{"plainAnswer": "...", "situationStatus": {"type": \
"consolidado|factibilidad|proceso", "title": "...", "desc": "..."}, \
"actionSteps": [{"num": 1, "text": "..."}], "citations": [{"norma": "...", \
"resumen": "..."}]}"""

# Nombres oficiales para citar, leídos de las portadas de los PDF
# (nunca el nombre de archivo). Clave = basename en metadatos Chroma.
FUENTES = {
    "Ley_388_1997.pdf": "Ley 388 de 1997",
    "Ley_9_1989.pdf": "Ley 9 de 1989",
    "Decreto_1420_1998.pdf": "Decreto 1420 de 1998",
    "Ley_1437_2011_CPACA.pdf": "Ley 1437 de 2011 (CPACA)",
    "Ley_1564_2012_CGP.pdf": "Ley 1564 de 2012 (CGP)",
    "Ley_1682_2013.pdf": "Ley 1682 de 2013",
    "Ley_1742_2014.pdf": "Ley 1742 de 2014",
    "Ley_1882_2018.pdf": "Ley 1882 de 2018",
    "AP-DR-002_Politica_Reasentamiento_PLMB_V01.pdf":
        "Política de Reasentamiento AP-DR-002 (PLMB, V01)",
    "prg_l2mb_may2024.pdf":
        "Plan de Reasentamiento Involuntario L2MB (2024)",
    "aviso_desierta_l2mb_2026-01-20.pdf":
        "Aviso de declaratoria de desierto L2MB (EMB, 20-ene-2026)",
    "acta_cierre_precalificacion_l2mb_2026_OCR.pdf":
        "Acta de cierre de precalificación L2MB (2026) [capa OCR del proyecto]",
    "precalificacion_l2mb_2026-03-06.pdf":
        "Documento de Precalificación L2MB (06-mar-2026) [?: portada por leer]",
    "cronograma_emb_2026.pdf":
        "Cronograma EIA L2MB Cap. 17 (versión cuarto de datos) [?: por leer]",
    "EST 7 2LMB FINAL.pdf":
        "Diagnóstico de adquisición predial, Estación 7 L2MB (EMB) [?: por leer]",
    "EST 8 2LMB FINAL.pdf":
        "Diagnóstico de adquisición predial, Estación 8 L2MB (EMB) [?: por leer]",
    "EST 9 2LMB FINAL.pdf":
        "Diagnóstico de adquisición predial, Estación 9 L2MB (EMB) [?: por leer]",
    "MATRIZ DE DECISIÓN PREDIAL FINAL.pdf":
        "Matriz de decisión predial L2MB (EMB) [?: por leer]",
}


# Actos 2025-2026: prevalecen sobre la narrativa EIA-2022 en fechas
# y estado del proceso. Misma lista que rag_pipeline.ACTOS_VIGENTES.
VIGENTES = (
    "aviso_desierta_l2mb_2026-01-20.pdf",
    "acta_cierre_precalificacion_l2mb_2026_OCR.pdf",
    "precalificacion_l2mb_2026-03-06.pdf",
    "cronograma_emb_2026.pdf",
    "EST 7 2LMB FINAL.pdf",
    "EST 8 2LMB FINAL.pdf",
    "EST 9 2LMB FINAL.pdf",
    "MATRIZ DE DECISIÓN PREDIAL FINAL.pdf",
)


def build_user_prompt(question: str, chunks: list[dict],
                      perfil: str | None = None) -> str:
    """Ensambla contexto + pregunta + perfil opcional + esqueleto JSON.

    Los fragmentos de actos vigentes van en sección propia al inicio:
    el modelo los ve primero y la regla 8 les da prevalencia.
    Sin actos en contexto, el prompt es idéntico al anterior."""
    vig = [c for c in chunks if c["archivo"] in VIGENTES]
    resto = [c for c in chunks if c["archivo"] not in VIGENTES]

    def fmt(c, i):
        return (f"[Fuente {i}: {c['archivo']} p.{c['pagina']}] "
                f"{c['texto']}")
    bloques = ""
    if vig:
        bloques += ("DATOS VIGENTES 2025-2026 (prevalecen sobre el EIA-2022 "
                    "en fechas y estado del proceso):\n"
                    + "\n\n".join(fmt(c, i + 1)
                                  for i, c in enumerate(vig)) + "\n\n")
    bloques += ("Contexto recuperado:\n"
                + "\n\n".join(fmt(c, i + 1 + len(vig))
                              for i, c in enumerate(resto)))
    nombres = "; ".join(f"{a} = {FUENTES.get(a, a)}"
                        for a in dict.fromkeys(c["archivo"]
                                               for c in chunks))
    who = (f"\nPerfil del consultante: {perfil}. Adapta ejemplos y pasos "
           f"a su situación sin cambiar los hechos ni las citas."
           if perfil else "")
    return (f"{bloques}\n\nNombres oficiales para citar: "
            f"{nombres}.\n\nPregunta del ciudadano: "
            f"{question}{who}\n\nResponde con este JSON exacto:\n{JSON_SKELETON}")
