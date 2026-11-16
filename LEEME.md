# AdelaIA: código fuente del prototipo

Este repositorio acompaña al trabajo final de maestría *AdelaIA. La asimetría de comprensión que la transparencia no cierra: un prototipo experimental de mediación normativa para la gestión predial del Metro de Bogotá* (Maestría en Gobierno Urbano, Universidad Nacional de Colombia, 2026). Se publica para que cualquier lector pueda ver cómo se produjeron las respuestas evaluadas en los anexos G, J, K, L, M y N.

El prototipo está en línea en <https://app.provident-ia.com>. Es un ejercicio académico y no constituye asesoría jurídica.

## Qué versión es esta

`backend/` corresponde a la **versión del 18 de septiembre de 2026** (confirmación `8a5a2bf`). Con esa versión se generaron las respuestas que revisó la auditoría jurídica (Anexo L) y la corrida calificada a ciegas (Anexo M).

## Contenido

- **`backend/`**: el servicio que responde las consultas.
  - Configuración: `config.py` y `.env.example`, sin llaves.
  - Ingesta del corpus: `ingestion.py`.
  - Representación vectorial: `embeddings.py` y `vectorstore.py`.
  - Recuperación, generación y filtro de citas: `rag_pipeline.py`.
  - Instrucción del sistema: `prompts.py`.
  - Esquemas de entrada y salida: `schemas.py`.
  - Límite de peticiones: `rate_limit.py`.
  - API: `main.py`.
  - Pruebas: `tests/`.
  - Dependencias y construcción: `requirements.txt` y `Dockerfile`.
- **`prompts_versiones/`**: las tres versiones de la instrucción del sistema que estuvieron vigentes en las fechas relevantes, tomadas del historial y nombradas con su confirmación:

| Archivo | Fecha | Qué se evaluó con ella |
|---|---|---|
| `prompts_10-sep_2bf42e6.py` | 10-sep-2026 | Respuestas de la auditoría técnico-predial (Anexo K) |
| `prompts_14-sep_4fe5e52.py` | 14-sep-2026 | Versión intermedia: fija la colección `adelaia_operativo`. **Es la que transcribe el §8 del Anexo E** |
| `prompts_18-sep_8a5a2bf.py` | 18-sep-2026 | Añade las reglas 9 a 12, derivadas de la auditoría técnica. Respuestas de la auditoría jurídica (Anexo L) y de la corrida a ciegas (Anexo M). Es idéntica a `backend/prompts.py` |

## Notas para leer el código

- **Índice operativo.** La colección `adelaia_operativo` (2.641 fragmentos, 18 documentos listados en `.env.example`) se construyó con `ingestion.py`: ventanas fijas de 500 tokens con solape de 50.
- **`ingestion_v3.py` no construyó el índice evaluado.** Es una ingesta posterior y experimental, con cortes por frase completa y auditoría de cobertura. Por defecto corre sin incrustar (modo *dry-run*) y nunca toca las colecciones vigentes. Se incluye como registro de la línea de mejora que el trabajo declara.
- **Hechos normativos fijados en la instrucción.** La regla 4 de `prompts.py` fija a mano hechos normativos verificados por el autor. El trabajo la llama «capa de hechos normativos preverificados» y discute su efecto sobre la evaluación de fidelidad: cuatro de los quince casos trampa coinciden con hechos de esa capa.

## Qué no contiene, y por qué

- **Credenciales.** Las llaves de Groq y Jina se leen del entorno (`.env`, que no se publica).
- **El índice vectorial y el corpus.** El índice pesa cientos de megabytes, y el corpus reúne documentos de terceros cuyo régimen de publicación no corresponde a este trabajo. El Anexo E declara la composición del índice.
- **El frontend y el sitio web.**

## Cómo ejecutarlo

```bash
cd backend
python -m venv .venv && .venv/bin/pip install -r requirements.txt
cp .env.example .env          # completar GROQ_API_KEY y JINA_API_KEY
.venv/bin/python -m pytest -q # 15 pruebas; la primera vez descarga el tokenizador de tiktoken
.venv/bin/uvicorn main:app --port 8000
```

Sin llaves o sin índice, `/api/query` responde 503: el servicio no inventa respuestas.

## Derechos

© 2026 Fabián Orlando López Cruz. Todos los derechos reservados. El código se publica para su consulta y verificación académica. No se concede permiso de copia, modificación ni redistribución sin autorización escrita del autor.

## Advertencia sobre reproducibilidad

Ejecutar este código no reproduce las respuestas evaluadas. El modelo generador (GPT-OSS 120B en Groq) se consume como servicio externo, su versión no queda fijada por el cliente, y la temperatura empleada (0,3) no elimina la variabilidad entre ejecuciones. La corrida del 17 de septiembre, con tres repeticiones por caso, documenta esa variación: dos de los quince casos cambiaron de veredicto entre repeticiones (ver Anexo M).
