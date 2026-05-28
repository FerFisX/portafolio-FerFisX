# Adrian.AI — Portafolio para aplicar a Meru (AI Engineer)

> Construido para demostrar que sé llevar IA a producción.
> No es un sitio estático con frases bonitas: cada demo corre sobre AWS Bedrock, Lambda y vector store custom (numpy en S3).

[Sitio en vivo](#) · [Diagrama de arquitectura](frontend/assets/architecture.svg) · [Plan para Meru](#por-qué-meru)

---

## ¿Qué hay acá?

```
.
├── frontend/                 → Sitio estático (HTML + CSS + JS, sin framework)
│   ├── index.html
│   ├── css/                  → main + chat widget
│   ├── js/                   → main + particles + chat
│   └── assets/               → favicon, diagrama SVG
│
├── backend/
│   ├── lambdas/              → Python 3.12, serverless
│   │   ├── chat/             → Agente con tool use + RAG
│   │   ├── router/           → Router multimodelo (Claude/Haiku/Llama)
│   │   ├── rag/              → Ingesta de docs → embeddings → numpy index en S3
│   │   ├── contact/          → Form → SES (con TL;DR generado por LLM)
│   │   ├── workflow/         → Step Functions worker
│   │   └── shared/           → Bedrock client, prompts, retrieval (numpy), observability
│   ├── knowledge_base/       → Markdown que se indexa como vectores en S3
│   └── evals/                → Golden set + LLM-as-judge harness
│
├── infrastructure/           → AWS CDK (Python). Todo el deploy en código.
│   ├── app.py
│   ├── stacks/               → data, api, frontend, workflow
│   └── cdk.json
│
└── docs/
    ├── ARCHITECTURE.md
    ├── DEPLOYMENT.md
    └── DECISIONS.md
```

## ¿Qué demuestra?

| Requisito del puesto                            | Dónde está demostrado                                          |
|-------------------------------------------------|----------------------------------------------------------------|
| LLMs en producción (Claude, GPT, Gemini)        | `backend/lambdas/router/` + `shared/bedrock_client.py`         |
| RAG y bases vectoriales                         | `backend/lambdas/rag/` + `shared/retrieval.py` (cosine + keyword hybrid, numpy en RAM) |
| Agentes con LLMs (tool use)                     | `backend/lambdas/chat/handler.py` (loop con 3 tools)           |
| Python                                          | Todo el backend + IaC                                           |
| Make / n8n / Zapier (workflow visual)           | `infrastructure/stacks/workflow_stack.py` (Step Functions)     |
| Prompt engineering                              | `shared/prompts.py` (versionado, cacheado)                     |
| Evals                                           | `backend/evals/` (golden set + LLM-as-judge)                   |
| Mentalidad de producto / adopción               | Sección "Meru" del sitio + métricas en CloudWatch              |
| Blockchain / Web3                               | `knowledge_base/stablecoins_overview.md` + bot fintech mock    |

## Quick start

### 1. Probar el frontend localmente (sin AWS)
```bash
cd frontend
python -m http.server 8000
# Abre http://localhost:8000
```

El chatbot funciona en modo "mock" (respuestas pregrabadas) hasta que despliegues la stack.

### 2. Desplegar todo en AWS
```bash
cd infrastructure
python -m venv .venv && source .venv/bin/activate   # (Windows: .venv\Scripts\activate)
pip install -r requirements.txt

# Configurar AWS CLI con credenciales
aws configure

# Habilitar acceso a modelos Bedrock en la consola:
# https://console.aws.amazon.com/bedrock/home#/modelaccess
# Pide acceso a: claude-3-5-sonnet, claude-3-5-haiku, titan-embed-v2, llama3-1-70b

cdk bootstrap        # solo la primera vez en la cuenta/región
cdk deploy --all     # ~10 minutos
```

CDK imprimirá al final:
- `SiteURL` — la URL del portafolio en CloudFront
- `ApiUrl` — base URL del HTTP API
- `KBBucketName` — bucket donde subís docs para que se indexen automáticamente

### 3. Cargar la knowledge base
```bash
aws s3 cp backend/knowledge_base/ s3://adrian-ai-kb-<ACCOUNT>/ --recursive --exclude "*" --include "*.md"
```

Cada `.md` que subas dispara la Lambda `ingest`, que chunkea + embedea con Titan + guarda el índice en `s3://<bucket>/_index/`.

### 4. Correr los evals
```bash
cd backend
pip install boto3 opensearch-py requests
python -m evals.run_evals
```

Exit code `0` si el score promedio ≥ 4.0/5. CI-ready.

## Costos estimados

Con tráfico de demo (~100 conversaciones/día):

| Servicio                  | Estimado mensual |
|---------------------------|------------------|
| Lambda (chat/router/etc.) | < $1             |
| API Gateway HTTP          | < $1             |
| DynamoDB on-demand        | < $1             |
| S3 (KB docs + index)      | < $0.10          |
| CloudFront                | $1–3             |
| **Bedrock (Claude)**      | **$5–15**        |
| CloudWatch + X-Ray        | $2–5             |
| **Total**                 | **~$10–25/mes**  |

> **Decisión de costo**: El vector store es **numpy en RAM cargado desde S3**, no OpenSearch Serverless.
> Ahorro: ~$350/mes (OS Serverless tiene 2 OCUs mínimas). Ver `docs/DECISIONS.md` por el trade-off completo.
> Para una KB de ~50-500 chunks (este caso), numpy es más rápido y prácticamente gratis.

## Por qué Meru

Más detalle en el sitio (sección "05 / por qué meru") y en `backend/knowledge_base/adrian_profile.md`.

Resumen:
- Meru construye sobre **stablecoins + IA** — la intersección más interesante de fintech.
- El rol está enmarcado como **infraestructura, no proyecto paralelo**: esa es mi mentalidad.
- Mi stack se solapa 1:1 con lo que pide el puesto.
- Tengo un plan concreto de 30/60/90 días — está en el sitio y en el agente.

## Contacto

Mejor preguntale al agente del sitio. O escribime directo: `adrian@example.com`.
