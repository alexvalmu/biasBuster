<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="docs/brand/logo-dark.svg">
    <img src="docs/brand/logo-light.svg" alt="biasbuster" width="340">
  </picture>
</p>

<p align="center"><em>Who paid for this paper?</em></p>

Sube el PDF de un estudio médico y un conjunto de agentes investiga si sus autores o su financiación tienen relación con la industria (farmacéuticas, fabricantes de dispositivos…) y si el paper lo declara. El resultado es un informe con estructura fija y una puntuación de riesgo reproducible, publicado en `/report/{sha256}`.

## Arquitectura

| Pieza | Tecnología | Dónde |
|---|---|---|
| Frontend | React + Vite + TS | Firebase Hosting |
| API | FastAPI (`APP_ROLE=api`) | Cloud Run |
| Agentes | LangGraph + LangChain, LLMs open source vía OpenRouter (`APP_ROLE=worker`) | Cloud Run + Cloud Tasks |
| BBDD | Postgres 16 + pgvector | VM e2-micro → Cloud SQL |

```
extract ─▶ enrich ─┬─▶ funding_investigator ───────────┐
                   └─▶ author_investigator × N (Send) ──┴─▶ synthesize + score
```

- **extract**: un LLM lee del PDF los autores y las secciones de Funding y COI, de forma literal.
- **enrich**: sin LLM. Consulta Crossref, Europe PMC, OpenAlex, PubMed y ClinicalTrials.gov.
- **investigators**: un agente por autor más uno de financiación, en paralelo, con tools de OpenAlex, ORCID, PubMed, Open Payments y Tavily.
- **synthesize**: consolida los hallazgos. **Se descarta cualquier evidencia cuya URL no haya devuelto realmente una tool**, que es la principal protección contra fuentes inventadas.
- **score**: puntuación determinista en Python (`app/agents/nodes/scoring.py`).

El contrato del informe vive en `backend/app/schemas/report.py`. Los tipos del frontend se generan a partir de él.

## Desarrollo local

```bash
cp .env.example .env          # rellena OPENROUTER_API_KEY y TAVILY_API_KEY
docker compose up --build     # db :5432 · api :8000 · worker :8001
cd frontend && npm install && npm run dev   # http://localhost:5173
```

- Informe de ejemplo, sin gastar en LLM: `docker compose exec api python -m app.devtools.seed` y abre `/report/dddd…` (64 `d`).
- Tests: `docker compose exec api pytest`.
- Regenerar los tipos del frontend tras cambiar el esquema:
  ```bash
  docker compose exec api python -c 'import json; from app.main import app; print(json.dumps(app.openapi(), indent=1))' > backend/openapi.json
  cd frontend && npm run gen:types
  ```

> **macOS + OrbStack/Docker Desktop**: si el repo está en `~/Documents`, da permiso a OrbStack en *Ajustes del Sistema → Privacidad y seguridad → Archivos y carpetas*. Si no, los contenedores con volúmenes se quedan en "Created".

## Despliegue

Los despliegues se hacen al hacer merge de un PR en `main`, tras aprobarlos en el environment `production` de GitHub. Configuración inicial de GCP en [`infra/README.md`](infra/README.md).

## Control de costes

- Deduplicación por hash: cada PDF se analiza una sola vez.
- Rate limit por IP, límite global diario (`MAX_DAILY_ANALYSES`) y reCAPTCHA v3 opcional.
- Máximo de autores investigados (`MAX_AUTHORS_INVESTIGATED`) y de búsquedas web por análisis.
- Caché de las APIs externas en Postgres (`http_cache`).
- `analyses.cost_usd` registra el coste de OpenRouter de cada análisis.
