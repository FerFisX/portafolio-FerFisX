# Arquitectura — Adrian.AI Portafolio

## Vista general

```
┌─────────┐   ┌──────────────┐   ┌──────────────┐
│ Usuario │──▶│  CloudFront  │──▶│   S3 (static)│   ← Frontend
└─────────┘   │  + WAF + R53 │   └──────────────┘
                     │
                     ▼
              ┌──────────────┐    ┌─────────────────┐
              │ API Gateway  │───▶│ Lambda (Python) │
              │  HTTP API    │    │ chat / router / │
              │  (CORS)      │    │ contact         │
              └──────────────┘    └────────┬────────┘
                                           │
                       ┌───────────────────┼───────────────────┐
                       ▼                   ▼                   ▼
              ┌──────────────┐    ┌─────────────────┐  ┌──────────────┐
              │   Bedrock    │    │  S3 _index/     │  │  DynamoDB    │
              │  Claude 3.5  │◀───│  vectors.npy +  │  │  sessions    │
              │  Titan embed │    │  chunks.json    │  │  + TTL       │
              └──────────────┘    │ (in-RAM cosine) │  └──────────────┘
                                  └────────┬────────┘
                                           ▲
                                           │ (S3 event → embed → rebuild index)
                                  ┌────────┴───────┐
                                  │   S3 (KB docs) │
                                  │  Lambda ingest │
                                  └────────────────┘

                       ┌─────────────────────────────────────┐
                       │      Step Functions + EventBridge   │
                       │  (workflow estilo n8n / Make)       │
                       └─────────────────────────────────────┘

                       ┌─────────────────────────────────────┐
                       │  CloudWatch Logs · X-Ray · EMF      │
                       │  tokens · latency · cost · evals    │
                       └─────────────────────────────────────┘
```

## Componentes en detalle

### 1. Frontend
- **S3 + CloudFront**: estático, sin servidor que mantener.
- **HTML + CSS + JS vanilla**: cero build step, fácil de auditar, cold-start de "minutos" para deploy.
- **CloudFront Price Class 100**: solo edges en US/EU/CA — suficiente para una postulación.
- **Cache strategy**: assets cacheados agresivamente, `index.html` no-cache (para que un deploy se vea ya).
- **Config inyectado**: `config.js` se genera en deploy con la API URL real.

### 2. API
- **API Gateway HTTP API** (no REST): más barato y rápido. CORS nativo.
- **3 rutas**: `POST /chat`, `POST /router`, `POST /contact`.
- **Sin autenticación pública**: rate-limiting vía WAF en CloudFront cuando lo agreguemos (TODO).

### 3. Lambdas
Cada endpoint es una Lambda Python 3.12 separada. Razones:
- Cost attribution clara (puedo ver qué endpoint duele).
- Scaling independiente.
- Permisos IAM mínimos por función.

**Compartido** en `backend/lambdas/shared/`:
- `bedrock_client.py`: wrapper con retries, prompt caching, cost tracking.
- `prompts.py`: prompts versionados, source-controlled.
- `retrieval.py`: hybrid search (BM25 + vector) sobre OpenSearch.
- `observability.py`: structured logs + CloudWatch EMF metrics.

### 4. LLMs (Bedrock)
- **Modelo principal**: `claude-3-5-sonnet-v2`. Bueno para razonamiento + tool use.
- **Modelo cheap**: `claude-3-5-haiku` para tareas simples (clasificación, extracción).
- **Modelo open**: `llama3-1-70b` para comparar en el router demo.
- **Embeddings**: `titan-embed-v2` (1024 dim, normalizados).

**Prompt caching**: el system prompt está marcado con `cache_control={'type':'ephemeral'}`.
En conversaciones largas se reusa, bajando latencia ~80% y costo ~90%.

### 5. RAG (numpy en S3 — custom vector store)
- **Storage**: dos archivos en S3: `_index/vectors.npy` (matriz N×1024 float32, normalizados) + `_index/chunks.json` (text+metadata).
- **Retrieval**: cosine similarity en RAM (numpy dot product, pre-normalizado).
- **Hybrid**: cosine 70% + keyword score 30% (BM25-lite con regex). Atrapa tickers y términos exactos sin necesidad de full BM25.
- **Chunking**: paragraph-aware, ~500 tokens con 50 de overlap, code blocks atómicos.
- **Embedding**: Titan v2 (1024 dim, normalizados al embedear).
- **Ingest pipeline**: S3 upload → Lambda → walk all docs → chunk → embed → upload `vectors.npy` + `chunks.json` atomicamente.
- **Cold start**: ~150ms para descargar y `np.load` un índice de 50 chunks. Cacheado a nivel módulo entre invocaciones.

**Trade-offs frente a OpenSearch Serverless**:
- ✓ Cuesta ~$0 vs ~$350/mes mínimo de OS Serverless.
- ✓ Latencia ~50ms vs ~200ms (round-trip a OS).
- ✗ No escala más allá de unos ~50k chunks (RAM Lambda).
- ✗ No tiene BM25 puro, ni filtros complejos por metadata.

Cuándo migrar a OS Serverless / pgvector: si la KB supera ~10MB de vectores (~10k chunks), o si necesitamos analytics on top.

### 6. Estado conversacional (DynamoDB)
- **Tabla `sessions`**: `session_id` (PK), `history` (JSON), `ttl`.
- **TTL automático a 7 días**.
- **PAY_PER_REQUEST**: cero costo si no hay tráfico.

### 7. Workflows (Step Functions)
Demo de orquestación tipo n8n / Make pero serverless:
- `Choice` state para validar input.
- Llamada a Lambda con extracción LLM.
- Branch por confidence score (route ops / compliance / human-review).
- Retries + catch built-in.

Definido en JSON declarativo (no Python) — más fácil de visualizar y modificar para no-devs.

### 8. Observabilidad
- **Structured logs** en CloudWatch (JSON).
- **EMF metrics**: tokens, latencia, costo, eval-score por prompt-version.
- **X-Ray tracing** activo en todas las Lambdas.
- **Dashboards** (próximo paso): un dashboard por endpoint con p50/p95/p99, cost-per-request, error rate.

## Patrones de seguridad

- **IAM least-privilege**: cada Lambda solo puede invocar los modelos específicos que usa.
- **S3 buckets privados**: solo CloudFront via OAI tiene acceso.
- **DynamoDB encrypted at rest** (default).
- **No secrets en código**: todos los configs vienen de env vars (CDK los inyecta).
- **CORS restringido** (en prod, allowlist de dominios).
- **Input validation** en cada handler (length limits, regex, etc.).

## Patrones de costo

1. **Pay-per-use en todo**: Lambda, DynamoDB, API Gateway, CloudFront. Escala a $0 cuando nadie usa.
2. **Prompt caching**: ~80% reducción en latencia/costo para conversaciones largas.
3. **Model routing**: Haiku para clasificación, Sonnet para razonamiento. ~10x menos $ en operaciones simples.
4. **TTL en sesiones**: la tabla no crece indefinidamente.
5. **CloudFront cache**: el static se sirve desde edge, no se golpea S3 cada vez.

## Patrones de evolución

Si esto fuera Meru, los próximos pasos serían:

1. **Auth**: Cognito o Auth0 + JWT en API Gateway.
2. **Rate limiting**: WAF rules para evitar abuso del chat.
3. **Multi-tenant**: prefijo por `tenant_id` en DynamoDB y OpenSearch.
4. **Bedrock Guardrails**: filtros de contenido + PII redaction automática.
5. **Streaming**: response streaming vía Lambda Function URLs con SSE.
6. **Knowledge Bases gestionadas**: usar Bedrock Knowledge Bases si la complejidad de mantener OS crece.
7. **CI/CD**: GitHub Actions → CDK deploy. Evals corren antes del deploy.
